"""Real SQLite plus production projector/ticket logic; synthetic runtime, no GPU."""
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from studio_workflow import preset_adapter
from studio_workflow.core import canonical, catalog, new_document, digest
from studio_workflow.documents import WorkflowDocuments, DocumentError
from studio_workflow.document_runs import DocumentRuns
from studio_workflow.execution import run_ticket
from studio_workflow.run_http import PREFIX, extend_handler, route

INFO = {'Sample': {'input': {'required': {'text': ['STRING', {}], 'seed': ['INT', {}]}}, 'output': ['IMAGE']},
        'Save': {'input': {'required': {'images': ['IMAGE', {}], 'filename_prefix': ['STRING', {}]}}, 'output_node': True}}
GRAPH = {'1': {'class_type': 'Sample', 'inputs': {'text': 'example', 'seed': 1}},
         '2': {'class_type': 'Save', 'inputs': {'images': ['1', 0], 'filename_prefix': 'fixed'}}}
PRESET = {'id': 'example', 'modality': 'image', 'graph': 'template.json', 'positive': ['1', 'text'], 'seed': ['1', 'seed']}


class Workspace:
    def __init__(self, root): self.database = Path(root) / 'assets.sqlite3'; self.fail_commit_reply = False
    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=5); db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
            if self.fail_commit_reply:
                self.fail_commit_reply = False
                raise OSError('Committed response lost')
        finally: db.close()


class Runtime:
    def __init__(self, root):
        self.root = Path(root); self.assets = Workspace(root); self.lock = threading.RLock()
        self.backends = SimpleNamespace(active='primary', busy=False)
        self.comfy_root = self.root / 'comfy'; self.comfy_url = 'http://127.0.0.1:8188'
        self.experiments = self.root / 'experiments'; self.runs = self.experiments / 'runs'
        self.runs.mkdir(parents=True, exist_ok=True)
        self.jobs = {}; self.submissions = 0; self.fail_after_job = False
        self.path = self.root / 'template.json'; self.path.write_bytes(canonical(GRAPH))
    def preset(self, key):
        if key != PRESET['id']: raise ValueError('Unknown preset')
        return copy.deepcopy(PRESET)
    def graph_for(self, preset): return json.loads(self.path.read_bytes()), self.path
    def node_info(self): return copy.deepcopy(INFO)
    def prune_disabled_loras(self, graph): return graph
    def prepare(self, recipe):
        preset = self.preset(recipe['preset_id']); graph, path = self.graph_for(preset)
        for control, value in recipe.get('controls', {}).items():
            key, field = preset[control]; graph[key]['inputs'][field] = value
        return preset, graph, path, recipe.get('controls', {}), 1
    def public(self, job): return copy.deepcopy({k: v for k, v in job.items() if k != 'graph'})
    def create_job(self, recipe, job_id=None):
        self.submissions += 1
        _, graph, _, _, _ = self.prepare(recipe)
        self.jobs[job_id] = {'id': job_id, 'preset_id': recipe['preset_id'], 'comfy_url': self.comfy_url,
                            'graph': graph, 'status': 'queued', 'prompt_ids': [], 'outputs': []}
        if self.fail_after_job: raise OSError('Response lost after job creation')
        return self.public(self.jobs[job_id])


class RunFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.runtime = Runtime(self.temp.name); self.docs = WorkflowDocuments(self.runtime.assets)
        doc = new_document(GRAPH, catalog(INFO, 'primary'))
        doc['nodes']['1']['inputs'].update(text='saved change', seed=2**63-1)
        self.source = self.docs.create({'request_id': 'source', 'document': doc})
        self.store = DocumentRuns(self.docs)
        self.value = {'request_id': 'prepare-first', 'document_id': self.source['id'],
                      'expected_revision': 1, 'preset_id': 'example'}
    def prepare(self, **edits): return self.store.prepare(self.runtime, {**self.value, **edits})
    def edit(self):
        return self.docs.command(self.source['id'], {'request_id': 'edit', 'expected_revision': 1,
                                                     'commands': [{'op': 'rename', 'name': 'Later revision'}]})


