import socket
import unittest
from unittest.mock import patch

import sources


class SourceTests(unittest.TestCase):
    def test_rejects_local_urls_and_credentials(self):
        for url in ['http://example.com', 'file:///etc/passwd', 'https://127.0.0.1',
                    'https://[::1]', 'https://169.254.169.254', 'https://10.0.0.1',
                    'https://user:secret@example.com', 'https://example.com:8443',
                    'https://example.com?q=private', 'https://localhost',
                    'https://example.com/\r\nheader:value']:
            with self.subTest(url=url), self.assertRaises(sources.SourceError):
                sources.validate_url(url)

    def test_fragment_removed(self):
        self.assertEqual(sources.validate_url('https://example.com/page#section'), 'https://example.com/page')

    def test_dns_must_only_return_public_addresses(self):
        for addresses in [['127.0.0.1'], ['93.184.216.34', '10.0.0.1']]:
            entries = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443)) for ip in addresses]
            with patch.object(socket, 'getaddrinfo', return_value=entries), self.assertRaises(sources.SourceError):
                sources.public_address('example.com')

    def test_connect_pins_checked_ip_and_preserves_tls_hostname(self):
        with patch.object(sources, 'public_address', return_value='93.184.216.34'), \
                patch.object(socket, 'create_connection') as connect:
            connection = sources.PublicHTTPSConnection('example.com')
            with patch.object(connection._context, 'wrap_socket') as wrap:
                connection.connect()
                self.assertEqual(connect.call_args.args[0], ('93.184.216.34', 443))
                self.assertEqual(wrap.call_args.kwargs['server_hostname'], 'example.com')

    def test_html_scripts_are_not_included(self):
        parser = sources.PageText()
        parser.feed('<p>Hello <b>world</b></p><script>secret()</script><style>x</style>')
        self.assertEqual(sources.normalize(' '.join(parser.parts)), 'Hello world')

    def test_failed_sources_stay_unavailable(self):
        with patch.object(sources, 'fetch', side_effect=sources.SourceError('Blocked')):
            result = sources.collect(['https://example.com', 'https://example.com'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'unavailable')
        self.assertEqual(result[0]['id'], 'S01')
