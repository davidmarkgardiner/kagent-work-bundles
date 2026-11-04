import http.server
import importlib.util
from pathlib import Path
import threading
import time
import unittest

spec = importlib.util.spec_from_file_location('golden_transport', Path(__file__).resolve().parents[1] / 'runtime/golden.py')
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)


class GatewayResponseTests(unittest.TestCase):
    def test_plain_text_gateway_rejection_still_checks_the_http_status(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                self.send_response(401)
                self.send_header('Content-Length', str(len(b'authentication failure: no bearer token found')))
                self.end_headers()
                self.wfile.write(b'authentication failure: no bearer token found')

            def log_message(self, *_):
                pass

        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            verifier = golden.Golden.__new__(golden.Golden)
            verifier.config = {'gatewayURL': 'http://127.0.0.1:' + str(server.server_port)}
            verifier.deadline = time.monotonic() + 3
            status, response = verifier.http('/invoke', {'prompt': 'denied'})
            self.assertEqual(status, 401)
            self.assertEqual(response, {'error': 'GatewayRejected'})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
