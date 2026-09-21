"""Real HTTP uses the shared analysis owner; no model calls from read routes."""
from contextlib import closing
import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlencode
import test_reference_jobs as fixtures
from studio_prompt.http_extension import extend_handler


class ReferenceJobHttpTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReferenceJobTests();self.f.setUp();self.f.start.stop()
        self.addCleanup(self.f.doCleanups);self.addCleanup(self.f.tearDown)
        class Base(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def _safe_host(self):return self.headers.get('Host')=='localhost:8191'
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://localhost:8191'
            def _content_length(self,limit):
                n=int(self.headers.get('Content-Length','-1'))
                if not 0<=n<=limit:raise ValueError('Body limit exceeded')
                return n
            def _json(self,code,value):
                raw=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        handler=extend_handler(Base);handler.studio=self.f.studio_instance
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler);self.thread=threading.Thread(target=self.http.serve_forever);self.thread.start()
        self.addCleanup(self.close)
    def close(self):self.http.shutdown();self.thread.join();self.http.server_close()
    def call(self,path,value=None,headers=None,raw=None):
        body=json.dumps(value) if value is not None else raw
        with closing(http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)) as client:
            client.request('POST' if body is not None else 'GET','/api/prompt/reference-jobs/'+path,body,
                {'Host':'localhost:8191','Origin':'http://localhost:8191','Content-Type':'application/json',**(headers or {})})
            response=client.getresponse();data=response.read()
            try:return response.status,json.loads(data)
            except ValueError:return response.status,{}
    def status_path(self):return 'status?'+urlencode({'workspace_id':self.f.scope,'request_id':self.f.payload['request_id']})
    def test_create_then_status_no_model_call(self):
        code,value=self.call('create',self.f.payload);self.assertEqual(code,202)
        self.assertEqual(self.call(self.status_path())[1]['request_id'],self.f.payload['request_id'])
        self.assertEqual(self.f.calls,[])
    def test_capabilities_are_configuration_only(self):
        code,value=self.call('capabilities');self.assertEqual(code,200);self.assertTrue(value['enabled']);self.assertEqual(self.f.calls,[])
    def test_origin_and_host_refuse_create(self):
        for headers in ({'Host':'elsewhere.invalid'},{'Origin':'https://elsewhere.invalid'}):
            self.assertEqual(self.call('create',self.f.payload,headers)[0],403)
        self.assertEqual(self.f.calls,[])
    def test_intake_is_single_flight_before_body_read(self):
        self.f.service.intake.acquire()
        try:self.assertEqual(self.call('create',raw=b'',headers={'Content-Length':str(40*1024*1024)})[0],409)
        finally:self.f.service.intake.release()
        self.assertTrue(self.f.studio_instance.queue.empty())
    def test_strict_json_and_exact_endpoint(self):
        self.assertEqual(self.call('create',raw=b'{"x":1,"x":2}')[0],400)
        self.assertEqual(self.call('create?extra=1',raw=b'{}')[0],400)
        self.assertEqual(self.call('capabilities',headers={'Host':'evil.invalid'})[0],403)
    def test_unknown_status_and_scope_are_not_retried(self):
        self.assertEqual(self.call(self.status_path())[0],404)
        self.call('create',self.f.payload)
        code,_=self.call('status?'+urlencode({'workspace_id':'a'*32,'request_id':self.f.payload['request_id']}))
        self.assertEqual(code,409);self.assertEqual(self.f.calls,[])
    def test_read_query_duplicate_rejected(self):
        self.assertEqual(self.call(self.status_path()+'&request_id=another-request')[0],400)
