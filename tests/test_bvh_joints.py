import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bvh_joints

# Hips at the root with two legs and a foot/toe on the left; centimetres, Y up, facing +Z with left on +X.
BVH = """HIERARCHY
ROOT Hips
{
  OFFSET 0 90 0
  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
  JOINT Spine
  {
    OFFSET 0 10 0
    CHANNELS 3 Zrotation Xrotation Yrotation
    End Site
    {
      OFFSET 0 10 0
    }
  }
  JOINT UpperLeg_L
  {
    OFFSET 10 0 0
    CHANNELS 3 Zrotation Xrotation Yrotation
    JOINT Foot_L
    {
      OFFSET 0 -80 0
      CHANNELS 3 Zrotation Xrotation Yrotation
      JOINT Toes_L
      {
        OFFSET 0 0 10
        CHANNELS 3 Zrotation Xrotation Yrotation
        End Site
        {
          OFFSET 0 0 5
        }
      }
    }
  }
  JOINT UpperLeg_R
  {
    OFFSET -10 0 0
    CHANNELS 3 Zrotation Xrotation Yrotation
    End Site
    {
      OFFSET 0 -80 0
    }
  }
}
MOTION
Frames: 3
Frame Time: 0.0333333
"""


def frame(x, z, spine_x=0.0, leg_z=0.0):
    # Hips(6) Spine(3) UpperLeg_L(3) Foot_L(3) Toes_L(3) UpperLeg_R(3), rotations in Z X Y order
    return [x, 90, z, 0, 0, 0] + [0, spine_x, 0] + [leg_z, 0, 0] + [0, 0, 0] + [0, 0, 0] + [0, 0, 0]


class BvhJointsTests(unittest.TestCase):
    def convert(self, rows, turned=False):
        # turned: the whole figure rotated 180 degrees about Y (left on -X, toes on -Z), not mirrored
        text = re.sub(r"OFFSET (\S+) (\S+) (\S+)", lambda m: f"OFFSET {-float(m[1]):g} {m[2]} {-float(m[3]):g}", BVH) if turned else BVH
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "c.bvh", Path(d) / "c.json"
            src.write_text(text + "\n".join(" ".join(str(v) for v in r) for r in rows) + "\n", encoding="utf-8")
            bvh_joints.main(str(src), str(out)); return json.loads(out.read_text(encoding="utf-8"))

    def test_forward_kinematics_in_metres_facing_plus_z(self):
        f = self.convert([frame(0, 0)] * 3)["frames"][0]
        self.assertEqual(f["Hips"], [0.0, 0.9, 0.0])
        self.assertEqual(f["Spine"], [0.0, 1.0, 0.0])
        self.assertEqual(f["UpperLeg_L"], [0.1, 0.9, 0.0])           # left side on +X
        self.assertEqual(f["Toes_L"], [0.1, 0.1, 0.1])                # toes forward on +Z

    def test_relative_root_translation_adds_to_the_offset(self):
        rel = [[r[0], 0.0, r[2]] + r[3:] for r in [frame(0, 0)] * 3]          # channels relative to OFFSET 0 90 0
        f = self.convert(rel)["frames"][0]
        self.assertEqual(f["Hips"], [0.0, 0.9, 0.0])                     # not placed at height zero

    def test_rotation_channels_rotate_children(self):
        f = self.convert([frame(0, 0, leg_z=90)] * 3)["frames"][0]   # Z +90 at the left hip swings the leg toward +X
        self.assertAlmostEqual(f["Foot_L"][0], 0.9, places=4); self.assertAlmostEqual(f["Foot_L"][1], 0.9, places=4)
        f = self.convert([frame(0, 0, spine_x=90)] * 3)["frames"][0]  # X +90 at the spine root has no effect on its own offset end
        self.assertEqual(f["Spine"], [0.0, 1.0, 0.0])

    def test_facing_turns_a_figure_built_backwards(self):
        f = self.convert([frame(0, 0)] * 3, turned=True)["frames"][0]
        self.assertGreater(f["UpperLeg_L"][0], 0)                    # left forced back onto +X
        self.assertGreater(f["Toes_L"][2] - f["Foot_L"][2], 0)       # and toes still point to +Z

    def test_travel_is_put_on_plus_z_without_drift(self):
        d = self.convert([frame(0, 0), frame(20, 30), frame(40, 60)])
        a, b = d["frames"][0]["Hips"], d["frames"][-1]["Hips"]
        self.assertAlmostEqual(b[0] - a[0], 0.0, places=4)
        self.assertAlmostEqual(b[2] - a[2], (0.4 ** 2 + 0.6 ** 2) ** 0.5, places=4)
        self.assertEqual(d["fps"], 30.0)


if __name__ == "__main__":
    unittest.main()
