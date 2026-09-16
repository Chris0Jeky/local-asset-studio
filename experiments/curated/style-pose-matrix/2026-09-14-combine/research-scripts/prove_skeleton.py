"""Proving run for `combine-klein-9b-skeleton` through the Studio's own path (POST /api/upload for the drawn skeleton, then POST /api/jobs:
prepare -> worker -> ComfyUI), the shape the page submits. One deliberate run, then evidence (prove_skeleton.json next to this file)."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
SKELETON = OUT + "/pose3-skeleton-drawn.png"
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-skeleton")
body = open(SKELETON, "rb").read()
req = urllib.request.Request(STUDIO + "/api/upload", body, {"Content-Type": "image/png", "X-Filename": "pose3-skeleton-drawn.png", "Origin": STUDIO})
upload = json.load(urllib.request.urlopen(req, timeout=60)); print("upload", upload.get("file"), upload.get("width"), upload.get("height"), flush=True)
fills = {
    "[image 1's pose, the hands and the camera in a few words, e.g. bent forward at the waist, one hand on the hip, looking back over the shoulder]": "bent forward deeply at the waist, seen from behind, legs crossed, one arm raised behind the head, looking back over her shoulder",
    "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
    "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet",
}
positive = preset["continuation_prompt"]
for k, v in fills.items(): assert k in positive, k; positive = positive.replace(k, v)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026091461
intent = {"preset_id": preset["id"], "controls": {"positive": positive, "last_reference": CHAR, "seed": seed}, "batch_count": 1,
          "references": [{"file": upload["file"], "role": "pose"}], "parent_assets": []}
req = urllib.request.Request(STUDIO + "/api/jobs", json.dumps(intent).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
try: job = json.load(urllib.request.urlopen(req, timeout=60))
except urllib.error.HTTPError as e: print("rejected", e.code, e.read().decode("utf-8", "replace")[:1200]); sys.exit(1)
print("job", job.get("id"), job.get("message"), flush=True); t0 = time.time()
while time.time() - t0 < 1800:
    time.sleep(5)
    j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job["id"], timeout=30))
    if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"):
        result = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "references")}
        result["positive"] = positive; result["seed"] = seed; result["skeleton_upload"] = upload
        print(json.dumps(result, indent=1)[:3000], flush=True); json.dump(result, open(OUT + "/prove_skeleton.json", "w"), indent=1); break
else: print("timeout", job["id"])
