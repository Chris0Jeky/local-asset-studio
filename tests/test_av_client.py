import json
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from threading import Thread
import types
import unittest
from contextlib import redirect_stdout

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from studio_av.client import StudioClient, StudioClientError


class Fixture(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*_):pass
    def _json(self,status,data):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        type(self).calls.append((self.command,self.path,dict(self.headers),None))
        if self.path=='/redirect':self.send_response(302);self.send_header('Location','http://example.invalid');self.end_headers();return
        if self.path=='/huge':self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length','999999');self.end_headers();return
        self._json(200,{'projects':[]} if self.path=='/api/av' else {'assets':[]})
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')));payload=json.loads(raw);type(self).calls.append((self.command,self.path,dict(self.headers),payload))
        if self.path.endswith('/fail'):self._json(409,{'error':'Scene conflict: reload'});return
        self._json(200,{'received':payload})


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);cls.thread=Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)
        if cls.thread.is_alive():raise AssertionError('AV client fixture server did not stop')
    def setUp(self):Fixture.calls=[]
    def test_loopback_and_redirect_restrictions(self):
        for url in ('https://127.0.0.1:8191','http://example.invalid','http://127.0.0.1:8191/path','http://user@127.0.0.1:8191'):
            with self.subTest(url=url),self.assertRaises(StudioClientError):StudioClient(url)
        with self.assertRaises(StudioClientError):StudioClient(self.url,timeout=0)
        with self.assertRaisesRegex(StudioClientError,'redirects'):StudioClient(self.url,response_limit=64).request('GET','/redirect')
        self.assertEqual(len(Fixture.calls),1);self.assertEqual(Fixture.calls[0][1],'/redirect')
    def test_commands_keep_revision_actor_and_are_never_retried(self):
        client=StudioClient(self.url)
        reply=client.command('scene1',{'action':'edit','expected_revision':7,'section':'audio','clip_id':'clip1','changes':{'gain_db':-6}})
        self.assertEqual(reply['received']['expected_revision'],7);self.assertEqual(reply['received']['actor'],'cli');self.assertEqual(Fixture.calls[0][2]['Origin'],self.url)
        with self.assertRaisesRegex(StudioClientError,'Scene conflict'):client.command('fail',{'action':'render','expected_revision':7})
        self.assertEqual(len(Fixture.calls),2,'a failed mutation must not be replayed')
    def test_body_response_and_identifier_limits(self):
        client=StudioClient(self.url,body_limit=8,response_limit=64)
        with self.assertRaises(StudioClientError):client.command('scene1',{'action':'edit','expected_revision':1})
        self.assertEqual(Fixture.calls,[])
        with self.assertRaises(StudioClientError):client.request('GET','/huge')
        with self.assertRaises(StudioClientError):client.inspect('../escape')
    def test_cli_list_uses_the_same_loopback_client(self):
        from studio_av.__main__ import main
        output=io.StringIO()
        with redirect_stdout(output):self.assertEqual(main(['studio','--url',self.url,'list']),0)
        self.assertEqual(json.loads(output.getvalue()),{'projects':[]});self.assertEqual(Fixture.calls[0][1],'/api/av')
    def test_studio_mcp_defaults_to_read_and_preview_tools(self):
        class FakeServer:
            def __init__(self,*_args,**_kwargs):self.tools={}
            def tool(self,**_kwargs):
                def decorate(fn):self.tools[fn.__name__]=fn;return fn
                return decorate
        original={key:sys.modules.get(key) for key in ('mcp','mcp.server')};mcp=types.ModuleType('mcp');server=types.ModuleType('mcp.server');server.MCPServer=FakeServer;sys.modules['mcp']=mcp;sys.modules['mcp.server']=server
        try:
            from studio_av.mcp_server import build_studio_server
            tools=build_studio_server(self.url).tools
            proposed=tools['propose_edit']('scene1',7,'shots','clip1','{"frames":48}')
        finally:
            for key,value in original.items():
                if value is None:sys.modules.pop(key,None)
                else:sys.modules[key]=value
        self.assertEqual(proposed['received']['action'],'preview');self.assertEqual(proposed['received']['expected_revision'],7);self.assertEqual(proposed['received']['actor'],'agent')
        self.assertTrue({'list_scenes','inspect_scene','workspace_sources','propose_edit'}<=set(tools));self.assertFalse({'create_scene','edit_scene','restore_scene','export_scene','render_scene','cancel_render'}&set(tools))


if __name__=='__main__':unittest.main()
