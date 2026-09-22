"""Official-SDK and real stdio contracts for bounded Workspace observations.

Ordinary Studio discovery may skip the optional SDK. The dedicated Linux/Windows
MCP workflow installs its pinned version and must execute this protocol gate.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import test_asset_read_http as http_fixture
from studio_workflow.agent_bridge import AgentBridge, OUTPUT_SCHEMA
from studio_workflow.client import Client
from studio_workflow.core import digest
from studio_workflow.mcp_server import build_server

HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install optional workflow-mcp requirements for protocol tests')
class AssetMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = http_fixture.AssetReadHTTPTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        f = self.fixture; self.requests = []; requests = self.requests
        base = f.http.RequestHandlerClass
        # Only adapt the test origin to its ephemeral port. All route parsing,
        # strict bodies, response projection and SQLite reads stay production.
        class EphemeralOrigin(base):
            def _safe_host(self):
                return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self):
                return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:' + str(self.server.server_port)
            def do_GET(self):
                requests.append(('GET', self.path)); return super().do_GET()
            def do_POST(self):
                requests.append(('POST', self.path)); return super().do_POST()
        f.http.RequestHandlerClass = EphemeralOrigin
        self.url = 'http://127.0.0.1:' + str(f.http.server_port)
        self.bridge = AgentBridge(Client(self.url, timeout=5))

    def assert_result(self, result):
        self.assertFalse(result.isError, result)
        value = result.structuredContent
        self.assertTrue(value['ok'])
        self.assertEqual(json.loads(result.content[0].text), value)
        decoded = json.loads(value['data_json'])
        self.assertEqual(value['data_sha256'], digest(decoded))
        self.assertIs(decoded['observation_only'], True)
        self.assertIs(decoded['media_bytes_verified'], False)
        self.assertIs(decoded['generation_submitted'], False)
        return decoded

    def assert_no_writes(self, before):
        f = self.fixture
        self.assertEqual(f.store.snapshot(), before)
        self.assertEqual((Path(f.temp.name) / 'image.png').read_bytes(), b'original')
        with f.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0], 0)
        self.assertTrue(all(path.split('?')[0] in ('/api/assets/page', '/api/assets/selection')
                            for _, path in self.requests), self.requests)

    async def test_official_sdk_lists_read_only_tools_and_rejects_invalid_inputs_before_io(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        f = self.fixture; before = f.store.snapshot()
        async with create_connected_server_and_client_session(build_server(self.bridge), raise_exceptions=True) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            for name in ('asset_page', 'asset_selection'):
                self.assertIn(name, tools)
                self.assertTrue(tools[name].annotations.readOnlyHint)
                self.assertTrue(tools[name].annotations.idempotentHint)
                self.assertFalse(tools[name].annotations.destructiveHint)
                self.assertFalse(tools[name].annotations.openWorldHint)
                self.assertEqual(tools[name].outputSchema, OUTPUT_SCHEMA)
            self.assertNotIn('recipe_run', tools)
            self.assertEqual(self.requests, [])
            for name, args in [('asset_page', {'limit': True}),
                               ('asset_page', {'filters': {'favorite': 1}}),
                               ('asset_page', {'filters': {'unknown': True}}),
                               ('asset_selection', {'workspace_id': f.scope, 'ids': ['x', 'x']}),
                               ('asset_selection', {'ids': ['x']})]:
                result = await session.call_tool(name, args)
                self.assertTrue(result.isError, (name, args, result))
                self.assertEqual(self.requests, [])
            # Explicit null filter values are valid; null filters object is not.
            result = await session.call_tool('asset_page', {'limit': 1, 'filters': {'favorite': None, 'review': None}})
            self.assertEqual(len(self.assert_result(result)['assets']), 1)
            self.assertEqual(len(self.requests), 1)
        self.assert_no_writes(before)

    async def test_stdio_pages_selection_and_stale_conflict_retain_exact_workspace_evidence(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        f = self.fixture; before = f.store.snapshot()
        root = Path(__file__).resolve().parents[1]
        params = StdioServerParameters(command=sys.executable,
            args=[str(root / 'scripts/workflow-mcp.py'), '--mode', 'read', '--url', self.url, '--http-timeout', '5'],
            cwd=f.temp.name)
        async with asyncio.timeout(35):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize(); await session.list_tools()
                    self.assertEqual(self.requests, [])
                    first = self.assert_result(await session.call_tool('asset_page', {'workspace_id': f.scope, 'limit': 1}))
                    self.assertEqual(first['assets'][0]['id'], f.ids[2])
                    self.assertEqual(len(self.requests), 1)
                    second = self.assert_result(await session.call_tool('asset_page', {'limit': 1, 'cursor': first['next_cursor']}))
                    self.assertEqual(second['assets'][0]['id'], f.ids[1])
                    self.assertEqual(len(self.requests), 2)
                    selected = self.assert_result(await session.call_tool('asset_selection',
                        {'workspace_id': f.scope, 'ids': [f.ids[0], 'missing', f.ids[2]]}))
                    self.assertEqual([item['id'] for item in selected['items']], [f.ids[0], 'missing', f.ids[2]])
                    self.assertEqual([item['state'] for item in selected['items']], ['active', 'missing', 'active'])
                    self.assertEqual(len(self.requests), 3)
                    self.assert_no_writes(before)
                    # A separate fixture writer changes the catalogue, not the tool.
                    with f.store.connection() as db: db.execute("UPDATE assets SET title='external edit'")
                    after = f.store.snapshot()
                    stale = await session.call_tool('asset_page', {'limit': 1, 'cursor': second['next_cursor']})
                    self.assertTrue(stale.isError)
                    self.assertEqual(stale.structuredContent['error']['code'], 'asset_cursor_stale')
                    self.assertEqual(stale.structuredContent['error']['http_status'], 409)
                    self.assertNotIn('recovery', stale.structuredContent['error'])
                    self.assertEqual(len(self.requests), 4)
                    foreign = await session.call_tool('asset_selection', {'workspace_id': 'f' * 32, 'ids': [f.ids[0]]})
                    self.assertTrue(foreign.isError)
                    self.assertEqual(foreign.structuredContent['context']['workspace_id'], 'f' * 32)
                    self.assertEqual(foreign.structuredContent['error']['code'], 'asset_workspace_conflict')
                    self.assertEqual(len(self.requests), 5)
                    self.assertTrue((await session.call_tool('workflow_apply', {})).isError)
                    self.assertEqual(len(self.requests), 5)
                    self.assert_no_writes(after)


if __name__ == '__main__': unittest.main()
