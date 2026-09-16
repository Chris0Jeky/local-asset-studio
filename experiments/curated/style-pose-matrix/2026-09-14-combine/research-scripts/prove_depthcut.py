"""Proving run for the `combine-klein-9b-depth` recipe with the new `depth_cut` control (16 September 2026), through the Studio's own
path (POST /api/jobs: prepare -> worker -> ComfyUI), the shape the page submits when the "Cut below the ankles (86 %)" variant is chosen.
Same pair, same fills and seed as prove_depth.py (job 22ff6394, the uncut map), so the only change is the cut. Evidence: prove_depthcut.json."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-depth")
assert preset["defaults"].get("depth_cut") == 100, preset["defaults"].get("depth_cut")
fills = {
    "[image 1's pose, the hands and the camera in a few words, e.g. bent forward deeply at the waist, seen from behind and below, one hand on the hip, the other raised to the lips, looking back over the shoulder; the camera is low and behind her]":
        "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder",
    "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
    "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet",
}
positive = preset["continuation_prompt"]
for k, v in fills.items(): assert k in positive, k; positive = positive.replace(k, v)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026091441; cut = int(sys.argv[2]) if len(sys.argv) > 2 else 86
intent = {"preset_id": preset["id"], "controls": {"positive": positive, "last_reference": CHAR, "seed": seed, "depth_cut": cut}, "batch_count": 1,
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
        result["positive"] = positive; result["seed"] = seed; result["depth_cut"] = cut
        print(json.dumps(result, indent=1)[:3000], flush=True); json.dump(result, open(OUT + "/prove_depthcut.json", "w"), indent=1); break
else: print("timeout", job["id"])
