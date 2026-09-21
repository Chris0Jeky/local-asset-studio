# BATCH 2 summary — chat-ready (2026-09-21 BST)

Merged pack (primary tables in FINDINGS.md § Batch 2 + supplement). Quality = thumbs + ratio + creator. No weight URLs. SFW from nsfwLevel.

## Top signals

1. **True FLUX.2 Klein LoRAs** — Anatomy/Quality Fixer `2324991` (651👍, SFW), Base→Turbo `2324315` (475👍, SFW), Anything2Real `2121900` (1074👍), Portrait Engine `2067704`, Anime→Real Slider `2367207` (SFW), AniEdit `2332320`. Reject Flux.1 D unless Klein/F2 on page.
2. **motimalu Klein-4B vers** of Aesthetic Masterpiece + Flat Color; PixelArtRedmond has Flux klein 9b ver.
3. **Z-Image 16GB:** quantized `2169712`, fp8 `2172944`/`2170391`, Low/High VRAM WF `2184844`, 6G CN `2192289`, Klein GGUF WFs `2325916`/`2400928`.
4. **Animagine still thin** — best utilities: Aesthetic Complete Animagine-v4 `1003636` (2.6k👍), Detail Enhancer `321576`, V3.1 ctx `260267`.
5. **RealVis depth** via EauDeNoire lighting + Skin&Face Pro `1426727` (not bare `query=RealVis`).
6. **Qwen-Image-2.1 LoRAs almost nonexistent** — Randoseru `2493065` (base Qwen 2); stick to GGUF/INT4 appendix; strip Sage on `2951890`.
7. **AMD strip:** SageAttention / Triton / DLSS / RTX VSR — flagged on `2951890`, `2170120`, `2052847`, `2173425`, `2440676`, `579280`.
8. **Pixel Art XL** ≈ Sprite Shaper `277680` (2510👍, SFW) + refiners `10706` / Hard Edge `681332` / PixelArtRedmond `144684`.
9. **Klein WFs:** Pro Grade Hi/Lo `2213699`, Face Swap `2356189`, 4B vs 9B cameras `2323627`, 6-in-1 `2543188`, AIO Pro `2390013`.
10. **Creators:** EauDeNoire lighting (NSFW-biased galleries); VelvetS 40K/Dark Lines; motimalu Aesthetic Complete; YeiYei Disney/Robot; reakaakasky Stabilizer + ZIT fp8.

---

## Categorized links (SendToAgent → Grok)

### FLUX.2 Klein LoRAs (not Flux.1 D)
- https://civitai.com/models/2324991 — Klein Anatomy/Quality Fixer (651👍, SFW)
- https://civitai.com/models/2324315 — Base→Turbo 4B/9B (475👍, SFW)
- https://civitai.com/models/2121900 — Anything2Real F2K 9B (1074👍)
- https://civitai.com/models/2067704 — Portrait Engine Klein (686👍)
- https://civitai.com/models/2343188 — Anything→Real Characters (418👍)
- https://civitai.com/models/2334190 — Klein Detail Slider (266👍, SFW)
- https://civitai.com/models/2442399 — Elusarca Detail Enhancer Klein (263👍, SFW)
- https://civitai.com/models/2438659 — [KLEIN 9b] Detail Slider (248👍)
- https://civitai.com/models/2406218 — Turn2Real (337👍)
- https://civitai.com/models/2367207 — Anime→Real Slider (140👍, SFW)
- https://civitai.com/models/2332320 — AniEdit (130👍)
- https://civitai.com/models/2361340 — Ref2Font (139👍)
- https://civitai.com/models/2417505 — R2I (99👍, SFW)
- https://civitai.com/models/2413760 — Skeleton Pose Extractor (92👍)
- https://civitai.com/models/2662689 — Realistic Detail (80👍, SFW)
- https://civitai.com/models/929497 — Aesthetic Masterpiece klein-4b (cross-ref)
- https://civitai.com/models/1132089 — Flat Color klein-4b (cross-ref)
- https://civitai.com/models/144684 — PixelArtRedmond Flux klein 9b ver

### FLUX.2 Klein workflows / GGUF
- https://civitai.com/models/2213699 — Pro Grade Hi/Lo VRAM (254👍)
- https://civitai.com/models/2325916 — Klein 4B GGUF Simple Fast (96👍)
- https://civitai.com/models/2400928 — Unsloth Klein-4B-GGUF (52👍)
- https://civitai.com/models/2356189 — Face/Head Swap (208👍)
- https://civitai.com/models/2323627 — 4B vs 9B Multi Camera (205👍, SFW)
- https://civitai.com/models/2543188 — Ultimate 6-in-1 (173👍, SFW)
- https://civitai.com/models/2390013 — AIO Pro (165👍)
- https://civitai.com/models/2327242 — 8-ref edit (111👍, SFW)
- https://civitai.com/models/2651727 — PiD low-vram Klein 4B (44👍)
- https://civitai.com/models/2464133 — Rebels Klein 9B-KV GGUF+fp8 (SFW)

### Z-Image Turbo — 16GB / Low VRAM
- https://civitai.com/models/2169712 — Quantized low VRAM (1075👍)
- https://civitai.com/models/2172944 — fp8 reakaakasky (382👍, SFW)
- https://civitai.com/models/2170391 — Kijai FP8 (283👍)
- https://civitai.com/models/2184844 — Pro Low/High VRAM WF [B1]
- https://civitai.com/models/2253524 — Moody Simple [B1]
- https://civitai.com/models/2186721 — Stable_Yogi WF (558👍)
- https://civitai.com/models/2170193 — t2i/i2i 6G (81👍)
- https://civitai.com/models/2192289 — ControlNet 6G (163👍)
- https://civitai.com/models/2343982 — GGUF + Detail Daemon (SFW)
- https://civitai.com/models/2478306 — Head Swap Low VRAM (SFW)
- https://civitai.com/models/2186776 — Z-Image-Art LoRA (323👍)
- https://civitai.com/models/2214707 — Aesthetic LoRA (269👍)
- https://civitai.com/models/2362961 — Fun Distill (307👍)

