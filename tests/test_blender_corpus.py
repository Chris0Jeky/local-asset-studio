import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_corpus as corpus
import blender_material_qualification as material_qualification

LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")
if os.environ.get("LAS_REQUIRE_MATERIAL_NATIVE") == "1" and not LIVE_BLENDER:
    raise RuntimeError("Required material qualification lacks explicit LAS_BLENDER_LAB_EXE executable")


class CorpusContractTests(unittest.TestCase):
    def test_every_corpus_defect_has_a_description_and_requested_kinds_are_present(self):
        defects = corpus.lab.bpy_side.CORPUS_DEFECTS
        self.assertTrue(all(isinstance(text, str) and text for text in defects.values()))
        self.assertLessEqual({"flipped-normals", "missing-uvs", "broken-weights"}, set(defects))

    def test_build_refuses_an_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            with self.assertRaises(corpus.lab.BlenderLabError): corpus.build(exe, tmp)


class Material:
    """Model only Blender ID user counting; native save/reopen coverage is opt-in below."""
    def __init__(self, name):
        self.name, self.real_users, self.use_fake_user = name, 0, False

    @property
    def users(self): return self.real_users + int(self.use_fake_user)


class MaterialSlot:
    def __init__(self, material):
        self._material = None
        self.material = material

    @property
    def material(self): return self._material

    @material.setter
    def material(self, value):
        if self._material is not None: self._material.real_users -= 1
        self._material = value
        if value is not None: value.real_users += 1


class CorpusMaterialTests(unittest.TestCase):
    def scene(self, alternate=True, assigned=True):
        original, other, unused = [Material(name) for name in ("RedPaint", "WoodPaint", "Material")]
        def mesh(name, materials):
            return SimpleNamespace(name=name, type="MESH", hide_render=False, visible_get=lambda **_: True,
                                   data=SimpleNamespace(polygons=[]), material_slots=[MaterialSlot(m) for m in materials])
        target = mesh("Badge", [None, original] if assigned else [])
        objects = [target] + ([mesh("Body", [other])] if alternate else [])
        materials = [original, other, unused]
        bpy = SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=objects), view_layer=object()),
                              data=SimpleNamespace(materials=materials))
        return bpy, target, original, other, unused

    def test_material_repair_restores_the_original_membership_without_promoting_orphans(self):
        bpy, target, original, other, unused = self.scene()
        materials = bpy.data.materials; identities = [id(m) for m in materials]
        before = sorted(m.name for m in materials if m.users)
        with mock.patch.dict(sys.modules, {"bpy": bpy}):
            label = corpus.lab.bpy_side.corpus_defect("material-mismatch")
        self.assertEqual(label, {"kind": "material-mismatch", "object": "Badge", "slot": 1,
                                 "from": "RedPaint", "to": "WoodPaint"})
        self.assertTrue(original.use_fake_user)  # displaced material must survive a saved variant
        self.assertEqual(original.users, 1)
        self.assertFalse(other.use_fake_user)
        self.assertFalse(unused.use_fake_user)
        self.assertEqual(unused.users, 0)
        target.material_slots[label["slot"]].material = original
        self.assertEqual(sorted(m.name for m in materials if m.users), before)
        self.assertEqual([id(m) for m in materials], identities)

    def test_no_distinct_used_material_is_not_applicable_without_mutation(self):
        bpy, target, original, other, unused = self.scene(alternate=False)
        with mock.patch.dict(sys.modules, {"bpy": bpy}):
            with self.assertRaises(corpus.lab.bpy_side.NotApplicable):
                corpus.lab.bpy_side.corpus_defect("material-mismatch")
        self.assertIs(target.material_slots[1].material, original)
        self.assertEqual([m.users for m in bpy.data.materials], [1, 0, 0])
        self.assertFalse(any(m.use_fake_user for m in bpy.data.materials))

    def test_missing_material_slots_does_not_promote_orphans(self):
        bpy, *_ = self.scene(alternate=False, assigned=False)
        with mock.patch.dict(sys.modules, {"bpy": bpy}):
            with self.assertRaises(corpus.lab.bpy_side.NotApplicable):
                corpus.lab.bpy_side.corpus_defect("material-mismatch")
        self.assertFalse(any(m.use_fake_user for m in bpy.data.materials))

    def test_sentinel_self_test_keeps_its_existing_transient_material_behavior(self):
        bpy, target, original, other, unused = self.scene()
        with mock.patch.dict(sys.modules, {"bpy": bpy}):
            label = corpus.lab.bpy_side.seed_defect("material-mismatch")
        self.assertIs(target.material_slots[label["slot"]].material, other)
        self.assertEqual(original.users, 0)
        self.assertFalse(any(m.use_fake_user for m in bpy.data.materials))


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live corpus build")
class LiveCorpusTests(unittest.TestCase):
    def test_material_swap_repair_preserves_native_checksum_after_reopen(self):
        if os.environ.get("LAS_MATERIAL_EVIDENCE"):
            output = Path(os.environ["LAS_MATERIAL_EVIDENCE"])
        else:
            temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
            output = Path(temporary.name) / "material"
        receipt = material_qualification.qualify(LIVE_BLENDER, output)
        self.assertEqual(receipt["state"], "passed", receipt.get("error"))

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
