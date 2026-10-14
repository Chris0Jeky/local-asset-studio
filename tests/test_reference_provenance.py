"""Pin app/references.image_record traversal guard: escape rejects, in-root succeeds."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "references", Path(__file__).resolve().parents[1] / "app/references.py"
)
references = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(references)


def _save_png(path):
    Image.new("RGB", (8, 6), "teal").save(path, "PNG")


class ReferenceProvenanceTests(unittest.TestCase):
    def test_image_record_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            root = tmp_path / "root"
            root.mkdir()
            _save_png(root / "inside.png")
            # A real escape target makes this fail if containment is removed.
            _save_png(tmp_path / "outside.png")
            with self.assertRaisesRegex(ValueError, "unavailable"):
                references.image_record(root, "../outside.png")
            record = references.image_record(root, "inside.png")
            self.assertEqual(record["file"], "inside.png")
            self.assertEqual((record["width"], record["height"]), (8, 6))
