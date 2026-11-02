import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_active as active

MANIFEST = json.loads((ROOT / "tests" / "fixtures" / "blender_lab" / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json").read_text(encoding="utf-8"))
LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


class PlanTests(unittest.TestCase):
    def test_plan_frames_the_visible_meshes_and_picks_search_dimensions(self):
        spec, frames, weights = active.plan_from(MANIFEST)
        self.assertGreater(spec["ortho_scale"], 0)
        self.assertEqual(len(spec["target"]), 3)
        self.assertEqual(frames, [1, 13, 24])  # rig action range thinned to three frames
        self.assertEqual(weights, (0.0, 1.0))  # the lab asset has shape keys
        self.assertEqual(len(active.grid(frames, weights)), 8 * 3 * 3 * 2 * 2)

    def test_refine_steps_around_a_config_within_bounds(self):
        neighbours = active.refine({"azimuth": 350, "elevation": 75, "frame": 1, "shape_keys": 0.0, "backface_culling": False})
        self.assertEqual(len(neighbours), 8)
        self.assertTrue(all(0 <= n["azimuth"] < 360 and -80 <= n["elevation"] <= 80 for n in neighbours))
        self.assertIn(5, {n["azimuth"] for n in neighbours})

    def test_different_render_sizes_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.png", Path(tmp) / "b.png"
            Image.new("RGBA", (16, 16)).save(a); Image.new("RGBA", (8, 8)).save(b)
            with self.assertRaises(active.lab.BlenderLabError): active.changed_px(a, b)

    def test_corpus_entries_cannot_escape_their_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "corpus"; root.mkdir()
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            for entries in ([{"id": "control", "blend": "../outside.blend"}],
                            [{"id": "control", "blend": "a.blend"}, {"id": "../x", "blend": "b.blend"}], [{"id": "x", "blend": "a.blend"}]):
                (root / "corpus.json").write_text(json.dumps({"entries": entries}))
                with self.assertRaises(active.lab.BlenderLabError): active.corpus(exe, root, Path(tmp) / f"out{len(list(Path(tmp).iterdir()))}")

    def test_changed_px_uses_the_level_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.png", Path(tmp) / "b.png"
            Image.new("RGBA", (16, 16), (100, 100, 100, 255)).save(a)
            image = Image.new("RGBA", (16, 16), (100, 100, 100, 255)); image.paste((105, 100, 100, 255), (0, 0, 16, 8))
            image.paste((200, 100, 100, 255), (0, 8, 4, 16)); image.save(b)
            self.assertEqual(active.changed_px(a, b), 32)  # the +5 band stays under level 8


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live active search")
class LiveActiveTests(unittest.TestCase):
    def test_search_finds_a_pose_only_defect_and_leaves_the_control_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = active.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "asset")
            broken = clean.parent / "broken-weights.blend"
            active.lab.run(active.lab.executable(LIVE_BLENDER), ["corpus-variant", "--blend", clean, "--kind", "broken-weights",
                           "--out-blend", broken, "--out", Path(tmp) / "variant.json"], Path(tmp) / "variant.log.json")
            control, cache = active.search(LIVE_BLENDER, clean, clean, Path(tmp) / "control")
            found, _ = active.search(LIVE_BLENDER, clean, broken, Path(tmp) / "found", before_cache=cache)
        self.assertEqual(control["max_changed_px"], 0)  # identical revisions render identically, not merely below the gate
        self.assertTrue(found["detected"])
        self.assertEqual(found["best_with_default"]["frame"], 0)  # invisible at the rest frame


if __name__ == "__main__":
    unittest.main()
