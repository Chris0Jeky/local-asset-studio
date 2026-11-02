import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import procgen_factory as factory

SCHEMA = factory.load_schema()
HAS_NUMPY = importlib.util.find_spec("numpy") is not None


def crate_measurements(width=0.4, height=0.6):
    """A synthetic measurement that passes every mesh gate for a default crate."""
    spec = SCHEMA["generators"]["prop"]
    half = width / 2
    def part(pid, name, lo, hi):
        return {"id": pid, "name": name, "triangles": 12, "boundary_edges": 0, "nonmanifold_edges": 0,
                "inconsistent_edges": 0, "degenerate_faces": 0, "islands": [lo + hi], "bbox_min": lo, "bbox_max": hi,
                "origin": [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], "uv0_present": True, "uv0_finite": True,
                "uv1_present": True, "uv1_in_unit": True, "uv1_overlap_texels": 0, "uv1_degenerate": 0}
    lo, hi = [-half, -half, 0.0], [half, half, height]
    parts = lambda: [part(4, "crate_core", [-half + 0.02, -half + 0.02, 0.02], [half - 0.02, half - 0.02, height - 0.02]),
                     part(5, "crate_frame", lo, hi)]
    lod = lambda detail, tris: {"detail": detail, "glb": f"asset_LOD{detail}.glb", "bbox_min": list(lo), "bbox_max": list(hi),
                                "triangles": tris, "parts": parts()}
    return {"blender": {"version": "test", "hash": "0"},
            "gn_bounds": {k: [r["min"], r["max"]] for k, r in spec["params"].items() if r.get("gn", True)},
            "lods": [lod(16, 300), lod(8, 300), lod(4, 300)], "parts": parts(),
            "collision_objects": ["crate_core-colonly", "crate_frame-colonly"], "collision_boxes": 2, "unknown_part_ids": []}


def crate_params(**overrides):
    params, errors = factory.resolve_params(SCHEMA["generators"]["prop"], {"kind": 1, **overrides})
    assert not errors, errors
    return params


def failed(gates):
    return {g["gate"]: g["failures"] for g in gates if not g["passed"]}


