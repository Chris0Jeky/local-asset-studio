"""Pure authoring, real HTTP routing and mocked shared-worker dispatch contracts."""
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from http_refusal_transport import atomic_json_post
from studio_workflow import core
from studio_workflow.execution import prepare_ticket, run_ticket
from studio_workflow.http_extension import extend_handler, PREFIX, post
from studio_workflow.__main__ import Client, main
from studio_workflow.guides import guides

INFO = {
    'Number': {'input': {'required': {'value': ['INT', {'default': 5, 'min': 0, 'max': 100}]}}, 'output': ['INT'], 'category': 'Example'},
    'Scale': {'input': {'required': {'source': ['INT', {'forceInput': True}], 'factor': ['FLOAT', {'default': 1.0, 'min': 0, 'max': 10}]}, 'optional': {'enabled': ['BOOLEAN', {'default': True}], 'mode': [['fast', 'precise']]}}, 'output': ['INT']},
    'Output': {'input': {'required': {'number': ['INT', {}]}}, 'output': [], 'output_node': True},
    'Text': {'input': {'required': {'text': ['STRING', {'default': 'hello'}]}}, 'output': ['STRING']},
    'Custom': {'input': {'required': {'color': ['COLOR', {'socketless': True, 'default': '#000000'}]}}, 'output': ['INT']},
}
GRAPH = {'1': {'class_type': 'Number', 'inputs': {'value': 5}},
         '2': {'class_type': 'Scale', 'inputs': {'source': ['1', 0], 'factor': 2.0}},
         '3': {'class_type': 'Output', 'inputs': {'number': ['2', 0]}}}


