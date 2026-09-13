"""SDK/CLI/MCP parity on real SQLite; no generation endpoint in this fixture."""
import asyncio
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

import test_workflow_document_runs as fixtures
from studio_workflow.__main__ import main
from studio_workflow.agent_bridge import AgentBridge, TOOLS
from studio_workflow.client import Client, ClientError
from studio_workflow.core import canonical, digest
from studio_workflow.execution import run_ticket
from studio_workflow.run_client import SavedRuns, record_result
from studio_workflow.run_http import PREFIX, route, extend_handler
from studio_workflow.sdk import WorkflowClient


class RouteClient:
    def __init__(self, studio): self.studio = studio; self.calls = []
    def request(self, path, body=None):
        self.calls.append((path, body))
        try: return route(self.studio, path, body)
        except fixtures.DocumentError as exc: raise ClientError(exc.status, exc.result()) from exc


class ClientTests(fixtures.RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp(); self.transport = RouteClient(self.runtime); self.runs = SavedRuns(self.transport.request)
    def call_prepare(self): return self.runs.prepare(self.source['id'], expected_revision=1, preset_id='example', request_id='prepare-first')
    def test_prepare_get_list_source_and_observe(self):
        result = self.call_prepare(); report = result['record']['report']
        self.assertEqual(report['ticket']['recipe']['controls']['seed'], 2**63-1)
        self.assertEqual(self.runs.get('prepare-first')['record'], result['record'])
        self.assertEqual(self.runs.by_job(report['job_id'])['record'], result['record'])
        self.assertEqual(len(self.runs.list(self.source['id'], limit=1)['runs']), 1)
        self.assertEqual(self.runs.observe('prepare-first')['observation']['state'], 'not_observed')
        self.assertEqual(self.runtime.submissions, 0)
    def test_sdk_namespace_uses_existing_transport(self):
        client = WorkflowClient(); client.request = self.transport.request
        result = client.saved_runs.prepare(self.source['id'], expected_revision=1, preset_id='example', request_id='prepare-first')
        self.assertEqual(result['record']['request'], self.value)
    def test_invalid_ids_revisions_limits_have_no_calls(self):
        for call in (lambda: self.runs.get('../escape'), lambda: self.runs.get('..'),
                     lambda: self.runs.prepare(self.source['id'], expected_revision=True, preset_id='example', request_id='x'),
                     lambda: self.runs.prepare(self.source['id'], expected_revision=1025, preset_id='example', request_id='x'),
                     lambda: self.runs.list(self.source['id'], before=False), lambda: self.runs.list(self.source['id'], limit=101)):
            with self.assertRaises(ValueError): call()
        self.assertEqual(self.transport.calls, [])
    def test_mismatched_response_rejected_before_ticket_export(self):
        result = self.call_prepare()
        with self.assertRaises(ValueError): record_result(result, {'request_id': 'other'})
        with self.assertRaises(ValueError): record_result(result, job_id='other')
        result['record']['report']['ticket']['recipe']['controls']['seed'] = 1
        with self.assertRaises(ValueError): record_result(result)
    def test_malformed_pages_observations_and_records_are_rejected(self):
        for result, operation in ((None, lambda x: x.get('p')), ({'record': None}, lambda x: x.get('p')),
              ({'document_id': self.source['id'], 'runs': [], 'next_before': 1}, lambda x: x.list(self.source['id'])),
              ({'request_id': 'p', 'observation': {'state': 'observed', 'job': None}}, lambda x: x.observe('p'))):
            with self.subTest(result=result), self.assertRaises(ValueError): operation(SavedRuns(lambda *args: result))
    def test_http_error_mapping_does_not_change_legacy_client(self):
        def failed(*args, **kwargs): raise HTTPError('http://127.0.0.1', 409, 'Conflict', {}, io.BytesIO(b'{"code":"revision_conflict","error":"changed"}'))
        with self.assertRaises(ClientError) as caught: SavedRuns(failed).get('p')
        self.assertEqual(caught.exception.status, 409); self.assertEqual(caught.exception.code, 'revision_conflict')
        base = Client(); base.opener.open = failed
        with self.assertRaises(HTTPError) as caught: base.request('/api/workflow-studio/compile', {})
        caught.exception.close()
    def test_real_loopback_sdk_roundtrip(self):
        fixtures.RunHTTPTests.start_http(self)
        def canonical_request(url, *args, **kwargs):
            kwargs['headers'] = {**kwargs.get('headers', {}), 'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191'}
            return Request(url, *args, **kwargs)
        with patch('studio_workflow.client.Request', side_effect=canonical_request):
            client = WorkflowClient(self.url)
            first = client.saved_runs.prepare(self.source['id'], expected_revision=1, preset_id='example', request_id='prepare-first')
            self.edit()
            self.assertEqual(client.saved_runs.get('prepare-first')['record'], first['record'])
            with self.assertRaises(ClientError) as caught:
                client.saved_runs.prepare(self.source['id'], expected_revision=1, preset_id='example', request_id='stale')
            self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.runtime.submissions, 0)


