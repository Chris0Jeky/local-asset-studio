"""Full host contract tests with synthetic worker artifacts and real PNG comparisons."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_sentinel as sentinel

FIXTURES = ROOT / "tests" / "fixtures" / "blender_lab"
MANIFEST = json.loads((FIXTURES / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((FIXTURES / "sentinel-result-material-mismatch-5.4.0-alpha.json").read_text(encoding="utf-8"))
VIEWS = ("front", "three_quarter", "profile", "back")
PASSES = ("lit", "clay", "object_id", "material_id")
FILES = [f"{view}.{pass_name}.png" for view in VIEWS for pass_name in PASSES]


class WorkerReceipts:
    def __init__(self, root, source_files=None, roundtrip_files=None, change_source=False):
        self.root, self.calls = root, []
        self.source, self.exe, self.output = root / "synthetic.blend", root / "blender", root / "output"
        self.original = b"synthetic original blend bytes"
        self.source.write_bytes(self.original)
        self.exe.write_bytes(b"synthetic configured executable")
        self.files = {"source": FILES if source_files is None else source_files,
                      "roundtrip": FILES if roundtrip_files is None else roundtrip_files}
        self.change_source = change_source

    def worker(self, executable, args, log_path, timeout):
        def arg(name): return Path(args[args.index(name) + 1])
        role = "source" if "--blend" in args else "roundtrip"
        self.calls.append(role)
        directory = arg("--out-dir")
        (directory / "renders").mkdir(parents=True)
        (directory / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
        evidence = {**copy.deepcopy(SAMPLE["render"]), "camera_spec": copy.deepcopy(SAMPLE["cameras"]),
                    "palette": {"object": {}, "material": {}}, "files": self.files[role]}
        (directory / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
        # Write only owned, fixed image paths, even for intentionally malformed receipt names.
        for name in FILES:
            if name not in self.files[role]: continue
            image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            image.paste((255, 0, 0, 255), (64, 64, 192, 192))
            image.save(directory / "renders" / name)
        record = {"kind": "evidence", "seeded_defect": None}
        if role == "source":
            arg("--export").write_bytes(b"synthetic exported GLB")
            record["export"] = {"settings": sentinel.lab.bpy_side.LAS_GLTF_SETTINGS}
        elif self.change_source:
            self.source.write_bytes(b"concurrent save during second process")
        arg("--out").write_text(json.dumps(record), encoding="utf-8")
        Path(log_path).write_text(json.dumps({"fixture": "synthetic worker", "returncode": 0}), encoding="utf-8")
        return 0.01

    def run(self):
        with patch.object(sentinel.lab, "run", side_effect=self.worker):
            return sentinel.sentinel(self.exe, self.source, self.output)


class SentinelReceiptTests(unittest.TestCase):
    def test_complete_control_compares_all_images_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = WorkerReceipts(Path(tmp), roundtrip_files=list(reversed(FILES)))
            result = fixture.run()
            self.assertEqual(fixture.calls, ["source", "roundtrip"])
            self.assertTrue(result["pass"])
            self.assertEqual(set(result["views"]), set(VIEWS))
            self.assertTrue(all(set(view) == set(PASSES) for view in result["views"].values()))
            self.assertTrue(result["source"]["unchanged"])
            self.assertEqual(fixture.source.read_bytes(), fixture.original)
            self.assertTrue((fixture.output / "result.json").is_file())

    def test_source_change_during_roundtrip_refuses_success_and_keeps_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = WorkerReceipts(Path(tmp), change_source=True)
            with self.assertRaisesRegex(sentinel.lab.BlenderLabError, "Source .blend changed"):
                fixture.run()
            self.assertEqual(fixture.calls, ["source", "roundtrip"])
            self.assertTrue((fixture.output / "export.glb").is_file())
            self.assertTrue((fixture.output / "roundtrip" / "evidence.json").is_file())
            self.assertFalse((fixture.output / "result.json").exists())

    def test_source_is_rechecked_after_artifact_hashing_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = WorkerReceipts(Path(tmp))
            file_sha = sentinel.lab.file_sha

            def hash_with_late_save(path):
                digest = file_sha(path)
                if Path(path) == fixture.output / "cameras.json":
                    fixture.source.write_bytes(b"concurrent save during final artifact hashing")
                return digest

            with patch.object(sentinel.lab, "file_sha", side_effect=hash_with_late_save):
                with self.assertRaisesRegex(sentinel.lab.BlenderLabError, "Source .blend changed"):
                    fixture.run()
            self.assertTrue((fixture.output / "diff" / "front.lit.diff.png").is_file())
            self.assertFalse((fixture.output / "result.json").exists())

    def test_incomplete_duplicate_or_foreign_evidence_names_cannot_pass(self):
        bad_sets = {"empty": [], "missing": FILES[:-1], "duplicate": FILES[:-1] + [FILES[0]],
                    "extra": FILES + ["extra.lit.png"], "traversal": FILES[:-1] + ["../../outside.lit.png"],
                    "absolute": FILES[:-1] + ["/outside.lit.png"]}
        for case, names in bad_sets.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                fixture = WorkerReceipts(Path(tmp), source_files=names, roundtrip_files=names)
                with self.assertRaisesRegex(sentinel.lab.BlenderLabError, "complete unique evidence set"):
                    fixture.run()
                self.assertEqual(fixture.calls, ["source"])
                self.assertEqual(fixture.source.read_bytes(), fixture.original)
                self.assertTrue((fixture.output / "export.glb").is_file())
                self.assertFalse((fixture.output / "result.json").exists())
                self.assertFalse((fixture.root / "outside.lit.diff.png").exists())

    def test_roundtrip_also_requires_the_complete_unique_evidence_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = WorkerReceipts(Path(tmp), roundtrip_files=[])
            with self.assertRaisesRegex(sentinel.lab.BlenderLabError, "Roundtrip.*complete unique evidence set"):
                fixture.run()
            self.assertEqual(fixture.calls, ["source", "roundtrip"])
            self.assertTrue((fixture.output / "source" / "renders" / "front.lit.png").is_file())
            self.assertFalse((fixture.output / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
