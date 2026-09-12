"""Build editable Studio recipes from native ComfyUI nodes (no GPU submissions)."""
import copy
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from server import CONTROL_KEYS
from game_asset_pipeline import expanded_input_contract


def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


def visual(graph, title, info):
    """Export ordinary native nodes with fixed seeds and all connections intact."""
    nodes, links = [], []
    ids = {key: i + 1 for i, key in enumerate(graph)}
    for index, (key, item) in enumerate(graph.items()):
        schema = info[item["class_type"]]
        sockets, widgets = [], []
        specs, _ = expanded_input_contract(schema, item['inputs'])
        for field, spec in specs.items():
            if field not in item["inputs"]: continue
            value = item["inputs"][field]
            primitive = isinstance(spec[0], list) or spec[0] in ("INT", "FLOAT", "BOOLEAN", "STRING", "COLOR", "COMBO", "COMFY_DYNAMICCOMBO_V3")
            if isinstance(value, list):
                source, slot = value
                socket = len(sockets); link_id = len(links) + 1
                output_type = info[graph[source]["class_type"]]["output"][slot]
                sockets.append({"name": field, "type": output_type, "link": link_id, **({"widget": {"name": field}} if primitive else {})})
                links.append([link_id, ids[source], slot, ids[key], socket, output_type])
                if primitive:
                    widgets.append(spec[1].get("default", 0) if len(spec) > 1 and isinstance(spec[1], dict) else "")
            elif primitive:
                widgets.append(value)
            if primitive and len(spec) > 1 and isinstance(spec[1], dict) and spec[1].get("control_after_generate"):
                widgets.append("fixed")
        outputs = [{"name": name, "type": typ, "links": []} for name, typ in zip(schema.get("output_name", schema.get("output", [])), schema.get("output", []))]
        nodes.append({"id": ids[key], "type": item["class_type"], "pos": [(index % 4) * 390, (index // 4) * 340], "size": [340, 260], "flags": {}, "order": index, "mode": 0, "inputs": sockets, "outputs": outputs, "properties": {"Node name for S&R": item["class_type"]}, "widgets_values": widgets, "title": item.get("_meta", {}).get("title", schema.get("display_name", item["class_type"]))})
    by_id = {n["id"]: n for n in nodes}
    for link in links: by_id[link[1]]["outputs"][link[2]]["links"].append(link[0])
    return {"last_node_id": len(nodes), "last_link_id": len(links), "nodes": nodes, "links": links, "groups": [], "config": {}, "extra": {"ds": {"scale": 0.7, "offset": [40, 40]}, "studio_title": title}, "version": 0.4}


def build():
    info = json.load(urlopen("http://127.0.0.1:8188/object_info", timeout=20))
    catalog = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))
    catalog["presets"] = [p for p in catalog["presets"] if p.get("collection") != "workflow-lab"]
    index = 30
    def add(preset_id, title, graph, **metadata):
        nonlocal index
        visual_path = f"workflows/comfyui/{index:02d} - {title}.json"; index += 1
        graph_path = f"workflows/api/{preset_id}-api.json"
        for path, data in ((graph_path, graph), (visual_path, visual(graph, title, info))):
            (ROOT / path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        entry = dict(id=preset_id, name=title, category="Workflow Lab", collection="workflow-lab", graph=graph_path, visual=visual_path, verified=False, commercial_note="Review the linked model terms for your intended use.")
        entry.update(metadata)
        catalog["presets"].append(entry)

    # Three complementary SDXL adapters, each with a clean family match.
    base = json.loads((ROOT / "workflows/api/anime-wai-quality-api.json").read_text())
    loras = [("lineani", "Manga Line Art", "LineAniRedmondV2-Lineart-LineAniAF.safetensors", "LineAniAF, black and white manga linework, precise ink contours", .8),
             ("screentone", "Manga Ink and Screentone", "manga-ink-screentone.safetensors", "m4ng41nk, monochrome manga panel, ink shadows, screentone shading", .85),
             ("cinematic-lighting", "Cinematic Anime Lighting", "cinematic lighting.safetensors", "cinematic lighting, dramatic anime illustration, warm rim light, cool shadows", 1.0)]
    common = dict(positive=["2", "text"], negative=["3", "text"], width=["4", "width"], height=["4", "height"], seed=["5", "seed"], steps=["5", "steps"], cfg=["5", "cfg"], sampler=["5", "sampler_name"], scheduler=["5", "scheduler"], choices={"sampler": ["euler", "euler_ancestral", "lms", "dpmpp_2m"], "scheduler": ["normal", "karras", "simple"]})
    for aid, title, filename, trigger, strength in loras:
        for variant in ("portrait", "environment"):
            graph = copy.deepcopy(base)
            graph["1"]["inputs"]["ckpt_name"] = "sd_xl_base_1.0.safetensors"
            subject = "adult wandering swordswoman in a rain-soaked futuristic street, composed expression, layered travel clothing, original character, detailed setting" if variant == "portrait" else "abandoned mountain observatory, immense clouds, winding staircase, cinematic perspective, environment concept art, no text"
            graph["2"]["inputs"].update(text=trigger + ", " + subject, clip=["8", 1])
            graph["3"]["inputs"]["clip"] = ["8", 1]
            graph["4"]["inputs"].update(width=768 if variant == "portrait" else 1024, height=1024 if variant == "portrait" else 768)
            graph["5"]["inputs"].update(model=["8", 0], steps=25, cfg=5.0, sampler_name="lms" if aid == "screentone" else "euler_ancestral", scheduler="normal")
            graph["8"] = node("LoraLoader", model=["1", 0], clip=["1", 1], lora_name=filename, strength_model=strength, strength_clip=strength)
            graph["7"]["inputs"]["filename_prefix"] = f"Studio/{aid}-{variant}"
            add(aid + "-" + variant, title + " - " + variant.title(), graph, **common, lora=["8", "strength_model"], bindings_extra={"lora": [["8", "strength_clip"]]}, modality="image", family="SDXL 1.0", category="Manga & style", description="A family-matched style adapter with an editable seed, sampler and strength. Compare three seeds, then refine your favorite.", stages=["SDXL base", "Style LoRA", "Prompt + seed", "25-step render", "PNG"], source=f"https://huggingface.co/{ {'lineani':'artificialguybr/LineAniRedmond-LinearMangaSDXL-V2','screentone':'strkyyy/manga-ink-screentone','cinematic-lighting':'ntc-ai/SDXL-LoRA-slider.cinematic-lighting'}[aid]}", variants=[{"name": "Quick study", "controls": {"steps": 16}}, {"name": "Quality study", "controls": {"steps": 30}}, {"name": "3-seed audition", "batch_count": 3}])

    # Native H3: no switch nodes or hidden missing image requirement in T2V.
    for mode in ("preview", "quality", "image", "first-last"):
        graph = {
            "1": node("UNETLoader", unet_name="minimax_h3_fl2va_pruned_int8_convrot.safetensors", weight_dtype="default"),
            "2": node("CLIPLoader", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type="minimax", device="default"),
            "3": node("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors"),
            "4": node("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors"),
            "5": node("MiniMaxH3ImageToVideo", clip=["2", 0], vae=["3", 0], prompt="A cinematic anime shot of a small brass lantern glowing on a mossy forest path. The camera slowly pushes in. Fireflies drift, leaves sway, warm light shines on the wet stones. Soft wind, gentle bell chime, quiet forest ambience. One continuous shot, no text.", width=640, height=384, length=124),
            "6": node("RandomNoise", noise_seed=2026091103),
            "7": node("KSamplerSelect", sampler_name="res_multistep"),
            "8": node("BasicScheduler", model=["1", 0], scheduler="simple", steps=20 if mode == "quality" else 8, denoise=1.0),
            "9": node("BasicGuider", model=["1", 0], conditioning=["5", 0]),
            "10": node("SamplerCustomAdvanced", noise=["6", 0], guider=["9", 0], sampler=["7", 0], sigmas=["8", 0], latent_image=["5", 1]),
            "11": node("VAEDecode", samples=["10", 0], vae=["3", 0]),
            "12": node("VAEDecodeAudio", samples=["10", 0], vae=["4", 0]),
            "13": node("CreateVideo", images=["11", 0], audio=["12", 0], fps=24.0),
            "14": node("SaveVideo", video=["13", 0], filename_prefix="Studio/H3-" + mode, format="auto", codec="auto"),
        }
        if mode == "preview":
            graph["5"]["inputs"].update(width=512, height=320, length=39)
            graph["6"]["inputs"]["noise_seed"] = 2026091143
        if mode != "quality":
            graph["15"] = node("LoraLoaderModelOnly", model=["1", 0], lora_name="minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", strength_model=1.0)
            graph["9"]["inputs"]["model"] = ["15", 0]
            graph["8"]["inputs"]["model"] = ["15", 0]
        refs = {}
        if mode in ("image", "first-last"):
            graph["16"] = node("LoadImage", image="lantern-reference.png")
            graph["5"]["inputs"]["first_frame"] = ["16", 0]; refs["reference"] = ["16", "image"]
        if mode == "first-last":
            graph["17"] = node("LoadImage", image="lantern-reference.png")
            graph["5"]["inputs"]["last_frame"] = ["17", 0]; refs["last_reference"] = ["17", "image"]
        add("h3-" + mode, "MiniMax H3 - " + mode.title(), graph, positive=["5", "prompt"], width=["5", "width"], height=["5", "height"], frames=["5", "length"], seed=["6", "noise_seed"], steps=["8", "steps"], **refs,
            modality="video", family="MiniMax H3", category="Video", backend_id="h3", dimension_multiple=32, max_pixels=1344*768, frame_grid=17, frame_offset=5,
            description="Native video + stereo audio. Preview uses the 8-step adapter; quality uses the base model. First/last mode anchors two images. Windows ROCm inference is experimental until measured.",
            commercial_note="MiniMax H3 Community license; territorial and commercial conditions apply. Eligible-territory use confirmed by owner for this session.",
            stages=["Prompt / keyframes", "H3 + text encoder", "8-step turbo" if mode != "quality" else "20-step base", "Video + audio decode", "MP4 at 24fps"],
            variants=([{"name": "Quick audition", "controls": {"width": 512, "height": 320, "frames": 39, "steps": 8}}] if mode == "preview" else []) + [{"name": "Longer shot - experimental", "controls": {"width": 640, "height": 384, "frames": 124}}, {"name": "Native canvas - experimental", "controls": {"width": 1344, "height": 768, "frames": 124}}, {"name": "3-seed audition", "batch_count": 3}],
            source="https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native")

    for quality in ("draft", "detail"):
        graph = {
            "1": node("ImageOnlyCheckpointLoader", ckpt_name="hunyuan_3d_v2.1.safetensors"),
            "2": node("LoadImage", image="lantern-reference.png"),
            "3": node("CLIPVisionEncode", clip_vision=["1", 1], image=["2", 0], crop="center"),
            "4": node("Hunyuan3Dv2Conditioning", clip_vision_output=["3", 0]),
            "5": node("EmptyLatentHunyuan3Dv2", resolution=4096, batch_size=1),
            "6": node("ModelSamplingAuraFlow", model=["1", 0], shift=1.0),
            "7": node("KSampler", model=["6", 0], positive=["4", 0], negative=["4", 1], latent_image=["5", 0], seed=2026091103, steps=20 if quality == "draft" else 30, cfg=5.0, sampler_name="euler", scheduler="normal", denoise=1.0),
            "8": node("VAEDecodeHunyuan3D", samples=["7", 0], vae=["1", 2], num_chunks=8000, octree_resolution=128 if quality == "draft" else 256),
            "9": node("VoxelToMesh", voxel=["8", 0], algorithm="surface net", threshold=.6),
            "10": node("SaveGLB", mesh=["9", 0], filename_prefix="Studio/Hunyuan3D-" + quality),
        }
        add("hunyuan-" + quality, "Hunyuan3D 2.1 - " + quality.title(), graph, reference=["2", "image"], seed=["7", "seed"], steps=["7", "steps"], cfg=["7", "cfg"], modality="3d", family="Hunyuan3D 2.1", category="3D", description="Turn an isolated reference into a downloadable GLB mesh. Draft decodes at 128; detail at 256. Geometry only: UVs, materials, cleanup and rigging are finishing work.", stages=["Reference image", "Shape conditioning", "Geometry diffusion", "Surface extraction", "GLB mesh"], source="https://huggingface.co/Comfy-Org/hunyuan3D_2.1_repackaged", variants=[{"name": "3-seed shape study", "batch_count": 3}])

    for family in ("krea", "anima"):
        for style in ("portrait", "environment"):
            krea = family == "krea"
            title = ("Krea 2 Retro Anime" if krea else "Anima Aesthetic 1.1") + " - " + style.title()
            subject = "adult silver-haired swordswoman in a dark travelling coat, standing under an umbrella on a rainy neon-lit street, teal and crimson lighting, original character, expressive face" if style == "portrait" else "a mountain observatory above a sea of clouds, glowing windows, overgrown stone stairs, richly detailed environment, atmospheric perspective"
            graph = {
                "1": node("UNETLoader", unet_name="krea2_turbo_fp8_scaled.safetensors" if krea else "anima-aesthetic-v1.1.safetensors", weight_dtype="default"),
                "2": node("CLIPLoader", clip_name="qwen3vl_4b_fp8_scaled.safetensors" if krea else "qwen_3_06b_base.safetensors", type="krea2" if krea else "stable_diffusion", device="default"),
                "3": node("VAELoader", vae_name="qwen_image_vae.safetensors"),
                "4": node("CLIPTextEncode", clip=["2", 0], text=("purple retro anime style, " if krea else "masterpiece, best quality, detailed anime illustration, ") + subject),
                "5": node("ConditioningZeroOut", conditioning=["4", 0]) if krea else node("CLIPTextEncode", clip=["2", 0], text="worst quality, low quality, blurry, bad anatomy, bad hands, text, watermark"),
                "6": node("EmptyLatentImage", width=768 if style == "portrait" else 1152, height=1152 if style == "portrait" else 768, batch_size=1),
                "7": node("KSampler", model=["10", 0] if krea else ["1", 0], positive=["4", 0], negative=["5", 0], latent_image=["6", 0], seed=2026091103, steps=8 if krea else 30, cfg=1.0 if krea else 4.0, sampler_name="euler", scheduler="simple", denoise=1.0),
                "8": node("VAEDecode", samples=["7", 0], vae=["3", 0]),
                "9": node("SaveImage", images=["8", 0], filename_prefix=f"Studio/{family}-{style}"),
            }
            bindings = {}
            if krea:
                graph["10"] = node("LoraLoaderModelOnly", model=["1", 0], lora_name="krea2_retroanime.safetensors", strength_model=1.0)
                bindings["lora"] = ["10", "strength_model"]
            else:
                bindings["negative"] = ["5", "text"]
            add(f"{family}-{style}", title, graph, positive=["4", "text"], width=["6", "width"], height=["6", "height"], seed=["7", "seed"], steps=["7", "steps"], cfg=["7", "cfg"], **bindings,
                modality="image", family="Krea 2 Turbo" if krea else "Anima", category="Anime flagship", dimension_multiple=16,
                description="Free official retro-anime adapter on Krea Turbo FP8. A separate interpretation of your reference, with literal prompts and no hidden prompt enhancement." if krea else "A modern anime foundation with a compact Qwen prompt encoder. Mix descriptive prose with character and quality tags; compare seeds before refinement.",
                commercial_note="Krea 2 Community terms apply; free weights do not mean unrestricted use." if krea else "CircleStone Labs Non-Commercial model weights; generated outputs have separate terms in the model card.",
                stages=["Prompt", "Krea Turbo + retro LoRA" if krea else "Anima Aesthetic", "8-step sampling" if krea else "30-step sampling", "Qwen VAE", "PNG"],
                source="https://huggingface.co/Comfy-Org/Krea-2" if krea else "https://huggingface.co/circlestone-labs/Anima",
                variants=([{ "name": "Without style adapter", "controls": {"lora": 0}}, {"name": "Retro anime", "controls": {"lora": 1}}] if krea else [{"name": "Quick study", "controls": {"steps": 20}}, {"name": "Fine study", "controls": {"steps": 36}}]) + [{"name": "3-seed audition", "batch_count": 3}])

    wan = json.loads((ROOT / "workflows/sources/wan22-native.json").read_text())
    for mode in ("t2v", "i2v"):
        graph = copy.deepcopy(wan[mode + "_api_prompt"])
        i2v = mode == "i2v"
        positive, negative, latent, sampler, output = ("5", "6", "7", "9", "12") if i2v else ("4", "5", "6", "8", "11")
        graph[latent]["inputs"]["length"] = 81
        graph[output]["inputs"].update(filename_prefix="Studio/Wan22-" + mode, codec="auto")
        if i2v: graph["4"]["inputs"]["image"] = "lantern-reference.png"
        add("wan22-" + mode, "Wan 2.2 - " + ("Animate Image" if i2v else "Text to Video"), graph,
            positive=[positive, "text"], negative=[negative, "text"], width=[latent, "width"], height=[latent, "height"], frames=[latent, "length"], seed=[sampler, "seed"], steps=[sampler, "steps"], cfg=[sampler, "cfg"], **({"reference": ["4", "image"]} if i2v else {}),
            modality="video", family="Wan 2.2 5B", category="Video", dimension_multiple=32, max_pixels=1280*768, frame_grid=4, frame_offset=1,
            description="Compact native video pipeline. Start with a short motion study, then expand the winning seed. Silent video at 24fps; no separate vision encoder or custom nodes.", commercial_note="Apache-2.0 model package; check rights to supplied reference images.",
            stages=["Image + motion prompt" if i2v else "Motion prompt", "Wan 2.2 5B", "20-step sampling", "Video VAE", "MP4 at 24fps"], source="https://docs.comfy.org/tutorials/video/wan/wan2_2",
            variants=[{"name":"Short motion study", "controls":{"frames":33}}, {"name":"3.4-second shot", "controls":{"frames":81}}, {"name":"3-seed audition", "batch_count":3}])

    trellis = json.loads((ROOT / "workflows/sources/trellis-native-draft.json").read_text())
    for mode in ("rgba", "auto-cutout"):
        graph = copy.deepcopy(trellis)
        graph["1"]["inputs"]["image"] = "studio-lantern-cutout.png" if mode == "rgba" else "lantern-reference.png"
        if mode == "rgba": graph["3"]["inputs"]["pad_factor"] = 1.1
        graph["27"]["inputs"]["filename_prefix"] = "Studio/Trellis2-" + mode
        for key in ("11", "17", "20"): graph[key]["inputs"]["seed"] = 2026091103
        if mode == "auto-cutout":
            graph["28"] = node("LoadBackgroundRemovalModel", bg_removal_name="birefnet.safetensors")
            graph["2"] = node("RemoveBackground", bg_removal_model=["28", 0], image=["1", 0])
        add("trellis-" + mode, "TRELLIS.2 - " + ("Transparent Reference" if mode == "rgba" else "Automatic Cutout"), graph,
            reference=["1", "image"], seed=["11", "seed"], bindings_extra={"seed":[["17", "seed"],["20", "seed"]]},
            modality="3d", family="TRELLIS.2", category="3D", description="512 shape draft with 1024 PBR textures and an interactive GLB preview. " + ("Supply an RGBA image with a transparent background." if mode == "rgba" else "BiRefNet isolates the subject before shape and texture generation.") + " Native Torch route; Radeon compatibility is experimental.",
            stages=["Transparent foreground" if mode == "rgba" else "BiRefNet cutout", "Sparse structure", "512 shape", "Texture diffusion", "UV + PBR bake", "Textured GLB"], source="https://huggingface.co/Comfy-Org/TRELLIS.2", variants=[{"name":"3-seed shape study", "batch_count":3}])

    # Every original recipe remains available, with explicit links into its graph.
    for preset in catalog["presets"]:
        preset.setdefault("modality", "image")
    (ROOT / "presets/catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Built {len(catalog['presets'])} Studio recipes and native visual exports")


if __name__ == "__main__":
    build()
