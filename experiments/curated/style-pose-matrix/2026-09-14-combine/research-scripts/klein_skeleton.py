"""FLUX.2 Klein 9B with an OpenPose skeleton as image 1 (15 September 2026, pose round two).

Why: the Klein models keep image 1's structure, and the pose-first recipe's residual defect is that image 1 is a full picture whose
shoes, tights or tail ghost back in. A skeleton of the pose picture (comfyui_controlnet_aux OpenposePreprocessor, drawn in the graph)
carries the body position and nothing else. Same character picture as image 2, the shipped 9B graph otherwise unchanged (6 steps,
CFG 1.0, 1024x1536)."""
import json, time, urllib.request, os, sys, copy
REPO = r"C:/Users/jekyt/Desktop/Printer Config/Others/Git/local-asset-studio"
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
POSEWORDS = "bent forward deeply at the waist, seen from behind, legs straight, one hand on the hip, looking back over her shoulder"
SKELETON_FIRST = ("Image 1 is a pose skeleton (a stick figure on black) giving the exact body position: " + POSEWORDS + ". Draw Ellen Joe from image 2, "
                  "a girl with short black hair with red tips, red eyes and a black choker, with her body exactly on that skeleton, in image 2's clean anime "
                  "rendering style. She wears image 2's clothes with image 2's colours: a black long-sleeved crop top with red SHARK lettering, bright pink "
                  "shorts, bare legs, bare feet. Replace the black background with a plain light background. No skeleton lines in the result, no tail. "
                  "One figure only, nobody else in the picture.")
DEPTH_FIRST = SKELETON_FIRST.replace("a pose skeleton (a stick figure on black)", "a depth map (a grey silhouette on black)").replace("exactly on that skeleton", "exactly in that silhouette's position").replace("No skeleton lines in the result", "Nothing of the depth map's grey remains")
ANNOTATORS = {
    "openpose": {"class_type": "OpenposePreprocessor", "inputs": {"detect_hand": "enable", "detect_body": "enable", "detect_face": "enable", "resolution": 1024, "scale_stick_for_xinsr_cn": "disable"}},
    "dwpose": {"class_type": "DWPreprocessor", "inputs": {"detect_hand": "enable", "detect_body": "enable", "detect_face": "disable", "resolution": 1024, "bbox_detector": "yolox_l.torchscript.pt", "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt"}},
    "depth": {"class_type": "DepthAnythingV2Preprocessor", "inputs": {"ckpt_name": "depth_anything_v2_vitl.pth", "resolution": 1024}},
}
BLANK_FIRST = SKELETON_FIRST.replace("Image 1 is a pose skeleton (a stick figure on black) giving the exact body position: ", "Image 1 is a blank canvas. Draw this body position on it: ").replace("with her body exactly on that skeleton, ", "").replace("No skeleton lines in the result, no tail", "No tail")
VARIANTS = {
    "9b-blank-first": dict(steps=6, text=BLANK_FIRST, annotator="blank"),
    "9b-skel-first": dict(steps=6, text=SKELETON_FIRST, annotator="openpose"),
    "9b-skel-first-8": dict(steps=8, text=SKELETON_FIRST, annotator="openpose"),
    "9b-dw-first": dict(steps=6, text=SKELETON_FIRST, annotator="dwpose"),
    "9b-depth-first": dict(steps=6, text=DEPTH_FIRST, annotator="depth"),
}
base = json.load(open(REPO + "/workflows/api/combine-klein-9b-api.json", encoding="utf-8"))
def build(name, v, seed):
    g = copy.deepcopy(base)
    g["14"]["inputs"]["image"] = POSE; g["20"]["inputs"]["image"] = CHAR
    if v["annotator"] == "blank": g["30"] = {"class_type": "EmptyImage", "inputs": {"width": 1024, "height": 1536, "batch_size": 1, "color": 0}}
    else: ann = ANNOTATORS[v["annotator"]]; g["30"] = {"class_type": ann["class_type"], "inputs": dict(ann["inputs"], image=["14", 0])}
    g["15"]["inputs"]["image"] = ["30", 0]
    g["31"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "Research/klein-" + name + "-ref", "images": ["30", 0]}}
    g["4"]["inputs"]["text"] = v["text"]; g["9"]["inputs"]["steps"] = v["steps"]; g["7"]["inputs"]["noise_seed"] = seed
    g["13"]["inputs"]["filename_prefix"] = "Research/klein-" + name
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
names = sys.argv[1:] or ["9b-skel-first"]; results = []
if os.path.exists(OUT + "/klein_skeleton.json"): results = json.load(open(OUT + "/klein_skeleton.json"))
for name in names:
    for seed in [int(x) for x in os.environ.get("SEEDS", "2026091411,2026091412").split(",")]:
        g = build(name, VARIANTS[name], seed); json.dump(g, open(OUT + f"/klein-{name}.graph.json", "w"), indent=1)
        pid, st, secs, files, err = run(g)
        print(name, seed, (pid or "-")[:8], st, secs, files, err, flush=True)
        results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=VARIANTS[name]["text"], steps=VARIANTS[name]["steps"], annotator=VARIANTS[name]["annotator"]))
        json.dump(results, open(OUT + "/klein_skeleton.json", "w"), indent=1)
