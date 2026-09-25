"""Run labels and prompt excerpts are additive asset columns (#939): old Workspaces open unchanged and read as unlabelled."""
import importlib.util
import sqlite3
import tempfile
import unittest
import uuid
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


class RunLabelEditCommandTests(unittest.TestCase):
    """The revisioned bulk edit marks assets as agent runs or as the operator's own (#939)."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        source = self.root/'render.png'; source.write_bytes(b'rendered bytes')
        self.store = workspace.AssetWorkspace(self.root)
        self.ids = [self.store.register({'id':f'job-{i}', 'preset_name':'Study', 'outputs':[{'filename':'render.png','media_type':'image'}]}, 0, source) for i in range(3)]
        self.scope = self.store.snapshot()['workspace_id']

    def command(self, ids=None, **fields):
        ids = ids or self.ids
        return dict({'ids':ids, 'action':'edit', 'workspace_id':self.scope, 'request_id':uuid.uuid4().hex,
                     'expected_revisions':{i:self.store.get(i)['metadata_revision'] for i in ids}}, **fields)

    def labels(self):
        return [self.store.get(i)['run_label'] for i in self.ids]

    def test_mark_as_agent_run_then_as_mine_round_trips_with_receipts(self):
        marked = self.store.update(self.command(run_label='  Agent lab  '))
        self.assertEqual(marked['applied'], {'run_label':'Agent lab'})
        self.assertEqual(marked['revisions'], {i:1 for i in self.ids})
        self.assertEqual(self.labels(), ['Agent lab']*3)
        # The editor-conflict envelope stays exactly METADATA_FIELDS; full asset reads carry the label.
        self.assertEqual([set(m) for m in marked['current']], [set(workspace.METADATA_FIELDS) | {'workspace_id'}]*3)
        self.assertNotIn('run_label', self.store.metadata(self.ids[0], self.scope))
        self.assertEqual({a['run_label'] for a in self.store.snapshot()['assets']}, {'Agent lab'})
        cleared = self.store.update(self.command(run_label=None))
        self.assertEqual(cleared['applied'], {'run_label':None}); self.assertEqual(self.labels(), [None]*3)
        self.assertEqual(cleared['revisions'], {i:2 for i in self.ids})
        # Other metadata is untouched by a source change.
        self.assertEqual({(a['title'], a['review'], a['favorite']) for a in map(self.store.get, self.ids)}, {('Study · 1', 'unreviewed', False)})

    def test_invalid_labels_are_refused_and_change_nothing(self):
        for label in ('', '   ', 'x'*81, 'tab\there', 'line\nbreak', 7, True, ['Agent lab'], {'label':'x'}):
            with self.subTest(label=label):
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Run label must be null or printable text'):
                    self.store.update(self.command(run_label=label))
                self.assertEqual(self.labels(), [None]*3)
                self.assertEqual({self.store.get(i)['metadata_revision'] for i in self.ids}, {0})
        self.assertEqual(self.store.update(self.command(run_label='x'*80))['applied'], {'run_label':'x'*80})

    def test_replayed_request_returns_its_receipt_and_a_reused_id_is_refused(self):
        payload = self.command(run_label='Agent lab')
        first = self.store.update(payload)
        self.assertEqual(self.store.update(dict(payload)), first)
        self.assertEqual({self.store.get(i)['metadata_revision'] for i in self.ids}, {1})
        self.assertEqual(self.store.command_status(payload['request_id'], self.scope)['applied'], {'run_label':'Agent lab'})
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.update(dict(payload, run_label=None))
        self.assertEqual(caught.exception.code, 'asset_request_reused'); self.assertEqual(self.labels(), ['Agent lab']*3)

    def test_a_stale_revision_refuses_the_whole_batch(self):
        stale = self.command(run_label='Agent lab')
        self.store.update(self.command(ids=[self.ids[1]], title='Renamed elsewhere'))
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.update(stale)
        error = caught.exception
        self.assertEqual((error.status, error.code, error.details['conflict_ids']), (409, 'asset_revision_conflict', [self.ids[1]]))
        self.assertEqual(error.details['current'][0]['title'], 'Renamed elsewhere')
        self.assertEqual(self.labels(), [None]*3)

    def test_the_command_limit_still_applies(self):
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Select between 1 and 200 assets'):
            self.store.update(dict(self.command(run_label='Agent lab'), ids=[f'x{i}' for i in range(201)]))

    def test_job_submission_and_the_edit_command_share_one_rule(self):
        self.assertEqual(workspace.clean_run_label('  lab p71  '), 'lab p71'); self.assertIsNone(workspace.clean_run_label(None))
        for label in ('', 'x'*81, 'a\u2028b', 3):
            with self.subTest(label=label), self.assertRaises(ValueError): workspace.clean_run_label(label)


if __name__ == '__main__':
    unittest.main()
