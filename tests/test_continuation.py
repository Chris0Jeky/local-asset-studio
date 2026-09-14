"""Real prepare, retained-output and HTTP regressions; synthetic pixels, no inference."""
import copy
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_server import server, png
import continuation


ROOT = Path(__file__).resolve().parents[1]
GRAPH = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "Unrelated example witch"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur"}},
    "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768}},
    "4": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
    "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0]}},
    "6": {"class_type": "KSampler", "inputs": {"positive": ["1", 0], "negative": ["2", 0], "latent_image": ["5", 0], "seed": 42, "denoise": .25, "steps": 4, "cfg": 1}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0]}},
    "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0]}},
}
PRESET = dict(id="refine", name="Refine", graph="workflows/api/refine.json", modality="image", reference=["4", "image"], positive=["1", "text"], negative=["2", "text"], seed=["6", "seed"], denoise=["6", "denoise"])


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        for path in ("presets", "config", "workflows/api", "fake-comfy/input", "fake-comfy/output"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        self.graph_path = self.root / PRESET["graph"]; self.graph_path.write_text(json.dumps(GRAPH))
        self.multi_preset = dict(PRESET, id="first-last", name="First and last", graph="workflows/api/first-last.json", last_reference=["9", "image"])
        multi_graph = copy.deepcopy(GRAPH); multi_graph["9"] = {"class_type": "LoadImage", "inputs": {"image": "authored-last.png"}}
        multi_graph["6"]["inputs"]["last_image"] = ["9", 0]
        self.multi_path = self.root / self.multi_preset["graph"]; self.multi_path.write_text(json.dumps(multi_graph))
        self.source_preset = {key: value for key, value in PRESET.items() if key != "reference"}
        self.source_preset.update(id="create", name="Anima source fixture", graph="workflows/api/create.json")
        graph = copy.deepcopy(GRAPH); graph["6"]["inputs"]["latent_image"] = ["3", 0]
        (self.root / self.source_preset["graph"]).write_text(json.dumps(graph))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET, self.source_preset, self.multi_preset]}))
        with patch.object(threading.Thread, "start"): self.studio = server.Studio(self.root)
        self.request = patch.object(self.studio, "_request", side_effect=AssertionError("Unexpected Comfy request")); self.request.start(); self.addCleanup(self.request.stop)
        created = self.studio.create_job({"preset_id": "create", "controls": {"positive": "{station|meadow}"}, "batch_count": 2}, enqueue=False)
        self.source_job = self.studio.jobs[created["id"]]; self.source_job.update(status="completed", prompt_ids=["p-1", "p-2"])
        for index, text in enumerate(("An adult traveller at the station.", "A witch in a meadow.")):
            resolved = copy.deepcopy(self.source_job["graph"]); resolved["1"]["inputs"]["text"] = text
            self.source_job["submissions"].append(dict(index=index, prompt_id=f"p-{index+1}", graph=resolved, status="completed", seed=42+index))
            filename = f"source-{index}.png"; (self.root / "fake-comfy/output" / filename).write_bytes(png())
            self.source_job["outputs"].append(dict(filename=filename, type="output", subfolder="", prompt_id=f"p-{index+1}", seed=42+index, media_type="image"))
        self.studio.index_outputs(self.source_job); self.studio._save(self.source_job)
        self.asset_id = self.source_job["outputs"][0]["asset_id"]
        self.attachment = self.studio.asset_reference(self.asset_id)
        self.claim = dict(version=1, intent="repair", preset_id="refine", source_asset_id=self.asset_id, source_sha256=self.attachment["sha256"], reference_file=self.attachment["file"], template_sha256=hashlib.sha256(self.graph_path.read_bytes()).hexdigest())
        self.payload = dict(preset_id="refine", controls={"positive": self.attachment["context"]["positive"], "reference": self.attachment["file"]}, parent_assets=[self.asset_id], continuation=self.claim)

    def test_board_preset_without_a_single_reference_key_still_has_a_capability(self):
        """A style board declares reference_slots plus a pose picture on last_reference and no `reference` at all;
        capability() used to raise KeyError there, and Studio.catalog() then silently dropped the recipe's defaults."""
        graph = copy.deepcopy(GRAPH); graph["6"]["inputs"]["latent_image"] = ["3", 0]
        graph["9"] = {"class_type": "LoadImage", "inputs": {"image": "pose.png"}}
        graph["10"] = {"class_type": "OpenposePreprocessor", "inputs": {"image": ["9", 0]}}
        graph["11"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {"positive": ["1", 0], "negative": ["2", 0], "image": ["10", 0]}}
        graph["6"]["inputs"]["positive"] = ["11", 0]; graph["6"]["inputs"]["negative"] = ["11", 1]
        graph["12"] = {"class_type": "IPAdapterEncoder", "inputs": {"image": ["4", 0]}}
        graph["13"] = {"class_type": "IPAdapterEmbeds", "inputs": {"model": ["14", 0], "pos_embed": ["12", 0]}}
        graph["14"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}}
        graph["6"]["inputs"]["model"] = ["13", 0]
        preset = {key: value for key, value in PRESET.items() if key != "reference"}
        preset.update(reference_slots=[{"role": "style", "binding": ["4", "image"]}], reference_board={"min": 1}, last_reference=["9", "image"])
        result = continuation.capability(preset, graph)
        self.assertEqual((result["operation"], result["reference_count"], result["consumes_source"]), ("restyle", 2, True))
        self.assertEqual((result["source_input"], result["board_min"]), ("last_reference", 1))
        self.assertEqual(continuation.reference_bindings(preset), [["4", "image"], ["9", "image"]])
        # A board without its own pose picture is not a restyle route: the source would have nowhere to go.
        no_pose = {key: value for key, value in preset.items() if key != "last_reference"}
        self.assertEqual(continuation.capability(no_pose, graph)["operation"], "reference-guided-generation")
        self.assertEqual(continuation.capability(no_pose, graph)["source_input"], "reference")

    def test_restyle_continuation_binds_source_to_pose_and_prunes_empty_board_slots(self):
        """Continue with this → Restyle on the shipped Nova board: the source becomes the pose picture, one style
        picture fills Picture 1, the two empty board slots are pruned, and the claim survives dispatch rechecks."""
        catalog = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))
        nova = next(preset for preset in catalog["presets"] if preset["id"] == "style-pose-nova")
        graph_path = self.root / nova["graph"]; shutil.copyfile(ROOT / nova["graph"], graph_path)
        data = json.loads((self.root / "presets/catalog.json").read_text()); data["presets"].append(nova)
        (self.root / "presets/catalog.json").write_text(json.dumps(data))
        cap = next(preset for preset in self.studio.catalog()["presets"] if preset["id"] == "style-pose-nova")["continuation_capability"]
        self.assertEqual((cap["operation"], cap["source_input"], cap["board_min"], cap["reference_count"]), ("restyle", "last_reference", 1, 4))
        import io; from PIL import Image
        stream = io.BytesIO(); Image.new("RGB", (8, 12), "green").save(stream, "PNG")
        style = self.studio.upload("style.png", "image/png", stream.getvalue())
        claim = dict(self.claim, intent="restyle", preset_id="style-pose-nova", template_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest())
        board = lambda first: [dict(role="style", file=first["file"], sha256=first["sha256"]) if first else dict(role="style", file=None), dict(role="style", file=None), dict(role="style", file=None)]
        payload = dict(preset_id="style-pose-nova", controls={"positive": self.attachment["context"]["positive"], "last_reference": self.attachment["file"]},
                       parent_assets=[self.asset_id], references=board(style), continuation=claim)
        preview = self.studio.preview(payload); workflow = preview["workflow"]
        self.assertFalse(preview["submitted"])
        self.assertEqual(workflow["11"]["inputs"]["image"], self.attachment["file"])
        self.assertEqual(workflow["10"]["inputs"]["image"], style["file"])
        self.assertNotIn("30", workflow); self.assertNotIn("31", workflow)
        self.assertEqual(set(workflow["22"]["inputs"]) & {"embed1", "embed2", "embed3"}, {"embed1"})
        self.assertEqual(workflow["2"]["inputs"]["text"], "An adult traveller at the station.")
        # The source must sit on the pose picture, not on a board slot; the board must hold at least one picture.
        moved = copy.deepcopy(payload); moved["controls"].pop("last_reference"); moved["references"] = board(self.attachment)
        with self.assertRaisesRegex(ValueError, "declared source input"): self.studio.prepare(moved)
        empty = copy.deepcopy(payload); empty["references"] = board(None)
        with self.assertRaises(ValueError): self.studio.prepare(empty)
        wrong_intent = copy.deepcopy(payload); wrong_intent["continuation"]["intent"] = "edit"
        with self.assertRaisesRegex(ValueError, "does not support"): self.studio.prepare(wrong_intent)
        swapped = copy.deepcopy(payload); swapped["controls"]["last_reference"] = style["file"]; swapped["references"] = board(self.attachment)
        with self.assertRaisesRegex(ValueError, "declared source input"): self.studio.prepare(swapped)
        job = self.studio.jobs[self.studio.create_job(payload, enqueue=False)["id"]]
        self.assertEqual(job["continuation"], claim)
        preset = self.studio.preset("style-pose-nova"); preset["_prepared_references"] = job["references"]
        self.assertEqual(continuation.validate(self.studio, job, preset, job["graph"], check_runtime=True), claim)
        (self.studio.comfy_root / "input" / self.attachment["file"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "bytes changed"): continuation.validate(self.studio, job, preset, job["graph"], check_runtime=True)

    def test_output_prompt_is_matched_by_prompt_id_not_template_or_batch_index(self):
        self.assertEqual(self.attachment["context"]["positive"], "An adult traveller at the station.")
        second = continuation.source_context(self.studio, self.source_job["outputs"][1]["asset_id"])
        self.assertEqual(second["positive"], "A witch in a meadow.")
        self.source_job["submissions"].reverse()
        self.assertEqual(continuation.source_context(self.studio, self.asset_id)["positive"], self.attachment["context"]["positive"])
        self.assertEqual(self.source_job["controls"]["positive"], "{station|meadow}")

    def test_missing_or_ambiguous_submission_never_uses_example_or_template(self):
        original = copy.deepcopy(self.source_job)
        for mutate in (lambda: self.source_job.update(submissions=[]), lambda: self.source_job.update(prompt_bindings={}), lambda: self.source_job["submissions"].append(copy.deepcopy(self.source_job["submissions"][0]))):
            with self.subTest(mutate=mutate):
                mutate(); self.assertIsNone(continuation.source_context(self.studio, self.asset_id)["positive"])
                self.source_job.clear(); self.source_job.update(copy.deepcopy(original))

    def test_instruction_source_and_imported_image_do_not_fabricate_descriptions(self):
        self.source_job["submissions"][0]["graph"]["1"]["class_type"] = "TextEncodeQwenImageEditPlus"
        self.assertEqual(continuation.source_context(self.studio, self.asset_id)["prompt_role"], "instruction")
        imported = self.studio.import_image("input.png", "image/png", png())
        source = continuation.source_context(self.studio, imported["asset"]["id"])
        self.assertIsNone(source["positive"]); self.assertEqual(source["prompt_origin"], "unavailable")

    def test_catalog_distinguishes_refine_from_same_family_text_generation(self):
        presets = {preset["id"]: preset for preset in self.studio.catalog()["presets"]}
        self.assertTrue(presets["refine"]["continuation_capability"]["consumes_source"])
        self.assertEqual(presets["refine"]["continuation_capability"]["operation"], "image-to-image")
        self.assertFalse(presets["create"]["continuation_capability"]["consumes_source"])

    def test_prepare_binds_source_and_context_survives_persistence(self):
        original = self.graph_path.read_bytes(); preview = self.studio.preview(self.payload)
        self.assertFalse(preview["submitted"]); self.assertTrue(self.studio.queue.empty())
        self.assertEqual(preview["workflow"]["4"]["inputs"]["image"], self.attachment["file"])
        self.assertEqual(preview["workflow"]["1"]["inputs"]["text"], "An adult traveller at the station.")
        self.assertEqual(self.graph_path.read_bytes(), original)
        result = self.studio.create_job(self.payload, enqueue=False); job = self.studio.jobs[result["id"]]
        self.assertEqual(result["continuation"], self.claim)
        self.assertEqual(self.studio.export_recipe(job)["continuation"], self.claim)
        self.assertEqual(json.loads((self.studio.runs / job["id"] / "recipe.json").read_text())["continuation"], self.claim)
        with patch.object(threading.Thread, "start"): restored = server.Studio(self.root)
        self.assertEqual(restored.jobs[job["id"]]["continuation"], self.claim)

    def test_new_image_switch_missing_inputs_and_bad_claims_are_rejected(self):
        wrong = copy.deepcopy(self.payload); wrong["preset_id"] = "create"; wrong["controls"].pop("reference")
        before = set(self.studio.runs.iterdir())
        with self.assertRaisesRegex(ValueError, "source-consuming"): self.studio.create_job(wrong)
        self.assertTrue(self.studio.queue.empty()); self.assertEqual(set(self.studio.runs.iterdir()), before)
        for key in ("positive", "reference"):
            request = copy.deepcopy(self.payload); request["controls"].pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError): self.studio.prepare(request)
        for change in ({"version": True}, {"version": 2}, {"intent": "mesh"}, {"source_sha256": "unknown"}, {"preset_id": "create"}, {"extra": "ignored?"}, {"reference_file": "../escape.png"}):
            request = copy.deepcopy(self.payload); request["continuation"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): self.studio.prepare(request)

    def test_source_template_and_staged_byte_drift_are_rejected(self):
        staged = self.studio.experiments / "uploads" / self.attachment["file"]; raw = staged.read_bytes(); staged.write_bytes(raw + b"changed")
        with self.assertRaisesRegex(ValueError, "bytes changed"): self.studio.prepare(self.payload)
        staged.write_bytes(raw); self.studio.assets.file(self.asset_id).write_bytes(png() + b"changed")
        with self.assertRaisesRegex(ValueError, "Source bytes changed"): self.studio.prepare(self.payload)
        self.studio.assets.file(self.asset_id).write_bytes(png()); self.graph_path.write_text(self.graph_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "destination graph changed"): self.studio.prepare(self.payload)

    def test_graph_consumption_is_required_and_conditioning_only_is_not_refine(self):
        graph = copy.deepcopy(GRAPH); graph["6"]["inputs"]["latent_image"] = ["3", 0]
        self.assertFalse(continuation.consumes_reference(graph, PRESET["reference"]))
        graph["1"]["inputs"]["image"] = ["4", 0]
        self.assertTrue(continuation.consumes_reference(graph, PRESET["reference"]))
        self.assertEqual(continuation.capability(PRESET, graph)["operation"], "reference-guided-generation")
        graph["debug"] = {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}}
        self.assertFalse(continuation.consumes_reference(graph, PRESET["reference"]))

    def test_dispatch_rechecks_runtime_copy_without_retrying(self):
        job = self.studio.jobs[self.studio.create_job(self.payload, enqueue=False)["id"]]
        (self.studio.comfy_root / "input" / self.attachment["file"]).write_bytes(b"changed")
        with patch.object(self.studio, "_wait_for_queue"): self.studio._run(job)
        self.assertEqual(job["status"], "failed"); self.assertEqual(job["prompt_ids"], [])
        self.assertNotIn("pending_submission", job); self.assertIn("No prompt was submitted", job["message"])

    def test_every_declared_source_input_is_explicit_and_dispatch_rechecked(self):
        last = self.studio.upload("last.png", "image/png", png())
        attachment = self.attachment
        claim = dict(self.claim, preset_id="first-last", template_sha256=hashlib.sha256(self.multi_path.read_bytes()).hexdigest())
        payload = dict(preset_id="first-last", controls={"positive": attachment["context"]["positive"], "reference": attachment["file"]}, parent_assets=[self.asset_id], continuation=claim)
        with self.assertRaisesRegex(ValueError, "every declared source input"):
            self.studio.prepare(payload)
        payload["controls"]["last_reference"] = last["file"]
        preview = self.studio.preview(payload)
        self.assertEqual(preview["workflow"]["9"]["inputs"]["image"], last["file"])
        job = self.studio.jobs[self.studio.create_job(payload, enqueue=False)["id"]]
        job["graph"]["9"]["inputs"]["image"] = "authored-last.png"
        with patch.object(self.studio, "_wait_for_queue"): self.studio._run(job)
        self.assertEqual(job["status"], "failed"); self.assertEqual(job["prompt_ids"], [])
        self.assertIn("every declared source input", job["message"])

    def test_legacy_jobs_keep_original_behavior_and_http_route_is_guarded(self):
        result = self.studio.create_job({"preset_id": "create", "controls": {}}, enqueue=False)
        self.assertIsNone(result["continuation"])
        handler = type("ContinuationHandler", (server.Handler,), {"studio": self.studio})
        http = ThreadingHTTPServer(("127.0.0.1", 0), handler); thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        def request(method, path, payload=None):
            client = HTTPConnection("127.0.0.1", http.server_port, timeout=5)
            try:
                client.request(method, path, json.dumps(payload) if payload is not None else None, {"Host": "127.0.0.1:8191", "Origin": "http://127.0.0.1:8191", "Content-Type": "application/json"})
                response = client.getresponse(); return response.status, json.loads(response.read())
            finally: client.close()
        try:
            status, source = request("GET", f"/api/assets/{self.asset_id}/context")
            self.assertEqual(status, 200); self.assertEqual(source["positive"], self.payload["controls"]["positive"])
            wrong = copy.deepcopy(self.payload); wrong["preset_id"] = "create"; wrong["controls"].pop("reference")
            self.assertEqual(request("POST", "/api/jobs", wrong)[0], 400); self.assertTrue(self.studio.queue.empty())
            self.assertEqual(request("POST", "/api/jobs", self.payload)[0], 201); self.assertEqual(self.studio.queue.qsize(), 1)
        finally: http.shutdown(); http.server_close(); thread.join(3)

    @unittest.skipUnless(shutil.which("node"), "Node required for client policy checks")
    def test_client_policy_and_draft_roundtrip(self):
        result = subprocess.run([shutil.which("node"), str(ROOT / "tests/continuation_core.cjs")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ShippedCatalogCapabilityTests(unittest.TestCase):
    def test_every_shipped_preset_yields_a_capability_and_defaults(self):
        """Studio.catalog() swallows capability errors into empty defaults, so a preset shape that breaks
        capability() ships with a blank workbench. Every shipped preset must get through, and every bound
        control must read a default back from its graph."""
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]
        keys = ("positive", "negative", "width", "height", "seed", "steps", "cfg", "denoise", "sampler", "scheduler", "style_weight", "pose_strength")
        for preset in catalog:
            graph = json.loads((root / preset["graph"]).read_text(encoding="utf-8"))
            result = continuation.capability(preset, graph)
            self.assertIn(result["operation"], {"new-image", "unsupported-reference", "masked-repair", "image-to-video", "image-to-3d", "localized-detail", "instruction-edit", "upscale", "image-to-image", "reference-guided-generation", "restyle"}, preset["id"])
            if preset.get("reference_board") and preset.get("last_reference"): self.assertEqual((result["operation"], result["source_input"]), ("restyle", "last_reference"), preset["id"])
            # Restyle a picture starts the sampler from the picture itself (img2img); Style + Pose starts from an empty latent.
            self.assertEqual(result["keeps_picture"], preset["id"].startswith("restyle-"), preset["id"])
            if preset["id"].startswith("restyle-"):
                self.assertEqual(graph["5"]["inputs"]["latent_image"][0], "41"); self.assertEqual(graph["41"]["inputs"]["pixels"][0], "4"); self.assertEqual(graph["4"]["inputs"]["image"][0], str(preset["last_reference"][0]))
                self.assertEqual(graph["14"]["inputs"]["weight_type"], "style transfer"); self.assertEqual(graph["7"]["inputs"]["images"][0], "51"); self.assertEqual(graph["51"]["class_type"], "FaceDetailer")
            for key in keys:
                binding = preset.get(key)
                if binding: self.assertIn(str(binding[1]), graph[str(binding[0])]["inputs"], (preset["id"], key))
