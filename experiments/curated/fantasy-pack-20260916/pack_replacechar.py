"""Fantasy pack, full body that keeps the face (16 September 2026, research straight against ComfyUI, not a Studio recipe yet):
the round-three `replace-character` LoRA (replace_character_v1_klein, pinned) with image 1 = the batch's full-body render (pose, camera,
composition, background kept) and image 2 = the batch's portrait (the face to keep), on the shipped 9B pose-first graph. Three seeds.
Evidence: pack_replacechar.json next to this file (prompt IDs, timing, outputs); the graphs are saved beside it."""
import json, time, urllib.request, os, sys, copy
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
REPO = "C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
FULLBODY = "9c880763266a454091725b57ad392762_Anima-v1-Baseline_00005_.png.png"   # Studio staged copies in ComfyUI's input folder
PORTRAIT = "aa93fb465e364532a33d40dfb21894a9_Anima-v1-Baseline_00004_.png.png"
TEXT = ("Replace the woman in image 1 with the woman in image 2, while keeping the same pose, action, camera angle, composition, background "
        "and lighting as in image 1. The woman in image 2 has long centre-parted dark hair, brown eyes, a calm face and small gold earrings; keep "
        "her face, hair and expression exactly as in image 2. She wears image 1's clothes: a navy double-breasted travelling coat with brass buttons, "
        "a teal scarf, dark trousers, brown lace-up boots, holding a brass lantern, a leather satchel on a strap. Keep image 1's painterly "
        "rendering and its station platform. One figure only, nobody else in the picture.")
base = json.load(open(REPO + "/workflows/api/combine-klein-9b-api.json", encoding="utf-8"))
def build(seed):
    g = copy.deepcopy(base)
    g["14"]["inputs"]["image"] = FULLBODY; g["20"]["inputs"]["image"] = PORTRAIT
    g["40"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "replace_character_v1_klein.safetensors", "strength_model": 1.0, "model": ["1", 0]}}
    g["6"]["inputs"]["model"] = ["40", 0]; g["4"]["inputs"]["text"] = TEXT; g["7"]["inputs"]["noise_seed"] = seed
    g["9"]["inputs"]["width"] = 832; g["9"]["inputs"]["height"] = 1216; g["10"]["inputs"]["width"] = 832; g["10"]["inputs"]["height"] = 1216
    g["13"]["inputs"]["filename_prefix"] = "Research/pack-replacechar"
    return g
def run(g):
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(4); h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["subfolder"] + "/" + o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message") for m in st.get("messages", []) if m[0] == "execution_error"]
            return pid, st.get("status_str"), round(time.time() - t0, 1), files, err
    return pid, "timeout", round(time.time() - t0, 1), [], []
if __name__ == "__main__":
    results = json.load(open(OUT + "/pack_replacechar.json")) if os.path.exists(OUT + "/pack_replacechar.json") else []
    for seed in [int(x) for x in (sys.argv[1:] or ["2026091301", "2026091302", "2026091303"])]:
        g = build(seed); os.makedirs(OUT + "/research-graphs", exist_ok=True); json.dump(g, open(OUT + "/research-graphs/pack-replacechar-%d.graph.json" % seed, "w"), indent=1)
        pid, st, secs, files, err = run(g); print("replacechar", seed, pid[:8], st, secs, files, err, flush=True)
        results.append(dict(variant="replacechar", seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=TEXT, image1=FULLBODY, image2=PORTRAIT, lora="replace_character_v1_klein.safetensors"))
        json.dump(results, open(OUT + "/pack_replacechar.json", "w"), indent=1)
