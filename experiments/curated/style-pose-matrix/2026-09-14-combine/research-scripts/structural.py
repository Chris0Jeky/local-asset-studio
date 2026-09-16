"""Structural route on the owner's case: the pose comes from an OpenPose skeleton of the maid picture (xinsir ControlNet),
the character comes from the SHARK picture through IP-Adapter Plus (identity, not style transfer) plus the prompt naming
her. Base: the shipped style-pose-wai graph (WAI v17). Variants: plain IP-Adapter Plus; Plus at 0.5; plus-face adapter stacked."""
import json, time, urllib.request, os, copy, sys
from PIL import Image
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"; OUTDIR = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
POSITIVE = ("1girl, solo, ellen joe, short black hair with red tips, red eyes, black choker, black long-sleeved crop top with red SHARK lettering, "
            "pink dolphin shorts, bare legs, bent forward at the waist, seen from behind, hands on hips, looking back over her shoulder, "
            "full body, plain white background, clean lineart, flat cel shading, masterpiece, best quality")
NEGATIVE = ("bad quality, worst quality, worst detail, sketch, censor, maid, apron, tights, pantyhose, high heels, tail, extra limbs, "
            "bad hands, bad anatomy, text, watermark, multiple girls")
base = json.load(open(REPO + "/workflows/api/style-pose-wai-api.json", encoding="utf-8"))
VARIANTS = {
    "cn-plus07": dict(weight=0.7, face=False, type="linear"),
    "cn-plus05": dict(weight=0.5, face=False, type="linear"),
    "cn-plus07-face": dict(weight=0.7, face=True, type="linear"),
}
def build(name, v, seed):
    g = copy.deepcopy(base)
    g["2"]["inputs"]["text"] = POSITIVE; g["3"]["inputs"]["text"] = NEGATIVE
    g["10"]["inputs"]["image"] = CHAR; g["11"]["inputs"]["image"] = POSE
    # one board picture: route the single embed straight in
    g["14"]["inputs"]["pos_embed"] = ["19", 0]; g["14"]["inputs"]["weight"] = v["weight"]; g["14"]["inputs"]["weight_type"] = v["type"]
    for n in ("20", "21", "22", "30", "31"): g.pop(n, None)
    g["5"]["inputs"]["seed"] = seed
    if v["face"]:
        g["40"] = {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-plus-face_sdxl_vit-h.safetensors"}}
        g["41"] = {"class_type": "IPAdapter", "inputs": {"model": ["14", 0], "ipadapter": ["40", 0], "image": ["10", 0], "weight": 0.5, "start_at": 0.0, "end_at": 0.9, "weight_type": "standard"}}
        g["5"]["inputs"]["model"] = ["41", 0]
    g["7"]["inputs"]["filename_prefix"] = "Research/structural-" + name
    return g
def run(g):
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=30); pid = json.load(r)["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(4)
        h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message", "")[:300] for m in st.get("messages", []) if isinstance(m, list) and m[0] == "execution_error"]
            return pid, st.get("status_str"), round(time.time() - t0, 1), files, err
    return pid, "timeout", round(time.time() - t0, 1), [], []
names = sys.argv[1:] or list(VARIANTS); results = []
for name in names:
    for seed in [int(x) for x in os.environ.get("SEEDS", "2026091411").split(",")]:
        pid, st, secs, files, err = run(build(name, VARIANTS[name], seed))
        print(name, seed, pid[:8], st, secs, files, err, flush=True)
        results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, **VARIANTS[name]))
        json.dump(results, open(OUT + "/structural.json", "w"), indent=1)
tiles = [Image.open(INP + CHAR).convert("RGB"), Image.open(INP + POSE).convert("RGB")] + [Image.open(OUTDIR + f).convert("RGB") for r in results for f in r["files"]]
H = 640; ims = [t.resize((int(t.width * H / t.height), H)) for t in tiles]
sheet = Image.new("RGB", (sum(i.width for i in ims) + 8 * (len(ims) - 1), H), "white"); x = 0
for i in ims: sheet.paste(i, (x, 0)); x += i.width + 8
sheet.save(OUT + "/structural.jpg", quality=85); print("sheet", sheet.size)
