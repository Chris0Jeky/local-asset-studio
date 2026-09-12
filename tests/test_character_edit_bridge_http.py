"""Actual loopback transport, not an image inference test."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import unittest
from unittest.mock import patch
from scripts.character_edit_bridge import StudioHTTP


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                cls.seen.append((self.path,dict(self.headers),None))
                if self.path=='/api/redirect':
                    self.send_response(302);self.send_header('Location','http://example.invalid/pixels');self.send_header('Content-Length','0');self.end_headers();return
                if self.path=='/api/huge':
                    self.send_response(200);self.send_header('Content-Length',str(10**9));self.end_headers();return
                if self.path=='/api/duplicate':raw=b'{"ok":true,"ok":false}'
                elif self.path=='/api/png':raw=b'actual-binary-fixture'
                else:raw=b'{"ok":true}'
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));cls.seen.append((self.path,dict(self.headers),raw))
                response=b'{"received":true}'
                self.send_response(201);self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)
        cls.seen=[];cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)
    def setUp(self):self.http=StudioHTTP(self.server.server_port,timeout=2)
    def test_numeric_loopback_ignores_proxy_environment(self):
        with patch.dict(os.environ,{'HTTP_PROXY':'http://example.invalid:9','http_proxy':'http://example.invalid:9'}):
            self.assertTrue(self.http.request('GET','/api/identity')['ok'])
    def test_origin_host_and_json(self):
        self.http.request('POST','/api/preview',{'text':'é'})
        _,headers,raw=self.seen[-1]
        self.assertEqual(self.http.origin,headers['Origin']);self.assertEqual('127.0.0.1:'+str(self.server.server_port),headers['Host'])
        self.assertEqual('application/json',headers['Content-Type']);self.assertEqual({'text':'é'},json.loads(raw))
    def test_upload_raw_bytes_and_filename(self):
        self.http.request('POST','/api/upload',b'png-bytes',filename='reference.png')
        _,headers,raw=self.seen[-1];self.assertEqual(b'png-bytes',raw);self.assertEqual('image/png',headers['Content-Type'])
        self.assertEqual('reference.png',headers['X-Filename'])
    def test_redirect_is_not_followed(self):
        before=len(self.seen)
        with self.assertRaisesRegex(ValueError,'302'):self.http.request('GET','/api/redirect')
        self.assertEqual(before+1,len(self.seen))
    def test_header_limit_before_read(self):
        with self.assertRaisesRegex(ValueError,'too large'):self.http.request('GET','/api/huge')
    def test_json_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.http.request('GET','/api/duplicate')
    def test_binary_is_not_decoded(self):self.assertEqual(b'actual-binary-fixture',self.http.request('GET','/api/png',binary=True))
    def test_header_injection_rejected_before_request(self):
        before=len(self.seen)
        with self.assertRaises(ValueError):self.http.request('POST','/api/upload',b'x',filename='a.png\r\nOther: yes')
        self.assertEqual(before,len(self.seen))
    def test_non_api_path_rejected(self):
        with self.assertRaises(ValueError):self.http.request('GET','http://example.invalid/')
    def test_port_boolean_rejected(self):
        with self.assertRaises(ValueError):StudioHTTP(True)

if __name__=='__main__':unittest.main()
