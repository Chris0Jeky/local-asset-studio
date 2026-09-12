"""Explicit CPU-only browser fixture, not the production Handler or a model service."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import urlparse


@contextmanager
def serve_fixture(studio):
    commands=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,data,content='application/json',download=None):
            if not isinstance(data,bytes):data=json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)))
            if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path
            try:
                if path in ('/review.html','/review.css','/review.js'):
                    file=Path(__file__).parents[1]/'app/static'/path[1:]
                elif path.startswith('/api/production/') and '/files/' in path:
                    identifier=path.split('/')[3];relative=path.split('/files/',1)[1];file=studio.production.file(identifier,relative)
                elif path.startswith('/api/assets/') and path.endswith('/file'):
                    file=studio.assets.file(path.split('/')[3])
                else:return self.send(404,{'error':'Not a fixture route'})
                return self.send(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream',file.name if urlparse(self.path).query=='download' else None)
            except (ValueError,OSError,KeyError) as exc:self.send(400,{'error':str(exc)})
        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Origin')!=origin:return self.send(403,{'error':'Same-origin fixture request required'})
            try:
                if not self.path.startswith('/api/production/') or not self.path.endswith('/review'):raise ValueError('No generation route in fixture')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1024**2:raise ValueError('Bounded JSON required')
                payload=json.loads(self.rfile.read(size));commands.append(payload)
                self.send(200,studio.production.review(self.path.split('/')[3],payload))
            except (ValueError,OSError,KeyError) as exc:self.send(400,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',commands
    finally:server.shutdown();server.server_close();thread.join(2)
