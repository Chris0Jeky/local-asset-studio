"""Same-origin HTTP and SDK over actual SQLite; no inference or workspace media."""
import copy
import http.client
import json
from pathlib import Path
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
import test_prompt_projects as project_fixtures
from studio_prompt.http_extension import extend_handler


class PromptProjectHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture=project_fixtures.PromptProjectTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.scope=self.fixture.scope;self.requests=[];self.drop=False;fixture=self
        class Base(BaseHTTPRequestHandler):
            studio=SimpleNamespace(prompt_projects=fixture.fixture.service)
            def log_message(self,*args):pass
            def _safe_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')==f'http://127.0.0.1:{self.server.server_port}'
            def _content_length(self,limit):
                size=int(self.headers.get('Content-Length','-1'))
                if not 0<=size<=limit:raise ValueError('Request exceeds limit')
                return size
            def _json(self,status,value):
                if fixture.drop and self.command=='POST' and status==200:
                    fixture.drop=False;self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
                raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):self._json(200,{'unrelated':True})
        class Handler(extend_handler(Base)):
            def do_POST(self):fixture.requests.append(self.path);return super().do_POST()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start();self.addCleanup(self.close)
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def close(self):self.server.shutdown();self.thread.join();self.server.server_close()
    def request(self,path,body=None,**headers):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            conn.request('POST' if body is not None else 'GET','/api/prompt/projects/'+path,
                json.dumps(body).encode() if body is not None else None,{'Origin':self.base,'Content-Type':'application/json',**headers})
            reply=conn.getresponse();return reply.status,json.loads(reply.read())
        finally:conn.close()
    def test_capabilities_and_complete_create_read_cycle(self):
        self.assertEqual(self.request('capabilities')[1]['workspace_id'],self.scope)
        status,created=self.request('create',self.fixture.request);self.assertEqual(status,200)
        key=created['project']['id'];status,row=self.request(f'read?workspace_id={self.scope}&id={key}')
        self.assertEqual(status,200);self.assertEqual(row['document'],self.fixture.doc)
        self.assertEqual(len(self.request('list?workspace_id='+self.scope)[1]['projects']),1)
        self.assertEqual(len(self.request(f'history?workspace_id={self.scope}&id={key}')[1]['revisions']),1)
    def test_reads_do_not_change_database(self):
        self.fixture.create()
        with self.fixture.workspace.connection() as db:
            before='\n'.join(db.iterdump())
        self.request('capabilities');self.request('list?workspace_id='+self.scope)
        self.request(f'status?workspace_id={self.scope}&request_id=prompt-request-0001')
        with self.fixture.workspace.connection() as db:self.assertEqual('\n'.join(db.iterdump()),before)
    def test_host_origin_body_and_unknown_queries_refused(self):
        self.assertEqual(self.request('create',self.fixture.request,Origin='http://elsewhere.invalid')[0],403)
        self.assertEqual(self.request('capabilities',Host='elsewhere.invalid')[0],403)
        self.assertEqual(self.request('create',self.fixture.request,**{'Content-Type':'text/plain'})[0],400)
        for path in ('capabilities?extra=1','list','read?workspace_id='+self.scope+'&id=bad',
                     'list?workspace_id='+self.scope+'&workspace_id='+self.scope):
            with self.subTest(path=path):self.assertEqual(self.request(path)[0],400)
        self.assertEqual(self.fixture.count(),0)
    def test_lost_committed_reply_recovers_by_read_without_second_write(self):
        self.drop=True
        with self.assertRaises((http.client.HTTPException,OSError)):self.request('create',self.fixture.request)
        status,reply=self.request(f'status?workspace_id={self.scope}&request_id=prompt-request-0001')
        self.assertEqual(status,200);self.assertEqual(reply['project']['revision'],1)
        self.assertEqual(len(self.requests),1);self.assertEqual(self.fixture.count(),1)
    def test_storage_error_is_unconfirmed_not_a_success(self):
        import sqlite3
        with patch.object(self.fixture.service,'command',side_effect=sqlite3.OperationalError('locked')):
            status,result=self.request('create',self.fixture.request)
        self.assertEqual(status,503);self.assertEqual(result['code'],'project_storage_unconfirmed')
    def test_sdk_uses_same_commands_and_keeps_conflicts(self):
        from studio_prompt.project_client import PromptProjectClient
        client=PromptProjectClient(self.base);result=client.command('create',self.fixture.request)
        self.assertEqual(client.get(self.scope,result['project']['id'])['document'],self.fixture.doc)
        changed=copy.deepcopy(self.fixture.request);changed['document']['name']='Changed'
        from studio_workflow.client import ClientError
        with self.assertRaises(ClientError) as error:client.command('create',changed)
        self.assertEqual(error.exception.code,'request_conflict');self.assertEqual(len(self.requests),2)

    def test_cli_reads_same_saved_project_without_a_write(self):
        import subprocess
        import tempfile
        created=self.fixture.create()
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'read.json'
            result=subprocess.run([sys.executable,'-m','studio_prompt.project_client','--base',self.base,
                '--output',str(target),'read','--workspace-id',self.scope,'--id',created['project']['id']],
                cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['document'],self.fixture.doc)
            again=subprocess.run([sys.executable,'-m','studio_prompt.project_client','--base',self.base,
                '--output',str(target),'capabilities'],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
            self.assertEqual(again.returncode,2)
        self.assertEqual(self.requests,[])
    def test_real_studio_initializes_project_service(self):
        import test_server
        fixture=test_server.ServerTests();fixture.setUp()
        try:
            studio=fixture.studio()
            self.assertTrue(hasattr(studio,'prompt_projects'))
            self.assertEqual(studio.prompt_projects.list(studio.prompt_projects.capabilities()['workspace_id'])['projects'],[])
            self.assertEqual(studio.queue.qsize(),0)
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
