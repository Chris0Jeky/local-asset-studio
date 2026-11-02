import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vrm_toon


def glb(doc):
    body = json.dumps(doc).encode(); body += b" " * (-len(body) % 4)
    return struct.pack("<III", 0x46546C67, 2, 20 + len(body)) + struct.pack("<II", len(body), 0x4E4F534A) + body


SPRING_DOC = {
    "nodes": [{"name": "J_Bip_C_Hips"}, {"name": "Skirt0_1"}, {"name": "Skirt0_2"}, {"name": "Skirt0_end"}, {"name": "J_Bip_L_UpperLeg"}],
    "extensions": {"VRMC_springBone": {
        "colliders": [{"node": 4, "shape": {"capsule": {"offset": [0, 0, 0], "tail": [0, -.3, 0], "radius": .077}}},
                      {"node": 0, "shape": {"sphere": {"offset": [0, .05, 0], "radius": .11}}},
                      {"node": 0, "shape": {"capsule": {}}}],
        "colliderGroups": [{"colliders": [0]}, {"colliders": [1, 0]}, {"colliders": [2]}],
        "springs": [{"name": "Skirt0", "colliderGroups": [1, 0], "joints": [{"node": 1, "stiffness": .9, "dragForce": .25, "gravityPower": .05, "hitRadius": .02},
                                                  {"node": 2}, {"node": 3}]},
                    {"name": "lonely", "joints": [{"node": 2}]}]}}}


class MaterialRoleTests(unittest.TestCase):
    def test_vroid_names_map_to_toon_roles(self):
        cases = {"Face_00_SKIN": "face", "Body_00_SKIN": "skin", "Hair_00_HAIR": "hair", "HairBack_00_HAIR": "hair",
                 "Braid_00_HAIR": "hair", "EyeIris_00_EYE": "unlit", "EyeHighlight_00_EYE": "unlit", "FaceMouth_00_FACE": "unlit",
                 "FaceBrow_00_FACE": "unlit", "Tops_01_CLOTH": "cloth", "Skirt_00_CLOTH": "cloth", "Material.001": "cloth"}
        for name, role in cases.items():
            with self.subTest(name=name): self.assertEqual(vrm_toon.material_role(name), role)

    def test_every_lit_role_has_a_shade_colour(self):
        for role in ("face", "skin", "hair", "cloth"):
            self.assertEqual(len(vrm_toon.SHADE[role]), 3); self.assertTrue(all(0 < c < 1 for c in vrm_toon.SHADE[role]))


class SdfThresholdTests(unittest.TestCase):
    MARKS = dict(eye_z=1.46, nose_z=1.41, nose_y=-.089)

    def t(self, x, z=1.46, y=-.05, w=.088): return vrm_toon.sdf_threshold(x, z, y, w, **self.MARKS)

    def test_terminator_sweeps_from_far_cheek_to_near_cheek(self):
        self.assertAlmostEqual(self.t(-.088), 0.0, places=6)          # far edge: lit only by a frontal light
        self.assertAlmostEqual(self.t(0.0), 0.5, places=6)            # centre line: lit up to a side light
        self.assertAlmostEqual(self.t(.088), 1.0, places=6)           # near edge: lit until the light is behind
        xs = [i / 100 * .088 for i in range(-100, 101, 5)]
        self.assertEqual([self.t(x) for x in xs], sorted(self.t(x) for x in xs))

    def test_crescent_bows_the_terminator_above_and_below_the_eyes(self):
        self.assertLess(self.t(0.0, z=1.54), self.t(0.0, z=1.46))
        self.assertLess(self.t(0.0, z=1.38), self.t(0.0, z=1.46))

    def test_nose_lobe_shades_early_only_at_the_front_of_the_face(self):
        front, back = self.t(-.008, z=1.41, y=-.085), self.t(-.008, z=1.41, y=-.01)
        self.assertLess(front, back - .05)
        self.assertAlmostEqual(self.t(.05, z=1.41, y=-.085), self.t(.05, z=1.41, y=-.01), places=3)

    def test_mirroring_x_gives_the_other_side(self):
        self.assertAlmostEqual(self.t(.03) + self.t(-.03), 1.0, places=6)


class LandmarkTests(unittest.TestCase):
    def test_landmarks_find_the_nose_and_widths_on_an_ellipsoid_face(self):
        pts = []
        for i in range(41):
            for j in range(40):
                th, ph = math.pi * i / 40, 2 * math.pi * j / 40           # a head-shaped ellipsoid, face toward -Y
                pts.append((.08 * math.sin(th) * math.cos(ph), -.09 * math.sin(th) * math.sin(ph), 1.47 + .11 * math.cos(th)))
        pts.append((0.0, -.11, 1.42))                                    # a nose tip proud of the surface
        marks = vrm_toon.face_landmarks(pts)
        self.assertAlmostEqual(marks["nose_z"], 1.42, places=6); self.assertAlmostEqual(marks["nose_y"], -.11, places=6)
        self.assertAlmostEqual(vrm_toon.width_at(marks["widths"], 1.47), .08, delta=.005)
        self.assertLess(vrm_toon.width_at(marks["widths"], 1.36), .03)


