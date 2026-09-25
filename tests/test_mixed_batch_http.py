"""Real loopback routes for revision-bound mixed batch commands; no Comfy runtime."""
import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import unittest
from unittest.mock import patch

import test_mixed_batch as fixtures
from http_refusal_transport import atomic_json_post


class MixedBatchHTTPTests(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.MixedBatchTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.studio=self.case.studio;self.case.fixture.patches[0].stop()
        handler=type('MixedHandler',(fixtures.server.Handler,),{'studio':self.studio})
        # Binding numeric loopback needs no reverse DNS; HTTPServer.server_bind normally calls getfqdn.
        with patch.object(socket,'getfqdn',return_value='127.0.0.1'):
            self.http=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
        self.route='/api/jobs/'+self.case.job['id']
    def close(self):
        # shutdown() waits without a bound for serve_forever to acknowledge; skip it when the
        # serving thread never ran or already died, so cleanup cannot hang (#872).
        if self.thread.is_alive():self.http.shutdown()
        self.http.server_close();self.thread.join(3)
    def request(self,path,payload=None,method='POST'):
        connection=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            body=None if method == 'GET' and payload is None else json.dumps(payload)
            connection.request(method,path,body,{'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
            if connection.sock:
                try:connection.sock.shutdown(socket.SHUT_WR)
                except OSError:pass
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()
    def test_get_fixture_sends_no_request_body(self):
        wire=bytearray();real_create_connection=socket.create_connection
        class ObservedSocket:
            def __init__(self,real):self.real=real
            def sendall(self,data,*args,**kwargs):wire.extend(data);return self.real.sendall(data,*args,**kwargs)
            def __getattr__(self,name):return getattr(self.real,name)
        def observe(address,*args,**kwargs):return ObservedSocket(real_create_connection(address,*args,**kwargs))
        socket.create_connection=observe
        try:
            status,_=self.request('/api/jobs',method='GET')
        finally:socket.create_connection=real_create_connection
        self.assertEqual(status,200)
        headers,body=bytes(wire).split(b'\r\n\r\n',1)
        self.assertEqual(body,b'')
        self.assertNotRegex(headers.lower(),rb'\r\ncontent-length: [1-9]')
    def test_get_and_observe_are_read_only_until_explicit_request_then_dispose_is_idempotent(self):
        before=self.case.files();calls=list(self.studio.requests)
        status,jobs=self.request('/api/jobs',method='GET')
        self.assertEqual(status,200);self.assertEqual(self.case.files(),before)
        self.assertEqual(jobs[0]['mixed_batch']['unknown_index'],1)
        payload=self.case.payload();status,data=self.request(self.route+'/observe-known',payload)
        self.assertEqual(status,202);self.assertEqual(data['status'],'queued');self.assertEqual(self.studio.requests,calls)
        self.assertEqual(self.request(self.route+'/observe-known',payload)[0],202);self.assertEqual(self.studio.queue.qsize(),1)
        self.case.consume();self.assertEqual(self.studio.requests,calls)
        disposition=self.case.payload('dispose-0001',reason='Keep all uncertain evidence',acknowledge_unknown=True)
        status,data=self.request(self.route+'/dispose-mixed',disposition)
        self.assertEqual(status,200);self.assertEqual(data['status'],'abandoned');self.assertTrue(data['has_pending_submission'])
        self.assertNotIn('pending_submission',data);self.assertNotIn('graph',json.dumps(data['mixed_batch']))
        self.assertEqual(self.request(self.route+'/dispose-mixed',disposition)[1],data)
        self.assertTrue(self.studio.queue.empty());self.case.no_posts_since(2)
    def test_origin_and_host_rejections_never_change_mixed_evidence(self):
        before=self.case.files()
        for endpoint in ('observe-known','dispose-mixed'):
            payload=self.case.payload(**({'reason':'Keep','acknowledge_unknown':True} if endpoint=='dispose-mixed' else {}))
            for host,origin in (('evil.invalid','http://127.0.0.1:8191'),('127.0.0.1:8191','null'),('127.0.0.1:8191','https://evil.invalid')):
                status,_=atomic_json_post(self.http.server_port,self.route+'/'+endpoint,json.dumps(payload).encode(),host=host,origin=origin)
                self.assertEqual(status,403)
        self.assertEqual(self.case.files(),before);self.assertTrue(self.studio.queue.empty());self.case.no_posts_since(2)
    def test_bad_routes_bodies_stale_revisions_and_reused_id_fail_closed(self):
        before=copy.deepcopy(self.case.job)
        for endpoint in ('observe-known','dispose-mixed'):
            for payload in ([],None,True,'wrong',{}, {'request_id':'request-0001','expected_revision':'0'*64}):
                self.assertEqual(self.request(self.route+'/'+endpoint,payload)[0],400)
            self.assertEqual(atomic_json_post(self.http.server_port,self.route+'/extra/'+endpoint,b'{}')[0],400)
        self.assertEqual(self.case.job,before)
        payload=self.case.payload();self.assertEqual(self.request(self.route+'/observe-known',payload)[0],202)
        self.case.consume()
        self.assertEqual(self.request(self.route+'/observe-known',dict(payload,request_id='request-0002'))[0],400)
        self.assertEqual(self.request(self.route+'/dispose-mixed',dict(payload,reason='Different operation',acknowledge_unknown=True))[0],400)
        self.assertTrue(self.studio.queue.empty());self.case.no_posts_since(2)


class MixedBatchFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node is needed to exercise shipped browser handlers')
    def test_actual_browser_handlers(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','tests/mixed_batch_frontend.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
