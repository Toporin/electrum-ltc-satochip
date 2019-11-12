from decimal import Decimal

from electrum_ltc.util import (format_satoshis, format_fee_satoshis, parse_URI,
                               is_hash256_str, chunks, is_ip_address, list_enabled_bits)

from . import ElectrumTestCase


class TestUtil(ElectrumTestCase):

    def test_format_satoshis(self):
        self.assertEqual("0.00001234", format_satoshis(1234))

    def test_format_satoshis_negative(self):
        self.assertEqual("-0.00001234", format_satoshis(-1234))

    def test_format_fee_float(self):
        self.assertEqual("1.7", format_fee_satoshis(1700/1000))

    def test_format_fee_decimal(self):
        self.assertEqual("1.7", format_fee_satoshis(Decimal("1.7")))

    def test_format_fee_precision(self):
        self.assertEqual("1.666",
                         format_fee_satoshis(1666/1000, precision=6))
        self.assertEqual("1.7",
                         format_fee_satoshis(1666/1000, precision=1))

    def test_format_satoshis_whitespaces(self):
        self.assertEqual("     0.0001234 ",
                         format_satoshis(12340, whitespaces=True))
        self.assertEqual("     0.00001234",
                         format_satoshis(1234, whitespaces=True))

    def test_format_satoshis_whitespaces_negative(self):
        self.assertEqual("    -0.0001234 ",
                         format_satoshis(-12340, whitespaces=True))
        self.assertEqual("    -0.00001234",
                         format_satoshis(-1234, whitespaces=True))

    def test_format_satoshis_diff_positive(self):
        self.assertEqual("+0.00001234",
                         format_satoshis(1234, is_diff=True))

    def test_format_satoshis_diff_negative(self):
        self.assertEqual("-0.00001234", format_satoshis(-1234, is_diff=True))

    def _do_test_parse_URI(self, uri, expected):
        result = parse_URI(uri)
        self.assertEqual(expected, result)

    def test_parse_URI_address(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv'})

    def test_parse_URI_only_address(self):
        self._do_test_parse_URI('LectrumELqJWMECz7W2iarBpT4VvAPqwAv',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv'})


    def test_parse_URI_address_label(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?label=electrum%20test',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'label': 'electrum test'})

    def test_parse_URI_address_message(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?message=electrum%20test',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'message': 'electrum test', 'memo': 'electrum test'})

    def test_parse_URI_address_amount(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?amount=0.0003',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'amount': 30000})

    def test_parse_URI_address_request_url(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?r=http://domain.tld/page?h%3D2a8628fc2fbe',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'r': 'http://domain.tld/page?h=2a8628fc2fbe'})

    def test_parse_URI_ignore_args(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?test=test',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'test': 'test'})

    def test_parse_URI_multiple_args(self):
        self._do_test_parse_URI('litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?amount=0.00004&label=electrum-test&message=electrum%20test&test=none&r=http://domain.tld/page',
                                {'address': 'LectrumELqJWMECz7W2iarBpT4VvAPqwAv', 'amount': 4000, 'label': 'electrum-test', 'message': u'electrum test', 'memo': u'electrum test', 'r': 'http://domain.tld/page', 'test': 'none'})

    def test_parse_URI_no_address_request_url(self):
        self._do_test_parse_URI('litecoin:?r=http://domain.tld/page?h%3D2a8628fc2fbe',
                                {'r': 'http://domain.tld/page?h=2a8628fc2fbe'})

    def test_parse_URI_invalid_address(self):
        self.assertRaises(BaseException, parse_URI, 'litecoin:invalidaddress')

    def test_parse_URI_invalid(self):
        self.assertRaises(BaseException, parse_URI, 'notlitecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv')

    def test_parse_URI_parameter_polution(self):
        self.assertRaises(Exception, parse_URI, 'litecoin:LectrumELqJWMECz7W2iarBpT4VvAPqwAv?amount=0.0003&label=test&amount=30.0')

    def test_is_hash256_str(self):
        self.assertTrue(is_hash256_str('09a4c03e3bdf83bbe3955f907ee52da4fc12f4813d459bc75228b64ad08617c7'))
        self.assertTrue(is_hash256_str('2A5C3F4062E4F2FCCE7A1C7B4310CB647B327409F580F4ED72CB8FC0B1804DFA'))
        self.assertTrue(is_hash256_str('00' * 32))

        self.assertFalse(is_hash256_str('00' * 33))
        self.assertFalse(is_hash256_str('qweqwe'))
        self.assertFalse(is_hash256_str(None))
        self.assertFalse(is_hash256_str(7))

    def test_chunks(self):
        self.assertEqual([[1, 2], [3, 4], [5]],
                         list(chunks([1, 2, 3, 4, 5], 2)))
        with self.assertRaises(ValueError):
            list(chunks([1, 2, 3], 0))

    def test_list_enabled_bits(self):
        self.assertEqual((0, 2, 3, 6), list_enabled_bits(77))
        self.assertEqual((), list_enabled_bits(0))

    def test_is_ip_address(self):
        self.assertTrue(is_ip_address("127.0.0.1"))
        self.assertTrue(is_ip_address("127.000.000.1"))
        self.assertTrue(is_ip_address("255.255.255.255"))
        self.assertFalse(is_ip_address("255.255.256.255"))
        self.assertFalse(is_ip_address("123.456.789.000"))
        self.assertTrue(is_ip_address("2001:0db8:0000:0000:0000:ff00:0042:8329"))
        self.assertTrue(is_ip_address("2001:db8:0:0:0:ff00:42:8329"))
        self.assertTrue(is_ip_address("2001:db8::ff00:42:8329"))
        self.assertFalse(is_ip_address("2001:::db8::ff00:42:8329"))
        self.assertTrue(is_ip_address("::1"))
        self.assertFalse(is_ip_address("2001:db8:0:0:g:ff00:42:8329"))
        self.assertFalse(is_ip_address("lol"))
        self.assertFalse(is_ip_address(":@ASD:@AS\x77\x22\xff¬!"))
