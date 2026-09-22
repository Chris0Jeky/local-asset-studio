"""Full production handler composition over loopback; no model or media calls."""
import importlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, ProxyHandler

import test_asset_metadata_http as metadata_http
from test_server import server
from http_refusal_transport import atomic_json_post

PAGE='/api/assets/page'
SELECTION='/api/assets/selection'


class AssetReadHTTPTests(unittest.TestCase):
    request=metadata_http.AssetMetadataHTTP.request
    tearDown=metadata_http.AssetMetadataHTTP.tearDown

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.store=server.AssetWorkspace(root);source=root/'image.png';source.write_bytes(b'original')
        self.ids=[self.store.register({'id':'job-'+str(i),'created_at':i,
                  'outputs':[{'filename':'image.png'}]},0,source) for i in range(3)]
        self.scope=self.store.snapshot()['workspace_id']
        self.http=server.create_server(root,host='127.0.0.1',port=0,
                                     studio_factory=lambda _:SimpleNamespace(assets=self.store))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()

    def test_production_composition_exposes_read_only_bounded_pages(self):
        before=self.store.snapshot()
        status,page,headers=self.request('GET',PAGE+'?limit=1')
        self.assertEqual(status,200,'Production composition has no bounded page route')
        self.assertEqual(page['assets'][0]['id'],self.ids[2]);self.assertEqual(len(page['assets']),1)
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(page['workspace_id'],self.scope)
        status,second,_=self.request('GET',PAGE+'?'+urlencode({'limit':1,'cursor':page['next_cursor']}))
        self.assertEqual(status,200);self.assertEqual(second['assets'][0]['id'],self.ids[1])
        self.assertEqual(before,self.store.snapshot())
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],0)

    def test_retained_selection_is_not_inferred_from_one_page(self):
        self.request('GET',PAGE+'?limit=1')
        with self.store.connection() as db:db.execute('UPDATE assets SET trashed_at=0 WHERE id=?',(self.ids[1],))
        ids=[self.ids[0],'missing',self.ids[1]]
        status,result,_=self.request('POST',SELECTION,{'workspace_id':self.scope,'ids':ids})
        self.assertEqual(status,200,'Production composition has no selected-ID read route')
        self.assertEqual([x['id'] for x in result['items']],ids)
        self.assertEqual([x['state'] for x in result['items']],['active','missing','trashed'])
        self.assertTrue(result['observation_only']);self.assertFalse(result['generation_submitted'])

    def test_malformed_repeated_unknown_and_overlong_queries_are_refused(self):
        for query in ('limit=1&limit=2','unknown=x','limit=true','limit=0','cursor=',
                      'favorite=1','visibility=','limit=%FF','limit=%GG','limit',
                      'workspace_id='+self.scope+'&workspace_id='+self.scope,'cursor='+'a'*4097):
            with self.subTest(query=query[:70]):
                status,result,_=self.request('GET',PAGE+'?'+query)
                self.assertEqual(status,400);self.assertIn('code',result)

    def test_foreign_scope_and_stale_cursor_are_explicit_conflicts(self):
        status,page,_=self.request('GET',PAGE+'?limit=1');self.assertEqual(status,200)
        for method,path,value in [('GET',PAGE+'?workspace_id='+'b'*32,None),
                                 ('POST',SELECTION,{'workspace_id':'b'*32,'ids':[self.ids[0]]})]:
            status,result,_=self.request(method,path,value)
            self.assertEqual(status,409);self.assertEqual(result['code'],'asset_workspace_conflict')
            self.assertNotIn('assets',result);self.assertNotIn('items',result)
        with self.store.connection() as db:db.execute("UPDATE assets SET title='new'")
        status,result,_=self.request('GET',PAGE+'?'+urlencode({'limit':1,'cursor':page['next_cursor']}))
        self.assertEqual(status,409);self.assertEqual(result['code'],'asset_cursor_stale')

    def test_host_origin_methods_and_utf8_body_rules_preserve_originals(self):
        payload={'workspace_id':self.scope,'ids':[self.ids[0]]};body=json.dumps(payload).encode()
        for path in (PAGE,SELECTION):
            status,_=atomic_json_post(self.http.server_port,path,body,origin='https://evil.test')
            self.assertEqual(status,403)
        status,_,_=self.request('GET',PAGE,host='evil.test');self.assertEqual(status,403)
        status,_,_=self.request('GET',SELECTION);self.assertEqual(status,405)
        status,_=atomic_json_post(self.http.server_port,PAGE,body);self.assertEqual(status,405)
        for raw in (b'{}',b'[]',b'{"ids":[],"ids":[]}',b'\xff',json.dumps(payload).encode('utf-16'),
                    b'{"workspace_id":"'+self.scope.encode()+b'","ids":["same","same"]}'):
            status,result=atomic_json_post(self.http.server_port,SELECTION,raw)
            self.assertIn(status,(400,428));self.assertIn('code',result)
        status,_=atomic_json_post(self.http.server_port,SELECTION,b' '*32769);self.assertEqual(status,400)
        self.assertEqual(self.store.snapshot()['assets'][0]['metadata_revision'],0)

    def test_storage_failure_is_typed_without_sql_or_private_paths(self):
        import sqlite3
        with patch.object(self.store,'asset_page',side_effect=sqlite3.OperationalError('private/path SELECT secret')):
            status,result,_=self.request('GET',PAGE)
        self.assertEqual(status,503);self.assertEqual(result['code'],'asset_read_unavailable')
        self.assertNotIn('private',str(result));self.assertFalse(result['generation_submitted'])

    def test_ambiguous_framing_is_refused_before_any_selection_lookup(self):
        from http.client import HTTPConnection
        for fields in ([('Content-Length','0'),('Content-Length','0')],
                       [('Content-Length','0'),('Transfer-Encoding','chunked')],
                       [('Content-Length','-1')], [('Content-Length','999999999')]):
            with self.subTest(fields=fields), patch.object(self.store,'asset_selection',side_effect=AssertionError('Lookup reached')):
                connection=HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
                try:
                    connection.putrequest('POST',SELECTION,skip_host=True)
                    for name,value in [('Host','127.0.0.1:8191'),('Origin','http://127.0.0.1:8191'),
                                       ('Content-Type','application/json'),*fields]:connection.putheader(name,value)
                    connection.endheaders();response=connection.getresponse()
                    self.assertEqual(response.status,400);self.assertIn('code',json.loads(response.read()))
                finally:connection.close()

    def test_body_deadline_is_absolute_and_restores_socket_timeout(self):
        from studio_workflow import asset_read_http as transport
        class Socket:
            timeout=None
            def gettimeout(self):return self.timeout
            def settimeout(self,value):self.timeout=value
        connection=Socket();stream=SimpleNamespace(read1=lambda _:b'{')
        handler=SimpleNamespace(connection=connection,rfile=stream,_content_length=lambda _:10)
        with patch.object(transport.time,'monotonic',side_effect=[0,1,6]):
            with self.assertRaises(ValueError) as error:transport._body(handler)
        self.assertEqual(error.exception.status,408);self.assertIsNone(connection.timeout)

    def make_client(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.asset_read_client'),
                             'Typed asset observation client does not exist')
        module=importlib.import_module('studio_workflow.asset_read_client')
        client=module.AssetReadClient()
        # Only the TCP destination changes for the ephemeral test fixture. Real
        # production Host/Origin checks still run against their fixed 8191 values.
        port=self.http.server_port
        class Forward:
            def open(self,req,timeout):
                parts=urlsplit(req.full_url)
                target='http://127.0.0.1:'+str(port)+parts.path+('?' + parts.query if parts.query else '')
                req=Request(target,data=req.data,headers={**dict(req.header_items()),'Host':'127.0.0.1:8191'})
                return build_opener(ProxyHandler({})).open(req,timeout=timeout)
        client.opener=Forward();return client,module

    def test_typed_client_and_cli_use_actual_composed_http_routes(self):
        client,module=self.make_client();first=client.page(limit=1)
        second=client.page(limit=1,cursor=first['next_cursor'])
        self.assertEqual(second['assets'][0]['id'],self.ids[1])
        self.assertEqual(client.selection([self.ids[0]],workspace_id=self.scope)['items'][0]['state'],'active')
        with patch.object(module,'AssetReadClient',return_value=client),patch('sys.stdout',new_callable=io.StringIO) as out:
            self.assertEqual(module.main(['page','--limit','1']),0)
            self.assertEqual(len(json.loads(out.getvalue())['assets']),1)

    def test_client_preserves_typed_stale_refusal_without_retry(self):
        client,_=self.make_client();page=client.page(limit=1)
        with self.store.connection() as db:db.execute("UPDATE assets SET title='changed'")
        with patch.object(client.opener,'open',wraps=client.opener.open) as calls:
            with self.assertRaises(ValueError) as error:client.page(limit=1,cursor=page['next_cursor'])
        self.assertEqual(getattr(error.exception,'code',None),'asset_cursor_stale');self.assertEqual(calls.call_count,1)


if __name__=='__main__':unittest.main()
