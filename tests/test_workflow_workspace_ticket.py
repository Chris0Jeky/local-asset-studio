"""Tickets bind the evidence workspace, not just the Git checkout (#126 review)."""
import copy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

from studio_workflow.execution import prepare_ticket, run_ticket


class TicketStudio:
    def __init__(self, root):
        self.root = Path(root)
        self.experiments = self.root / 'experiments'
        self.runs = self.experiments / 'runs'
        self.runs.mkdir(parents=True)
        self.comfy_root = self.root / 'comfy'
        self.comfy_url = 'http://127.0.0.1:8188'
        self.backends = SimpleNamespace(active='primary')
        self.lock = threading.RLock()
        self.jobs, self.calls = {}, 0
        self.last_recipe = None
        self.path = self.root / 'graph.json'
        self.path.write_text('{"1":{"class_type":"Example","inputs":{}}}')
    def graph_for(self, preset): return json.loads(self.path.read_text()), self.path
    def prepare(self, recipe):
        graph, path = self.graph_for({})
        return {'id': 'example'}, graph, path, {}, 1
    def create_job(self, recipe, job_id=None):
        self.calls += 1
        self.last_recipe = copy.deepcopy(recipe)
        job = {'id': job_id, 'status': 'uncertain', 'prompt_ids': ['retained']}
        if isinstance(recipe, dict) and recipe.get('label') is not None:
            job['label'] = recipe['label']
        self.jobs[job_id] = job
        return self.public(self.jobs[job_id])
    def public(self, job): return copy.deepcopy(job)


class WorkspaceTicketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.studio = TicketStudio(self.temp.name)
        self.ticket = prepare_ticket(self.studio, {'preset_id': 'example'})
    def test_same_repository_new_experiments_rejects_dispatched_ticket(self):
        first = run_ticket(self.studio, self.ticket, True)
        old_receipt = self.studio.runs / 'workflow-requests' / (self.ticket['request_id'] + '.json')
        old_bytes = old_receipt.read_bytes()
        self.studio.experiments = self.studio.root / 'moved-experiments'
        self.studio.runs = self.studio.experiments / 'runs'
        self.studio.runs.mkdir(parents=True)
        self.studio.jobs = {}
        with self.assertRaisesRegex(ValueError, 'Run workspace changed'):
            run_ticket(self.studio, self.ticket, True)
        self.assertEqual(self.studio.calls, 1)
        self.assertEqual(old_receipt.read_bytes(), old_bytes)
        self.assertFalse((self.studio.runs / 'workflow-requests').exists())
        self.assertEqual(first['job']['prompt_ids'], ['retained'])
    def test_runs_path_alone_cannot_move_evidence_identity(self):
        self.studio.runs = self.studio.experiments / 'different-runs'
        self.studio.runs.mkdir()
        with self.assertRaisesRegex(ValueError, 'Run workspace changed'):
            run_ticket(self.studio, self.ticket, True)
        self.assertEqual(self.studio.calls, 0)
    def test_experiments_path_alone_is_also_pinned(self):
        self.studio.experiments = self.studio.root / 'other'
        with self.assertRaisesRegex(ValueError, 'Run workspace changed'):
            run_ticket(self.studio, self.ticket, True)
        self.assertEqual(self.studio.calls, 0)
    def test_legacy_unpinned_ticket_requires_manual_reconciliation(self):
        for key in ('experiments_root', 'runs_root'):
            ticket = copy.deepcopy(self.ticket); ticket['pins'].pop(key, None)
            with self.assertRaisesRegex(ValueError, 'lacks workspace pins'):
                run_ticket(self.studio, ticket, True)
        self.assertEqual(self.studio.calls, 0)
    def test_unchanged_workspace_replay_observes_retained_job(self):
        first = run_ticket(self.studio, self.ticket, True)
        again = run_ticket(self.studio, self.ticket, True)
        self.assertEqual(first['job'], again['job'])
        self.assertTrue(again['replayed']); self.assertFalse(again['dispatch_attempted'])
        self.assertEqual(self.studio.calls, 1)
    def test_empty_jobs_in_same_workspace_never_resubmit(self):
        run_ticket(self.studio, self.ticket, True); self.studio.jobs = {}
        result = run_ticket(self.studio, self.ticket, True)
        self.assertEqual(result['status'], 'reconciliation_required')
        self.assertEqual(self.studio.calls, 1)
    def test_valid_label_reaches_create_job_trimmed(self):
        ticket = prepare_ticket(self.studio, {'preset_id': 'example', 'label': '  Field Study  '})
        self.assertEqual(ticket['recipe']['label'], 'Field Study')
        result = run_ticket(self.studio, ticket, True)
        self.assertEqual(result['job']['label'], 'Field Study')
        self.assertEqual(self.studio.last_recipe['label'], 'Field Study')
        self.assertEqual(self.studio.calls, 1)
    def test_none_label_stays_backward_compatible(self):
        ticket = prepare_ticket(self.studio, {'preset_id': 'example', 'label': None})
        self.assertNotIn('label', ticket['recipe'])
        result = run_ticket(self.studio, ticket, True)
        self.assertNotIn('label', result['job'])
        self.assertEqual(self.studio.calls, 1)
    def test_invalid_labels_refused_before_receipt_or_dispatch(self):
        invalid = ['', '   ', 'x' * 81, 'bad\nlabel', 'bad\x00label', 123, True, ['x'], {'x': 1}]
        for index, label in enumerate(invalid):
            with self.subTest(label=repr(label)):
                studio = TicketStudio(Path(self.temp.name) / ('invalid-%d' % index))
                with self.assertRaisesRegex(ValueError, 'label must be|printable'):
                    prepare_ticket(studio, {'preset_id': 'example', 'label': label})
                self.assertEqual(studio.calls, 0)
                self.assertFalse((studio.runs / 'workflow-requests').exists())
        tampered = copy.deepcopy(self.ticket)
        tampered['recipe']['label'] = '   '
        with self.assertRaisesRegex(ValueError, 'label must be|printable'):
            run_ticket(self.studio, tampered, True)
        self.assertEqual(self.studio.calls, 0)
        self.assertFalse((self.studio.runs / 'workflow-requests').exists())
    def test_label_participates_in_replay_identity(self):
        ticket = prepare_ticket(self.studio, {'preset_id': 'example', 'label': 'Field Study'})
        first = run_ticket(self.studio, ticket, True)
        again = run_ticket(self.studio, ticket, True)
        self.assertEqual(first['job'], again['job'])
        self.assertTrue(again['replayed']); self.assertFalse(again['dispatch_attempted'])
        self.assertEqual(self.studio.calls, 1)
        relabelled = copy.deepcopy(ticket)
        relabelled['recipe']['label'] = 'Other Study'
        with self.assertRaisesRegex(ValueError, 'different content'):
            run_ticket(self.studio, relabelled, True)
        self.assertEqual(self.studio.calls, 1)
        unlabelled = copy.deepcopy(ticket)
        del unlabelled['recipe']['label']
        with self.assertRaisesRegex(ValueError, 'different content'):
            run_ticket(self.studio, unlabelled, True)
        self.assertEqual(self.studio.calls, 1)
