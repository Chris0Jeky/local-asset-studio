"""Prepared operation factory uses actual Production rows and read-only checks."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if not (HERE / 'pipeline.py').exists():
    sys.path.insert(0, str(HERE.parent / 'studio/prototypes/pro/P36/P36-B-20261126-2'))
import pipeline as p
import production_intent as subject
from production_intent_fixtures import make_production_case


class ProductionIntentTests(unittest.TestCase):
    def setUp(self):
        base = p.REPO_ROOT / '.runtime/pro/P36-B-20261126-2/production-intent-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base); self.addCleanup(self.temp.cleanup)
        self.case = make_production_case(Path(self.temp.name) / 'studio')
        self.intent = self.case['intent']

    def capture(self, **changes):
        args = {k: self.case[k] for k in ('experiments', 'project_id', 'stage_index', 'family_id', 'stage', 'studio_root')}
        args.update(changes)
        return subject.capture_production_intent(**args)

    def mutate_plan(self, action, *, rewrite=True):
        studio = self.case['studio']; project = studio.production._get(self.case['project_id'])
        action(project['plan'])
        project['plan']['sha256'] = subject.production_fingerprint({k: v for k, v in project['plan'].items() if k != 'sha256'})
        with studio.production.connect() as db:
            db.execute('UPDATE projects SET plan=? WHERE id=?', (json.dumps(project['plan']), project['id']))
        if rewrite:
            (studio.production.root / project['id'] / 'plan.json').write_text(json.dumps(project['plan']), encoding='utf-8')

    def test_actual_production_api_valid_capture_is_preparation_only_and_read_only(self):
        root = self.case['studio_root']
        before = {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob('*') if x.is_file()}
        result = self.capture()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['intent'], self.intent)
        self.assertTrue(result['preparation_only'])
        for flag in ('generation_submitted', 'submission_authority', 'budget_authority', 'runtime_ready'):
            self.assertFalse(result[flag])
        self.assertEqual(self.case['studio'].requests, [])
        self.assertTrue(self.case['studio'].queue.empty())
        after = {str(x): hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob('*') if x.is_file()}
        self.assertEqual(before, after)

    def test_validate_strict_top_level_and_identity(self):
        self.assertIsInstance(subject.validate_intent(self.intent), str)
        for key, value in [('batch_count', True), ('batch_count', 2), ('seed', True), ('operation', 'native.fake'),
                           ('stage_index', -1), ('job_id', 'other'), ('stage', 'bad-stage')]:
            bad = copy.deepcopy(self.intent); bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): subject.validate_intent(bad)
        bad = copy.deepcopy(self.intent); bad['submission_authority'] = True
        with self.assertRaises(ValueError): subject.validate_intent(bad)

    def test_wrong_trusted_root_and_experiments_cannot_revalidate(self):
        self.assertFalse(subject.revalidate_intent(self.case['experiments'], self.intent, studio_root=p.REPO_ROOT)['passed'])
        self.assertFalse(subject.revalidate_intent(self.case['experiments'].parent / 'other', self.intent,
                                                  studio_root=self.case['studio_root'])['passed'])

    def test_source_project_state_or_budget_change_invalidates_intent(self):
        for target in ('state', 'budget'):
            with self.subTest(target=target):
                studio = self.case['studio']; project = studio.production._get(self.case['project_id'])
                with studio.production.connect() as db:
                    if target == 'state':
                        changed = dict(project['state'], stop_requested=True)
                        db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps(changed), project['id']))
                    else: db.execute('UPDATE budgets SET reserved=1 WHERE id=?', (project['root_id'],))
                self.assertFalse(subject.revalidate_intent(self.case['experiments'], self.intent,
                                                         studio_root=self.case['studio_root'])['passed'])

    def test_db_and_materialized_plan_must_match(self):
        self.mutate_plan(lambda plan: plan.update(name='changed only in DB'), rewrite=False)
        self.assertFalse(self.capture()['passed'])

    def test_corrupted_plan_hash_refuses(self):
        path = self.case['studio'].production.root / self.case['project_id'] / 'plan.json'
        data = json.loads(path.read_text()); data['sha256'] = 'f' * 64; path.write_text(json.dumps(data))
        self.assertFalse(self.capture()['passed'])

    def test_incomplete_project_and_existing_future_job_refuse(self):
        directory = self.case['studio'].production.root / self.case['project_id']
        marker = directory / '.incomplete-create'; marker.write_text('{}')
        self.assertFalse(self.capture()['passed']); marker.unlink()
        (self.case['experiments'] / 'runs' / self.intent['job_id']).mkdir(parents=True)
        self.assertFalse(self.capture()['passed'])

    def test_native_batch_private_and_wildcards_refuse(self):
        changes = [lambda plan: plan.update(kind='native'),
                   lambda plan: plan['stages'][0]['request'].update(batch_count=2),
                   lambda plan: plan['stages'][0]['request'].update(privacy='private'),
                   lambda plan: plan['stages'][0].update(operation='native.fake'),
                   lambda plan: plan['stages'][0]['graph']['2']['inputs'].update(text='__fixture__')]
        original = copy.deepcopy(self.case['studio'].production._get(self.case['project_id'])['plan'])
        for change in changes:
            with self.subTest(change=change):
                self.mutate_plan(lambda plan: (plan.clear(), plan.update(copy.deepcopy(original)), change(plan)))
                self.assertFalse(self.capture()['passed'])

    def test_stage_index_and_unknown_project_refuse_without_database_creation(self):
        for value in (-1, True, 1, '0'):
            with self.subTest(value=value): self.assertFalse(self.capture(stage_index=value)['passed'])
        self.assertFalse(self.capture(project_id='b' * 32)['passed'])
        missing = Path(self.temp.name) / 'missing'
        self.assertFalse(self.capture(experiments=missing)['passed']); self.assertFalse(missing.exists())

    def test_changed_graph_and_template_are_refused(self):
        self.mutate_plan(lambda plan: plan['stages'][0]['graph']['2']['inputs'].update(seed=8))
        self.assertFalse(self.capture()['passed'])
        path = self.case['studio_root'] / 'workflows/api/p36-fixture.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.assertFalse(self.capture()['passed'])

    def test_changed_model_same_size_and_mtime_is_refused(self):
        path = self.case['model_path']; stamp = path.stat()
        path.write_bytes(b'X' * stamp.st_size); os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertFalse(self.capture()['passed'])

    def test_missing_input_or_model_refuses(self):
        self.case['input_path'].unlink(); self.assertFalse(self.capture()['passed'])
        self.case['model_path'].unlink(); self.assertFalse(self.capture()['passed'])

    def test_changed_library_pin_and_missing_bundle_dependency_refuse(self):
        self.mutate_plan(lambda plan: plan['bundle'].update(models=[]))
        self.assertFalse(self.capture()['passed'])

    def test_changed_library_pin_refuses_even_when_preflight_bytes_still_match(self):
        path = self.case['studio_root'] / 'models/library.json'
        data = json.loads(path.read_text()); data['assets'][0]['sha256'] = 'f' * 64
        path.write_text(json.dumps(data))
        self.assertFalse(self.capture()['passed'])

    def test_semantically_identical_decimal_seed_spelling_is_valid(self):
        self.mutate_plan(lambda plan: plan['stages'][0]['request']['controls'].update(seed='7.0'))
        self.assertTrue(self.capture()['passed'])

    def test_changed_node_class_coverage_and_backend_refuse(self):
        self.mutate_plan(lambda plan: plan['bundle'].update(node_classes=[]))
        self.assertFalse(self.capture()['passed'])

    def test_unreadable_source_is_failed_report(self):
        with patch.object(subject, '_read_document', side_effect=PermissionError('fixture denied')):
            self.assertFalse(self.capture()['passed'])

    def test_malformed_retained_plan_shapes_return_failure(self):
        studio = self.case['studio']
        for value in ([], None, {'stages': [None]}):
            with self.subTest(value=value):
                with studio.production.connect() as db:
                    db.execute('UPDATE projects SET plan=? WHERE id=?', (json.dumps(value), self.case['project_id']))
                self.assertFalse(self.capture()['passed'])

    def test_malformed_nested_intent_is_value_error(self):
        for name, value in [('project_record', []), ('preset_record', []), ('budget_record', None), ('observed_files', [None])]:
            bad = copy.deepcopy(self.intent); bad['source_snapshot'][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError): subject.validate_intent(bad)

    def test_serialized_numeric_graph_alias_cannot_change_exact_intent(self):
        # JSON reload separates top-level graph from the source graph. Plain
        # Python dict equality would incorrectly treat 7.0 and integer 7 alike.
        bad = p.decode_json(p.canonical_bytes(self.intent))
        bad['graph']['2']['inputs']['seed'] = 7.0
        self.assertEqual(bad['graph'], bad['source_snapshot']['project_record']['plan']['stages'][0]['graph'])
        self.assertNotEqual(p.canonical_bytes(bad['graph']), p.canonical_bytes(self.intent['graph']))
        with self.assertRaises(ValueError): subject.validate_intent(bad)
        self.assertFalse(subject.revalidate_intent(self.case['experiments'], bad,
                                                 studio_root=self.case['studio_root'])['passed'])

    def test_source_change_during_final_recheck_refuses(self):
        original = subject._read_document; calls = 0
        def changing(path):
            nonlocal calls
            value = original(path); calls += 1
            if calls == 5:
                with self.case['studio'].production.connect() as db:
                    db.execute('UPDATE budgets SET reserved=1 WHERE id=?', (self.intent['source_snapshot']['budget_record']['id'],))
            return value
        with patch.object(subject, '_read_document', side_effect=changing):
            self.assertFalse(self.capture()['passed'])

    def test_model_path_link_is_refused(self):
        model = self.case['model_path']; target = model.with_suffix('.real'); model.rename(target)
        try: model.symlink_to(target)
        except OSError: self.skipTest('Symlink creation unavailable')
        self.assertFalse(self.capture()['passed'])

    def test_changed_workspace_identity_invalidates_intent(self):
        with self.case['studio'].assets.connection() as db:
            db.execute('UPDATE workspace_identity SET id=?', ('b' * 32,))
        self.assertFalse(subject.revalidate_intent(self.case['experiments'], self.intent,
                                                 studio_root=self.case['studio_root'])['passed'])

    def test_shared_existing_workspace_fixture_is_preserved(self):
        from authority_fixtures import make_workspace
        context = make_workspace(Path(self.temp.name) / 'shared', through='concept')
        original = context['binding']['stages']['concept']['jobs']
        case = make_production_case(Path(self.temp.name) / 'second-studio', experiments=context['experiments'])
        self.assertEqual(case['intent']['source_snapshot']['workspace_id'], 'a' * 32)
        for job_id, hashes in original.items():
            directory = context['experiments'] / 'runs' / job_id
            for name, key in [('state.json', 'state_sha256'), ('workflow.json', 'workflow_sha256')]:
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), hashes[key])


if __name__ == '__main__': unittest.main()
