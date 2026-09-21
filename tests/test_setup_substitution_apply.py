"""Revision-checked atomic application of setup substitutions."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest import mock

import test_recipe_shortlist_apply as A
import test_setup_substitution as F
from studio_workflow import setup_substitution as S
from studio_workflow.core import canonical


class AtomicSetupSubstitutionTests(unittest.TestCase):
    setUp = A.SetupApplyTests.setUp
    store = A.SetupApplyTests.store
    command = A.SetupApplyTests.command
    create = A.SetupApplyTests.create

    def set_controls(self):
        self.before['recipe']['controls'].update(F.draft()['recipe']['controls'])
        self.q['draft'] = copy.deepcopy(self.before)

    def plan(self, **updates):
        value = F.substitution_request(current=self.before, **updates)
        return S.request(value)

    def substitute(self, current, report=None, *, request_id='substitute-request',
                   expected_revision=None):
        report = report or self.plan()
        return self.command(
            'substitute', request_id=request_id,
            draft_id=current['draft_id'],
            expected_revision=(current['revision'] if expected_revision is None
                               else expected_revision),
            proposal_json=report['proposal_json'],
            approved_proposal_sha256=report['proposal_sha256'],
        )

    def test_substitute_commits_the_complete_diff_as_one_revision_without_staging(self):
        self.set_controls()
        current = self.create()
        report = self.plan()
        result = self.substitute(current, report)
        self.assertEqual(result['status'], 'committed')
        self.assertEqual((result['previous_revision'], result['revision']), (1, 2))
        self.assertEqual(result['draft'], report['after'])
        self.assertEqual(self.store().get(current['draft_id'], 1)['draft'], self.before)
        self.assertEqual(self.store().get(current['draft_id'], 2)['draft'], report['after'])
        self.assertEqual(self.s.upload_count, 0)
        self.assertEqual(result['staged'], [])
        self.assertFalse(result['staging_may_have_occurred'])
        self.assertFalse(result['generation_submitted'])
        replay = self.substitute(current, report)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['revision'], 2)
        self.assertEqual(self.s.upload_count, 0)

    def test_stale_revision_refuses_before_any_write(self):
        self.set_controls()
        current = self.create()
        changed = copy.deepcopy(self.before)
        changed['recipe']['controls']['cfg'] = 4
        newer = self.command('replace', request_id='newer-edit',
                             draft_id=current['draft_id'], expected_revision=1,
                             draft=changed)
        self.assertEqual(newer['revision'], 2)
        with self.assertRaisesRegex(ValueError, 'revision|Revision'):
            self.substitute(current, self.plan(), request_id='late-substitution')
        self.assertEqual(self.store().get(current['draft_id'])['draft'], changed)
        self.assertEqual(self.s.upload_count, 0)

    def test_tampered_proposal_fails_and_retains_the_head(self):
        self.set_controls()
        current = self.create()
        report = self.plan()
        core = json.loads(report['proposal_json'])
        core['after']['recipe']['controls']['steps'] = 9
        exact = canonical(core).decode()
        result = self.command(
            'substitute', request_id='tampered-substitution',
            draft_id=current['draft_id'], expected_revision=1,
            proposal_json=exact,
            approved_proposal_sha256=hashlib.sha256(exact.encode()).hexdigest(),
        )
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.store().get(current['draft_id'])['revision'], 1)
        self.assertEqual(self.store().recover('tampered-substitution')['status'], 'failed')
        self.assertEqual(self.s.upload_count, 0)

    def test_incompatible_or_stale_inspectable_plan_cannot_be_applied(self):
        self.set_controls()
        for label, report in [
            ('incompatible', self.plan(
                compatibility=F.compatibility_request(architecture='flux'))),
            ('stale', self.plan(card=F.profile(source_status='stale'))),
        ]:
            with self.subTest(label=label):
                current = self.command('create', request_id='create-' + label,
                                       draft=self.before)
                result = self.substitute(current, report,
                                         request_id='substitute-' + label)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(self.store().get(current['draft_id'])['revision'], 1)
        self.assertEqual(self.s.upload_count, 0)

    def test_runtime_or_graph_change_refuses_the_reviewed_transaction(self):
        self.set_controls()
        current = self.create()
        report = self.plan()
        self.s.comfy_url = 'http://127.0.0.1:9999'
        runtime = self.substitute(current, report, request_id='runtime-changed')
        self.assertEqual(runtime['status'], 'failed')
        self.assertEqual(self.store().get(current['draft_id'])['revision'], 1)
        self.s.comfy_url = 'http://127.0.0.1:8188'
        _, path = self.s.graph_for(self.p)
        path.write_bytes(path.read_bytes() + b' ')
        graph = self.substitute(current, report, request_id='graph-changed')
        self.assertEqual(graph['status'], 'failed')
        self.assertEqual(self.store().get(current['draft_id'])['revision'], 1)
        self.assertEqual(self.s.upload_count, 0)

    def test_append_failure_records_failure_without_partial_revision(self):
        self.set_controls()
        current = self.create()
        report = self.plan()
        store = self.store()
        command = {
            'action': 'substitute', 'workspace_id': self.scope,
            'request_id': 'append-failure', 'draft_id': current['draft_id'],
            'expected_revision': 1, 'proposal_json': report['proposal_json'],
            'approved_proposal_sha256': report['proposal_sha256'],
        }
        with mock.patch.object(store, '_append', side_effect=ValueError('append fixture')):
            result = store.command(command)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(store.get(current['draft_id'])['revision'], 1)
        self.assertEqual(store.recover('append-failure')['status'], 'failed')
        self.assertEqual(self.s.upload_count, 0)


class AtomicSetupSubstitutionAgentTests(unittest.TestCase):
    setUp = A.SetupApplyTransportTests.setUp

    def test_author_agent_uses_the_same_atomic_command_and_read_scope_cannot_write(self):
        from studio_workflow.agent_bridge import AgentBridge

        self.before['recipe']['controls'].update(F.draft()['recipe']['controls'])
        current = self.client.setup_drafts.create(
            self.before, workspace_id=self.scope, request_id='agent-create')
        report = S.request(F.substitution_request(current=self.before))
        command = {
            'action': 'substitute', 'workspace_id': self.scope,
            'request_id': 'agent-substitute', 'draft_id': current['draft_id'],
            'expected_revision': current['revision'],
            'proposal_json': report['proposal_json'],
            'approved_proposal_sha256': report['proposal_sha256'],
        }
        read = AgentBridge(self.client, 'read').invoke(
            'setup_draft_command', {'command_json': json.dumps(command)})
        self.assertFalse(read['ok'])
        self.assertEqual(self.s.upload_count, 0)
        authored = AgentBridge(self.client, 'author').invoke(
            'setup_draft_command', {'command_json': json.dumps(command)})
        self.assertTrue(authored['ok'], authored)
        saved = json.loads(authored['data_json'])
        self.assertEqual(saved['status'], 'committed')
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(saved['draft'], report['after'])
        self.assertEqual(self.client.setup_drafts.recover('agent-substitute')['revision'], 2)
        self.assertEqual(self.s.upload_count, 0)
        self.assertFalse(saved['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
