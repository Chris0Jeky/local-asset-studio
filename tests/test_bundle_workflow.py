"""Bundle document projection, existing shared service, and revisioned reuse."""
from contextlib import contextmanager
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


def projected_document():
    code = "const C=require('./app/static/bundle-workflow-core.js'),f=require('./tests/bundle_workflow_fixture.cjs');console.log(JSON.stringify(C.build(f.snapshot,f.base,'Reusable bundle').document));"
    result = subprocess.run([shutil.which('node'), '-e', code], cwd=ROOT,
                            capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


class BundleWorkflowPolicyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser policy checks')
    def test_policy(self):
        result = subprocess.run([shutil.which('node'), '--test', 'tests/bundle_workflow_core.cjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(shutil.which('node') and (ROOT/'studio_workflow/documents.py').is_file(),
                     'Node.js and the full shared-workflow source are required')
class BundleWorkflowServiceTests(unittest.TestCase):
    def setUp(self):
        from studio_workflow.documents import WorkflowDocuments
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name)/'workspace.sqlite3'
        # Real WorkflowDocuments/commands/validation on an isolated SQLite database.
        # This implements the existing connection protocol, not a new application store.
        class Workspace:
            @contextmanager
            def connection(self):
                db = sqlite3.connect(path); db.row_factory = sqlite3.Row
                db.execute('PRAGMA foreign_keys=ON')
                try:
                    with db: yield db
                finally: db.close()
        self.workspace = Workspace()
        self.store = WorkflowDocuments(self.workspace)
        self.document = projected_document()
        self.payload = {'request_id': 'bundle-service-test', 'document': self.document}

    def tearDown(self):
        self.tmp.cleanup()

    def test_generated_steps_pass_real_document_validation(self):
        from studio_workflow.core import document
        result = document(self.document)
        self.assertEqual(result, self.document)
        self.assertEqual(result['nodes']['4']['inputs']['strength_model'], .7)
        self.assertEqual(result['nodes']['4']['inputs']['strength_clip'], .7)
        self.assertEqual(result['outputs'], ['8'])

    def test_saved_document_and_source_survive_service_restart(self):
        from studio_workflow.documents import WorkflowDocuments
        first = self.store.create(self.payload)
        fresh = WorkflowDocuments(self.workspace).get(first['id'])
        self.assertEqual(first['document'], fresh['document'])
        self.assertEqual(fresh['document']['source']['bundle']['recipe_id'], 'painted')
        self.assertEqual(fresh['document']['steps'], self.document['steps'])
        self.assertFalse(fresh['generation_submitted'])
        self.assertEqual(first['id'], str(uuid.uuid5(uuid.UUID('0943b1d3-3a9c-4de4-a1b7-b59b8d7fa86d'), self.payload['request_id'])))

    def test_lost_reply_replays_exact_request_without_duplicate(self):
        from studio_workflow.documents import WorkflowDocuments
        first = self.store.create(self.payload)  # Discarding receipt simulates caller response loss.
        second = WorkflowDocuments(self.workspace).create(self.payload)
        self.assertTrue(second['replayed'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.store.list()['documents']), 1)
        self.assertEqual(len(self.store.history(first['id'])['revisions']), 1)

    def test_browser_receipt_validator_accepts_real_service_result(self):
        result = self.store.create(self.payload)
        record = {'path': '/api/workflow-studio/documents', 'operation': 'save', 'body': self.payload}
        code = "const C=require('./app/static/bundle-workflow-core.js');let input='';process.stdin.on('data',s=>input+=s);process.stdin.on('end',async()=>{const x=JSON.parse(input);try{await C.receipt(x.result,x.pending);console.log('ok')}catch(e){console.error(e);process.exitCode=1}});"
        run = subprocess.run([shutil.which('node'), '-e', code], cwd=ROOT,
                             input=json.dumps({'result':result,'pending':record}), capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)

    def test_same_request_different_document_is_refused(self):
        from studio_workflow.documents import DocumentError
        self.store.create(self.payload)
        altered = copy.deepcopy(self.payload); altered['document']['name'] = 'Different'
        with self.assertRaises(DocumentError) as caught: self.store.create(altered)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(len(self.store.list()['documents']), 1)

    def test_later_edits_use_existing_revision_checks_and_undo_history(self):
        from studio_workflow.documents import DocumentError
        saved = self.store.create(self.payload)
        newer = self.store.command(saved['id'], {'request_id':'agent-edit', 'expected_revision':1,
            'commands':[{'op':'replace','document':{**saved['document'],'name':'Agent revised'}}]})
        self.assertEqual(newer['revision'], 2)
        with self.assertRaises(DocumentError) as caught:
            self.store.command(saved['id'], {'request_id':'stale-browser-edit', 'expected_revision':1,
                'commands':[{'op':'replace','document':saved['document']}]})
        self.assertEqual(caught.exception.code, 'revision_conflict')
        restored = self.store.command(saved['id'], {'request_id':'restore-original', 'expected_revision':2,'revision':1}, restore=True)
        self.assertEqual(restored['revision'], 3)
        self.assertEqual(restored['document']['steps'], self.document['steps'])
        self.assertEqual(len(self.store.history(saved['id'])['revisions']), 3)
        replay = self.store.create(self.payload)
        self.assertEqual(replay['revision'], 1)
        self.assertEqual(replay['head_revision'], 3)
        self.assertEqual(len(self.store.list()['documents']), 1)
