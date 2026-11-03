import datetime as dt
import hashlib
import http.client
import http.server
import json
import os
import re
import ssl
import time
import urllib.parse
from pathlib import Path

NAME = re.compile(r'[a-z][a-z0-9-]{1,28}[a-z0-9]')
TOKEN = re.compile(r'[A-Za-z0-9._-]{16,16384}')
REASON = re.compile(r'[A-Za-z0-9]{1,64}')
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')


def log(line):
    print(line, flush=True)


class Denied(Exception):
    """A bounded, client-visible refusal: HTTP status plus a short reason code."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason if REASON.fullmatch(str(reason)) else 'Denied'


def require(ok, status, reason):
    if not ok:
        raise Denied(status, reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha256(encoded(value))


def _constant(name):
    raise ValueError('NonFiniteNumber')


def loads(raw, limit):
    """Strict JSON: bounded size, UTF-8, no duplicate keys and no NaN/Infinity."""
    require(isinstance(raw, (bytes, bytearray)) and len(raw) <= limit, 413, 'BodyTooLarge')

    def pairs(items):
        if len(items) != len({k for k, _ in items}):
            raise ValueError('DuplicateJSONKey')
        return dict(items)
    try:
        return json.loads(bytes(raw).decode('utf-8'), object_pairs_hook=pairs, parse_constant=_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Denied(400, 'InvalidJSON') from None


def now():
    return time.time()


def stamp(seconds):
    return dt.datetime.fromtimestamp(int(seconds), dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_stamp(value):
    require(isinstance(value, str) and STAMP.fullmatch(value), 403, 'InvalidTimestamp')
    return dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp()


def read_token(path):
    """Re-read a projected token for every use; never cache credentials."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise Denied(503, 'CredentialUnavailable') from None
    token = raw.decode('ascii', 'replace').strip()
    require(len(raw) <= 16384 and TOKEN.fullmatch(token), 503, 'CredentialUnavailable')
    return token


def header(items, name):
    """Return one header value; duplicated security headers are refused."""
    values = [v for k, v in items if k.lower() == name.lower()]
    require(len(values) <= 1, 400, 'DuplicateHeader')
    return values[0] if values else None


def remaining(deadline):
    left = deadline - time.monotonic()
    require(left > 0, 504, 'DeadlineExceeded')
    return left


def http_call(method, url, headers, body=None, *, deadline, max_bytes, ca_file=None, before_send=None):
    """One bounded HTTP exchange with no proxy, redirect or retry. Returns (status, body)."""
    target = urllib.parse.urlsplit(url)
    require(target.scheme in ('http', 'https') and target.hostname and target.username is None
            and target.password is None and not target.fragment, 502, 'InvalidUpstream')
    if target.scheme == 'https':
        connection = http.client.HTTPSConnection(target.hostname, target.port, timeout=remaining(deadline),
                                                 context=ssl.create_default_context(cafile=ca_file))
    else:
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=remaining(deadline))
    try:
        connection.connect()
        if before_send:
            before_send()
        connection.sock.settimeout(remaining(deadline))
        path = (target.path or '/') + ('?' + target.query if target.query else '')
        connection.request(method, path, body=body, headers=headers)
        # getresponse() detaches closing connections while the response owns their socket.
        response_socket = connection.sock
        with connection.getresponse() as response:
            data = bytearray()
            while not response.isclosed():
                response_socket.settimeout(remaining(deadline))
                chunk = response.read1(min(65536, max_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                require(len(data) <= max_bytes, 502, 'ResponseTooLarge')
            return response.status, bytes(data)
    except Denied:
        raise
    except (OSError, http.client.HTTPException):
        raise Denied(504 if time.monotonic() >= deadline else 502, 'UpstreamUnavailable') from None
    finally:
        connection.close()


class Kube:
    """Minimal Kubernetes API client: every call re-reads the projected token."""

    def __init__(self, token_file, ca_file, transport=http_call, timeout=5):
        host = os.environ.get('KUBERNETES_SERVICE_HOST', 'kubernetes.default.svc')
        host = '[' + host + ']' if ':' in host else host
        self.base = 'https://' + host + ':' + os.environ.get('KUBERNETES_SERVICE_PORT', '443')
        self.token_file, self.ca_file, self.transport, self.timeout = token_file, ca_file, transport, timeout

    def call(self, method, path, value=None, content_type='application/json'):
        headers = {'Authorization': 'Bearer ' + read_token(self.token_file), 'Accept': 'application/json'}
        body = None
        if value is not None:
            body = encoded(value)
            headers['Content-Type'] = content_type
        try:
            status, raw = self.transport(method, self.base + path, headers, body,
                                         deadline=time.monotonic() + self.timeout, max_bytes=1048576,
                                         ca_file=self.ca_file)
        except Denied:
            raise Denied(503, 'AuthorityUnavailable') from None
        try:
            return status, loads(raw, 1048576) if raw else None
        except Denied:
            raise Denied(503, 'AuthorityUnavailable') from None

    def get(self, path):
        """Return the object, or None when it does not exist; any other failure denies."""
        status, value = self.call('GET', path)
        if status == 404:
            return None
        require(status == 200 and isinstance(value, dict), 503, 'AuthorityUnavailable')
        return value


def serve(handle, port, max_body, log=log):

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = 'standalone'
        sys_version = ''

        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def dispatch(self, method):
            try:
                body = b''
                if method == 'POST':
                    require(self.headers.get('Transfer-Encoding') is None, 411, 'ContentLengthRequired')
                    try:
                        size = int(header(self.headers.items(), 'Content-Length'))
                    except (TypeError, ValueError):
                        raise Denied(411, 'ContentLengthRequired') from None
                    require(0 <= size <= max_body, 413, 'BodyTooLarge')
                    body = self.rfile.read(size)
                    require(len(body) == size, 400, 'IncompleteBody')
                status, payload = handle(method, self.path, self.headers.items(), body)
            except Denied as error:
                status, payload = error.status, {'error': error.reason}
            except Exception as error:
                log(json.dumps({'event': 'internal-error', 'type': type(error).__name__}))
                status, payload = 500, {'error': 'InternalError'}
            raw = json.dumps(payload, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(raw)
            self.close_connection = True

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

    server = http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler)
    server.daemon_threads = True
    server.serve_forever()
