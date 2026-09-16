"""Fantasy pack, replace-character LoRA, second research batch (16 September 2026, straight against ComfyUI, not a Studio recipe yet):
  chain  image 1 = the depth-Combine output that lost the face (Workspace asset 7a8a5d27, staged through POST /api/assets/reference the way
         *Continue with this* does), image 2 = the batch's portrait: does the pose route + the face route chain? three seeds.
  cross  image 1 = the batch's full-body render, image 2 = the anime SHARK character: does identity cross styles, do image 1's clothes hold? two seeds.
Every accepted prompt ID is written to pack_replacechar_chain.json before polling; a recorded (group, seed) is never submitted again."""
import json, time, urllib.request, urllib.error, os, sys, copy
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"; STUDIO = "http://127.0.0.1:8191"
REPO = "C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"; J = OUT + "/pack_replacechar_chain.json"
FULLBODY = "9c880763266a454091725b57ad392762_Anima-v1-Baseline_00005_.png.png"
PORTRAIT = "aa93fb465e364532a33d40dfb21894a9_Anima-v1-Baseline_00004_.png.png"
SHARK = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
DEPTH_OUTPUT_ASSET = "7a8a5d27c1975ced96ff3d04f2fc7d03"   # Combine/Klein-9B-depth_00005_.png, job 18a4f441
CLOTHES = ("She wears image 1's clothes: a navy double-breasted travelling coat with brass buttons, a teal scarf, dark trousers, brown lace-up boots, "
           "holding a brass lantern, a leather satchel on a strap. ")
TEXT = {
 "chain": ("Replace the woman in image 1 with the woman in image 2, while keeping the same pose, action, camera angle, composition, background and "
           "lighting as in image 1. The woman in image 2 has long centre-parted dark hair with a fringe, brown eyes, a calm face and small gold earrings; "
           "keep her face, hair and expression exactly as in image 2. " + CLOTHES + "Keep image 1's clean rendering and its plain light background. "
           "One figure only, nobody else in the picture."),
 "cross": ("Replace the woman in image 1 with the character in image 2, while keeping the same pose, action, camera angle, composition, background and "
           "lighting as in image 1. The character in image 2 is Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker; "
           "keep her face, hair and expression exactly as in image 2. " + CLOTHES + "Keep image 1's painterly rendering and its station platform. "
           "One figure only, nobody else in the picture."),
}
base = json.load(open(REPO + "/workflows/api/combine-klein-9b-api.json", encoding="utf-8"))
def load(): return json.load(open(J)) if os.path.exists(J) else []
def save(rs): json.dump(rs, open(J, "w"), indent=1)
def post_studio(path, body):
    req = urllib.request.Request(STUDIO + path, json.dumps(body).encode(), {"Content-Type": "application/json", "Origin": STUDIO})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit("rejected %s %s %s" % (path, e.code, e.read().decode("utf-8", "replace")[:800]))
def build(group, image1, image2, seed):
    g = copy.deepcopy(base)
    g["14"]["inputs"]["image"] = image1; g["20"]["inputs"]["image"] = image2
    g["40"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "replace_character_v1_klein.safetensors", "strength_model": 1.0, "model": ["1", 0]}}
    g["6"]["inputs"]["model"] = ["40", 0]; g["4"]["inputs"]["text"] = TEXT[group]; g["7"]["inputs"]["noise_seed"] = seed
    for n in ("9", "10"): g[n]["inputs"]["width"] = 832; g[n]["inputs"]["height"] = 1216
    g["13"]["inputs"]["filename_prefix"] = "Research/pack-replacechar-" + group
    return g
def run(group, image1, image2, seed):
    if any(r["group"] == group and r["seed"] == seed for r in load()): print("skip", group, seed, "(recorded)", flush=True); return
    g = build(group, image1, image2, seed); json.dump(g, open(OUT + "/pack-replacechar-%s-%d.graph.json" % (group, seed), "w"), indent=1)
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]; t0 = time.time()
    rec = dict(group=group, seed=seed, prompt_id=pid, status="submitted", image1=image1, image2=image2, text=TEXT[group], lora="replace_character_v1_klein.safetensors", size="832x1216")
    rs = load(); rs.append(rec); save(rs)
    while time.time() - t0 < 1800:
        time.sleep(4); h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["subfolder"] + "/" + o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message") for m in st.get("messages", []) if m[0] == "execution_error"]
            rec.update(status=st.get("status_str"), seconds=round(time.time() - t0, 1), files=files, error=err); break
    else: rec.update(status="timeout", seconds=round(time.time() - t0, 1))
    rs = [r for r in load() if r["prompt_id"] != pid]; rs.append(rec); save(rs)
    print(group, seed, pid[:8], rec["status"], rec.get("seconds"), rec.get("files"), rec.get("error"), flush=True)
if __name__ == "__main__":
    groups = sys.argv[1:] or ["chain", "cross"]
    if "chain" in groups:
        staged = post_studio("/api/assets/reference", {"id": DEPTH_OUTPUT_ASSET}); print("staged depth output as", staged.get("file"), flush=True)
        for seed in (2026091311, 2026091312, 2026091313): run("chain", staged["file"], PORTRAIT, seed)
    if "cross" in groups:
        for seed in (2026091321, 2026091322): run("cross", FULLBODY, SHARK, seed)
