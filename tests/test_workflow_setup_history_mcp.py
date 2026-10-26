"""Reviewed-setup MCP reads share the typed client and real SQLite history owner."""
import asyncio
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import test_reviewed_setup_history_clients as client_fixture
import test_reviewed_setup_history_edges as http_fixture
from studio_workflow.agent_bridge import AgentBridge, OUTPUT_SCHEMA
from studio_workflow.client import Client
from studio_workflow.core import canonical, digest
from studio_workflow.mcp_server import build_server
from studio_workflow.setup_draft_client import SetupDraftClient
from studio_workflow.setup_drafts import PREFIX
from studio_workflow.setup_history import FLAGS, MAX_READ_BYTES


READS = ('setup_draft_history', 'setup_draft_compare', 'setup_draft_export_revision')
HAS_MCP = importlib.util.find_spec('mcp') is not None


class HistoryOpener:
    """Replace only the socket; Client framing and the SQLite HTTP route stay real."""
    def __init__(self, transport):
        self.transport = transport; self.calls = []; self.streams = []
        self.transform = lambda value: value; self.failure = None; self.headers = None
        self.raw_transform = lambda raw: raw

    def open(self, request, timeout):
        self.calls.append((request.get_method(), request.selector, request.data, timeout))
        if self.failure is not None: raise self.failure
        value = self.transport.request(request.selector, json.loads(request.data) if request.data is not None else None)
        raw = self.raw_transform(json.dumps(self.transform(value), allow_nan=False).encode())
        response = io.BytesIO(raw)
        response.headers = self.headers if self.headers is not None else {'Content-Length': str(len(raw))}
        self.streams.append(response)
        return response


class HistoryFixture:
    store = client_fixture.ReviewedSetupHistoryClientTests.store
    command = client_fixture.ReviewedSetupHistoryClientTests.command
    create = client_fixture.ReviewedSetupHistoryClientTests.create
    dump = client_fixture.ReviewedSetupHistoryClientTests.dump

    def setUp(self):
        client_fixture.ReviewedSetupHistoryClientTests.setUp(self)
        self.http_client = Client(timeout=7)
        self.opener = HistoryOpener(self.transport); self.http_client.opener = self.opener
        self.bridge = AgentBridge(self.http_client)

    def arguments(self, name, **extra):
        values = {'draft_id': self.key, 'workspace_id': self.scope}
        if name == READS[1]: values.update(left=1, right=3)
        if name == READS[2]: values['revision'] = 1
        return dict(values, **extra)

    def result_data(self, result):
        self.assertTrue(result['ok'], result)
        value = json.loads(result['data_json'])
        self.assertEqual(result['data_sha256'], digest(value))
        self.assertLessEqual(len(result['data_json'].encode()), MAX_READ_BYTES)
        for key, expected in FLAGS.items(): self.assertIs(value[key], expected)
        return value

    def assert_read_only(self, before):
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.s.upload_count, 0)
        self.assertTrue(all(method == 'GET' and body is None and timeout == 7
                            for method, _, body, timeout in self.opener.calls), self.opener.calls)
        self.assertTrue(all(stream.closed for stream in self.opener.streams))