class ParamsAndConstraints(unittest.TestCase):
    def test_defaults_fill_and_satisfy_constraints_for_every_generator(self):
        for name, spec in SCHEMA["generators"].items():
            params, errors = factory.resolve_params(spec, {})
            self.assertEqual(errors, [], name)
            self.assertEqual(set(params), set(spec["params"]))
            self.assertEqual(factory.check_constraints(spec, params), [], name)
            for part in spec["parts"].values():
                self.assertRegex(part["name"], factory.NAME_RE)

    def test_rejects_unknown_out_of_bounds_and_wrong_types_without_clamping(self):
        spec = SCHEMA["generators"]["room_kit"]
        params, errors = factory.resolve_params(spec, {"width": 9.0, "shelf_count": 3.0, "colour": "red", "depth": True,
                                                       "height": float("nan")})
        self.assertEqual(len(errors), 5, errors)
        self.assertNotIn("width", params)
        self.assertTrue(any("unknown parameter 'colour'" in e for e in errors))
        self.assertTrue(any("shelf_count must be an integer" in e for e in errors))

    def test_window_constraint_names_the_violated_rule(self):
        spec = SCHEMA["generators"]["room_kit"]
        params, _ = factory.resolve_params(spec, {"width": 2.4, "window_width": 2.4})
        failures = factory.check_constraints(spec, params)
        self.assertEqual(len(failures), 2)
        self.assertIn("window clears the right wall", failures[0])

    def test_shrine_platform_snaps_to_half_metre_grid(self):
        params, _ = factory.resolve_params(SCHEMA["generators"]["shrine"], {"gate_width": 2.6, "pillar_radius": 0.15, "step_count": 3})
        size, slack = factory.expected_bounds("shrine", params)
        self.assertEqual(size[0], 5.0)          # 1.3*2.6 + 0.6 = 3.98, +1 = 4.98 -> 5.0
        self.assertAlmostEqual(size[1], 3 * 0.32 + 3.0)
        self.assertEqual(slack, [0, 0, 0])

    def test_lighthouse_bounds_cover_panel_corners_and_floor_polygon(self):
        params, _ = factory.resolve_params(SCHEMA["generators"]["lighthouse_room"], {"radius": 2.0, "wall_thickness": 0.2, "panels": 12, "detail": 5})
        size, slack = factory.expected_bounds("lighthouse_room", params)
        rt = 2.2
        self.assertAlmostEqual(size[2], params["height"])
        self.assertAlmostEqual(size[0] / 2, rt / math.cos(math.pi / 12))          # n-gon vertices (panel corners, floor)
        self.assertAlmostEqual(size[0] * (1 - slack[0]), 2 * rt)                   # n-gon faces at the apothem
        self.assertEqual(slack[0], slack[1])

    def test_pier_bounds_follow_the_tallest_fixture(self):
        spec = SCHEMA["generators"]["pier"]
        lamps, _ = factory.resolve_params(spec, {"length": 8.0, "width": 2.0, "water_level": 0.5, "deck_height": 1.0, "lamps": 2})
        bare, _ = factory.resolve_params(spec, {"water_level": 0.5, "deck_height": 1.0, "lamps": 0, "railing": 0, "bollards": 0})
        self.assertEqual(factory.expected_bounds("pier", lamps)[0][:2], [8.0, 11.0])        # water plane: +6 wide, +3 long
        self.assertAlmostEqual(factory.expected_bounds("pier", lamps)[0][2], 1.5 + 2.72)     # lamp roof top
        self.assertAlmostEqual(factory.expected_bounds("pier", bare)[0][2], 1.5)             # bare deck surface

    def test_coastal_bounds_band_between_land_and_tallest_feature(self):
        spec = SCHEMA["generators"]["coastal_path"]
        fenced, _ = factory.resolve_params(spec, {"land_height": 2.0, "roughness": 0.2, "fence": 1, "grass_density": 3.0})
        bare, _ = factory.resolve_params(spec, {"land_height": 2.0, "roughness": 0.2, "fence": 0, "grass_density": 0.0})
        size, slack = factory.expected_bounds("coastal_path", fenced)
        self.assertAlmostEqual(size[2], 3.15)                        # post on the highest ground (2.2) + 0.95 beats tufts
        self.assertAlmostEqual(size[2] * (1 - slack[2]), 1.95)       # floor: the flattened path
        size, slack = factory.expected_bounds("coastal_path", bare)
        self.assertAlmostEqual(size[2], 2.2)                         # noise ceiling only
        self.assertAlmostEqual(size[2] * (1 - slack[2]), 1.95)       # a narrow strip may be all path blend

    def test_tide_pool_bounds_follow_the_stair_and_the_shelf(self):
        spec = SCHEMA["generators"]["tide_pools"]
        stair, _ = factory.resolve_params(spec, {"shelf_height": 0.5, "stair_top": 1.95, "length": 8.0, "width": 6.0})
        size, slack = factory.expected_bounds("tide_pools", stair)
        self.assertEqual(size[:2], [12.0, 0.6 + 9 * 0.3 + 8.0 + 3.0])           # 9 steps of <= 0.18 m, then shelf, then 3 m of sea
        self.assertAlmostEqual(size[2], 1.95)
        bare, _ = factory.resolve_params(spec, {"stair": 0, "shelf_height": 0.5, "roughness": 0.1, "boulders": 0})
        size, slack = factory.expected_bounds("tide_pools", bare)
        self.assertAlmostEqual(size[1], bare["length"] + 3.0)                    # no stair: the shelf starts at y=0
        self.assertAlmostEqual(size[2], 0.62)                                    # starfish/shells add <= 2 cm
        self.assertAlmostEqual(size[2] * (1 - slack[2]), 0.25)                  # a basin floor

    def test_constraints_on_disabled_features_do_not_apply(self):
        spec = SCHEMA["generators"]["tide_pools"]
        flat, _ = factory.resolve_params(spec, {"stair": 0, "stair_top": 0.8, "shelf_height": 0.8, "water_level": 0.3,
                                                "pools": 0, "width": 3.0, "pool_radius": 1.2})
        self.assertEqual(factory.check_constraints(spec, flat), [])
        on, _ = factory.resolve_params(spec, {**flat, "stair": 1, "pools": 2})
        self.assertEqual(len(factory.check_constraints(spec, on)), 2)            # stair descent + basin across the width

    def test_lod_details_halve_with_floor(self):
        self.assertEqual(factory.lod_details(16), [16, 8, 4])
        self.assertEqual(factory.lod_details(6), [6, 4, 4])


