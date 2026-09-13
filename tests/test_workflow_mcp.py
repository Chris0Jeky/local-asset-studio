"""Optional official-SDK protocol and real stdio/shared-SQLite contracts.

The dedicated MCP CI job installs the exact SDK and must not skip these tests.
The ordinary Studio suite can run without the optional agent environment.
"""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

from studio_workflow.agent_bridge import AgentBridge, OUTPUT_SCHEMA
from studio_workflow.client import Client
from studio_workflow.core import canonical, digest
from studio_workflow.mcp_server import build_server

HAS_MCP = importlib.util.find_spec('mcp') is not None


class RecordingClient:
    def __init__(self): self.calls = []
    def request(self, path, body=None):
        self.calls.append((path, body))
        return {'seed': 2**64 - 1, 'status': 'ok'}


@unittest.skipUnless(HAS_MCP, 'Install optional workflow-mcp requirements for protocol tests')
class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_list_and_exact_structured_reply(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        client = RecordingClient(); server = build_server(AgentBridge(client))
        async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
            listing = await session.list_tools()
            names = {t.name for t in listing.tools}
            self.assertIn('workflow_get', names); self.assertNotIn('recipe_run', names)
            self.assertNotIn('workflow_apply', names); self.assertEqual(client.calls, [])
            self.assertTrue(all(t.outputSchema == OUTPUT_SCHEMA for t in listing.tools))
            result = await session.call_tool('workflow_get', {'document_id': 'a'})
            self.assertFalse(result.isError)
            self.assertEqual(json.loads(result.structuredContent['data_json'])['seed'], 2**64-1)
            self.assertEqual(result.structuredContent['data_sha256'], digest({'seed': 2**64-1, 'status': 'ok'}))
            self.assertEqual(json.loads(result.content[0].text), result.structuredContent)
    async def test_author_permission_schema_and_invalid_arguments(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        client = RecordingClient(); server = build_server(AgentBridge(client, 'author'))
        async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
            listing = await session.list_tools()
            tools = {t.name: t for t in listing.tools}
            self.assertFalse(tools['workflow_apply'].annotations.readOnlyHint)
            self.assertNotIn('recipe_run', tools)
            rejected = await session.call_tool('workflow_apply', {'document_id': 'a', 'expected_revision': True,
                        'request_id': 'bad', 'commands_json': '[]'})
            self.assertTrue(rejected.isError); self.assertEqual(client.calls, [])
            blocked = await session.call_tool('recipe_run', {})
            self.assertTrue(blocked.isError); self.assertEqual(client.calls, [])
    async def test_saved_run_execute_is_hash_bound_and_permission_scoped(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        source = {'request_id': 'original', 'record_sha256': 'a'*64, 'ticket_sha256': 'b'*64, 'job_id': 'job-1'}
        client = RecordingClient()
        def response(path, body=None):
            client.calls.append((path, body))
            return {'source': source, 'dispatch': {'status': 'reconciliation_required', 'job_id': 'job-1'}}
        client.request = response
        async with create_connected_server_and_client_session(build_server(AgentBridge(client)), raise_exceptions=True) as session:
            tools = {t.name for t in (await session.list_tools()).tools}
            self.assertIn('saved_run_review', tools); self.assertNotIn('saved_run_execute', tools)
            self.assertEqual(client.calls, [])
        async with create_connected_server_and_client_session(build_server(AgentBridge(client, 'execute')), raise_exceptions=True) as session:
            result = await session.call_tool('saved_run_execute', {k: source[k] for k in ('request_id', 'record_sha256', 'ticket_sha256')})
            self.assertTrue(result.isError)
            self.assertEqual(result.structuredContent['error']['code'], 'reconciliation_required')
            self.assertEqual(client.calls, [('/api/workflow-studio/document-runs/original/run',
                {'approved': True, 'record_sha256': 'a'*64, 'ticket_sha256': 'b'*64})])

    async def test_compile_error_has_tool_error_and_unchanged_diagnostics(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        client = RecordingClient()
        client.request = lambda *args: {'valid': False, 'errors': [{'code': 'missing_node'}]}
        async with create_connected_server_and_client_session(build_server(AgentBridge(client)), raise_exceptions=True) as session:
            result = await session.call_tool('workflow_compile', {'document_json': '{}'})
            self.assertTrue(result.isError)
            self.assertEqual(result.structuredContent['error']['code'], 'invalid_workflow')
            self.assertEqual(json.loads(result.structuredContent['data_json'])['errors'], [{'code': 'missing_node'}])


@unittest.skipUnless(HAS_MCP, 'Install optional workflow-mcp requirements for protocol tests')
class MCPStdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_to_real_documents_preserves_cas_and_exact_replay(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from studio_workflow.documents import WorkflowDocuments
        from studio_workflow.document_http import extend_handler
        from studio_workflow.core import catalog, new_document
        with tempfile.TemporaryDirectory() as temp:
            class Workspace:
                @contextmanager
                def connection(self):
                    db = sqlite3.connect(str(Path(temp) / 'assets.sqlite3'), timeout=15)
                    db.row_factory = sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
                    try:
                        with db: yield db
                    finally: db.close()
            workspace = Workspace(); store = WorkflowDocuments(workspace)
            studio = SimpleNamespace(assets=workspace, lock=threading.RLock())
            class Base(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
                def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://127.0.0.1:' + str(self.server.server_port)
                def _content_length(self, limit):
                    size = int(self.headers.get('Content-Length', 0))
                    if not 0 <= size <= limit: raise ValueError('Body limit')
                    return size
                def _json(self, status, result):
                    raw = canonical(result)
                    self.send_response(status); self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
                def do_GET(self): self._json(404, {'error': 'No other routes in fixture'})
                def do_POST(self): self._json(404, {'error': 'No generation routes in fixture'})
            handler = extend_handler(Base); handler.studio = studio
            http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
            try:
                root = Path(__file__).resolve().parents[1]
                params = StdioServerParameters(command=sys.executable,
                    args=[str(root / 'scripts/workflow-mcp.py'), '--mode', 'author', '--url', 'http://127.0.0.1:' + str(http.server_port)],
                    cwd=temp)
                async with asyncio.timeout(35):
                    async with stdio_client(params) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize(); await session.list_tools()
                            schema = catalog({'Value': {'input': {'required': {'seed': ['INT', {'max': 2**64-1}]}}, 'output': ['INT']}}, 'primary')
                            doc = new_document({'1': {'class_type': 'Value', 'inputs': {'seed': 2**64-1}}}, schema)
                            created = await session.call_tool('workflow_create', {'document_json': canonical(doc).decode(), 'request_id': 'created-over-stdio'})
                            self.assertFalse(created.isError, created)
                            initial = json.loads(created.structuredContent['data_json']); key = initial['id']
                            self.assertEqual(store.get(key)['document']['nodes']['1']['inputs']['seed'], 2**64-1)
                            args = {'document_id': key, 'expected_revision': 1, 'request_id': 'agent-edit',
                                    'commands_json': '[{"op":"rename","name":"Agent version"}]'}
                            result = await session.call_tool('workflow_apply', args)
                            self.assertFalse(result.isError, result)
                            store.command(key, {'request_id': 'human-edit', 'expected_revision': 2,
                                                'commands': [{'op': 'rename', 'name': 'Human version'}]})
                            # Discarding the first response and repeating its exact write
                            # must recover revision 2, not overwrite the newer human head.
                            repeated = await session.call_tool('workflow_apply', args)
                            record = json.loads(repeated.structuredContent['data_json'])
                            self.assertTrue(record['replayed']); self.assertEqual(record['revision'], 2)
                            self.assertEqual(record['head_revision'], 3)
                            stale = await session.call_tool('workflow_apply', dict(args, request_id='stale-new-request'))
                            self.assertTrue(stale.isError)
                            self.assertEqual(stale.structuredContent['error']['code'], 'revision_conflict')
                            self.assertEqual(store.get(key)['document']['name'], 'Human version')
                            readback = await session.call_tool('workflow_get', {'document_id': key})
                            self.assertEqual(json.loads(readback.structuredContent['data_json'])['revision'], 3)
                            self.assertEqual(len(store.history(key)['revisions']), 3)
            finally:
                http.shutdown(); http.server_close(); thread.join(5)


if __name__ == '__main__': unittest.main()
