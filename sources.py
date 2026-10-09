"""Retrieve bounded public HTTPS documents without sending local credentials."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

MAX_BYTES = 512_000
MAX_TEXT = 12_000


class SourceError(ValueError):
    pass


def normalize(text):
    return ' '.join(text.split())


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise SourceError('Invalid source URL.')
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or parts.query):
            raise SourceError('Use a public HTTPS URL on port 443 without credentials or a query string.')
        host = parts.hostname.encode('idna').decode('ascii')
    except (ValueError, UnicodeError):
        raise SourceError('Invalid source URL.') from None
    if '%' in host or host.lower() == 'localhost' or host.lower().endswith('.localhost'):
        raise SourceError('Local hosts are not allowed.')
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise SourceError('Private and reserved addresses are not allowed.')
    authority = f'[{host}]' if ':' in host else host
    path = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
    return urlunsplit(('https', authority, path, '', ''))


def public_address(host):
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = [answer[4][0] for answer in answers]
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise SourceError('Host resolved to a private or reserved address.')
    return addresses[0]


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # Connect to the checked address while keeping TLS verification tied to the host.
        address = public_address(self.host)
        raw = socket.create_connection((address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def fetch(url, timeout=10):
    original = validate_url(url)
    current = original
    deadline = time.monotonic() + timeout
    for _ in range(4):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError('Source request timed out.')
        parts = urlsplit(current)
        connection = PublicHTTPSConnection(parts.hostname, timeout=remaining,
                                           context=ssl.create_default_context())
        try:
            connection.request('GET', parts.path or '/', headers={
                'User-Agent': 'Agora/0.1 (source retrieval)',
                'Accept': 'text/html, text/plain', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise SourceError('Redirect has no destination.')
                current = validate_url(urljoin(current, location))
                continue
            if response.status != 200:
                raise SourceError(f'Source returned HTTP {response.status}.')
            content_type = response.getheader('Content-Type', '').split(';')[0].lower()
            if content_type not in ('text/html', 'text/plain'):
                raise SourceError('Only HTML and plain text sources are supported.')
            if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise SourceError('Compressed responses are not supported.')
            chunks = []
            size = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceError('Source request timed out.')
                if connection.sock:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(16384, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise SourceError('Source exceeds the download limit.')
            charset = response.headers.get_content_charset() or 'utf-8'
            try:
                text = b''.join(chunks).decode(charset, errors='replace')
            except LookupError:
                raise SourceError('Unsupported source encoding.') from None
            if content_type == 'text/html':
                parser = PageText()
                parser.feed(text)
                text = ' '.join(parser.parts)
            text = normalize(text)
            if not text:
                raise SourceError('Source contains no readable text.')
            captured = text[:MAX_TEXT]
            return {'url': original, 'final_url': current, 'status': 'retrieved',
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'text': captured, 'truncated': len(text) > MAX_TEXT,
                    'sha256': hashlib.sha256(captured.encode()).hexdigest(),
                    'content_type': content_type}
        except (OSError, http.client.HTTPException):
            raise SourceError('Source request failed or timed out.') from None
        finally:
            connection.close()
    raise SourceError('Too many source redirects.')


def collect(urls):
    if len(urls) > 5:
        raise SourceError('Use at most five source URLs.')
    result = []
    for url in dict.fromkeys(urls):
        entry = {'id': f'S{len(result) + 1:02d}', 'url': url, 'status': 'unavailable', 'text': ''}
        try:
            entry.update(fetch(url))
        except SourceError as exc:
            entry['error'] = str(exc)
        result.append(entry)
    return result
