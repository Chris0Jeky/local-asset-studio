"""The shared shell fixture uses the production catalogue query owner."""
import copy
import io
import json
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.parse import urlencode

import studio_browser_smoke as fixture


class CatalogueOwnerTests(unittest.TestCase):
    scope='f'*32

    def setUp(self):
        self.addCleanup(fixture.close_fixture_observations)
        prototype=fixture.ASSETS[0]
        rows=[
            dict(prototype,id='z-upper',title='Éclair',created_at=2,job_id='run-a',favorite=False,
                 run_label='Agent task',collections=['zeta']),
            dict(prototype,id='a-lower',title='éclair',created_at=3,job_id='run-b',favorite=True,
                 run_label='Make · Example',collections=['alpha']),
            dict(prototype,id='plain',title='Zulu',created_at=4,job_id='run-c',favorite=False,
                 tags=['needle_100%'],run_label=None,collections=['zeta']),
            dict(prototype,id='trash',title='Alpha',created_at=1,job_id='run-d',favorite=False,
                 trashed_at=123,collections=['zeta']),
        ]
        self.assets=self.enterContext(mock.patch.object(fixture,'ASSETS',copy.deepcopy(rows)))
        self.enterContext(mock.patch.object(fixture,'COLLECTIONS',[
            {'id':'zeta','name':'Zulu','description':''},{'id':'alpha','name':'Alpha','description':''}
        ],create=True))
        self.enterContext(mock.patch.object(fixture,'WORKSPACE_DELAY',0))
        self.enterContext(mock.patch.object(fixture,'FAIL_WORKSPACE',False))

    def get(self,path='/api/assets/page',**query):
        handler=SimpleNamespace(path=path+('?' + urlencode(query) if query else ''),workspace_id=self.scope,
                                json=lambda value,status=200:(status,value))
        return fixture.Handler.do_GET(handler)

    def select(self,ids,**query):
        body=json.dumps(dict(workspace_id=self.scope,ids=ids,**query)).encode()
        handler=SimpleNamespace(path='/api/assets/selection',workspace_id=self.scope,
                                headers={'Content-Length':str(len(body))},rfile=io.BytesIO(body),
                                json=lambda value,status=200:(status,value))
        return fixture.Handler.do_POST(handler)

    def test_native_page_size_cursor_and_query_binding(self):
        status,first=self.get(limit=1);self.assertEqual(status,200)
        self.assertEqual([a['id'] for a in first['assets']],['plain'])
        status,second=self.get(limit=1,cursor=first['next_cursor']);self.assertEqual(status,200)
        self.assertEqual([a['id'] for a in second['assets']],['a-lower'])
        status,refusal=self.get(limit=1,cursor=first['next_cursor'],sort='oldest')
        self.assertEqual(status,409)
        self.assertEqual(refusal['code'],'asset_cursor_mismatch')

    def test_native_filter_semantics_and_sqlite_title_order(self):
        for query,expected in [
            ({'source':'agent'},['z-upper']),
            ({'favorite':'false'},['plain','z-upper']),
            ({'visibility':'all'},['plain','a-lower','z-upper','trash']),
            ({'sort':'title'},['plain','z-upper','a-lower']),
            ({'q':'needle_100%'},['plain']),
            ({'collection_id':'zeta'},['plain','z-upper']),
        ]:
            with self.subTest(query=query):
                status,page=self.get(**query);self.assertEqual(status,200)
                self.assertEqual([a['id'] for a in page['assets']],expected)

    def test_reads_share_catalogue_stamp_and_synthetic_edits_make_cursors_stale(self):
        _,first=self.get(limit=1)
        _,same=self.get(limit=1);self.assertEqual(first['catalogue'],same['catalogue'])
        _,selection=self.select(['plain','missing','trash'],details=True)
        self.assertEqual(selection['catalogue'],first['catalogue'])
        self.assertEqual([item['state'] for item in selection['items']],['active','missing','trashed'])
        self.assertEqual(selection['items'][0]['asset']['url'],self.assets[2]['url'])
        self.assets[0]['notes']='Changed synthetic evidence'
        status,refusal=self.get(limit=1,cursor=first['next_cursor'])
        self.assertEqual(status,409)
        self.assertEqual(refusal['code'],'asset_cursor_stale')

    def test_collections_share_production_order_counts_and_scope_guard(self):
        status,page=self.get('/api/collections');self.assertEqual(status,200)
        self.assertEqual([(c['id'],c['count']) for c in page['collections']],[('alpha',1),('zeta',2)])
        _,assets=self.get();self.assertEqual(page['catalogue'],assets['catalogue'])
        status,refusal=self.get(workspace_id='e'*32)
        self.assertEqual(status,409)
        self.assertEqual(refusal['code'],'asset_workspace_conflict')


if __name__=='__main__':unittest.main()
