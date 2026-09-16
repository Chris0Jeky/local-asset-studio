"""Qwen Image Edit 2511 (Q4_K_M + Lightning 4 steps) on the owner's pose case, second round (15 September 2026).

Why: the first Qwen render (qwen_pose.py, prompt 659e4504) was the owner's preferred result but took 14.5 min. The ComfyUI log
shows the model fully loaded in 65 s and the four steps taking 13 min, so the time is the sampling, not the load. The stock
TextEncodeQwenImageEditPlus node rescales every reference to ~1 megapixel for its reference latents whatever size it is given,
so this script feeds the VL encoder through that node without a VAE and appends the reference latents itself (ReferenceLatent,
as the Klein graphs do) at a chosen size. Variants: smaller references (timing), pose picture first (the Klein finding), and an
OpenPose skeleton of the pose picture as the second reference (no costume to leak)."""
import json, time, urllib.request, os, sys
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"
INP = "C:/AI/ComfyUI_windows_portable/ComfyUI/input/"; OUTDIR = "C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
WHO = "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker"
CLOTHES = "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs"
POSEWORDS = "bent forward deeply at the waist, seen from behind, legs straight, one hand on the hip, looking back over her shoulder"
IDENTITY_FIRST = (f"Picture 1 shows {WHO}, wearing {CLOTHES}. Picture 2 shows only the pose to copy. Draw the girl from Picture 1 in exactly the pose of "
                  f"Picture 2: {POSEWORDS}. Keep Picture 1's face, hair, clothes, colours and clean anime rendering style. Do not copy Picture 2's maid "
                  "outfit, tights, heels or tail. Plain light background, one figure only.")
POSE_FIRST = (f"Keep Picture 1 exactly as it is: the same {POSEWORDS} pose, camera angle, framing and background. Replace the person in Picture 1 with "
              f"the girl from Picture 2: {WHO}, drawn in Picture 2's clean anime rendering style. She wears Picture 2's clothes with Picture 2's colours: "
              f"{CLOTHES}, no tights, no heels, no maid outfit, no tail. Nothing of Picture 1's clothing remains. One figure only.")
SKELETON = (f"Picture 1 shows {WHO}, wearing {CLOTHES}. Picture 2 is a pose skeleton (a stick figure on black) giving the body position to copy. Draw the "
            f"girl from Picture 1 with her body in exactly the skeleton's pose: {POSEWORDS}. Keep her face, hair, clothes, colours and clean anime "
            "rendering style. Plain light background, one figure only, no skeleton lines in the result.")
