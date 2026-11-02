import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_corpus as corpus

LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


class CorpusContractTests(unittest.TestCase):
    def test_every_corpus_defect_has_a_description_and_requested_kinds_are_present(self):
        defects = corpus.lab.bpy_side.CORPUS_DEFECTS
        self.assertTrue(all(isinstance(text, str) and text for text in defects.values()))
        self.assertLessEqual({"flipped-normals", "missing-uvs", "broken-weights"}, set(defects))

    def test_build_refuses_an_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            with self.assertRaises(corpus.lab.BlenderLabError): corpus.build(exe, tmp)


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live corpus build")
class LiveCorpusTests(unittest.TestCase):
    def test_a_real_asset_source_records_inapplicable_defects(self):
        import articulated_prop
        with tempfile.TemporaryDirectory() as tmp:
            articulated_prop.execute(Path(tmp) / "chest", {"render_size": 64, "samples": 1}, LIVE_BLENDER)
            result = corpus.build(LIVE_BLENDER, Path(tmp) / "corpus", source=Path(tmp) / "chest" / "chest.blend")
        self.assertIn("shape-key-damage", result["not_applicable"])  # the chest has no shape keys
        self.assertIn("material-mismatch", {e["id"] for e in result["entries"]})
        self.assertTrue(result["summary"]["control_clean"])

    def test_corpus_labels_every_defect_and_the_control_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = corpus.build(LIVE_BLENDER, Path(tmp) / "corpus")
            self.assertTrue((Path(tmp) / "corpus" / "corpus.json").is_file())
        self.assertEqual(len(result["entries"]), len(corpus.lab.bpy_side.CORPUS_DEFECTS) + 1)
        self.assertTrue(result["summary"]["control_clean"])
        self.assertEqual(result["summary"]["missed"], [])
        for entry in result["entries"]:
            self.assertEqual(entry["expected"] == "clean", entry["id"] == "control")


if __name__ == "__main__":
    unittest.main()