class GateEvaluation(unittest.TestCase):
    def gates(self, m, **params):
        return factory.evaluate_gates("prop", SCHEMA["generators"]["prop"], crate_params(**params), m)

    def test_clean_crate_passes_every_mesh_gate(self):
        self.assertEqual(failed(self.gates(crate_measurements())), {})

    def test_seeded_defects_each_fail_their_own_gate(self):
        cases = {
            "manifold": lambda m: m["parts"][0].update(boundary_edges=4),
            "uv": lambda m: m["parts"][1].update(uv1_overlap_texels=9),
            "lod_chain": lambda m: m["lods"][2].update(triangles=500),
            "triangle_budget": lambda m: m["lods"][0].update(triangles=4001),
            "pivots": lambda m: m["parts"][1].update(origin=[0.0, 0.0, 0.1]),
            "naming": lambda m: m["collision_objects"].pop(),
            "gn_interface": lambda m: m["gn_bounds"].update(height=[0.2, 9.0]),
            "parts_present": lambda m: m.update(unknown_part_ids=[42]),
            "interpenetration": None,
        }
        cases = list(cases.items()) + [
            ("parts_present", lambda m: m["parts"].pop(0)),                                    # crate without its core
            ("parts_present", lambda m: m["lods"][2]["parts"].pop(0)),                         # LOD2 lost a part
            ("parts_present", lambda m: m["parts"].append({**m["parts"][0], "id": 1, "name": "lantern_body"})),
            ("manifold", lambda m: m["lods"][1]["parts"][1].update(nonmanifold_edges=2)),      # lower LODs are gated too
            ("uv", lambda m: m["parts"][0].update(uv1_degenerate=3)),
            ("manifold", lambda m: m["parts"][1].update(loose_verts=4)),                         # bare points from a failed node
            ("naming", lambda m: m.update(collision_boxes=1)),
            ("lod_chain", lambda m: m["lods"][1].update(bbox_min=[98.8, 98.8, 99.0], bbox_max=[99.2, 99.2, 99.6])),   # LOD moved
        ]
        for gate, seed in cases:
            m = crate_measurements()
            if gate == "interpenetration":
                # The core belongs to another group in this seeded schema: overlapping islands must be reported.
                spec = copy.deepcopy(SCHEMA["generators"]["prop"]); spec["parts"]["4"]["group"] = "other"
                result = failed(factory.evaluate_gates("prop", spec, crate_params(), m))
            else:
                seed(m); result = failed(self.gates(m))
            self.assertIn(gate, result, (gate, result))
            self.assertLessEqual(set(result), {gate, "naming"}, (gate, result))   # a missing part also drops its collision

    def test_dimensions_catch_wrong_size_and_floating_asset(self):
        m = crate_measurements(width=0.4, height=0.6)
        self.assertIn("axis z", failed(self.gates(m, height=0.7))["dimensions"][0])
        m["lods"][0]["bbox_min"] = [-0.2, -0.2, 0.05]
        self.assertTrue(any("z=0" in f for f in failed(self.gates(m))["dimensions"]))

    def test_open_parts_may_have_boundary_edges(self):
        spec = copy.deepcopy(SCHEMA["generators"]["prop"]); spec["parts"]["4"]["open"] = True
        m = crate_measurements(); m["parts"][0]["boundary_edges"] = 4
        self.assertEqual(failed(factory.evaluate_gates("prop", spec, crate_params(), m)), {})

    def test_island_overlap_ignores_same_group_and_touching(self):
        a = ("g1", "a", [0, 0, 0], [1, 1, 1])
        self.assertEqual(factory.island_overlaps([a, ("g1", "b", [0.5, 0, 0], [2, 1, 1])]), [])
        self.assertEqual(factory.island_overlaps([a, ("g2", "b", [1, 0, 0], [2, 1, 1])]), [])
        self.assertEqual(factory.island_overlaps([a, ("g2", "b", [0.9, 0, 0], [2, 1, 1])]), ["a x b"])

    def test_godot_gate_swaps_axes_and_counts_collision(self):
        report = {"state": "loaded", "collision_shapes": 2, "static_bodies": 2, "collision_triangles": 36, "mesh_aabb_size": [1.0, 3.0, 2.0]}
        self.assertTrue(factory.godot_gate(report, 2, [0, 0, 0], [1, 2, 3], 3)["passed"])
        self.assertFalse(factory.godot_gate({**report, "collision_shapes": 1}, 2, [0, 0, 0], [1, 2, 3], 3)["passed"])
        self.assertFalse(factory.godot_gate(report, 2, [0, 0, 0], [1, 3, 2], 3)["passed"])
        # A single hull over two islands (e.g. both torii pillars) would close the passage: 12 triangles, not 24.
        self.assertFalse(factory.godot_gate({**report, "collision_triangles": 12}, 2, [0, 0, 0], [1, 2, 3], 3)["passed"])

    def test_odd_detail_lantern_slack_covers_ring_and_segment_loss(self):
        params, _ = factory.resolve_params(SCHEMA["generators"]["prop"], {"kind": 0, "width": 0.316, "height": 1.0, "detail": 19})
        size, slack = factory.expected_bounds("prop", params)
        self.assertLessEqual(size[0] * (1 - slack[0]) - factory.TOL, 0.3091)   # measured live at detail 19
        size, slack = factory.expected_bounds("prop", params, 6)
        self.assertLessEqual(size[1] * (1 - slack[1]), 0.75 * 0.316 + 1e-9)              # hexagon x 3 rings

    def test_centring_tolerance_is_exact_for_even_segments(self):
        params, _ = factory.resolve_params(SCHEMA["generators"]["prop"], {"kind": 0, "width": 0.4, "detail": 4})
        m = crate_measurements(width=0.4)
        for lod in m["lods"]: lod["bbox_min"][0] += 0.02; lod["bbox_max"][0] += 0.02   # shifted 2 cm on x
        spec = SCHEMA["generators"]["prop"]
        result = failed(factory.evaluate_gates("prop", spec, params, m))
        self.assertIn("asset not centred on x", result.get("dimensions", []))

    def test_snap_matches_generator_just_above_a_grid_line(self):
        params, _ = factory.resolve_params(SCHEMA["generators"]["shrine"], {"gate_width": 2.6, "pillar_radius": 0.15501})
        self.assertEqual(factory.expected_bounds("shrine", params)[0][0], 5.0)


