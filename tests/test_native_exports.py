import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
try:
    from PIL import Image
except ImportError:
    Image = None
from native_exports import NativeExportError, NativeExports


@unittest.skipUnless(Image is not None, "Optional Pillow not installed")
class NativeExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.media = self.root / "media"
        self.media.mkdir()
        for name, color in (("first.png", (255, 0, 0, 255)), ("second.png", (0, 0, 255, 255))):
            Image.new("RGBA", (4, 6), color).save(self.media / name)
        self.exports = NativeExports(ROOT, self.media)

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, name, asset_id):
        path = self.media / name
        return {"id": asset_id, "path": name, "filename": name, "media_type": "image/png",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_rejects_escape_and_hash_mismatch(self):
        outside = self.root / "outside.png"
        outside.write_bytes((self.media / "first.png").read_bytes())
        escaped = self.asset("first.png", "first-frame")
        escaped["path"] = "../outside.png"
        with self.assertRaises(NativeExportError):
            self.exports.execute(self.root / "escaped", "atlas", [escaped], {})
        wrong = self.asset("first.png", "first-frame")
        wrong["sha256"] = "0" * 64
        with self.assertRaises(NativeExportError):
            self.exports.execute(self.root / "wrong", "atlas", [wrong], {})

    def test_atlas_preserves_order_and_variable_timing(self):
        result = self.exports.execute(self.root / "atlas-out", "atlas",
                                      [self.asset("first.png", "first-frame"), self.asset("second.png", "second-frame")],
                                      {"clip": "idle-test", "duration_ms": [80, 140], "anchor": [2, 6],
                                       "loop": False, "filter": "linear", "columns": 1})
        manifest = __import__("json").loads((self.root / "atlas-out/atlas/manifest.json").read_text())
        self.assertEqual([frame["id"] for frame in manifest["frames"]], ["first-frame", "second-frame"])
        self.assertEqual([frame["duration_ms"] for frame in manifest["frames"]], [80, 140])
        self.assertEqual(manifest["anchor"], [2, 6])
        self.assertEqual(manifest["filter"], "linear")
        self.assertIn("native-sources.zip", [artifact["path"] for artifact in result["artifacts"]])
        with zipfile.ZipFile(self.root / "atlas-out/native-sources.zip") as archive:
            self.assertIn("recipe.json", archive.namelist())
            self.assertIn("sources/00-first-frame.png", archive.namelist())

    def test_ora_round_trips_topmost_names(self):
        self.exports.execute(self.root / "ora-out", "ora",
                             [self.asset("first.png", "first-frame"), self.asset("second.png", "second-frame")],
                             {"clip": "layers-test", "layer_names": ["Top red", "Bottom blue"]})
        with zipfile.ZipFile(self.root / "ora-out/layers.ora") as archive:
            doc = ET.fromstring(archive.read("stack.xml"))
        self.assertEqual([layer.get("name") for layer in doc.findall("stack/layer")], ["Top red", "Bottom blue"])


if __name__ == "__main__":
    unittest.main()
