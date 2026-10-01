"""Materialize collision contract: a retained directory/marker retries as ValueError."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import project_storage


def _plan():
    base = {'kind': 'comparison', 'name': 'collision fixture'}
    base['sha256'] = hashlib.sha256(project_storage._canonical(base)).hexdigest()
    return base


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


class MaterializeCollisionTests(unittest.TestCase):
    def test_materialize_collision_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identifier = 'a' * 32
            plan = _plan()
            # Fresh create still succeeds.
            project_storage.materialize(root, identifier, plan, _write_json)
            marker = root / identifier / project_storage.MARKER
            self.assertTrue(marker.is_file())
            original = (root / identifier / 'plan.json').read_bytes()
            # Retry with the retained directory plus marker collides as ValueError.
            try:
                project_storage.materialize(root, identifier, plan, _write_json)
            except FileExistsError:
                self.fail('collision raised FileExistsError instead of ValueError')
            except ValueError as exc:
                self.assertIn('already exists', str(exc))
            else:
                self.fail('collision did not raise ValueError')
            # The existing directory is never overwritten.
            self.assertEqual((root / identifier / 'plan.json').read_bytes(), original)
            self.assertTrue(marker.is_file())


if __name__ == '__main__':
    unittest.main()
