"""Compare the real Create capacity projection with the authoritative graph guard."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from test_server import server
import wan_capacity

ROOT = Path(__file__).resolve().parents[1]


def catalogue():
    studio = server.Studio.__new__(server.Studio)
    studio.root = ROOT
    studio.catalog_path = ROOT / 'presets/catalog.json'
    studio.config = {}
    studio.options = lambda: {'loras': []}
    return {p['id']: p for p in studio.catalog()['presets']}


class WanReadinessTests(unittest.TestCase):
    def test_catalogue_projects_actual_ordinary_decoder_latents(self):
        for identifier in ('wan22-i2v', 'wan22-t2v'):
            with self.subTest(preset=identifier):
                preset = catalogue()[identifier]
                spec = preset.get('wan_decode_capacity')
                self.assertIsInstance(spec, dict)
                self.assertEqual(spec['version'], 1)
                graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
                self.assertTrue(spec['latents'])
                for latent in spec['latents']:
                    self.assertEqual(latent['shape'], {k: graph[latent['node']]['inputs'][k] for k in ('width', 'height', 'length', 'batch_size')})
                self.assertEqual(spec['limits']['max_pixels'], 512 * 768)
        self.assertNotIn('wan_decode_capacity', catalogue()['anima-v1-baseline'])

    def test_projection_covers_companions_and_ignores_disconnected_nodes(self):
        project = getattr(wan_capacity, 'projection', None)
        self.assertTrue(callable(project), 'Capacity projection is missing')
        preset = catalogue()['wan22-i2v']
        graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
        # Bind only a companion width; the raw graph, not defaults or names, is authoritative.
        preset.pop('width')
        preset['bindings_extra'] = {'width': [['7', 'width']]}
        graph['unused'] = {'class_type': 'Wan22ImageToVideoLatent', 'inputs': {'width': 2048}}
        before = copy.deepcopy((preset, graph))
        spec = project(preset, graph)
        self.assertEqual([row['node'] for row in spec['latents']], ['7'])
        self.assertIn({'control': 'width', 'input': 'width'}, spec['latents'][0]['bindings'])
        self.assertEqual((preset, graph), before)
        graph['10']['class_type'] = 'VAEDecodeTiled'
        self.assertIsNone(project(preset, graph), 'Tiled decode is not certified by this ordinary-decoder contract')

    def test_noninteger_literals_cannot_become_valid_by_json_round_trip(self):
        preset = catalogue()['wan22-t2v']
        for value in (1.0, True, '1', None):
            with self.subTest(value=repr(value)):
                graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
                node = str(preset['width'][0])
                graph[node]['inputs']['batch_size'] = value
                spec = wan_capacity.projection(preset, graph)
                # In JavaScript 1.0 is indistinguishable from 1, unlike the Python guard.
                self.assertIsNone(spec['latents'][0]['shape']['batch_size'])
                self.assertEqual(graph[node]['inputs']['batch_size'], value)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for real Create contracts')
    def test_browser_blockers_match_actual_graph_capacity(self):
        presets = catalogue()
        cases = []
        for identifier, mode, overrides in (
            ('wan22-t2v', None, {}),
            ('wan22-t2v', None, {'frames': '33'}),
            ('wan22-t2v', None, {'frames': '81'}),
            ('wan22-i2v', 'quick-diagnostic', {}),
            ('wan22-i2v', 'balanced', {'frames': '81'}),
            ('wan22-i2v', 'balanced', {'width': '1024', 'height': '256'}),
            ('wan22-i2v', 'balanced', {'width': '768', 'height': '768'}),
            ('wan22-i2v', 'quality', {'width': '512', 'height': '768', 'frames': '33'}),
            ('wan22-i2v', 'balanced', {'width': '768', 'height': '512'}),
            ('wan22-i2v', 'balanced', {'frames': ''}),
        ):
            preset = presets[identifier]
            mode_values = next((m['controls'] for m in preset.get('i2v_modes', []) if m['id'] == mode), {})
            values = dict(preset['defaults'], **mode_values); values.update(overrides)
            graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
            for key in ('frames', 'width', 'height'):
                value = values.get(key)
                if value == '': value = mode_values.get(key)
                if value is None: continue
                for binding in ([preset[key]] if preset.get(key) else []) + preset.get('bindings_extra', {}).get(key, []):
                    graph[str(binding[0])]['inputs'][binding[1]] = int(value)
            blocked = False
            try: wan_capacity.enforce(graph)
            except ValueError: blocked = True
            cases.append({'name': f'{identifier}/{mode}/{overrides}', 'preset': preset, 'mode': mode, 'values': values, 'blocked': blocked})
        result = subprocess.run(['node', str(ROOT / 'tests/wan_readiness.cjs')], input=json.dumps(cases), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__': unittest.main()
