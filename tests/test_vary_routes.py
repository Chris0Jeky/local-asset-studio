"""Vary subtle / Vary strong routes (#1202): catalog contract and the browser's pure policy. No inference."""
import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import continuation  # noqa: E402  (bare-name app import, as the server does)

CATALOG = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]


def graph_of(preset):
    return json.loads((ROOT / preset["graph"]).read_text(encoding="utf-8"))


def by_id(presets, identifier):
    return next(p for p in presets if p["id"] == identifier)


class ShippedVaryRoutes(unittest.TestCase):
    def test_the_shipped_catalog_has_no_vary_problems(self):
        self.assertEqual(continuation.vary_catalog_problems(CATALOG, graph_of), [])

    def test_declared_routes_and_their_sources(self):
        routes = {p["id"]: p["vary"]["sources"] for p in CATALOG if p.get("vary")}
        self.assertEqual(set(routes), {"krea-refine", "gentle-variation"})
        self.assertIn("krea-anime-atelier", routes["krea-refine"])
        self.assertIn("krea-refine", routes["krea-refine"], "a varied picture can be varied again")
        self.assertIn("sdxl", routes["gentle-variation"])
        # A style LoRA the route does not carry would be lost on the strong pass: those recipes fall back to new seeds.
        for lora_recipe in ("lineani-portrait", "screentone-portrait", "cinematic-lighting-portrait", "pixel-lora"):
            self.assertNotIn(lora_recipe, routes["gentle-variation"])

    def test_every_strength_is_labelled_per_recipe_not_a_global(self):
        # A route is a labelled starting value until the owner judges it; an owner-approved route's basis records the owner's
        # answer and its date (27 Sep 2026: "Nudge both up" for krea-refine and gentle-variation, #1202).
        for preset in CATALOG:
            vary = preset.get("vary")
            if not vary: continue
            self.assertIn(vary["status"], ("starting-value", "owner-approved"), preset["id"])
            if vary["status"] == "owner-approved":
                for name in ("subtle", "strong"):
                    self.assertIn("owner", vary[name]["basis"].lower(), (preset["id"], name))
                    self.assertRegex(vary[name]["basis"], r"20\d\d", (preset["id"], name))
            self.assertLess(vary["subtle"]["controls"]["denoise"], vary["strong"]["controls"]["denoise"], preset["id"])
            for name in ("subtle", "strong"): self.assertTrue(vary[name]["basis"].strip(), (preset["id"], name))


class VaryContract(unittest.TestCase):
    def setUp(self):
        self.presets = copy.deepcopy(CATALOG)
        self.route = by_id(self.presets, "krea-refine")

    def problems(self):
        return continuation.vary_catalog_problems(self.presets, graph_of)

    def test_a_route_must_resample_the_kept_picture(self):
        text = by_id(self.presets, "krea-portrait")
        text["vary"] = copy.deepcopy(self.route["vary"]); text["vary"]["sources"] = ["krea-environment"]
        self.route["vary"]["sources"].remove("krea-environment")
        self.assertTrue(any("image-to-image" in p for p in self.problems()))

    def test_strengths_are_bound_controls_with_subtle_below_strong(self):
        # Above the shipped strong value (0.65 since the owner's 27 Sep 2026 answer), so subtle would resample more than strong.
        self.route["vary"]["subtle"]["controls"]["denoise"] = 0.9
        self.assertTrue(any("subtle" in p and "strong" in p for p in self.problems()))
        self.route["vary"]["subtle"]["controls"] = {"denoise": 0.2, "width": 512}
        self.assertTrue(any("width" in p for p in self.problems()))
        for bad in (0, 1, True, "0.3", None):
            self.route["vary"]["subtle"]["controls"] = {"denoise": bad}
            self.assertTrue(any("denoise" in p for p in self.problems()), bad)
        self.route["vary"]["subtle"]["controls"] = {"denoise": 0.2, "seed": 1}
        self.assertTrue(any("seed" in p for p in self.problems()), "the round picks its own new seeds")

    def test_a_strength_needs_its_basis_and_the_route_its_status(self):
        self.route["vary"]["strong"]["basis"] = " "
        self.assertTrue(any("basis" in p for p in self.problems()))
        self.route["vary"]["strong"]["basis"] = "Starting value."; self.route["vary"]["status"] = "measured"
        self.assertTrue(any("status" in p for p in self.problems()))

    def test_sources_exist_draw_with_the_same_model_and_have_one_route(self):
        self.route["vary"]["sources"].append("missing-recipe")
        self.assertTrue(any("missing-recipe" in p for p in self.problems()))
        self.route["vary"]["sources"][-1] = "wai"
        self.assertTrue(any("wai" in p and "model" in p for p in self.problems()))
        self.route["vary"]["sources"][-1] = "sdxl"
        self.assertTrue(any("sdxl" in p and "more than one" in p for p in self.problems()))
        self.route["vary"]["sources"] = []
        self.assertTrue(any("sources" in p for p in self.problems()))

    def test_unknown_fields_are_refused(self):
        self.route["vary"]["count"] = 4
        self.assertTrue(any("exactly" in p for p in self.problems()), "the round size is the owner's timing rule, not catalog data")


class VaryClientPolicy(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for client policy checks")
    def test_client_vary_policy(self):
        result = subprocess.run([shutil.which("node"), str(ROOT / "tests/vary_core.cjs")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Vary policy contracts passed", result.stdout, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
