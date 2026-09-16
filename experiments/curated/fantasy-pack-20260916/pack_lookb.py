"""Fantasy character pack, first four-step batch (16 September 2026): the owner's look B (anima-v1-baseline, slot 1 nsfw_girls_anima at 1.0,
seed 2026091301, 832x1216, 30 steps, CFG 4.5, euler/simple) through the brief's four steps, each a deliberate Studio job
(POST /api/jobs: prepare -> worker -> ComfyUI, the page's own path), then one documented correction through the repair route
(the output staged with POST /api/assets/reference as Continue with this does, then anime-detail-fix on it). Evidence in pack_lookb.json
next to this file: job IDs, prompt IDs, outputs, timing. Nothing here is art acceptance; the four outputs land in the Workspace
review queue for the owner (HUMAN_TODO).

Usage: python pack_lookb.py [step ...]   steps: portrait fullbody expression fix   (default: all four in order)"""
import json, time, urllib.request, urllib.error, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"; SEED = 2026091301
CHARACTER = ("A fully clothed adult original character with long dark hair wears a tailored navy travelling coat with brass buttons, a high-neck "
             "shirt, trousers and leather boots, teal scarf")
NEG = "worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, bad anatomy, bad hands, extra digits, missing fingers, text, watermark"
STEPS = {
    "portrait": CHARACTER + ". Three-quarter portrait, upper body, her face in focus with a calm, attentive expression, both hands visible holding a small brass lantern in front of her, soft evening light on a rain-washed station platform, detailed modern anime illustration, cinematic composition.",
    "fullbody": CHARACTER + ". Full body, standing calmly on a rain-washed station platform, one hand holding a brass lantern at her side, the other resting on the strap of a leather satchel, boots and coat hem visible, soft evening light, detailed modern anime illustration, cinematic composition.",
    "expression": CHARACTER + ". Three-quarter portrait, upper body, a warm surprised smile with raised eyebrows as she looks slightly to the side, both hands visible holding a small brass lantern in front of her, soft evening light on a rain-washed station platform, detailed modern anime illustration, cinematic composition.",
}
def post(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:1500]))
def wait(job_id):
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(4)
        j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30))
        if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"): return j
    raise SystemExit("timeout " + job_id)
def record(step, j, extra):
    r = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "parent_assets", "references")}; r["step"] = step; r.update(extra)
    results = json.load(open(OUT + "/pack_lookb.json")) if os.path.exists(OUT + "/pack_lookb.json") else []
    results.append(r); json.dump(results, open(OUT + "/pack_lookb.json", "w"), indent=1); print(json.dumps(r, indent=1)[:1800], flush=True); return r
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
base = next(p for p in catalog["presets"] if p["id"] == "anima-v1-baseline"); fix = next(p for p in catalog["presets"] if p["id"] == "anime-detail-fix")
assert base["defaults"]["lora_name"] == "nsfw_girls_anima.safetensors", base["defaults"]
def run_base(step):
    controls = {"positive": STEPS[step], "negative": NEG, "seed": SEED, "width": 832, "height": 1216, "steps": 30, "cfg": 4.5, "sampler": "euler", "scheduler": "simple", "denoise": 1.0,
                "lora": 1.0, "lora_name": "nsfw_girls_anima.safetensors", "lora2": 0, "lora3": 0, "lora4": 0, "lora5": 0, "lora6": 0}
    for attempt in (1, 2):
        job = post("/api/jobs", {"preset_id": base["id"], "controls": controls, "batch_count": 1, "references": [], "parent_assets": []})
        print(step, "job", job.get("id"), job.get("message"), flush=True); j = wait(job["id"])
        # The first checkpoint swap of a ComfyUI session can die with an IndexError in free_memory (memory note, 14 Sep); a clean
        # failure with that signature is retried once. An uncertain outcome is never resubmitted.
        if j["status"] == "failed" and attempt == 1 and "IndexError" in str(j.get("error") or ""): record(step, j, {"retried": True, "attempt": 1}); continue
        return record(step, j, {"attempt": attempt, "controls": controls})
def run_fix(source):
    asset_id = source["outputs"][0]["asset_id"]; staged = post("/api/assets/reference", {"id": asset_id})
    controls = {"positive": STEPS[source["step"]], "reference": staged["file"], "seed": SEED}
    job = post("/api/jobs", {"preset_id": fix["id"], "controls": controls, "batch_count": 1, "references": [], "parent_assets": [asset_id]})
    print("fix job", job.get("id"), job.get("message"), flush=True); j = wait(job["id"])
    return record("fix", j, {"source_step": source["step"], "source_job": source["id"], "source_asset": asset_id, "staged": staged.get("file"), "controls": controls})
if __name__ == "__main__":
    steps = sys.argv[1:] or ["portrait", "fullbody", "expression", "fix"]; done = {}
    if os.path.exists(OUT + "/pack_lookb.json"):
        for r in json.load(open(OUT + "/pack_lookb.json")):
            if r.get("status") == "completed" and r["step"] != "fix": done[r["step"]] = r
    for step in steps:
        if step == "fix":
            src = done.get(os.environ.get("FIX_SOURCE", "portrait")) or next(iter(done.values()), None)
            if not src: raise SystemExit("no completed base step to correct")
            run_fix(src)
        else:
            r = run_base(step)
            if r and r["status"] == "completed": done[step] = r
