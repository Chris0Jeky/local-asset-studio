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

    def test_krea_carries_only_compatible_fp8_sources_with_all_four_slots_and_historical_steps(self):
        route = by_id(CATALOG, "krea-refine")
        self.assertEqual(route["vary"]["sources"], ["krea-anime-atelier", "krea-refine"])
        self.assertEqual(route["vary"]["carry"], [key for slot in ("lora", "lora2", "lora3", "lora4") for key in (slot, slot + "_name")] + ["sampler", "scheduler", "cfg"])
        self.assertEqual(route["vary"]["subtle"]["controls"], {"denoise": 0.45, "steps": 4})
        self.assertEqual(route["vary"]["strong"]["controls"], {"denoise": 0.65, "steps": 6})
        self.assertEqual(route["vary"]["status"], "owner-approved")
        self.assertFalse(route["verified"], "Historical refine execution does not qualify the new source-stack carry")
        for source_id in ("krea-portrait", "krea-portrait-gguf", "krea-environment", "krea-anime-atelier-gguf", "krea-style-lab"):
            self.assertFalse(any(source_id in p.get("vary", {}).get("sources", []) for p in CATALOG))
            self.assertEqual(continuation.capability(by_id(CATALOG, source_id), graph_of(by_id(CATALOG, source_id)))["operation"], "new-image")

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
        # Started at the SDXL owner values; owner-approved on 16 Oct 2026 after the WAI proof sheet (wai-vary-look-1202).
        self.assertEqual(route["vary"]["status"], "owner-approved")
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
        text["vary"] = copy.deepcopy(self.route["vary"]); text["vary"]["sources"] = ["krea-anime-atelier"]
        self.route["vary"]["sources"].remove("krea-anime-atelier")
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

    def test_source_lora_name_and_strength_must_bind_the_same_node(self):
        by_id(self.presets, "wai")["lora_name"] = ["9", "lora_name"]
        self.assertTrue(any("wai" in p and "lora_name" in p and "different nodes" in p for p in self.problems()), self.problems())

    def test_sampler_model_cannot_bypass_lora_through_its_conditioning(self):
        self.edits["wai-vary"] = [lambda graph: graph["5"]["inputs"].update(model=["1", 0])]
        self.assertTrue(any("does not feed" in p for p in self.problems()), self.problems())

    def test_model_and_clip_must_use_the_correct_lora_output_ports(self):
        for node, field, wrong in (("5", "model", 1), ("2", "clip", 0)):
            with self.subTest(node=node):
                self.edits["wai-vary"] = [lambda graph: graph[node]["inputs"].update({field: ["9", wrong]})]
                self.assertTrue(any("does not feed" in p for p in self.problems()), self.problems())

    def test_every_text_encoder_must_receive_the_carried_clip(self):
        self.edits["wai-vary"] = [lambda graph: graph["3"]["inputs"].update(clip=["1", 1])]
        self.assertTrue(any("does not feed" in p for p in self.problems()), self.problems())

    def test_every_sampler_must_receive_the_carried_model(self):
        for model, reason in ((["1", 0], "does not feed"), (["unknown", 0], "cannot determine")):
            with self.subTest(model=model):
                def second(graph):
                    graph["30"] = copy.deepcopy(graph["5"]); graph["30"]["inputs"]["model"] = model
                self.edits["wai-vary"] = [second]
                self.assertTrue(any(reason in p for p in self.problems()), self.problems())

    def test_two_samplers_through_the_carried_loras_are_accepted(self):
        self.edits["wai-vary"] = [lambda graph: graph.update({"30": copy.deepcopy(graph["5"])})]
        self.assertEqual(self.problems(), [])

    def test_unknown_or_missing_graph_shape_is_reported(self):
        def unknown(graph):
            graph["20"] = {"class_type": "UnknownModelWrapper", "inputs": {"model": ["9", 0]}}
            graph["5"]["inputs"]["model"] = ["20", 0]
        for edit in (unknown, lambda graph: graph["8"].update(class_type="UnknownLora"),
                     lambda graph: graph["5"].update(class_type="UnknownSampler"),
                     lambda graph: [graph[key].update(class_type="UnknownEncoder") for key in ("2", "3")]):
            with self.subTest(edit=edit):
                self.edits["wai-vary"] = [edit]
                self.assertTrue(any("cannot determine" in p for p in self.problems()), self.problems())

    def _forward(self, kind, field, source="9", out=0):
        """Insert one node between `source` (the carried LoRA by default) and the sampler (model) or both encoders (clip)."""
        def edit(graph):
            graph["20"] = {"class_type": kind, "inputs": {field: [source, 0 if field == "model" else 1]}}
            for key, name in (("5", "model"),) if field == "model" else (("2", "clip"), ("3", "clip")):
                graph[key]["inputs"][name] = ["20", out]
        return edit

    def test_allowlisted_pass_through_nodes_between_the_lora_and_its_consumers_are_accepted(self):
        # PASS_THROUGH mirrors shipped wiring (qwen: ModelSamplingAuraFlow, trellis: RescaleCFG, pony: CLIPSetLastLayer).
        allowed = {"model": {"ModelSamplingAuraFlow", "ModelSamplingSD3", "RescaleCFG"}, "clip": {"CLIPSetLastLayer"}}
        for field, kinds in allowed.items():
            for kind in sorted(kinds):
                with self.subTest(kind=kind):
                    self.edits["wai-vary"] = [self._forward(kind, field)]
                    self.assertEqual(self.problems(), [])
        self.edits["wai-vary"] = [self._forward("ModelSamplingSD3", "model"), lambda g: g.update({"20b": {"class_type": "RescaleCFG", "inputs": {"model": ["9", 0]}}}),
                                  lambda g: g["20"]["inputs"].update(model=["20b", 0])]
        self.assertEqual(self.problems(), [], "a chain of pass-throughs is followed")
        self.assertEqual(continuation.PASS_THROUGH, allowed, "the allowlist is exactly what the tests cover")

    def test_a_pass_through_that_bypasses_the_lora_does_not_feed_it(self):
        for field, kind in (("model", "ModelSamplingAuraFlow"), ("clip", "CLIPSetLastLayer")):
            with self.subTest(kind=kind):
                self.edits["wai-vary"] = [self._forward(kind, field, "1")]
                self.assertTrue(any("does not feed" in p for p in self.problems()), self.problems())

    def test_a_pass_through_is_refused_off_its_allowlist_or_on_the_wrong_wire(self):
        cases = [("ModelMergeSimple", "model", 0), ("Reroute", "model", 0), ("CFGOverride", "model", 0), ("CLIPMergeSimple", "clip", 0),
                 ("CLIPSetLastLayer", "model", 0), ("ModelSamplingSD3", "clip", 0),   # right node, wrong kind of wire
                 ("RescaleCFG", "model", 1)]                                          # allowlisted, but its consumer reads a port it does not have
        for kind, field, out in cases:
            with self.subTest(kind=kind, field=field, out=out):
                self.edits["wai-vary"] = [self._forward(kind, field, out=out)]
                self.assertTrue(any("cannot determine" in p for p in self.problems()), self.problems())

    def test_a_route_without_a_ksampler_is_refused_with_a_reason_not_a_crash(self):
        # Evidence for #1243 item (b): no shipped Vary route draws without KSampler; SamplerCustomAdvanced and HiDream
        # pipelines are not image-to-image under capability(), so a carry there stays refused rather than guessed.
        for kind in ("KSamplerAdvanced", "SamplerCustomAdvanced", "HiDreamO1Sampler"):
            with self.subTest(kind=kind):
                self.edits["wai-vary"] = [lambda graph: graph["5"].update(class_type=kind)]
                problems = self.problems()
                self.assertTrue(any("image-to-image" in p for p in problems), problems)

    def test_every_shipped_graph_traces_to_a_verdict_and_every_recipe_declares_or_is_refused(self):
        verdicts = {True, False, None}
        for preset in CATALOG:
            try: graph = graph_of(preset)
            except (KeyError, OSError, ValueError): continue
            if not isinstance(graph, dict): continue
            nodes = {str(k): v for k, v in graph.items() if isinstance(v, dict)}
            for start in [k for k, v in nodes.items() if v.get("class_type") == "LoraLoader"]:
                for target, v in nodes.items():
                    for prefix, field in (("KSampler", "model"), ("CLIPTextEncode", "clip")):
                        if str(v.get("class_type") or "").startswith(prefix):
                            self.assertIn(continuation._lora_feeds(nodes, start, target, field), verdicts, (preset["id"], start, target))
            # Declare the WAI carry on this recipe: only wai-vary itself may come back clean, every other recipe is refused in words.
            probe = copy.deepcopy(preset); probe["vary"] = copy.deepcopy(self.route["vary"]); probe["vary"]["sources"] = ["wai"]
            problems = continuation.vary_problems(probe, graph, self.presets, graph_of)
            self.assertTrue(all(isinstance(p, str) and p for p in problems), preset["id"])
            if preset["id"] != "wai-vary": self.assertTrue(problems, preset["id"] + " must not pass as a WAI carry route")

    def test_alternate_loader_fields_compare_exactly_without_counting_auxiliary_models(self):
        for loader, field in (("HiDreamO1ModelLoader", "model_name"), ("UnetLoaderGGUF", "gguf_name")):
            with self.subTest(loader=loader):
                def replace(graph):
                    value = graph["1"]["inputs"].pop("ckpt_name")
                    graph["1"] = {"class_type": loader, "inputs": {field: value}}
                    graph["30"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "upscale.pth"}}
                self.edits = {key: [replace] for key in ("wai-vary", "wai", "anime-wai-quality")}
                self.assertEqual(continuation._models(self.graph(self.route)), {"waiIllustriousSDXL_v170.safetensors"})
                self.assertEqual(self.problems(), [])
                self.edits["wai"].append(lambda graph: graph["1"]["inputs"].update({field: "other.gguf"}))
                self.assertTrue(any("wai" in p and "another checkpoint" in p for p in self.problems()), self.problems())


