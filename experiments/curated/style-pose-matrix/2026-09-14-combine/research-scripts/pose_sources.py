"""Pose round three (15 September 2026): what can stand in for the pose picture on the depth route, and do hand and camera words move anything.

Why: `combine-klein-9b-depth` holds the deep bend (3 of 4 seeds) but the silhouette's heel shapes a foot (#427), the hands and the camera
are not controlled, and the owner's idea is a posing tool ("skeleton editor") as the pose source. Every variant here is the shipped 9B
graph (6 steps, CFG 1.0, 1024x1536, character = image 2) with a different image 1:
  depth-feet      the Depth Anything V2 map of the pose picture with everything below the ankles painted black (heels, floor band)
  depth-painted   the same map with the tail and the skirt frill painted black as well (the #427 "subject only" case, done by hand)
  skeleton-drawn  an OpenPose-style stick figure drawn with PIL from a hand-estimated keypoint list (the owner's skeleton-editor idea)
  mannequin-drawn a grey capsule mannequin drawn with PIL from the same keypoints (a 3D-mannequin / posing-app stand-in, nothing to leak)
  hands-camera    the shipped depth graph (unpainted map) with the pose fill naming both hands and a camera sentence
  depth-8steps    the shipped depth graph at 8 steps
The prepared images are uploaded to ComfyUI's input folder and saved next to this script; prompt IDs go to pose_sources.json and the README."""
import json, time, urllib.request, os, sys, copy, uuid
from PIL import Image, ImageDraw
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
COMFY_OUT = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
DEPTH_MAP = COMFY_OUT + "klein-9b-depth-first-ref_00001_.png"   # Depth Anything V2 vitl at 1024, saved by klein_skeleton.py on 15 Sep
W, H = 1024, 1536
catalog = json.load(open(REPO + "/presets/catalog.json", encoding="utf-8"))
DEPTH_PRESET = next(p for p in catalog["presets"] if p["id"] == "combine-klein-9b-depth")
# The pose fill as shipped after this round (hands and camera named); the batch before the catalog change used the shorter fill text.
FILL_POSE = "[image 1's pose, the hands and the camera in a few words, e.g. bent forward deeply at the waist, seen from behind and below, one hand on the hip, the other raised to the lips, looking back over the shoulder; the camera is low and behind her]"
FILL_WHO = "[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]"
FILL_CLOTHES = "[image 2's clothes and colours, e.g. a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet]"
WHO = "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker"
CLOTHES = "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet"
POSEWORDS = "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder"
HANDS_CAMERA = ("bent forward deeply at the waist, seen from behind and below, legs crossed, her right hand resting on her hip, her left hand "
                "raised to her lips holding a lollipop, looking back over her shoulder at the viewer. The camera is low and behind her, looking up")
def wording(pose_words, image1="a depth map (a grey silhouette on black)"):
    t = DEPTH_PRESET["continuation_prompt"]
    for k, v in ((FILL_POSE, pose_words), (FILL_WHO, WHO), (FILL_CLOTHES, CLOTHES)): assert k in t, k; t = t.replace(k, v)
    return t.replace("a depth map (a grey silhouette on black)", image1).replace("Nothing of the depth map's grey remains", "Nothing of image 1's drawing remains")
# Hand-estimated OpenPose-18 keypoints (fractions of the 1024x1536 canvas) for the bent-over, legs-crossed, look-back pose:
# 0 nose 1 neck 2 Rsho 3 Relb 4 Rwri 5 Lsho 6 Lelb 7 Lwri 8 Rhip 9 Rknee 10 Rank 11 Lhip 12 Lknee 13 Lank 14 Reye 15 Leye 16 Rear 17 Lear
KP = [(0.23, 0.31), (0.34, 0.17), (0.30, 0.14), (0.27, 0.27), (0.31, 0.31), (0.42, 0.11), (0.55, 0.05), (0.44, 0.30),
      (0.62, 0.30), (0.49, 0.58), (0.20, 0.84), (0.81, 0.31), (0.63, 0.62), (0.68, 0.85), (0.25, 0.28), (0.21, 0.30), None, (0.30, 0.23)]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
          (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
def px(p): return (p[0] * W, p[1] * H)
def draw_skeleton(path):
    im = Image.new("RGB", (W, H), "black"); d = ImageDraw.Draw(im)
    for i, (a, b) in enumerate(LIMBS):
        if KP[a] is None or KP[b] is None: continue
        d.line([px(KP[a]), px(KP[b])], fill=COLORS[i], width=14)
    for i, p in enumerate(KP):
        if p is None: continue
        x, y = px(p); d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=COLORS[i])
    im.save(path); return im
def capsule(d, a, b, r, fill):
    (x1, y1), (x2, y2) = px(a), px(b); d.line([(x1, y1), (x2, y2)], fill=fill, width=int(2 * r))
    for x, y in ((x1, y1), (x2, y2)): d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
