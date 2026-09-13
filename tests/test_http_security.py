"""Exercise the real Handler's common response boundary over loopback HTTP (#98)."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import copy
import json
import socket
import threading
import unittest

import test_production as fixtures
from test_server import FakeStudio, png, server


class ResponseSecurityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProductionTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.studio=FakeStudio(self.fixture.root,[])
        self.asset=self.studio.import_image('fixture.png','image/png',png())['asset']
        self.job=self.studio.jobs[self.studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        self.job['outputs']=[{'filename':'fixture.mp4','type':'output','subfolder':'','media_type':'video'}]
        self.fixture.patches[0].stop()
        class Media(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                if self.headers.get('Range')=='bytes=100-':
                    self.send_response(416);self.send_header('Content-Range','bytes */10');self.send_header('Content-Length','0');self.end_headers();return
                partial=self.headers.get('Range')=='bytes=0-3';body=b'0123' if partial else b'0123456789'
                self.send_response(206 if partial else 200);self.send_header('Content-Type','video/mp4')
                self.send_header('Accept-Ranges','bytes');self.send_header('ETag','"fixture"')
                if partial:self.send_header('Content-Range','bytes 0-3/10')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        self.upstream,self.upstream_thread=self.serve(Media)
        self.job['comfy_url']='http://127.0.0.1:'+str(self.upstream.server_port)
        handler=type('SecurityFixture',(server.extend_handler(server.Handler),),{'studio':self.studio})
        self.http,self.thread=self.serve(handler)
    def serve(self,handler):
        http=ThreadingHTTPServer(('127.0.0.1',0),handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def close():http.shutdown();http.server_close();thread.join(2)
        self.addCleanup(close);return http,thread
    def request(self,path,method='GET',headers=None,payload=None):
        conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            conn.request(method,path,json.dumps(payload) if payload is not None else None,
                         {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json',**(headers or {})})
            if conn.sock:
                try:conn.sock.shutdown(socket.SHUT_WR)
                except OSError:pass
            response=conn.getresponse();return response.status,response.read(),response.getheaders()
        finally:conn.close()
    def secured(self,response,status):
        code,body,pairs=response;self.assertEqual(code,status)
        headers={key.lower():value for key,value in pairs}
        expected={'x-frame-options':'DENY','x-content-type-options':'nosniff',
                  'content-security-policy':"frame-ancestors 'none'"}
        for name,value in expected.items():
            self.assertEqual(headers.get(name),value,name)
            self.assertEqual(sum(key.lower()==name for key,_ in pairs),1,'one shared policy, no duplicate headers')
        self.assertNotIn('access-control-allow-origin',headers)
        return body,headers
    def test_static_pages_scripts_styles_and_not_found_have_headers(self):
        for path in ('/','/review.html','/prompt-lab.html','/app.js','/style.css'):
            with self.subTest(path=path):
                body,headers=self.secured(self.request(path),200);self.assertTrue(body)
                if path.endswith('.js'):self.assertIn(headers['content-type'],('text/javascript','application/javascript'))
                if path.endswith('.css'):self.assertEqual(headers['content-type'],'text/css')
        self.secured(self.request('/missing-security-fixture.html'),404)
    def test_json_and_composed_prompt_routes_share_headers(self):
        for path in ('/api/identity','/api/jobs','/api/prompt/profiles'):
            with self.subTest(path=path):
                body,headers=self.secured(self.request(path),200)
                self.assertEqual(headers['content-type'],'application/json');json.loads(body)
        self.secured(self.request('/api/prompt/invalid',method='POST',payload={}),400)
        self.assertEqual(self.studio.requests,[]);self.assertTrue(self.studio.queue.empty())
    def test_rejected_host_origin_and_unsupported_methods_share_headers(self):
        before=copy.deepcopy(self.studio.jobs)
        self.secured(self.request('/',headers={'Host':'attacker.invalid'}),403)
        self.secured(self.request('/api/jobs',method='POST',headers={'Origin':'https://attacker.invalid'},payload={}),403)
        self.secured(self.request('/api/prompt/compile',method='POST',headers={'Origin':'null'},payload={}),403)
        self.secured(self.request('/',method='OPTIONS'),501)
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.jobs,before)
    def test_local_asset_full_partial_unsatisfiable_and_download_keep_contracts(self):
        path='/api/assets/'+self.asset['id']+'/file'
        raw,headers=self.secured(self.request(path),200);self.assertEqual(raw,png());self.assertEqual(headers['content-type'],'image/png')
        raw,headers=self.secured(self.request(path,headers={'Range':'bytes=0-7'}),206)
        self.assertEqual(raw,png()[:8]);self.assertTrue(headers['content-range'].startswith('bytes 0-7/'))
        self.secured(self.request(path,headers={'Range':'bytes=999999-'}),416)
        raw,headers=self.secured(self.request(path+'?download'),200)
        self.assertIn('attachment',headers['content-disposition']);self.assertEqual(raw,png())
    def test_proxy_full_range_and_upstream_416_are_secured_without_losing_headers(self):
        path='/api/image/'+self.job['id']+'/0'
        raw,headers=self.secured(self.request(path),200);self.assertEqual(raw,b'0123456789')
        self.assertEqual(headers['content-type'],'video/mp4');self.assertEqual(headers['etag'],'"fixture"')
        raw,headers=self.secured(self.request(path,headers={'Range':'bytes=0-3'}),206)
        self.assertEqual(raw,b'0123');self.assertEqual(headers['content-range'],'bytes 0-3/10')
        raw,headers=self.secured(self.request(path,headers={'Range':'bytes=100-'}),416)
        self.assertEqual(raw,b'');self.assertEqual(headers['content-range'],'bytes */10')
