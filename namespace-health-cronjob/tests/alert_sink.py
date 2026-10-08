"""Local test-only webhook sink for proving the independent observer sends alerts."""
import json
import sys
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
path=Path(sys.argv[1]);port=int(sys.argv[2])
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if size>2048:self.send_error(413);return
        event=json.loads(self.rfile.read(size))
        with path.open('a') as f:f.write(json.dumps(event,sort_keys=True)+'\n')
        self.send_response(204);self.end_headers()
    def log_message(self,*args):pass
HTTPServer(('0.0.0.0',port),Handler).serve_forever()
