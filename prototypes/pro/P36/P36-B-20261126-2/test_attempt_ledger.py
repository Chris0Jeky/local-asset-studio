"""Durable no-output uncertainty and duplicate-request regressions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

import attempt_ledger as ledger
import pipeline as p


class AttemptLedgerTests(unittest.TestCase):
    def setUp(self):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'attempts.sqlite3'
        self.experiments = self.root / 'experiments'
        from workspace import AssetWorkspace
        self.workspace = AssetWorkspace(self.experiments)
        self.workspace_id = self.workspace.snapshot()['workspace_id']
        ledger.initialize(self.path)

    def reserve(self, request='request-1', job='job-1', plan='b' * 64, stage='turnaround'):
        result = ledger.reserve(self.path, family_id='p36-fixture', stage=stage,
                                request_id=request, job_id=job, intent_sha256=plan,
                                experiments=self.experiments, workspace_id=self.workspace_id)
        self.reservation = result
        return result

    def job(self, job_id='job-1', **changes):
        value = {'id': job_id, 'status': 'completed', 'operation': 'asset.import',
                 'prompt_ids': [], 'submissions': [], 'outputs': [{'filename': 'test.png'}]}
        value.update(changes)
        if getattr(self, 'reservation', None): value.setdefault('p36_attempt', self.reservation['job_binding'])
        root = self.experiments / 'runs' / job_id; root.mkdir(parents=True, exist_ok=True)
        (root / 'state.json').write_bytes(p.canonical_bytes(value))
        (root / 'workflow.json').write_bytes(p.canonical_bytes({'fixture': 'no-generation'}))
        return root / 'state.json'

    def inspect(self):
        return ledger.inspect(self.path, family_id='p36-fixture', stages=['turnaround'], experiments=self.experiments)

    def test_first_reservation_is_durable_and_does_not_submit(self):
        result = self.reserve()
        self.assertTrue(result['created'])
        self.assertFalse(result['generation_submitted'])
        self.assertFalse(result['submission_authority'])
        self.assertFalse(self.inspect()['passed'])

    def test_same_request_is_observation_only_never_reissue(self):
        first = self.reserve(); second = self.reserve()
        self.assertEqual(first['attempt_id'], second['attempt_id'])
        self.assertFalse(second['created'])
        self.assertEqual(second['action'], 'observe-existing')

    def test_changed_request_payload_is_refused(self):
        self.reserve()
        for changes in ({'job': 'other'}, {'plan': 'c' * 64}, {'stage': 'mesh'}):
            with self.subTest(changes=changes), self.assertRaises(p.PipelineError): self.reserve(**changes)

    def test_no_artifacts_and_no_prompt_does_not_allow_fresh_attempt(self):
        self.reserve()
        self.assertFalse((self.experiments / 'runs').exists())
        with self.assertRaises(p.PipelineError): self.reserve('request-2', 'job-2')

    def test_lost_response_preserves_reserved_identity_after_reopen(self):
        attempt = self.reserve(); ledger.initialize(self.path)
        self.assertEqual(attempt['attempt_id'], self.reserve()['attempt_id'])
        with self.assertRaises(p.PipelineError): self.reserve('new', 'new')

    def test_observed_completion_requires_explicit_resolution(self):
        attempt = self.reserve(); self.job()
        self.assertFalse(self.inspect()['passed'])
        result = ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)
        self.assertEqual(result['state'], 'completed')
        self.assertTrue(self.inspect()['passed'])
        self.assertTrue(self.reserve('request-2', 'job-2')['created'])

    def test_uncertain_and_missing_job_cannot_resolve(self):
        attempt = self.reserve()
        with self.assertRaises((p.PipelineError, OSError)): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)
        self.job(status='uncertain')
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_completed_label_with_pending_submission_cannot_resolve(self):
        attempt = self.reserve(); self.job(pending_submission={'index': 0})
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_completed_comfy_job_needs_every_known_prompt(self):
        attempt = self.reserve()
        self.job(operation=None, batch_count=2, prompt_ids=['prompt-1'],
                 submissions=[{'prompt_id': 'prompt-1', 'status': 'completed'}], outputs=[{'prompt_id': 'prompt-1'}])
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_known_terminal_failure_can_be_recorded_without_a_retry(self):
        attempt = self.reserve()
        self.job(operation=None, status='failed', batch_count=1, prompt_ids=['prompt-1'],
                 submissions=[{'prompt_id': 'prompt-1', 'status': 'failed'}], outputs=[])
        result = ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)
        self.assertEqual(result['state'], 'failed')
        self.assertFalse(result['generation_submitted'])
        self.assertTrue(self.inspect()['passed'])

    def test_failed_label_without_submission_evidence_does_not_clear_uncertainty(self):
        attempt = self.reserve(); self.job(status='failed', outputs=[])
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_other_job_cannot_resolve_reserved_attempt(self):
        attempt = self.reserve(); path = self.job()
        value = p.load_json(path); value['id'] = 'job-2'; path.write_bytes(p.canonical_bytes(value))
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_resolved_evidence_changed_afterwards_blocks_again(self):
        attempt = self.reserve(); self.job(); ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)
        self.job(status='uncertain')
        self.assertFalse(self.inspect()['passed'])

    def test_two_simultaneous_connections_admit_exactly_one(self):
        barrier = threading.Barrier(2)
        def submit(index):
            barrier.wait()
            try: return self.reserve('r-' + str(index), 'j-' + str(index))['created']
            except p.PipelineError: return False
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(submit, [1, 2]))
        self.assertEqual(sorted(results), [False, True])

    def test_job_id_cannot_be_reused_by_other_stage(self):
        self.reserve()
        with self.assertRaises(p.PipelineError): self.reserve('new', stage='mesh')

    def test_missing_ledger_read_never_initializes_it(self):
        path = self.root / 'missing.sqlite3'
        with self.assertRaises(p.PipelineError): ledger.inspect(path, family_id='p36-fixture', stages=['mesh'], experiments=self.experiments)
        self.assertFalse(path.exists())

    def test_ledger_outside_runtime_is_refused(self):
        with self.assertRaises(p.PipelineError): ledger.initialize(p.REPO_ROOT / 'unexpected.sqlite3')

    def test_empty_ledger_snapshot_is_stable(self):
        self.assertEqual(self.inspect(), self.inspect())
        self.assertTrue(self.inspect()['passed'])

    def test_preexisting_job_cannot_be_attached_to_new_attempt(self):
        self.job()
        with self.assertRaises(p.PipelineError): self.reserve()

    def test_other_workspace_cannot_resolve_original_uncertainty(self):
        from workspace import AssetWorkspace
        attempt = self.reserve(); self.job(status='uncertain')
        other = self.root / 'other-experiments'; AssetWorkspace(other)
        directory = other / 'runs' / 'job-1'; directory.mkdir(parents=True)
        fake = {'id': 'job-1', 'status': 'completed', 'operation': 'asset.import',
                'prompt_ids': [], 'submissions': [], 'outputs': [{'filename': 'other.png'}],
                'p36_attempt': attempt['job_binding']}
        (directory / 'state.json').write_bytes(p.canonical_bytes(fake))
        (directory / 'workflow.json').write_bytes(p.canonical_bytes({}))
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=other)
        self.assertFalse(self.inspect()['passed'])

    def test_missing_or_changed_worker_ticket_cannot_resolve(self):
        attempt = self.reserve(); path = self.job()
        job = p.load_json(path); job.pop('p36_attempt'); path.write_bytes(p.canonical_bytes(job))
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)
        job['p36_attempt'] = dict(attempt['job_binding'], intent_sha256='f' * 64)
        path.write_bytes(p.canonical_bytes(job))
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)

    def test_mutated_ledger_identity_is_refused_before_replay_or_resolution(self):
        import sqlite3
        attempt = self.reserve(); self.job()
        with sqlite3.connect(self.path) as db: db.execute('UPDATE attempts SET job_id=?', ('other',))
        with self.assertRaises(p.PipelineError): self.reserve()
        with self.assertRaises(p.PipelineError): ledger.resolve(self.path, attempt['attempt_id'], experiments=self.experiments)


if __name__ == '__main__': unittest.main()