class ModelOnlyCarryContract(unittest.TestCase):
    """Krea's model-only adapters keep their own footprint; they never claim a CLIP output."""
    def setUp(self):
        self.presets = copy.deepcopy(CATALOG)
        self.route = by_id(self.presets, "krea-refine")
        self.route["vary"]["sources"] = ["krea-anime-atelier", "krea-refine"]
        self.route["vary"]["carry"] = [key for slot in ("lora", "lora2", "lora3", "lora4") for key in (slot, slot + "_name")] + ["sampler", "scheduler", "cfg"]
        self.route["vary"]["subtle"]["controls"]["steps"] = 4
        self.edits = {}

    graph = CarryContract.graph
    problems = CarryContract.problems

    def test_four_model_only_adapters_feed_the_sampler_without_a_clip_footprint(self):
        self.assertEqual(self.problems(), [])
        graph = self.graph(self.route)
        for node in ("10", "11", "12", "13"):
            self.assertTrue(continuation._lora_feeds(graph, node, "7", "model"))
            self.assertFalse(continuation._lora_feeds(graph, node, "4", "clip"))

    def test_exact_model_identity_is_required_even_with_matching_family_and_slots(self):
        self.route["vary"]["sources"].append("krea-anime-atelier-gguf")
        self.assertTrue(any("krea-anime-atelier-gguf" in p and "another checkpoint" in p for p in self.problems()))

    def test_source_and_route_cannot_change_adapter_loader_kind(self):
        def clip_adapter(graph):
            graph["10"]["class_type"] = "LoraLoader"
            graph["10"]["inputs"].update(clip=["2", 0], strength_clip=1)
        self.edits["krea-anime-atelier"] = [clip_adapter]
        self.assertTrue(any("krea-anime-atelier" in p and "loader kind" in p for p in self.problems()), self.problems())

    def test_model_only_bindings_cannot_claim_an_extra_strength_or_another_file_field(self):
        for wrong in ("extra-strength", "file-field"):
            with self.subTest(wrong=wrong):
                self.setUp()
                for preset_id in ("krea-refine", "krea-anime-atelier"):
                    preset = by_id(self.presets, preset_id)
                    if wrong == "extra-strength": preset["bindings_extra"] = {"lora": [["10", "strength_clip"]]}
                    else: preset["lora_name"] = ["10", "other_name"]
                self.assertTrue(any("model-only" in p and "binding" in p for p in self.problems()), self.problems())

    def assert_filename_fanout_is_refused(self, preset_id):
        from server import Studio
        preset = by_id(self.presets, preset_id)
        preset["bindings_extra"] = {"lora4_name": [["10", "lora_name"]]}
        graph = self.graph(preset); studio = Studio.__new__(Studio)
        studio._bind_control(graph, preset, "lora_name", "recorded-first.safetensors")
        studio._bind_control(graph, preset, "lora4_name", "recorded-fourth.safetensors")
        self.assertEqual(graph["10"]["inputs"]["lora_name"], "recorded-fourth.safetensors",
                         "The real companion binding overwrites the first recorded filename")
        self.assertTrue(any(p.startswith(preset_id + ":") and "model-only lora4" in p and "binding" in p for p in self.problems()), self.problems())

    def test_model_only_route_filename_fanout_is_refused(self):
        self.assert_filename_fanout_is_refused("krea-refine")

    def test_model_only_source_filename_fanout_is_refused(self):
        self.assert_filename_fanout_is_refused("krea-anime-atelier")

    def test_every_model_only_route_and_source_sampler_must_receive_every_adapter(self):
        for preset_id in ("krea-refine", "krea-anime-atelier"):
            for model in (["1", 0], ["13", 1], ["missing", 0]):
                with self.subTest(preset=preset_id, model=model):
                    self.edits = {preset_id: [lambda graph: graph["7"]["inputs"].update(model=model)]}
                    self.assertTrue(any(preset_id in p and ("does not feed" in p or "cannot determine" in p) for p in self.problems()), self.problems())
            def second_sampler(graph):
                graph["30"] = copy.deepcopy(graph["7"]); graph["30"]["inputs"]["model"] = ["1", 0]
            self.edits = {preset_id: [second_sampler]}
            self.assertTrue(any(preset_id in p and "does not feed" in p for p in self.problems()), self.problems())

    def test_model_only_unknown_wrappers_stay_refused_and_known_model_forwarders_stay_supported(self):
        for kind in ("UnknownModelWrapper", "ModelSamplingSD3"):
            def wrapper(graph):
                graph["30"] = {"class_type": kind, "inputs": {"model": ["13", 0]}}
                graph["7"]["inputs"]["model"] = ["30", 0]
            self.edits = {"krea-refine": [wrapper], "krea-anime-atelier": [wrapper]}
            if kind == "UnknownModelWrapper": self.assertTrue(any("cannot determine" in p for p in self.problems()), self.problems())
            else: self.assertEqual(self.problems(), [])

    def assert_upstream_wrapper_is_refused(self, preset_id):
        def wrapper(graph):
            graph["30"] = {"class_type": "UnknownModelWrapper", "inputs": {"model": ["1", 0]}}
            graph["10"]["inputs"]["model"] = ["30", 0]
        self.edits = {preset_id: [wrapper]}
        # Every adapter still reaches the sampler, and the declared base name is unchanged. Neither proves its input.
        graph = self.graph(by_id(self.presets, preset_id))
        self.assertTrue(continuation._lora_feeds(graph, "10", "7", "model"))
        self.assertEqual(continuation._models(graph), continuation._models(graph_of(self.route)))
        self.assertTrue(any(p.startswith(preset_id + ":") and "connected base" in p for p in self.problems()), self.problems())

    def test_model_only_route_unknown_wrapper_before_first_adapter_is_refused(self):
        self.assert_upstream_wrapper_is_refused("krea-refine")

    def test_model_only_source_unknown_wrapper_before_first_adapter_is_refused(self):
        self.assert_upstream_wrapper_is_refused("krea-anime-atelier")

    def test_model_only_upstream_links_need_a_real_model_output_without_cycles_or_missing_nodes(self):
        for preset_id in ("krea-refine", "krea-anime-atelier"):
            for link in (["1", 1], ["missing", 0], ["10", 0], ["1", True], "1", None):
                with self.subTest(preset=preset_id, link=link):
                    self.edits = {preset_id: [lambda graph: graph["10"]["inputs"].update(model=link)]}
                    self.assertTrue(any(p.startswith(preset_id + ":") and "connected base" in p for p in self.problems()), self.problems())

    def test_model_only_known_forwarders_before_first_adapter_are_supported(self):
        for kind in sorted(continuation.PASS_THROUGH["model"]):
            def wrapper(graph):
                graph["30"] = {"class_type": kind, "inputs": {"model": ["1", 0]}}
                graph["10"]["inputs"]["model"] = ["30", 0]
            self.edits = {key: [wrapper] for key in ("krea-refine", "krea-anime-atelier")}
            self.assertEqual(self.problems(), [], kind)
        self.edits["krea-refine"].append(lambda graph: graph["10"]["inputs"].update(model=["30", 1]))
        self.assertTrue(any("krea-refine:" in p and "connected base" in p for p in self.problems()), self.problems())

    def test_model_only_connected_base_cannot_be_masked_by_matching_orphan_loader_names(self):
        def extra_base(graph):
            graph["30"] = copy.deepcopy(graph["1"])
            graph["30"]["inputs"]["unet_name"] = "other-base.safetensors"
        self.edits = {key: [extra_base] for key in ("krea-refine", "krea-anime-atelier")}
        self.edits["krea-refine"].append(lambda graph: graph["10"]["inputs"].update(model=["30", 0]))
        source = by_id(self.presets, "krea-anime-atelier")
        self.assertEqual(continuation._models(self.graph(self.route)), continuation._models(self.graph(source)),
                         "Both graphs declare both base names, but their stacks draw from different loaders")
        self.assertTrue(any("krea-anime-atelier" in p and "connected base" in p for p in self.problems()), self.problems())

    def test_model_only_connected_base_includes_the_recognized_loader_kind(self):
        self.edits = {"krea-refine": [lambda graph: graph["1"].update(class_type="UnetLoaderGGUF")]}
        self.assertTrue(any("krea-anime-atelier" in p and "connected base" in p for p in self.problems()), self.problems())

    def test_model_only_connected_base_needs_its_own_single_filename_field(self):
        for inputs in ({"ckpt_name": "krea2_turbo_fp8_scaled.safetensors"},
                       {"unet_name": ["missing", 0], "ckpt_name": "krea2_turbo_fp8_scaled.safetensors"}):
            with self.subTest(inputs=inputs):
                self.edits = {"krea-refine": [lambda graph: graph["1"].update(inputs=inputs)]}
                self.assertTrue(any(p.startswith("krea-refine:") and "connected base" in p for p in self.problems()), self.problems())


class VaryClientPolicy(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for client policy checks")
    def test_client_vary_policy(self):
        result = subprocess.run([shutil.which("node"), str(ROOT / "tests/vary_core.cjs")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Vary policy contracts passed", result.stdout, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
