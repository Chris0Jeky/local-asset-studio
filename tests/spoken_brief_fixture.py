import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import wave


def wav_bytes(frames, value=0):
    import io
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setparams((1, 2, 48000, 0, 'NONE', ''))
        output.writeframes(int(value).to_bytes(2, 'little', signed=True) * frames)
    return stream.getvalue()


def signed_plan(payload, *, producer_revision='fixture-v1'):
    plan = {**payload, 'version': 1, 'kind': 'voice', 'producer_revision': producer_revision}
    plan['sha256'] = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return plan


class Fixture:
    def __init__(self):
        self.requests = []
        self.projects = {}
        self.audio = {}
        self.counter = 0
        self.create_id_override = None
        self.create_rejection = None
        self.create_response_override = None
        self.start_response_override = None
        self.identity_redirect = None
        self.mismatch_after_start = False
        self.identity = {'app': 'local-asset-studio', 'workspace': 'fixture-workspace', 'version': 'production-workspace-1'}
        self.producer_revision = 'fixture-v1'
        self.on_identity = None
        self.after_create = None
        self.after_start = None
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), self.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

    def handler(self):
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _json(self, status, value):
                raw = json.dumps(value).encode('utf-8')
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                fixture.requests.append(('GET', self.path, self.headers.get('Origin'), None))
                if self.path == '/api/identity' and fixture.identity_redirect:
                    self.send_response(302); self.send_header('Location', fixture.identity_redirect); self.end_headers(); return
                if self.path == '/redirected-identity': return self._json(200, fixture.identity)
                if self.path == '/oversized-json': return self._json(200, {'payload': 'x' * 512})
                if self.path == '/json-array': return self._json(200, [])
                if self.path == '/api/identity':
                    if fixture.on_identity is not None: fixture.on_identity()
                    return self._json(200, fixture.identity)
                if self.path.startswith('/api/production/') and '/files/' not in self.path:
                    identifier = self.path.split('/')[3]
                    project = json.loads(json.dumps(fixture.projects[identifier]))
                    if fixture.mismatch_after_start and project.get('state', {}).get('status') == 'completed':
                        project['plan']['lines'][0]['text'] = 'Different words returned after Start.'
                        unsigned = {key: value for key, value in project['plan'].items() if key != 'sha256'}
                        project['plan']['sha256'] = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
                    return self._json(200, project)
                if self.path in fixture.audio:
                    raw = fixture.audio[self.path]
                    self.send_response(200); self.send_header('Content-Type', 'audio/wav')
                    self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw); return
                self._json(404, {'error': 'not found'})
            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length) or b'{}')
                fixture.requests.append(('POST', self.path, self.headers.get('Origin'), body))
                if self.path == '/api/voice-baseline':
                    if fixture.create_rejection is not None:
                        return self._json(fixture.create_rejection, {'error': 'voice bundle is not configured'})
                    fixture.counter += 1; identifier = fixture.create_id_override or f'{fixture.counter:032x}'
                    project = {'id': identifier, 'kind': 'voice', 'name': body['name'],
                               'plan': signed_plan(body, producer_revision=fixture.producer_revision),
                               'state': {'status': 'planned', 'message': 'prepared', 'artifacts': []}}
                    fixture.projects[identifier] = project
                    if fixture.after_create is not None: fixture.after_create(project)
                    response = fixture.create_response_override if fixture.create_response_override is not None else project
                    return self._json(201, response)
                if self.path.endswith('/start'):
                    identifier = self.path.split('/')[3]
                    project = fixture.projects[identifier]; artifacts = []
                    for line in project['plan']['lines']:
                        relative = f"voice/{line['id']}-scene.wav"
                        route = f'/api/production/{identifier}/files/{relative}'
                        raw = wav_bytes(480, fixture.counter)
                        fixture.audio[route] = raw
                        artifacts.append({'path': relative, 'url': route, 'sha256': hashlib.sha256(raw).hexdigest(), 'role': 'audio'})
                    project['state'] = {'status': 'completed', 'message': 'done', 'artifacts': artifacts}
                    if fixture.after_start is not None: fixture.after_start(project)
                    response = fixture.start_response_override if fixture.start_response_override is not None else project
                    return self._json(202, response)
                return self._json(404, {'error': 'unknown'})
        return Handler
