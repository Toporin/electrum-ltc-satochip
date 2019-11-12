#!/usr/bin/env python
# Electrum - lightweight Bitcoin client
# Copyright (C) 2014 Thomas Voegtlin
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from electrum_ltc.plugin import BasePlugin, hook
from electrum_ltc.logging import get_logger

import hashlib
import base64
import time
from xmlrpc.client import ServerProxy

_logger = get_logger(__name__)
server = ServerProxy('https://cosigner.electrum.org/', allow_none=True)

class Plugin(BasePlugin):

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)

    def is_available(self):
        return True
    
    # send the challenge and get the reply 
    @hook
    def do_challenge_response(self, d):
        
        id_2FA= d['id_2FA']
        msg= d['msg_encrypt']        
        replyhash= hashlib.sha256(id_2FA.encode('utf-8')).hexdigest()
        
        #purge server from old messages then sends message
        server.delete(id_2FA)
        server.delete(replyhash)
        server.put(id_2FA, msg)
        _logger.info(f"challenge sent to id_2FA:{id_2FA}")
                
        # wait for reply
        timeout= 180
        period=10
        reply= None
        while timeout>0:
            try:
                reply = server.get(replyhash)
            except Exception as e:
                _logger.info(f"Exception: cannot contact server - error: {str(e)}")
                continue
            if reply:
                _logger.info(f"received response from {replyhash}")
                _logger.info(f"response received: {reply}")
                d['reply_encrypt']=base64.b64decode(reply)
                server.delete(replyhash)
                break
            # poll every t seconds
            time.sleep(period)
            timeout-=period
        
        if reply is None:
            _logger.info(f"Error: Time-out without server reply...")
            d['reply_encrypt']= None #default 
    