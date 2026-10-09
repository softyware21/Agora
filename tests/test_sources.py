import socket
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from email.message import Message

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

    def test_unicode_paths_are_encoded_without_double_encoding(self):
        self.assertEqual(sources.validate_url('https://example.com/문서/%20'),
                         'https://example.com/%EB%AC%B8%EC%84%9C/%20')

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

    def response(self, status=200, headers=None, chunks=None):
        response = MagicMock()
        response.status = status
        response.headers = Message()
        for key, value in (headers or {'Content-Type': 'text/plain'}).items():
            response.headers[key] = value
        response.getheader.side_effect = response.headers.get
        response.read1.side_effect = chunks or [b'Example text.', b'']
        return response

    def test_redirect_to_private_host_is_blocked_before_second_connection(self):
        with patch.object(sources, 'PublicHTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = self.response(302, {'Location': 'https://127.0.0.1/'})
            with self.assertRaises(sources.SourceError):
                sources.fetch('https://example.org/')
            self.assertEqual(connection.call_count, 1)

    def test_content_limits_and_unsupported_formats(self):
        responses = [self.response(404), self.response(headers={'Content-Type': 'application/pdf'}),
                     self.response(headers={'Content-Type': 'text/plain', 'Content-Encoding': 'gzip'}),
                     self.response(chunks=[b'x' * (sources.MAX_BYTES + 1), b''])]
        for response in responses:
            with patch.object(sources, 'PublicHTTPSConnection') as connection:
                connection.return_value.getresponse.return_value = response
                with self.assertRaises(sources.SourceError):
                    sources.fetch('https://example.org/')

    def test_snapshot_has_date_hash_and_truncation_flag(self):
        with patch.object(sources, 'PublicHTTPSConnection') as connection:
            connection.return_value.getresponse.return_value = self.response(chunks=[b'x' * 13000, b''])
            result = sources.fetch('https://example.org/')
        self.assertEqual(len(result['text']), sources.MAX_TEXT)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['sha256']), 64)
        self.assertIn('retrieved_at', result)
