import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from controller import Kubernetes


class Credentials(unittest.TestCase):
    def test_projected_token_rotation_changes_next_http_request(self):
        observed = []

        class Backend(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(self.headers['Authorization'])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'items': []}).encode())

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                kube = Kubernetes.__new__(Kubernetes)
                kube.base = 'http://127.0.0.1:' + str(server.server_port)
                kube.context = None
                kube.token_file = Path(directory) / 'token'
                kube.token_file.write_text('first')
                kube.call('GET', '/requests')
                replacement = Path(directory) / 'replacement'
                replacement.write_text('rotated')
                replacement.replace(kube.token_file)
                kube.call('GET', '/requests')
                self.assertEqual(observed, ['Bearer first', 'Bearer rotated'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
