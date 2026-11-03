import http.server
import threading
import time
import unittest

from fixtures import common


class HTTPTests(unittest.TestCase):
    def upstream(self, *, status=200, protocol='HTTP/1.0', headers=(), chunks=()):
        stopped = threading.Event()

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = protocol

            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(status)
                for name, value in headers:
                    self.send_header(name, value)
                self.end_headers()
                try:
                    for delay, chunk in chunks:
                        if stopped.wait(delay):
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except OSError:
                    pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        thread.start()

        def close():
            stopped.set()
            server.shutdown()
            server.server_close()
            thread.join(1)
        self.addCleanup(close)
        return 'http://127.0.0.1:%d/' % server.server_port

    def call(self, url, *, max_bytes=64, timeout=2):
        return common.http_call('GET', url, {}, deadline=time.monotonic() + timeout, max_bytes=max_bytes)

    def test_http10_content_length_success(self):
        url = self.upstream(headers=(('Content-Length', '5'),), chunks=((0, b'ready'),))
        self.assertEqual(self.call(url), (200, b'ready'))

    def test_http10_content_length_error(self):
        url = self.upstream(status=403, headers=(('Content-Length', '6'),), chunks=((0, b'denied'),))
        self.assertEqual(self.call(url), (403, b'denied'))

    def test_http11_connection_close_content_length(self):
        url = self.upstream(protocol='HTTP/1.1', headers=(('Connection', 'close'), ('Content-Length', '5')),
                            chunks=((0, b'ready'),))
        self.assertEqual(self.call(url), (200, b'ready'))

    def test_http11_persistent_content_length(self):
        url = self.upstream(protocol='HTTP/1.1', headers=(('Content-Length', '5'),), chunks=((0, b'ready'),))
        self.assertEqual(self.call(url), (200, b'ready'))

    def test_http10_eof_delimited_body(self):
        url = self.upstream(chunks=((0, b'ready'),))
        self.assertEqual(self.call(url), (200, b'ready'))

    def test_content_length_body_limit(self):
        for body in (b'12345', b'123456'):
            with self.subTest(size=len(body)):
                url = self.upstream(headers=(('Content-Length', str(len(body))),), chunks=((0, body),))
                if len(body) == 5:
                    self.assertEqual(self.call(url, max_bytes=5), (200, body))
                else:
                    with self.assertRaises(common.Denied) as caught:
                        self.call(url, max_bytes=5)
                    self.assertEqual((caught.exception.status, caught.exception.reason), (502, 'ResponseTooLarge'))

    def test_chunked_connection_close_body(self):
        url = self.upstream(protocol='HTTP/1.1', headers=(('Connection', 'close'), ('Transfer-Encoding', 'chunked')),
                            chunks=((0, b'2\r\nre\r\n3\r\nady\r\n0\r\n\r\n'),))
        self.assertEqual(self.call(url, max_bytes=5), (200, b'ready'))

    def test_chunked_connection_close_body_limit(self):
        url = self.upstream(protocol='HTTP/1.1', headers=(('Connection', 'close'), ('Transfer-Encoding', 'chunked')),
                            chunks=((0, b'6\r\n123456\r\n0\r\n\r\n'),))
        with self.assertRaises(common.Denied) as caught:
            self.call(url, max_bytes=5)
        self.assertEqual((caught.exception.status, caught.exception.reason), (502, 'ResponseTooLarge'))

    def test_slow_close_body_keeps_absolute_deadline(self):
        url = self.upstream(headers=(('Content-Length', '20'),), chunks=((0.03, b'x'),) * 20)
        started = time.monotonic()
        with self.assertRaises(common.Denied) as caught:
            self.call(url, timeout=0.12)
        self.assertEqual(caught.exception.status, 504)
        self.assertIn(caught.exception.reason, ('DeadlineExceeded', 'UpstreamUnavailable'))
        self.assertLess(time.monotonic() - started, 0.8)

    def test_slow_chunked_close_body_keeps_absolute_deadline(self):
        url = self.upstream(protocol='HTTP/1.1', headers=(('Connection', 'close'), ('Transfer-Encoding', 'chunked')),
                            chunks=((0.03, b'1\r\nx\r\n'),) * 20 + ((0, b'0\r\n\r\n'),))
        started = time.monotonic()
        with self.assertRaises(common.Denied) as caught:
            self.call(url, timeout=0.12)
        self.assertEqual(caught.exception.status, 504)
        self.assertIn(caught.exception.reason, ('DeadlineExceeded', 'UpstreamUnavailable'))
        self.assertLess(time.monotonic() - started, 0.8)


if __name__ == '__main__':
    unittest.main()
