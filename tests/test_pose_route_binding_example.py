"""The documented pose-route binding commands must run without private media."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'pose_route_binding.py'


class PoseRouteBindingExampleTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=ROOT, text=True, capture_output=True, timeout=20)

    def test_synthetic_bundle_compiles_validates_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            example = root / 'example'
            result = self.cli('write-example', example)
            self.assertEqual(result.returncode, 0, result.stderr)
            created = json.loads(result.stdout)
            self.assertFalse(created['ready_for_execution'])
            self.assertFalse(created['execution_authorized'])
            self.assertFalse(created['generation_submitted'])
            for name in ('request.json', 'source.png', 'artifact.json'):
                self.assertTrue((example / name).is_file())

            binding = root / 'binding.json'
            result = self.cli(
                'compile', example / 'request.json',
                '--source', example / 'source.png',
                '--artifact', example / 'artifact.json',
                '--out', binding)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertFalse(receipt['ready_for_execution'])
            self.assertFalse(receipt['generation_submitted'])
            self.assertTrue(binding.is_file())

            result = self.cli(
                'validate-binding', example / 'request.json', binding,
                '--source', example / 'source.png',
                '--artifact', example / 'artifact.json')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['binding_id'], receipt['binding_id'])

            original = {path.name: path.read_bytes() for path in example.iterdir()}
            result = self.cli('write-example', example)
            self.assertEqual(result.returncode, 2)
            self.assertIn('already exists', json.loads(result.stderr)['error'])
            self.assertEqual(
                {path.name: path.read_bytes() for path in example.iterdir()}, original)


if __name__ == '__main__':
    unittest.main()
