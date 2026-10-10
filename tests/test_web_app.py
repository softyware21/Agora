import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from local_app import App
from web_app import Server


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = Server(App(self.temp.name), 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        base = {'X-Agora-Token': self.server.token, 'Origin': self.server.origin}
        if payload is not None:
            base['Content-Type'] = 'application/json'
        base.update(headers or {})
        connection.request('POST' if payload is not None else 'GET', path,
                           None if payload is None else json.dumps(payload), headers=base)
        response = connection.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        connection.close()
        return result

    def test_cross_origin_and_wrong_host_cannot_read_or_start(self):
        for headers in ({'Origin': 'https://example.org'}, {'Host': 'example.org'}, {'X-Agora-Token': 'wrong'}):
            with self.subTest(headers=headers), patch.object(self.server.app, 'start') as start:
                try:
                    self.assertEqual(self.request('/api/start', {'question': 'q'}, headers)[0], 403)
                except ConnectionError:
                    # Windows may reset a rejected POST while discarding its unread body.
                    pass
                self.assertEqual(self.request('/api/state', headers=headers)[0], 403)
                start.assert_not_called()

    def test_judgment_endpoint_uses_local_request_guards(self):
        with patch.object(self.server.app, 'save_judgment', return_value={'revision': 1}) as save:
            status, _, body = self.request('/api/judgment', {'run_id': 'fixture'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['revision'], 1)
            save.assert_called_once_with({'run_id': 'fixture'})
        with patch.object(self.server.app, 'save_judgment') as save:
            try:
                self.assertEqual(self.request('/api/judgment', {'run_id': 'fixture'}, {'X-Agora-Token': 'wrong'})[0], 403)
            except ConnectionError:
                pass
            save.assert_not_called()

    def test_preview_remains_offline(self):
        with patch.object(self.server.app, 'factory') as factory:
            status, _, body = self.request('/api/plan', {'question': 'q'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['calls'], 5)
        factory.assert_not_called()

    def test_root_token_and_security_headers(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(self.server.token.encode(), body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn(b'__AGORA_TOKEN__', body)

    def test_answer_formatter_is_served(self):
        status, headers, body = self.request('/answer.js')
        self.assertEqual(status, 200)
        self.assertIn('text/javascript', headers['Content-Type'])
        self.assertIn(b'function renderAnswer', body)
        self.assertEqual(self.request('/discussion.js')[0], 200)

    def test_only_explicit_assets_and_run_downloads_are_served(self):
        for path in ('/agora.py', '/../../auth.json', '/api/download/../auth.json', '/api/runs/../secret'):
            with self.subTest(path=path):
                self.assertIn(self.request(path)[0], (400, 404))

    def test_bad_or_large_body_never_starts_a_job(self):
        with patch.object(self.server.app, 'start') as start:
            self.assertEqual(self.request('/api/start', [], {})[0], 400)
            connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
            connection.request('POST', '/api/start', headers={
                'Origin': self.server.origin, 'X-Agora-Token': self.server.token,
                'Content-Type': 'application/json', 'Content-Length': '132000'})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            connection.close()
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