VARIANTS = {
    "ref05": dict(order="identity", text=IDENTITY_FIRST, mp=0.5, skeleton=False),
    "swap05": dict(order="pose", text=POSE_FIRST, mp=0.5, skeleton=False),
    "skel05": dict(order="identity", text=SKELETON, mp=0.5, skeleton=True),
    "ref10": dict(order="identity", text=IDENTITY_FIRST, mp=1.0, skeleton=False),
    "skel10": dict(order="identity", text=SKELETON, mp=1.0, skeleton=True),
    "dw05": dict(order="identity", text=SKELETON, mp=0.5, skeleton="dwpose"),
    "depth05": dict(order="identity", text=SKELETON.replace("a pose skeleton (a stick figure on black)", "a depth map (a grey silhouette on black)").replace("in exactly the skeleton's pose", "exactly in that silhouette's position").replace("no skeleton lines in the result", "nothing of the depth map's grey remains, bare legs, bare feet, no tail"), mp=0.5, skeleton="depth"),
}
def build(name, v, seed):
    first, second = (CHAR, POSE) if v["order"] == "identity" else (POSE, CHAR)
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "qwen-image-edit-2511-Q4_K_M.gguf"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "8": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1.0, "model": ["1", 0]}},
        "9": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.1, "model": ["8", 0]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": first}},
        "16": {"class_type": "LoadImage", "inputs": {"image": second}},
        "5": {"class_type": "ImageScaleToTotalPixels", "inputs": {"upscale_method": "lanczos", "megapixels": v["mp"], "resolution_steps": 1, "image": ["4", 0]}},
        "18": {"class_type": "ImageScaleToTotalPixels", "inputs": {"upscale_method": "lanczos", "megapixels": v["mp"], "resolution_steps": 1, "image": ["16", 0]}},
        "21": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
        "22": {"class_type": "VAEEncode", "inputs": {"pixels": ["18", 0], "vae": ["3", 0]}},
        "6": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"prompt": v["text"], "clip": ["2", 0], "image1": ["5", 0], "image2": ["18", 0]}},
        "7": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"prompt": "", "clip": ["2", 0], "image1": ["5", 0], "image2": ["18", 0]}},
        "23": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["6", 0], "latent": ["21", 0]}},
        "24": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["23", 0], "latent": ["22", 0]}},
        "25": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["7", 0], "latent": ["21", 0]}},
        "26": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["25", 0], "latent": ["22", 0]}},
        "14": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"reference_latents_method": "index_timestep_zero", "conditioning": ["24", 0]}},
        "15": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"reference_latents_method": "index_timestep_zero", "conditioning": ["26", 0]}},
        "20": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 832, "height": 1248, "batch_size": 1}},
        "11": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                                                    "model": ["9", 0], "positive": ["14", 0], "negative": ["15", 0], "latent_image": ["20", 0]}},
        "12": {"class_type": "VAEDecodeTiled", "inputs": {"tile_size": 256, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8, "samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"filename_prefix": "Research/qwen2-" + name, "images": ["12", 0]}},
    }
    if v["skeleton"]:
        if v["skeleton"] == "depth": g["17"] = {"class_type": "DepthAnythingV2Preprocessor", "inputs": {"ckpt_name": "depth_anything_v2_vitl.pth", "resolution": 1024, "image": ["16", 0]}}
        else: g["17"] = {"class_type": "DWPreprocessor", "inputs": {"detect_hand": "enable", "detect_body": "enable", "detect_face": "disable", "resolution": 1024, "bbox_detector": "yolox_l.torchscript.pt", "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt", "image": ["16", 0]}} if v["skeleton"] == "dwpose" else {"class_type": "OpenposePreprocessor", "inputs": {"detect_hand": "enable", "detect_body": "enable", "detect_face": "enable", "resolution": 1024,
                                                                     "scale_stick_for_xinsr_cn": "disable", "image": ["16", 0]}}
        g["18"]["inputs"]["image"] = ["17", 0]
        g["27"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "Research/qwen2-" + name + "-ref", "images": ["17", 0]}}
    return g
def run(g):
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    try: r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e: return None, "rejected", 0, [], [e.read().decode("utf-8", "replace")[:800]]
    pid = r["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 2400:
        time.sleep(5)
        h = json.load(urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30))
        if pid in h:
            st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            err = [m[1].get("exception_message", "")[:300] for m in st.get("messages", []) if isinstance(m, list) and m[0] == "execution_error"]
            return pid, st.get("status_str"), round(time.time() - t0, 1), files, err
    return pid, "timeout", round(time.time() - t0, 1), [], []
names = sys.argv[1:] or ["ref05", "skel05", "swap05"]; results = []
if os.path.exists(OUT + "/qwen_pose2.json"): results = json.load(open(OUT + "/qwen_pose2.json"))
for name in names:
    for seed in [int(x) for x in os.environ.get("SEEDS", "2026091411").split(",")]:
        g = build(name, VARIANTS[name], seed); json.dump(g, open(OUT + f"/qwen2-{name}.graph.json", "w"), indent=1)
        pid, st, secs, files, err = run(g)
        print(name, seed, (pid or "-")[:8], st, secs, files, err, flush=True)
        results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=VARIANTS[name]["text"], mp=VARIANTS[name]["mp"], order=VARIANTS[name]["order"]))
        json.dump(results, open(OUT + "/qwen_pose2.json", "w"), indent=1)
