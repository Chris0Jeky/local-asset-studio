"""Real Studio dependency/readiness contracts; synthetic files, no models or GPU."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

from test_server import FakeStudio, server


class PresetModelReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ('config', 'presets', 'models', 'workflows/api', 'comfy/input'):
            (self.root/folder).mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root': str(self.root/'comfy')}))
        self.preset = {'id': 'fixture', 'name': 'Dependency fixture', 'graph': 'workflows/api/fixture.json'}
        self.graph = {'1': {'class_type': 'INPAINT_LoadFooocusInpaint', 'inputs': {'head': 'head.pth', 'patch': 'fix.patch'}}}
        self.schema = {'INPAINT_LoadFooocusInpaint': {'input': {'required': {'head': [['head.pth']], 'patch': [['fix.patch']]}}, 'output': []}}
        self.manifest = []

    def studio(self):
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [self.preset]}))
        (self.root/self.preset['graph']).write_text(json.dumps(self.graph))
        (self.root/'models/library.json').write_text(json.dumps({'assets': self.manifest}))
        with patch.object(threading.Thread, 'start'):
            studio = FakeStudio(self.root, [])
        return studio

    def health(self, studio, schema=True):
        with patch.object(studio, '_request', return_value={'system': {}}) as requests, \
             patch.object(studio, 'node_info', return_value=self.schema, side_effect=None if schema else URLError('schema unavailable')):
            report = studio.health()
        self.assertTrue(all(c.args[0] == '/system_stats' for c in requests.call_args_list))
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())
        return report

    def put(self, relative, body=b'synthetic', root=None):
        path = (root or self.root/'comfy/models')/relative
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        return path

    def pin(self, relative, identifier='model-pin', **changes):
        result = {'id': identifier, 'file': relative, 'sha256': 'a'*64, 'bytes': 9,
                  'url': 'https://huggingface.co/example/model/resolve/main/file.safetensors', 'source': 'source fixture'}
        result.update(changes); self.manifest.append(result); return result

    def requirements(self, studio):
        return {r['file']: r for r in studio.inspect_preset('fixture')['requirements']}

    def test_non_name_patch_reports_missing_even_when_cached_enum_lists_it(self):
        self.preset['model_files'] = ['inpaint/head.pth', 'inpaint/fix.patch']
        self.put('inpaint/head.pth'); path = self.put('inpaint/fix.patch')
        studio = self.studio(); self.assertNotIn('fixture', self.health(studio)['missing_models'])
        path.unlink()
        self.assertIn('inpaint/fix.patch', self.health(studio)['missing_models']['fixture'])
        self.assertFalse(self.requirements(studio)['inpaint/fix.patch']['present'])
        self.put('inpaint/fix.patch')
        self.assertNotIn('fixture', self.health(studio)['missing_models'])

    def test_graph_only_patch_and_head_resolve_without_per_preset_exception(self):
        studio = self.studio(); rows = self.requirements(studio)
        self.assertEqual(set(rows), {'inpaint/head.pth', 'inpaint/fix.patch'})
        self.assertEqual(set(self.health(studio)['missing_models']['fixture']), set(rows))

    def test_exact_folder_wins_over_same_basename_pin_elsewhere(self):
        self.graph = {'1': {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': 'shared.safetensors'}}}
        self.pin('clip_vision/shared.safetensors', 'vision')
        self.pin('text_encoders/shared.safetensors', 'text')
        self.put('text_encoders/shared.safetensors')
        rows = self.requirements(self.studio())
        self.assertEqual(list(rows), ['clip_vision/shared.safetensors'])
        self.assertEqual(rows['clip_vision/shared.safetensors']['asset_id'], 'vision')
        self.assertFalse(rows['clip_vision/shared.safetensors']['present'])

    def test_unknown_folder_is_not_invented_from_manifest_basename(self):
        self.graph = {'1': {'class_type': 'UnreviewedLoader', 'inputs': {'weights': 'unknown.safetensors'}}}
        self.pin('loras/unknown.safetensors'); self.put('loras/unknown.safetensors')
        row = next(iter(self.requirements(self.studio()).values()))
        self.assertIsNone(row['path']); self.assertIsNone(row['folder']); self.assertIsNone(row['present'])
        self.assertIsNone(row.get('asset_id')); self.assertFalse(row['installable'])
        self.assertIn('unknown', row['note'].lower())

    def test_explicit_declaration_resolves_unknown_loader_without_duplicate(self):
        self.graph = {'1': {'class_type': 'UnreviewedLoader', 'inputs': {'weights': 'custom.safetensors'}}}
        self.preset['model_files'] = ['background_removal/custom.safetensors']
        self.pin('background_removal/custom.safetensors'); self.put('background_removal/custom.safetensors')
        rows = self.requirements(self.studio())
        self.assertEqual(list(rows), self.preset['model_files'])
        self.assertTrue(rows[self.preset['model_files'][0]]['present'])
        self.assertEqual(rows[self.preset['model_files'][0]]['asset_id'], 'model-pin')

    def test_detector_subdirectory_and_windows_selection_separator(self):
        self.graph = {'1': {'class_type': 'UltralyticsDetectorProvider', 'inputs': {'model_name': 'bbox\\face.pt'}}}
        self.pin('ultralytics/bbox/face.pt'); self.put('ultralytics/bbox/face.pt')
        row = self.requirements(self.studio())['ultralytics/bbox/face.pt']
        self.assertTrue(row['present']); self.assertFalse(row['installable'])
        self.assertIn('safetensors', row['install_note'])

    def test_installability_matches_existing_library_policy(self):
        self.graph = {}
        self.preset['model_files'] = ['loras/good.safetensors', 'diffusion_models/manual.gguf', 'loras/unsourced.safetensors']
        for i, relative in enumerate(self.preset['model_files']): self.pin(relative, 'pin-'+str(i), **({'url': ''} if i == 2 else {}))
        studio = self.studio(); rows = self.requirements(studio)
        for asset in self.manifest:
            row = rows[asset['file']]; reason = studio.library.install_block(asset, False)
            self.assertEqual((row['installable'], row['install_note']), (reason is None, reason))

    def test_inactive_backend_uses_its_root_and_does_not_offer_active_installer(self):
        self.graph = {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'same.safetensors'}}}
        self.preset['backend_id'] = 'hidream'; self.pin('diffusion_models/same.safetensors')
        self.put('diffusion_models/same.safetensors')
        studio = self.studio(); isolated = self.root/'isolated'
        studio.backends.profiles['hidream']['root'] = str(isolated)
        rows = self.requirements(studio); row = rows['diffusion_models/same.safetensors']
        self.assertFalse(row['present']); self.assertFalse(row['installable'])
        self.assertIn('backend', row['install_note'].lower())
        self.assertFalse(isolated.exists(), 'inspection must not create a backend or its model folders')
        self.put('diffusion_models/same.safetensors', root=isolated/'models')
        self.assertTrue(self.requirements(studio)['diffusion_models/same.safetensors']['present'])
        # Active schema does not claim this separate backend is missing its loader.
        self.schema = {}
        self.assertNotIn('fixture', self.health(studio)['missing_models'])

    def test_schema_failure_keeps_local_file_evidence_without_claiming_ready(self):
        studio = self.studio(); report = self.health(studio, schema=False)
        self.assertFalse(report['schema_available'])
        self.assertIn('inpaint/fix.patch', report['missing_models']['fixture'])

    def test_unknown_requirement_refuses_preflight_without_a_type_error(self):
        self.graph = {'1': {'class_type': 'UnreviewedLoader', 'inputs': {'weights': 'unknown.safetensors'}}}
        studio = self.studio()
        with patch.object(studio, 'node_info', return_value={}), patch.object(studio, 'validate_graph'), \
             self.assertRaisesRegex(server.StudioError, 'resolve|Unknown|unknown'):
            studio.production_preflight(self.preset, self.graph)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_empty_declared_file_is_missing_not_usable_presence(self):
        self.preset['model_files'] = ['inpaint/head.pth', 'inpaint/fix.patch']
        self.put('inpaint/head.pth'); self.put('inpaint/fix.patch', b'')
        studio = self.studio()
        self.assertFalse(self.requirements(studio)['inpaint/fix.patch']['present'])
        self.assertIn('inpaint/fix.patch', self.health(studio)['missing_models']['fixture'])

    def test_readiness_does_not_call_inventory_hashes_or_installation(self):
        studio = self.studio(); before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        with patch.object(studio.library, 'snapshot', side_effect=AssertionError('no inventory scan')), \
             patch.object(studio.library, 'start_install', side_effect=AssertionError('no installation')), \
             patch.object(server, 'digest_file', side_effect=AssertionError('no hashing')):
            self.requirements(studio); self.health(studio)
        self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')))


    def test_same_basename_declarations_are_ambiguous_for_unknown_loader(self):
        self.graph = {'1': {'class_type': 'UnreviewedLoader', 'inputs': {'weights': 'same.safetensors'}}}
        self.preset['model_files'] = ['loras/same.safetensors', 'vae/same.safetensors']
        studio = self.studio(); rows = self.requirements(studio)
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows['same.safetensors']['path'])
        self.assertIn('ambiguous', rows['same.safetensors']['note'])
        self.assertFalse(rows['same.safetensors']['installable'])

    def test_duplicate_exact_pins_do_not_choose_an_arbitrary_installer(self):
        self.graph = {}; self.preset['model_files'] = ['loras/same.safetensors']
        self.pin('loras/same.safetensors', 'first'); self.pin('loras/same.safetensors', 'second')
        row = self.requirements(self.studio())['loras/same.safetensors']
        self.assertIsNone(row['asset_id']); self.assertFalse(row['installable'])
        self.assertIn('Multiple exact-path', row['install_note'])

    def test_invalid_loader_paths_remain_unknown_and_never_escape(self):
        studio = self.studio()
        for value in ('../escape.pth', '/absolute.pth', 'C:/absolute.pth', 'part:stream.pth', 'a//b.pth'):
            with self.subTest(value=value):
                graph = {'1': {'class_type': 'INPAINT_LoadFooocusInpaint', 'inputs': {'head': value}}}
                row = studio.inspect_preset('fixture', graph)['requirements'][0]
                self.assertIsNone(row['path']); self.assertIsNone(row['present']); self.assertFalse(row['installable'])

    def test_linked_and_broken_model_paths_are_unknown_not_missing_installs(self):
        self.graph = {}; self.preset['model_files'] = ['loras/linked.safetensors']
        self.pin('loras/linked.safetensors'); studio = self.studio()
        target = self.put('vae/original.safetensors'); link = self.root/'comfy/models/loras/linked.safetensors'
        link.parent.mkdir(parents=True)
        try: link.symlink_to(target)
        except OSError: self.skipTest('Symlink creation unavailable')
        for broken in (False, True):
            with self.subTest(broken=broken):
                if broken: target.unlink()
                row = self.requirements(studio)['loras/linked.safetensors']
                self.assertIsNone(row['present']); self.assertIsNone(row['path']); self.assertFalse(row['installable'])
                self.assertIn('link', row['note'])

    def test_permission_failure_is_unknown_and_readiness_is_not_green(self):
        studio = self.studio(); original = Path.stat
        def denied(path, *args, **kwargs):
            if path.name == 'fix.patch': raise PermissionError('fixture access denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', denied):
            row = self.requirements(studio)['inpaint/fix.patch']; report = self.health(studio)
        self.assertIsNone(row['present']); self.assertFalse(row['installable'])
        self.assertIn('unknown', row['note'])
        self.assertTrue(any('Unresolved dependency' in item for item in report['missing_models']['fixture']))

    def test_prompt_and_output_names_do_not_become_model_dependencies(self):
        self.graph = {'1': {'class_type': 'SomeNode', 'inputs': {'text': 'describe a file.safetensors',
                      'prompt': 'draw weights.gguf', 'filename_prefix': 'art/model.pt'}}}
        self.assertEqual(self.requirements(self.studio()), {})

    def test_annotator_checkpoint_is_not_a_models_library_dependency(self):
        # Depth Anything V2's weights are fetched by the comfyui_controlnet_aux node into its own ckpts folder; the
        # readiness projection must neither invent a models-library location for them nor report them missing.
        self.graph = {'1': {'class_type': 'DepthAnythingV2Preprocessor', 'inputs': {'ckpt_name': 'depth_anything_v2_vitl.pth', 'resolution': 1024}},
                      '2': {'class_type': 'CLIPVisionLoader', 'inputs': {'clip_name': 'shared.safetensors'}}}
        rows = self.requirements(self.studio())
        self.assertEqual(list(rows), ['clip_vision/shared.safetensors'])

    def test_live_non_name_enum_remains_authoritative_with_files_present(self):
        self.put('inpaint/head.pth'); self.put('inpaint/fix.patch')
        self.schema['INPAINT_LoadFooocusInpaint']['input']['required']['patch'] = [['different.patch']]
        report = self.health(self.studio())
        self.assertIn('fix.patch', report['missing_models']['fixture'])

    def test_one_health_pass_reuses_file_observations_across_presets(self):
        studio = self.studio(); from model_requirements import _presence
        observed = []
        def observe(root, relative, cache):
            observed.append(((str(root), relative) in cache))
            return _presence(root, relative, cache)
        presets = [dict(self.preset, id='first'), dict(self.preset, id='second')]
        with patch.object(studio, 'catalog', return_value={'presets': presets}), \
             patch('model_requirements._presence', side_effect=observe):
            self.health(studio)
        self.assertEqual(observed, [False, False, True, True])

    def test_every_current_catalog_model_selection_has_an_explicit_location(self):
        from model_requirements import requirements
        repo = Path(__file__).resolve().parents[1]
        presets = json.loads((repo/'presets/catalog.json').read_text(encoding='utf-8'))['presets']
        assets = json.loads((repo/'models/library.json').read_text(encoding='utf-8'))['assets']
        studio = self.studio()
        for preset in presets:
            graph = json.loads((repo/preset['graph']).read_text(encoding='utf-8'))
            with self.subTest(preset=preset['id']):
                rows = requirements(studio.library, preset, graph, studio.library.models, assets=assets)
                self.assertTrue(all(row['path'] is not None for row in rows), rows)
                self.assertTrue(all(row['present'] is False for row in rows))
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_real_http_readiness_inspection_and_pin_only_refusal(self):
        from http.client import HTTPConnection
        from http.server import ThreadingHTTPServer
        self.graph = {}; self.preset['model_files'] = ['inpaint/fix.patch', 'diffusion_models/manual.gguf']
        self.pin('diffusion_models/manual.gguf', 'manual-pin')
        studio = self.studio(); handler = type('ReadinessHandler', (server.Handler,), {'studio': studio})
        http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        def request(path, method='GET', payload=None):
            connection = HTTPConnection('127.0.0.1', http.server_port, timeout=5)
            headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191', 'Content-Type': 'application/json'}
            try:
                connection.request(method, path, body=json.dumps(payload) if payload is not None else None, headers=headers)
                response = connection.getresponse(); return response.status, json.loads(response.read())
            finally: connection.close()
        try:
            with patch.object(studio, '_request', return_value={'system': {}}), patch.object(studio, 'node_info', return_value={}):
                code, inspection = request('/api/inspect/fixture'); self.assertEqual(code, 200)
                manual = next(row for row in inspection['requirements'] if row['asset_id'])
                self.assertIs(manual['installable'], False); self.assertIn('safetensors', manual['install_note'])
                code, report = request('/api/health'); self.assertEqual(code, 200)
                self.assertIn('inpaint/fix.patch', report['missing_models']['fixture'])
                before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
                code, error = request('/api/models/install', 'POST', {'id': 'manual-pin'})
                self.assertEqual(code, 400); self.assertIn('safetensors', error['error'])
                self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')))
        finally: http.shutdown(); http.server_close(); thread.join(5)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())


if __name__ == '__main__': unittest.main()
