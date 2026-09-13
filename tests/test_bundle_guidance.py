"""Resource-scoped guidance, real Handler and offline CLI. Never loads a model."""
import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from studio_workflow import guidance as G

ROOT = Path(__file__).resolve().parents[1]
BASE = 'diffusion_models/base.safetensors'
ADAPTER = 'loras/accelerator.safetensors'


def fixture():
    graph = {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'base.safetensors'}},
             '2': {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['1', 0], 'lora_name': 'accelerator.safetensors', 'strength_model': 1.0}},
             '3': {'class_type': 'KSampler', 'inputs': {'model': ['2', 0], 'steps': 15, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'seed': 42}},
             '4': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': 'unchanged'}}}
    preset = {'id': 'fixture', 'modality': 'image', 'graph': 'workflows/api/fixture.json',
              'steps': ['3', 'steps'], 'cfg': ['3', 'cfg'], 'sampler': ['3', 'sampler_name'], 'scheduler': ['3', 'scheduler'],
              'seed': ['3', 'seed'], 'lora4': ['2', 'strength_model'], 'lora4_name': ['2', 'lora_name']}
    manifest = {'assets': [{'file': BASE, 'sha256': 'a'*64}, {'file': ADAPTER, 'sha256': 'b'*64}]}
    claim = {'id': 'accelerator', 'title': 'Synthetic accelerator schedule', 'runtime': 'comfyui',
             'resources': [{'file': BASE, 'sha256': 'a'*64}, {'file': ADAPTER, 'sha256': 'b'*64}],
             'when': [{'resource': ADAPTER, 'state': 'active'}],
             'settings': [{'target': {'control': 'steps', 'node_types': ['KSampler']}, 'recommended': {'values': [4]}, 'tested': None}],
             'source': {'kind': 'authored_hypothesis', 'locator': 'Synthetic unit-test fixture, not model advice', 'url': 'https://example.org/fixture', 'revision': None, 'retrieved_at': '2026-09-13'},
             'rationale': 'Exercise the scope contract without inference.', 'review_after': '2026-12-12'}
    return preset, graph, manifest, {'guidance': {'version': 1, 'claims': [claim]}}


