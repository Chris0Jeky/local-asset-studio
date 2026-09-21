"""Proving run for the pose editor (PR #466, 16 September 2026): the panel's own render endpoint draws the guide (POST /api/pose/render with the
"Bent forward, looking back" starting figure, the research KP list at 1024x1536, right ear unknown), then the guide goes through
`combine-klein-9b-skeleton` on the Studio's own path (POST /api/jobs) exactly as *Use this pose* + Generate would submit it: the drawn guide on
Pose skeleton (image 1), the SHARK character on Picture to keep (image 2), the three fills replaced. Same seed as the hand-drawn proving run
(job 26448d58, seed 2026091461) so the thinner `studio.coco18-lines/v1` strokes are compared against the research figure. Evidence:
prove_pose_editor.json next to this file."""
import json, time, urllib.request, urllib.error, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"; W, H = 1024, 1536
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
KP = [(0.23, 0.31), (0.34, 0.17), (0.30, 0.14), (0.27, 0.27), (0.31, 0.31), (0.42, 0.11), (0.55, 0.05), (0.44, 0.30),
      (0.62, 0.30), (0.49, 0.58), (0.20, 0.84), (0.81, 0.31), (0.63, 0.62), (0.68, 0.85), (0.25, 0.28), (0.21, 0.30), None, (0.30, 0.23)]
def post(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:1500]))
guide = post("/api/pose/render", {"width": W, "height": H, "keypoints": [[round(x * W), round(y * H)] if p else None for p in KP for x, y in [p or (0, 0)]]})
assert guide.get("generation_submitted") is False and guide["renderer"] == "studio.coco18-lines/v1", guide
print("guide", guide["file"], guide["width"], guide["height"], guide["sha256"][:12], guide["bytes"], "bytes", flush=True)
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-skeleton")
fills = {
    "[image 1's pose, the hands and the camera in a few words, e.g. bent forward at the waist, one hand on the hip, looking back over the shoulder]": "bent forward deeply at the waist, seen from behind, legs crossed, one arm raised behind the head, looking back over her shoulder",
    "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
    "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet",
}
positive = preset["continuation_prompt"]
for k, v in fills.items(): assert k in positive, k; positive = positive.replace(k, v)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026091461
job = post("/api/jobs", {"preset_id": preset["id"], "controls": {"positive": positive, "last_reference": CHAR, "seed": seed}, "batch_count": 1,
                         "references": [{"file": guide["file"], "role": "pose"}], "parent_assets": []})
print("job", job.get("id"), job.get("message"), flush=True); t0 = time.time()
while time.time() - t0 < 1800:
    time.sleep(5); j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job["id"], timeout=30))
    if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"):
        result = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "references")}
        result.update(positive=positive, seed=seed, guide=guide)
        print(json.dumps(result, indent=1)[:2500], flush=True); json.dump(result, open(OUT + "/prove_pose_editor.json", "w"), indent=1); break
else: print("timeout", job["id"])
