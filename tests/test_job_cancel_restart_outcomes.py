"""The restart outcomes documented in OPERATIONS, without a Studio or engine."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import job_cancel


class RestartOutcomesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.request = {'event_id': 'request-1', 'state': 'requested', 'requested_at': 1.0}
        self.path = self.root / job_cancel.REQUEST_FILE
        self.path.write_text(json.dumps(self.request), encoding='utf-8')
        self.original = self.path.read_bytes()

    def assert_no_disk_writes(self):
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_never_submitted_job_is_cancelled(self):
        job = {'status': 'not_submitted', 'prompt_ids': [], 'submissions': [], 'outputs': []}
        self.assertTrue(job_cancel.reconcile_restart(job, self.root))
        self.assertEqual((job['status'], job['cancellation']['state']), ('cancelled', 'cancelled'))
        self.assertIn('nothing was sent', job['cancellation']['note'])
        self.assert_no_disk_writes()

    def test_settled_job_retains_status_and_cancellation_is_too_late(self):
        for status in ('completed', 'failed', 'partial', 'cancelled', 'abandoned'):
            with self.subTest(status=status):
                job = {'status': status, 'outputs': ['kept-output']}
                self.assertTrue(job_cancel.reconcile_restart(job, self.root))
                self.assertEqual(job['status'], status)
                self.assertEqual(job['outputs'], ['kept-output'])
                self.assertEqual(job['cancellation']['state'], 'too_late')
                self.assertIn('settled as ' + status, job['cancellation']['note'])
        self.assert_no_disk_writes()

    def test_live_or_uncertain_job_keeps_unresolved_cancellation(self):
        for status in (*job_cancel.CANCELLABLE, 'uncertain'):
            with self.subTest(status=status):
                job = {'status': status, 'prompt_ids': ['original-prompt']}
                self.assertTrue(job_cancel.reconcile_restart(job, self.root))
                self.assertEqual(job['status'], status)
                self.assertEqual(job['prompt_ids'], ['original-prompt'])
                self.assertEqual(job['cancellation']['state'], 'unresolved')
                self.assertIn('nothing was resubmitted', job['cancellation']['note'])
        self.assert_no_disk_writes()

    def test_already_resolved_same_request_is_unchanged(self):
        for state in ('cancelled', 'refused', 'too_late', 'unresolved'):
            with self.subTest(state=state):
                job = {'status': 'completed', 'cancellation': dict(self.request, state=state, note='keep evidence')}
                before = copy.deepcopy(job)
                self.assertFalse(job_cancel.reconcile_restart(job, self.root))
                self.assertEqual(job, before)
        self.assert_no_disk_writes()
