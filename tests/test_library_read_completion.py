"""Current-position Library reads remain bounded, scoped and honest under writes."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_asset_reads as baseline
from studio_workflow import asset_reads


class LibraryReadCompletionTests(unittest.TestCase):
    setUp = baseline.AssetReadTests.setUp
    seed = baseline.AssetReadTests.seed
    page = baseline.AssetReadTests.page
    selection = baseline.AssetReadTests.selection
    expect_error = baseline.AssetReadTests.expect_error

    def edit(self, asset_id, **changes):
        with self.store.connection() as db:
            revision = db.execute('SELECT metadata_revision FROM assets WHERE id=?',(asset_id,)).fetchone()[0]
        return self.store.update(dict(action='edit',ids=[asset_id],workspace_id=self.scope,
            request_id='library-completion-'+str(revision),expected_revisions={asset_id:revision},**changes))

    def test_explicit_job_filter_precedes_limit_and_binds_continuation(self):
        self.seed(100,7)
        with self.store.connection() as db:
            db.execute("UPDATE assets SET job_id='same-run',output_index=CAST(substr(id,7) AS INTEGER) WHERE id<'asset-000003'")
        first=self.page(limit=2,filters={'job_id':'same-run'})
        second=self.page(limit=2,filters={'job_id':'same-run'},cursor=first['next_cursor'])
        self.assertEqual([a['id'] for a in first['assets']+second['assets']],['asset-000002','asset-000001','asset-000000'])
        self.assertIsNone(second['next_cursor'])
        self.expect_error('asset_cursor_mismatch',self.page,limit=2,filters={'job_id':'other'},cursor=first['next_cursor'])
        self.assertEqual(self.page(filters={'job_id':'missing-run'})['assets'],[])

    def test_job_filter_and_new_read_options_refuse_bad_types_before_database(self):
        with patch.object(self.store,'connection',side_effect=AssertionError('Database reached')):
            for job in ('','a'*129,'bad\0id',1,True,[],{}):
                with self.subTest(job=job):self.expect_error('asset_read_invalid',self.page,filters={'job_id':job})
            for key in ('reanchor','include_collections'):
                for value in (None,1,'true',[]):
                    with self.subTest(key=key,value=value):self.expect_error('asset_read_invalid',self.page,**{key:value})

    def test_legacy_summary_and_omitted_job_filter_keep_response_and_cursor_identity(self):
        first=self.page(limit=2)
        self.assertEqual(self.page(limit=2,filters={'job_id':None}),first)
        self.assertFalse({'cursor','collection_page','unavailable_assets'} & set(first))
        self.assertEqual(first['filters'],asset_reads.DEFAULT_FILTERS)

    def test_confirmed_edit_reanchors_same_position_without_relaxing_normal_next(self):
        first=self.page(limit=2);old_cursor=first['next_cursor']
        before=self.page(limit=2,cursor=old_cursor,details=True)
        self.edit('asset-000004',title='Confirmed new title')
        self.seed(1,107)  # Newer content must not send the user back to page 1.
        self.expect_error('asset_cursor_stale',self.page,limit=2,cursor=old_cursor)
        refreshed=self.page(workspace_id=self.scope,limit=2,cursor=old_cursor,details=True,reanchor=True)
        self.assertEqual([a['id'] for a in refreshed['assets']],[a['id'] for a in before['assets']])
        self.assertEqual(refreshed['assets'][0]['title'],'Confirmed new title')
        self.assertEqual(asset_reads._cursor(refreshed['cursor'])['last'],asset_reads._cursor(old_cursor)['last'])
        self.assertEqual(asset_reads._cursor(refreshed['cursor'])['catalogue'],refreshed['catalogue'])
        self.assertEqual(self.page(limit=2,cursor=refreshed['cursor'],details=True),refreshed)

    def test_reanchor_handles_deleted_boundary_and_all_sort_orders(self):
        for sort in ('newest','oldest','title'):
            with self.subTest(sort=sort):
                first=self.page(limit=1,sort=sort);cursor=first['next_cursor']
                expected=self.page(limit=1,sort=sort,cursor=cursor)['assets'][0]['id']
                with self.store.connection() as db:db.execute('DELETE FROM assets WHERE id=?',(first['assets'][0]['id'],))
                current=self.page(workspace_id=self.scope,limit=1,sort=sort,cursor=cursor,reanchor=True)
                self.assertEqual(current['assets'][0]['id'],expected)
                self.assertEqual(asset_reads._cursor(current['cursor'])['last'],asset_reads._cursor(cursor)['last'])

    def test_reanchor_refuses_foreign_scope_query_epoch_and_future_revision(self):
        cursor=self.page(limit=2)['next_cursor']
        self.expect_error('asset_workspace_conflict',self.page,workspace_id='f'*32,limit=2,cursor=cursor,reanchor=True)
        self.expect_error('asset_cursor_mismatch',self.page,workspace_id=self.scope,limit=1,cursor=cursor,reanchor=True)
        self.expect_error('asset_cursor_mismatch',self.page,workspace_id=self.scope,limit=2,cursor=cursor,reanchor=True,filters={'source':'mine'})
        old=asset_reads._cursor(cursor)
        future=asset_reads._encode_cursor(self.scope,dict(old['catalogue'],revision=old['catalogue']['revision']+100),old['query_sha256'],2,{'id':old['last'][1],'created_at':old['last'][0]})
        self.expect_error('asset_cursor_stale',self.page,workspace_id=self.scope,limit=2,cursor=future,reanchor=True)
        with self.store.connection() as db:db.execute("UPDATE asset_read_state_v1 SET epoch=?",('c'*32,))
        self.expect_error('asset_cursor_stale',self.page,workspace_id=self.scope,limit=2,cursor=cursor,reanchor=True)

    def test_asset_and_collection_snapshot_survives_writer_between_projections(self):
        with self.store.connection() as db:
            db.execute("INSERT INTO collections(id,name,description,created_at) VALUES ('keeps','Keeps','',1)")
            db.execute("INSERT INTO collection_assets VALUES ('keeps','asset-000006')")
        original=self.store._library_assets;writer=baseline.workspace.AssetWorkspace(self.temp.name)
        def concurrent_write(*args,**kwargs):
            with writer.connection() as db:db.execute("UPDATE assets SET trashed_at=10 WHERE id='asset-000006'")
            return original(*args,**kwargs)
        with patch.object(self.store,'_library_assets',side_effect=concurrent_write):
            page=self.page(details=True,include_collections=True)
        self.assertIn('asset-000006',[a['id'] for a in page['assets']])
        self.assertEqual(page['collection_page']['collections'][0]['count'],1)
        self.assertEqual(page['collection_page']['workspace_id'],page['workspace_id'])
        self.assertEqual(page['collection_page']['catalogue'],page['catalogue'])
        fresh=self.page(details=True,include_collections=True)
        self.assertNotIn('asset-000006',[a['id'] for a in fresh['assets']])
        self.assertEqual(fresh['collection_page']['collections'][0]['count'],0)

    def test_collection_bundle_is_bounded_and_continues_with_existing_contract(self):
        with self.store.connection() as db:
            db.executemany('INSERT INTO collections(id,name,description,created_at) VALUES (?,?,?,1)',[(f'c{i:03}',f'Collection {i:03}','') for i in range(103)])
        page=self.page(include_collections=True)
        collections=page['collection_page']
        self.assertEqual(len(collections['collections']),100)
        rest=self.store.collection_page(workspace_id=self.scope,limit=100,cursor=collections['next_cursor'])
        self.assertEqual(len(rest['collections']),3)
        self.assertEqual(rest['catalogue'],page['catalogue'])

    def test_writer_accepted_unicode_tags_are_complete_on_page_and_selection(self):
        tags=[chr(0x1f300+i)*60 for i in range(30)]
        self.edit('asset-000006',tags=tags)
        self.assertGreater(len(json.dumps(tags).encode()),8192)
        page=self.page(details=True)
        self.assertEqual(page['assets'][0]['tags'],tags)
        self.assertEqual(page['unavailable_assets'],[])
        self.assertEqual(self.selection(['asset-000006'],details=True)['items'][0]['asset']['tags'],tags)

    def test_registered_maximum_unicode_title_has_a_bounded_title_cursor(self):
        title='A'+'🌙'*1023
        with self.store.connection() as db:db.execute('UPDATE assets SET title=? WHERE id=?',(title,'asset-000006'))
        first=self.page(limit=1,sort='title')
        self.assertEqual(first['assets'][0]['id'],'asset-000006')
        self.assertLessEqual(len(first['next_cursor']),asset_reads.MAX_CURSOR)
        self.assertEqual(asset_reads._cursor(first['next_cursor'])['last'][0],title)
        second=self.page(limit=1,sort='title',cursor=first['next_cursor'])
        self.assertEqual(second['assets'][0]['id'],'asset-000000')
        self.expect_error('asset_cursor_invalid',self.page,cursor='x'*(asset_reads.MAX_CURSOR+1))

    def test_writer_accepted_escaped_title_has_a_bounded_title_cursor(self):
        source=Path(self.temp.name)/'output.png';source.write_bytes(b'Synthetic registration fixture')
        identifier=self.store.register({'id':'escaped-title-job','preset_name':'\0'*1024,
            'created_at':1,'outputs':[{'filename':'output.png','media_type':'image'}]},0,source)
        first=self.page(sort='title',limit=1)
        self.assertEqual(first['assets'][0]['id'],identifier)
        self.assertGreater(len(first['next_cursor']),8192)
        self.assertLessEqual(len(first['next_cursor']),asset_reads.MAX_CURSOR)
        second=self.page(sort='title',limit=1,cursor=first['next_cursor'])
        self.assertEqual(second['assets'][0]['id'],'asset-000000')

    def test_private_text_decode_failure_is_isolated_before_sqlite_materialization(self):
        with self.store.connection() as db:db.execute("UPDATE assets SET source=CAST(X'80' AS TEXT) WHERE id='asset-000003'")
        page=self.page(details=True)
        self.assertEqual(len(page['assets']),6)
        self.assertEqual([e['id'] for e in page['unavailable_assets']],['asset-000003'])
        self.expect_error('asset_read_unavailable',self.selection,['asset-000003'],details=True)
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT hex(CAST(source AS BLOB)) FROM assets WHERE id='asset-000003'").fetchone()[0],'80')

    def test_writer_accepted_tags_remain_complete_in_utf16_databases(self):
        from test_asset_read_encoding import AssetReadEncodingTests
        tags=[chr(0x1f300+i)*60 for i in range(30)]
        for encoding in ('UTF-16le','UTF-16be'):
            with self.subTest(encoding=encoding):
                AssetReadEncodingTests.encoded_store(self,encoding)
                self.scope=self.store.asset_page()['workspace_id']
                self.edit('asset-000006',tags=tags)
                with self.store.connection() as db:
                    size=db.execute('SELECT length(CAST(tags AS BLOB)) FROM assets WHERE id=?',('asset-000006',)).fetchone()[0]
                self.assertGreater(size,32000)
                self.assertEqual(self.page(details=True)['assets'][0]['tags'],tags)
                self.assertEqual(self.selection(['asset-000006'],details=True)['items'][0]['asset']['tags'],tags)

    def test_one_oversize_record_does_not_hide_other_assets_or_become_missing(self):
        with self.store.connection() as db:db.execute("UPDATE assets SET notes=? WHERE id='asset-000003'",('x'*32001,))
        stamp=self.page()['catalogue']
        page=self.page(details=True)
        self.assertEqual(len(page['assets']),6)
        self.assertEqual([e['id'] for e in page['unavailable_assets']],['asset-000003'])
        self.assertEqual(page['unavailable_assets'][0]['code'],'asset_read_unavailable')
        self.assertNotIn('asset-000003',[a['id'] for a in page['assets']])
        self.expect_error('asset_read_unavailable',self.selection,['asset-000003'],details=True)
        self.assertEqual(self.page()['catalogue'],stamp)
        with self.store.connection() as db:self.assertEqual(db.execute("SELECT notes FROM assets WHERE id='asset-000003'").fetchone()[0],'x'*32001)

    def test_all_unavailable_page_still_has_truthful_continuation(self):
        with self.store.connection() as db:db.execute('UPDATE assets SET source=?',('x'*65537,))
        cursor=None;seen=[]
        for _ in range(4):
            page=self.page(limit=2,cursor=cursor,details=True)
            self.assertEqual(page['assets'],[])
            seen.extend(e['id'] for e in page['unavailable_assets'])
            cursor=page['next_cursor']
            if cursor is None:break
        self.assertEqual(seen,[f'asset-{i:06}' for i in reversed(range(7))])

    def test_response_budget_shortens_details_page_without_losing_ids(self):
        self.seed(50,7)
        notes='🌙'*8000
        with self.store.connection() as db:db.execute('UPDATE assets SET notes=?',(notes,))
        cursor=None;seen=[];sizes=[]
        for _ in range(10):
            page=self.page(limit=100,cursor=cursor,details=True,include_collections=True)
            sizes.append(len(page['assets']))
            self.assertLessEqual(len(json.dumps(page,allow_nan=False).encode()),asset_reads.MAX_RESPONSE_BYTES)
            self.assertTrue(page['assets'])
            self.assertTrue(all(a['notes']==notes for a in page['assets']))
            seen.extend(a['id'] for a in page['assets'])
            cursor=page['next_cursor']
            if cursor is None:break
        else:self.fail('Bounded details walk did not finish')
        self.assertLess(sizes[0],57)
        self.assertEqual(seen,[f'asset-{i:06}' for i in reversed(range(57))])


if __name__=='__main__':unittest.main()