class GuidancePolicyTests(unittest.TestCase):
    def setUp(self): self.p, self.g, self.m, self.k = fixture()
    def run_report(self, controls=None, today='2026-09-13'):
        return G.explain(self.p, self.g, controls or {}, self.k, self.m, today)
    def row(self, **kwargs): return self.run_report(**kwargs)['claims'][0]

    def test_active_scope_explains_current_without_changes(self):
        before = copy.deepcopy([self.p, self.g, self.m, self.k]); row = self.row()
        self.assertEqual(row['applicability'], 'applies'); self.assertEqual(row['checks'][0]['current'], 15)
        self.assertEqual(row['checks'][0]['assessment'], 'outside')
        self.assertEqual([self.p, self.g, self.m, self.k], before)
        report = self.run_report({'steps': 4}); self.assertEqual(report['claims'][0]['checks'][0]['assessment'], 'within')
        self.assertFalse(report['generation_submitted']); self.assertTrue(report['authoring_only'])

    def test_disabled_accelerator_stops_its_recommendation(self):
        self.assertEqual(self.row(controls={'lora4': 0})['applicability'], 'not_applicable')

    def test_moved_slot_targets_actual_resource_strength(self):
        self.k['guidance']['claims'][0]['settings'][0]['target'] = {'resource': ADAPTER, 'input': 'strength_model', 'node_types': ['LoraLoaderModelOnly']}
        row = self.row(); self.assertEqual(row['checks'][0]['control'], 'lora4'); self.assertEqual(row['checks'][0]['key'], '2.strength_model')

    def test_changed_pin_not_matching_family_blocks_scope(self):
        self.p['family'] = 'Same family'; self.m['assets'][1]['sha256'] = 'c'*64
        self.assertEqual(self.row()['applicability'], 'not_applicable')

    def test_renamed_and_missing_hash_are_not_verified(self):
        self.g['2']['inputs']['lora_name'] = 'renamed.safetensors'
        self.assertEqual(self.row()['applicability'], 'not_applicable')
        self.assertIn('loras/renamed.safetensors', self.run_report()['uncovered_resources'])
        self.g['2']['inputs']['lora_name'] = 'accelerator.safetensors'; self.m['assets'][1].pop('sha256')
        self.assertEqual(self.row()['applicability'], 'unknown')

    def test_duplicate_pin_is_ambiguous_even_if_hashes_equal(self):
        self.m['assets'].append(copy.deepcopy(self.m['assets'][1]))
        self.assertEqual(self.row()['applicability'], 'unknown')

    def test_custom_loader_activation_is_unknown(self):
        self.g['2']['class_type'] = 'CustomLoader'
        self.assertEqual(self.row()['applicability'], 'unknown')

    def test_text_encoder_strength_prevents_false_disabled_state(self):
        self.g['2']['class_type'] = 'LoraLoader'; self.g['2']['inputs'].update(strength_model=0, strength_clip=1)
        self.assertEqual(self.row()['applicability'], 'applies')

    def test_another_cfg_node_convention_is_not_transferred(self):
        self.g['3']['class_type'] = 'DifferentSampler'
        self.assertEqual(self.row()['applicability'], 'unknown')

    def test_control_prerequisites_are_checked(self):
        self.k['guidance']['claims'][0]['when'].append({'control': 'cfg', 'values': [1]})
        self.assertEqual(self.row(controls={'cfg': 2})['applicability'], 'not_applicable')
        self.p.pop('cfg'); self.assertEqual(self.row()['applicability'], 'unknown')

    def test_stock_baseline_requires_all_known_adapters_off(self):
        self.k['guidance']['claims'][0]['when'] = [{'adapters': 'none_active'}]
        self.assertEqual(self.row()['applicability'], 'not_applicable')
        self.assertEqual(self.row(controls={'lora4': 0})['applicability'], 'applies')
        self.g['2']['class_type'] = 'CustomLoader'; self.assertEqual(self.row(controls={'lora4': 0})['applicability'], 'unknown')

    def test_conflicting_recommendations_are_not_averaged(self):
        other = copy.deepcopy(self.k['guidance']['claims'][0]); other['id'] = 'other'
        other['settings'][0]['recommended'] = {'range': [8, 12]}; self.k['guidance']['claims'].append(other)
        report = self.run_report(); self.assertEqual(report['conflicts'], [{'target': '3.steps', 'claims': ['accelerator', 'other']}])
        self.assertEqual([c['checks'][0]['current'] for c in report['claims']], [15, 15])

    def test_conflicts_use_joint_not_only_pairwise_intersection(self):
        rows = []
        for i, values in enumerate([[1, 2], [2, 3], [1, 3]]):
            row = copy.deepcopy(self.k['guidance']['claims'][0]); row['id'] = 'c'+str(i); row['settings'][0]['recommended'] = {'values': values}; rows.append(row)
        self.k['guidance']['claims'] = rows; self.assertEqual(len(self.run_report()['conflicts']), 1)

    def test_observation_does_not_override_or_conflict_with_advice(self):
        row = copy.deepcopy(self.k['guidance']['claims'][0]); row['id'] = 'observation'; row['source']['kind'] = 'local_observation'
        row['settings'][0].update(recommended=None, tested={'range': [15, 15]}); self.k['guidance']['claims'].append(row)
        result = self.run_report(); self.assertEqual(result['conflicts'], [])
        self.assertEqual(result['claims'][1]['checks'][0]['assessment'], 'observation_only')

    def test_old_source_is_flagged_for_review_not_relabelled_current(self):
        self.assertTrue(self.row(today='2027-01-01')['review_due'])
        self.k['guidance']['claims'][0]['source']['retrieved_at'] = None
        self.assertIsNone(self.row()['source']['retrieved_at'])

    def test_invalid_claim_is_visible_not_silently_applied(self):
        for malformed in [{'range': [2, 1]}, {'values': [True]}, {'range': [0, float('inf')]}, {'values': ['4', 4]}]:
            with self.subTest(malformed=malformed):
                self.k['guidance']['claims'][0]['settings'][0]['recommended'] = malformed
                # Nonfinite JSON is rejected at the shared JSON boundary; direct evaluator refuses too.
                with self.assertRaises(ValueError): G.validate_claim(self.k['guidance']['claims'][0])
        self.k['guidance']['claims'][0]['settings'][0]['recommended'] = {'range': [2, 1]}
        report = self.run_report(); self.assertEqual(report['claims'], []); self.assertTrue(report['diagnostics'])

    def test_local_observation_cannot_be_entered_as_prescriptive(self):
        self.k['guidance']['claims'][0]['source']['kind'] = 'local_observation'
        self.assertTrue(self.run_report()['diagnostics']); self.assertEqual(self.run_report()['claims'], [])

    def test_untrusted_source_is_text_and_executable_url_is_refused(self):
        self.k['guidance']['claims'][0]['source']['url'] = 'javascript:alert(1)'
        self.assertTrue(self.run_report()['diagnostics'])
        self.k['guidance']['claims'][0]['source']['url'] = 'https://user:secret@example.org'
        self.assertTrue(self.run_report()['diagnostics'])

    def test_unknown_control_connections_and_nonfinite_values_refuse(self):
        for controls in [{'reference': 'x.png'}, {'steps': ['2', 0]}, {'steps': float('nan')}, {'steps': True}, {'steps': '4'}]:
            with self.subTest(controls=controls), self.assertRaises(ValueError): self.run_report(controls)
        self.assertEqual(self.g['3']['inputs']['steps'], 15)

    def test_companion_edits_are_complete_and_conflicting_aliases_refuse(self):
        self.g['5'] = {'class_type': 'KSampler', 'inputs': {'steps': 10}}
        self.p['bindings_extra'] = {'steps': [['5', 'steps']]}
        self.assertEqual([r['current'] for r in self.row(controls={'steps': 4})['checks']], [4, 4])
        self.p['cfg'] = ['5', 'steps']
        with self.assertRaises(ValueError): self.run_report({'steps': 4, 'cfg': 1})

    def test_reference_and_non_image_routes_stay_out_of_scope(self):
        for update in [{'modality': 'video'}, {'reference': ['1', 'image']}, {'requires_rgba_mask': True}]:
            p = {**self.p, **update}
            with self.assertRaises(ValueError): G.explain(p, self.g, {}, self.k, self.m)

    def test_legacy_kb_absence_is_an_explicit_coverage_gap(self):
        self.k = {'families': {}}
        report = self.run_report(); self.assertEqual(report['claims'], []); self.assertEqual(len(report['uncovered_resources']), 2)

    def test_duplicate_claims_are_all_excluded_not_first_wins(self):
        self.k['guidance']['claims'].append(copy.deepcopy(self.k['guidance']['claims'][0]))
        result = self.run_report()
        self.assertEqual(result['claims'], [])
        self.assertEqual(len(result['diagnostics']), 2)

    def test_prerequisite_files_need_exact_scope_pins(self):
        self.k['guidance']['claims'][0]['when'][0]['resource'] = 'loras/unpinned.safetensors'
        with self.assertRaisesRegex(ValueError, 'exact scope pin'):
            G.validate_claim(self.k['guidance']['claims'][0])

    def test_repository_claims_have_valid_unique_exact_pins(self):
        kb = G.read_json(ROOT/'presets/settings-kb.json'); manifest = G.read_json(ROOT/'models/library.json')
        pins = {a['file']: a['sha256'] for a in manifest['assets']}; seen = set()
        for claim in kb['guidance']['claims']:
            G.validate_claim(claim); self.assertNotIn(claim['id'], seen); seen.add(claim['id'])
            for item in claim['resources']: self.assertEqual(pins[item['file']], item['sha256'])

    def test_all_registered_non_reference_image_graphs_can_be_explained_offline(self):
        kb = G.read_json(ROOT/'presets/settings-kb.json'); manifest = G.read_json(ROOT/'models/library.json'); count = 0
        for p in G.read_json(ROOT/'presets/catalog.json')['presets']:
            if p.get('modality') != 'image' or any(p.get(k) for k in ('reference','last_reference','reference_slots','requires_rgba_mask')): continue
            with self.subTest(preset=p['id']):
                report = G.explain(p, G.read_json(ROOT/p['graph']), {}, kb, manifest)
                self.assertFalse(report['generation_submitted']); self.assertEqual(report['diagnostics'], []); count += 1
        self.assertGreater(count, 10)


class GuidanceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('bundle_guidance_server', ROOT/'app/server.py')
        server = importlib.util.module_from_spec(spec); spec.loader.exec_module(server)
        cls.server_module = server
    def setUp(self):
        self.p, self.g, self.m, self.k = fixture(); self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        for folder in ('presets','models','workflows/api'): (root/folder).mkdir(parents=True,exist_ok=True)
        for path,value in [('presets/settings-kb.json',self.k),('presets/catalog.json',{'presets':[self.p]}),('models/library.json',self.m),('workflows/api/fixture.json',self.g)]: (root/path).write_text(json.dumps(value))
        p,g=self.p,self.g
        class NoRuntime:
            def __init__(self): self.root=root; self.lock=threading.RLock()
            def preset(self,key):
                if key!=p['id']: raise ValueError('Unknown preset')
                return p
            def graph_for(self,preset): return copy.deepcopy(g),root/preset['graph']
            def __getattr__(self,key): raise AssertionError('Unexpected runtime/storage access: '+key)
        self.studio = NoRuntime()
        # Production factory composes Prompt/Workflow/Document/Run handlers.
        self.http = self.server_module.create_server(root, port=0, studio_factory=lambda _: self.studio)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.payload = {'preset_id':'fixture','controls':{},'expected_graph':copy.deepcopy(self.g),'expected_bindings':G.bindings(self.p)}
    def tearDown(self): self.http.shutdown();self.http.server_close();self.thread.join(5);self.temp.cleanup()
    def send(self, value=None, host='127.0.0.1:8191', origin='http://127.0.0.1:8191'):
        connection = HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            connection.request('POST','/api/workflow-studio/guidance',json.dumps(self.payload if value is None else value),headers={'Host':host,'Origin':origin,'Content-Type':'application/json'})
            reply=connection.getresponse();return reply.status,json.loads(reply.read())
        finally:connection.close()
    def test_real_http_explains_with_zero_runtime_or_storage_access(self):
        before={p.relative_to(self.studio.root):p.read_bytes() for p in self.studio.root.rglob('*') if p.is_file()}
        status,result=self.send();self.assertEqual(status,200);self.assertEqual(result['claims'][0]['applicability'],'applies')
        after={p.relative_to(self.studio.root):p.read_bytes() for p in self.studio.root.rglob('*') if p.is_file()};self.assertEqual(before,after)
    def test_host_and_origin_are_still_enforced(self):
        self.assertEqual(self.send(host='evil.invalid')[0],403);self.assertEqual(self.send(origin='https://evil.invalid')[0],403)
    def test_changed_template_and_binding_are_rejected(self):
        self.g['3']['inputs']['steps']=20;self.assertEqual(self.send()[0],400)
        self.g['3']['inputs']['steps']=15;self.p['steps']=['3','cfg'];self.assertEqual(self.send()[0],400)
    def test_malformed_graph_or_extra_commands_never_enter_runtime(self):
        for updates in [{'expected_graph':None},{'expected_graph':[]},{'expected_graph':{'x':None}},{'run':True}]:
            status,result=self.send({**self.payload,**updates});self.assertEqual(status,400);self.assertFalse(result['generation_submitted'])
    def test_missing_and_corrupt_registry_fail_visibly(self):
        (self.studio.root/'models/library.json').write_text('{}');self.assertEqual(self.send()[0],400)
        (self.studio.root/'models/library.json').unlink();self.assertEqual(self.send()[0],400)
    def test_cli_uses_same_read_only_evaluator(self):
        before={str(p):p.stat().st_mtime_ns for p in self.studio.root.rglob('*') if p.is_file()}
        proc=subprocess.run([sys.executable,'-m','studio_workflow.guidance','--repo-root',str(self.studio.root),'--preset','fixture','--controls','{"steps":4}'],cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stderr);self.assertEqual(json.loads(proc.stdout)['claims'][0]['checks'][0]['assessment'],'within')
        self.assertEqual(before,{str(p):p.stat().st_mtime_ns for p in self.studio.root.rglob('*') if p.is_file()})


class GuidanceClientTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_client_contracts(self):
        result=subprocess.run([shutil.which('node'),'--test','tests/bundle_guidance_client.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
