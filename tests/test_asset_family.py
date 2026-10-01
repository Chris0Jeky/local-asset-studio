"""Family observations and split recall use retained Workspace/job evidence only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test_server import server


class FamilyFixture:
    def __init__(self, root):
        self.assets = server.AssetWorkspace(root)
        self.root = Path(root)
        self.jobs = {}
        self.ids = []
        source = self.root / 'synthetic.png'
        source.write_bytes(b'synthetic immutable image fixture')
        for index in range(4):
            job = {'id': 'family-job-'+str(index), 'status': 'completed', 'created_at': index+1,
                   'preset_id': 'anima-portrait', 'preset_name': ('Draft', 'Refine', 'Repair', 'Upscale')[index],
                   'controls': {'positive': '__place__', 'negative': 'blur', 'seed': 10, 'denoise': .3},
                   'batch_count': 3, 'parent_assets': self.ids[-1:], 'references': [],
                   'graph': {'1': {'class_type': 'Text', 'inputs': {'text': '__place__'}},
                             '2': {'class_type': 'Text', 'inputs': {'text': 'blur'}}},
                   'prompt_bindings': {'positive': [['1', 'text']], 'negative': [['2', 'text']]},
                   'outputs': [{'filename': 'synthetic.png', 'media_type': 'image', 'seed': 12,
                                'prompt_id': 'prompt-'+str(index)}]}
            graph = copy.deepcopy(job['graph']); graph['1']['inputs']['text'] = 'A forest at dusk'
            job['submissions'] = [{'prompt_id': 'prompt-'+str(index), 'graph': graph, 'seed': 12, 'status': 'completed'}]
            self.jobs[job['id']] = job
            self.ids.append(self.assets.register(job, 0, source))
        self.scope = self.assets.snapshot()['workspace_id']
        self.export_recipe = lambda job: server.Studio.export_recipe(self, job)
        self.create_job = Mock(side_effect=AssertionError('read submitted generation'))
        self.upload = Mock(side_effect=AssertionError('read staged an input'))


class AssetFamilyTests(unittest.TestCase):
    def setUp(self):
        from studio_workflow import asset_family
        self.family = asset_family
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.studio = FamilyFixture(temp.name)
        self.store = self.studio.assets
        self.ids, self.scope = self.studio.ids, self.studio.scope

    def read(self, asset_id=None, **query):
        return self.family.observe(self.studio, asset_id or self.ids[-1], workspace_id=self.scope, **query)

    def test_four_steps_are_oldest_first_and_reads_never_change_workspace(self):
        before = self.store.snapshot()
        report = self.read()
        self.assertEqual([n['id'] for n in report['nodes']], self.ids)
        self.assertEqual([n['operation'] for n in report['nodes']], ['Draft', 'Refine', 'Repair', 'Upscale'])
        self.assertEqual(report['nodes'][-1]['seed'], '12')
        self.assertEqual(report['nodes'][-1]['strength'], '0.3')
        self.assertFalse(report['generation_submitted']); self.assertTrue(report['observation_only'])
        self.assertEqual(before, self.store.snapshot())
        self.studio.create_job.assert_not_called(); self.studio.upload.assert_not_called()

    def test_missing_and_trashed_ancestors_are_named_gaps(self):
        with self.store.connection() as db:
            db.execute('DELETE FROM assets WHERE id=?', (self.ids[0],))
            db.execute('UPDATE assets SET trashed_at=0 WHERE id=?', (self.ids[1],))
        nodes = self.read()['nodes']
        self.assertEqual([n['id'] for n in nodes], self.ids)
        self.assertEqual([n['state'] for n in nodes], ['missing', 'trashed', 'active', 'active'])
        self.assertIn(self.ids[0], nodes[0]['title']); self.assertIn('Refine', nodes[1]['title'])

    def test_cycle_does_not_repeat_or_recurse_forever(self):
        with self.store.connection() as db:
            db.execute('UPDATE assets SET lineage=? WHERE id=?', (json.dumps([self.ids[-1]]), self.ids[0]))
        report = self.read()
        self.assertEqual(len(report['nodes']), 4)
        self.assertTrue(any(x['reason'] == 'cycle' for x in report['gaps']))

    def test_multiple_parents_remain_edges_not_an_invented_single_chain(self):
        with self.store.connection() as db:
            db.execute('UPDATE assets SET lineage=? WHERE id=?', (json.dumps(self.ids[:2]), self.ids[-1]))
        report = self.read()
        self.assertEqual({e['parent'] for e in report['edges'] if e['child'] == self.ids[-1]}, set(self.ids[:2]))
        self.assertEqual(len({n['id'] for n in report['nodes']}), len(report['nodes']))

    def test_children_are_only_read_on_request_and_bounded(self):
        report = self.read(self.ids[0]); self.assertIsNone(report['children'])
        report = self.read(self.ids[0], children=True)
        self.assertEqual([n['id'] for n in report['children']], [self.ids[1]])
        self.assertFalse(report['children_truncated'])

    def test_depth_limit_folds_without_silently_claiming_complete_history(self):
        with self.store.connection() as db:
            original = dict(db.execute('SELECT * FROM assets WHERE id=?', (self.ids[0],)).fetchone())
            columns = list(original)
            for index in range(20):
                row = dict(original, id='deep-'+str(index), job_id='deep-job-'+str(index),
                           lineage=json.dumps(['deep-'+str(index+1)]) if index < 19 else '[]')
                db.execute('INSERT INTO assets ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')', [row[k] for k in columns])
        report = self.read('deep-0')
        self.assertEqual(len(report['nodes']), self.family.MAX_DEPTH)
        self.assertTrue(report['truncated'])
        self.assertEqual(report['gaps'][0]['reason'], 'depth')

    def test_malformed_oversized_or_non_list_lineage_is_a_visible_gap(self):
        for raw in ('{', '{}', '[true]', '["'+('a'*129)+'"]', ' '*20000):
            with self.subTest(raw=raw[:40]):
                with self.store.connection() as db: db.execute('UPDATE assets SET lineage=? WHERE id=?', (raw, self.ids[-1]))
                report = self.read()
                self.assertEqual(report['nodes'][-1]['id'], self.ids[-1])
                self.assertTrue(any(g['reason'] == 'invalid-lineage' for g in report['gaps']))

    def test_extreme_or_nonfinite_operation_numbers_are_not_rendered(self):
        job = self.studio.jobs['family-job-3']
        for value in (10**1000, float('inf'), float('nan'), True, [], {}):
            with self.subTest(value_type=type(value).__name__):
                job['controls']['denoise'] = value
                self.assertIsNone(self.read()['nodes'][-1]['strength'])

    def test_children_disclose_result_and_scan_truncation(self):
        from unittest.mock import patch
        with self.store.connection() as db:
            original = dict(db.execute('SELECT * FROM assets WHERE id=?', (self.ids[-1],)).fetchone())
            columns = list(original)
            for index in range(25):
                row = dict(original, id='child-'+str(index), job_id='child-job-'+str(index),
                           created_at=100+index, lineage=json.dumps([self.ids[0]]))
                db.execute('INSERT INTO assets ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')', [row[k] for k in columns])
        report = self.read(self.ids[0], children=True)
        self.assertEqual(len(report['children']), self.family.MAX_CHILDREN)
        self.assertTrue(report['children_truncated'])
        with patch.object(self.family, 'MAX_CHILD_SCAN', 3):
            report = self.read(self.ids[0], children=True)
        self.assertEqual(report['children_scanned'], 3)
        self.assertEqual(len(report['children']), 3)
        self.assertTrue(report['children_truncated'])

    def test_wrong_workspace_refuses_before_returning_any_asset(self):
        with self.assertRaises(ValueError) as caught:
            self.family.observe(self.studio, self.ids[0], workspace_id='b'*32)
        self.assertEqual(caught.exception.code, 'asset_workspace_conflict')

    def test_bad_ids_scopes_and_boolean_flags_are_refused(self):
        for asset_id in ('../x', '', 'x'*129, None, []):
            with self.subTest(id=asset_id), self.assertRaises(ValueError):
                self.family.observe(self.studio, asset_id, workspace_id=self.scope)
        for scope in (None, '', 'X'*32):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.family.observe(self.studio, self.ids[0], workspace_id=scope)
        with self.assertRaises(ValueError): self.read(children='true')

    def test_recall_keeps_output_seed_resolved_words_and_original_recipe_separate(self):
        before = copy.deepcopy(self.studio.jobs)
        result = self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
        self.assertEqual(result['controls']['positive'], 'A forest at dusk')
        self.assertEqual(result['controls']['seed'], '12')
        self.assertEqual(result['recipe']['controls']['positive'], '__place__')
        self.assertEqual(result['recipe']['batch_count'], 3)
        self.assertEqual(result['parent_assets'], [self.ids[2]])
        self.assertEqual(before, self.studio.jobs)
        self.assertFalse(result['generation_submitted'])
        self.assertEqual(result['workspace_id'], self.scope)

    def test_recall_retains_large_seed_as_decimal_text(self):
        with self.store.connection() as db:
            source = {'seed': '18446744073709551615', 'prompt_id': 'prompt-3'}
            db.execute('UPDATE assets SET source=? WHERE id=?', (json.dumps(source), self.ids[-1]))
        result = self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
        self.assertEqual(result['controls']['seed'], '18446744073709551615')

    def test_recall_refuses_trashed_missing_uncertain_or_specialized_jobs(self):
        job = self.studio.jobs['family-job-3']
        for changes in ({'status': 'uncertain'}, {'operation': 'native.av-preview.v1'}, {'tile': {'source': 'x'}}, {'parallax': {}}):
            with self.subTest(changes=changes):
                original = copy.deepcopy(job); job.update(changes)
                with self.assertRaises(ValueError): self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
                job.clear(); job.update(original)
        with self.store.connection() as db: db.execute('UPDATE assets SET trashed_at=0 WHERE id=?', (self.ids[-1],))
        with self.assertRaises(ValueError): self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
        with self.assertRaises(ValueError): self.family.recall(self.studio, 'missing', workspace_id=self.scope)

    def test_recall_refuses_ambiguous_submitted_wording_instead_of_using_template(self):
        job = self.studio.jobs['family-job-3']
        for submissions in ([], job['submissions']*2):
            with self.subTest(count=len(submissions)):
                original = job['submissions']; job['submissions'] = submissions
                with self.assertRaises(ValueError): self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
                job['submissions'] = original

    def test_recall_refuses_malformed_retained_submissions_and_missing_job_fields(self):
        job = self.studio.jobs['family-job-3']
        for value in (1, True, 'invalid', {'prompt_id': 'prompt-3'}):
            with self.subTest(submissions=value):
                original = job['submissions']; job['submissions'] = value
                with self.assertRaises(ValueError): self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
                job['submissions'] = original
        original = job.pop('batch_count')
        try:
            with self.assertRaises(ValueError): self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)
        finally: job['batch_count'] = original

    def test_recall_refuses_divergent_companion_prompt_bindings(self):
        job = self.studio.jobs['family-job-3']
        job['prompt_bindings']['positive'].append(['2', 'text'])
        with self.assertRaisesRegex(ValueError, 'wording'):
            self.family.recall(self.studio, self.ids[-1], workspace_id=self.scope)


if __name__ == '__main__': unittest.main()