class FakeStudio:
    def __init__(self, root):
        self.root = Path(root); self.experiments = self.root / 'experiments'
        self.runs = self.experiments / 'runs'; self.runs.mkdir(parents=True)
        self.comfy_root = self.root / 'comfy'; (self.comfy_root / 'input').mkdir(parents=True)
        self.comfy_url = 'http://127.0.0.1:8188'
        self.backends = SimpleNamespace(active='primary', busy=False)
        self.lock = threading.RLock(); self.jobs = {}; self.calls = 0
        self.path = self.root / 'graph.json'; self.path.write_text(json.dumps(GRAPH))
        self.recipe = {'id': 'example', 'name': 'Example recipe', 'backend_id': 'primary'}
    def node_info(self, refresh=False): return copy.deepcopy(INFO)
    def preset(self, identifier):
        if identifier != 'example': raise ValueError('Unknown preset')
        return copy.deepcopy(self.recipe)
    def graph_for(self, preset): return json.loads(self.path.read_text()), self.path
    def prepare(self, payload):
        preset = self.preset(payload.get('preset_id'))
        graph, path = self.graph_for(preset)
        expected = payload.get('expected_template_sha256')
        if expected and expected != core.hashlib.sha256(path.read_bytes()).hexdigest(): raise ValueError('Template changed')
        controls = payload.get('controls', {})
        if set(controls) - {'value'}: raise ValueError('Unsupported controls')
        if 'value' in controls: graph['1']['inputs']['value'] = controls['value']
        return preset, graph, path, controls, payload.get('batch_count', 1)
    def create_job(self, payload, job_id=None):
        self.calls += 1; self.prepare(payload)
        job = {'id': job_id, 'status': 'queued', 'prompt_ids': []}; self.jobs[job_id] = job
        return self.public(job)
    def public(self, job): return copy.deepcopy(job)


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.schema = core.catalog(INFO, 'primary'); self.doc = core.new_document(GRAPH, self.schema)
    def check(self, doc=None): return core.compile_document(doc or self.doc, self.schema)
    def test_preserves_graph_and_never_mutates_input(self):
        original = copy.deepcopy(self.doc); result = self.check()
        self.assertTrue(result['valid']); self.assertEqual(GRAPH, result['graph']); self.assertEqual(original, self.doc)
        self.assertFalse(result['generation_submitted'])
    def test_disconnected_nodes_retained_but_not_exported(self):
        self.doc['nodes']['4'] = {'class_type': 'MissingClass', 'inputs': {}}
        self.assertTrue(self.check()['valid']); self.assertNotIn('4', self.check()['graph']); self.assertIn('4', self.doc['nodes'])
    def test_cycles_and_dangling_links_fail(self):
        for value in (['2', 0], ['absent', 0], ['1', 90]):
            with self.subTest(value=value):
                doc = copy.deepcopy(self.doc); doc['nodes']['2']['inputs']['source'] = value
                self.assertFalse(self.check(doc)['valid'])
    def test_values_are_strict_not_silently_coerced(self):
        for value in (True, 1.5, '12', -1, 101, None):
            with self.subTest(value=value):
                doc = copy.deepcopy(self.doc); doc['nodes']['1']['inputs']['value'] = value
                self.assertFalse(self.check(doc)['valid'])
    def test_union_and_wildcard_types(self):
        self.assertTrue(core.compatible('MESH', 'MESH,FILE_3D_GLB')); self.assertTrue(core.compatible('IMAGE', '*'))
        self.assertFalse(core.compatible('IMAGE', 'LATENT'))
    def test_missing_required_unknown_fields_and_wrong_type(self):
        for inputs in ({'factor': 2.0}, {'source': ['1', 0], 'factor': 2, 'extra': 1}, {'source': 'not a link', 'factor': 2}):
            doc = copy.deepcopy(self.doc); doc['nodes']['2']['inputs'] = inputs
            self.assertFalse(self.check(doc)['valid'])
    def test_optional_boolean_combo(self):
        self.doc['nodes']['2']['inputs'].update(enabled=False, mode='fast')
        self.assertTrue(self.check()['valid'])
        self.doc['nodes']['2']['inputs']['mode'] = 'bad'; self.assertFalse(self.check()['valid'])
    def test_disabled_bypass_is_explicit_and_type_checked(self):
        self.doc['disabled'] = ['2']; self.assertFalse(self.check()['valid'])
        self.doc['bypass'] = {'2': {'0': 'source'}}
        result = self.check(); self.assertTrue(result['valid']); self.assertEqual(result['graph']['3']['inputs']['number'], ['1', 0])
        self.assertNotIn('2', result['graph']); self.assertIn('2', self.doc['nodes'])
        self.doc['nodes']['2']['inputs']['source'] = ['2', 0]; self.assertFalse(self.check()['valid'])
    def test_bypass_does_not_hide_wrong_source_type(self):
        self.doc['nodes']['1'] = {'class_type': 'Text', 'inputs': {'text': 'wrong type'}}
        self.doc['disabled'] = ['2']; self.doc['bypass'] = {'2': {'0': 'source'}}
        self.assertFalse(self.check()['valid'])
    def test_disabled_output_refused(self):
        self.doc['disabled'] = ['3']; self.assertFalse(self.check()['valid'])
    def test_custom_widget_retained_but_compile_refuses(self):
        self.doc['nodes']['1'] = {'class_type': 'Custom', 'inputs': {'color': '#000000'}}
        self.assertFalse(self.check()['valid']); self.assertEqual(self.doc['nodes']['1']['inputs']['color'], '#000000')
    def test_raw_link_behaviour_requires_adapter_even_when_connected(self):
        info = copy.deepcopy(INFO); info['Scale']['input']['required']['source'][1]['rawLink'] = True
        schema = core.catalog(info, 'primary'); doc = core.new_document(GRAPH, schema)
        self.assertFalse(core.compile_document(doc, schema)['valid'])
    def test_schema_and_backend_change_require_explicit_rebase(self):
        for field, value in (('backend_id', 'hidream'), ('schema_sha256', '0' * 64)):
            doc = copy.deepcopy(self.doc); doc[field] = value; self.assertFalse(self.check(doc)['valid'])
    def test_visual_and_envelope_import_not_silently_flattened(self):
        for value in ({'nodes': []}, {'prompt': GRAPH}):
            with self.assertRaises(ValueError): core.new_document(value, self.schema)
    def test_decoder_rejects_duplicate_reserved_nonfinite_nested_and_oversized(self):
        for raw in ('{"x":1,"x":2}', '{"__proto__":{}}', 'NaN', '1e400', '[' * 50 + '0' + ']' * 50, ' ' * (core.MAX_BYTES + 1)):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError): core.decode(raw)
    def test_python_preserves_int64_without_javascript_rounding(self):
        self.assertEqual(core.decode('{"seed":9223372036854775807}')['seed'], 9223372036854775807)
    def test_node_caps_and_unknown_document_fields(self):
        doc = copy.deepcopy(self.doc); doc['surprise'] = True
        with self.assertRaises(ValueError): core.document(doc)
        doc = copy.deepcopy(self.doc); doc['nodes'] = {str(i): GRAPH['1'] for i in range(257)}
        with self.assertRaises(ValueError): core.document(doc)
    def test_v3_combo_and_nodedef_v2(self):
        info = {'V3': {'input': {'required': {'mode': ['COMBO', {'options': ['a', 'b']}]}}, 'output': []},
                'V2': {'inputs': {'count': {'type': 'INT', 'default': 1, 'isOptional': True}}, 'outputs': [{'index': 0, 'type': 'INT', 'name': 'count'}]}}
        schema = core.catalog(info, 'primary')
        self.assertEqual(schema['nodes']['V3']['inputs'][0]['widget'], 'combo')
        self.assertFalse(schema['nodes']['V2']['inputs'][0]['required'])
    def test_guides_have_real_local_routes_and_no_implicit_actions(self):
        data = guides(); self.assertEqual(len(data['guides']), 7)
        for guide in data['guides']:
            for step in guide['steps']: self.assertTrue(step['route'].startswith('/')); self.assertNotIn('/api/', step['route'])
        self.assertFalse(data['generation_submitted'])


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.studio = FakeStudio(self.temp.name); self.recipe = {'preset_id': 'example', 'controls': {}}
    def ticket(self): return prepare_ticket(self.studio, self.recipe)
    def test_prepare_is_inert_and_pinned(self):
        ticket = self.ticket(); self.assertEqual(self.studio.calls, 0); self.assertFalse(ticket['generation_submitted'])
        self.assertEqual(ticket['recipe']['expected_template_sha256'], ticket['pins']['template_sha256'])
    def test_approval_and_registered_fields_required(self):
        with self.assertRaises(ValueError): run_ticket(self.studio, self.ticket())
        for recipe in ({'graph': GRAPH}, dict(self.recipe, batch_count=2), dict(self.recipe, batch_count=True)):
            with self.assertRaises(ValueError): prepare_ticket(self.studio, recipe)
        self.assertEqual(self.studio.calls, 0)
    def test_repeat_ticket_and_uncertain_job_never_redispatch(self):
        ticket = self.ticket(); first = run_ticket(self.studio, ticket, True)
        self.studio.jobs[first['job']['id']]['status'] = 'uncertain'
        again = run_ticket(self.studio, ticket, True)
        self.assertTrue(again['replayed']); self.assertEqual(again['job']['status'], 'uncertain'); self.assertEqual(self.studio.calls, 1)
    def test_concurrent_ticket_dispatches_once(self):
        ticket = self.ticket()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: run_ticket(self.studio, ticket, True), range(4)))
        self.assertEqual(self.studio.calls, 1); self.assertEqual(len({r['job']['id'] for r in results}), 1)
    def test_content_conflict_refused(self):
        ticket = self.ticket(); run_ticket(self.studio, ticket, True); ticket['recipe']['controls']['value'] = 9
        with self.assertRaises(ValueError): run_ticket(self.studio, ticket, True)
        self.assertEqual(self.studio.calls, 1)
    def test_changed_environment_or_template_refused_before_receipt(self):
        ticket = self.ticket(); self.studio.backends.active = 'hidream'
        with self.assertRaises(ValueError): run_ticket(self.studio, ticket, True)
        self.assertEqual(self.studio.calls, 0)
        self.studio.backends.active = 'primary'; self.studio.path.write_text(json.dumps({'7': GRAPH['1']}))
        with self.assertRaises(ValueError): run_ticket(self.studio, ticket, True)
        self.assertEqual(self.studio.calls, 0)
    def test_intent_without_job_stays_parked(self):
        ticket = self.ticket()
        with patch.object(self.studio, 'create_job', side_effect=OSError('disk failed')):
            first = run_ticket(self.studio, ticket, True)
        second = run_ticket(self.studio, ticket, True)
        self.assertEqual(first['status'], 'reconciliation_required'); self.assertEqual(second['status'], 'reconciliation_required'); self.assertEqual(self.studio.calls, 0)
    def test_response_loss_after_job_creation_reconciles(self):
        ticket = self.ticket(); original = self.studio.create_job
        def lose(payload, job_id=None): original(payload, job_id); raise OSError('response lost')
        with patch.object(self.studio, 'create_job', side_effect=lose): first = run_ticket(self.studio, ticket, True)
        self.assertEqual(first['status'], 'reconciliation_required')
        second = run_ticket(self.studio, ticket, True); self.assertEqual(second['job']['id'], first['job_id']); self.assertEqual(self.studio.calls, 1)
    def test_restart_with_retained_receipt_but_no_loaded_job_never_dispatches(self):
        ticket = self.ticket(); run_ticket(self.studio, ticket, True); self.studio.jobs.clear()
        self.assertEqual(run_ticket(self.studio, ticket, True)['status'], 'reconciliation_required'); self.assertEqual(self.studio.calls, 1)
    def test_reference_bytes_are_pinned(self):
        graph = copy.deepcopy(GRAPH); graph['4'] = {'class_type': 'LoadImage', 'inputs': {'image': 'source.png'}}
        self.studio.path.write_text(json.dumps(graph)); image = self.studio.comfy_root / 'input' / 'source.png'; image.write_bytes(b'original')
        ticket = self.ticket(); image.write_bytes(b'changed')
        with self.assertRaises(ValueError): run_ticket(self.studio, ticket, True)
    def test_refresh_and_compile_do_not_dispatch(self):
        post(PREFIX + '/nodes/refresh', {}, self.studio)
        doc = core.new_document(GRAPH, core.catalog(INFO, 'primary'))
        self.assertTrue(post(PREFIX + '/compile', {'document': doc}, self.studio)['valid']); self.assertEqual(self.studio.calls, 0)


class LocalHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def _json(self, status, data):
        raw = json.dumps(data).encode(); self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _safe_host(self): return self.headers.get('Host') == self.server.expected_host
    def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.server.expected_host
    def _content_length(self, limit):
        size = int(self.headers.get('Content-Length', -1)); core.need(0 <= size <= limit, 'Invalid body size'); return size
    def do_GET(self): self._json(200, {'existing_route': True})
    def do_POST(self): self._json(200, {'existing_route': True})


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.studio = FakeStudio(self.temp.name)
        handler = extend_handler(LocalHandler); handler.studio = self.studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.server.expected_host = '127.0.0.1:' + str(self.server.server_port)
        self.url = 'http://' + self.server.expected_host
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def test_get_and_post_use_existing_host_origin_guards(self):
        client = Client(self.url)
        self.assertTrue(client.request(PREFIX + '/capabilities')['shared_worker'])
        self.assertEqual(client.request('/api/old'), {'existing_route': True})
        self.assertEqual(atomic_json_post(self.server.server_port, PREFIX + '/compile', b'{}',
                                          host=self.server.expected_host, origin='https://foreign.invalid')[0], 403)
        self.assertEqual(self.studio.calls, 0)
    def test_strict_json_import_has_no_side_effect(self):
        with self.assertRaises(HTTPError) as caught: Client(self.url).request(PREFIX + '/open', {'content': '{"x":1,"x":2}'})
        self.addCleanup(caught.exception.close)
        result = Client(self.url).request(PREFIX + '/open', {'content': json.dumps(GRAPH)})
        self.assertEqual(result['document']['nodes'], GRAPH); self.assertEqual(self.studio.calls, 0)
    def test_cli_prepare_run_replay_roundtrip(self):
        recipe = Path(self.temp.name) / 'recipe.json'; recipe.write_text(json.dumps({'preset_id': 'example'}))
        ticket = Path(self.temp.name) / 'ticket.json'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--url', self.url, 'prepare', '--recipe', str(recipe), '--out', str(ticket)]), 0)
            self.assertEqual(main(['--url', self.url, 'run', '--ticket', str(ticket), '--approve']), 0)
            self.assertEqual(main(['--url', self.url, 'run', '--ticket', str(ticket), '--approve']), 0)
        self.assertEqual(self.studio.calls, 1)
    def test_cli_rejects_external_origin_credentials_and_nonfinite_timeout(self):
        for url in ('https://127.0.0.1:8191', 'http://example.com', 'http://user@127.0.0.1:8191', 'http://localhost:8191', 'http://127.0.0.1/a'):
            with self.assertRaises(ValueError): Client(url)
        with self.assertRaises(ValueError): Client(self.url, float('nan'))


class TypedTextFrontendTests(unittest.TestCase):
    """The shipped editor script in Node, without a browser: re-renders keep what the user is typing."""
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_typed_name_and_inspector_values_survive_rerender_and_number_box_follows_slider(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('workflow_studio_typed_frontend.cjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('number boxes and sliders stay in sync', result.stdout)

if __name__ == '__main__': unittest.main()
