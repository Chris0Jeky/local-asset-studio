"""Exact resource coverage and binding provenance; no installed model reads."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from studio_workflow import guidance as G
from test_bundle_guidance import fixture, ADAPTER

ROOT = Path(__file__).resolve().parents[1]


class GuidanceResourceTests(unittest.TestCase):
    def real_report(self, name):
        preset = next(p for p in G.read_json(ROOT / 'presets/catalog.json')['presets'] if p['id'] == name)
        return preset, G.explain(preset, G.read_json(ROOT / preset['graph']), {}, {},
                                G.read_json(ROOT / 'models/library.json'))

    def test_anime_complete_includes_detector_and_upscaler(self):
        _, report = self.real_report('anime-complete')
        rows = {row['file']: row for row in report['resources']}
        for path, node in [('ultralytics/bbox/face_yolov8s.pt', '8'),
                           ('upscale_models/RealESRGAN_x4plus_anime_6B.pth', '10')]:
            with self.subTest(path=path):
                self.assertIn(path, rows)
                self.assertIn(path, report['uncovered_resources'])
                self.assertEqual(rows[path]['bindings'], [{'node': node, 'input': 'model_name', 'active': True}])

    def test_hidream_includes_every_declared_companion_without_inventing_loader_path(self):
        preset, report = self.real_report('hidream-o1-concept')
        self.assertEqual({r['file'] for r in report['resources']}, set(preset['model_files']))
        self.assertEqual(set(report['uncovered_resources']), set(preset['model_files']))
        self.assertEqual(len(report['resources']), 9)
        for row in report['resources']:
            self.assertEqual(row['bindings'], [])
            self.assertIsNone(row['active'])
            self.assertEqual(row['sources'], [{'kind': 'catalog_declaration', 'preset_id': preset['id']}])

    def test_class_specific_clip_vision_role_overrides_generic_field(self):
        p, g, m, k = fixture()
        g['5'] = {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': 'vision.safetensors'}}
        paths = {r['file'] for r in G.explain(p, g, {}, k, m)['resources']}
        self.assertIn('clip_vision/vision.safetensors', paths)
        self.assertNotIn('text_encoders/vision.safetensors', paths)

    def test_duplicate_resources_retain_each_binding_and_claim_target(self):
        p, g, m, k = fixture()
        g['5'] = copy.deepcopy(g['2']); g['5']['inputs']['strength_model'] = 0.25
        p['model_files'] = [ADAPTER, ADAPTER]
        k['guidance']['claims'][0]['settings'] = [{
            'target': {'resource': ADAPTER, 'input': 'strength_model', 'node_types': ['LoraLoaderModelOnly']},
            'recommended': {'range': [0.5, 1.0]}, 'tested': None}]
        before = copy.deepcopy([p, g, m, k])
        report = G.explain(p, g, {}, k, m)
        rows = [r for r in report['resources'] if r['file'] == ADAPTER]
        self.assertEqual(len(rows), 1)
        self.assertEqual([b['node'] for b in rows[0]['bindings']], ['2', '5'])
        self.assertEqual({c['key']: c['assessment'] for c in report['claims'][0]['checks']},
                         {'2.strength_model': 'within', '5.strength_model': 'outside'})
        self.assertEqual([s['kind'] for s in rows[0]['sources']],
                         ['graph_input', 'graph_input', 'catalog_declaration'])
        self.assertEqual([p, g, m, k], before)

    def test_disabled_graph_adapter_is_not_reactivated_by_declaration(self):
        p, g, m, k = fixture(); p['model_files'] = [ADAPTER]
        report = G.explain(p, g, {'lora4': 0}, k, m)
        row = next(r for r in report['resources'] if r['file'] == ADAPTER)
        self.assertIs(row['active'], False)
        self.assertEqual(report['claims'][0]['applicability'], 'not_applicable')
        self.assertNotIn(ADAPTER, report['uncovered_resources'])

    def test_declared_only_adapter_does_not_prove_no_active_adapters(self):
        p, g, m, k = fixture(); p['model_files'] = ['loras/custom.safetensors']
        k['guidance']['claims'][0]['when'] = [{'adapters': 'none_active'}]
        report = G.explain(p, g, {'lora4': 0}, k, m)
        self.assertEqual(report['claims'][0]['applicability'], 'unknown')
        self.assertIn('loras/custom.safetensors', report['uncovered_resources'])

    def test_invalid_declarations_are_not_reported_as_empty_coverage(self):
        for declarations in (None, 'diffusion_models/a.safetensors', ['../a'], ['other/a'], [123]):
            with self.subTest(declarations=declarations):
                p, g, m, k = fixture(); p['model_files'] = declarations
                with self.assertRaises(ValueError): G.explain(p, g, {}, k, m)

    def test_same_basename_in_distinct_folders_stays_distinct(self):
        p, g, m, k = fixture()
        p['model_files'] = ['embeddings/same.safetensors', 'loras/same.safetensors', 'vae_approx/same.safetensors']
        report = G.explain(p, g, {}, k, m)
        for path in p['model_files']:
            self.assertEqual(len([r for r in report['resources'] if r['file'] == path]), 1)

    def test_graph_windows_separator_matches_portable_declaration(self):
        p, g, m, k = fixture(); p['model_files'] = ['upscale_models/sub/up.pth']
        g['5'] = {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': 'sub\\up.pth'}}
        rows = [r for r in G.explain(p, g, {}, k, m)['resources'] if r['file'].endswith('up.pth')]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['bindings'][0]['node'], '5')

    def test_unknown_model_name_has_no_guessed_folder(self):
        p, g, m, k = fixture()
        g['5'] = {'class_type': 'CustomLoader', 'inputs': {'model_name': 'unknown.safetensors'}}
        report = G.explain(p, g, {}, k, m)
        self.assertFalse(any('unknown.safetensors' in r['file'] for r in report['resources']))

    def test_guidance_import_does_not_load_runtime_or_comfy_app_modules(self):
        code = "import sys,types;sys.path.insert(0,"+repr(str(ROOT))+" );sys.modules['app']=types.ModuleType('app');from studio_workflow import guidance;assert 'model_library' not in sys.modules;assert 'server' not in sys.modules"
        result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_model_entry_points_resolve_shared_contract_from_another_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            for script in ('fetch-hf.py', 'intake-downloads.py', 'civitai-fetch.py'):
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts' / script), '--help'],
                                            cwd=directory, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout)


if __name__ == '__main__': unittest.main()