def draw_mannequin(path):
    im = Image.new("RGB", (W, H), "black"); d = ImageDraw.Draw(im); g = (150, 150, 150); l = (190, 190, 190)
    capsule(d, KP[1], ((KP[8][0] + KP[11][0]) / 2, (KP[8][1] + KP[11][1]) / 2), 95, g)      # torso
    capsule(d, KP[8], KP[11], 80, g)                                                          # pelvis
    for hip, knee, ank in ((8, 9, 10), (11, 12, 13)): capsule(d, KP[hip], KP[knee], 62, l); capsule(d, KP[knee], KP[ank], 46, l)
    for sho, elb, wri in ((2, 3, 4), (5, 6, 7)): capsule(d, KP[sho], KP[elb], 36, l); capsule(d, KP[elb], KP[wri], 30, l)
    x, y = px(KP[0]); d.ellipse([x - 105, y - 95, x + 105, y + 95], fill=g)                   # head
    im.save(path); return im
def paint_depth(path, tail_and_skirt):
    im = Image.open(DEPTH_MAP).convert("RGB"); w, h = im.size; d = ImageDraw.Draw(im)
    d.rectangle([0, int(0.86 * h), w, h], fill="black")                                         # below the ankles: both heels and the floor band
    if tail_and_skirt:
        d.polygon([(int(0.80 * w), int(0.40 * h)), (int(0.92 * w), int(0.17 * h)), (w, int(0.17 * h)), (w, int(0.66 * h)), (int(0.84 * w), int(0.66 * h))], fill="black")
    im.save(path); return im
def upload(path):
    name = os.path.basename(path); boundary = uuid.uuid4().hex; data = open(path, "rb").read()
    head = ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\nContent-Type: image/png\r\n\r\n" % (boundary, name)).encode()
    tail = ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n" % (boundary, boundary)).encode()
    req = urllib.request.Request(COMFY + "/upload/image", head + data + tail, {"Content-Type": "multipart/form-data; boundary=" + boundary})
    return json.load(urllib.request.urlopen(req, timeout=60))["name"]
VARIANTS = {
    "depth-feet": dict(prepared=lambda p: paint_depth(p, False), text=wording(POSEWORDS)),
    "depth-painted": dict(prepared=lambda p: paint_depth(p, True), text=wording(POSEWORDS)),
    "skeleton-drawn": dict(prepared=draw_skeleton, text=wording(POSEWORDS, "a pose skeleton (a coloured stick figure on black)")),
    "mannequin-drawn": dict(prepared=draw_mannequin, text=wording(POSEWORDS, "a grey mannequin silhouette on black")),
    "hands-camera": dict(prepared=None, text=wording(HANDS_CAMERA)),
    "depth-8steps": dict(prepared=None, text=wording(POSEWORDS), steps=8),
    "depth-q8": dict(prepared=None, text=wording(POSEWORDS), unet="flux-2-klein-9b-Q8_0.gguf"),
}
base9b = json.load(open(REPO + "/workflows/api/combine-klein-9b-api.json", encoding="utf-8"))
basedepth = json.load(open(REPO + "/workflows/api/combine-klein-9b-depth-api.json", encoding="utf-8"))
def build(name, v, seed, image1):
    g = copy.deepcopy(basedepth if v["prepared"] is None else base9b)
    g["14"]["inputs"]["image"] = image1; g["20"]["inputs"]["image"] = CHAR
    g["4"]["inputs"]["text"] = v["text"]; g["9"]["inputs"]["steps"] = v.get("steps", 6); g["7"]["inputs"]["noise_seed"] = seed
    if v.get("unet"): g["1"]["inputs"]["unet_name"] = v["unet"]
    g["13"]["inputs"]["filename_prefix"] = "Research/pose3-" + name
    return g
def run(g):
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    try: r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e: return None, "rejected", 0, [], [e.read().decode("utf-8", "replace")[:800]]
    pid = r["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 3600:
        time.sleep(5)
        h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message", "")[:300] for m in st.get("messages", []) if isinstance(m, list) and m[0] == "execution_error"]
            return pid, st.get("status_str"), round(time.time() - t0, 1), files, err
    return pid, "timeout", round(time.time() - t0, 1), [], []
if __name__ == "__main__":
    names = sys.argv[1:] or ["depth-feet"]; results = []
    if os.path.exists(OUT + "/pose_sources.json"): results = json.load(open(OUT + "/pose_sources.json"))
    for name in names:
        v = VARIANTS[name]; image1 = POSE
        if v["prepared"]:
            path = OUT + "/pose3-" + name + ".png"; v["prepared"](path); image1 = upload(path); print("uploaded", image1, flush=True)
        for seed in [int(x) for x in os.environ.get("SEEDS", "2026091411,2026091412,2026091413").split(",")]:
            g = build(name, v, seed, image1); json.dump(g, open(OUT + "/pose3-" + name + ".graph.json", "w"), indent=1)
            pid, st, secs, files, err = run(g)
            print(name, seed, (pid or "-")[:8], st, secs, files, err, flush=True)
            results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=v["text"], steps=v.get("steps", 6), image1=image1))
            json.dump(results, open(OUT + "/pose_sources.json", "w"), indent=1)
