"""Independent dispatch-boundary regressions; synthetic callbacks and files only."""
from __future__ import annotations

import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import attempt_ledger as ledger
import dispatch_coordinator as coordinator
from dispatch_fixtures import make_dispatch_case, parameters
from dispatch_simulation import SimulationPort
import pipeline as p


class IndependentDispatchReviewTests(unittest.TestCase):
    def setUp(self):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'dispatch-review-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = make_dispatch_case(self.root)
        coordinator.initialize(self.c['ledger_path'])
        self.port = SimulationPort(self.c['simulation_path'])
        self.ticket = coordinator.prepare_dispatch(self.c['ledger_path'], request_id='review-request',
                                                    **parameters(self.c))
        self.assertTrue(self.ticket['passed'], self.ticket)

    def drive(self):
        return coordinator.dispatch_once(self.c['ledger_path'], self.ticket['attempt_id'],
                                          port=self.port, **parameters(self.c))

    def reconcile(self):
        return coordinator.reconcile_dispatch(self.c['ledger_path'], self.ticket['attempt_id'],
                                               experiments=self.c['experiments'], intent=self.c['intent'])

    def retained_attempt(self):
        with ledger._connection(self.c['ledger_path']) as db:
            return dict(db.execute('SELECT * FROM attempts WHERE attempt_id=?',
                                   (self.ticket['attempt_id'],)).fetchone())

    def completed_job(self):
        acknowledged = self.drive()
        self.assertTrue(acknowledged['passed'], acknowledged)
        root = self.c['experiments'] / 'runs' / self.c['intent']['job_id']
        job = p.load_json(root / 'state.json')
        job['status'] = 'completed'
        job['submissions'][0]['status'] = 'completed'
        job['outputs'] = [{'filename': 'fixture.png', 'prompt_id': acknowledged['prompt_id']}]
        (root / 'state.json').write_bytes(p.canonical_bytes(job))
        return root, job, acknowledged

    def assert_unresolved(self):
        self.assertEqual(self.retained_attempt()['state'], 'unresolved')
        self.assertIsNone(self.retained_attempt()['observation_sha256'])

    def test_caller_graph_mutation_during_admission_cannot_change_callback_body(self):
        expected = p.digest({'prompt': copy.deepcopy(self.c['intent']['graph']),
                             'client_id': 'asset-studio'})
        original = coordinator._admit

        def mutate_caller(*args, **kwargs):
            report = original(*args, **kwargs)
            self.c['intent']['graph']['2']['inputs']['text'] = 'late unprepared mutation'
            return report

        with patch.object(coordinator, '_admit', side_effect=mutate_caller):
            result = self.drive()
        with sqlite3.connect(self.c['simulation_path']) as db:
            sent = [row[0] for row in db.execute('SELECT body_sha256 FROM callbacks')]
        # Refusal is safe; a callback must use the exact frozen prepared body.
        if result['passed']:
            self.assertEqual(result['state'], 'acknowledged', result)
            self.assertEqual(sent, [expected])
        else:
            self.assertEqual(sent, [], result)

    def test_terminal_prompt_must_match_retained_acknowledgement(self):
        root, job, acknowledged = self.completed_job()
        self.assertNotEqual(acknowledged['prompt_id'], 'foreign-prompt')
        job['prompt_ids'] = ['foreign-prompt']
        job['submissions'][0]['prompt_id'] = 'foreign-prompt'
        job['outputs'][0]['prompt_id'] = 'foreign-prompt'
        (root / 'state.json').write_bytes(p.canonical_bytes(job))
        result = self.reconcile()
        self.assertFalse(result['passed'], result)
        self.assert_unresolved()
        self.assertEqual(self.port.count(), 1)

    def test_workflow_changed_between_validation_and_resolution_stays_unresolved(self):
        root, _, _ = self.completed_job()
        original = ledger._observation

        def mutate_workflow(*args, **kwargs):
            (root / 'workflow.json').write_bytes(p.canonical_bytes(
                {'wrong': {'class_type': 'Changed', 'inputs': {}}}))
            return original(*args, **kwargs)

        with patch.object(ledger, '_observation', side_effect=mutate_workflow):
            result = self.reconcile()
        self.assertFalse(result['passed'], result)
        self.assert_unresolved()

    def test_state_changed_between_validation_and_resolution_stays_unresolved(self):
        root, job, _ = self.completed_job()
        original = ledger._observation

        def mutate_state(*args, **kwargs):
            changed = copy.deepcopy(job)
            changed['submissions'][0]['seed'] = self.c['intent']['seed'] + 1
            (root / 'state.json').write_bytes(p.canonical_bytes(changed))
            return original(*args, **kwargs)

        with patch.object(ledger, '_observation', side_effect=mutate_state):
            result = self.reconcile()
        self.assertFalse(result['passed'], result)
        self.assert_unresolved()

    def test_numeric_aliases_do_not_satisfy_exact_submission_member(self):
        root, job, _ = self.completed_job()
        cases = {
            'float-seed': lambda member: member.update(seed=float(self.c['intent']['seed'])),
            'bool-index': lambda member: member.update(index=False),
            'float-index': lambda member: member.update(index=0.0),
            'wrong-index': lambda member: member.update(index=1),
            'float-graph-seed': lambda member: member['graph']['2']['inputs'].update(
                seed=float(self.c['intent']['seed'])),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                changed = copy.deepcopy(job)
                mutate(changed['submissions'][0])
                (root / 'state.json').write_bytes(p.canonical_bytes(changed))
                result = self.reconcile()
                self.assertFalse(result['passed'], result)
                self.assert_unresolved()
        (root / 'state.json').write_bytes(p.canonical_bytes(job))
        self.assertTrue(self.reconcile()['passed'])

    def test_withdrawal_during_pending_publication_consumes_claim_without_callback(self):
        original = coordinator._publish_pending

        def withdraw(*args, **kwargs):
            job = original(*args, **kwargs)
            with self.c['workspace'].connection() as db:
                db.execute("UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'")
            return job

        with patch.object(coordinator, '_publish_pending', side_effect=withdraw):
            result = self.drive()
        self.assertFalse(result['passed'], result)
        self.assertIn(result['state'], ('claimed', 'uncertain'))
        self.assertEqual(self.port.count(), 0)
        replay = self.drive()
        self.assertEqual(replay['action'], 'observe-existing', replay)
        self.assertFalse(replay['callback_invoked'])
        self.assertEqual(self.port.count(), 0)


if __name__ == '__main__':
    unittest.main()
