"""Serve Agora on the loopback interface with no third-party dependencies."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import webbrowser

import agora
from local_app import App
import run_state

WEB = Path(__file__).resolve().parent / 'web'


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, app, port=8765):
        self.app = app
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status, data, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, write=False):
        if self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            self.reply(403, {'error': 'Use the local address printed by Agora.'})
            return False
        origin = self.headers.get('Origin')
        if (write and origin != self.server.origin) or (origin and origin != self.server.origin):
            self.reply(403, {'error': 'Only the local Agora page can make this request.'})
            return False
        if self.path.startswith('/api/') and not secrets.compare_digest(self.headers.get('X-Agora-Token', ''), self.server.token):
            self.reply(403, {'error': 'Reload the Agora page to reconnect.'})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        try:
            if self.path == '/':
                text = (WEB / 'index.html').read_text(encoding='utf-8').replace('__AGORA_TOKEN__', self.server.token)
                self.reply(200, text.encode('utf-8'), 'text/html; charset=utf-8')
            elif self.path in ('/app.js', '/style.css'):
                kind = 'text/javascript' if self.path.endswith('.js') else 'text/css'
                self.reply(200, (WEB / self.path[1:]).read_bytes(), kind + '; charset=utf-8')
            elif self.path == '/api/state':
                self.reply(200, {'job': self.server.app.state(), 'runs': self.server.app.history(), 'default_rules': agora.DEFAULT_RULES})
            elif self.path.startswith('/api/runs/'):
                self.reply(200, self.server.app.detail(self.path.removeprefix('/api/runs/')))
            elif self.path.startswith('/api/download/'):
                parts = self.path.removeprefix('/api/download/').split('/')
                if len(parts) != 2 or parts[1] not in ('report.md', 'transcript.json'):
                    raise ValueError('Unknown download.')
                folder = self.server.app.folder(parts[0])
                path = (folder / parts[1]).resolve()
                if path.parent != folder:
                    raise ValueError('Invalid download path.')
                with run_state.io_lock:
                    data = path.read_bytes()
                self.reply(200, data, 'text/plain; charset=utf-8', parts[0] + '-' + parts[1])
            else:
                self.reply(404, {'error': 'Not found.'})
        except (ValueError, OSError, run_state.StateError) as exc:
            self.reply(400, {'error': str(exc) if not isinstance(exc, OSError) else 'Saved discussion is not available yet.'})

    def do_POST(self):
        if not self.allowed(write=True):
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072 or self.headers.get('Content-Type') != 'application/json':
                raise ValueError('Expected JSON settings up to 128 KiB.')
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected discussion settings.')
            actions = {'/api/plan': self.server.app.plan, '/api/start': self.server.app.start,
                       '/api/stop': lambda _: self.server.app.stop()}
            if self.path not in actions:
                self.reply(404, {'error': 'Not found.'})
                return
            self.reply(200, actions[self.path](payload))
        except (ValueError, OSError, run_state.StateError) as exc:
            self.reply(400, {'error': str(exc) if not isinstance(exc, OSError) else 'The local request could not be completed.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('Port must be between 0 and 65535.')
    app = App()
    try:
        server = Server(app, args.port)
    except OSError:
        print('Could not open the local server. Try another --port.')
        return 1
    print(f'Agora is ready at {server.origin}', flush=True)
    print('Closing the browser keeps the discussion running. Ctrl+C stops after the current answer.', flush=True)
    if not args.no_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        app.stop()
    finally:
        server.server_close()
        if app.thread:
            app.thread.join()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
