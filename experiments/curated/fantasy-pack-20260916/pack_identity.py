"""Fantasy pack, identity follow-up (16 September 2026): carry the portrait's identity into the other two steps through reference routes
instead of the seed. Two deliberate Studio jobs on the page's own path (POST /api/jobs), the outputs staged the way Continue with this does
(POST /api/assets/reference):
  A  expression: `flux-edit` (Change one thing, FLUX.2 Klein 4B) on the portrait: only the expression changes.
  B  full body:  `combine-klein-9b-depth` with the portrait as the character (image 2) and the first batch's full-body render as the pose
                 picture (image 1, read as a depth map): the portrait's face and hair in the full-body pose.
Evidence: pack_identity.json next to this file. A step already completed there is skipped unless FORCE=1."""
import json, time, urllib.request, urllib.error, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"; SEED = 2026091301
PORTRAIT = "021731c057d955b4a2487395a37fadf6"; FULLBODY = "025678cadf5750bf9a3bfa8ed62e6590"   # Workspace asset IDs of batch 1 steps 1 and 2
def post(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:1500]))
def wait(job_id):
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(4); j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30))
        if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"): return j
    raise SystemExit("timeout " + job_id)
def record(step, j, extra):
    r = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "parent_assets", "references")}; r["step"] = step; r.update(extra)
    results = json.load(open(OUT + "/pack_identity.json")) if os.path.exists(OUT + "/pack_identity.json") else []
    results.append(r); json.dump(results, open(OUT + "/pack_identity.json", "w"), indent=1); print(json.dumps(r, indent=1)[:1600], flush=True); return r
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
edit = next(p for p in catalog["presets"] if p["id"] == "flux-edit"); depth = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-depth")
portrait = post("/api/assets/reference", {"id": PORTRAIT}); fullbody = post("/api/assets/reference", {"id": FULLBODY})
print("staged", portrait.get("file"), fullbody.get("file"), flush=True)
steps = sys.argv[1:] or ["expression", "fullbody"]
done = {r["step"] for r in (json.load(open(OUT + "/pack_identity.json")) if os.path.exists(OUT + "/pack_identity.json") else []) if r.get("status") == "completed"}
if os.environ.get("FORCE") != "1": steps = [st for st in steps if st not in done or print(st, "already completed (set FORCE=1 to run it again)", flush=True)]
if "expression" in steps:
    positive = edit["continuation_prompt"].replace("{source}", "")
    ph = edit["continuation_placeholder"]; ph = ph[0] if isinstance(ph, list) else ph; assert ph in positive
    positive = positive.replace(ph, "change her expression to a warm, surprised smile with raised eyebrows and the mouth slightly open")
    controls = {"positive": positive, "reference": portrait["file"], "seed": SEED, "width": 832, "height": 1216}
    job = post("/api/jobs", {"preset_id": edit["id"], "controls": controls, "batch_count": 1, "references": [], "parent_assets": [PORTRAIT]})
    print("expression job", job.get("id"), job.get("message"), flush=True); record("expression", wait(job["id"]), {"controls": controls, "source_asset": PORTRAIT})
if "fullbody" in steps:
    positive = depth["continuation_prompt"]
    fills = {"[who is in image 2": "the dark-haired woman in the navy coat from image 2, the same face, hair and earrings",
             "[image 1's pose": "standing upright facing the viewer, full body from head to boots, holding a brass lantern down at her right side, her left hand on the strap of a satchel over her shoulder; the camera at chest height, straight on",
             "[image 2's clothes": "a navy double-breasted travelling coat with brass buttons, a teal scarf, dark trousers, brown lace-up boots"}
    for ph in depth["continuation_placeholder"]:
        key = next(k for k in fills if ph.startswith(k)); assert ph in positive; positive = positive.replace(ph, fills[key])
    controls = {"positive": positive, "last_reference": portrait["file"], "seed": SEED, "width": 1024, "height": 1536}
    job = post("/api/jobs", {"preset_id": depth["id"], "controls": controls, "batch_count": 1, "references": [{"file": fullbody["file"], "role": "pose"}], "parent_assets": [PORTRAIT, FULLBODY]})
    print("fullbody job", job.get("id"), job.get("message"), flush=True); record("fullbody", wait(job["id"]), {"controls": controls, "source_assets": [PORTRAIT, FULLBODY]})
