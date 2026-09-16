"""Proving run for `combine-klein-9b-depth` through the Studio's own path (POST /api/jobs: prepare -> worker -> ComfyUI), the
same shape the page submits (see the 09cdf30b job record of the 9B pose-first proving run). One deliberate run, then evidence."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-depth")
fills = {
    "[image 1's pose in a few words, e.g. bent forward at the waist, hands on hips]": "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder",
    "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
    "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet",
}
positive = preset["continuation_prompt"]
for k, v in fills.items(): assert k in positive, k; positive = positive.replace(k, v)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026091441
intent = {"preset_id": preset["id"], "controls": {"positive": positive, "last_reference": CHAR, "seed": seed}, "batch_count": 1,
          "references": [{"file": POSE, "role": "pose"}], "parent_assets": []}
req = urllib.request.Request(STUDIO + "/api/jobs", json.dumps(intent).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
try: job = json.load(urllib.request.urlopen(req, timeout=60))
except urllib.error.HTTPError as e: print("rejected", e.code, e.read().decode("utf-8", "replace")[:1200]); sys.exit(1)
print("job", job.get("id"), job.get("message"), flush=True); t0 = time.time()
while time.time() - t0 < 1800:
    time.sleep(5)
    j = json.load(urllib.request.urlopen(STUDIO + "/api/jobs/" + job["id"], timeout=30))
    if j.get("status") in ("completed", "failed", "not_submitted", "uncertain", "abandoned"):
        result = {k: j.get(k) for k in ("id", "status", "preset_id", "prompt_ids", "outputs", "elapsed_seconds", "error", "references")}
        result["positive"] = positive; result["seed"] = seed
        print(json.dumps(result, indent=1)[:3000], flush=True); json.dump(result, open(OUT + "/prove_depth.json", "w"), indent=1); break
else: print("timeout", job["id"])
