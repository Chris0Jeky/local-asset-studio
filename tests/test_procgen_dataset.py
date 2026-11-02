import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import procgen_dataset as dataset
import procgen_factory as factory

SCHEMA = factory.load_schema()


class Sampling(unittest.TestCase):
    def test_samples_stay_in_bounds_and_satisfy_constraints(self):
        rng = random.Random(1)
        spec = SCHEMA["generators"]["room_kit"]
        for _ in range(200):
            p = dataset.sample_params(spec, rng)
            resolved, errors = factory.resolve_params(spec, p)
            self.assertEqual(errors, [])
            self.assertEqual(factory.check_constraints(spec, resolved), [])
            self.assertLessEqual(p["detail"], dataset.MAX_DETAIL)

    def test_fixed_values_and_seed_are_deterministic(self):
        spec = SCHEMA["generators"]["prop"]
        a = [dataset.sample_params(spec, random.Random(7), {"kind": 2}) for _ in range(3)]
        b = [dataset.sample_params(spec, random.Random(7), {"kind": 2}) for _ in range(3)]
        self.assertEqual(a, b)
        self.assertTrue(all(p["kind"] == 2 for p in a))

    def test_impossible_constraints_raise_instead_of_looping(self):
        spec = json.loads(json.dumps(SCHEMA["generators"]["room_kit"]))
        spec["constraints"].append({"terms": {"width": 1}, "le": 0.0, "doc": "impossible"})
        with self.assertRaises(factory.EvidenceError):
            dataset.sample_params(spec, random.Random(1), tries=20)


@unittest.skipUnless(os.environ.get("PROCGEN_LIVE_BLENDER"), "set PROCGEN_LIVE_BLENDER=<blender.exe> for the live round trip")
class LiveDataset(unittest.TestCase):
    def test_render_validate_and_seeded_defects(self):
        blender = os.environ["PROCGEN_LIVE_BLENDER"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builds = dataset.pool(root / "pool", blender, rooms=1, shrines=1, props_per_kind=1, seed=3)
            self.assertTrue(all(not b["failed_gates"] for b in builds.values()), builds)
            views = dataset.render(root / "pool", root / "data", blender, scenes=2, views=6)
            self.assertEqual(len(views), 12)
            summary = dataset.validate(root / "data", root / "pool", blender)
            self.assertEqual(summary["passed"], 12, summary)
            self.assertLess(summary["median_planar_rel_err"], 1e-4)       # Cycles Z is planar depth...
            self.assertGreater(summary["median_range_rel_err"], 1e-3)     # ...not range
            seeded = root / "seeded"; shutil.copytree(root / "data" / "scene_00", seeded / "scene_00")
            dataset._blender(blender, ["seed", (seeded / "scene_00").resolve()], seeded, "seed", 120)
            dataset.validate(seeded, root / "pool", blender, stride=4)
            report = json.loads((seeded / "label-validation.json").read_text(encoding="utf-8"))
            verdicts = {r["view"].split("/")[1]: r["passed"] for r in report["views"]}
            self.assertEqual(verdicts, {f"view_{i:02d}": i not in range(1, 6) for i in range(6)})
            self.assertGreater(report["views"][3]["full_image"]["bad_foreground_normals"], 0)   # odd rows only: full-image check sees them
            self.assertTrue(summary["certified"])
            # Incomplete or mislabelled datasets are not certified even when every remaining view is exact.
            broken = root / "broken"; shutil.copytree(root / "data" / "scene_01", broken / "scene_01")
            (broken / "scene_01" / "view_00" / "rgb.png").unlink()
            meta_path = broken / "scene_01" / "objects.json"; meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["objects"][-1]["class"] = "wall_back"; meta_path.write_text(json.dumps(meta), encoding="utf-8")
            bad = dataset.validate(broken, root / "pool", blender, stride=4)
            self.assertFalse(bad["certified"])
            self.assertTrue(any("missing ['rgb.png']" in p for p in bad["problems"]), bad["problems"])
            self.assertTrue(any("wall_back" in p for p in bad["problems"]), bad["problems"])
            dataset.validate(broken, root / "pool", blender, stride=4)                          # a rerun keeps the first logs
            self.assertTrue((broken / "validate1-exit.json").exists() and (broken / "validate2-exit.json").exists())


if __name__ == "__main__":
    unittest.main()
