"""#1163: one prepared plan runs the same Combine pair on several engines with the same seeds. Real catalog entries and
graphs, real prepare and continuation checks, a fake ComfyUI; no inference."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

from test_server import server, FakeStudio
import combine_plan
import production

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('combine-klein', 'combine-klein-9b-depth', 'combine-klein-9b-copypose', 'combine-klein-9b-skeleton')
SOURCE_GRAPH = {
    "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "An adult traveller"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "blur"}},
    "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768}},
    "6": {"class_type": "KSampler", "inputs": {"positive": ["1", 0], "negative": ["2", 0], "latent_image": ["3", 0], "seed": 42, "steps": 4, "cfg": 1}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0]}},
    "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0]}},
}
SOURCE = dict(id="create", name="Source fixture", graph="workflows/api/create.json", modality="image", positive=["1", "text"], negative=["2", "text"], seed=["6", "seed"])
IDLE = {"queue_running": [], "queue_pending": []}
# The worker's own model swap between two different graphs: idle check, memory reading, /free, a second reading.
SWAP = (IDLE, IDLE, {"system": {}, "devices": []}, {}, {"system": {}, "devices": []})
ANSWERS = {"who": "the witch in the black robe", "pose": "leaning forward, one hand on her hip", "clothes": "a black robe with gold trim"}


def picture(colour):
    from PIL import Image
    stream = io.BytesIO(); Image.new("RGB", (8, 12), colour).save(stream, "PNG"); return stream.getvalue()


class CombinePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        for path in ("presets", "config", "workflows/api", "fake-comfy/input", "fake-comfy/output"): (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / SOURCE["graph"]).write_text(json.dumps(SOURCE_GRAPH))
        shipped = {p["id"]: p for p in json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]}
        self.presets = {key: copy.deepcopy(shipped[key]) for key in ENGINES}
        for preset in self.presets.values():
            target = self.root / preset["graph"]; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / preset["graph"], target)
        self.write_catalog()
        self.patches = [patch.object(threading.Thread, "start", lambda *_: None),
                        patch.object(server.Studio, "production_preflight", lambda s, *a: {"test_bundle": True, "comfy_url": s.comfy_url, "comfy_root": str(s.comfy_root)}),
                        patch.object(server.Studio, "check_production_bundle", lambda *a: None),
                        patch.object(server.Studio, "validate_graph", lambda *a: None)]
        for item in self.patches: item.start(); self.addCleanup(item.stop)
        self.studio = self.fresh([])
        created = self.studio.create_job({"preset_id": "create", "controls": {}}, enqueue=False)
        job = self.studio.jobs[created["id"]]; job.update(status="completed", prompt_ids=["p-1"])
        job["submissions"].append(dict(index=0, prompt_id="p-1", graph=copy.deepcopy(job["graph"]), status="completed", seed=42))
        (self.root / "fake-comfy/output/source.png").write_bytes(picture("red"))
        job["outputs"].append(dict(filename="source.png", type="output", subfolder="", prompt_id="p-1", seed=42, media_type="image"))
        self.studio.index_outputs(job); self.studio._save(job)
        self.asset_id = job["outputs"][0]["asset_id"]; self.attachment = self.studio.asset_reference(self.asset_id)
        self.pose = self.studio.upload("pose.png", "image/png", picture("green"))

    def write_catalog(self):
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [SOURCE, *self.presets.values()]}))

    def fresh(self, replies): return FakeStudio(self.root, replies)

    def base(self, preset_id="combine-klein-9b-depth", **controls):
        preset = self.studio.preset(preset_id)
        claim = dict(version=1, intent="combine", preset_id=preset_id, source_asset_id=self.asset_id, source_sha256=self.attachment["sha256"],
                     reference_file=self.attachment["file"], template_sha256=hashlib.sha256((self.root / preset["graph"]).read_bytes()).hexdigest())
        wording = combine_plan.assemble(preset["continuation_prompt"], combine_plan.fill_values(preset, ANSWERS))
        references = [dict(role=slot["role"], contribution="", avoid="", file=None) for slot in preset["reference_slots"]]
        references[0].update(file=self.pose["file"], sha256=self.pose["sha256"])
        return dict(preset_id=preset_id, controls=dict({"positive": wording, "last_reference": self.attachment["file"], "seed": 5}, **controls),
                    parent_assets=[self.asset_id], references=references, continuation=claim)

    def intent(self, engines=("combine-klein-9b-depth", "combine-klein-9b-copypose", "combine-klein"), seeds=(11, 12), **extra):
        plan = dict(base=self.base(), engines=list(engines), seeds=list(seeds), answers=dict(ANSWERS)); plan.update(extra)
        return {"name": "Same pair, three engines", "combine_plan": plan}

    def test_one_plan_pins_every_engine_and_seed_with_its_own_image_order(self):
        lab = self.studio.production; project = lab.create(self.intent()); plan = lab.get(project["id"], full=True)["plan"]
        self.assertEqual(project["state"]["status"], "planned"); self.assertEqual(project["budget"], {"allowance": 6, "reserved": 0})
        self.assertEqual([(s["engine"], s["seed"]) for s in project["stages"]],
                         [(e, s) for e in ("combine-klein-9b-depth", "combine-klein-9b-copypose", "combine-klein") for s in (11, 12)])
        self.assertEqual(project["axis"], "engine"); self.assertEqual(project["combine"]["seeds"], [11, 12])
        self.assertEqual(self.post_count(self.studio), 0); self.assertEqual(self.studio.queue.qsize(), 0)
        # The depth recipe keeps the character on node 20 (image 2); Copy Pose and 4B keep it on node 14 (image 1).
        keep = {"combine-klein-9b-depth": ("20", "14"), "combine-klein-9b-copypose": ("14", "20"), "combine-klein": ("14", "20")}
        for stage in plan["stages"]:
            kept, board = keep[stage["engine"]]
            self.assertEqual(stage["graph"][kept]["inputs"]["image"], self.attachment["file"], stage["engine"])
            self.assertEqual(stage["graph"][board]["inputs"]["image"], self.pose["file"], stage["engine"])
            request = stage["request"]
            self.assertEqual(request["continuation"]["preset_id"], stage["engine"]); self.assertEqual(request["controls"]["seed"], stage["seed"])
            self.assertEqual(request["continuation"]["template_sha256"], hashlib.sha256((self.root / self.presets[stage["engine"]]["graph"]).read_bytes()).hexdigest())
            self.assertEqual([r["file"] for r in request["references"] if r.get("file")], [self.pose["file"]])
            self.assertEqual(combine_plan.continuation.unfilled(self.presets[stage["engine"]], request["controls"]["positive"]), [])
        copypose = next(s for s in plan["stages"] if s["engine"] == "combine-klein-9b-copypose")["request"]["controls"]["positive"]
        self.assertIn(ANSWERS["clothes"], copypose); self.assertIn(ANSWERS["who"], copypose)
        # The 4B recipe has no clothes fill: the clothes ride on who, as the Combine screen's switch does.
        four = next(s for s in plan["stages"] if s["engine"] == "combine-klein")["request"]["controls"]["positive"]
        self.assertIn(ANSWERS["who"] + ", wearing " + ANSWERS["clothes"], four)
        estimate = project["combine"]["estimate"]
        self.assertEqual(set(estimate["per_engine"]), {"combine-klein-9b-depth", "combine-klein-9b-copypose", "combine-klein"})
        self.assertEqual(estimate["total_seconds"], round(sum(estimate["per_engine"][s["engine"]]["estimate_seconds"] for s in project["stages"]), 1))
        self.assertEqual(plan["max_seconds"], combine_plan.default_seconds(estimate))
        self.assertEqual(plan["sha256"], production.fingerprint({k: v for k, v in plan.items() if k != "sha256"}))

    def post_count(self, studio): return sum(1 for args, _ in studio.requests if args and args[0] == "/prompt")

    def test_the_open_recipe_keeps_its_own_wording_and_settings_and_edited_wording_is_used(self):
        base = self.base(depth_cut=80); base["controls"]["positive"] = base["controls"]["positive"] + " Extra owner words."
        edited = combine_plan.assemble(self.presets["combine-klein"]["continuation_prompt"], combine_plan.fill_values(self.presets["combine-klein"], ANSWERS)) + " Owner edit."
        plan = self.studio.production.get(self.studio.production.create({"name": "Edited", "combine_plan": dict(base=base, engines=["combine-klein-9b-depth", "combine-klein"], seeds=[3], answers=ANSWERS, wording={"combine-klein": edited})})["id"], full=True)["plan"]
        depth, four = plan["stages"]
        self.assertTrue(depth["request"]["controls"]["positive"].endswith("Extra owner words.")); self.assertEqual(depth["request"]["controls"]["depth_cut"], 80)
        self.assertEqual(four["request"]["controls"]["positive"], edited); self.assertNotIn("depth_cut", four["request"]["controls"])

    def test_refusals_happen_before_anything_is_stored(self):
        lab = self.studio.production
        cases = [
            (dict(engines=["combine-klein-9b-depth", "combine-klein-9b-skeleton"]), "different input"),
            (dict(engines=["combine-klein", "combine-klein"]), "different Combine recipes"),
            (dict(engines=["create"]), "different input|not a Combine pair"),
            (dict(seeds=[1, 1]), "different whole-number seeds"),
            (dict(seeds=[True]), "whole-number seeds"),
            (dict(seeds=[1, 2, 3, 4, 5]), "one to 4"),
            (dict(answers={"mood": "x"}), "who, pose, clothes and outfit"),
            (dict(wording={"combine-klein-9b-skeleton": "x"}), "chosen recipe"),
            (dict(answers={}), "fill in the wording"),
            (dict(recipe={"preset_id": "create"}), "Unknown Combine plan field"),
        ]
        for extra, message in cases:
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(ValueError, message): lab.create(self.intent(**extra))
        missing = self.intent(); missing["combine_plan"]["base"]["references"][0]["missing"] = True
        with self.assertRaisesRegex(ValueError, "missing picture"): lab.create(missing)
        empty = self.intent(); empty["combine_plan"]["base"]["references"][0].update(file=None)
        with self.assertRaisesRegex(ValueError, "pose picture"): lab.create(empty)
        moved = self.intent(); moved["combine_plan"]["base"]["controls"]["last_reference"] = self.pose["file"]
        with self.assertRaisesRegex(ValueError, "continuation source"): lab.create(moved)
        changed = self.intent(); changed["combine_plan"]["base"]["continuation"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source changed"): lab.create(changed)
        swapped = self.intent(); swapped["combine_plan"]["base"]["references"][0]["sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "combine-klein-9b-depth · seed 11: Reference bytes changed"): lab.create(swapped)
        with self.assertRaisesRegex(ValueError, "Unknown Combine plan field"): lab.create(dict(self.intent(), axis="seed"))
        self.assertEqual(lab.list(), []); self.assertEqual(self.post_count(self.studio), 0)

    def test_a_plan_bigger_than_sixteen_pictures_is_refused(self):
        self.presets.update({f"combine-klein-copy{i}": dict(copy.deepcopy(self.presets["combine-klein"]), id=f"combine-klein-copy{i}") for i in range(3)})
        self.write_catalog()
        engines = ["combine-klein", "combine-klein-9b-depth", "combine-klein-9b-copypose", "combine-klein-copy0", "combine-klein-copy1"]
        with self.assertRaisesRegex(ValueError, "at most 16"): self.studio.production.create(self.intent(engines=engines, seeds=[1, 2, 3, 4]))

    def test_mixed_backends_are_refused(self):
        self.presets["combine-klein"]["backend_id"] = "hidream"; self.write_catalog()
        with patch.object(server.Studio, "catalog", self.unblocked_catalog(server.Studio.catalog)):
            with self.assertRaisesRegex(ValueError, "different backend environments"): self.studio.production.create(self.intent())
        self.assertEqual(self.studio.production.list(), [])

    @staticmethod
    def unblocked_catalog(original):
        def catalog(self):
            data = original(self)
            for preset in data["presets"]: preset["runtime_block"] = None
            return data
        return catalog

    def test_a_blocked_engine_is_refused_by_name(self):
        self.presets["combine-klein"]["backend_id"] = "hidream"; self.write_catalog()
        with self.assertRaisesRegex(ValueError, "Put this character in another picture's pose \\(FLUX.2 Klein 4B\\): Switch to"): self.studio.production.create(self.intent())

    def test_stage_bundles_from_another_runtime_are_refused_and_node_classes_are_unioned(self):
        calls = iter([{"comfy_url": "http://127.0.0.1:8188", "comfy_root": "a", "node_classes": ["A"], "schema_sha256": "x"},
                      {"comfy_url": "http://127.0.0.1:8192", "comfy_root": "b", "node_classes": ["A"]}])
        with patch.object(server.Studio, "production_preflight", lambda *a: next(calls)):
            with self.assertRaisesRegex(ValueError, "same backend environment"): self.studio.production.create(self.intent(engines=["combine-klein"], seeds=[1, 2]))
        calls = iter([{"comfy_url": "u", "comfy_root": "r", "node_classes": ["A"], "schema_sha256": "x"}, {"comfy_url": "u", "comfy_root": "r", "node_classes": ["A", "B"]}])
        with patch.object(server.Studio, "production_preflight", lambda *a: next(calls)), patch.object(server.Studio, "node_contract", lambda s, classes: {c: {} for c in classes}):
            project = self.studio.production.create(self.intent(engines=["combine-klein"], seeds=[1, 2]))
        bundle = self.studio.production.get(project["id"], full=True)["plan"]["bundle"]
        self.assertEqual(bundle["node_classes"], ["A", "B"]); self.assertNotEqual(bundle["schema_sha256"], "x")

    def test_the_plan_records_every_engines_terms_note_once(self):
        preflight = lambda s, preset, graph: {"comfy_url": s.comfy_url, "comfy_root": str(s.comfy_root), "terms_note": preset.get("commercial_note")}
        with patch.object(server.Studio, "production_preflight", preflight):
            project = self.studio.production.create(self.intent(engines=["combine-klein", "combine-klein-9b-depth", "combine-klein-9b-copypose"], seeds=[1, 2]))
        note = self.studio.production.get(project["id"], full=True)["plan"]["bundle"]["terms_note"]
        notes = {self.presets[e]["commercial_note"] for e in ("combine-klein", "combine-klein-9b-depth", "combine-klein-9b-copypose")}
        self.assertEqual(sorted(note.split("\n\n")), sorted(notes), "each engine's terms recorded once, whatever the stage order")

    def test_start_runs_every_stage_on_the_one_worker_and_an_uncertain_stage_is_never_resubmitted(self):
        project = self.studio.production.create(self.intent(engines=["combine-klein-9b-depth", "combine-klein"], seeds=[11]))
        studio = self.fresh([IDLE, {"prompt_id": "depth-11"}, {"depth-11": {"status": {"status_str": "success"}, "outputs": {}}}, *SWAP, URLError("lost POST response")])
        lab = studio.production; lab.start(project["id"]); self.assertEqual(studio.queue.qsize(), 1)
        self.assertEqual(lab.get(project["id"])["budget"], {"allowance": 2, "reserved": 2})
        lab.run(project["id"])
        after = lab.get(project["id"]); self.assertEqual(after["state"]["status"], "uncertain")
        self.assertEqual(self.post_count(studio), 2); self.assertEqual(next(studio.replies, None), None)
        first, second = after["stages"]
        self.assertEqual((first["job"]["preset_id"], first["job"]["status"], first["job"]["project_id"]), ("combine-klein-9b-depth", "completed", project["id"]))
        self.assertEqual(first["job"]["continuation"]["preset_id"], "combine-klein-9b-depth"); self.assertEqual(first["job"]["controls"]["seed"], 11)
        self.assertEqual((second["job"]["preset_id"], second["job"]["status"]), ("combine-klein", "uncertain"))
        restarted = self.fresh([]); restarted.production.resume(project["id"]); restarted.production.run(project["id"])
        self.assertEqual(self.post_count(restarted), 0); self.assertEqual(restarted.production.get(project["id"])["state"]["status"], "uncertain")
        self.assertEqual(restarted.production.get(project["id"])["budget"]["reserved"], 2)

    def test_completed_plan_lands_every_result_as_a_run_of_the_same_pair(self):
        project = self.studio.production.create(self.intent(engines=["combine-klein-9b-depth", "combine-klein-9b-copypose"], seeds=[7]))
        studio = self.fresh([IDLE, {"prompt_id": "a"}, {"a": {"status": {"status_str": "success"}, "outputs": {}}},
                             *SWAP, {"prompt_id": "b"}, {"b": {"status": {"status_str": "success"}, "outputs": {}}}])
        studio.production.start(project["id"]); studio.production.run(project["id"])
        after = studio.production.get(project["id"]); self.assertEqual(after["state"]["status"], "awaiting_review")
        jobs = [studio.public(studio.jobs[s["attempt"]["job_id"]]) for s in after["stages"]]
        for job in jobs:
            self.assertEqual(job["controls"]["last_reference"], self.attachment["file"]); self.assertEqual(job["continuation"]["source_sha256"], self.attachment["sha256"])
            self.assertEqual([r["file"] for r in job["references"] if r.get("file")], [self.pose["file"]])
        self.assertEqual({j["preset_id"] for j in jobs}, {"combine-klein-9b-depth", "combine-klein-9b-copypose"})


class CombinePlanHelperTests(unittest.TestCase):
    def test_fill_values_and_assemble_match_the_combine_screen(self):
        preset = {"continuation_placeholder": ["[who is in image 1, e.g. X]", "[the pose in a few words, e.g. Y]"]}
        values = combine_plan.fill_values(preset, {"who": "Ann", "pose": "sitting", "clothes": "a red coat"})
        self.assertEqual(values, {"[who is in image 1, e.g. X]": "Ann, wearing a red coat", "[the pose in a few words, e.g. Y]": "sitting"})
        self.assertEqual(combine_plan.assemble("Draw [who is in image 1, e.g. X] [the pose in a few words, e.g. Y].", values), "Draw Ann, wearing a red coat sitting.")
        self.assertEqual(combine_plan.assemble("Keep [a].", {"[a]": "  "}), "Keep [a].")
        self.assertEqual(combine_plan.meaning("[image 1's outfit and its colours, e.g. z]"), "outfit")

    def test_references_follow_the_target_slots_and_keep_a_drawn_guide(self):
        guide = {"file": "a" * 32 + "_drawn-pose.png", "sha256": "b" * 64, "artifact_id": "c" * 64, "renderer": "studio.coco18-lines/v1", "role": "style", "extra": 1}
        result = combine_plan.references({"id": "x", "reference_slots": [{"role": "pose"}, {"role": "pose"}]}, [guide])
        self.assertEqual(result[0], {"role": "pose", "contribution": "", "avoid": "", "file": guide["file"], "sha256": guide["sha256"], "artifact_id": guide["artifact_id"], "renderer": guide["renderer"]})
        self.assertEqual(result[1]["file"], None)
        with self.assertRaisesRegex(ValueError, "takes fewer pictures"): combine_plan.references({"id": "x", "reference_slots": [{"role": "pose"}]}, [guide, guide])


if __name__ == "__main__":
    unittest.main()
