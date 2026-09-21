"""Proving run for `combine-klein-9b-copypose` (16 September 2026) through the Studio's own path (POST /api/jobs: prepare -> worker ->
ComfyUI), the shape the page submits: the SHARK crop-top character on Picture to keep (image 1, last_reference), the bent-over fan
picture on Pose picture (image 2, the board slot), the three fills replaced in the wording's reading order. One deliberate run per
seed; evidence in prove_copypose.json next to this file (prompt ID, timing, output)."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
catalog = json.load(urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30))
preset = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-copypose")
assert preset["defaults"].get("lora_name") == "KleinBase9B_PoseTransfer.safetensors" and preset["defaults"].get("lora") == 1.0, preset["defaults"]
fills = {
    "[who is in image 1, e.g. Ellen Joe, a girl with short black hair with red tips]": "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker",
    "[image 1's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]": "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet",
    "[image 2's pose, the hands and the camera in a few words, e.g. bent forward deeply at the waist, seen from behind, legs crossed, looking back over the shoulder]": "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder",
}
positive = preset["continuation_prompt"]
for k, v in fills.items(): assert k in positive, k; positive = positive.replace(k, v)
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2026091471
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
        results = json.load(open(OUT + "/prove_copypose.json")) if os.path.exists(OUT + "/prove_copypose.json") else []
        results.append(result); print(json.dumps(result, indent=1)[:3000], flush=True); json.dump(results, open(OUT + "/prove_copypose.json", "w"), indent=1); break
else: print("timeout", job["id"])
