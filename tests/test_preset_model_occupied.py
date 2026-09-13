"""An invalid occupied destination is not an actionable missing-model download."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
from model_library import ModelLibrary
from model_requirements import requirements


class OccupiedDependencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.library = ModelLibrary(self.root, self.root/'comfy')
        self.asset = {'id': 'fixture-model', 'file': 'loras/fixture.safetensors', 'bytes': 9,
                      'sha256': 'a'*64, 'url': 'https://huggingface.co/example/model/resolve/main/fixture.safetensors'}
        (self.root/'models').mkdir()
        (self.root/'models/library.json').write_text(json.dumps({'assets': [self.asset]}), encoding='utf-8')
        self.target = self.library.models/self.asset['file']
        self.target.parent.mkdir(parents=True)
        self.preset = {'model_files': [self.asset['file']]}

    def observe(self):
        return requirements(self.library, self.preset, {}, self.library.models)[0]

    def test_empty_destination_is_preserved_and_install_is_not_offered(self):
        self.target.write_bytes(b'')
        row = self.observe()
        self.assertIs(row['present'], False); self.assertIs(row['occupied'], True)
        self.assertIs(row['installable'], False); self.assertIn('occupied', row['install_note'])
        self.assertIn('inspect', row['note']); self.assertEqual(self.target.read_bytes(), b'')
        self.assertEqual(list(self.library.state.iterdir()), [])

    def test_directory_destination_is_preserved_and_install_is_not_offered(self):
        self.target.mkdir(); child = self.target/'keep.txt'; child.write_bytes(b'keep')
        row = self.observe()
        self.assertIs(row['present'], False); self.assertIs(row['occupied'], True)
        self.assertIs(row['installable'], False); self.assertIn('occupied', row['install_note'])
        self.assertTrue(self.target.is_dir()); self.assertEqual(child.read_bytes(), b'keep')
        self.assertEqual(list(self.library.state.iterdir()), [])

    def test_absent_destination_still_offers_the_supported_install(self):
        row = self.observe()
        self.assertIs(row['present'], False); self.assertIs(row['occupied'], False)
        self.assertIs(row['installable'], True); self.assertIsNone(row['install_note'])
        self.assertFalse(self.target.exists()); self.assertEqual(list(self.library.state.iterdir()), [])

    def test_next_observation_distinguishes_empty_present_and_explicitly_removed(self):
        self.target.write_bytes(b'')
        self.assertFalse(self.observe()['installable'])
        self.target.write_bytes(b'synthetic')
        present = self.observe()
        self.assertIs(present['present'], True); self.assertIs(present['occupied'], True)
        self.assertIs(present['installable'], True)  # existing policy allows verification, not a UI Install button
        self.target.unlink()  # fixture's explicit operator action, never performed by the projector
        missing = self.observe()
        self.assertIs(missing['present'], False); self.assertIs(missing['occupied'], False)
        self.assertIs(missing['installable'], True)


if __name__ == '__main__': unittest.main()
