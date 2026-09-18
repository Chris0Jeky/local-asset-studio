import json, time, urllib.request, sys, os
from PIL import Image
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__))
COMFY = "http://127.0.0.1:8188"
IMG1 = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
IMG2 = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
g = json.load(open(REPO + "/workflows/api/combine-klein-api.json", encoding="utf-8"))
tpl = g["4"]["inputs"]["text"]
ph = [p for p in json.load(open(REPO + "/presets/catalog.json", encoding="utf-8"))["presets"] if p["id"] == "combine-klein"][0]["continuation_placeholder"]
text = tpl.replace(ph[0], "Ellen Joe in pink shorts and top with attractive silhouette").replace(ph[1], "bent forward at the waist, seen from behind, both hands on the hips, looking back over her shoulder") + " Leave out the tail."
assert "[" not in text, text
g["4"]["inputs"]["text"] = text
g["14"]["inputs"]["image"] = IMG1; g["20"]["inputs"]["image"] = IMG2
for n in ("24", "25", "26", "27"): g.pop(n)
g["6"]["inputs"]["positive"] = ["23", 0]
g["13"]["inputs"]["filename_prefix"] = "Research/combine-bend"
json.dump({"text": text}, open(OUT + "/prove_bend.wording.json", "w", encoding="utf-8"), indent=1)
results = []
for seed in (2026091411, 2026091412):
    g["7"]["inputs"]["noise_seed"] = seed
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(3)
        h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}).get("status_str"); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            print(seed, pid[:8], st, round(time.time() - t0, 1), files, flush=True); results.append((seed, pid, st, files)); break
        if time.time() - t0 > 900: print(seed, pid, "TIMEOUT"); break
json.dump(results, open(OUT + "/prove_bend.results.json", "w"), indent=1)
base = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"; inp = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"
tiles = [Image.open(inp + IMG1).convert("RGB"), Image.open(inp + IMG2).convert("RGB")] + [Image.open(base + f).convert("RGB") for _, _, _, fs in results for f in fs]
H = 640; ims = [t.resize((int(t.width * H / t.height), H)) for t in tiles]
sheet = Image.new("RGB", (sum(i.width for i in ims) + 8 * (len(ims) - 1), H), "white"); x = 0
for i in ims: sheet.paste(i, (x, 0)); x += i.width + 8
sheet.save(OUT + "/combine-bend-sheet.jpg", quality=85); print("sheet", sheet.size)