### Animagine XL4 depth
- https://civitai.com/models/1003636 — Aesthetic Complete Animagine-v4 (2.6k👍)
- https://civitai.com/models/977115 — Aesthetic Best Quality (2.8k👍)
- https://civitai.com/models/321576 — V3 Detail Enhancer (327👍)
- https://civitai.com/models/260267 — V3.1 official (18694👍, SFW)
- https://civitai.com/models/1378329 — Realistic Stylistic (600👍)
- https://civitai.com/models/275687 — Enma Ai XL4 (152👍)
- https://civitai.com/models/409642 — Sansei Muramasa Opt (132👍)
- https://civitai.com/models/401760 — LimbusCompany Style (175👍)
- https://civitai.com/models/1319919 — Stabilizer Animagine [B1]

### RealVis V5 depth
- https://civitai.com/models/1426727 — Skin & Face Pro Photography (1.1k👍)
- https://civitai.com/models/214956 — Cinematic Photography Style (1636👍)
- https://civitai.com/models/391036 — Cucoloris shadow (1723👍)
- https://civitai.com/models/370194 — Translucent SSS (1511👍, SFW)
- https://civitai.com/models/280472 — Chiaroscuro (1400👍)
- https://civitai.com/models/280454 — Rembrandt (1242👍)
- https://civitai.com/models/541620 — Facial Expressions (1197👍)
- https://civitai.com/models/280421 — Low-key lighting (1074👍)
- https://civitai.com/models/562884 — Skin Tone Glamour (1025👍)
- https://civitai.com/models/289500 — Volumetric God Rays (622👍, SFW)

### Qwen-Image-2.1 (base Qwen 2 — not 2511-only)
- https://civitai.com/models/2493065 — Randoseru LoRA Qwen 2 (SFW, sparse)
- https://civitai.com/models/2951814 — 2.1 + prompt enhancer WF
- https://civitai.com/models/2952715 — 2.1 2K Upscale WF
- https://civitai.com/models/2951890 — T2I+Edit — **strip SageAttention** [B1]
- https://civitai.com/models/2952100 — GGUF WFs [B1]
- https://civitai.com/models/2952547 — GGUF ckpt [B1]
- https://civitai.com/models/2951557 — INT8/INT4 [B1]
- https://civitai.com/models/579280 — 2.1 collection — **strip RTX VSR/DLSS** [B1]

### AMD-safe / strip list
- Prefer: https://civitai.com/models/2169712 · https://civitai.com/models/2184844 · https://civitai.com/models/2325916 · https://civitai.com/models/2400928 · https://civitai.com/models/2192289 · https://civitai.com/models/2952100 · https://civitai.com/models/2951557
- Strip Sage/Triton/DLSS/RTX VSR: https://civitai.com/models/2951890 · https://civitai.com/models/2170120 · https://civitai.com/models/2052847 · https://civitai.com/models/2173425 · https://civitai.com/models/2440676 · https://civitai.com/models/579280
- https://rocm.blogs.amd.com/software-tools-optimization/comfyui-fa-backends/README.html

### Pixel Art XL + ZIT/Qwen refiners
- https://civitai.com/models/277680 — Pixel Art Diffusion XL Sprite Shaper (2510👍, SFW)
- https://civitai.com/models/10706 — Z-IMAGE AND QWEN PIXEL ART REFINER (1503👍, SFW)
- https://civitai.com/models/144684 — PixelArtRedmond
- https://civitai.com/models/681332 — Hard Edge Pixel Art ZIT (409👍, SFW)
- https://civitai.com/models/685038 — Soft Pixel Art ZIT
- https://civitai.com/models/2190363 — Elusarca Detailed Pixel ZIT (SFW)
- https://civitai.com/models/620687 — Retro Game CPS II Pixel
- https://civitai.com/models/581162 — Super_PixelArt_XL_M_V1
- https://civitai.com/models/2182113 — PC-98 Style ZIT
- https://civitai.com/models/2481158 — PixelArt Perfect ZIT

### Creators (3–5 keepers each)
**EauDeNoire:** https://civitai.com/models/289500 · https://civitai.com/models/214956 · https://civitai.com/models/280472 · https://civitai.com/models/280454 · https://civitai.com/models/290860  
**VelvetS:** https://civitai.com/models/632900 · https://civitai.com/models/679697 · https://civitai.com/models/954220 · https://civitai.com/models/690505 · https://civitai.com/models/2807075  
**motimalu:** https://civitai.com/models/977115 · https://civitai.com/models/1003636 · https://civitai.com/models/333139 · https://civitai.com/models/337060 · https://civitai.com/models/1252497  
**YeiYeiArt:** https://civitai.com/models/100435 · https://civitai.com/models/35930 · https://civitai.com/models/404277 · https://civitai.com/models/42668 · https://civitai.com/models/2030402  
**reakaakasky:** https://civitai.com/models/971952 · https://civitai.com/models/2172944 · https://civitai.com/models/2356447 · https://civitai.com/models/1523055 · https://civitai.com/models/1519509  

Full tables: FINDINGS.md § Batch 2 · spoken: COMPRESSED.md · sources: SOURCES.md · raw: raw/batch2*/ + raw/batch2/
