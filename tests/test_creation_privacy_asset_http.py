"""Explicit privacy scope through the composed asset handlers and agent client."""
from http.client import HTTPConnection
import json
from pathlib import Path
import unittest

import test_asset_read_http as http_fixture


class CreationPrivacyAssetHTTPTests(unittest.TestCase):
    tearDown = http_fixture.AssetReadHTTPTests.tearDown

    def setUp(self):
        http_fixture.AssetReadHTTPTests.setUp(self)
        source = Path(self.temp.name)/'image.png'
        self.private = self.store.register({'id':'private-canary','privacy':'private','created_at':9,
                        'preset_name':'Quiet canary','outputs':[{'filename':'image.png'}]},0,source)

    def request(self, method, path, body=None, privacy=None, creation=None):
        connection = HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        headers = {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'}
        if privacy is not None: headers['X-Studio-Privacy'] = privacy
        if creation is not None: headers['X-Studio-Creation-Privacy'] = creation
        try:
            connection.request(method,path,json.dumps(body) if body is not None else None,headers)
            response = connection.getresponse()
            return response.status,json.loads(response.read())
        finally: connection.close()

    def test_header_scope_reaches_the_paged_sql_query(self):
        status, result = self.request('GET','/api/assets/page',privacy='private')
        self.assertEqual(status,200)
        self.assertEqual([a['id'] for a in result['assets']],[self.private])
        status, regular = self.request('GET','/api/assets/page?q=canary')
        self.assertEqual(status,200); self.assertEqual(regular['assets'],[])

    def test_query_scope_header_conflicts_and_invalid_scopes_fail_closed(self):
        for path, header in [('/api/assets/page?privacy=private','regular'),
                             ('/api/assets/page?privacy=all&privacy=private',None),
                             ('/api/assets/page','PRIVATE')]:
            with self.subTest(path=path,header=header):
                status, result = self.request('GET',path,privacy=header)
                self.assertEqual(status,400)
                self.assertNotIn('Quiet canary',json.dumps(result))

    def test_selection_header_and_body_scopes_must_agree(self):
        body = {'workspace_id':self.scope,'ids':[self.private]}
        status, hidden = self.request('POST','/api/assets/selection',body)
        self.assertEqual(status,200); self.assertEqual(hidden['items'][0]['state'],'missing')
        for payload, header in [(dict(body,privacy='private'),None),(body,'private')]:
            status, result = self.request('POST','/api/assets/selection',payload,privacy=header)
            self.assertEqual(status,200); self.assertEqual(result['items'][0]['asset']['id'],self.private)
        self.assertEqual(self.request('POST','/api/assets/selection',dict(body,privacy='private'),privacy='regular')[0],400)

    def test_private_collection_pages_use_header_scope_and_cursor_scope(self):
        self.store.collection({'name':'Ordinary shelf'})
        private = self.store.collection({'name':'Quiet shelf'},privacy='private')
        status, result = self.request('GET','/api/collections',privacy='private')
        self.assertEqual(status,200)
        self.assertEqual([c['id'] for c in result['collections']],[private['id']])
        status, regular = self.request('GET','/api/assets/page?include_collections=true')
        self.assertEqual(status,200)
        self.assertNotIn(private['id'],json.dumps(regular))

    def test_private_collection_creation_header_is_not_regularized_by_the_read_view(self):
        for view in ('regular','all'):
            with self.subTest(view=view):
                body = {'format':'studio.collection-command/v1','action':'create',
                        'request_id':'private-collection-'+view,'workspace_id':self.scope,
                        'name':'Private collection '+view,'description':'Private description canary'}
                status, result = self.request('POST','/api/collections',body,privacy=view,creation='private')
                self.assertEqual(status,200,result)
                key = result['receipt']['result']['id']
                self.assertNotIn(key,json.dumps(self.store.snapshot()))
                self.assertIn(key,json.dumps(self.store.snapshot(privacy='private')))
                hidden_status, hidden = self.request('GET','/api/collections/commands/'+body['request_id']+'?workspace_id='+self.scope)
                self.assertEqual(hidden_status,200); self.assertEqual(hidden['status'],'unknown')
                self.assertIsNone(hidden['receipt']); self.assertNotIn('Private description',json.dumps(hidden))
                status, replay = self.request('POST','/api/collections',body,privacy=view,creation='private')
                self.assertEqual(status,200,replay); self.assertTrue(replay['replayed'])

    def test_default_agent_reads_hide_private_and_explicit_arguments_reveal_it(self):
        from studio_workflow.agent_bridge import AgentBridge
        from studio_workflow.client import Client
        base = self.http.RequestHandlerClass
        class LocalOrigin(base):
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:'+str(self.server.server_port)
            def _safe_mutation(self):
                return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:'+str(self.server.server_port)
        self.http.RequestHandlerClass = LocalOrigin
        bridge = AgentBridge(Client('http://127.0.0.1:'+str(self.http.server_port),timeout=3))
        ordinary = bridge.invoke('asset_page',{})
        self.assertTrue(ordinary['ok'],ordinary)
        self.assertNotIn(self.private,ordinary['data_json'])
        for name, arguments in [('asset_page',{'filters':{'privacy':'private'}}),
                                ('asset_selection',{'workspace_id':self.scope,'ids':[self.private],'privacy':'private'})]:
            result = bridge.invoke(name,arguments)
            self.assertTrue(result['ok'],result)
            self.assertIn(self.private,result['data_json'])


if __name__ == '__main__': unittest.main()
