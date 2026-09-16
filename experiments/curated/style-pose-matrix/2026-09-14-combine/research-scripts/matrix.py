"""Research renders straight against ComfyUI for the owner's case: identity = the SHARK crop-top Ellen Joe picture,
pose = the bent-over maid picture. Variants: reference order, steps, LoRA, model. Two seeds each. Usage:
python matrix.py <variant-names...>   (default: all 4B variants)"""
import json, time, urllib.request, sys, os, copy
from PIL import Image
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__))
COMFY = "http://127.0.0.1:8188"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"
OUTDIR = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
WHO = "Ellen Joe, a girl with short black hair with red tips, a black long-sleeved crop top with red SHARK lettering and pink shorts"
POSE_WORDS = "bent forward at the waist, seen from behind, both hands on the hips, looking back over her shoulder"
NORMAL = ("Redraw " + WHO + " from image 1 in the pose of the person in image 2: " + POSE_WORDS + ". Keep the face, the hair, the outfit and its colours, and image 1's rendering style. One figure only, nobody else in the picture. Do not copy the person from image 2, their clothing or their colours. Leave out the tail.")
SWAP = ("Keep image 1 exactly as it is: the same pose, camera angle, framing, lighting and background. Replace the person in image 1 with " + WHO + " from image 2, drawn in image 2's rendering style, wearing image 2's clothes with their colours. One figure only. Leave out the tail.")
SWAP_COLOUR = ("Keep image 1 exactly as it is: the same bent-forward pose, camera angle, framing and background. Replace the person in image 1 with " + WHO + " from image 2, drawn in image 2's clean anime rendering style. She wears image 2's clothes with image 2's colours: a black long-sleeved crop top with red SHARK lettering on the front, bright pink shorts (not black), bare legs, no tights, no heels, no maid outfit. One figure only. Leave out the tail.")
VARIANTS = {
    # name: dict(order, steps, lora, model, text)
    "4b-swap": dict(order="swap", steps=6, lora=None, model="4b", text=SWAP),
    "4b-8steps": dict(order="normal", steps=8, lora=None, model="4b", text=NORMAL),
    "4b-aniedit": dict(order="normal", steps=6, lora=("AniEdit-Klein4B.safetensors", 1.0), model="4b", text=NORMAL),
    "4b-swap-aniedit": dict(order="swap", steps=6, lora=("AniEdit-Klein4B.safetensors", 1.0), model="4b", text=SWAP),
    "9b-normal": dict(order="normal", steps=6, lora=None, model="9b", text=NORMAL),
    "9b-swap": dict(order="swap", steps=6, lora=None, model="9b", text=SWAP),
    "9b-swap-anime": dict(order="swap", steps=6, lora=("Klein9B_Anime_V3_Refined.safetensors", 0.8), model="9b", text=SWAP),
    "9b-swap-colour": dict(order="swap", steps=6, lora=None, model="9b", text=SWAP_COLOUR),
    "9b-swap-8": dict(order="swap", steps=8, lora=None, model="9b", text=SWAP_COLOUR),
}
base = json.load(open(REPO + "/workflows/api/combine-klein-api.json", encoding="utf-8"))

def build(v, seed):
    g = copy.deepcopy(base)
    for n in ("24", "25", "26", "27"): g.pop(n)
    g["6"]["inputs"]["positive"] = ["23", 0]
    img1, img2 = (CHAR, POSE) if v["order"] == "normal" else (POSE, CHAR)
    g["14"]["inputs"]["image"] = img1; g["20"]["inputs"]["image"] = img2
    g["4"]["inputs"]["text"] = v["text"]; g["9"]["inputs"]["steps"] = v["steps"]; g["7"]["inputs"]["noise_seed"] = seed
    if v["model"] == "9b":
        g["1"] = {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux-2-klein-9b-Q6_K.gguf"}}
        g["2"]["inputs"]["clip_name"] = "qwen_3_8b_fp8mixed.safetensors"
    if v["lora"]:
        g["30"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": v["lora"][0], "strength_model": v["lora"][1]}}
        g["6"]["inputs"]["model"] = ["30", 0]
    g["13"]["inputs"]["filename_prefix"] = "Research/matrix-" + v["name"]
    return g

def run(g):
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    pid = json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 1500:
        time.sleep(3)
        h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message", "")[:200] for m in st.get("messages", []) if isinstance(m, list) and m[0] == "execution_error"]
            return pid, st.get("status_str"), round(time.time() - t0, 1), files, err
    return pid, "timeout", round(time.time() - t0, 1), [], []

names = sys.argv[1:] or ["4b-swap", "4b-8steps", "4b-aniedit", "4b-swap-aniedit"]
results = []
for name in names:
    v = dict(VARIANTS[name], name=name)
    for seed in [int(x) for x in os.environ.get('SEEDS','2026091411,2026091412').split(',')]:
        pid, st, secs, files, err = run(build(v, seed))
        print(name, seed, pid[:8], st, secs, files, err, flush=True)
        results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=v["text"], order=v["order"], steps=v["steps"], lora=v["lora"], model=v["model"]))
        json.dump(results, open(OUT + "/matrix-" + "-".join(names) + ".json", "w"), indent=1)
tiles = [Image.open(INP + CHAR).convert("RGB"), Image.open(INP + POSE).convert("RGB")] + [Image.open(OUTDIR + f).convert("RGB") for r in results for f in r["files"]]
H = 640; ims = [t.resize((int(t.width * H / t.height), H)) for t in tiles]
sheet = Image.new("RGB", (sum(i.width for i in ims) + 8 * (len(ims) - 1), H), "white"); x = 0
for i in ims: sheet.paste(i, (x, 0)); x += i.width + 8
sheet.save(OUT + "/matrix-" + "-".join(names) + ".jpg", quality=85); print("sheet", sheet.size)