class SpringTests(unittest.TestCase):
    def test_chains_and_colliders_come_out_by_bone_name(self):
        out = vrm_toon.vrm_springs(SPRING_DOC)
        self.assertEqual(out["chains"], [{"name": "Skirt0", "root": "Skirt0_1", "end": "Skirt0_end", "joints": 3,
                                          "stiffness": .9, "drag": .25, "gravity": .05, "radius": .02, "colliders": [0, 1]}])
        self.assertEqual(out["colliders"][0], {"bone": "J_Bip_L_UpperLeg", "type": "capsule", "offset": [0, 0, 0], "tail": [0, -.3, 0], "radius": .077})
        self.assertEqual(out["colliders"][1]["type"], "sphere"); self.assertIsNone(out["colliders"][1]["tail"])
        self.assertEqual(out["colliders"][2], {"bone": "J_Bip_C_Hips", "type": "capsule", "offset": [0, 0, 0], "tail": [0, 0, 0], "radius": 0.0})

    def test_glb_round_trip_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "m.vrm", Path(d) / "s.json"; src.write_bytes(glb(SPRING_DOC))
            self.assertEqual(vrm_toon.read_glb_json(src)["nodes"][1]["name"], "Skirt0_1")
            self.assertEqual(vrm_toon.main(["springs", str(src), str(dst)]), 0)
            self.assertEqual(json.loads(dst.read_text(encoding="utf-8"))["chains"][0]["end"], "Skirt0_end")

    def test_rejects_non_glb_and_vrm0(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.vrm"; bad.write_bytes(b"glTF" + b"\0" * 30)
            with self.assertRaises(ValueError): vrm_toon.read_glb_json(bad)
            good = glb(SPRING_DOC)
            for name, data in {"version 1": good[:4] + struct.pack("<I", 1) + good[8:],
                               "declared too short": good[:8] + struct.pack("<I", 12) + good[12:]}.items():
                with self.subTest(name=name):
                    bad.write_bytes(data)
                    with self.assertRaises(ValueError): vrm_toon.read_glb_json(bad)
        with self.assertRaises(ValueError): vrm_toon.vrm_springs({"nodes": [], "extensions": {"VRM": {}}})


class ConstraintTests(unittest.TestCase):
    def test_aim_roll_and_rotation_constraints_by_name(self):
        doc = {"nodes": [{"name": "J_Bip_L_LowerArm"},
                         {"name": "J_Aim_L_TopsUpperArm", "extensions": {"VRMC_node_constraint": {"constraint": {"aim": {"source": 0, "aimAxis": "PositiveY", "weight": 1.0}}}}},
                         {"name": "J_Roll_L_Elbow", "extensions": {"VRMC_node_constraint": {"constraint": {"roll": {"source": 0, "rollAxis": "X", "weight": .5}}}}},
                         {"name": "Copy", "extensions": {"VRMC_node_constraint": {"constraint": {"rotation": {"source": 0}}}}}]}
        self.assertEqual(vrm_toon.vrm_constraints(doc), [
            {"bone": "J_Aim_L_TopsUpperArm", "type": "aim", "source": "J_Bip_L_LowerArm", "weight": 1.0, "axis": [0, 1, 0]},
            {"bone": "J_Roll_L_Elbow", "type": "roll", "source": "J_Bip_L_LowerArm", "weight": .5, "axis": [1, 0, 0]},
            {"bone": "Copy", "type": "rotation", "source": "J_Bip_L_LowerArm", "weight": 1.0, "axis": None}])

    def test_springs_cli_carries_constraints(self):
        doc = json.loads(json.dumps(SPRING_DOC)); doc["nodes"][2]["extensions"] = {"VRMC_node_constraint": {"constraint": {"aim": {"source": 1, "aimAxis": "NegativeZ"}}}}
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "m.vrm", Path(d) / "s.json"; src.write_bytes(glb(doc))
            self.assertEqual(vrm_toon.main(["springs", str(src), str(dst)]), 0)
            self.assertEqual(json.loads(dst.read_text(encoding="utf-8"))["constraints"][0]["axis"], [0, 0, -1])


class ExpressionTests(unittest.TestCase):
    def test_expression_binds_resolve_node_and_target_names(self):
        doc = {"nodes": [{"name": "Root"}, {"name": "Face", "mesh": 0}],
               "meshes": [{"extras": {"targetNames": ["Fcl_ALL_Neutral", "Fcl_ALL_Joy", "Fcl_EYE_Close"]}}],
               "extensions": {"VRMC_vrm": {"expressions": {
                   "preset": {"blink": {"morphTargetBinds": [{"node": 1, "index": 2, "weight": 1.0}]},
                              "happy": {"isBinary": True, "overrideBlink": "blend", "morphTargetBinds": [{"node": 1, "index": 1}]},
                              "lookUp": {"morphTargetBinds": []}},
                   "custom": {"wink": {"morphTargetBinds": [{"node": 1, "index": 9, "weight": .5}]}}}}}}
        out = vrm_toon.vrm_expressions(doc)
        self.assertEqual(out["blink"], {"binds": [{"node": "Face", "node_index": 1, "index": 2, "weight": 1.0, "name": "Fcl_EYE_Close"}],
                                        "binary": False, "override_blink": "none", "override_mouth": "none"})
        self.assertTrue(out["happy"]["binary"]); self.assertEqual(out["happy"]["binds"][0]["weight"], 1.0)
        self.assertEqual(out["happy"]["override_blink"], "blend")
        self.assertNotIn("lookUp", out)                                  # bone-driven, no morph binds
        self.assertIsNone(out["wink"]["binds"][0]["name"])               # index past the names list keeps the index only


if __name__ == "__main__":
    unittest.main()