@unittest.skipUnless(HAS_NUMPY, "numpy not installed (Blender bundles it)")
class UvOverlap(unittest.TestCase):
    def test_disjoint_shared_edge_and_stacked_triangles(self):
        lower = [[0.1, 0.1], [0.5, 0.1], [0.1, 0.5]]
        upper = [[0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]   # shares the diagonal with lower
        self.assertEqual(factory.uv_overlap_texels([lower, upper], 64), 0)
        self.assertEqual(factory.uv_overlap_texels([lower, [[0.6, 0.6], [0.9, 0.6], [0.6, 0.9]]], 64), 0)
        self.assertGreater(factory.uv_overlap_texels([lower, lower], 64), 50)

    def test_degenerate_uv_triangles_are_counted(self):
        self.assertEqual(factory.uv_degenerate([[[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]], [[0, 0], [1, 0], [0, 1]]]), 1)


class BuildRejection(unittest.TestCase):
    def test_bad_params_are_rejected_before_blender_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "run"
            report = factory.build("room_kit", {"width": 2.4, "window_width": 2.4}, out, blender=Path(directory) / "missing.exe")
            self.assertEqual(report["state"], "rejected")
            self.assertEqual(report["failed_gates"], ["constraints"])
            self.assertEqual(json.loads((out / "report.json").read_text(encoding="utf-8"))["state"], "rejected")
            self.assertFalse((out / "request.json").exists())

    def test_blender_failure_still_writes_a_failed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "run"
            report = factory.build("prop", {}, out, blender=sys.executable)   # "-b" is not a Python flag: exits non-zero
            self.assertEqual(report["state"], "failed")
            self.assertEqual(report["failed_gates"], ["blender"])
            self.assertEqual(json.loads((out / "report.json").read_text(encoding="utf-8"))["failed_gates"], ["blender"])
            self.assertTrue((out / "blender-stderr.log").exists())

    def test_partial_blender_output_still_writes_a_failed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "run"
            measured = Path(directory) / "measurements.json"; measured.write_text(json.dumps(crate_measurements()), encoding="utf-8")
            fake = Path(directory) / "fake_blender.py"     # exits 0 but its measurements name GLBs it never wrote
            fake.write_text("import json, shutil, sys\nfrom pathlib import Path\n"
                            "req = json.loads(Path(sys.argv[-1]).read_text())\n"
                            f"shutil.copyfile({str(measured)!r}, Path(req['output'], 'measurements.json'))\n", encoding="utf-8")
            launcher = Path(directory) / ("blender.cmd" if os.name == "nt" else "blender")
            launcher.write_text(f'@"{sys.executable}" "{fake}" %*\n' if os.name == "nt"
                                else f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
            report = factory.build("prop", {"kind": 1}, out, blender=launcher)
            self.assertEqual(report["state"], "failed")
            self.assertIn("blender", report["failed_gates"])
            self.assertTrue((out / "report.json").exists())

    def test_output_directory_must_be_new(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                factory.build("prop", {}, directory, blender="unused")


@unittest.skipUnless(os.environ.get("PROCGEN_LIVE_BLENDER"), "set PROCGEN_LIVE_BLENDER=<blender.exe> for the live round trip")
class LiveBuild(unittest.TestCase):
    def test_every_generator_default_passes_all_gates(self):
        config = json.loads(factory.LOCAL_CONFIG.read_text(encoding="utf-8")) if factory.LOCAL_CONFIG.is_file() else {}
        with tempfile.TemporaryDirectory() as directory:
            for name in SCHEMA["generators"]:
                report = factory.build(name, {}, Path(directory) / name, os.environ["PROCGEN_LIVE_BLENDER"],
                                       config.get("godot"), config.get("node"))
                self.assertEqual(report["state"], "passed", (name, report["failed_gates"]))


if __name__ == "__main__":
    unittest.main()
