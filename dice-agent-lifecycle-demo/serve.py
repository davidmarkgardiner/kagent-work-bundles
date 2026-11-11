"""Local-only media review server with HTTP byte-range support for chapter seeking."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import re

ROOT=Path(__file__).resolve().parent
class MediaHandler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def send_head(self):
        self.byte_range=None
        path=Path(self.translate_path(self.path))
        requested=self.headers.get('Range')
        if not requested or not path.is_file():
            return super().send_head()
        size=path.stat().st_size
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested.strip())
        if not match or not any(match.groups()):
            self.send_error(416);return None
        left,right=match.groups()
        start=int(left) if left else max(0,size-int(right))
        end=min(int(right),size-1) if left and right else size-1
        if start>=size or start>end:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
        source=path.open('rb');source.seek(start);self.byte_range=(start,end)
        self.send_response(206)
        self.send_header('Content-type',self.guess_type(str(path)))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1))
        self.end_headers();return source
    def end_headers(self):
        if getattr(self,"byte_range",None) is None:self.send_header('Accept-Ranges','bytes')
        super().end_headers()
    def copyfile(self,source,destination):
        try:
            if self.byte_range is None:return super().copyfile(source,destination)
            remaining=self.byte_range[1]-self.byte_range[0]+1
            while remaining:
                chunk=source.read(min(1024*1024,remaining))
                if not chunk:break
                destination.write(chunk);remaining-=len(chunk)
        except (BrokenPipeError,ConnectionResetError):
            pass

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Review the public DICE work bundle locally.')
    parser.add_argument('--port',type=int,default=3054)
    args=parser.parse_args()
    print(f'DICE bundle: http://127.0.0.1:{args.port}/START-HERE.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),MediaHandler).serve_forever()