class SetupHistoryBridgeTests(HistoryFixture, unittest.TestCase):
    def test_discovery_exposes_three_observers_in_every_mode_without_io(self):
        before = self.dump()
        for mode in ('read', 'author', 'execute'):
            definitions = AgentBridge(self.http_client, mode).definitions()
            for name in READS:
                self.assertIn(name, list(definitions))
                self.assertEqual(definitions[name]['mode'], 'read')
                self.assertFalse(definitions[name]['mutating'])
                self.assertFalse(definitions[name]['inputSchema']['additionalProperties'])
        self.assertEqual(self.opener.calls, [])
        self.assert_read_only(before)

    def test_one_hundred_sqlite_revisions_require_explicit_bounded_continuations(self):
        for revision in range(4, 101):
            draft = copy.deepcopy(self.before); draft['recipe']['controls']['positive'] = 'Revision ' + str(revision)
            self.command('replace', request_id='history-' + str(revision), draft_id=self.key,
                         expected_revision=revision-1, draft=draft)
        before = self.dump(); arguments = self.arguments(READS[0], limit=20); seen = []
        for call in range(1, 6):
            page = self.result_data(self.bridge.invoke(READS[0], arguments))
            self.assertEqual(len(self.opener.calls), call, 'One tool invocation must perform exactly one read')
            self.assertEqual(page['head_revision'], 100)
            self.assertEqual(len(page['revisions']), 20)
            self.assertTrue(all('draft' not in row and 'record_json' not in row for row in page['revisions']))
            seen.extend(row['revision'] for row in page['revisions'])
            if call < 5:
                arguments = self.arguments(READS[0], limit=20, before_revision=page['next_before_revision'],
                                           expected_head=page['head_revision'])
            else: self.assertIsNone(page['next_before_revision'])
        self.assertEqual(seen, list(range(100, 0, -1)))
        self.assert_read_only(before)

    def test_compare_and_export_match_sdk_and_preserve_declared_seed_text(self):
        draft = copy.deepcopy(self.before)
        draft['recipe']['controls'].update(positive='Changed 界', seed='18446744073709551615')
        self.command('replace', draft_id=self.key, expected_revision=3, request_id='seed-revision', draft=draft)
        before = self.dump(); sdk = SetupDraftClient(self.http_client.request)
        comparison = self.result_data(self.bridge.invoke(READS[1], self.arguments(READS[1], right=4, expected_head=4)))
        self.assertEqual(comparison, sdk.compare(self.key, 1, 4, workspace_id=self.scope, expected_head=4))
        self.assertTrue(next(section for section in comparison['sections'] if section['section'] == 'wording')['changed'])
        exported = self.result_data(self.bridge.invoke(READS[2], self.arguments(READS[2], revision=4, expected_head=4)))
        self.assertEqual(exported, sdk.export_revision(self.key, 4, workspace_id=self.scope, expected_head=4))
        self.assertEqual(exported['export']['draft']['recipe']['controls']['seed'], '18446744073709551615')
        self.assertEqual(exported['export']['draft'], draft)
        self.assertEqual(exported['export']['authority'], 'none')
        self.assertEqual(exported['export_json'].encode(), canonical(exported['export']))
        self.assertEqual(exported['export_sha256'], digest(exported['export']))
        self.assert_read_only(before)

    def test_raw_transport_gets_exact_workspace_revision_and_expected_head(self):
        calls = ((READS[0], {'limit': 1, 'before_revision': 3, 'expected_head': 3}, 'history',
                  {'limit': '1', 'before_revision': '3'}),
                 (READS[1], {'expected_head': 3}, 'compare', {'left': '1', 'right': '3'}),
                 (READS[2], {'expected_head': 3}, 'export', {'revision': '1'}))
        for name, values, action, query in calls:
            arguments = self.arguments(name, **values)
            result = self.bridge.invoke(name, arguments); self.result_data(result)
            self.assertEqual(result['context'], arguments)
            method, path, body, timeout = self.opener.calls[-1]
            self.assertEqual((method, body, timeout), ('GET', None, 7))
            parsed = urlsplit(path); self.assertEqual(parsed.path, PREFIX + '/' + self.key + '/' + action)
            self.assertEqual(parse_qs(parsed.query), {key: [value] for key, value in
                dict(workspace_id=self.scope, expected_head='3', **query).items()})

    def test_invalid_inputs_and_unguarded_continuations_refuse_before_transport(self):
        common = ({'draft_id': '../escape'}, {'draft_id': 'requests'}, {'workspace_id': 'F'*32},
                  {'workspace_id': 'f'*31}, {'workspace_id': 'f'*32+'&limit=1'}, {'workspace_id': None},
                  {'expected_head': True}, {'expected_head': 257}, {'unexpected': True})
        for name in READS:
            extras = (common + ({'limit': 0}, {'limit': 21}, {'limit': True}, {'before_revision': 2},
                                {'before_revision': 4, 'expected_head': 3}) if name == READS[0] else
                      common + ({'left': True}, {'right': 0}, {'right': 257}) if name == READS[1] else
                      common + ({'revision': 0}, {'revision': 257}, {'revision': True}))
            candidates = [self.arguments(name, **extra) for extra in extras]
            for key in ('draft_id', 'workspace_id'):
                value = self.arguments(name); value.pop(key); candidates.append(value)
            for arguments in candidates:
                with self.subTest(name=name, arguments=arguments):
                    result = self.bridge.invoke(name, arguments)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['error']['code'], 'invalid_arguments')
                    self.assertNotIn('recovery', result['error'])
        self.assertEqual(self.opener.calls, [])

    def test_stale_head_and_foreign_workspace_preserve_refusal_and_requested_context(self):
        before = self.dump()
        for name in READS:
            for change, code in (({'expected_head': 2}, 'setup_history_head_changed'),
                                 ({'workspace_id': 'f'*32}, 'asset_workspace_conflict')):
                arguments = self.arguments(name, **change); count = len(self.opener.calls)
                result = self.bridge.invoke(name, arguments)
                self.assertFalse(result['ok']); self.assertEqual(result.get('context'), arguments)
                self.assertEqual(result['error']['code'], code); self.assertEqual(result['error']['http_status'], 409)
                self.assertNotIn('recovery', result['error'])
                self.assertEqual(len(self.opener.calls), count+1)
                self.assertEqual(json.loads(result['data_json'])['code'], code)
        self.assert_read_only(before)

    def test_wrong_identity_authority_or_oversized_reply_is_not_success(self):
        before = self.dump()
        for name in READS:
            for change in ({'workspace_id': 'e'*32}, {'draft_id': 'other'}, {'head_revision': 2},
                           {'generation_submitted': True}, {'staging_performed': True},
                           {'padding': '界' * (MAX_READ_BYTES // 6)}):
                self.opener.transform = lambda value, change=change: dict(value, **change)
                count = len(self.opener.calls)
                result = self.bridge.invoke(name, self.arguments(name, expected_head=3))
                self.assertFalse(result['ok'], (name, change.keys()))
                self.assertEqual(result['error']['code'], 'request_failed')
                self.assertEqual(json.loads(result['data_json']), {})
                self.assertEqual(len(self.opener.calls), count+1)
                self.assertNotIn('recovery', result['error'])
        self.assert_read_only(before)

    def test_rehashed_export_with_wrong_nested_draft_digest_refuses(self):
        def corrupt(value):
            value['export']['draft']['recipe']['controls']['positive'] = 'Unapproved replacement'
            raw = canonical(value['export'])
            value.update(export_json=raw.decode(), export_sha256=digest(value['export']), export_bytes=len(raw))
            return value
        before = self.dump(); self.opener.transform = corrupt
        result = self.bridge.invoke(READS[2], self.arguments(READS[2]))
        self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], 'request_failed')
        self.assertEqual(len(self.opener.calls), 1)
        self.assert_read_only(before)

    def test_ambiguous_or_oversized_raw_history_replies_refuse_through_the_shared_client(self):
        before = self.dump()
        for transform in (lambda raw: raw+b' '*MAX_READ_BYTES,
                          lambda raw: raw.replace(b'"head_revision": 3', b'"head_revision": 2, "head_revision": 3')):
            self.opener.raw_transform = transform
            for name in READS:
                count = len(self.opener.calls); result = self.bridge.invoke(name, self.arguments(name))
                self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], 'request_failed')
                self.assertNotIn('recovery', result['error']); self.assertEqual(len(self.opener.calls), count+1)
        self.assert_read_only(before)

    def test_incomplete_history_is_not_presented_as_a_successful_empty_page(self):
        before = self.dump()
        self.opener.transform = lambda value: dict(value, revisions=[], next_before_revision=None)
        result = self.bridge.invoke(READS[0], self.arguments(READS[0]))
        self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], 'request_failed')
        self.assertEqual(json.loads(result['data_json']), {})
        self.assertEqual(len(self.opener.calls), 1); self.assert_read_only(before)

    def test_lost_or_truncated_reads_never_become_unknown_writes_or_retry(self):
        before = self.dump()
        for failure in (TimeoutError('response lost'), OSError('transport unavailable')):
            self.opener.failure = failure
            for name in READS:
                count = len(self.opener.calls); result = self.bridge.invoke(name, self.arguments(name))
                self.assertEqual(result['error']['code'], 'request_failed')
                self.assertNotIn('recovery', result['error']); self.assertEqual(len(self.opener.calls), count+1)
        self.opener.failure = None; self.opener.headers = {'Content-Length': str(MAX_READ_BYTES)}
        result = self.bridge.invoke(READS[0], self.arguments(READS[0]))
        self.assertEqual(result['error']['code'], 'request_failed')
        self.assertNotIn('recovery', result['error'])
        self.assert_read_only(before)

    def test_error_stream_is_bounded_closed_and_not_retried(self):
        for raw, headers, code in ((b'{"code":"setup_history_corrupt","error":"Corrupt"}', {}, 'setup_history_corrupt'),
                                   (b'{}', {'Content-Length': '999999'}, 'http_error'),
                                   (b'{}', {'Content-Length': '100'}, 'http_error')):
            stream = io.BytesIO(raw)
            self.opener.failure = HTTPError('http://127.0.0.1', 503, 'Refused', headers, stream)
            count = len(self.opener.calls); result = self.bridge.invoke(READS[0], self.arguments(READS[0]))
            self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], code)
            self.assertEqual(result['error']['http_status'], 503)
            self.assertNotIn('recovery', result['error'])
            self.assertTrue(stream.closed); self.assertEqual(len(self.opener.calls), count+1)

    def test_malformed_get_error_does_not_direct_the_caller_to_write_recovery(self):
        before = self.dump()
        for name in READS:
            with self.subTest(name=name):
                stream = io.BytesIO(b'not JSON')
                self.opener.failure = HTTPError('http://127.0.0.1', 503, 'Refused', {}, stream)
                count = len(self.opener.calls); result = self.bridge.invoke(name, self.arguments(name))
                self.assertFalse(result['ok']); self.assertEqual(result['error']['http_status'], 503)
                self.assertEqual(result['error']['code'], 'http_error')
                self.assertNotIn('receipt', result['error']['message'].lower())
                self.assertNotIn('recover', result['error']['message'].lower())
                self.assertNotIn('recovery', result['error'])
                self.assertTrue(stream.closed); self.assertEqual(len(self.opener.calls), count+1)
        self.assert_read_only(before)

    def test_malformed_post_error_still_retains_original_command_receipt_guidance(self):
        before = self.dump(); stream = io.BytesIO(b'not JSON')
        self.opener.failure = HTTPError('http://127.0.0.1', 503, 'Refused', {}, stream)
        command = {'action': 'create', 'workspace_id': self.scope, 'request_id': 'retained-command', 'draft': self.before}
        result = AgentBridge(self.http_client, 'author').invoke('setup_draft_command', {'command_json': json.dumps(command)})
        self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], 'outcome_unknown')
        self.assertIn('Unverified setup error; inspect the original request receipt', result['error']['message'])
        self.assertEqual(result['context']['request_id'], 'retained-command')
        self.assertIn('recovery', result['error']); self.assertEqual(len(self.opener.calls), 1)
        self.assertEqual(self.opener.calls[0][0], 'POST'); self.assertTrue(stream.closed)
        self.assertEqual(self.dump(), before); self.assertEqual(self.s.upload_count, 0)

    def test_corrupt_retained_record_is_a_read_refusal_and_remains_untouched(self):
        with self.s.assets.connection() as db: db.execute("UPDATE setup_versions_v1 SET record='{}'")
        before = self.dump()
        for name in READS:
            result = self.bridge.invoke(name, self.arguments(name))
            self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], 'setup_history_corrupt')
            self.assertEqual(result['error']['http_status'], 503)
            self.assertNotIn('recovery', result['error'])
        self.assertEqual(len(self.opener.calls), 3)
        self.assert_read_only(before)


