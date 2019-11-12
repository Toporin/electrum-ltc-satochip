import asyncio
import tempfile
from decimal import Decimal
import os
from contextlib import contextmanager
from collections import defaultdict
import logging

from electrum_ltc.network import Network
from electrum_ltc.ecc import ECPrivkey
from electrum_ltc import simple_config, lnutil
from electrum_ltc.lnaddr import lnencode, LnAddr, lndecode
from electrum_ltc.bitcoin import COIN, sha256
from electrum_ltc.util import bh2u, create_and_start_event_loop
from electrum_ltc.lnpeer import Peer
from electrum_ltc.lnutil import LNPeerAddr, Keypair, privkey_to_pubkey
from electrum_ltc.lnutil import LightningPeerConnectionClosed, RemoteMisbehaving
from electrum_ltc.lnutil import PaymentFailure, LnLocalFeatures
from electrum_ltc.lnrouter import LNPathFinder
from electrum_ltc.channel_db import ChannelDB
from electrum_ltc.lnworker import LNWallet
from electrum_ltc.lnmsg import encode_msg, decode_msg
from electrum_ltc.logging import console_stderr_handler
from electrum_ltc.lnworker import InvoiceInfo, RECEIVED, PR_UNPAID

from .test_lnchannel import create_test_channels
from . import ElectrumTestCase

def keypair():
    priv = ECPrivkey.generate_random_key().get_secret_bytes()
    k1 = Keypair(
            pubkey=privkey_to_pubkey(priv),
            privkey=priv)
    return k1

@contextmanager
def noop_lock():
    yield

class MockNetwork:
    def __init__(self, tx_queue):
        self.callbacks = defaultdict(list)
        self.lnwatcher = None
        self.interface = None
        user_config = {}
        user_dir = tempfile.mkdtemp(prefix="electrum-lnpeer-test-")
        self.config = simple_config.SimpleConfig(user_config, read_user_dir_function=lambda: user_dir)
        self.asyncio_loop = asyncio.get_event_loop()
        self.channel_db = ChannelDB(self)
        self.path_finder = LNPathFinder(self.channel_db)
        self.tx_queue = tx_queue

    @property
    def callback_lock(self):
        return noop_lock()

    register_callback = Network.register_callback
    unregister_callback = Network.unregister_callback
    trigger_callback = Network.trigger_callback

    def get_local_height(self):
        return 0

    async def broadcast_transaction(self, tx):
        if self.tx_queue:
            await self.tx_queue.put(tx)

class MockStorage:
    def put(self, key, value):
        pass

    def get(self, key, default=None):
        pass

    def write(self):
        pass

class MockWallet:
    storage = MockStorage()
    def set_label(self, x, y):
        pass

class MockLNWallet:
    storage = MockStorage()
    def __init__(self, remote_keypair, local_keypair, chan, tx_queue):
        self.chan = chan
        self.remote_keypair = remote_keypair
        self.node_keypair = local_keypair
        self.network = MockNetwork(tx_queue)
        self.channels = {self.chan.channel_id: self.chan}
        self.invoices = {}
        self.inflight = {}
        self.wallet = MockWallet()
        self.localfeatures = LnLocalFeatures(0)
        self.pending_payments = defaultdict(asyncio.Future)

    def get_invoice_status(self, key):
        pass

    @property
    def lock(self):
        return noop_lock()

    @property
    def peers(self):
        return {self.remote_keypair.pubkey: self.peer}

    def channels_for_peer(self, pubkey):
        return self.channels

    def get_channel_by_short_id(self, short_channel_id):
        with self.lock:
            for chan in self.channels.values():
                if chan.short_channel_id == short_channel_id:
                    return chan

    def save_channel(self, chan):
        print("Ignoring channel save")

    def on_channels_updated(self):
        pass

    def save_invoice(*args, is_paid=False):
        pass

    preimages = {}
    get_invoice_info = LNWallet.get_invoice_info
    save_invoice_info = LNWallet.save_invoice_info
    set_invoice_status = LNWallet.set_invoice_status
    save_preimage = LNWallet.save_preimage
    get_preimage = LNWallet.get_preimage
    _create_route_from_invoice = LNWallet._create_route_from_invoice
    _check_invoice = staticmethod(LNWallet._check_invoice)
    _pay_to_route = LNWallet._pay_to_route
    force_close_channel = LNWallet.force_close_channel
    get_first_timestamp = lambda self: 0

class MockTransport:
    def __init__(self, name):
        self.queue = asyncio.Queue()
        self._name = name

    def name(self):
        return self._name

    async def read_messages(self):
        while True:
            yield await self.queue.get()

