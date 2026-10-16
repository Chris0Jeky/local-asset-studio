"""Provenance guards for app/references.image_record: traversal escape and animation."""
import hashlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "references", Path(__file__).resolve().parents[1] / "app/references.py"
)
references = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(references)


def make_png(width=7, height=5, color="red"):
    stream = io.BytesIO()
    Image.new("RGB", (width, height), color).save(stream, "PNG")
    return stream.getvalue()


def make_gif(width=6, height=4):
    first = Image.new("RGB", (width, height), "red")
    second = Image.new("RGB", (width, height), "blue")
    stream = io.BytesIO()
    first.save(stream, format="GIF", save_all=True, append_images=[second], loop=0)
    return stream.getvalue()


class ImageRecordProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        self.png_bytes = make_png()
        (self.root / "valid.png").write_bytes(self.png_bytes)
        # Escape target exists outside the root so the traversal assert only
        # passes when the containment guard rejects it; without the guard the
        # call would succeed by reading this file.
        (Path(self.tmp.name) / "x.png").write_bytes(make_png())
        (self.root / "anim.gif").write_bytes(make_gif())

    def test_valid_png_returns_sha256_dimensions(self):
        record = references.image_record(self.root, "valid.png")
        self.assertEqual(record["file"], "valid.png")
        self.assertEqual(record["sha256"], hashlib.sha256(self.png_bytes).hexdigest())
        self.assertEqual(record["bytes"], len(self.png_bytes))
        self.assertEqual((record["width"], record["height"]), (7, 5))

    def test_traversal_name_is_rejected(self):
        with self.assertRaises(ValueError):
            references.image_record(self.root, "../x.png")

    def test_animated_gif_is_rejected(self):
        with Image.open(io.BytesIO((self.root / "anim.gif").read_bytes())) as probe:
            self.assertEqual(probe.n_frames, 2)
        with self.assertRaises(ValueError):
            references.image_record(self.root, "anim.gif")


if __name__ == "__main__":
    unittest.main()
