"""Offline qualification projection: declarations cannot become execution evidence."""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def fixture(preset_id='anime'):
    catalog = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
    preset = next(p for p in catalog['presets'] if p['id'] == preset_id)
    graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
    library = json.loads((ROOT / 'models/library.json').read_text(encoding='utf-8'))
    profiles = json.loads((ROOT / 'research/prompt-studio/profiles.json').read_text(encoding='utf-8'))
    return preset, graph, library, profiles


class RouteQualificationTests(unittest.TestCase):
    def setUp(self):
        self.q = importlib.import_module('studio_workflow.qualification')

    def test_real_routes_preserve_evidence_boundaries(self):
        for pid in ('anime', 'anima-portrait', 'anima-v1-baseline', 'pony', 'noob', 'qwen-3ref'):
            with self.subTest(preset=pid):
                result = self.q.inspect_route(*fixture(pid))
                self.assertFalse(result['generation_submitted'])
                self.assertFalse(result['qualification_complete'])
                for name in ('source_reviewed', 'installed', 'executed', 'visually_reviewed', 'accepted'):
                    self.assertIsNone(result['evidence'][name])
                self.assertIsNone(result['results']['resources']['peak_vram_bytes'])
                self.assertIsNone(result['results']['resources']['restart_required'])
                self.assertIsNone(result['results']['acceptance']['accepted'])
                self.assertIsNone(result['references']['native_slot_maximum'])
                self.assertTrue(result['components'])
                self.assertEqual(len(result['configuration_sha256']), 64)

    def test_exact_profile_match_is_not_legacy_association(self):
        result = self.q.inspect_route(*fixture())
        profiles = {p['id']: p for p in result['prompt_profiles']}
        self.assertEqual(profiles['animagine40-opt-tags-v1']['template_match'], True)
        self.assertIsNone(profiles['animagine4-tags-v1']['template_match'])
        self.assertEqual(profiles['animagine4-tags-v1']['scope'], 'recipe_association_only')

    def test_graph_and_text_binding_drift_invalidate_exact_profile(self):
        for kind in ('graph', 'binding', 'companion'):
            inputs = fixture()
            if kind == 'graph': inputs[1][inputs[0]['seed'][0]]['inputs']['seed'] += 1
            elif kind == 'binding': inputs[0]['positive'] = inputs[0]['negative']
            else: inputs[0]['bindings_extra'] = {'positive': [inputs[0]['negative']]}
            report = self.q.inspect_route(*inputs)
            exact = next(p for p in report['prompt_profiles'] if p['id'] == 'animagine40-opt-tags-v1')
            self.assertFalse(exact['template_match'], kind)

    def test_configuration_changes_for_pin_graph_profile_and_role_order(self):
        original = fixture('qwen-3ref')
        baseline = self.q.inspect_route(*original)['configuration_sha256']
        for part in ('pin', 'graph', 'profile', 'roles'):
            p, g, m, profiles = copy.deepcopy(original)
            if part == 'pin':
                next(a for a in m['assets'] if a['id'] == 'qwen-image-edit-2511-q4-gguf')['sha256'] = 'f' * 64
            elif part == 'graph': g[p['seed'][0]]['inputs']['seed'] += 1
            elif part == 'profile':
                next(a for a in profiles['profiles'] if a['id'] == 'qwen-edit2511-three-v1')['note'] += ' changed'
            else: p['reference_slots'].reverse()
            self.assertNotEqual(baseline, self.q.inspect_route(p, g, m, profiles)['configuration_sha256'], part)

    def test_qwen_keeps_accelerator_encoder_and_vae_separate(self):
        report = self.q.inspect_route(*fixture('qwen-3ref'))
        folders = {c['file'].split('/')[0] for c in report['components']}
        self.assertTrue({'diffusion_models', 'text_encoders', 'vae', 'loras'} <= folders)
        self.assertEqual([s['role'] for s in report['references']['catalog_slots']], ['identity', 'pose', 'style'])
        self.assertEqual(report['references']['catalog_slot_count'], 3)
        self.assertIn('UnetLoaderGGUF', [x['class_type'] for x in report['graph_inspection']['model_claims']])
        self.assertIsNone(report['runtime']['precision_verified'])
        self.assertIsNone(report['runtime']['prediction_type_verified'])

    def test_disabled_adapter_is_retained_and_not_reactivated(self):
        p, g, m, profiles = fixture('qwen-3ref')
        for node in g.values():
            if node['class_type'] == 'LoraLoaderModelOnly': node['inputs']['strength_model'] = 0
        report = self.q.inspect_route(p, g, m, profiles)
        adapters = [c for c in report['components'] if c['file'].startswith('loras/')]
        self.assertTrue(adapters)
        self.assertTrue(all(c['active'] is False for c in adapters))

    def test_ambiguous_and_missing_pins_do_not_choose_a_winner(self):
        for duplicate in (True, False):
            p, g, m, profiles = fixture()
            target = next(a for a in m['assets'] if a['id'] == 'sdxl-animagine-40-opt')
            if duplicate: m['assets'].append(copy.deepcopy(target))
            else: m['assets'].remove(target)
            report = self.q.inspect_route(p, g, m, profiles)
            row = next(c for c in report['components'] if c['file'] == target['file'])
            self.assertIsNone(row['pin_sha256'])
            self.assertIsNone(row['library_declaration'])
            self.assertTrue(any(x['code'] == 'unresolved_component_identity' for x in report['diagnostics']))

    def test_unrelated_library_addition_does_not_change_configuration(self):
        p, g, m, profiles = fixture()
        before = self.q.inspect_route(p, g, m, profiles)
        m['assets'].append({'id': 'irrelevant', 'file': 'vae/unrelated.safetensors', 'sha256': 'a' * 64})
        after = self.q.inspect_route(p, g, m, profiles)
        self.assertEqual(before['configuration_sha256'], after['configuration_sha256'])

    def test_outputs_are_detached_and_input_key_order_is_not_identity(self):
        inputs = fixture()
        before = copy.deepcopy(inputs)
        result = self.q.inspect_route(*inputs)
        result['components'][0]['library_declaration']['terms'] = 'changed'
        result['graph_inspection']['stages'].clear()
        self.assertEqual(inputs, before)
        reversed_inputs = tuple(dict(reversed(list(x.items()))) for x in inputs)
        self.assertEqual(self.q.inspect_route(*inputs), self.q.inspect_route(*reversed_inputs))

    def test_fixture_decoding_is_not_host_locale_dependent(self):
        original = Path.read_text
        def windows_default(path, *args, **kwargs):
            kwargs.setdefault('encoding', 'cp1252')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', windows_default):
            report = self.q.inspect_route(*fixture())
        exact = next(p for p in report['prompt_profiles'] if p['id'] == 'animagine40-opt-tags-v1')
        self.assertTrue(exact['template_match'])

    def test_malformed_library_file_keys_refuse_cleanly(self):
        for key in ([], {}, None, 7):
            p, g, m, profiles = fixture()
            m['assets'].append({'id': 'malformed', 'file': key})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.q.inspect_route(p, g, m, profiles)

    def test_malformed_inputs_refuse_cleanly(self):
        for index, replacement in ((0, []), (1, {}), (2, []), (3, {'profiles': [None]})):
            inputs = list(fixture()); inputs[index] = replacement
            with self.subTest(index=index), self.assertRaises(ValueError): self.q.inspect_route(*inputs)

    def test_declared_graph_resources_never_become_architecture_certification(self):
        p, g, m, profiles = fixture()
        first = next(iter(g.values()))
        first['class_type'] = 'UnreviewedLoader'
        report = self.q.inspect_route(p, g, m, profiles)
        self.assertTrue(report['graph_inspection']['uninterpreted_nodes'])
        self.assertFalse(report['qualification_complete'])

    def test_repository_read_is_bounded_and_has_no_runtime_side_effects(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            report = self.q.inspect_repository(ROOT, ['anime', 'qwen-3ref'])
        self.assertEqual([r['preset_id'] for r in report['routes']], ['anime', 'qwen-3ref'])
        self.assertTrue(report['input_files'])
        for identity in report['input_files']:
            self.assertEqual(len(identity['sha256']), 64)
        self.assertFalse(report['generation_submitted'])

    def test_duplicate_unknown_and_excessive_presets_refuse(self):
        for ids in ([], ['anime', 'anime'], ['unknown'], ['anime'] * 17):
            with self.subTest(ids=ids), self.assertRaises(ValueError): self.q.inspect_repository(ROOT, ids)

    def test_path_traversal_and_symlink_escape_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ('presets/catalog.json', 'models/library.json', 'research/prompt-studio/profiles.json'):
                target = root / rel; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / rel).read_bytes())
            cp = root / 'presets/catalog.json'; catalog = json.loads(cp.read_text(encoding='utf-8'))
            for route in catalog['presets']:
                if route['id'] == 'anime': route['graph'] = '../outside.json'
            cp.write_text(json.dumps(catalog), encoding='utf-8')
            with self.assertRaises(ValueError): self.q.inspect_repository(root, ['anime'])
            for route in catalog['presets']:
                if route['id'] == 'anime': route['graph'] = 'workflows/api/anime-api.json'
            cp.write_text(json.dumps(catalog), encoding='utf-8')
            (root / 'workflows').mkdir()
            try: (root / 'workflows/api').symlink_to(ROOT / 'workflows/api', target_is_directory=True)
            except OSError: self.skipTest('symlink creation unavailable')
            with self.assertRaises(ValueError): self.q.inspect_repository(root, ['anime'])

    def test_ambiguous_candidate_changes_still_change_content_identity(self):
        p, g, m, profiles = fixture()
        target = next(a for a in m['assets'] if a['id'] == 'sdxl-animagine-40-opt')
        m['assets'].append(copy.deepcopy(target))
        before = self.q.inspect_route(p, g, m, profiles)
        m['assets'][-1]['sha256'] = 'b' * 64
        after = self.q.inspect_route(p, g, m, profiles)
        self.assertNotEqual(before['configuration_sha256'], after['configuration_sha256'])
        row = next(c for c in after['components'] if c['file'] == target['file'])
        self.assertEqual(len(row['library_candidates']), 2)
        self.assertIsNone(row['library_declaration'])

    def test_boolean_schema_version_is_not_integer_one(self):
        p, g, m, profiles = fixture()
        profiles['schema_version'] = True
        with self.assertRaises(ValueError): self.q.inspect_route(p, g, m, profiles)

    def test_nonfinite_oversized_and_recursive_inputs_refuse(self):
        for bad in (float('nan'), float('inf'), 'x' * (1024 * 1024 + 1)):
            p, g, m, profiles = fixture(); p['description'] = bad
            with self.subTest(kind=type(bad)), self.assertRaises(ValueError):
                self.q.inspect_route(p, g, m, profiles)
        p, g, m, profiles = fixture(); p['cycle'] = p
        with self.assertRaises(ValueError): self.q.inspect_route(p, g, m, profiles)

    def test_invalid_catalog_byte_count_does_not_report_a_verified_pin(self):
        for size in (True, -1, 0, None):
            p, g, m, profiles = fixture()
            target = next(a for a in m['assets'] if a['id'] == 'sdxl-animagine-40-opt')
            target['bytes'] = size
            report = self.q.inspect_route(p, g, m, profiles)
            row = next(c for c in report['components'] if c['file'] == target['file'])
            self.assertEqual(row['identity'], 'invalid_catalog_pin')
            self.assertIsNone(row['pin_sha256'])

    def test_import_has_no_runtime_import_or_filesystem_creation(self):
        code = ("import sys, pathlib; "
                "sys.modules.update({k: None for k in ['torch','app','server','model_library']}); "
                "import studio_workflow.qualification; "
                "assert not list(pathlib.Path('.').iterdir())")
        with tempfile.TemporaryDirectory() as directory:
            import os
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                                    env=env, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_file_json_keys_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'presets').mkdir()
            (root / 'presets/catalog.json').write_text('{"presets": [], "presets": []}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                self.q.inspect_repository(root, ['anime'])

    def test_real_cli_json_and_unknown_recipe_exit(self):
        command = [sys.executable, '-m', 'studio_workflow.qualification', '--root', str(ROOT), '--preset']
        result = subprocess.run(command + ['anime'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['routes'][0]['preset_id'], 'anime')
        result = subprocess.run(command + ['missing'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)['generation_submitted'])


if __name__ == '__main__': unittest.main()
