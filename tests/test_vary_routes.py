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
        self.assertEqual(set(routes), {"krea-refine", "gentle-variation", "wai-vary"})
        self.assertIn("krea-anime-atelier", routes["krea-refine"])
        self.assertIn("krea-refine", routes["krea-refine"], "a varied picture can be varied again")
        self.assertIn("sdxl", routes["gentle-variation"])
        # A style LoRA the route does not carry would be lost on the strong pass: those recipes fall back to new seeds.
        for lora_recipe in ("lineani-portrait", "screentone-portrait", "cinematic-lighting-portrait", "pixel-lora"):
            self.assertNotIn(lora_recipe, routes["gentle-variation"])
        # WAI pictures keep their checkpoint and LoRA stack (owner, 27 Sep 2026: "Yes, WAI img2img"). Other anime
        # checkpoints need their own checkpoint, so they keep the new-seeds fallback until a route carries it.
        self.assertEqual(routes["wai-vary"], ["wai", "anime-wai-quality", "wai-vary"])
        for other in ("anime", "noob", "pony", "anime-animagine-quality", "style-pose-wai", "restyle-wai", "anime-complete"):
            self.assertFalse(any(other in sources for sources in routes.values()), other)

    def test_the_wai_route_keeps_the_source_checkpoint_and_every_lora_slot(self):
        route = by_id(CATALOG, "wai-vary")
        self.assertEqual(route["vary"]["carry"], ["lora", "lora_name", "lora2", "lora2_name", "sampler", "scheduler", "cfg", "steps"])
        for source_id in ("wai", "anime-wai-quality"):
            source = by_id(CATALOG, source_id)
            self.assertEqual(continuation._models(graph_of(route)), continuation._models(graph_of(source)), source_id)
            for slot in ("lora", "lora2"): self.assertIn(slot, source)
        self.assertEqual(continuation.capability(route, graph_of(route))["operation"], "image-to-image")
        # verified only with a recorded proving run (the 27 Sep 2026 live proof through the page, #1202)
        if route["verified"]: self.assertIn("Executed", route.get("execution_note", ""))
        # Started at the SDXL owner values, still a starting value until a GPU proof and the owner's look at WAI pictures.
        self.assertEqual(route["vary"]["status"], "starting-value")
        self.assertEqual((route["vary"]["subtle"]["controls"], route["vary"]["strong"]["controls"]), ({"denoise": 0.5}, {"denoise": 0.7}))

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


