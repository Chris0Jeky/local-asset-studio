"""Actual Studio/HTTP/CLI/SDK integration; no worker thread or Comfy request runs."""
import copy
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from test_workflow_preset_adapter import GRAPH, PRESET, INFO
from studio_workflow.core import catalog, new_document, digest
from studio_workflow.preset_adapter import prepare_document
from studio_workflow.execution import run_ticket

FULL_CHECKOUT = (Path(__file__).parents[1] / 'app/server.py').is_file()


@unittest.skipUnless(FULL_CHECKOUT, 'Requires the complete Studio source checkout')
class PresetIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_server import server
        from studio_workflow.http_extension import extend_handler
        self.server_module = server
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ('presets', 'workflows/api', 'config', 'fake-comfy/input'):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}), encoding='utf-8')
        (self.root / PRESET['graph']).write_text(json.dumps(GRAPH), encoding='utf-8')
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}), encoding='utf-8')
        with patch.object(threading.Thread, 'start'):
            self.studio = server.Studio(self.root)
        self.studio.node_info = lambda *args: copy.deepcopy(INFO)
        self.studio._request = lambda *args, **kwargs: self.fail('No Comfy HTTP request is authorized by this fixture')
        self.doc = new_document(GRAPH, catalog(INFO, 'primary'))
        handler = extend_handler(server.Handler); handler.studio = self.studio
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        def stop():
            self.http.shutdown(); self.http.server_close(); self.thread.join(5)
        self.addCleanup(stop)
        self.url = 'http://127.0.0.1:' + str(self.http.server_port)
    def test_real_preparation_and_ticket_job_recovery(self):
        self.doc['nodes']['3']['inputs'].update(text='local graph', seed=2**63-1)
        report = prepare_document(self.studio, self.doc, 'example')
        self.assertFalse(self.studio.jobs)
        first = run_ticket(self.studio, report['ticket'], True)
        second = run_ticket(self.studio, report['ticket'], True)
        self.assertEqual(first['job']['id'], report['job_id']); self.assertTrue(second['replayed'])
        self.assertEqual(len(self.studio.jobs), 1); self.assertEqual(self.studio.queue.qsize(), 1)
        job = self.studio.jobs[report['job_id']]
        self.assertNotIn('2', job['graph']); self.assertEqual(job['graph']['3']['inputs']['seed'], 2**63-1)
        self.assertEqual(digest(job['graph']), report['prepared_graph_sha256'])
    def test_real_host_memory_gate_on_prepare_and_later_dispatch(self):
        self.studio.config['enforce_host_commit_headroom'] = True
        preset = dict(PRESET, host_commit_heavy=True)
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [preset]}), encoding='utf-8')
        self.doc['nodes']['3']['inputs'].update(width=1024, height=1024)
        def reading(available):
            return {'available_bytes': available, 'limit_bytes': 96*1024**3,
                    'committed_bytes': 96*1024**3-available, 'unknown_reason': None}
        with patch.object(self.studio, 'host_commit_reading', return_value=reading(31*1024**3)):
            with self.assertRaisesRegex(ValueError, '32 GiB'): prepare_document(self.studio, self.doc, 'example')
        with patch.object(self.studio, 'host_commit_reading', return_value=reading(40*1024**3)):
            report = prepare_document(self.studio, self.doc, 'example')
        with patch.object(self.studio, 'host_commit_reading', return_value=reading(31*1024**3)):
            with self.assertRaisesRegex(ValueError, '32 GiB'): run_ticket(self.studio, report['ticket'], True)
        self.assertFalse(self.studio.jobs); self.assertEqual(self.studio.queue.qsize(), 0)
    def test_actual_http_sdk_and_external_origin_refusal(self):
        from studio_workflow.sdk import WorkflowClient
        client = WorkflowClient(self.url)
        report = client.prepare_document(self.doc, preset_id='example')
        self.assertEqual(report['recipe']['preset_id'], 'example'); self.assertFalse(self.studio.jobs)
        req = Request(self.url + '/api/workflow-studio/prepare-document',
                      data=json.dumps({'document': self.doc, 'preset_id': 'example'}).encode(),
                      headers={'Content-Type': 'application/json', 'Origin': 'https://untrusted.invalid'})
        with self.assertRaises(HTTPError) as caught: urlopen(req, timeout=3)
        self.assertEqual(caught.exception.code, 403); caught.exception.close()
    def test_cli_writes_a_runnable_ticket_and_prints_source_report(self):
        from studio_workflow.__main__ import main
        source = self.root / 'workflow.json'; source.write_text(json.dumps(self.doc), encoding='utf-8')
        ticket_file = self.root / 'ticket.json'; output = io.StringIO()
        args = ['--url', self.url, 'prepare-document', '--document', str(source), '--preset', 'example', '--out', str(ticket_file)]
        with redirect_stdout(output): self.assertEqual(main(args), 0)
        report = json.loads(output.getvalue()); self.assertEqual(json.loads(ticket_file.read_bytes()), report['ticket'])
        self.assertFalse(self.studio.jobs)
        with redirect_stdout(io.StringIO()): self.assertEqual(main(['--url', self.url, 'run', '--ticket', str(ticket_file), '--approve']), 0)
        self.assertEqual(len(self.studio.jobs), 1)
        with redirect_stdout(io.StringIO()): self.assertEqual(main(args), 2)
        self.assertEqual(json.loads(ticket_file.read_bytes()), report['ticket'])
        self.assertEqual(len(self.studio.jobs), 1)
