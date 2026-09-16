"""Night audition, 16 September 2026: purposeful Studio jobs (POST /api/jobs, the page's own path) that turn tonight's single proving runs
into small auditions and characterise the new control. Results appended to audition_night.json; every run keeps its prompt ID.
  depthcut  the depth recipe at depth_cut 80 and 92 (seed 2026091441; 86 and 100 already recorded) -> what the hint should say
  editor    the page-rendered guide (same file as the proving run) at two more seeds -> a 3-seed claim for the editor
  copypose  the Copy Pose recipe at two more seeds -> a 3-seed claim through the Studio
  expression the Klein edit on the pack portrait with a stricter instruction (no grin) -> HUMAN_TODO q-30 (e)
Accepted job IDs are written to the JSON before polling and a recorded run is never submitted again (AGENTS.md: an uncertain
outcome is looked up on /api/jobs/<id>, not re-run); hardened after review, the runs above were made before that change.
Usage: python audition_night.py [group ...]"""
import json, time, urllib.request, urllib.error, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
GUIDE = "0d468872db0a4cb0b05a49fd94c4ec0b_drawn-pose.png"
PORTRAIT_ASSET = "021731c057d955b4a2487395a37fadf6"
WHO = "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker"
CLOTHES = "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet"
POSEWORDS = "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder"
SKELWORDS = "bent forward deeply at the waist, seen from behind, legs crossed, one arm raised behind the head, looking back over her shoulder"
def post(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:1500]))
def wait(job_id):
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(5); j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30))
        if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"): return j
    raise SystemExit("timeout " + job_id)
def load(): return json.load(open(OUT + "/audition_night.json")) if os.path.exists(OUT + "/audition_night.json") else []
def save(results): json.dump(results, open(OUT + "/audition_night.json", "w"), indent=1)
def submit(group, body, extra):
    """POST once, persist the accepted job ID immediately, and refuse to resubmit a run that is already recorded (any status)."""
    prior = next((r for r in load() if r.get("group") == group and all(r.get(k) == v for k, v in extra.items())), None)
    if prior: print("skip", group, extra, prior["id"][:8], prior.get("status"), "(recorded; look it up on /api/jobs/<id>, do not run it again)", flush=True); return None
    job = post("/api/jobs", body); results = load(); results.append({"group": group, "id": job["id"], "status": "submitted", **extra}); save(results); return job
def record(group, j, extra):
    r = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error")}; r["group"] = group; r.update(extra)
    results = [x for x in load() if x.get("id") != j.get("id")]; results.append(r); save(results)
    print(group, r.get("seed"), r.get("depth_cut", ""), r["id"][:8], r["status"], round(r.get("elapsed_seconds") or 0, 1), [o["filename"] for o in r.get("outputs") or []], (r.get("error") or "")[:120], flush=True); return r
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30)); P = {p["id"]: p for p in catalog["presets"]}
def filled(preset, values):
    text = preset["continuation_prompt"]
    for ph in preset["continuation_placeholder"]:
        key = next(k for k in values if ph.startswith(k)); assert ph in text; text = text.replace(ph, values[key])
    return text
groups = sys.argv[1:] or ["depthcut", "editor", "copypose", "expression"]
if "depthcut" in groups:
    p = P["combine-klein-9b-depth"]; text = filled(p, {"[who is in image 2": WHO, "[image 1's pose": POSEWORDS, "[image 2's clothes": CLOTHES})
    for cut in (80, 92):
        extra = {"seed": 2026091441, "depth_cut": cut}
        job = submit("depthcut", {"preset_id": p["id"], "controls": {"positive": text, "last_reference": CHAR, "seed": 2026091441, "depth_cut": cut}, "batch_count": 1, "references": [{"file": POSE, "role": "pose"}], "parent_assets": []}, extra)
        if job: record("depthcut", wait(job["id"]), extra)
if "editor" in groups:
    p = P["combine-klein-9b-skeleton"]; text = filled(p, {"[who is in image 2": WHO, "[image 1's pose": SKELWORDS, "[image 2's clothes": CLOTHES})
    for seed in (2026091462, 2026091463):
        extra = {"seed": seed, "guide": GUIDE}
        job = submit("editor", {"preset_id": p["id"], "controls": {"positive": text, "last_reference": CHAR, "seed": seed}, "batch_count": 1, "references": [{"file": GUIDE, "role": "pose"}], "parent_assets": []}, extra)
        if job: record("editor", wait(job["id"]), extra)
if "copypose" in groups:
    p = P["combine-klein-9b-copypose"]; text = filled(p, {"[who is in image 1": WHO, "[image 1's clothes": CLOTHES, "[image 2's pose": POSEWORDS})
    for seed in (2026091472, 2026091473):
        extra = {"seed": seed}
        job = submit("copypose", {"preset_id": p["id"], "controls": {"positive": text, "last_reference": CHAR, "seed": seed}, "batch_count": 1, "references": [{"file": POSE, "role": "pose"}], "parent_assets": []}, extra)
        if job: record("copypose", wait(job["id"]), extra)
if "expression" in groups:
    p = P["flux-edit"]; staged = post("/api/assets/reference", {"id": PORTRAIT_ASSET})
    text = p["continuation_prompt"].replace("{source}", ""); ph = p["continuation_placeholder"]; ph = ph[0] if isinstance(ph, list) else ph
    text = text.replace(ph, "change her expression to surprised: eyebrows raised, eyes a little wider, lips parted slightly as if about to speak, no smile and no grin")
    extra = {"seed": 2026091301, "source_asset": PORTRAIT_ASSET, "instruction": "surprised, no grin"}
    job = submit("expression", {"preset_id": p["id"], "controls": {"positive": text, "reference": staged["file"], "seed": 2026091301, "width": 832, "height": 1216}, "batch_count": 1, "references": [], "parent_assets": [PORTRAIT_ASSET]}, extra)
    if job: record("expression", wait(job["id"]), extra)
