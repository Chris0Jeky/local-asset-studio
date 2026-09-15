"""Qwen Image Edit 2511 (Q4_K_M + Lightning 4 steps) with two references on the owner's case: image 1 = identity
(SHARK Ellen Joe), image 2 = pose (maid picture). One seed; the recipe's own graph with a larger latent."""
import json, time, urllib.request, os, copy
from PIL import Image
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"; OUTDIR = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
PROMPT = ("Image 1 - identity and costume: Ellen Joe, a girl with short black hair with red tips, red eyes, a black long-sleeved crop top with red SHARK lettering, pink shorts. Avoid transferring: her pose and the tail.\n"
          "Image 2 - pose only: bent forward at the waist, seen from behind, both hands on the hips, looking back over her shoulder. Avoid transferring: the maid outfit, the tights, the heels, the person.\n\n"
          "Requested result: one picture of the girl from image 1 in exactly the pose of image 2, in image 1's clean anime rendering style, plain light background, single figure, no lettering except SHARK on the top.")
g = json.load(open(REPO + "/workflows/api/qwen-2ref-api.json", encoding="utf-8"))
g["4"]["inputs"]["image"] = CHAR; g["16"]["inputs"]["image"] = POSE
g["6"]["inputs"]["prompt"] = PROMPT; g["7"]["inputs"]["prompt"] = ""
g["20"]["inputs"].update(width=832, height=1248); g["11"]["inputs"]["seed"] = 2026091411
g["13"]["inputs"]["filename_prefix"] = "Research/qwen-pose"
req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
pid = json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]; t0 = time.time(); result = None
while time.time() - t0 < 1800:
    time.sleep(5)
    h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
    if pid in h:
        st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
        err = [m[1].get("exception_message", "")[:300] for m in st.get("messages", []) if isinstance(m, list) and m[0] == "execution_error"]
        result = dict(prompt_id=pid, status=st.get("status_str"), seconds=round(time.time() - t0, 1), files=files, error=err, prompt=PROMPT); break
print(json.dumps(result or dict(prompt_id=pid, status="timeout"), indent=1), flush=True)
json.dump(result, open(OUT + "/qwen-pose.json", "w"), indent=1)
if result and result["files"]:
    tiles = [Image.open(INP + CHAR).convert("RGB"), Image.open(INP + POSE).convert("RGB"), Image.open(OUTDIR + result["files"][0]).convert("RGB")]
    H = 640; ims = [t.resize((int(t.width * H / t.height), H)) for t in tiles]
    sheet = Image.new("RGB", (sum(i.width for i in ims) + 16, H), "white"); x = 0
    for i in ims: sheet.paste(i, (x, 0)); x += i.width + 8
    sheet.save(OUT + "/qwen-pose.jpg", quality=85); print("sheet", sheet.size)
