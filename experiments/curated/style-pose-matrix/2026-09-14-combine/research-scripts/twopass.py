"""Two passes as one Studio journey (15 September 2026): the depth Combine, then Change one thing (FLUX.2 Klein 4B) on its output.

Pass 1 is `combine-klein-9b-depth` through POST /api/jobs exactly as prove_depth.py submits it (the page's prepare/worker path). Pass 2
stages pass 1's output as a reference the way the page's Continue with this does (POST /api/assets/reference with the output's asset id),
then submits `flux-edit` with its one bracketed fill replaced by the correction asked for (a bare foot instead of the heel-shaped one, or the
lettering restored). Both jobs are ordinary Studio jobs with their prompt IDs and evidence under experiments/runs/<job-id>/. Nothing is
resubmitted: a failed or uncertain pass is reported as such. Report: twopass.json next to this file."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
FIX = sys.argv[1] if len(sys.argv) > 1 else "redraw both feet as plain bare feet flat on the ground, with no high heel and no shoe shape"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 2026091451
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = lambda pid: next(p for p in catalog["presets"] if p["id"] == pid)
def post(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:1200]))
def wait(job_id):
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(5); j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30))
        if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"): return j
    return json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30))
def record(j, extra):
    r = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "parent_assets")}; r.update(extra); return r
report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "fix": FIX, "seed": SEED}
# Pass 1: the depth Combine, the three fills replaced as prove_depth.py did.
depth = preset("combine-klein-9b-depth"); positive = depth["continuation_prompt"]
for k, v in {"[image 1's pose, the hands and the camera in a few words, e.g. bent forward deeply at the waist, seen from behind and below, one hand on the hip, the other raised to the lips, looking back over the shoulder; the camera is low and behind her]": "bent forward deeply at the waist, seen from behind and below, legs crossed, her right hand resting on her hip, her left hand raised to her lips holding a lollipop, looking back over her shoulder at the viewer. The camera is low and behind her, looking up",
             "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
             "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet"}.items():
    assert k in positive, k; positive = positive.replace(k, v)
t0 = time.time()
job1 = post("/api/jobs", {"preset_id": depth["id"], "controls": {"positive": positive, "last_reference": CHAR, "seed": SEED}, "batch_count": 1, "references": [{"file": POSE, "role": "pose"}], "parent_assets": []})
print("pass 1 job", job1.get("id"), flush=True); j1 = wait(job1["id"]); report["pass1"] = record(j1, {"positive": positive, "wall_seconds": round(time.time() - t0, 1)})
print(json.dumps(report["pass1"], indent=1)[:1500], flush=True); json.dump(report, open(OUT + "/twopass.json", "w"), indent=1)
if j1.get("status") != "completed" or not j1.get("outputs"): raise SystemExit("pass 1 did not complete; nothing resubmitted")
# Pass 2: stage the output as the page does, then Change one thing on it.
asset_id = j1["outputs"][0]["asset_id"]; staged = post("/api/assets/reference", {"id": asset_id})
edit = preset("flux-edit"); fill = edit["continuation_placeholder"]; fill = fill if isinstance(fill, str) else fill[0]
positive2 = edit["continuation_prompt"].replace(fill, FIX).replace("{source}", "")
t1 = time.time()
job2 = post("/api/jobs", {"preset_id": edit["id"], "controls": {"positive": positive2, "reference": staged["file"], "seed": SEED}, "batch_count": 1, "references": [], "parent_assets": [asset_id]})
print("pass 2 job", job2.get("id"), flush=True); j2 = wait(job2["id"]); report["pass2"] = record(j2, {"positive": positive2, "source_asset": asset_id, "staged_file": staged["file"], "wall_seconds": round(time.time() - t1, 1)})
report["journey_seconds"] = round(time.time() - t0, 1); report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
print(json.dumps(report["pass2"], indent=1)[:1500], flush=True); json.dump(report, open(OUT + "/twopass.json", "w"), indent=1); print("journey", report["journey_seconds"], "s")
