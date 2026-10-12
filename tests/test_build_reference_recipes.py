"""Atomic JSON publication for the Qwen reference recipe builder."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'reference_recipes_under_test', ROOT / 'scripts/build-reference-recipes.py')


def load_module():
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    return module


def minimal_graph():
    return {
        '4': {'class_type': 'LoadImage', 'inputs': {'image': 'old.png'}},
        '16': {'class_type': 'LoadImage', 'inputs': {'image': 'old.png'}},
        '17': {'class_type': 'LoadImage', 'inputs': {'image': 'old.png'}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'prompt': 'old'}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'prompt': 'neg'}},
        '11': {'class_type': 'KSampler', 'inputs': {'seed': 1, 'steps': 4, 'cfg': 1.0}},
        '13': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'old'}},
    }


class PublishTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.module = load_module()

    def test_roundtrip_writes_valid_json_with_no_tmp_left(self):
        target = Path(self.tmp.name) / 'out.json'
        raw = json.dumps({'a': 1}, indent=2) + '\n'
        self.module._publish_text(target, raw)
        self.assertEqual(target.read_text(encoding='utf-8'), raw)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'a': 1})
        self.assertEqual(list(Path(self.tmp.name).glob('*.tmp')), [])

    def test_torn_replace_leaves_original_valid_json(self):
        target = Path(self.tmp.name) / 'keep.json'
        original = json.dumps({'kept': True}, indent=2) + '\n'
        target.write_text(original, encoding='utf-8')
        with patch.object(Path, 'replace', side_effect=OSError('injected torn replace')):
            with self.assertRaises(OSError):
                self.module._publish_text(target, json.dumps({'new': True}) + '\n')
        # A direct write_text would have truncated the target; the atomic
        # sibling-.tmp publish must leave the original bytes intact.
        self.assertEqual(target.read_text(encoding='utf-8'), original)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'kept': True})
        self.assertEqual(list(Path(self.tmp.name).glob('*.tmp')), [])

    def test_readback_rejects_truncated_publish(self):
        target = Path(self.tmp.name) / 'torn.json'
        intended = json.dumps({'full': [1, 2, 3]}, indent=2) + '\n'
        real_replace = Path.replace

        def torn_replace(self, other):
            result = real_replace(self, other)
            Path(other).write_bytes(b'{')
            return result

        with patch.object(Path, 'replace', torn_replace):
            with self.assertRaises(ValueError):
                self.module._publish_text(target, intended)
        self.assertNotEqual(target.read_bytes(), intended.encode('utf-8'))
        with self.assertRaises(ValueError):
            json.loads(target.read_bytes())

    def test_build_routes_api_visual_and_catalog_through_helper(self):
        module = self.module
        fake = Path(self.tmp.name) / 'fake-root'
        (fake / 'scripts').mkdir(parents=True)
        (fake / 'scripts/build-expansion.py').write_text(
            'def visual(graph, title, info):\n    return {"title": title}\n',
            encoding='utf-8')
        (fake / 'presets').mkdir(parents=True)
        (fake / 'presets/catalog.json').write_text(
            json.dumps({'presets': []}), encoding='utf-8')
        research = fake / 'research/game-assets/workflows'
        research.mkdir(parents=True)
        for count in (1, 2, 3):
            (research / f'qwen-{count}ref-api.json').write_text(
                json.dumps(minimal_graph()), encoding='utf-8')
        calls = []
        real_publish = module._publish_text

        def spy(path, raw):
            calls.append(str(path))
            return real_publish(path, raw)

        with patch.object(module, 'ROOT', fake), \
                patch.object(module, '_publish_text', side_effect=spy):
            module.build({})
        api = [c for c in calls if 'workflows/api/' in c.replace('\\', '/')]
        visual = [c for c in calls if 'workflows/comfyui/' in c.replace('\\', '/')]
        catalog = [c for c in calls if c.replace('\\', '/').endswith('presets/catalog.json')]
        self.assertEqual(len(api), 3)
        self.assertEqual(len(visual), 3)
        self.assertEqual(len(catalog), 1)
        for name in calls:
            self.assertEqual(json.loads(Path(name).read_text(encoding='utf-8')) is not None, True)
        self.assertEqual(list(fake.rglob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