@unittest.skipUnless(HAS_MCP, 'Install optional workflow-mcp requirements for protocol tests')
class SetupHistoryMCPTests(HistoryFixture, unittest.IsolatedAsyncioTestCase):
    def protocol_data(self, result):
        self.assertFalse(result.isError, result)
        self.assertEqual(json.loads(result.content[0].text), result.structuredContent)
        return self.result_data(result.structuredContent)

    async def test_official_sdk_schemas_annotations_and_invalid_reads_are_inert(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        before = self.dump()
        async with create_connected_server_and_client_session(build_server(self.bridge), raise_exceptions=True) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            for name in READS:
                self.assertIn(name, list(tools))
                self.assertTrue(tools[name].annotations.readOnlyHint)
                self.assertTrue(tools[name].annotations.idempotentHint)
                self.assertFalse(tools[name].annotations.destructiveHint)
                self.assertFalse(tools[name].annotations.openWorldHint)
                self.assertEqual(tools[name].outputSchema, OUTPUT_SCHEMA)
            self.assertNotIn('setup_draft_command', tools)
            for name, arguments in ((READS[0], self.arguments(READS[0], limit=21)),
                                    (READS[0], self.arguments(READS[0], before_revision=2)),
                                    (READS[1], self.arguments(READS[1], left=True)),
                                    (READS[2], self.arguments(READS[2], revision=257)),
                                    (READS[2], self.arguments(READS[2], workspace_id='foreign'))):
                self.assertTrue((await session.call_tool(name, arguments)).isError)
            self.assertEqual(self.opener.calls, [])
            for name in READS:
                self.protocol_data(await session.call_tool(name, self.arguments(name)))
            self.assertEqual(len(self.opener.calls), 3)
        self.assert_read_only(before)

    async def test_stdio_uses_real_http_sqlite_and_preserves_changed_head_refusal(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        f = http_fixture.HistoryHTTPTests(); self.addCleanup(f.doCleanups); f.setUp()
        requests = []; base = f.http.RequestHandlerClass
        class EphemeralOrigin(base):
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self):
                return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:' + str(self.server.server_port)
            def do_GET(self): requests.append(('GET', self.path)); return super().do_GET()
            def do_POST(self): requests.append(('POST', self.path)); return super().do_POST()
        f.http.RequestHandlerClass = EphemeralOrigin
        def dump():
            with f.s.assets.connection() as db: return list(db.iterdump())
        before = dump(); root = Path(__file__).resolve().parents[1]
        common = {'draft_id': f.key, 'workspace_id': f.scope}
        params = StdioServerParameters(command=sys.executable,
            args=[str(root / 'scripts/workflow-mcp.py'), '--mode', 'read', '--url',
                  'http://127.0.0.1:' + str(f.http.server_port), '--http-timeout', '5'], cwd=f.temp.name)
        async with asyncio.timeout(35):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize(); await session.list_tools(); self.assertEqual(requests, [])
                    first = self.protocol_data(await session.call_tool(READS[0], dict(common, limit=2)))
                    self.assertEqual([row['revision'] for row in first['revisions']], [3, 2])
                    continuation = dict(common, limit=2, before_revision=first['next_before_revision'], expected_head=3)
                    last = self.protocol_data(await session.call_tool(READS[0], continuation))
                    self.assertEqual([row['revision'] for row in last['revisions']], [1]); self.assertIsNone(last['next_before_revision'])
                    comparison = self.protocol_data(await session.call_tool(READS[1], dict(common, left=1, right=3, expected_head=3)))
                    self.assertEqual((comparison['left_revision'], comparison['right_revision']), (1, 3))
                    exported = self.protocol_data(await session.call_tool(READS[2], dict(common, revision=1, expected_head=3)))
                    self.assertEqual(exported['export']['draft'], f.before)
                    self.assertEqual(len(requests), 4); self.assertEqual(dump(), before)
                    f.command('replace', draft_id=f.key, expected_revision=3, request_id='external-head', draft=f.before)
                    after = dump(); refused = await session.call_tool(READS[0], continuation)
                    self.assertTrue(refused.isError)
                    self.assertEqual(refused.structuredContent['error']['code'], 'setup_history_head_changed')
                    self.assertEqual(refused.structuredContent['error']['http_status'], 409)
                    self.assertEqual(refused.structuredContent['context'], continuation)
                    self.assertNotIn('recovery', refused.structuredContent['error'])
                    foreign = await session.call_tool(READS[2], dict(common, workspace_id='f'*32, revision=1))
                    self.assertTrue(foreign.isError)
                    self.assertEqual(foreign.structuredContent['error']['code'], 'asset_workspace_conflict')
                    self.assertEqual(len(requests), 6)
                    self.assertTrue((await session.call_tool('setup_draft_command', {})).isError)
                    self.assertEqual(len(requests), 6); self.assertEqual(dump(), after)
        self.assertEqual(f.s.upload_count, 0)
        self.assertTrue(all(method == 'GET' and path.startswith(PREFIX + '/' + f.key + '/') for method, path in requests), requests)


if __name__ == '__main__': unittest.main()
