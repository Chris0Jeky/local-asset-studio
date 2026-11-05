"""Run the production rasterizer/NPZ writer over synthetic meshes; this is not native Blender evidence."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

try: import numpy as np
except ImportError: np = None

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vrm_posmap_bpy.py"


class Texture:
    def __init__(self):
        self.name, self.size = "base-colour", (8, 4)
        self.filepath = str((ROOT / "tests" / "fixture-texture.png").resolve())
        self.saved = []

    @property
    def filepath_raw(self): return self.filepath

    @filepath_raw.setter
    def filepath_raw(self, value): self.filepath = value

    def save(self):
        from PIL import Image
        Image.new("RGB", self.size, (120, 160, 200)).save(self.filepath)
        self.saved.append(Path(self.filepath).name)


def material(name, image):
    return SimpleNamespace(name=name, node_tree=SimpleNamespace(nodes=[SimpleNamespace(type="TEX_IMAGE", image=image)]))


def mesh(name, mat, u0=0.0, u1=1.0, translation=(0, 0, 0)):
    vertices = [SimpleNamespace(co=co) for co in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
    uvs = [SimpleNamespace(uv=uv) for uv in ((u0, 0), (u1, 0), (u1, 1), (u0, 1))]
    triangles = [SimpleNamespace(material_index=0, loops=ids, vertices=ids) for ids in ((0, 1, 2), (0, 2, 3))]
    data = SimpleNamespace(vertices=vertices, materials=[mat], loop_triangles=triangles, calc_loop_triangles=lambda: None,
                           uv_layers=SimpleNamespace(active=SimpleNamespace(data=uvs)))
    matrix = np.eye(4); matrix[:3, 3] = translation
    return SimpleNamespace(name=name, type="MESH", data=data, matrix_world=matrix)


@unittest.skipUnless(np is not None, "numpy not installed (Blender bundles it); no position-map raster check ran")
class PositionMapTests(unittest.TestCase):
    def bake(self, objects):
        bpy = SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=objects)),
                              path=SimpleNamespace(abspath=lambda path: str(Path(path).resolve())))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(sys.modules, {"bpy": bpy}), \
                mock.patch.object(sys, "argv", [str(SCRIPT), "--", tmp]), redirect_stdout(io.StringIO()):
            runpy.run_path(str(SCRIPT), run_name="__main__")
            result = {}
            for path in Path(tmp).glob("*.npz"):
                with np.load(path) as data: result[path.stem] = {key: data[key].copy() for key in data.files}
            return result, sorted(path.name for path in Path(tmp).iterdir())

    def test_shared_material_merges_disjoint_meshes_with_world_positions_and_top_down_rows(self):
        image = Texture(); source = image.filepath; skin = material("Skin", image)
        left = mesh("A_Left", skin, 0, .5, (1, 2, 3))
        right = mesh("B_Right", skin, .5, 1, (10, 20, 30))
        maps, files = self.bake([right, left])
        out = maps["Skin"]
        self.assertTrue(out["mask"].all(), "Both non-overlapping UV halves must survive in the one material map")
        self.assertEqual(set(out), {"pos", "mask", "image", "path"})
        self.assertEqual(out["pos"].shape, (4, 8, 3)); self.assertEqual(out["pos"].dtype, np.float32)
        self.assertEqual(out["mask"].dtype, np.bool_)
        np.testing.assert_allclose(out["pos"][0, 0], [1.125, 2.875, 3])
        np.testing.assert_allclose(out["pos"][3, 7], [10.875, 20.125, 30])
        self.assertEqual(out["image"].item(), image.name); self.assertEqual(out["path"].item(), source)
        self.assertEqual(files, ["Skin.npz", "Skin__src.png"])
        self.assertEqual(image.saved, ["Skin__src.png"])

    def test_overlaps_choose_the_last_object_name_regardless_of_scene_iteration(self):
        results = []
        for reverse in (False, True):
            image = Texture(); skin = material("Skin", image)
            objects = [mesh("A_Lower", skin, translation=(0, 0, 1)), mesh("Z_Upper", skin, translation=(0, 0, 2))]
            maps, _ = self.bake(list(reversed(objects)) if reverse else objects)
            out = maps["Skin"]; self.assertTrue(out["mask"].all())
            np.testing.assert_array_equal(out["pos"][..., 2], 2)
            results.append(out["pos"])
        np.testing.assert_array_equal(results[0], results[1])

    def test_distinct_materials_using_one_image_keep_separate_coverage_and_source_paths(self):
        image = Texture(); source = image.filepath
        skin, cloth = material("Skin", image), material("Cloth", image)
        maps, files = self.bake([mesh("Left", skin, 0, .5), mesh("Right", cloth, .5, 1)])
        self.assertEqual(set(maps), {"Skin", "Cloth"})
        self.assertTrue(maps["Skin"]["mask"][:, :4].all()); self.assertFalse(maps["Skin"]["mask"][:, 4:].any())
        self.assertFalse(maps["Cloth"]["mask"][:, :4].any()); self.assertTrue(maps["Cloth"]["mask"][:, 4:].all())
        for out in maps.values(): self.assertEqual(out["path"].item(), source)
        self.assertEqual(files, ["Cloth.npz", "Cloth__src.png", "Skin.npz", "Skin__src.png"])


if __name__ == "__main__": unittest.main()
