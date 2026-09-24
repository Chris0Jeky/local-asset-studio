import importlib.util
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root/'render.png'; self.source.write_bytes(b'original rendered bytes')
        self.job = {'id':'job-1', 'preset_name':'Study', 'outputs':[{'filename':'render.png','media_type':'image'}]}
        self.asset = self.store.register(self.job, 0, self.source)

    @staticmethod
    def write(store, payload):
        return store.update(dict(payload, request_id=uuid.uuid4().hex,
                                 expected_revisions={i: store.get(i)["metadata_revision"] for i in payload['ids'] if i != 'missing'}))

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_survives_original_change_and_is_idempotent(self):
        self.source.write_bytes(b'changed original')
        self.assertEqual(self.store.file(self.asset).read_bytes(), b'original rendered bytes')
        self.assertEqual(self.store.register(self.job, 0, self.source), self.asset)
        self.assertEqual(len(self.store.snapshot()['assets']), 1)

    def test_collections_many_to_many_and_deletion_preserves_assets(self):
        a=self.store.collection({'name':'Character'}); b=self.store.collection({'name':'Chapter one'})
        for col in (a,b): self.write(self.store, {'ids':[self.asset],'action':'add_collection','collection_id':col['id']})
        self.assertEqual(set(self.store.snapshot()['assets'][0]['collections']), {a['id'],b['id']})
        self.store.collection({'id':a['id'],'action':'delete'})
        self.assertEqual(self.store.snapshot()['assets'][0]['collections'],[b['id']])
        self.assertTrue(self.source.exists()); self.assertTrue(self.store.file(self.asset).exists())

    def test_edit_trash_restore_and_restart_preserve_metadata(self):
        self.write(self.store, {'ids':[self.asset],'action':'edit','title':'My ink study','tags':['ink','ink','pose'],'review':'needs_work','notes':'Fix the hand','favorite':True})
        self.write(self.store, {'ids':[self.asset],'action':'trash'})
        recovered=workspace.AssetWorkspace(self.root)
        self.assertIsNotNone(recovered.get(self.asset)['trashed_at'])
        self.write(recovered, {'ids':[self.asset],'action':'restore'})
        result=recovered.get(self.asset)
        self.assertEqual(result['tags'],['ink','pose']); self.assertEqual(result['notes'],'Fix the hand')
        self.assertEqual(result['review'],'needs_work'); self.assertTrue(result['favorite']); self.assertIsNone(result['trashed_at'])

    def test_bulk_edit_rejects_missing_asset_atomically(self):
        with self.assertRaises(workspace.WorkspaceError):
            self.write(self.store, {'ids':[self.asset,'missing'],'action':'trash'})
        self.assertIsNone(self.store.get(self.asset)['trashed_at'])
        with self.assertRaises(workspace.WorkspaceError):
            self.write(self.store, {'ids':[self.asset],'action':'edit','review':'commercially_approved'})

    def test_saved_setups_roundtrip_and_delete(self):
        # The recipe is stored verbatim, not whitelisted: the browser's per-input lineage attribution
        # (parent_by_input, issue #108) survives a save/reload without a server-side schema change.
        recipe={'preset':'test','controls':{'seed':'9223372036854775806'},
                'parent_assets':[self.asset],'parent_by_input':{'reference':self.asset}}
        saved=self.store.save_setup({'name':'My setup','recipe':recipe})
        self.assertEqual(workspace.AssetWorkspace(self.root).setups()[0]['recipe'],recipe)
        self.store.save_setup({'id':saved['id'],'action':'delete'})
        self.assertEqual(self.store.setups(),[])

    def test_save_setup_validation_rejects_invalid_without_storing(self):
        self.assertEqual(self.store.setups(),[])
        with self.assertRaisesRegex(workspace.WorkspaceError,'Name and recipe are required'): self.store.save_setup({'name':'','recipe':{'preset':'test'}})
        with self.assertRaisesRegex(workspace.WorkspaceError,'Setup name must be text up to 120 characters'): self.store.save_setup({'name':'x'*121,'recipe':{'preset':'test'}})
        with self.assertRaisesRegex(workspace.WorkspaceError,'Name and recipe are required'): self.store.save_setup({'name':'OK','recipe':'not-a-dict'})
        overhead=len(json.dumps({'preset':'test','pad':''})); limit=128*1024
        over={'preset':'test','pad':'x'*(limit-overhead+1)}; self.assertEqual(len(json.dumps(over)),limit+1)
        with self.assertRaisesRegex(workspace.WorkspaceError,'Saved setup is too large'): self.store.save_setup({'name':'Big','recipe':over})
        self.assertEqual(self.store.setups(),[])
        recipe={'preset':'test','pad':'x'*(limit-overhead)}; self.assertEqual(len(json.dumps(recipe)),limit)   # exactly 128 KiB is accepted
        saved=self.store.save_setup({'name':'Boundary','recipe':recipe}); self.assertEqual(saved['name'],'Boundary')
        self.assertEqual(self.store.setups()[0]['recipe'],recipe)

    def test_file_rejects_escaped_absolute_and_missing_snapshots(self):
        outside=self.store.root.parent/'outside.png'; outside.write_bytes(b'outside bytes')
        elsewhere=self.store.root.parent/'elsewhere.png'; elsewhere.write_bytes(b'elsewhere bytes')
        for path in ('../outside.png', str(elsewhere.resolve())):
            with self.subTest(path=path):
                with self.store.connection() as db: db.execute('UPDATE assets SET path=? WHERE id=?', (path, self.asset))
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset snapshot is unavailable'): self.store.file(self.asset)
        with self.store.connection() as db: db.execute('UPDATE assets SET path=? WHERE id=?', ('media/missing.png', self.asset))
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset snapshot is unavailable'): self.store.file(self.asset)

    def test_snapshot_file_rejects_empty_source_without_leaving_files(self):
        empty=self.root/'empty.png'; empty.write_bytes(b'')
        before=set(p.name for p in self.store.media.iterdir())
        with self.assertRaisesRegex(workspace.WorkspaceError, 'The output file is empty'): self.store.snapshot_file(empty)
        self.assertEqual(set(p.name for p in self.store.media.iterdir()), before)

    def test_repeated_migration_is_idempotent_but_never_replaces_another_setup(self):
        recipe={'preset':'test','parent_assets':[self.asset]}
        payload={'id':'legacy-0','name':'Browser A','recipe':recipe}
        self.store.save_setup(payload); self.store.save_setup(payload)
        with self.assertRaisesRegex(workspace.WorkspaceError,'original was preserved'):
            self.store.save_setup({'id':'legacy-0','name':'Browser B','recipe':{'preset':'another'}})
        self.assertEqual(len(self.store.setups()),1)
        self.assertEqual(self.store.setups()[0]['name'],'Browser A')
        self.assertEqual(self.store.setups()[0]['recipe']['parent_assets'],[self.asset])

    def test_concurrent_setup_save_preserves_original_without_integrity_error(self):
        # A lost race hides the winner's row from the existence check; the INSERT OR IGNORE
        # path must then keep the original: identical payload returns normally, anything else
        # raises WorkspaceError, never sqlite3.IntegrityError.
        recipe={'preset':'test'}; identifier='race-0'
        with self.store.connection() as db: db.execute("INSERT INTO setups VALUES (?,?,?,?)", (identifier,'Original',json.dumps(recipe),time.time()))
        with self.assertRaisesRegex(workspace.WorkspaceError,'original was preserved'):
            self.store.save_setup({'id':identifier,'name':'Late','recipe':{'preset':'other'}})
        state={'hide':True}
        class _Missing:
            def fetchone(self): return None
        class _RacedDb:
            def __init__(self,inner): self._inner=inner
            def execute(self,sql,*args,**kwargs):
                if state['hide'] and isinstance(sql,str) and sql.startswith('SELECT name,recipe'): state['hide']=False; return _Missing()
                return self._inner.execute(sql,*args,**kwargs)
            def __getattr__(self,name): return getattr(self._inner,name)
        class _RacedConnection:
            def __init__(self,inner): self._inner=inner
            def __enter__(self): return _RacedDb(self._inner.__enter__())
            def __exit__(self,*exc): return self._inner.__exit__(*exc)
        real_connection=workspace.AssetWorkspace.connection
        def raced_connection(store_self): return _RacedConnection(real_connection(store_self))
        with patch.object(workspace.AssetWorkspace,'connection',raced_connection):
            self.assertEqual(self.store.save_setup({'id':identifier,'name':'Original','recipe':recipe}),{'id':identifier,'name':'Original'})
        self.assertEqual(self.store.setups()[0]['name'],'Original')
        state['hide']=True
        with patch.object(workspace.AssetWorkspace,'connection',raced_connection):
            with self.assertRaisesRegex(workspace.WorkspaceError,'original was preserved'):
                self.store.save_setup({'id':identifier,'name':'Late','recipe':{'preset':'other'}})
        self.assertEqual(self.store.setups()[0]['recipe'],recipe)
