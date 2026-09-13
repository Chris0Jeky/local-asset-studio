"""Saved-ID dispatch: real records/ticket journal plus synthetic runtime only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess
import shutil
import unittest
from unittest.mock import patch

from http_refusal_transport import atomic_json_post
from test_workflow_document_runs import RunFixture
from studio_workflow.core import canonical, digest
from studio_workflow.documents import DocumentError
from studio_workflow.run_http import route, PREFIX, extend_handler
from studio_workflow.saved_dispatch import review_saved, run_saved


class SavedDispatchTests(RunFixture, unittest.TestCase):
    def approval(self):
        result = self.prepare(); report = result['record']['report']
        return {'approved': True, 'record_sha256': result['record_sha256'], 'ticket_sha256': report['ticket_sha256']}

    def test_read_packet_preserves_large_seed_and_hashes_as_exact_text(self):
        self.prepare()
        with patch.object(self.runtime, 'node_info', side_effect=AssertionError('No backend read')):
            packet = review_saved(self.store, self.value['request_id'])
        self.assertIn('9223372036854775807', packet['controls_json'])
        for key in ('record', 'ticket'):
            self.assertEqual(hashlib.sha256(packet[key + '_json'].encode()).hexdigest(), packet['source'][key + '_sha256'])
        self.assertEqual(self.runtime.submissions, 0)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for cross-language JSON proof')
    def test_javascript_number_roundtrip_changes_ticket_but_saved_id_does_not(self):
        approval = self.approval(); report = self.store.get(self.value['request_id'])['record']['report']
        raw = canonical(report['ticket'])
        coerced = subprocess.check_output(['node', '-e', 'let s="";process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))));'], input=raw, timeout=5)
        self.assertNotEqual(digest(json.loads(coerced)), report['ticket_sha256'])
        result = run_saved(self.runtime, self.store, self.value['request_id'], approval)
        self.assertEqual(result['dispatch']['job']['id'], report['job_id'])
        self.assertEqual(self.runtime.jobs[report['job_id']]['graph']['1']['inputs']['seed'], 2**63-1)
        receipt = json.loads((self.runtime.runs / 'workflow-requests' / (report['ticket']['request_id'] + '.json')).read_bytes())
        self.assertEqual(receipt['ticket_sha256'], report['ticket_sha256'])

    def test_bad_approval_never_reaches_dispatch(self):
        approved = self.approval()
        for edit in ({'approved': False}, {'approved': 1}, {'record_sha256': 'a'*64}, {'ticket_sha256': 'b'*64},
                     {'ticket': {}}, {'ticket_sha256': None}):
            with self.subTest(edit=edit), patch('studio_workflow.execution.run_ticket') as run:
                with self.assertRaises(ValueError): run_saved(self.runtime, self.store, self.value['request_id'], {**approved, **edit})
                run.assert_not_called()
        self.assertEqual(self.runtime.submissions, 0)

    def test_missing_record_does_not_prepare_or_run(self):
        with patch('studio_workflow.preset_adapter.prepare_document') as prepare, patch('studio_workflow.execution.run_ticket') as run:
            with self.assertRaises(DocumentError):
                run_saved(self.runtime, self.store, 'absent', {'approved': True, 'record_sha256': 'a'*64, 'ticket_sha256': 'b'*64})
            run.assert_not_called(); prepare.assert_not_called()

    def test_changed_source_runs_original_revision_and_repeat_is_one_job(self):
        approved = self.approval(); self.edit()
        first = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        again = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.assertEqual(first['source']['revision'], 1); self.assertEqual(self.docs.get(self.source['id'])['revision'], 2)
        self.assertTrue(again['dispatch']['replayed']); self.assertEqual(self.runtime.submissions, 1)
        self.assertEqual(first['source'], again['source'])

    def test_concurrent_runs_only_dispatch_once(self):
        approved = self.approval()
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: run_saved(self.runtime, self.store, self.value['request_id'], approved), range(4)))
        self.assertEqual(sum(not r['dispatch']['replayed'] for r in results), 1)
        self.assertEqual(self.runtime.submissions, 1)

    def test_post_job_loss_remains_recoverable(self):
        approved = self.approval(); self.runtime.fail_after_job = True
        first = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.assertEqual(first['dispatch']['status'], 'reconciliation_required')
        self.runtime.fail_after_job = False
        again = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.assertTrue(again['dispatch']['replayed']); self.assertEqual(self.runtime.submissions, 1)

    def test_journal_without_job_is_not_resubmitted(self):
        approved = self.approval(); run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.runtime.jobs.clear()
        again = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.assertEqual(again['dispatch']['status'], 'reconciliation_required'); self.assertFalse(again['dispatch']['dispatch_attempted'])
        self.assertEqual(self.runtime.submissions, 1)

    def test_unknown_dispatch_exception_never_claims_not_attempted(self):
        approved = self.approval()
        with patch('studio_workflow.execution.run_ticket', side_effect=OSError('unknown phase')):
            result = run_saved(self.runtime, self.store, self.value['request_id'], approved)
        self.assertEqual(result['dispatch']['status'], 'reconciliation_required')
        self.assertIsNone(result['dispatch']['dispatch_attempted']); self.assertNotIn('generation_submitted', result)

    def test_copied_store_workspace_refuses_before_execution(self):
        approved = self.approval()
        # Keep reading original checked record but change the runtime store identity.
        stored = self.store.get(self.value['request_id'])
        self.runtime.assets.database = self.runtime.root / 'different.sqlite'
        with patch.object(self.store, 'get', return_value=stored), patch('studio_workflow.execution.run_ticket') as run:
            with self.assertRaisesRegex(ValueError, 'workspace changed'):
                run_saved(self.runtime, self.store, self.value['request_id'], approved)
            run.assert_not_called()

    def test_get_run_route_is_inert_and_query_rejected(self):
        approved = self.approval()
        with patch('studio_workflow.run_http.store', return_value=self.store):
            with self.assertRaises(DocumentError): route(self.runtime, PREFIX + '/prepare-first/run')
            with self.assertRaises(ValueError): route(self.runtime, PREFIX + '/prepare-first/run?x=1', approved)
            self.assertEqual(route(self.runtime, PREFIX + '/prepare-first/review')['source']['request_id'], 'prepare-first')
        self.assertEqual(self.runtime.submissions, 0)

    def test_http_size_failure_after_dispatch_does_not_claim_false(self):
        class Base:
            def _json(self, code, value): return code, value
        handler = object.__new__(extend_handler(Base)); handler.studio = self.runtime; handler.path = PREFIX + '/prepare-first/run'
        with patch('studio_workflow.run_http.route', return_value={'dispatch': {'job': {'id': 'x'}}}), \
             patch('studio_workflow.run_http.canonical', return_value=b'x'*(2*1024*1024+1)):
            code, result = handler._run_record_reply({'approved': True})
        self.assertEqual(code, 400); self.assertIsNone(result['dispatch_attempted']); self.assertNotIn('generation_submitted', result)


class SavedDispatchIntegrationTests(unittest.TestCase):
    def test_real_handler_hash_approval_and_retained_queue(self):
        from test_workflow_document_runs_integration import DocumentRunIntegrationTests
        fixture = DocumentRunIntegrationTests(); fixture.setUp()
        try:
            status, record = fixture.request(PREFIX, fixture.value); self.assertEqual(status, 200, record)
            path = PREFIX + '/prepared-run'
            status, packet = fixture.request(path + '/review'); self.assertEqual(status, 200, packet)
            body = {'approved': True, **{k: packet['source'][k] for k in ('record_sha256', 'ticket_sha256')}}
            self.assertEqual(atomic_json_post(fixture.http.server_port, path + '/run', canonical(body), origin='https://foreign.invalid')[0], 403)
            self.assertEqual(fixture.request(path + '/run', {**body, 'record_sha256': 'a'*64})[0], 409)
            self.assertFalse(fixture.studio.jobs)
            first = fixture.request(path + '/run', body); self.assertEqual(first[0], 200, first)
            second = fixture.request(path + '/run', body); self.assertEqual(second[0], 200, second)
            self.assertTrue(second[1]['dispatch']['replayed']); self.assertEqual(fixture.studio.queue.qsize(), 1)
            self.assertEqual(fixture.request(path + '/observe')[1]['observation']['state'], 'observed')
        finally: fixture.doCleanups()

class SavedDispatchClientTests(RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.result = self.prepare(); self.calls = []
        from studio_workflow.run_client import SavedRuns
        def request(path, value=None):
            self.calls.append((path, value))
            with patch('studio_workflow.run_http.store', return_value=self.store):
                return route(self.runtime, path, value)
        self.client = SavedRuns(request)

    def test_client_review_and_run_keep_exact_ticket(self):
        packet = self.client.review('prepare-first'); source = packet['source']
        self.assertEqual(len(self.calls), 1); self.assertEqual(self.runtime.submissions, 0)
        self.client.run('prepare-first', record_sha256=source['record_sha256'], ticket_sha256=source['ticket_sha256'], approved=True)
        self.assertEqual(self.runtime.submissions, 1)

    def test_client_refuses_without_approval_and_mismatched_reply(self):
        source = review_saved(self.store, 'prepare-first')['source']
        with self.assertRaises(ValueError):
            self.client.run('prepare-first', record_sha256=source['record_sha256'], ticket_sha256=source['ticket_sha256'])
        self.assertEqual(self.calls, [])
        with patch.object(self.client, '_call', return_value={'source': {**source, 'request_id': 'wrong'}, 'dispatch': {}}):
            with self.assertRaises(ValueError):
                self.client.run('prepare-first', record_sha256=source['record_sha256'], ticket_sha256=source['ticket_sha256'], approved=True)

    def test_agent_permission_and_unknown_outcome(self):
        from studio_workflow.agent_bridge import AgentBridge
        from types import SimpleNamespace
        source = review_saved(self.store, 'prepare-first')['source']
        args = {k: source[k] for k in ('request_id', 'record_sha256', 'ticket_sha256')}
        for mode in ('read', 'author'):
            bridge = AgentBridge(SimpleNamespace(request=self.client.request), mode)
            self.assertFalse(bridge.invoke('saved_run_execute', args)['ok'])
        self.assertEqual(self.calls, [])
        bridge = AgentBridge(SimpleNamespace(request=self.client.request), 'execute')
        with patch('studio_workflow.execution.run_ticket', side_effect=OSError('lost')):
            result = bridge.invoke('saved_run_execute', args)
        self.assertEqual(result['error']['code'], 'reconciliation_required')
        self.assertEqual(result['context']['record_sha256'], args['record_sha256'])

    def test_cli_approval_and_reconciliation_exit_code(self):
        from contextlib import redirect_stdout
        from studio_workflow.__main__ import main
        from types import SimpleNamespace
        import io
        source = review_saved(self.store, 'prepare-first')['source']
        argv = ['runs', 'run', 'prepare-first', '--record-sha256', source['record_sha256'], '--ticket-sha256', source['ticket_sha256']]
        with patch('studio_workflow.run_cli.WorkflowClient', return_value=SimpleNamespace(saved_runs=self.client)), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(argv), 3)
            self.assertEqual(self.runtime.submissions, 0)
            with patch('studio_workflow.execution.run_ticket', side_effect=OSError('lost')):
                self.assertEqual(main(argv + ['--approve']), 3)
        self.assertNotIn('"dispatch_attempted": false', out.getvalue().lower())
