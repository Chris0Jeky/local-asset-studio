"""Collect real saved Production/Workspace fixtures without a runtime or inference."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_character_handoff_import as fixtures
from scripts import character_study as study
from scripts import character_study_results as results


class CollectionTests(unittest.TestCase):
    character_preflight = fixtures.CharacterHandoffImportTests.character_preflight
    payload = fixtures.CharacterHandoffImportTests.payload

    def setUp(self):
        fixtures.CharacterHandoffImportTests.setUp(self)
        self.destination = self.workspace/'collected-v1'

    def project(self, index=0):
        payload = self.payload(self.plan['cases'][index]); payload['name'] = 'Étude 人物'
        return self.studio.production.create(payload)

    def execute(self, project, outcome='completed'):
        prompt = 'fixture-'+project['id']
        path = self.studio.comfy_root/'output'/'fixture.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(fixtures.PNG)
        history = {'status': {'status_str': 'success'}, 'outputs': {'1': {'images': [
            {'filename': path.name, 'subfolder': '', 'type': 'output'}]}}}
        replies = [{'queue_running': [], 'queue_pending': []}, {'prompt_id': prompt}, {prompt: history}]
        if outcome == 'uncertain': replies[1:] = [URLError('lost reply')]
        if outcome == 'failed': history.update(status={'status_str': 'error', 'messages': []}, outputs={})
        self.studio.replies = iter(replies)
        self.studio.production.start(project['id']); self.studio.production.run(project['id'])
        return next(j for j in self.studio.jobs.values() if j['project_id'] == project['id'])

    def collect(self):
        return results.collect(self.plan, self.workspace, self.studio.experiments, self.destination)

    def test_completed_and_planned_cases_feed_existing_summarizer_without_review_or_mutation(self):
        first = self.project(); second = self.project(1); job = self.execute(first)
        self.studio.production.review(first['id'], {'asset_id': job['outputs'][0]['asset_id'], 'notes': 'Generic selection only', 'reviewer': 'local-user'})
        before = (copy.deepcopy(self.studio.jobs), self.studio.production.list(), list(self.studio.requests), self.studio.queue.qsize())
        with patch.object(self.studio, '_request', side_effect=AssertionError('Collector contacted runtime')):
            report = self.collect()
        records = study.read_json(self.destination/'records.json')
        summary = study.read_json(self.destination/'summary.json')
        self.assertEqual(summary, study.summarize(self.plan, records, self.workspace))
        self.assertEqual((summary['attempts_used'], summary['completed_attempts'], summary['human_accepted_cases'], summary['selected_cases']), (1, 1, 0, 0))
        self.assertEqual(report['production_budget'], {'allowance': 2, 'reserved': 1})
        self.assertFalse(report['generation_submitted']); self.assertFalse(report['grants_generation_allowance'])
        self.assertEqual({item['disposition'] for item in report['cases']}, {'completed', 'planned'})
        self.assertEqual(records[0]['prompt_id'], job['prompt_ids'][0]); self.assertIsNone(records[0]['review'])
        self.assertIsNone(records[0]['cleanup_seconds'])
        evidence = study.read_json(study.verify_artifact(self.workspace, records[0]['execution_evidence']))
        self.assertEqual(evidence['job']['pending_submission'] if 'pending_submission' in evidence['job'] else None, None)
        self.assertEqual(evidence['project']['plan']['character_source']['study_plan'], self.plan)
        self.assertEqual(study.verify_artifact(self.workspace, records[0]['output']).read_bytes(), fixtures.PNG)
        self.assertEqual(before, (self.studio.jobs, self.studio.production.list(), self.studio.requests, self.studio.queue.qsize()))
        self.assertTrue((self.destination/'collection.json').is_file())
        self.assertFalse((self.destination/'.incomplete').exists())

    def test_uncertain_submission_keeps_pending_evidence_and_consumes_an_attempt(self):
        job = self.execute(self.project(), 'uncertain'); report = self.collect()
        record = study.read_json(self.destination/'records.json')[0]
        self.assertEqual(record['state'], 'submission_uncertain'); self.assertIsNone(record['prompt_id']); self.assertIsNone(record['output'])
        evidence = study.read_json(study.verify_artifact(self.workspace, record['execution_evidence']))
        self.assertEqual(evidence['job']['pending_submission'], job['pending_submission'])
        self.assertEqual(study.read_json(self.destination/'summary.json')['unresolved_submission_case_ids'], [record['case_id']])
        self.assertEqual(report['production_budget']['reserved'], 1)

    def test_failed_known_prompt_is_retained_with_null_output(self):
        job = self.execute(self.project(), 'failed'); self.collect()
        record = study.read_json(self.destination/'records.json')[0]
        self.assertEqual(record['state'], 'failed'); self.assertEqual(record['prompt_id'], job['prompt_ids'][0]); self.assertIsNone(record['output'])

    def test_never_submitted_reservation_is_not_returned_to_the_study(self):
        project = self.project(); self.studio.production.start(project['id'])
        stage = self.studio.production._get(project['id'])['plan']['stages'][0]
        job_id = results.job_identity(project['id'])
        self.studio.production._attempt(project['id'], 0, job_id=job_id)
        self.studio.create_job(stage['request'], enqueue=False, job_id=job_id)
        job = self.studio.jobs[job_id]; job.update(project_id=project['id'], status='not_submitted'); self.studio._save(job)
        report = self.collect()
        self.assertEqual(study.read_json(self.destination/'records.json'), [])
        self.assertEqual(report['cases'][0]['disposition'], 'not_submitted')
        self.assertEqual(report['production_budget'], {'allowance': 2, 'reserved': 1})
        self.assertIsNotNone(report['cases'][0]['execution_evidence'])

    def test_rehashed_stage_cannot_change_approved_case_seed(self):
        project = self.project(); stored = self.studio.production._get(project['id']); plan = stored['plan']
        stage = plan['stages'][0]; node, field = plan['character_source']['handoff']['control_bindings']['seed'][0]
        stage['request']['controls']['seed'] = 99; stage['graph'][node]['inputs'][field] = 99
        from production import fingerprint
        stage['graph_sha256'] = fingerprint(stage['graph']); plan['sha256'] = fingerprint({k:v for k,v in plan.items() if k != 'sha256'})
        with self.studio.production.connect() as db: db.execute('UPDATE projects SET plan=? WHERE id=?', (json.dumps(plan), project['id']))
        self.studio._write_json_atomic(self.studio.production.root/project['id']/'plan.json', plan)
        with self.assertRaisesRegex(ValueError, 'handoff'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_active_known_prompt_is_uncertain_and_does_not_invent_elapsed_time(self):
        job = self.execute(self.project()); job.update(status='running', outputs=[])
        job['submissions'][0]['status'] = 'observing'; self.studio._save(job)
        self.collect(); record = study.read_json(self.destination/'records.json')[0]
        self.assertEqual(record['state'], 'submission_uncertain'); self.assertEqual(record['prompt_id'], job['prompt_ids'][0])
        self.assertIsNone(record['elapsed_seconds']); self.assertIsNone(record['output'])

    def test_output_path_and_byte_limits_are_checked_before_export(self):
        job = self.execute(self.project()); asset_id = job['outputs'][0]['asset_id']
        with patch.object(results, 'IMAGE_LIMIT', len(fixtures.PNG)-1):
            with self.assertRaisesRegex(ValueError, 'byte count'): self.collect()
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET path=? WHERE id=?', ('media/../../escape.png', asset_id))
        with self.assertRaisesRegex(ValueError, 'Path escapes'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_missing_reservation_cannot_produce_a_valid_attempt_record(self):
        self.execute(self.project())
        with self.studio.production.connect() as db: db.execute('UPDATE budgets SET reserved=0')
        with self.assertRaisesRegex(ValueError, 'exceed saved reservations'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_output_copy_is_exclusive_and_a_second_collection_keeps_the_first(self):
        self.execute(self.project()); self.collect()
        original = (self.destination/'collection.json').read_bytes()
        with self.assertRaises(FileExistsError): self.collect()
        self.assertEqual((self.destination/'collection.json').read_bytes(), original)

    def test_wrong_job_owner_graph_prompt_and_batch_are_rejected(self):
        job = self.execute(self.project()); original = copy.deepcopy(job)
        for mutation in (
                lambda j: j.update(project_id='0'*32),
                lambda j: j.update(batch_count=2),
                lambda j: j['graph']['3']['inputs'].update(seed=999),
                lambda j: j['outputs'][0].update(prompt_id='another-prompt')):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(original); mutation(changed); self.studio._save(changed)
                with self.assertRaises(ValueError): self.collect()
                self.assertFalse(self.destination.exists())
        self.studio._save(original)

    def test_missing_job_and_torn_plan_are_not_silently_omitted(self):
        project = self.project(); job = self.execute(project)
        state = self.studio.runs/job['id']/'state.json'; original = state.read_bytes(); state.unlink()
        with self.assertRaises((OSError, ValueError)): self.collect()
        self.assertFalse(self.destination.exists()); state.write_bytes(original)
        (self.studio.production.root/project['id']/'plan.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'plan'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_wrong_asset_owner_or_changed_snapshot_rejects_success(self):
        job = self.execute(self.project()); asset = self.studio.assets.get(job['outputs'][0]['asset_id'])
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET job_id=? WHERE id=?', ('unrelated', asset['id']))
        with self.assertRaisesRegex(ValueError, 'asset'): self.collect()
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET job_id=? WHERE id=?', (job['id'], asset['id']))
        self.studio.assets.file(asset['id']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'asset'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_unbound_same_budget_branch_cannot_be_hidden(self):
        parent = self.project(); recipe = self.studio.production._get(parent['id'])['plan']['recipe']
        self.studio.production.create({'name': 'Generic branch', 'recipe': recipe, 'axis': 'seed', 'values': [9], 'parent_project': parent['id']})
        with self.assertRaisesRegex(ValueError, 'primary'): self.collect()
        self.assertFalse(self.destination.exists())

    def test_changing_source_during_collection_keeps_an_incomplete_marker(self):
        job = self.execute(self.project()); original = results._copy_asset
        def change_after_copy(*args):
            value = original(*args); job['message'] = 'Changed while collecting'; self.studio._save(job); return value
        with patch.object(results, '_copy_asset', side_effect=change_after_copy):
            with self.assertRaisesRegex(ValueError, 'changed during'): self.collect()
        self.assertTrue((self.destination/'.incomplete').is_file())
        self.assertFalse((self.destination/'collection.json').exists())

    def test_read_only_database_connection_and_missing_database(self):
        self.project()
        with results._database(self.studio.production.db) as db:
            with self.assertRaises(sqlite3.OperationalError): db.execute('DELETE FROM projects')
        missing = self.root/'missing.sqlite3'
        with self.assertRaises((OSError, ValueError, sqlite3.Error)):
            with results._database(missing): pass
        self.assertFalse(missing.exists())

    def test_cli_collects_actual_saved_fixture_and_reports_existing_summary(self):
        self.execute(self.project()); plan = self.workspace/'plan.json'; study.write_json(plan, self.plan)
        self.patches[0].stop()  # The fixture worker stays unstarted; subprocess readers need their own threads.
        run = subprocess.run([sys.executable, '-Xutf8', str(fixtures.ROOT/'scripts/character_study_results.py'),
            '--plan', str(plan), '--workspace', str(self.workspace), '--experiments', str(self.studio.experiments),
            '--out', str(self.destination)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout)['completed_attempts'], 1)
        self.assertEqual(study.read_json(self.destination/'summary.json')['human_accepted_cases'], 0)


if __name__ == '__main__': unittest.main()
