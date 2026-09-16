"""Native loopback requests and SDK parity for the non-mutating preview route."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from studio_workflow.core import canonical
from studio_workflow.sdk import WorkflowClient
from test_workflow_control_preview import fixture
try:
    from studio_workflow.control_http import extend_handler, PATH
except ImportError:
    extend_handler = None
    PATH = '/api/workflow-studio/control-preview'


class FakeStudio:
    def __init__(self, info):
        self.info = info; self.lock = threading.RLock()
        self.backends = SimpleNamespace(active='primary', busy=False)
        self.calls = []
    def node_info(self, refresh=False):
        self.calls.append(('schema', refresh)); return self.info
    def create_job(self, *args, **kwargs):
        raise AssertionError('Preview must never create a job')
    @property
    def workspace(self):
        raise AssertionError('Preview must never initialize or write Workspace')


class Base(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def _safe_mutation(self):
        host = '127.0.0.1:' + str(self.server.server_port)
        return self.headers.get('Host') == host and self.headers.get('Origin') == 'http://' + host
    def _content_length(self, cap):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 <= size <= cap: raise ValueError('Body limit exceeded')
        return size
    def _json(self, status, value):
        raw = canonical(value); self.send_response(status)
        self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def do_POST(self): self._json(404, {'error': 'Unrelated route'})
    def do_GET(self): self._json(404, {'error': 'Unrelated route'})


class ControlHttpTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(extend_handler), 'Control preview route is missing')
        self.value, self.info = fixture(); self.studio = FakeStudio(self.info)
        handler = extend_handler(Base); handler.studio = self.studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.stop)
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)
        self.assertFalse(self.thread.is_alive())
    def wire(self, value=None, path=PATH, method='POST', **headers):
        body = canonical(self.value if value is None else value)
        full = {'Content-Type': 'application/json', 'Origin': self.origin, **headers}
        c = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            c.request(method, path, body=body, headers=full)
            r = c.getresponse(); return r.status, json.loads(r.read())
        finally: c.close()
    def test_native_http_and_sdk_return_the_identical_read_only_proposal(self):
        status, direct = self.wire(); self.assertEqual(status, 200)
        client = WorkflowClient(self.origin)
        self.assertTrue(hasattr(client, 'preview_control'), 'SDK method is missing')
        via_sdk = client.preview_control(self.value['document'], self.value['control'], self.value['value'],
                                         expected_revision=self.value['expected_revision'])
        self.assertEqual(direct, via_sdk)
        self.assertEqual(self.studio.calls, [('schema', False), ('schema', False)])
        self.assertFalse(direct['committed']); self.assertFalse(direct['generation_submitted'])
    def test_sdk_errors_are_structured_and_do_not_repeat_the_request(self):
        from studio_workflow.client import ClientError
        self.studio.backends.busy = True
        client = WorkflowClient(self.origin)
        try:
            client.preview_control(self.value['document'], self.value['control'], 12, expected_revision=0)
        except Exception as error:
            if hasattr(error, 'close'): error.close()
            self.assertIsInstance(error, ClientError)
            self.assertEqual(error.status, 400)
            self.assertEqual(error.code, 'control_preview_invalid')
            self.assertEqual(self.studio.calls, [])
        else:
            self.fail('Busy backend unexpectedly returned a preview')

    def test_origin_and_content_type_guards_precede_schema_reads(self):
        self.assertEqual(self.wire(Origin='http://example.test')[0], 403)
        self.assertEqual(self.wire(**{'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.studio.calls, [])
    def test_invalid_body_is_refused_before_reading_schema(self):
        status, result = self.wire({'approved': True})
        self.assertEqual(status, 400); self.assertFalse(result['generation_submitted'])
        self.assertEqual(self.studio.calls, [])
    def test_inactive_or_changed_backend_does_not_switch(self):
        self.studio.backends.busy = True
        self.assertEqual(self.wire()[0], 400); self.assertEqual(self.studio.calls, [])
        self.studio.backends.busy = False; self.studio.backends.active = 'other'
        status, result = self.wire()
        self.assertEqual(status, 200); self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['commands'], []); self.assertEqual(self.studio.backends.active, 'other')
    def test_get_and_neighboring_routes_delegate_without_reading_schema(self):
        self.assertEqual(self.wire(method='GET')[0], 404)
        self.assertEqual(self.wire(path=PATH+'/other')[0], 404)
        self.assertEqual(self.studio.calls, [])
    def test_schema_error_is_not_a_success_or_automatic_retry(self):
        def offline(*args): self.studio.calls.append('offline'); raise OSError('Fixture offline')
        self.studio.node_info = offline
        status, result = self.wire()
        self.assertEqual(status, 400); self.assertIn('offline', result['error'])
        self.assertNotIn('commands', result); self.assertEqual(self.studio.calls, ['offline'])
    def test_duplicate_json_keys_and_oversize_body_refuse(self):
        # Send the oversized declaration, not a racing multi-MiB body after refusal.
        c = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            c.putrequest('POST', PATH)
            c.putheader('Origin', self.origin); c.putheader('Content-Type', 'application/json')
            c.putheader('Content-Length', str(1024*1024 + 1)); c.endheaders()
            r = c.getresponse(); self.assertEqual(r.status, 400); r.read()
        finally: c.close()
        self.assertEqual(self.studio.calls, [])
        c = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            c.request('POST', PATH, body=b'{"value":1,"value":2}', headers={'Origin':self.origin,'Content-Type':'application/json'})
            r=c.getresponse(); self.assertEqual(r.status,400); r.read()
        finally: c.close()
        self.assertEqual(self.studio.calls, [])


class FullCompositionTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'studio_workflow/document_http.py').exists(),
                         'Full-checkout handler composition is exercised in CI')
    def test_ordinary_workflow_handler_includes_the_new_route_and_capability(self):
        from studio_workflow.http_extension import extend_handler as full, capabilities
        self.assertTrue(capabilities()['multi_target_control_preview'])
        value, info = fixture(); handler=full(Base); handler.studio=FakeStudio(info)
        with ThreadingHTTPServer(('127.0.0.1',0),handler) as server:
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});thread.start()
            try:
                result=WorkflowClient('http://127.0.0.1:'+str(server.server_port)).preview_control(
                    value['document'],value['control'],value['value'],expected_revision=0)
                self.assertEqual(result['state'],'ready');self.assertFalse(result['committed'])
            finally:server.shutdown();thread.join(5)
            self.assertFalse(thread.is_alive())