class RunRecordTests(RunFixture, unittest.TestCase):
    def test_saved_source_exact_seed_and_no_dispatch(self):
        result = self.prepare(); record = result['record']; report = record['report']
        self.assertEqual(record['request'], self.value)
        self.assertEqual(report['document_sha256'], self.source['document_sha256'])
        self.assertEqual(report['ticket']['recipe']['controls']['seed'], 2**63-1)
        self.assertFalse(result['dispatch_attempted']); self.assertFalse(self.runtime.jobs)
        self.assertEqual(self.runtime.submissions, 0)
    def test_replay_recovers_ticket_after_later_edit_without_schema_calls(self):
        first = self.prepare(); self.edit()
        with patch.object(self.runtime, 'node_info', side_effect=AssertionError('No schema reads')):
            again = self.prepare()
        self.assertTrue(again['replayed']); self.assertEqual(again['record'], first['record'])
        self.assertEqual(again['head_revision'], 2); self.assertFalse(again['source_is_current'])
    def test_same_request_different_content_is_conflict(self):
        self.prepare()
        with self.assertRaises(DocumentError) as caught: self.prepare(preset_id='other')
        self.assertEqual(caught.exception.code, 'request_conflict')
    def test_stale_revision_fails_before_preparation(self):
        self.edit()
        with patch.object(self.runtime, 'node_info', side_effect=AssertionError('No schema reads')):
            with self.assertRaises(DocumentError) as caught: self.prepare()
        self.assertEqual(caught.exception.code, 'revision_conflict')
    def test_mid_preparation_edit_is_conflict_no_record(self):
        original = preset_adapter.prepare_document
        def concurrent(*args):
            report = original(*args); self.edit(); return report
        with patch.object(preset_adapter, 'prepare_document', side_effect=concurrent):
            with self.assertRaises(DocumentError) as caught: self.prepare()
        self.assertEqual(caught.exception.code, 'revision_conflict')
        self.assertEqual(self.store.list(self.source['id'])['runs'], []); self.assertFalse(self.runtime.jobs)
    def test_two_independent_clients_receive_one_committed_ticket(self):
        other = Runtime(self.temp.name); other_store = DocumentRuns(WorkflowDocuments(other.assets))
        barrier = threading.Barrier(2); original = preset_adapter.prepare_document
        def prepare(*args):
            report = original(*args); barrier.wait(timeout=5); return report
        with patch.object(preset_adapter, 'prepare_document', side_effect=prepare), ThreadPoolExecutor(2) as pool:
            left = pool.submit(self.store.prepare, self.runtime, self.value)
            right = pool.submit(other_store.prepare, other, self.value)
            results = [left.result(10), right.result(10)]
        self.assertEqual(results[0]['record'], results[1]['record'])
        self.assertCountEqual([r['replayed'] for r in results], [True, False])
        self.assertEqual(len(self.store.list(self.source['id'])['runs']), 1)
    def test_committed_but_lost_reply_is_recoverable(self):
        original = preset_adapter.prepare_document
        def after(*args):
            report = original(*args); self.runtime.assets.fail_commit_reply = True; return report
        with patch.object(preset_adapter, 'prepare_document', side_effect=after):
            with self.assertRaises(OSError): self.prepare()
        retained = self.store.get('prepare-first')
        self.assertEqual(self.prepare()['record'], retained['record']); self.assertFalse(self.runtime.jobs)
    def test_insert_failure_rolls_back_and_never_dispatches(self):
        with self.runtime.assets.connection() as db:
            db.execute("CREATE TRIGGER refuse_run BEFORE INSERT ON workflow_document_runs_v1 BEGIN SELECT RAISE(ABORT,'disk fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.prepare()
        self.assertEqual(self.store.list(self.source['id'])['runs'], []); self.assertFalse(self.runtime.jobs)
    def test_report_corruption_is_storage_error(self):
        self.prepare()
        with self.runtime.assets.connection() as db: db.execute("UPDATE workflow_document_runs_v1 SET record='{}'")
        with self.assertRaises(DocumentError) as caught: self.store.get('prepare-first')
        self.assertEqual(caught.exception.status, 503)
    def test_source_corruption_is_storage_error(self):
        self.prepare()
        with self.runtime.assets.connection() as db: db.execute("UPDATE workflow_revisions_v1 SET document='{}'")
        with self.assertRaises(DocumentError) as caught: self.store.get('prepare-first')
        self.assertEqual(caught.exception.status, 503)
    def test_run_then_reopen_recovers_same_ticket_and_observes_outputs(self):
        report = self.prepare()['record']['report']; first = run_ticket(self.runtime, report['ticket'], True)
        self.runtime.jobs[first['job']['id']].update(status='completed', prompt_ids=['kept-id'], outputs=[{'asset_id': 'asset-one'}])
        reopened = DocumentRuns(WorkflowDocuments(Workspace(self.temp.name)))
        # Reopening storage alone does not replace the runtime's current Workspace object.
        record = reopened.get('prepare-first')['record']; self.assertEqual(record['report'], report)
        observation = self.store.observe(self.runtime, 'prepare-first')['observation']
        self.assertEqual(observation['job']['outputs'], [{'asset_id': 'asset-one'}])
        self.assertEqual(observation['job']['prompt_ids'], ['kept-id'])
        self.assertEqual(self.store.by_job(report['job_id'])['record'], record)
        run_ticket(self.runtime, report['ticket'], True); self.assertEqual(self.runtime.submissions, 1)
    def test_missing_job_does_not_claim_unsubmitted_or_retry(self):
        self.prepare(); result = self.store.observe(self.runtime, 'prepare-first')
        self.assertEqual(result['observation']['state'], 'not_observed')
        self.assertNotIn('generation_submitted', result); self.assertEqual(self.runtime.submissions, 0)
    def test_lost_dispatch_reply_keeps_source_and_one_job(self):
        report = self.prepare()['record']['report']; self.runtime.fail_after_job = True
        self.assertEqual(run_ticket(self.runtime, report['ticket'], True)['status'], 'reconciliation_required')
        self.assertEqual(self.store.observe(self.runtime, 'prepare-first')['observation']['state'], 'observed')
        self.assertTrue(run_ticket(self.runtime, report['ticket'], True)['replayed'])
        self.assertEqual(self.runtime.submissions, 1)
    def test_missing_job_after_dispatch_is_only_observed_not_replayed(self):
        report = self.prepare()['record']['report']; run_ticket(self.runtime, report['ticket'], True)
        self.runtime.jobs.clear(); observed = self.store.observe(self.runtime, 'prepare-first')
        self.assertEqual(observed['observation']['state'], 'not_observed')
        self.assertEqual(run_ticket(self.runtime, report['ticket'], True)['status'], 'reconciliation_required')
        self.assertEqual(self.runtime.submissions, 1)
    def test_changed_workspace_and_wrong_graph_cannot_join(self):
        report = self.prepare()['record']['report']; run_ticket(self.runtime, report['ticket'], True)
        self.runtime.jobs[report['job_id']]['graph']['1']['inputs']['seed'] = 0
        self.assertEqual(self.store.observe(self.runtime, 'prepare-first')['observation']['state'], 'evidence_mismatch')
        self.runtime.runs = self.runtime.root / 'another-workspace'
        self.assertEqual(self.store.observe(self.runtime, 'prepare-first')['observation']['state'], 'workspace_changed')
    def test_pages_do_not_shift_with_new_records(self):
        for n in range(6): self.prepare(request_id='p-' + str(n))
        page = self.store.list(self.source['id'], limit=2); ids = [x['request_id'] for x in page['runs']]
        self.prepare(request_id='later')
        while page['next_before']:
            page = self.store.list(self.source['id'], before=page['next_before'], limit=2)
            ids.extend(x['request_id'] for x in page['runs'])
        self.assertEqual(ids, ['p-5', 'p-4', 'p-3', 'p-2', 'p-1', 'p-0'])
    def test_record_count_and_byte_budgets_never_prune(self):
        self.prepare()
        for limit in ('MAX_RECORDS', 'MAX_STORAGE_BYTES'):
            with patch('studio_workflow.document_runs.' + limit, 1):
                with self.assertRaises(ValueError): self.prepare(request_id='second')
        self.assertEqual(len(self.store.list(self.source['id'])['runs']), 1)
    def test_invalid_arguments_and_unsupported_graph_do_not_commit(self):
        for kwargs in ({'expected_revision': True}, {'request_id': '../run'}, {'unexpected': 1}, {'preset_id': '..'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.prepare(**kwargs)
        self.docs.command(self.source['id'], {'request_id': 'rewire', 'expected_revision': 1,
            'commands': [{'op': 'set_input', 'id': '2', 'input': 'filename_prefix', 'value': 'changed'}]})
        with self.assertRaises(ValueError): self.prepare(expected_revision=2)
        self.assertEqual(self.store.list(self.source['id'])['runs'], [])
    def test_workspace_replacement_during_prepare_cannot_commit(self):
        original = preset_adapter.prepare_document
        def changed(*args):
            report = original(*args); self.runtime.assets = Workspace(self.temp.name); return report
        with patch.object(preset_adapter, 'prepare_document', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'workspace changed'): self.prepare()
        self.assertEqual(self.store.list(self.source['id'])['runs'], [])

    def test_summary_paging_does_not_load_embedded_reports(self):
        for n in range(3): self.prepare(request_id='page-' + str(n))
        with patch.object(self.store, '_read', side_effect=AssertionError('List must not load reports')):
            self.assertEqual(len(self.store.list(self.source['id'])['runs']), 3)
    def test_corrupt_summary_fails_without_removing_history(self):
        self.prepare()
        with self.runtime.assets.connection() as db: db.execute("UPDATE workflow_document_runs_v1 SET summary='{}'")
        with self.assertRaises(DocumentError) as caught: self.store.list(self.source['id'])
        self.assertEqual(caught.exception.status, 503)
        with self.runtime.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_document_runs_v1').fetchone()[0], 1)
    def test_oversize_report_is_refused_before_commit(self):
        original = preset_adapter.prepare_document
        def large(*args):
            report = original(*args); report['notice'] = 'x' * 1048576; return report
        with patch.object(preset_adapter, 'prepare_document', side_effect=large):
            with self.assertRaisesRegex(ValueError, 'exceeds 1 MiB'): self.prepare()
        self.assertEqual(self.store.list(self.source['id'])['runs'], [])
    def test_unknown_source_and_invalid_cursors_are_rejected(self):
        with self.assertRaises(DocumentError) as caught: self.prepare(document_id='absent')
        self.assertEqual(caught.exception.status, 404)
        for kwargs in ({'limit': 0}, {'limit': True}, {'before': False}, {'before': -1}, {'limit': 101}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.store.list(self.source['id'], **kwargs)


class RunHTTPTests(RunFixture, unittest.TestCase):
    def start_http(self):
        class Base(BaseHTTPRequestHandler):
            def _safe_host(handler): return handler.headers.get('Host') == '127.0.0.1:8191'
            def _safe_mutation(handler): return handler._safe_host() and handler.headers.get('Origin') == 'http://127.0.0.1:8191'
            def _content_length(handler, limit):
                size = int(handler.headers['Content-Length']); assert 0 <= size <= limit; return size
            def _json(handler, code, data):
                raw = canonical(data); handler.send_response(code); handler.send_header('Content-Length', str(len(raw))); handler.end_headers(); handler.wfile.write(raw)
            def log_message(self, *args): pass
            def do_GET(handler): handler._json(404, {'error': 'base route'})
            def do_POST(handler): handler._json(404, {'error': 'base route'})
        handler = extend_handler(Base); handler.studio = self.runtime
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        def stop(): http.shutdown(); http.server_close(); thread.join(5)
        self.addCleanup(stop)
        self.url = 'http://127.0.0.1:' + str(http.server_port)
    def request(self, path, value=None, origin='http://127.0.0.1:8191'):
        request = Request(self.url + path, data=canonical(value) if value is not None else None,
            headers={'Host': '127.0.0.1:8191', 'Origin': origin, 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response: return response.status, json.loads(response.read())
        except HTTPError as exc:
            with exc: return exc.code, json.loads(exc.read())
    def test_http_prepare_recover_conflict_observe_and_security(self):
        self.start_http()
        self.assertEqual(self.request(PREFIX, self.value, 'https://untrusted.invalid')[0], 403)
        code, first = self.request(PREFIX, self.value); self.assertEqual(code, 200)
        self.edit(); code, recovered = self.request(PREFIX + '/prepare-first')
        self.assertEqual(recovered['record'], first['record']); self.assertEqual(recovered['head_revision'], 2)
        self.assertEqual(self.request(PREFIX, {**self.value, 'preset_id': 'other'})[0], 409)
        self.assertEqual(self.request(PREFIX + '/prepare-first/observe')[1]['observation']['state'], 'not_observed')
        self.assertEqual(self.request(PREFIX + '?document_id=' + self.source['id'])[0], 200)
        self.assertEqual(self.request(PREFIX + '/by-job/' + first['record']['report']['job_id'])[0], 200)
        self.assertFalse(self.runtime.jobs)
    def test_invalid_json_queries_methods_and_corruption(self):
        self.start_http(); self.prepare()
        for path in (PREFIX + '?document_id=x&document_id=y', PREFIX + '?document_id=x&limit=0',
                     PREFIX + '?document_id=x&limit=1.1', PREFIX + '?document_id=x&after=2', PREFIX + '/prepare-first?limit=1'):
            self.assertEqual(self.request(path)[0], 400, path)
        self.assertEqual(self.request(PREFIX + '/prepare-first/observe', {})[0], 400)
        self.assertEqual(self.request(PREFIX + '/unknown')[0], 404)
        with self.runtime.assets.connection() as db: db.execute("UPDATE workflow_document_runs_v1 SET record='{}'")
        self.assertEqual(self.request(PREFIX + '/prepare-first')[0], 503)

