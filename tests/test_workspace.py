import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root/'render.png'; self.source.write_bytes(b'original rendered bytes')
        self.job = {'id':'job-1', 'preset_name':'Study', 'outputs':[{'filename':'render.png','media_type':'image'}]}
        self.asset = self.store.register(self.job, 0, self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_survives_original_change_and_is_idempotent(self):
        self.source.write_bytes(b'changed original')
        self.assertEqual(self.store.file(self.asset).read_bytes(), b'original rendered bytes')
        self.assertEqual(self.store.register(self.job, 0, self.source), self.asset)
        self.assertEqual(len(self.store.snapshot()['assets']), 1)

    def test_collections_many_to_many_and_deletion_preserves_assets(self):
        a=self.store.collection({'name':'Character'}); b=self.store.collection({'name':'Chapter one'})
        for col in (a,b): self.store.update({'ids':[self.asset],'action':'add_collection','collection_id':col['id']})
        self.assertEqual(set(self.store.snapshot()['assets'][0]['collections']), {a['id'],b['id']})
        self.store.collection({'id':a['id'],'action':'delete'})
        self.assertEqual(self.store.snapshot()['assets'][0]['collections'],[b['id']])
        self.assertTrue(self.source.exists()); self.assertTrue(self.store.file(self.asset).exists())

    def test_edit_trash_restore_and_restart_preserve_metadata(self):
        self.store.update({'ids':[self.asset],'action':'edit','title':'My ink study','tags':['ink','ink','pose'],'review':'needs_work','notes':'Fix the hand','favorite':True})
        self.store.update({'ids':[self.asset],'action':'trash'})
        recovered=workspace.AssetWorkspace(self.root)
        self.assertIsNotNone(recovered.get(self.asset)['trashed_at'])
        recovered.update({'ids':[self.asset],'action':'restore'})
        result=recovered.get(self.asset)
        self.assertEqual(result['tags'],['ink','pose']); self.assertEqual(result['notes'],'Fix the hand')
        self.assertEqual(result['review'],'needs_work'); self.assertTrue(result['favorite']); self.assertIsNone(result['trashed_at'])

    def test_bulk_edit_rejects_missing_asset_atomically(self):
        with self.assertRaises(workspace.WorkspaceError):
            self.store.update({'ids':[self.asset,'missing'],'action':'trash'})
        self.assertIsNone(self.store.get(self.asset)['trashed_at'])
        with self.assertRaises(workspace.WorkspaceError):
            self.store.update({'ids':[self.asset],'action':'edit','review':'commercially_approved'})

    def test_saved_setups_roundtrip_and_delete(self):
        # The recipe is stored verbatim, not whitelisted: the browser's per-input lineage attribution
        # (parent_by_input, issue #108) survives a save/reload without a server-side schema change.
        recipe={'preset':'test','controls':{'seed':'9223372036854775806'},
                'parent_assets':[self.asset],'parent_by_input':{'reference':self.asset}}
        saved=self.store.save_setup({'name':'My setup','recipe':recipe})
        self.assertEqual(workspace.AssetWorkspace(self.root).setups()[0]['recipe'],recipe)
        self.store.save_setup({'id':saved['id'],'action':'delete'})
        self.assertEqual(self.store.setups(),[])

    def test_repeated_migration_is_idempotent_but_never_replaces_another_setup(self):
        recipe={'preset':'test','parent_assets':[self.asset]}
        payload={'id':'legacy-0','name':'Browser A','recipe':recipe}
        self.store.save_setup(payload); self.store.save_setup(payload)
        with self.assertRaisesRegex(workspace.WorkspaceError,'original was preserved'):
            self.store.save_setup({'id':'legacy-0','name':'Browser B','recipe':{'preset':'another'}})
        self.assertEqual(len(self.store.setups()),1)
        self.assertEqual(self.store.setups()[0]['name'],'Browser A')
        self.assertEqual(self.store.setups()[0]['recipe']['parent_assets'],[self.asset])
