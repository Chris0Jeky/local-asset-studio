"""Run labels and prompt excerpts are additive asset columns (#939): old Workspaces open unchanged and read as unlabelled."""
import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace_labels', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class RunLabelWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.source = self.root/'render.png'; self.source.write_bytes(b'rendered bytes')

    def job(self, identifier, **extra):
        return dict({'id':identifier, 'preset_name':'Study', 'outputs':[{'filename':'render.png','media_type':'image'}]}, **extra)

    def test_register_copies_the_job_label_and_a_bounded_prompt_excerpt(self):
        store = workspace.AssetWorkspace(self.root)
        prompt = '  a knight\n\tin  silver armour, ' + 'standing in the rain ' * 10
        asset = store.get(store.register(self.job('labelled', label='nsfw-lab p71 · G16 ports', controls={'positive':prompt}), 0, self.source))
        self.assertEqual(asset['run_label'], 'nsfw-lab p71 · G16 ports')
        self.assertEqual(len(asset['prompt_excerpt']), workspace.PROMPT_EXCERPT_CHARS)
        self.assertTrue(asset['prompt_excerpt'].startswith('a knight in silver armour, standing'))
        self.assertTrue(asset['prompt_excerpt'].endswith('…'))
        self.assertEqual(asset['title'], 'Study · 1')
        mine = store.get(store.register(self.job('mine', controls={'positive':'short'}), 0, self.source))
        self.assertIsNone(mine['run_label']); self.assertEqual(mine['prompt_excerpt'], 'short')
        self.assertEqual({a['id']:a['run_label'] for a in store.snapshot()['assets']}, {asset['id']:'nsfw-lab p71 · G16 ports', mine['id']:None})

    def test_excerpt_reads_the_bound_graph_prompt_and_never_raises(self):
        graph = {'job':{'graph':{'6':{'inputs':{'text':'authored  wording'}}}, 'prompt_bindings':{'positive':[['6','text']]}}}
        self.assertEqual(workspace.prompt_excerpt(graph['job']), 'authored wording')
        for job in ({}, {'controls':None}, {'controls':{'positive':7}}, {'prompt_bindings':{'positive':[]}, 'graph':{}},
                    {'prompt_bindings':{'positive':[['6','text']]}, 'graph':{'6':{'inputs':{'text':['4', 0]}}}}, {'controls':{'positive':'   '}}):
            self.assertIsNone(workspace.prompt_excerpt(job), job)

    def test_a_workspace_created_before_the_columns_opens_with_its_assets_unlabelled(self):
        store = workspace.AssetWorkspace(self.root)
        asset = store.register(self.job('old', label='should vanish', controls={'positive':'old prompt'}), 0, self.source)
        before = store.get(asset)
        with closing(sqlite3.connect(store.database)) as db:
            db.execute('ALTER TABLE assets DROP COLUMN run_label'); db.execute('ALTER TABLE assets DROP COLUMN prompt_excerpt'); db.commit()
        for _ in range(2): reopened = workspace.AssetWorkspace(self.root)
        after = reopened.get(asset)
        self.assertIsNone(after['run_label']); self.assertIsNone(after['prompt_excerpt'])
        self.assertEqual({k:v for k,v in after.items() if k not in workspace.ADDITIVE_COLUMNS}, {k:v for k,v in before.items() if k not in workspace.ADDITIVE_COLUMNS})
        with closing(sqlite3.connect(store.database)) as db:
            names = [r[1] for r in db.execute('PRAGMA table_info(assets)')]
        self.assertEqual([names.count(c) for c in workspace.ADDITIVE_COLUMNS], [1, 1])
        # Re-registering an existing output never rewrites it; only new outputs carry the new fields.
        self.assertEqual(reopened.register(self.job('old', label='later', controls={'positive':'x'}), 0, self.source), asset)
        self.assertIsNone(reopened.get(asset)['run_label'])


if __name__ == '__main__':
    unittest.main()