class CarryContract(unittest.TestCase):
    """A route that carries the source's recorded LoRA stack must prove it draws with the same model and adapters."""
    def setUp(self):
        self.presets = copy.deepcopy(CATALOG)
        self.route = by_id(self.presets, "wai-vary")
        self.edits = {}

    def graph(self, preset):
        graph = graph_of(preset)
        for edit in self.edits.get(preset["id"], []): edit(graph)
        return graph

    def problems(self):
        return continuation.vary_catalog_problems(self.presets, self.graph)

    def test_the_shipped_route_is_sound(self):
        self.assertEqual(self.problems(), [])

    def test_a_source_on_another_checkpoint_is_refused_even_under_the_same_family_label(self):
        anime = by_id(self.presets, "anime"); anime["family"] = self.route["family"]
        self.route["vary"]["sources"].append("anime")
        self.assertTrue(any("anime" in p and "checkpoint" in p for p in self.problems()), self.problems())

    def test_every_source_lora_slot_must_be_carried(self):
        self.route["vary"]["carry"] = ["lora", "lora_name", "sampler", "scheduler", "cfg", "steps"]
        self.assertTrue(any("wai" in p and "adapter" in p for p in self.problems()), self.problems())

    def test_a_carried_strength_needs_its_file_and_the_other_way_round(self):
        self.route["vary"]["carry"].remove("lora2_name")
        self.assertTrue(any("lora2" in p and "file" in p for p in self.problems()), self.problems())

    def test_the_route_may_not_add_an_adapter_of_its_own(self):
        def extra(graph):
            graph["20"] = {"class_type": "LoraLoader", "inputs": {"model": ["9", 0], "clip": ["9", 1], "lora_name": "noirpopwave.safetensors", "strength_model": 0.8, "strength_clip": 0.8}}
            graph["5"]["inputs"]["model"] = ["20", 0]
        self.edits["wai-vary"] = [extra]
        self.assertTrue(any("wai-vary" in p and "adapter" in p and "20" in p for p in self.problems()), self.problems())

    def test_a_source_adapter_the_recipe_does_not_bind_is_refused(self):
        def fixed(graph):
            graph["20"] = {"class_type": "LoraLoader", "inputs": {"model": ["9", 0], "clip": ["9", 1], "lora_name": "noirpopwave.safetensors", "strength_model": 1, "strength_clip": 1}}
            graph["5"]["inputs"]["model"] = ["20", 0]
        self.edits["anime-wai-quality"] = [fixed]
        self.assertTrue(any("anime-wai-quality" in p and "adapter" in p for p in self.problems()), self.problems())

    def test_carried_keys_are_bound_on_both_sides_and_never_the_round_s_own(self):
        for key in ("seed", "denoise", "positive", "reference"):
            self.route["vary"]["carry"] = ["lora", "lora_name", "lora2", "lora2_name", key]
            self.assertTrue(any("carry " + key in p for p in self.problems()), (key, self.problems()))
        self.route["vary"]["carry"] = ["lora", "lora_name", "lora2", "lora2_name", "style_weight"]
        self.assertTrue(any("style_weight" in p and "does not bind" in p for p in self.problems()), self.problems())
        del by_id(self.presets, "anime-wai-quality")["scheduler"]
        self.route["vary"]["carry"] = ["lora", "lora_name", "lora2", "lora2_name", "scheduler"]
        self.assertTrue(any("anime-wai-quality" in p and "scheduler" in p for p in self.problems()), self.problems())
        self.route["vary"]["carry"] = []
        self.assertTrue(any("carry" in p for p in self.problems()))

    def test_a_recorded_choice_must_be_accepted_by_the_route(self):
        self.route["choices"]["sampler"] = ["euler"]
        self.assertTrue(any("sampler" in p and "euler_ancestral" in p for p in self.problems()), self.problems())

    def test_clip_strength_fans_out_the_same_way(self):
        del self.route["bindings_extra"]["lora2"]
        self.assertTrue(any("lora2" in p and "strength" in p for p in self.problems()), self.problems())

    def test_a_carried_lora_file_binds_the_same_node_as_its_strength(self):
        self.route["lora_name"] = ["9", "lora_name"]
        self.assertTrue(any("lora_name" in p and "different nodes" in p for p in self.problems()), self.problems())

    def test_a_carried_lora_must_reach_the_sampler_and_the_text_encoders(self):
        def disconnect(graph):
            graph["5"]["inputs"]["model"] = ["1", 0]
            graph["2"]["inputs"]["clip"] = ["1", 1]
            graph["3"]["inputs"]["clip"] = ["1", 1]
        self.edits["wai-vary"] = [disconnect]
        self.assertTrue(any("does not feed" in p for p in self.problems()), self.problems())

    def test_checkpoint_name_is_the_checkpoint_and_a_detector_model_name_is_not(self):
        def use_checkpoint_name(graph):
            for node in graph.values():
                inputs = node.get("inputs") or {}
                if "ckpt_name" in inputs: inputs["checkpoint_name"] = inputs.pop("ckpt_name")
        def detector(graph):
            graph["1"]["inputs"]["model_name"] = "bbox/face_yolov8s.pt"
        for preset_id in ("wai-vary", "wai", "anime-wai-quality"):
            self.edits[preset_id] = [use_checkpoint_name]
        self.edits["wai-vary"].append(detector)
        self.assertEqual(self.problems(), [], self.problems())


class VaryClientPolicy(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for client policy checks")
    def test_client_vary_policy(self):
        result = subprocess.run([shutil.which("node"), str(ROOT / "tests/vary_core.cjs")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Vary policy contracts passed", result.stdout, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
