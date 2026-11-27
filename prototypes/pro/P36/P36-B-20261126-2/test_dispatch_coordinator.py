"""At-most-once synthetic dispatch with real SQLite, file barriers and processes."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import pipeline as p
import attempt_ledger
from dispatch_fixtures import make_dispatch_case, parameters, write_context

try:
    import dispatch_coordinator as coordinator
    from dispatch_simulation import SimulationPort
except ModuleNotFoundError as error:
    if error.name not in ('dispatch_coordinator', 'dispatch_simulation'):
        raise
    coordinator = None


class DispatchCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(coordinator, 'Durable dispatch coordinator must be implemented')
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'dispatch-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = make_dispatch_case(self.root)
        coordinator.initialize(self.c['ledger_path'])
        self.port = SimulationPort(self.c['simulation_path'])

    def prepare(self, request='request-1', **changes):
        return coordinator.prepare_dispatch(self.c['ledger_path'], request_id=request,
                                            **{**parameters(self.c), **changes})

    def drive(self, ticket, **changes):
        return coordinator.dispatch_once(self.c['ledger_path'], ticket['attempt_id'],
                                          port=self.port, **{**parameters(self.c), **changes})

    def revoke(self):
        with self.c['workspace'].connection() as db:
            db.execute("UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'")

    def test_prepare_binds_intent_without_callback_and_replay_keeps_identity(self):
        first = self.prepare(); replay = self.prepare()
        self.assertTrue(first['passed'], first)
        self.assertTrue(first['created'])
        self.assertFalse(replay['created'])
        self.assertEqual(first['attempt_id'], replay['attempt_id'])
        self.assertEqual(self.port.count(), 0)
        self.assertFalse(first['generation_submitted'])
        self.assertFalse(first['submission_authority'])

    def test_one_valid_callback_and_repeated_drive_never_reissues(self):
        ticket = self.prepare()
        first = self.drive(ticket)
        self.assertTrue(first['passed'], first)
        self.assertEqual(first['state'], 'acknowledged')
        self.assertEqual(self.port.count(), 1)
        self.assertFalse(first['generation_submitted'])
        for _ in range(3):
            replay = self.drive(ticket)
            self.assertEqual(replay['action'], 'observe-existing')
            self.assertFalse(replay['callback_invoked'])
        self.assertEqual(self.port.count(), 1)

    def test_ordinary_admission_stays_blocked_by_the_owned_reservation(self):
        import admission
        self.prepare()
        args = parameters(self.c); args.pop('intent'); args.pop('studio_root')
        result = admission.check_transition(**args, stage='turnaround', ledger_path=self.c['ledger_path'])
        self.assertFalse(result['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_withdrawal_before_preparation_does_not_reserve(self):
        self.revoke(); result = self.prepare()
        self.assertFalse(result['passed'])
        self.assertEqual(coordinator.ticket_count(self.c['ledger_path']), 0)
        self.assertEqual(self.port.count(), 0)

    def test_withdrawal_after_preparation_blocks_claim(self):
        ticket = self.prepare(); self.revoke()
        result = self.drive(ticket)
        self.assertFalse(result['passed'])
        self.assertEqual(result['state'], 'prepared')
        self.assertEqual(self.port.count(), 0)

    def test_semantic_side_swap_after_preparation_blocks(self):
        ticket = self.prepare()
        self.c['annotations']['concept']['views'][0]['anchors']['left-iris']['value'] = 'blue'
        self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_changed_effective_graph_cannot_rebind_same_ticket(self):
        ticket = self.prepare()
        wrong = copy.deepcopy(self.c['intent']); wrong['graph']['invented'] = {'class_type': 'Changed', 'inputs': {}}
        self.assertFalse(self.drive(ticket, intent=wrong)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_changed_prepared_plan_file_blocks_unchanged_intent(self):
        ticket = self.prepare()
        path = self.c['experiments'] / 'projects' / self.c['intent']['project_id'] / 'plan.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_changed_workspace_source_cannot_borrow_ticket(self):
        ticket = self.prepare()
        with self.c['workspace'].connection() as db:
            db.execute('UPDATE workspace_identity SET id=?', ('b' * 32,))
        self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_other_unresolved_ancestor_is_not_hidden_by_own_ticket_exception(self):
        ticket = self.prepare()
        attempt_ledger.reserve(self.c['ledger_path'], family_id=self.c['family']['family_id'], stage='concept',
            request_id='foreign', job_id='foreign', intent_sha256='c' * 64,
            experiments=self.c['experiments'], workspace_id=self.c['family']['workspace_id'])
        self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_known_orphaned_reservation_is_never_adopted(self):
        intent_hash = p.digest(self.c['intent'])
        attempt_ledger.reserve(self.c['ledger_path'], family_id=self.c['family']['family_id'], stage='turnaround',
            request_id='request-1', job_id=self.c['intent']['job_id'], intent_sha256=intent_hash,
            experiments=self.c['experiments'], workspace_id=self.c['family']['workspace_id'])
        self.assertFalse(self.prepare()['passed'])
        self.assertEqual(coordinator.ticket_count(self.c['ledger_path']), 0)

    def test_worker_conditions_fail_before_claim(self):
        ticket = self.prepare()
        for field in ('backend_ready', 'budget_allowed', 'lease_held'):
            with self.subTest(field=field):
                self.port.conditions[field] = False
                self.assertFalse(self.drive(ticket)['passed'])
                self.assertEqual(self.port.count(), 0)
                self.port.conditions[field] = True
        self.assertTrue(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 1)

    def test_conditions_that_revoke_authority_cannot_create_a_stale_claim(self):
        ticket = self.prepare(); conditions = self.port.check_conditions
        def revoke(*args, **kwargs):
            result = conditions(*args, **kwargs); self.revoke(); return result
        with patch.object(self.port, 'check_conditions', side_effect=revoke):
            self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.port.count(), 0)

    def test_lost_response_consumes_claim_without_repeating_callback(self):
        ticket = self.prepare(); self.port.mode = 'lost-response'
        first = self.drive(ticket)
        self.assertFalse(first['passed'])
        self.assertEqual(first['state'], 'uncertain')
        self.assertEqual(self.port.count(), 1)
        self.port.mode = 'accept'
        self.assertEqual(self.drive(ticket)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 1)

    def test_malformed_response_consumes_claim(self):
        ticket = self.prepare(); self.port.mode = 'malformed'
        self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.drive(ticket)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 1)

    def test_pending_publication_failure_sends_nothing_and_never_rearms(self):
        ticket = self.prepare()
        with patch.object(coordinator, '_publish_pending', side_effect=OSError('synthetic full disk')):
            result = self.drive(ticket)
        self.assertFalse(result['passed'])
        self.assertEqual(self.port.count(), 0)
        self.assertEqual(self.drive(ticket)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 0)

    def test_receipt_publication_failure_preserves_claim_and_does_not_reissue(self):
        ticket = self.prepare()
        with patch.object(coordinator, '_publish_acknowledgement', side_effect=OSError('lost receipt')):
            self.assertFalse(self.drive(ticket)['passed'])
        self.assertEqual(self.drive(ticket)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 1)

    def test_malformed_retained_outcomes_cannot_be_observed_or_reconciled_as_success(self):
        ticket = self.prepare(); self.drive(ticket)
        for value in (None, [], True, 1, 'invalid', {}, {'simulation_only': True, 'prompt_id': 'unbound'}):
            with self.subTest(value=value):
                with sqlite3.connect(self.c['ledger_path']) as db:
                    db.execute('UPDATE p36_dispatch_tickets SET outcome_json=?', (json.dumps(value),))
                self.assertFalse(coordinator.inspect_dispatch(self.c['ledger_path'], ticket['attempt_id'])['passed'])
                result = coordinator.reconcile_dispatch(self.c['ledger_path'], ticket['attempt_id'],
                    experiments=self.c['experiments'], intent=self.c['intent'])
                self.assertFalse(result['passed'], result)
        self.assertEqual(self.port.count(), 1)

    def test_malformed_terminal_job_is_a_refusal(self):
        ticket = self.prepare(); self.drive(ticket)
        path = self.c['experiments'] / 'runs' / self.c['intent']['job_id'] / 'state.json'
        for value in (None, [], True, 1, 'invalid'):
            with self.subTest(value=value):
                path.write_bytes(p.canonical_bytes(value))
                result = coordinator.reconcile_dispatch(self.c['ledger_path'], ticket['attempt_id'],
                    experiments=self.c['experiments'], intent=self.c['intent'])
                self.assertFalse(result['passed'], result)
        self.assertEqual(self.port.count(), 1)

    def test_real_studio_never_submitted_predicate_refuses_the_pending_marker(self):
        import submission_evidence
        ticket = self.prepare(); self.port.mode = 'lost-response'; self.drive(ticket)
        state = p.load_json(self.c['experiments'] / 'runs' / self.c['intent']['job_id'] / 'state.json')
        self.assertFalse(submission_evidence.never_submitted(state))
        self.assertEqual(state['p36_attempt']['attempt_id'], ticket['attempt_id'])
        self.assertEqual(state['pending_submission']['graph'], self.c['intent']['graph'])

    def _command(self, ticket, *, crash_at=None):
        context = self.root / 'context.json'
        if not context.exists(): write_context(context, self.c)
        command = [sys.executable, str(Path(__file__).with_name('dispatch_simulation.py')), 'worker',
                   '--context', str(context), '--ledger', str(self.c['ledger_path']),
                   '--attempt-id', ticket['attempt_id'], '--port', str(self.c['simulation_path'])]
        if crash_at: command.extend(['--crash-at', crash_at])
        return command

    def test_independent_processes_racing_same_ticket_call_port_once(self):
        ticket = self.prepare(); command = self._command(ticket)
        workers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
        results = [worker.communicate(timeout=45) for worker in workers]
        for worker, (stdout, stderr) in zip(workers, results):
            self.assertEqual(worker.returncode, 0, stderr.decode() + stdout.decode())
            self.assertIn(json.loads(stdout)['action'], ('acknowledged', 'observe-existing'))
        self.assertEqual(self.port.count(), 1)

    def test_process_crash_after_claim_never_rearms_even_before_callback(self):
        ticket = self.prepare()
        crashed = subprocess.run(self._command(ticket, crash_at='after-claim'), capture_output=True, timeout=45)
        self.assertEqual(crashed.returncode, 73, crashed.stderr.decode() + crashed.stdout.decode())
        self.assertEqual(self.port.count(), 0)
        recovered = subprocess.run(self._command(ticket), capture_output=True, timeout=45)
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        self.assertEqual(json.loads(recovered.stdout)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 0)

    def test_process_crash_after_callback_never_repeats_remote_effect(self):
        ticket = self.prepare()
        crashed = subprocess.run(self._command(ticket, crash_at='after-callback'), capture_output=True, timeout=45)
        self.assertEqual(crashed.returncode, 73, crashed.stderr.decode() + crashed.stdout.decode())
        self.assertEqual(self.port.count(), 1)
        recovered = subprocess.run(self._command(ticket), capture_output=True, timeout=45)
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        self.assertEqual(json.loads(recovered.stdout)['action'], 'observe-existing')
        self.assertEqual(self.port.count(), 1)


if __name__ == '__main__': unittest.main()
