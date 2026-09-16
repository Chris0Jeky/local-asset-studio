"""Klein 9B LoRAs from civitai that claim pose transfer, character replacement or mannequin extraction (15 September 2026, pose round three).

Downloaded and SHA-256-verified with scripts/civitai-fetch.py (receipts in .runtime/downloads/receipts.json, pins in models/library.json):
  KleinBase9B_PoseTransfer.safetensors   "Copy Pose [Qwen & Klein]" (model 2380153 / version 2701726): image 1 = the character to re-pose,
                                          image 2 = the pose; trigger "change the actions and poses in Image 1 to match those in Image 2"
  replace_character_v1_klein.safetensors "[klein 9b] replace character" (2829085 / 3192138): image 1 = the scene whose pose is kept, image 2 =
                                          the identity; no trigger; recommended weight 1.0 (0.8-1.2)
  refcontrol_v2_poses.safetensors         "RefControl FLUX.2 Klein 9B - Reference Pose LoRA" (2732076 / 3071631): image 1 = a pose skeleton,
                                          image 2 = the reference; trigger "apply pose from image 1 with reference from image 2"; weight 0.8-1.0
  Mannequin_V1_F29B.safetensors           "Mannequins / Pose References" (2191265 / 2689061): one reference picture -> CGI mannequins in its pose
Every variant is the shipped 9B graph (CFG 1.0, 1024x1536) with a LoraLoaderModelOnly between the GGUF loader and the guider.
`mannequin-gen` renders one mannequin picture from the owner's pose picture; `mannequin-combine` then feeds that picture into the shipped
depth recipe (combine-klein-9b-depth) as the pose picture, which is the 3D-mannequin test HUMAN_TODO q-28 (b) asks for."""
import json, os, sys, copy, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pose_sources import wording, upload, run, CHAR, POSE, POSEWORDS, WHO, CLOTHES, base9b, basedepth, COMFY_OUT, OUT, DEPTH_MAP
COPY_POSE = ("change the actions and poses in Image 1 to match those in Image 2. The character in image 1 is " + WHO + "; keep her face, hair and "
             "rendering style and her clothes with their colours (" + CLOTHES + "); only her pose and framing change, to image 2's: " + POSEWORDS +
             ". No tights, no heels, no tail. One figure only, nobody else in the picture.")
REPLACE = ("Replace the woman in image 1 with the girl in image 2, while keeping the same pose, action, facial expression, camera angle, composition, "
           "background, and lighting as in image 1. The girl in image 2 is " + WHO + ". She wears image 2's clothes with image 2's colours: " + CLOTHES +
           "; no tights, no heels, no tail. One figure only, nobody else in the picture.")
REFCONTROL = "apply pose from image 1 with reference from image 2. "
MANNEQUIN = ("Generate a picture of CGI mannequins in the exact same pose as the people in the image. The mannequins should have fingers, toes, eyes, and a "
             "detailed facial expression. The mannequins do not have any hair. They have perfectly clean white skin without any discolorations. The background "
             "of the image is a plain featureless shiny black void. Do not include any objects the people in the image may or may not be interacting with. "
             "Do not change the people's pose in any way.")
VARIANTS = {
    "copypose": dict(lora="KleinBase9B_PoseTransfer.safetensors", image1=CHAR, image2=POSE, text=COPY_POSE),
    "copypose-depth": dict(lora="KleinBase9B_PoseTransfer.safetensors", image1=CHAR, image2="depthmap", text=COPY_POSE.replace("image 2's:", "image 2's (a depth map, a grey silhouette on black):")),
    "replacechar": dict(lora="replace_character_v1_klein.safetensors", image1=POSE, image2=CHAR, text=REPLACE),
    "refcontrol-skel": dict(lora="refcontrol_v2_poses.safetensors", image1="pose3-skeleton-drawn.png", image2=CHAR, text=REFCONTROL + wording(POSEWORDS, "a pose skeleton (a coloured stick figure on black)")),
    "refcontrol-depth": dict(lora="refcontrol_v2_poses.safetensors", image1="depthmap", image2=CHAR, text=REFCONTROL + wording(POSEWORDS)),
    "mannequin-gen": dict(lora="Mannequin_V1_F29B.safetensors", image1=POSE, image2=None, text=MANNEQUIN, steps=8, prefix="Research/pose3-mannequin-gen"),
    "mannequin-combine": dict(lora=None, depth=True, image1="mannequin", image2=CHAR, text=wording(POSEWORDS)),
}
def build(name, v, seed, image1):
    g = copy.deepcopy(basedepth if v.get("depth") else base9b)
    g["14"]["inputs"]["image"] = image1
    if v["image2"] is None: g["6"]["inputs"]["positive"] = ["17", 0]; del g["20"]; del g["21"]; del g["22"]; del g["23"]
    else: g["20"]["inputs"]["image"] = v["image2"]
    if v.get("lora"): g["40"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": v["lora"], "strength_model": v.get("strength", 1.0), "model": ["1", 0]}}; g["6"]["inputs"]["model"] = ["40", 0]
    g["4"]["inputs"]["text"] = v["text"]; g["9"]["inputs"]["steps"] = v.get("steps", 6); g["7"]["inputs"]["noise_seed"] = seed
    g["13"]["inputs"]["filename_prefix"] = v.get("prefix", "Research/pose3-" + name)
    return g
def resolve_image1(name, v, results):
    if v["image1"] == "depthmap":
        path = OUT + "/pose3-depth-raw.png"; shutil.copyfile(DEPTH_MAP, path); return upload(path)
    if v["image1"] == "mannequin":
        gen = [r for r in results if r["variant"] == "mannequin-gen" and r["files"]]
        if not gen: raise SystemExit("run mannequin-gen first")
        src = COMFY_OUT + os.path.basename(gen[-1]["files"][-1]); path = OUT + "/pose3-mannequin-gen.png"; shutil.copyfile(src, path); return upload(path)
    return v["image1"]
if __name__ == "__main__":
    names = sys.argv[1:] or ["copypose"]; results = []
    if os.path.exists(OUT + "/lora_pose.json"): results = json.load(open(OUT + "/lora_pose.json"))
    for name in names:
        v = VARIANTS[name]; image1 = resolve_image1(name, v, results)
        if v["image2"] == "depthmap": v["image2"] = resolve_image1(name, dict(image1="depthmap"), results)
        seeds = [2026091411] if name == "mannequin-gen" else [int(x) for x in os.environ.get("SEEDS", "2026091411,2026091412,2026091413").split(",")]
        for seed in seeds:
            g = build(name, v, seed, image1); json.dump(g, open(OUT + "/pose3-" + name + ".graph.json", "w"), indent=1)
            pid, st, secs, files, err = run(g)
            print(name, seed, (pid or "-")[:8], st, secs, files, err, flush=True)
            results.append(dict(variant=name, seed=seed, prompt_id=pid, status=st, seconds=secs, files=files, error=err, text=v["text"], steps=v.get("steps", 6), lora=v.get("lora"), image1=image1, image2=v["image2"]))
            json.dump(results, open(OUT + "/lora_pose.json", "w"), indent=1)