class NoFeaturesTransport(MockTransport):
    """
    This answers the init message with a init that doesn't signal any features.
    Used for testing that we require DATA_LOSS_PROTECT.
    """
    def send_bytes(self, data):
        decoded = decode_msg(data)
        print(decoded)
        if decoded[0] == 'init':
            self.queue.put_nowait(encode_msg('init', lflen=1, gflen=1, localfeatures=b"\x00", globalfeatures=b"\x00"))

class PutIntoOthersQueueTransport(MockTransport):
    def __init__(self, name):
        super().__init__(name)
        self.other_mock_transport = None

    def send_bytes(self, data):
        self.other_mock_transport.queue.put_nowait(data)

def transport_pair(name1, name2):
    t1 = PutIntoOthersQueueTransport(name1)
    t2 = PutIntoOthersQueueTransport(name2)
    t1.other_mock_transport = t2
    t2.other_mock_transport = t1
    return t1, t2

class TestPeer(ElectrumTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        console_stderr_handler.setLevel(logging.DEBUG)

    def setUp(self):
        super().setUp()
        self.asyncio_loop, self._stop_loop, self._loop_thread = create_and_start_event_loop()
        self.alice_channel, self.bob_channel = create_test_channels()

    def tearDown(self):
        super().tearDown()
        self.asyncio_loop.call_soon_threadsafe(self._stop_loop.set_result, 1)
        self._loop_thread.join(timeout=1)

    def prepare_peers(self):
        k1, k2 = keypair(), keypair()
        t1, t2 = transport_pair(self.alice_channel.name, self.bob_channel.name)
        q1, q2 = asyncio.Queue(), asyncio.Queue()
        w1 = MockLNWallet(k1, k2, self.alice_channel, tx_queue=q1)
        w2 = MockLNWallet(k2, k1, self.bob_channel, tx_queue=q2)
        p1 = Peer(w1, k1.pubkey, t1)
        p2 = Peer(w2, k2.pubkey, t2)
        w1.peer = p1
        w2.peer = p2
        # mark_open won't work if state is already OPEN.
        # so set it to OPENING
        self.alice_channel.set_state("OPENING")
        self.bob_channel.set_state("OPENING")
        # this populates the channel graph:
        p1.mark_open(self.alice_channel)
        p2.mark_open(self.bob_channel)
        return p1, p2, w1, w2, q1, q2

    @staticmethod
    def prepare_invoice(w2 # receiver
            ):
        amount_sat = 100000
        amount_btc = amount_sat/Decimal(COIN)
        payment_preimage = os.urandom(32)
        RHASH = sha256(payment_preimage)
        info = InvoiceInfo(RHASH, amount_sat, RECEIVED, PR_UNPAID)
        w2.save_preimage(RHASH, payment_preimage)
        w2.save_invoice_info(info)
        lnaddr = LnAddr(
                    RHASH,
                    amount_btc,
                    tags=[('c', lnutil.MIN_FINAL_CLTV_EXPIRY_FOR_INVOICE),
                          ('d', 'coffee')
                         ])
        return lnencode(lnaddr, w2.node_keypair.privkey)

    def test_payment(self):
        p1, p2, w1, w2, _q1, _q2 = self.prepare_peers()
        pay_req = self.prepare_invoice(w2)
        async def pay():
            result = await LNWallet._pay(w1, pay_req)
            self.assertEqual(result, True)
            gath.cancel()
        gath = asyncio.gather(pay(), p1._message_loop(), p2._message_loop())
        async def f():
            await gath
        with self.assertRaises(asyncio.CancelledError):
            run(f())

    def test_channel_usage_after_closing(self):
        p1, p2, w1, w2, q1, q2 = self.prepare_peers()
        pay_req = self.prepare_invoice(w2)

        addr = w1._check_invoice(pay_req)
        route = run(w1._create_route_from_invoice(decoded_invoice=addr))

        run(w1.force_close_channel(self.alice_channel.channel_id))
        # check if a tx (commitment transaction) was broadcasted:
        assert q1.qsize() == 1

        with self.assertRaises(PaymentFailure) as e:
            run(w1._create_route_from_invoice(decoded_invoice=addr))
        self.assertEqual(str(e.exception), 'No path found')

        peer = w1.peers[route[0].node_id]
        # AssertionError is ok since we shouldn't use old routes, and the
        # route finding should fail when channel is closed
        async def f():
            await asyncio.gather(w1._pay_to_route(route, addr, pay_req), p1._message_loop(), p2._message_loop())
        with self.assertRaises(PaymentFailure):
            run(f())

def run(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop=asyncio.get_event_loop()).result()
