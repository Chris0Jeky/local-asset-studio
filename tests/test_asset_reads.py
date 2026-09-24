"""Real SQLite contracts for bounded asset observations; no media/runtime needed."""
import base64
from contextlib import contextmanager
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_workspace import workspace


class AssetReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = workspace.AssetWorkspace(self.temp.name)
        self.scope = self.store.snapshot()['workspace_id']
        self.seed(7)

    def seed(self, count, start=0):
        with self.store.connection() as db:
            db.executemany('''INSERT INTO assets
                (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,
                 created_at,preset_id,preset_name,source,lineage,notes,tags)
                VALUES (?,?,0,?,'image','media/not-read.png','frame.png',?,12,?,
                        'test','Test recipe','{}','[]','private notes','[]')''',
                [(f'asset-{i:06}', f'job-{i}', f'Title {i}', 'a'*64, float(i//3))
                 for i in range(start, start+count)])

    def page(self, **kwargs):
        self.assertTrue(callable(getattr(self.store, 'asset_page', None)),
                        'AssetWorkspace has no bounded page contract')
        return self.store.asset_page(**kwargs)

    def selection(self, ids, **kwargs):
        self.assertTrue(callable(getattr(self.store, 'asset_selection', None)),
                        'AssetWorkspace has no bounded off-page selection contract')
        return self.store.asset_selection(ids, workspace_id=kwargs.pop('workspace_id', self.scope), **kwargs)

    def expect_error(self, code, call, *args, **kwargs):
        with self.assertRaises(workspace.WorkspaceError) as error: call(*args, **kwargs)
        self.assertEqual(error.exception.code, code)
        return error.exception

    def test_pages_have_stable_ties_and_no_missing_or_duplicate_ids(self):
        cursor = None; found = []
        while True:
            result = self.page(limit=2, cursor=cursor)
            self.assertEqual(result['format'], 'studio.asset-page/v1')
            self.assertEqual(result['workspace_id'], self.scope)
            self.assertTrue(result['observation_only'])
            self.assertFalse(result['generation_submitted'])
            self.assertFalse(result['media_bytes_verified'])
            self.assertLessEqual(len(result['assets']), 2)
            found += [a['id'] for a in result['assets']]
            cursor = result['next_cursor']
            if cursor is None: break
        self.assertEqual(found, [f'asset-{i:06}' for i in reversed(range(7))])

    def test_empty_page_and_exact_page_boundary_have_no_phantom_continuation(self):
        self.assertIsNone(self.page(limit=7)['next_cursor'])
        self.assertEqual(self.page(filters={'visibility': 'trash'})['assets'], [])
        self.assertIsNone(self.page(filters={'visibility': 'trash'})['next_cursor'])

    def test_summary_does_not_decode_large_or_corrupt_private_fields(self):
        with self.store.connection() as db:
            db.execute("UPDATE assets SET source='not JSON',lineage='not JSON',tags='not JSON',notes=?", ('secret'*200000,))
            db.execute('UPDATE assets SET title=?,filename=?,preset_name=?', ('🌙'*500, 'x'*500, 'y'*500))
        with patch.object(self.store, '_asset', side_effect=AssertionError('Full asset decoded')), \
             patch.object(self.store, 'file', side_effect=AssertionError('Media read')), \
             patch.object(self.store, 'snapshot', side_effect=AssertionError('Full snapshot')):
            result = self.page(limit=1)
        a = result['assets'][0]
        self.assertEqual(len(a['title']), 200)
        self.assertEqual(set(a['truncated_fields']), {'title','filename','preset_name'})
        self.assertFalse(set(a) & {'notes','tags','lineage','source','path','collections'})
        self.assertLess(len(json.dumps(result).encode()), 10000)

    def test_filters_are_typed_and_bound_to_cursor(self):
        with self.store.connection() as db:
            db.execute("UPDATE assets SET favorite=1,review='selected' WHERE id >= 'asset-000004'")
            db.execute("UPDATE assets SET trashed_at=0 WHERE id='asset-000006'")
        active = self.page(filters={'favorite': True, 'review':'selected'}, limit=1)
        self.assertEqual(active['assets'][0]['id'], 'asset-000005')
        trash = self.page(filters={'visibility':'trash'})
        self.assertEqual([a['id'] for a in trash['assets']], ['asset-000006'])
        self.expect_error('asset_cursor_mismatch', self.page, limit=1, cursor=active['next_cursor'])
        self.expect_error('asset_cursor_mismatch', self.page, limit=2, cursor=active['next_cursor'],
                          filters={'favorite':True,'review':'selected'})
        self.assertEqual(self.page(limit=1,cursor=active['next_cursor'],
                         filters={'review':'selected','favorite':True})['assets'][0]['id'], 'asset-000004')

    def test_all_mutation_classes_invalidate_instead_of_mixing_pages(self):
        col = self.store.collection({'name':'Example'})['id']
        statements = [
            ("UPDATE assets SET notes='new' WHERE id='asset-000000'", ()),
            ("UPDATE assets SET trashed_at=1 WHERE id='asset-000001'", ()),
            ("UPDATE assets SET trashed_at=NULL WHERE id='asset-000001'", ()),
            ("INSERT INTO collection_assets VALUES (?, 'asset-000000')", (col,)),
            ("DELETE FROM collection_assets WHERE collection_id=?", (col,)),
            ("UPDATE collections SET name='Renamed' WHERE id=?", (col,)),
            ("DELETE FROM collections WHERE id=?", (col,)),
            ("DELETE FROM assets WHERE id='asset-000002'", ()),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql):
                cursor = self.page(limit=1)['next_cursor']
                with self.store.connection() as db: db.execute(sql, params)
                e = self.expect_error('asset_cursor_stale', self.page, cursor=cursor, limit=1)
                self.assertEqual(e.status,409)
        cursor = self.page(limit=1)['next_cursor']; self.seed(1,100)
        self.expect_error('asset_cursor_stale', self.page, cursor=cursor, limit=1)

    def test_rollback_does_not_expire_a_cursor(self):
        first = self.page(limit=2)
        with self.store.connection() as db:
            db.execute("UPDATE assets SET title='rollback'"); db.rollback()
        second = self.page(limit=2,cursor=first['next_cursor'])
        self.assertEqual(first['catalogue'],second['catalogue'])

    def test_restart_preserves_valid_cursor_and_scope(self):
        first = self.page(limit=2)
        self.store = workspace.AssetWorkspace(self.temp.name)
        second = self.page(limit=2,cursor=first['next_cursor'])
        self.assertEqual(second['catalogue'], first['catalogue'])
        self.assertEqual(second['assets'][0]['id'],'asset-000004')

    def test_query_only_connection_supports_page_and_selection_without_repairs(self):
        self.page(); original = self.store.connection
        @contextmanager
        def readonly():
            with original() as db:
                db.execute('PRAGMA query_only=ON'); yield db
        with patch.object(self.store,'connection',readonly):
            self.assertEqual(len(self.page()['assets']),7)
            self.assertEqual(self.selection(['asset-000000'])['items'][0]['state'],'active')

    def test_foreign_scope_and_cursor_never_read_asset_rows(self):
        cursor=self.page(limit=1)['next_cursor']; queries=[]; original=self.store.connection
        @contextmanager
        def traced():
            with original() as db:
                db.set_trace_callback(queries.append); yield db
        with patch.object(self.store,'connection',traced):
            self.expect_error('asset_workspace_conflict',self.page,workspace_id='b'*32)
            self.expect_error('asset_workspace_conflict',self.selection,['asset-000000'],workspace_id='b'*32)
        self.assertFalse(any('FROM assets' in q for q in queries))
        with tempfile.TemporaryDirectory() as other:
            self.store=workspace.AssetWorkspace(other)
            self.expect_error('asset_workspace_conflict',self.page,cursor=cursor,limit=1)

    def test_invalid_inputs_fail_before_database_access(self):
        self.page()
        with patch.object(self.store,'connection',side_effect=AssertionError('Database reached')):
            for value in (0,101,True,1.0,'2',None):
                with self.subTest(limit=value): self.expect_error('asset_read_invalid',self.page,limit=value)
            for filters in ([],{'search':'text'},{'visibility':'hidden'},{'favorite':1},
                            {'review':'accepted'},{'collection_id':''},{'media_type':[]}):
                with self.subTest(filters=filters): self.expect_error('asset_read_invalid',self.page,filters=filters)
            for ids in ([],['same','same'],['x']*201,[True],['x'*129],iter(['x'])):
                self.expect_error('asset_read_invalid',self.selection,ids)
            for cursor in ('', 'x'*2049, 'a=', '!!!', base64.urlsafe_b64encode(b'null').decode().rstrip('=')):
                self.expect_error('asset_cursor_invalid',self.page,cursor=cursor)

    def test_selected_ids_preserve_order_and_distinguish_missing_from_off_page(self):
        self.page(limit=1)
        with self.store.connection() as db: db.execute("UPDATE assets SET trashed_at=0 WHERE id='asset-000001'")
        result=self.selection(['asset-000000','missing','asset-000001'])
        self.assertEqual([i['id'] for i in result['items']], ['asset-000000','missing','asset-000001'])
        self.assertEqual([i['state'] for i in result['items']], ['active','missing','trashed'])
        self.assertIsNone(result['items'][1]['asset'])
        self.assertEqual(result['items'][0]['asset']['metadata_revision'],0)
        self.assertEqual(result['workspace_id'],self.scope)

    def test_collection_filter_uses_current_membership_and_refuses_missing_collection(self):
        col=self.store.collection({'name':'Example'})['id']
        with self.store.connection() as db:
            db.executemany('INSERT INTO collection_assets VALUES (?,?)', [(col,'asset-000001'),(col,'asset-000004')])
        first=self.page(filters={'collection_id':col},limit=1)
        self.assertEqual(first['assets'][0]['id'],'asset-000004')
        self.assertEqual(self.page(filters={'collection_id':col},limit=1,cursor=first['next_cursor'])['assets'][0]['id'],'asset-000001')
        self.expect_error('asset_collection_unavailable',self.page,filters={'collection_id':'missing'})

    def test_large_keyset_walk_has_bounded_rows_and_payload(self):
        for size in (100,1000,10000):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as root:
                self.store=workspace.AssetWorkspace(root); self.seed(size)
                cursor=None; seen=set(); max_bytes=0
                while True:
                    page=self.page(limit=100,cursor=cursor)
                    self.assertLessEqual(len(page['assets']),100)
                    ids={x['id'] for x in page['assets']}
                    self.assertFalse(seen & ids); seen.update(ids)
                    max_bytes=max(max_bytes,len(json.dumps(page).encode()))
                    cursor=page['next_cursor']
                    if cursor is None:break
                self.assertEqual(len(seen),size)
                self.assertLess(max_bytes,128*1024)

    def test_continuation_uses_indexed_keyset_not_offset_or_full_snapshot(self):
        first=self.page(limit=2); queries=[]; original=self.store.connection
        @contextmanager
        def traced():
            with original() as db:
                db.set_trace_callback(queries.append);yield db
        with patch.object(self.store,'connection',traced):self.page(limit=2,cursor=first['next_cursor'])
        sql=next(q for q in queries if 'FROM assets AS a' in q)
        self.assertNotIn('OFFSET',sql.upper());self.assertIn('LIMIT 3',sql)
        self.assertNotIn('SELECT *',sql.upper());self.assertNotIn('COUNT(',sql.upper())
        with original() as db:plan=' '.join(r[3] for r in db.execute('EXPLAIN QUERY PLAN '+sql))
        self.assertIn('SEARCH',plan);self.assertIn('asset_read',plan)
        self.assertNotIn('TEMP B-TREE',plan)

    def test_unknown_state_version_is_not_silently_reinitialized(self):
        self.page()
        with self.store.connection() as db:db.execute('UPDATE asset_read_state_v1 SET version=2')
        self.expect_error('asset_read_unavailable',self.page)
        with self.assertRaises(ValueError):workspace.AssetWorkspace(self.temp.name)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT version FROM asset_read_state_v1').fetchone()[0],2)


    def test_sql_projection_does_not_alias_an_identity_containing_nul(self):
        with self.store.connection() as db:
            db.execute("UPDATE assets SET id=? WHERE id='asset-000006'", ('asset-alias\0hidden',))
        self.expect_error('asset_read_unavailable',self.page)

    def test_embedded_nul_in_display_label_is_not_silently_cut_by_sql_substr(self):
        title='prefix\0suffix🌙'
        with self.store.connection() as db:db.execute('UPDATE assets SET title=?',(title,))
        item=self.page(limit=1)['assets'][0]
        self.assertEqual(item['title'],title)
        self.assertEqual(item['truncated_fields'],[])

    def test_label_prefix_handles_a_split_four_byte_scalar_without_losing_text(self):
        title='abc'+'🌙'*300
        with self.store.connection() as db:db.execute('UPDATE assets SET title=?',(title,))
        item=self.page(limit=1)['assets'][0]
        self.assertEqual(item['title'],title[:200])
        self.assertEqual(item['truncated_fields'],['title'])

    def test_exhausted_change_stamp_refuses_mutation_with_typed_error_and_rollback(self):
        self.page()
        with self.store.connection() as db:db.execute('UPDATE asset_read_state_v1 SET revision=?',(workspace.MAX_REVISION,))
        self.expect_error('asset_read_unavailable',self.store.update,
            {'ids':['asset-000000'],'action':'edit','title':'not committed',
             'request_id':'exhausted-catalogue-0001','expected_revisions':{'asset-000000':0}})
        self.assertEqual(self.store.get('asset-000000')['title'],'Title 0')
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],0)

    def test_missing_change_stamp_refuses_existing_writes_without_partial_commit(self):
        self.page()
        with self.store.connection() as db:db.execute('DELETE FROM asset_read_state_v1')
        self.expect_error('asset_read_unavailable',self.page)
        self.expect_error('asset_read_unavailable',self.store.update,
            {'ids':['asset-000000'],'action':'edit','title':'not committed',
             'request_id':'missing-catalogue-0001','expected_revisions':{'asset-000000':0}})
        self.assertEqual(self.store.get('asset-000000')['title'],'Title 0')

    def test_wal_read_keeps_identity_stamp_and_rows_in_the_same_snapshot(self):
        import threading
        self.page()
        original=self.store.connection; observed=[]; errors=[]; changed=False
        def write():
            try:
                with original() as db:db.execute("UPDATE assets SET title='concurrent'")
            except BaseException as exc:errors.append(exc)
        @contextmanager
        def interleaved():
            with original() as db:
                def trace(sql):
                    nonlocal changed
                    if 'FROM asset_read_state_v1' in sql and not changed:
                        changed=True
                        writer=threading.Thread(target=write)
                        writer.start();writer.join(5)
                        observed.append(not writer.is_alive())
                db.set_trace_callback(trace);yield db
        with patch.object(self.store,'connection',interleaved):old=self.page(limit=1)
        self.assertEqual(observed,[True]);self.assertEqual(errors,[])
        self.assertEqual(old['assets'][0]['title'],'Title 6')
        self.assertEqual(self.page(limit=1)['assets'][0]['title'],'concurrent')
        self.expect_error('asset_cursor_stale',self.page,limit=1,cursor=old['next_cursor'])

    def test_two_real_writers_advance_one_shared_stamp(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        before=self.page();other=workspace.AssetWorkspace(self.temp.name);gate=threading.Barrier(2)
        def write(pair):
            store,key=pair;gate.wait(timeout=5)
            return store.update({'ids':[key],'action':'edit','title':'new',
                'request_id':'concurrent-read-'+key,'expected_revisions':{key:0}})
        with ThreadPoolExecutor(2) as pool:
            result=list(pool.map(write,[(self.store,'asset-000000'),(other,'asset-000001')]))
        self.assertTrue(all(r['status']=='applied' for r in result))
        self.assertEqual(self.page()['catalogue']['revision'],before['catalogue']['revision']+2)

    def test_malformed_cursor_json_cannot_bypass_its_value_bounds(self):
        def token(raw):return base64.urlsafe_b64encode(raw).decode().rstrip('=')
        for raw in (b'{"position":1,"position":2}',b'{"position":NaN}',b'['*1100+b']'*1100,
                    '{"position":1}'.encode('utf-16'),b'\xff'):
            self.expect_error('asset_cursor_invalid',self.page,cursor=token(raw))
        first=self.page(limit=1)['next_cursor']
        raw=base64.urlsafe_b64decode(first+'='*((-len(first))%4))
        changed=json.loads(raw);changed['position']['last'][1]='wrong'
        self.expect_error('asset_cursor_invalid',self.page,cursor=token(json.dumps(changed).encode()))

    def test_initialization_adds_derived_state_without_rewriting_legacy_records(self):
        self.page()
        before=self.store.snapshot()
        with self.store.connection() as db:
            triggers=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'asset_read_%'")]
            for name in triggers:db.execute('DROP TRIGGER '+name)
            db.execute('DROP TABLE asset_read_state_v1')
            db.execute('DROP INDEX asset_read_order_v1');db.execute('DROP INDEX asset_read_active_v1')
        self.store=workspace.AssetWorkspace(self.temp.name)
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(len(self.page()['assets']),7)


    def test_optional_invalid_scalars_are_not_relabelled_as_absent(self):
        for column,value in [('preset_id','bad\0id'),('preset_id','x'*129),('trashed_at','not a timestamp')]:
            with self.subTest(column=column,value=value):
                with self.store.connection() as db:
                    db.execute('UPDATE assets SET preset_id=NULL,trashed_at=NULL')
                    db.execute('UPDATE assets SET '+column+'=?',(value,))
                self.expect_error('asset_read_unavailable',self.page,filters={'visibility':'all'})

    def test_invalid_large_scalar_is_bounded_before_python_projection(self):
        from studio_workflow import asset_reads
        original=asset_reads._summary;sizes=[]
        def observed(row):
            sizes.extend(len(v) for v in row if type(v) in (str,bytes))
            return original(row)
        with self.store.connection() as db:db.execute('UPDATE assets SET bytes=?',(b'x'*1000000,))
        with patch.object(asset_reads,'_summary',observed):
            self.expect_error('asset_read_unavailable',self.page)
        self.assertLess(max(sizes),1024,'A corrupt scalar was materialized without a SQL bound')

    def test_legacy_media_type_lists_in_page_and_exact_filter(self):
        with self.store.connection() as db:
            db.execute("UPDATE assets SET media_type='image/png' WHERE id='asset-000006'")
        unfiltered = self.page()
        self.assertIn('image/png', [a['media_type'] for a in unfiltered['assets']],
                      'A listed legacy media type must be exactly filterable')
        selected = self.page(filters={'media_type': 'image/png'})
        self.assertEqual([a['id'] for a in selected['assets']], ['asset-000006'])
        self.assertIsNone(selected['next_cursor'])
        for bad in ('x'*33, 'bad\x01type'):
            with self.subTest(filter=repr(bad)):
                self.expect_error('asset_read_invalid', self.page, filters={'media_type': bad})
        with self.store.connection() as db:
            db.execute('UPDATE assets SET media_type=? WHERE id=?', ('x'*33, 'asset-000006'))
        before = self.store.snapshot()
        self.expect_error('asset_read_unavailable', self.page)
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT media_type FROM assets WHERE id='asset-000006'").fetchone()[0], 'x'*33)
        self.assertEqual(self.store.snapshot(), before, 'Reading must not repair or rewrite stored text')


if __name__=='__main__':unittest.main()
