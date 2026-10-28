"""Strict collection discovery: untrusted replies and the production HTTP owner."""
from contextlib import closing
import importlib
import io
import json
import sqlite3
import unittest
from http.client import IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import test_asset_read_client as responses
import test_asset_read_http as http_fixture
from studio_workflow.collection_http import encode_cursor
from studio_workflow.core import canonical
from studio_workflow.client import ClientError


class CollectionReadClientTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.collection_read_client'),
                             'Typed collection discovery is missing')
        self.module = importlib.import_module('studio_workflow.collection_read_client')
        self.client = self.module.CollectionReadClient(timeout=7)
        self.scope = 'a' * 32
        self.stamp = {'epoch': 'b' * 32, 'revision': 5}
        self.item = {'id': 'one', 'name': 'Keeps', 'description': 'Synthetic notes', 'revision': 1, 'count': 3}
        self.page = dict(format='studio.collection-page/v1', workspace_id=self.scope, catalogue=self.stamp,
                         limit=50, order='name_nocase_asc_id_asc', collections=[self.item], next_cursor=None,
                         observation_only=True, media_bytes_verified=False, generation_submitted=False)

    def reply(self, value, **kwargs):
        response = responses.Reply(value if isinstance(value, bytes) else canonical(value), **kwargs)
        self.client.opener = type('Transport', (), {'open': lambda _, request, timeout: response})()
        return response

    def cursor(self, **changes):
        position = dict(format='studio.collection-cursor/v1', workspace_id=self.scope,
                        catalogue=self.stamp, limit=50, last=['Before', 'earlier'])
        position.update(changes)
        return encode_cursor(position)

    def test_one_get_retains_exact_data_and_closes_transport(self):
        response = self.reply(self.page)
        with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
            self.assertEqual(self.client.page(workspace_id=self.scope), self.page)
        self.assertEqual(calls.call_count, 1)
        request = calls.call_args.args[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(urlsplit(request.full_url).path, '/api/collections')
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {'workspace_id': [self.scope], 'limit': ['50']})
        self.assertEqual(calls.call_args.kwargs['timeout'], 7)
        self.assertTrue(response.closed)

    def test_invalid_request_and_cross_scope_cursor_never_reach_transport(self):
        cases = [{'limit': n} for n in (0, 101, True, 1.5, None)]
        cases += [{'privacy': x} for x in ('Private', '', None, [], True)]
        cases += [{'workspace_id': x} for x in ('../x', 'A' * 32, 12)]
        cases += [{'cursor': x} for x in ('', 'x' * 2049, 'not-a-cursor', [])]
        cases += [dict(cursor=self.cursor(limit=1)), dict(cursor=self.cursor(privacy='private')),
                  dict(cursor=self.cursor(), workspace_id='c' * 32)]
        with patch.object(self.client.opener, 'open', side_effect=AssertionError('Unexpected I/O')) as calls:
            for args in cases:
                with self.subTest(args=str(args)[:80]), self.assertRaises(ValueError):
                    self.client.page(**args)
        calls.assert_not_called()

    def test_private_and_all_are_explicit_and_checked_per_row(self):
        self.item['privacy'] = 'private'
        for scope in ('private', 'all'):
            self.reply(self.page)
            with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
                self.assertEqual(self.client.page(privacy=scope), self.page)
            self.assertIn('privacy=' + scope, calls.call_args.args[0].full_url)
        for scope, classification in (('regular', 'private'), ('private', 'regular'), ('all', 'unknown'), ('all', [])):
            with self.subTest(scope=scope, classification=classification):
                self.item['privacy'] = classification
                self.reply(self.page)
                with self.assertRaises(ValueError): self.client.page(privacy=scope)

    def test_reply_schema_bounds_counts_and_unique_ids_fail_closed(self):
        cases = []
        for key, value in [('format', 'other'), ('limit', True), ('order', 'other'), ('workspace_id', 'c'*32),
                           ('observation_only', 1), ('media_bytes_verified', True), ('extra', 'not allowed'),
                           ('catalogue', {'epoch': 'b'*32, 'revision': True}), ('collections', {}),
                           ('collections', [self.item, self.item])]:
            cases.append(dict(self.page, **{key: value}))
        for key, value in [('id', '../x'), ('name', ''), ('name', 'x'*101), ('description', 'x'*1001),
                           ('description', None), ('count', -1), ('count', True), ('revision', 0),
                           ('revision', 1.5), ('unknown', 1)]:
            cases.append(dict(self.page, collections=[dict(self.item, **{key: value})]))
        for reply in cases:
            with self.subTest(reply=str(reply)[:120]):
                self.reply(reply)
                with self.assertRaises(ValueError): self.client.page(workspace_id=self.scope)

    def test_continuation_binds_catalogue_order_and_boundary_without_auto_paging(self):
        self.page['limit'] = 1
        self.page['next_cursor'] = self.cursor(limit=1, last=['Keeps', 'one'])
        self.reply(self.page)
        with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
            self.assertEqual(self.client.page(limit=1), self.page)
        self.assertEqual(calls.call_count, 1)
        for next_cursor in (self.cursor(limit=1), self.cursor(limit=1, privacy='private'),
                            self.cursor(limit=2), self.cursor(limit=1, workspace_id='c'*32),
                            self.cursor(limit=1, catalogue={'epoch':'b'*32,'revision':6})):
            self.reply(dict(self.page, next_cursor=next_cursor))
            with self.assertRaises(ValueError): self.client.page(limit=1)
        self.page['next_cursor'] = None
        self.reply(self.page)
        self.assertEqual(self.client.page(limit=1, cursor=self.cursor(limit=1)), self.page)
        self.reply(self.page)
        with self.assertRaises(ValueError): self.client.page(limit=1, cursor=self.cursor(limit=1,last=['Z','last']))
        self.reply(dict(self.page, catalogue={'epoch':'b'*32,'revision':6}))
        with self.assertRaises(ValueError): self.client.page(limit=1,cursor=self.cursor(limit=1))
        self.reply(dict(self.page, collections=[], next_cursor=self.cursor(limit=1)))
        with self.assertRaises(ValueError): self.client.page(limit=1)

    def test_order_matches_sqlite_nocase_including_unicode_and_embedded_nuls(self):
        names = ['a','A','aa','B','Z','Å','å','ß','SS','猫','a\0x','a\0yy','A\0猫','a\0xx']
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE TABLE names(id TEXT,name TEXT)')
            db.executemany('INSERT INTO names VALUES (?,?)', [('col-'+str(i), name) for i,name in enumerate(names)])
            ordered = db.execute('SELECT id,name FROM names ORDER BY name COLLATE NOCASE,id').fetchall()
        rows = [dict(self.item, id=key, name=name) for key,name in ordered]
        self.reply(dict(self.page, collections=rows))
        self.assertEqual(self.client.page()['collections'], rows)
        self.reply(dict(self.page, collections=list(reversed(rows))))
        with self.assertRaises(ValueError): self.client.page()
        # Every page boundary is checked against the same SQLite ordering.
        for left, right in zip(rows, rows[1:]):
            self.reply(dict(self.page,limit=1,collections=[right]))
            self.assertEqual(self.client.page(limit=1,cursor=self.cursor(limit=1,last=[left['name'],left['id']]))['collections'],[right])

    def test_duplicate_json_short_body_oversize_and_wrong_status_are_not_observations(self):
        for raw in (b'{"format":"a","format":"b"}', b'{"x":NaN}', b'\xff', b'{"x":"\\ud800"}'):
            self.reply(raw)
            with self.assertRaises(ValueError): self.client.page()
        self.reply(self.page, length=len(canonical(self.page))+1)
        with self.assertRaises(IncompleteRead): self.client.page()
        response = self.reply(b'{}', length=2*1024*1024+1)
        with self.assertRaises(ValueError): self.client.page()
        self.assertTrue(response.closed)
        response = self.reply(self.page); response.status = 202
        with self.assertRaises(ValueError): self.client.page()

    def test_http_conflict_preserves_code_and_is_never_retried(self):
        error = HTTPError(self.client.base,409,'Conflict',{},io.BytesIO(canonical({'error':'Explicit refresh required','code':'collection_cursor_stale'})))
        with patch.object(self.client.opener, 'open', side_effect=error) as calls:
            with self.assertRaises(ClientError) as raised: self.client.page()
        self.assertEqual(raised.exception.code,'collection_cursor_stale')
        self.assertEqual(calls.call_count,1)

    def test_cli_retains_explicit_inputs_and_prints_exact_json(self):
        with patch.object(self.module.CollectionReadClient,'page',return_value=self.page) as call, \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(self.module.main(['--workspace-id',self.scope,'--privacy','private','--limit','1','--cursor','abc']),0)
        self.assertEqual(call.call_args.kwargs,dict(workspace_id=self.scope,privacy='private',limit=1,cursor='abc'))
        self.assertEqual(json.loads(output.getvalue()),self.page)


class CollectionReadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.collection_read_client'))
        self.module=importlib.import_module('studio_workflow.collection_read_client')
        self.fixture=http_fixture.AssetReadHTTPTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        f=self.fixture;self.requests=[];requests=self.requests;base=f.http.RequestHandlerClass
        class EphemeralOrigin(base):
            def _safe_host(self): return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
            def do_GET(self):
                requests.append(('GET',self.path));return super().do_GET()
            def do_POST(self):
                requests.append(('POST',self.path));return super().do_POST()
        f.http.RequestHandlerClass=EphemeralOrigin
        self.url='http://127.0.0.1:'+str(f.http.server_port)
        self.client=self.module.CollectionReadClient(self.url,timeout=5)
        with f.store.connection() as db:
            db.executemany('INSERT INTO collections(id,name,description,created_at,privacy) VALUES(?,?,?,0,?)',
                           [('alpha','Alpha','', 'regular'),('beta','Beta','', 'regular'),('hidden','Hidden','private notes','private')])
            db.execute('INSERT INTO collection_assets VALUES (?,?)',('alpha',f.ids[0]))

    def test_native_http_default_private_all_and_off_page_ids_without_writes(self):
        f=self.fixture;before=f.store.snapshot(privacy='all')
        first=self.client.page(limit=1)
        second=self.client.page(limit=1,cursor=first['next_cursor'])
        self.assertEqual([first['collections'][0]['id'],second['collections'][0]['id']],['alpha','beta'])
        self.assertEqual(first['collections'][0]['count'],1)
        self.assertIsNone(second['next_cursor'])
        self.assertEqual([c['id'] for c in self.client.page(privacy='private')['collections']],['hidden'])
        self.assertEqual(len(self.client.page(privacy='all')['collections']),3)
        self.assertEqual(len(self.requests),4)
        self.assertEqual(f.store.snapshot(privacy='all'),before)
        self.assertTrue(all(method=='GET' and urlsplit(path).path=='/api/collections' for method,path in self.requests))
        with f.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM collection_commands_v1').fetchone()[0], 0)

    def test_hidden_edits_preserve_regular_cursor_and_visible_edits_refuse_without_retry(self):
        f=self.fixture;first=self.client.page(limit=1)
        with f.store.connection() as db: db.execute("UPDATE collections SET description='changed' WHERE id='hidden'")
        self.assertEqual(self.client.page(limit=1,cursor=first['next_cursor'])['collections'][0]['id'],'beta')
        with f.store.connection() as db: db.execute("UPDATE collections SET description='changed' WHERE id='beta'")
        with self.assertRaises(ClientError) as raised:self.client.page(limit=1,cursor=first['next_cursor'])
        self.assertEqual(raised.exception.code,'collection_cursor_stale');self.assertEqual(len(self.requests),3)
