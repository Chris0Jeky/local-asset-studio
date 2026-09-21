# BATCH 2 browser notes — 2026-09-21

Public pages only. No login. No weight downloads. Civitai search sort URLs (`sortBy=Highest%20Rated` / `Most%20Downloaded`) were rewritten client-side to `sortBy=models_v9` (UI label **Relevancy**). Cloudflare did **not** block. Card “thumbs” digits are rolling animations (digits duplicated in the DOM); counts below are from the model header or the public models API, cross-checked against visible cards.

16GB AMD Comfy filter used throughout: prefer fp8 / GGUF / 4–8 step turbo; **skip Nunchaku/SVDQ (NVIDIA-only)** and **SageAttention** workflows.

## Gap vs batch 1

- **Qwen-Image-2.1 LoRA: still empty.** Query `Qwen-Image-2.1` + type LoRA returns older **Qwen-Image / Edit-2511 / Klein / Krea 2** LoRAs, not 2.1. Base-model filter `Qwen 2` + type LoRA returns ~16 newest LoRAs; **none** of their titles or descriptions claim 2.1 (they say 2512, Krea2, ZIT, LTX, or generic style). Version JSON on [2952100](https://civitai.com/models/2952100) T2I says: **“2.1 doesnt have a base model available in selection yet.”** That is why a “2.1 LoRA” filter cannot exist yet. Do not treat Edit-2511 Lightning or `2567623` Intentional Decay (base tagged Qwen 2, no 2.1 claim) as 2.1-compatible.
- **Animagine XL 4 LoRA “Highest Rated”** is almost all character LoRAs on base `SDXL 1.0`. Utility signal is still [1319919](https://civitai.com/models/1319919) Stabilizer (already in LINKS) plus a thin saturation LoRA. No new general style stack.
- **RealVisXL LoRA search** returns one tagged portrait LoRA ([2605632](https://civitai.com/models/2605632), already in LINKS). RealVis use is still the V5 checkpoint + generic SDXL detail LoRAs, not a RealVis-named LoRA family.
- **Klein / Flux.2** search is healthy and explicitly base-tagged `Flux.2 Klein 9B` / `9B-base` / `4B` (not Flux.1). Top cards are utility sliders from l226 / anyMODE / alcaitiff, mostly SFW. Body/bust sliders are flagged NSFW-adjacent even when `nsfw=false`.

## 1. Flux.2 Klein LoRA (browser search `Klein`, type LoRA, 478 results)

| id | title | base | thumbs / dl | vibe | why 16GB AMD |
|---|---|---|---|---|---|
| 2324991 | Klein Anatomy / Quality Fixer | Flux.2 Klein 9B | 651 / 24.7k | SFW utility | Small slider LoRA; negative weight ≈ anatomy negative prompt. Author says 4B quality is poor without it. Already linked; confirmed live. |
| 2324315 | Klein 4B/9B Base to Turbo Lora | Flux.2 Klein 9B-base | 475 / 17.4k | SFW | Difference LoRA: adds turbo back onto base so you can trade CFG vs speed. anyMODE. |
| 2334190 | Klein Detail Slider | Flux.2 Klein 9B | 266 / 6.1k | SFW | I2I detail on a blurry/low-res photo; no style lock. |
| 2438659 | [KLEIN 9b] Detail Slider | Flux.2 Klein 9B | 248 / 4.9k | SFW | Second detail slider (alcaitiff); compare to 2334190 before stacking. |
| 2474084 | Ultimate Upscaler Klein-9b | Flux.2 Klein 9B | 460 / 9.6k | SFW restore | **Use fast variant, 4 steps (max 12).** Prompt is fixed “restore the image quality…”. Avoids 20-step base. Google Drive workflow linked, not required. |
| 2442399 | Elusarca Detail Enhancer | Flux.2 Klein 9B | 263 / 7.6k | SFW | Strength 0.7–1.0 on bad images, 0.3–0.6 on good ones. Already linked. |
| 2859218 | Detail Reconstruction + Upscaler + Workflow | Flux.2 Klein 9B | 33 / 726 | SFW portrait | Bundled workflow; author loads `flux-2-klein-9b-fp8`. Trigger `zqvx, sharpen the image…`. Built to avoid a male-hair artifact of other upscale LoRAs. |
| 2662689 | Flux2 Klein 9B Realistic Detail | Flux.2 Klein 9B | 80 / 1.5k | SFW realism | Detail without a full style convert. |
| 2327604 | Klein Chiaroscuro Slider | Flux.2 Klein 9B | ~85 visible on card / 1.2k dl | SFW lighting | Lighting slider, not a character. |
| 2413760 | Flux 2 Klein Image Edit Skeleton Pose Extractor | Flux.2 Klein 9B | 92 / 1.1k | SFW pose tool | Edit LoRA for pose extraction, not a style. |
| 2413450 | Retro comic (PULPKHOR) | Flux.2 Klein 9B | 44 / 454 | SFW style | Explicit Flux.2 Klein 9B style, not Flux.1. |
| 2680498 | Airbrush it! | Flux.2 Klein 9B | 31 / 562 | SFW illustration | Named Flux.2 Klein 9B style LoRA. |
| 2515526 | Flux 2 Klein 4B Outpaint Lora | Flux.2 Klein 4B | 11 / 347 | SFW tool | 4B outpaint; lighter than 9B if VRAM is tight. |
| 2367207 | Anime to Real Slider | Flux.2 Klein 9B-base | 140 / 2.8k | SFW convert | Slider, pair with Klein base→turbo. |
| 2343298 | Arcane Style | Flux.2 Klein 9B | 46 / 954 | SFW style | Named Klein 9B, not Flux.1. |

Skip for default stack: [2318844](https://civitai.com/models/2318844) Body Weight Slider (344 thumbs, 9.5k dl, anatomy) and [2327035](https://civitai.com/models/2327035) Bust Slider. “AI Babe Pack” parts (2436391 etc.) are character packs, `nsfw=false` but not studio utilities.

Browser top row matched API: Anatomy Fixer, Base-to-Turbo, Body Weight Slider, Detail Slider, alcaitiff Detail Slider.

## 2. Z-Image Turbo — Low VRAM

Browser search `Z-Image Turbo` (2,312 results, relevancy). First cards: official checkpoint, then **SVDQ 4bit / Nunchaku** cover on the quant page, then anime AIO, then Turbo+Base workflow.

| id | title | base | thumbs / dl | vibe | why 16GB AMD |
|---|---|---|---|---|---|
| 2168935 | Z Image Turbo (official) | ZImageTurbo | 8.7k / 95k | SFW page; model is uncensored-capable | Description: **fits 16G VRAM**, **8 NFEs**, photoreal + bilingual text. BF16 file is ~11.7 GB — too tight with TE. Prefer the quant page. |
| 2169712 | Quantized for low VRAM | ZImageTurbo | 1.1k / 37k | SFW | **AMD pick: `fp8_scaled_e4m3fn_KJ` ~5.9 GB.** Nunchaku/svdq-int4 is **RTX-only** (page warns Nunchaku discontinued; native nvfp4/int8). Steps **5–15 (sweet 6–11), CFG 1.0** (negatives ignored). Photo: euler + beta/simple. |
| 2176468 | ti2i workflow, **16GB VRAM** in the title | ZImageTurbo | 30 / 1.4k | SFW workflow | Explicit 16GB callout: metadata, upscale, controlnet, FaceDetailer. |
| 2184844 | Pro Grade Low or High VRAM | ZImageTurbo | 848 / 33.6k | SFW, node-heavy | Low/High VRAM toggle, v27.1 lighting fix. Already linked. Heavy custom nodes. |
| 2588499 | High / Low VRAM + 4k upscale + Detail Daemon | ZImageTurbo | 33 / 796 | SFW | Another explicit low-VRAM branch. |
| 2172270 | Simple Diffusion/GGUF (T2I, I2I, upscale) | ZImageTurbo | 50 / 2.7k | SFW | GGUF path for AMD; smaller than bf16. |
| 2193133 | Z-Image Turbo workflow gguf | tagged SD 1.5 (mislabeled) | 8 / 726 | SFW | GGUF unet + optional fp8_scaled from 2169712. Ignore the SD1.5 base tag. |
| 2439528 | GGUF: LoRA One-Click + Upscaler | ZImageTurbo | 14 / 516 | SFW | One-click LoRA + upscale on GGUF. |
| 2186721 | Stable_Yogi workflow | ZImageTurbo | 558 / 28.6k | SFW | Documents both bf16 and `z_image_turbo-Q4_K_S.gguf` plus Qwen3-4B TE. |
| 2170134 | Z Image (Turbo & Base) Workflow | ZImageTurbo | high card (1.5k shown) | SFW | Top browser card; Turbo and Base in one graph. |
| 2362961 | Z-Image Fun Distill Lora | **ZImageBase** not Turbo | 307 / 8.0k | SFW speed | For **base**, not Turbo. 4–10 steps, **CFG 1**, **avoid SageAttention** (AMD-relevant). Samplers: dpmpp_sde, lcm, er_sde. Strength ~0.8. |
| 2409672 | Z-Image Turbo Lightning | ZImageTurbo | 204 / 3.9k | SFW speed | 4–8 steps, LoRA strength 0.5–1.0, euler. Can hurt text. |
| 2190193 | UltraReal workflow | ZImageTurbo | 274 / 10.5k | SFW realism | High-download realism graph. |

Skip: [2190716](https://civitai.com/models/2190716) “NSFW Uncensored … 4–6 GB” (title is NSFW). Skip Nunchaku cover on 2169712 even though it is the second search card.

## 3. Qwen-Image-2.1 LoRA

**No LoRA found that claims Qwen-Image-2.1 compatibility.** Searches opened/queried: `Qwen-Image-2.1` Highest Rated, type LoRA, quoted `"Image 2.1" LoRA`, and base model `Qwen 2`. Hits are workflows/checkpoints already in batch 1 (`579280`, `2951557`, `2951890`, `2952100`, `2952547`, `2951814`, `2952715`) plus pre-2.1 LoRAs (Edit-2511, Qwen-Image, Klein, Famegrid). Do not import Edit-2511 Lightning as a 2.1 LoRA.

## 4. Model pages 2952547 and 2952100

### [2952547](https://civitai.com/models/2952547) Qwen Image 2.1 GGUF — checkpoint, base tag QWEN, updated 2026-09-20

- Header: **4 thumbs, 44 downloads**, 3 comments, 0 buzz. No comments in gallery.
- Download panel: **Q8_0 GGUF “BEST MATCH”, 8-bit, 7.16 GB**, verified hours ago. Also Q-sizes in the API (~4.0 GB and ~6.9 GB files).
- Loader called out in the description: **molbal** `ComfyUI-GGUF` / `comfyui-gguf-reboot` (not only city96).
- **Sampler (visible in description): steps 25, CFG 1, euler, simple.** T2I seed fixed; edit workflow randomizes seed.
- Resolution: native **2K**; template defaults 1:1 at 1 MP (~1024). Set ~**4.0 MP** for 2048². Edit: `custom_size` off follows `image_1` aspect scaled to `resolution` (default 1024, multiple of 32). Set resolution 0 to keep reference size. Prompt addresses refs as `<image1>`.
- **No LoRA warning and the word “LoRA” does not appear on the page.** Gap is “no LoRA ecosystem yet,” not a negative warning.

### [2952100](https://civitai.com/models/2952100) Qwen Image 2.1 GGUFs — workflows, tag **QWEN IMAGE 2.1**, updated 2026-09-20

- Header: **5 thumbs, 60 downloads**. Versions **EDIT** and **T2I**. Selected EDIT download is a **21.99 KB JSON** (workflow only, not weights).
- Quant notes on page: **Q4_K_M = recommended size/quality**; Q8_0 highest; Q3/Q2 = lower VRAM, test before production. Quality varies by sampler/resolution.
- Needs the rest of the 2.1 stack (text encoder + VAE). Diffusion-only GGUF. Source is Comfy-Org BF16. Install notes point at **city96** `ComfyUI-GGUF` (Windows paths).
- **No sampler recipe and no LoRA warning on the visible description.** The **T2I version description** (in page JSON, not the EDIT tab) is only: **“2.1 doesnt have a base model available in selection yet.”** That is the LoRA-compatibility warning.

16GB AMD pick remains INT4 W4A8 on [2951557](https://civitai.com/models/2951557) (~4.0 GB diffusion) or a Q4/Q5 GGUF from this ladder, not Q8_0 7.16 GB plus a full TE.

## 5. Animagine XL 4 LoRA and RealVisXL LoRA

**Animagine XL 4** (`query=Animagine XL 4`, type LoRA, Highest Rated): results are character LoRAs on `SDXL 1.0` (Enma Ai 275687, 152 thumbs; Iris 1322937; Amelia 1363972). None are a general quality stack besides:

| id | title | base | thumbs / dl | vibe | why |
|---|---|---|---|---|---|
| 1319919 | Stabilizer AnimagineXL 4.0 | SDXL 1.0 (trained on 4.0 zero/opt) | 194 / 1.8k | SFW detail | Strength **0.5–1**, no trigger. Already linked. Still the only general Animagine 4 LoRA worth keeping. |
| 1337270 | Animagine XL 4 saturated | SDXL 1.0 | 8 / 185 | SFW color | Thin; saturation only. |
| 1188071 | Animagine XL 4.0 checkpoint | SDXL 1.0 | 4.7k thumbs | SFW base | Already linked. LoRA search does not replace the checkpoint. |
| 2110148 | Animagine-XL_4.0_Opt_clear | SDXL 1.0 | 60 thumbs | SFW ckpt | Alternate clear merge, not a LoRA. |
| 1208930 | Animagine XL 4.0 ControlNet | SDXL 1.0 | 35 thumbs | SFW CN | Not a LoRA; only control hit in that search. |

**RealVisXL:** type LoRA + query `RealVisXL` returns **one** model, [2605632](https://civitai.com/models/2605632) Sofia (16 thumbs) — already noted as thin. Checkpoint [139562](https://civitai.com/models/139562) RealVisXL V5.0 (18.1k thumbs) still has the real settings: **Turbo = DPM++ SDE Karras, 4–10 steps, CFG 1–2.5**; **Lightning = DPM++ SDE, 4–6 steps, CFG 1–2**; full = DPM++ SDE Karras 30+ or 2M Karras 50+. Hires.fix on V5 Lightning: **3 steps, denoise 0.5, CFG 1–2**. Companions that actually show up under “detail” rather than the RealVis name: [122359](https://civitai.com/models/122359) Detail Tweaker XL (43.6k thumbs, SDXL) and [1317134](https://civitai.com/models/1317134) DetailN_XL (530 thumbs). Use those, not a phantom RealVis LoRA family.

## 6. Pixel art — Illustrious and Z-Image

| id | title | base | thumbs / dl | vibe | why |
|---|---|---|---|---|---|
| 43820 | Illustrious Pixel Art XL & 1.5 | Illustrious (later version) | 5.3k / 54k | SFW style | Highest-rated Illustrious pixel hit. Trigger `pixel`, weight 1; drop “high quality” from the prompt. NoobAI 0.75 mentioned. |
| 1288970 | Pixel art style LoRa \| Illustrious | Illustrious | 606 / 4.1k | SFW | Large style set, Oktaze. |
| 888939 | pixel art Style (Illustrious) | Illustrious | 235 / 1.4k | SFW | GLora, ~60 images; stacks with other styles. |
| 1130279 | Vixon's Detailed Pixel Art | Illustrious | 446 / 2.6k | SFW | Detailed pixel, not a sprite sheet. |
| 1084875 | Pixel Art Sprite – Elin style | Illustrious | 583 / 4.9k | SFW sprite | Sprite look on Noob/Illustrious. |
| 2481158 | PixelArt Perfect [Z-Image Turbo] | ZImageTurbo | 50 / 659 | SFW shader | **Steps 8, CFG 1, weight 0.5–1.5**, trigger `pixelart`. Then 6× nearest down/up for a clean grid. Shader, not a subject generator. |
| 10706 | Z-IMAGE AND QWEN PIXEL ART REFINER | ZImageTurbo | 1.5k / 11k | SFW | Already linked. v1 strength ~1.2 without the token. |
| 2190363 | Elusarca Detailed Pixel Art | ZImage | 93 / 868 | SFW | Turbo already does pixel; this adds detail. |
| 2182113 | PC-98 Style | ZImageTurbo | 84 / 568 | SFW retro | Narrower than generic pixel; useful if the look is PC-98. |

## Concrete URLs (this pass)

1. https://civitai.com/models/2324991
2. https://civitai.com/models/2324315
3. https://civitai.com/models/2334190
4. https://civitai.com/models/2438659
5. https://civitai.com/models/2474084
6. https://civitai.com/models/2859218
7. https://civitai.com/models/2662689
8. https://civitai.com/models/2327604
9. https://civitai.com/models/2413760
10. https://civitai.com/models/2413450
11. https://civitai.com/models/2680498
12. https://civitai.com/models/2515526
13. https://civitai.com/models/2367207
14. https://civitai.com/models/2343298
15. https://civitai.com/models/2168935
16. https://civitai.com/models/2169712
17. https://civitai.com/models/2176468
18. https://civitai.com/models/2588499
19. https://civitai.com/models/2172270
20. https://civitai.com/models/2193133
21. https://civitai.com/models/2439528
22. https://civitai.com/models/2362961
23. https://civitai.com/models/2409672
24. https://civitai.com/models/2952547
25. https://civitai.com/models/2952100
26. https://civitai.com/models/1337270
27. https://civitai.com/models/139562
28. https://civitai.com/models/122359
29. https://civitai.com/models/43820
30. https://civitai.com/models/1288970
31. https://civitai.com/models/2481158
32. https://civitai.com/models/888939

Search URLs used: Klein LoRA, Z-Image Turbo, Qwen-Image-2.1, plus the two model pages in the brief.
