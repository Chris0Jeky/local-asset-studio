"""Real SQLite and loopback HTTP contracts, with no installed Comfy dependency."""
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from studio_workflow.core import catalog, new_document, compile_document, canonical
from studio_workflow.commands import apply_commands, execution_inputs_sha256
from studio_workflow.documents import WorkflowDocuments, DocumentError
from studio_workflow.document_http import extend_handler, PREFIX
from studio_workflow.sdk import WorkflowClient, ClientError
from studio_workflow.__main__ import main

INFO = {'Value': {'input': {'required': {'value': ['INT', {'min': 0, 'max': 2**63 - 1}]}}, 'output': ['INT']},
        'Pass': {'input': {'required': {'source': ['INT', {'forceInput': True}]}}, 'output': ['INT']},
        'Save': {'input': {'required': {'source': ['INT', {'forceInput': True}]}}, 'output': [], 'output_node': True}}
GRAPH = {'1': {'class_type': 'Value', 'inputs': {'value': 3}, '_meta': {'title': 'Original', 'opaque': {'keep': [1, 2]}}},
         '2': {'class_type': 'Pass', 'inputs': {'source': ['1', 0]}},
         '3': {'class_type': 'Save', 'inputs': {'source': ['2', 0]}}}


class SQLiteWorkspace:
    """The AssetWorkspace connection protocol, real SQL/rollback rather than mocks."""
    def __init__(self, root): self.database = Path(root) / 'assets.sqlite3'
    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=15); db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
        finally: db.close()


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = SQLiteWorkspace(self.temp.name)
        self.store = WorkflowDocuments(self.workspace)
        self.schema = catalog(INFO, 'primary'); self.doc = new_document(GRAPH, self.schema, 'Example')
        self.doc['source'] = {'opaque': {'reference': 'kept'}}
        self.initial = self.store.create({'request_id': 'create-test', 'document': self.doc})
        self.key = self.initial['id']
    def command(self, commands, expected=1, request='edit-test'):
        return self.store.command(self.key, {'request_id': request, 'expected_revision': expected, 'commands': commands})
    def test_create_roundtrip_and_reopen(self):
        current = WorkflowDocuments(SQLiteWorkspace(self.temp.name)).get(self.key)
        self.assertEqual(current, self.store.get(self.key)); self.assertEqual(current['revision'], 1)
        self.assertEqual(current['document']['source'], self.doc['source'])
        self.assertEqual(current['document']['nodes'], GRAPH)
    def test_atomic_batch_and_monotonic_revision(self):
        result = self.command([{'op': 'set_input', 'id': '1', 'input': 'value', 'value': 9}, {'op': 'rename', 'name': 'Renamed'}])
        self.assertEqual(result['revision'], 2); self.assertEqual(result['document']['nodes']['1']['inputs']['value'], 9)
        self.assertEqual(result['document']['name'], 'Renamed'); self.assertEqual(self.store.get(self.key, 1)['document']['name'], 'Example')
    def test_failed_command_rolls_back_entire_batch(self):
        with self.assertRaises(ValueError): self.command([{'op': 'rename', 'name': 'Lost'}, {'op': 'unknown'}])
        self.assertEqual(self.store.get(self.key), {k:v for k,v in self.initial.items() if k != 'replayed'})
        self.assertEqual(len(self.store.history(self.key)['revisions']), 1)
    def test_expected_revision_rejects_stale_client(self):
        self.command([{'op': 'rename', 'name': 'Human edit'}])
        with self.assertRaises(DocumentError) as caught:
            self.command([{'op': 'rename', 'name': 'Stale agent'}], request='agent-test')
        self.assertEqual(caught.exception.code, 'revision_conflict'); self.assertEqual(caught.exception.details['current_revision'], 2)
    def test_two_independent_clients_have_one_winner(self):
        def attempt(index):
            other = WorkflowDocuments(SQLiteWorkspace(self.temp.name))
            try: return other.command(self.key, {'request_id': 'race-' + str(index), 'expected_revision': 1,
                                                'commands': [{'op': 'rename', 'name': str(index)}]})['revision']
            except DocumentError as exc: return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, (1, 2)))
        self.assertCountEqual(results, [2, 'revision_conflict'])
        self.assertEqual(len(self.store.history(self.key)['revisions']), 2)
    def test_repeat_request_recovers_exact_receipt_after_later_edits(self):
        first = self.command([{'op': 'rename', 'name': 'First'}])
        self.command([{'op': 'rename', 'name': 'Second'}], expected=2, request='second')
        repeated = self.command([{'op': 'rename', 'name': 'First'}])
        self.assertTrue(repeated['replayed']); self.assertEqual(repeated['document'], first['document'])
        self.assertEqual(repeated['revision'], 2); self.assertEqual(repeated['head_revision'], 3)
    def test_create_request_is_recoverable_and_content_bound(self):
        repeated = self.store.create({'request_id': 'create-test', 'document': self.doc})
        self.assertEqual(repeated['id'], self.key); self.assertTrue(repeated['replayed'])
        with self.assertRaises(DocumentError): self.store.create({'request_id': 'create-test', 'document': {**self.doc, 'name': 'Changed'}})
        self.assertEqual(len(self.store.list()['documents']), 1)
    def test_request_id_cannot_be_repurposed_across_actions(self):
        with self.assertRaises(DocumentError): self.command([{'op': 'rename', 'name': 'Bad'}], request='create-test')
    def test_database_exception_rolls_back_rows_head_and_receipt(self):
        with self.workspace.connection() as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON workflow_requests_v1 BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.command([{'op': 'rename', 'name': 'Never committed'}])
        self.assertEqual(self.store.get(self.key)['revision'], 1)
        with self.workspace.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_revisions_v1').fetchone()[0], 1)
            db.execute('DROP TRIGGER fail_receipt')
        self.assertEqual(self.command([{'op': 'rename', 'name': 'Now committed'}])['revision'], 2)
    def test_preview_matches_commit_but_does_not_write(self):
        commands = [{'op': 'set_input', 'id': '1', 'input': 'value', 'value': 8}]
        preview = self.store.preview(self.key, {'expected_revision': 1, 'commands': commands})
        self.assertFalse(preview['committed']); self.assertEqual(self.store.get(self.key)['revision'], 1)
        result = self.command(commands); self.assertEqual(preview['document_sha256'], result['document_sha256'])
    def test_restore_appends_and_preserves_abandoned_versions(self):
        self.command([{'op': 'rename', 'name': 'Later'}])
        result = self.store.command(self.key, {'request_id': 'restore', 'expected_revision': 2, 'revision': 1}, restore=True)
        self.assertEqual(result['revision'], 3); self.assertEqual(result['document']['name'], 'Example')
        self.assertEqual(self.store.get(self.key, 2)['document']['name'], 'Later')
        self.assertEqual(len(self.store.history(self.key)['revisions']), 3)
    def test_restore_requires_fresh_revision(self):
        self.command([{'op': 'rename', 'name': 'Changed'}])
        with self.assertRaises(DocumentError): self.store.command(self.key, {'request_id': 'restore', 'expected_revision': 1, 'revision': 1}, restore=True)
    def test_fork_pins_exact_source_and_does_not_mutate_it(self):
        result = self.store.fork(self.key, {'request_id': 'fork', 'revision': 1, 'name': 'Branch'})
        self.assertNotEqual(result['id'], self.key); self.assertEqual(result['origin']['document_sha256'], self.initial['document_sha256'])
        self.assertEqual(result['document']['source'], self.doc['source']); self.assertEqual(self.store.get(self.key)['revision'], 1)
    def test_layout_and_names_do_not_change_execution_inputs(self):
        result = self.command([{'op': 'rename', 'name': 'Layout only'}, {'op': 'set_position', 'id': '1', 'position': [10, 20]}])
        self.assertEqual(result['execution_inputs_sha256'], self.initial['execution_inputs_sha256'])
        self.assertEqual(compile_document(result['document'], self.schema)['graph_sha256'], compile_document(self.doc, self.schema)['graph_sha256'])
    def test_remove_node_keeps_dangling_edges_as_diagnostics(self):
        doc = apply_commands(self.doc, [{'op': 'remove_node', 'id': '2'}])
        self.assertEqual(doc['nodes']['3']['inputs']['source'], ['2', 0]); self.assertFalse(compile_document(doc, self.schema)['valid'])
    def test_disable_requires_explicit_bypass(self):
        doc = apply_commands(self.doc, [{'op': 'set_enabled', 'id': '2', 'enabled': False}])
        self.assertFalse(compile_document(doc, self.schema)['valid'])
        doc = apply_commands(doc, [{'op': 'set_bypass', 'id': '2', 'output': 0, 'input': 'source'}])
        self.assertTrue(compile_document(doc, self.schema)['valid'])
    def test_connect_disconnect_and_add_node(self):
        doc = apply_commands(self.doc, [{'op': 'add_node', 'id': '4', 'node': {'class_type': 'Value', 'inputs': {'value': 7}}},
                              {'op': 'connect', 'id': '2', 'input': 'source', 'source': '4', 'output': 0}])
        self.assertEqual(doc['nodes']['2']['inputs']['source'], ['4', 0])
        doc = apply_commands(doc, [{'op': 'disconnect', 'id': '2', 'input': 'source'}]); self.assertFalse(compile_document(doc, self.schema)['valid'])
    def test_replacement_ignores_client_revision_but_preserves_opaque_data(self):
        replacement = copy.deepcopy(self.doc); replacement['revision'] = 999
        result = self.command([{'op': 'replace', 'document': replacement}])
        self.assertEqual(result['revision'], 2); self.assertEqual(result['document']['nodes'], self.doc['nodes'])
    def test_large_integer_exact_roundtrip(self):
        result = self.command([{'op': 'set_input', 'id': '1', 'input': 'value', 'value': 9223372036854775807}])
        self.assertEqual(self.store.get(self.key)['document']['nodes']['1']['inputs']['value'], 9223372036854775807)
        self.assertEqual(result['revision'], 2)
    def test_invalid_requests_do_not_create_revisions(self):
        for request in ({'request_id': '../bad', 'expected_revision': 1, 'commands': []},
                        {'request_id': 'bad', 'expected_revision': True, 'commands': [{'op': 'rename', 'name': 'Bad'}]},
                        {'request_id': 'bad', 'expected_revision': 1, 'commands': [], 'surprise': 1}):
            with self.subTest(request=request), self.assertRaises(ValueError): self.store.command(self.key, request)
        self.assertEqual(len(self.store.history(self.key)['revisions']), 1)
    def test_changed_stored_bytes_are_not_returned_as_verified(self):
        with self.workspace.connection() as db:
            changed = {**self.initial['document'], 'name': 'Corrupted'}
            db.execute('UPDATE workflow_revisions_v1 SET document=? WHERE document_id=?',
                       (canonical(changed).decode(), self.key))
        with self.assertRaisesRegex(ValueError, 'integrity check failed'): self.store.get(self.key)
    def test_history_budget_refuses_without_pruning(self):
        with patch('studio_workflow.documents.MAX_HISTORY_BYTES', 1), self.assertRaises(ValueError): self.command([{'op': 'rename', 'name': 'Too much'}])
        self.assertEqual(len(self.store.history(self.key)['revisions']), 1)
    @unittest.skipUnless((Path(__file__).parents[1] / 'app/workspace.py').is_file(), 'Full application checkout required')
    def test_real_asset_workspace_connection_integration(self):
        from app.workspace import AssetWorkspace
        with tempfile.TemporaryDirectory() as root:
            workspace = AssetWorkspace(root); store = WorkflowDocuments(workspace)
            result = store.create({'request_id': 'real-workspace', 'document': self.doc})
            self.assertEqual(WorkflowDocuments(AssetWorkspace(root)).get(result['id'])['document'], result['document'])
            with workspace.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM assets').fetchone()[0], 0)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        workspace = SQLiteWorkspace(self.temp.name)
        studio = SimpleNamespace(assets=workspace, lock=threading.RLock())
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers.get('Host', '')
            def _content_length(self, cap):
                n = int(self.headers.get('Content-Length', 0))
                if not 0 <= n <= cap: raise ValueError('Body limit')
                return n
            def _json(self, status, value):
                raw = canonical(value); self.send_response(status); self.send_header('Content-Length', str(len(raw)))
                self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)
            def do_GET(self): return self._json(404, {'error': 'Base route'})
            def do_POST(self): return self._json(404, {'error': 'Base route'})
        Handler = extend_handler(Base); Handler.studio = studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.client = WorkflowClient(self.url)
        self.doc = new_document(GRAPH, catalog(INFO, 'primary'))
    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join()
    def test_sdk_roundtrip_preview_conflict_history_restore_and_fork(self):
        created = self.client.create_document(self.doc, request_id='sdk-create'); key = created['id']
        commands = [{'op': 'rename', 'name': 'SDK'}]
        preview = self.client.preview(key, commands, expected_revision=1)
        result = self.client.apply(key, commands, expected_revision=1, request_id='sdk-edit')
        self.assertEqual(result['document_sha256'], preview['document_sha256'])
        with self.assertRaises(ClientError) as caught: self.client.apply(key, commands, expected_revision=1, request_id='stale')
        self.assertEqual(caught.exception.code, 'revision_conflict'); self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.client.restore(key, 1, expected_revision=2, request_id='restore')['revision'], 3)
        self.assertEqual(self.client.get_document(key, 2)['document']['name'], 'SDK')
        self.assertEqual(len(self.client.history(key)['revisions']), 3)
        self.assertEqual(self.client.fork(key, 2, 'Branch', request_id='fork')['origin']['revision'], 2)
        self.assertEqual(len(self.client.documents()['documents']), 2)
    def test_origin_and_duplicate_keys_are_refused_before_document_creation(self):
        for raw, origin in ((canonical({'request_id': 'bad', 'document': self.doc}), 'http://evil.test'),
                            (b'{"request_id":"a","request_id":"b"}', self.url)):
            req = Request(self.url + PREFIX, data=raw, headers={'Content-Type': 'application/json', 'Origin': origin})
            with self.assertRaises(HTTPError) as caught: urlopen(req)
            caught.exception.close()
        self.assertEqual(self.client.documents()['documents'], [])
    def test_cli_shared_service_and_machine_conflict_exit(self):
        path = Path(self.temp.name) / 'doc.json'; path.write_bytes(canonical(self.doc))
        output = io.StringIO()
        with redirect_stdout(output): code = main(['--url', self.url, 'documents', 'create', '--document', str(path), '--request-id', 'cli-create'])
        self.assertEqual(code, 0); key = json.loads(output.getvalue())['id']
        commands = Path(self.temp.name) / 'commands.json'; commands.write_text('[{"op":"rename","name":"CLI"}]')
        args = ['--url', self.url, 'documents', 'apply', key, '--commands', str(commands), '--expected-revision', '1', '--request-id', 'cli-edit']
        with redirect_stdout(io.StringIO()): self.assertEqual(main(args), 0)
        args[-1] = 'cli-stale'; output = io.StringIO()
        with redirect_stdout(output): self.assertEqual(main(args), 6)
        self.assertEqual(json.loads(output.getvalue())['code'], 'revision_conflict')
    def test_request_after_commit_response_loss_recovers_same_revision(self):
        created = self.client.create_document(self.doc, request_id='lost-create')
        # Discard first response, then use a fresh client with the retained request.
        repeated = WorkflowClient(self.url).create_document(self.doc, request_id='lost-create')
        self.assertTrue(repeated['replayed']); self.assertEqual(repeated['id'], created['id'])
        self.assertEqual(len(self.client.history(created['id'])['revisions']), 1)
    def test_sdk_rejects_external_origins(self):
        for url in ('https://127.0.0.1:8191', 'http://example.test', 'http://127.0.0.1:8191/path', 'http://user@127.0.0.1:8191'):
            with self.assertRaises(ValueError): WorkflowClient(url)