class CLITests(fixtures.RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp(); self.transport = RouteClient(self.runtime)
        transport = patch.object(Client, 'request', side_effect=self.transport.request)
        transport.start(); self.addCleanup(transport.stop)
    def cli(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output): code = main(['runs', *arguments])
        return code, json.loads(output.getvalue())
    def prep_args(self): return ['prepare', self.source['id'], '--expected-revision', '1', '--preset', 'example', '--request-id', 'prepare-first']
    def test_prepare_export_get_replay_and_no_automatic_run(self):
        file = self.runtime.root / 'ticket.json'
        code, first = self.cli(*self.prep_args(), '--ticket-out', str(file)); self.assertEqual(code, 0, first)
        ticket = json.loads(file.read_bytes()); self.assertEqual(ticket, first['record']['report']['ticket'])
        self.assertEqual(ticket['recipe']['controls']['seed'], 2**63-1)
        self.edit(); code, repeated = self.cli(*self.prep_args()); self.assertEqual(code, 0)
        self.assertTrue(repeated['replayed']); self.assertEqual(repeated['record'], first['record'])
        recovered = self.runtime.root / 'recovered.json'
        code, result = self.cli('get', 'prepare-first', '--ticket-out', str(recovered)); self.assertEqual(code, 0)
        self.assertEqual(file.read_bytes(), recovered.read_bytes()); self.assertEqual(self.runtime.submissions, 0)
    def test_existing_output_and_missing_directory_block_before_http(self):
        file = self.runtime.root / 'ticket.json'; file.write_text('keep')
        for output in (file, self.runtime.root / 'missing' / 'ticket.json'):
            code, _ = self.cli(*self.prep_args(), '--ticket-out', str(output)); self.assertEqual(code, 2)
        self.assertEqual(file.read_text(), 'keep'); self.assertEqual(self.transport.calls, [])
    def test_export_race_retains_response_without_overwriting_other_file(self):
        file = self.runtime.root / 'race.json'; original = self.transport.request
        def race(*args):
            result = original(*args); file.write_text('someone else'); return result
        with patch.object(Client, 'request', side_effect=race):
            code, result = self.cli(*self.prep_args(), '--ticket-out', str(file))
        self.assertEqual(code, 2); self.assertIn('result', result); self.assertEqual(file.read_text(), 'someone else')
        self.assertEqual(len(self.store.list(self.source['id'])['runs']), 1)
    def test_conflict_exit_and_original_request_context(self):
        self.edit(); code, result = self.cli(*self.prep_args())
        self.assertEqual(code, 6); self.assertEqual(result['context']['request_id'], 'prepare-first')
        self.assertEqual(result['code'], 'revision_conflict'); self.assertEqual(self.runtime.submissions, 0)
    def test_observation_uncertainty_and_terminal_job_exit_codes(self):
        report = self.prepare()['record']['report']
        code, result = self.cli('observe', 'prepare-first'); self.assertEqual(code, 3)
        self.assertEqual(result['observation']['state'], 'not_observed')
        run_ticket(self.runtime, report['ticket'], True)
        self.assertEqual(self.cli('observe', 'prepare-first')[0], 0)
        self.runtime.jobs[report['job_id']]['status'] = 'uncertain'; self.assertEqual(self.cli('observe', 'prepare-first')[0], 3)
        self.runtime.jobs[report['job_id']]['status'] = 'failed'; self.assertEqual(self.cli('observe', 'prepare-first')[0], 5)
        self.runtime.jobs[report['job_id']]['status'] = 'completed'; self.assertEqual(self.cli('observe', 'prepare-first')[0], 0)
        self.assertEqual(self.runtime.submissions, 1)
    def test_list_source_and_lost_reply_are_not_retried(self):
        _, first = self.cli(*self.prep_args()); job_id = first['record']['report']['job_id']
        self.assertEqual(self.cli('by-job', job_id)[1]['record'], first['record'])
        self.assertEqual(len(self.cli('list', self.source['id'], '--limit', '1')[1]['runs']), 1)
        original = self.transport.request
        def lose(*args): original(*args); raise TimeoutError('response lost')
        self.transport.calls.clear()
        with patch.object(Client, 'request', side_effect=lose): code, error = self.cli(*self.prep_args())
        self.assertEqual(code, 2); self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(error['context']['request_id'], 'prepare-first')


class AgentTests(fixtures.RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp(); self.transport = RouteClient(self.runtime)
    def test_permissions_apply_to_discovery_and_calls(self):
        for mode in ('read', 'author'):
            bridge = AgentBridge(self.transport, mode)
            self.assertNotIn('saved_run_prepare', bridge.definitions())
            self.assertIn('saved_run_get', bridge.definitions())
            self.assertFalse(bridge.invoke('saved_run_prepare', self.value)['ok'])
        self.assertEqual(self.transport.calls, [])
        self.assertTrue(TOOLS['saved_run_prepare']['mutating'])
        self.assertFalse(TOOLS['saved_run_get']['mutating'])
    def test_all_tools_exact_response_and_offline_recovery(self):
        bridge = AgentBridge(self.transport, 'execute')
        result = bridge.invoke('saved_run_prepare', self.value); self.assertTrue(result['ok'], result)
        prepared = json.loads(result['data_json']); self.assertEqual(result['data_sha256'], digest(prepared))
        self.assertEqual(prepared['record']['report']['ticket']['recipe']['controls']['seed'], 2**63-1)
        self.edit()
        with patch.object(self.runtime, 'node_info', side_effect=AssertionError('Offline read must not discover nodes')):
            read = AgentBridge(self.transport)
            for name, args in (('saved_run_get', {'request_id': 'prepare-first'}),
                               ('saved_run_list', {'document_id': self.source['id'], 'limit': 1}),
                               ('saved_run_source', {'job_id': prepared['record']['report']['job_id']}),
                               ('saved_run_observe', {'request_id': 'prepare-first'})):
                value = read.invoke(name, args); self.assertTrue(value['ok'], value)
        self.assertEqual(self.runtime.submissions, 0)
    def test_bad_arguments_and_malformed_reply_retain_context(self):
        bridge = AgentBridge(self.transport, 'execute')
        self.assertFalse(bridge.invoke('saved_run_prepare', {**self.value, 'expected_revision': True})['ok'])
        self.assertEqual(self.transport.calls, [])
        with patch.object(self.transport, 'request', return_value={'record': None}) as request:
            result = bridge.invoke('saved_run_prepare', self.value)
            self.assertEqual(result['error']['code'], 'outcome_unknown'); self.assertEqual(request.call_count, 1)
        self.assertEqual(result['context'], self.value)
    def test_lost_preparation_reply_then_read_recovers_original(self):
        bridge = AgentBridge(self.transport, 'execute'); original = self.transport.request
        def lose(*args): original(*args); raise TimeoutError('lost reply')
        with patch.object(self.transport, 'request', side_effect=lose):
            result = bridge.invoke('saved_run_prepare', self.value)
        self.assertEqual(result['error']['code'], 'outcome_unknown')
        self.assertEqual(len(self.transport.calls), 1)
        recovered = AgentBridge(self.transport).invoke('saved_run_get', {'request_id': 'prepare-first'})
        self.assertTrue(recovered['ok']); self.assertEqual(len(self.store.list(self.source['id'])['runs']), 1)
        self.assertEqual(self.runtime.submissions, 0)
    def test_conflict_is_machine_readable_and_not_rebased(self):
        self.edit(); result = AgentBridge(self.transport, 'execute').invoke('saved_run_prepare', self.value)
        self.assertFalse(result['ok']); self.assertEqual(result['error']['http_status'], 409)
        self.assertEqual(result['error']['code'], 'revision_conflict'); self.assertEqual(len(self.transport.calls), 1)


HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install optional workflow-mcp SDK for stdio contract')
class SavedRunStdioTests(fixtures.RunFixture, unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_http_sqlite_prepare_and_read_recovery(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:' + str(self.server.server_port)
            def _content_length(self, limit):
                size = int(self.headers['Content-Length'])
                if not 0 <= size <= limit: raise ValueError('Body limit')
                return size
            def _json(self, status, result):
                raw = canonical(result); self.send_response(status); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self): self._json(404, {'error': 'No other fixture routes'})
            def do_POST(self): self._json(404, {'error': 'No generation routes'})
        handler = extend_handler(Base); handler.studio = self.runtime
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        try:
            script = Path(__file__).resolve().parents[1] / 'scripts/workflow-mcp.py'
            url = 'http://127.0.0.1:' + str(http.server_port)
            async with asyncio.timeout(35):
                params = StdioServerParameters(command=sys.executable, args=[str(script), '--url', url, '--mode', 'execute'], cwd=self.temp.name)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = {t.name: t for t in (await session.list_tools()).tools}
                        self.assertIn('saved_run_prepare', tools); self.assertFalse(tools['saved_run_prepare'].annotations.readOnlyHint)
                        result = await session.call_tool('saved_run_prepare', self.value)
                        self.assertFalse(result.isError, result)
                        original = json.loads(result.structuredContent['data_json'])['record']
                        self.assertEqual(original['report']['ticket']['recipe']['controls']['seed'], 2**63-1)
                self.edit()
                params = StdioServerParameters(command=sys.executable, args=[str(script), '--url', url, '--mode', 'read'], cwd=self.temp.name)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.assertNotIn('saved_run_prepare', {t.name for t in (await session.list_tools()).tools})
                        result = await session.call_tool('saved_run_get', {'request_id': 'prepare-first'})
                        self.assertFalse(result.isError, result)
                        self.assertEqual(json.loads(result.structuredContent['data_json'])['record'], original)
                        observed = await session.call_tool('saved_run_observe', {'request_id': 'prepare-first'})
                        self.assertEqual(json.loads(observed.structuredContent['data_json'])['observation']['state'], 'not_observed')
            self.assertEqual(self.runtime.submissions, 0); self.assertEqual(len(self.store.list(self.source['id'])['runs']), 1)
        finally:
            http.shutdown(); http.server_close(); thread.join(5)
