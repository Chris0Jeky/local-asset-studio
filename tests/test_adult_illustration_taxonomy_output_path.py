"""Nested --out parent creation with exclusive no-overwrite behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "studio_adult_illustration_taxonomy.py"

_spec = importlib.util.spec_from_file_location(
    "studio_adult_illustration_taxonomy_under_test", _SCRIPT
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class TaxonomyOutputPathTests(unittest.TestCase):
    def test_nested_out_creates_parents_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = (
                Path(directory).resolve()
                / "adult-illustration"
                / "nested"
                / "taxonomy-index.json"
            )
            first = b'{"schema":"probe"}\n'
            second = b'{"schema":"other"}\n'
            self.assertFalse(target.exists())
            _module._write_new(target, first)
            self.assertTrue(target.parent.is_dir())
            self.assertEqual(target.read_bytes(), first)
            with self.assertRaisesRegex(ValueError, "already exists"):
                _module._write_new(target, second)
            self.assertEqual(target.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
