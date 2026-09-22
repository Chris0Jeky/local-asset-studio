# BATCH2.md — Civitai scavenge addendum 2026-09-21 (BST)

**Audience:** Chris Local Asset Studio (LAS) · same rules as batch 1.

**Rule:** Page URLs + model ids + version names + 👍/DL + nsfwLevel only. **No weight downloads.**

**API:** `https://civitai.com/api/v1/models` · UA `LAS-scavenge/1.0` · raw `raw/batch2_*.json` · scrape ~01:27–01:35 BST.

Rows marked `*` already appeared in batch 1 (often with a new Klein / Z-Image / Qwen version).


## Executive TLDR

1. **Klein LoRA base tags are real:** Anatomy / Quality Fixer `2324991` (651👍, SFW), Base→Turbo `2324315` (475👍, SFW), Anything2Real `2121900` (1074👍), Portrait Engine `2067704` (Klein 9B ver), Detail sliders `2334190` / `2442399`. motimalu Masterpiece / Flat Color pages now ship **Flux.2 Klein 4B** versions — check version before load (same Flux.1 D trap as batch 1).
2. **Z-Image 16GB path:** Quantized ckpt `2169712` (1075👍, fp8/int4), reakaakasky FP8 `2172944`, Kijai FP8 `2170391`, Pro Low/High VRAM WF `2184844`*, Moody `2253524`*, GGUF+DetailDaemon `2343982`, 6G t2i/i2i `2170193`.
3. **Animagine XL4 utilities stay thin:** motimalu Aesthetic Complete **animagine v4** ver `1003636` (2611👍) is the main new utility; Stabilizer `1319919`*; V3 Detail Enhancer `321576`. Year Highest Rated LORA query returned empty page-1 (cursor quirk) — used AllTime.
4. **RealVis-tagged LoRAs almost don't exist** as a query (~1 portrait). Use SDXL photoreal companions: Skin&Face `1426727`, Cinematic Photography `214956`, Chiaroscuro `280472`, Rembrandt `280454`, plus batch-1 Skin `580857`* / Cinematic Shot `432586`* / Perfection `411088`*.
5. **Qwen-Image-2.1 still sparse:** keep only `Qwen 2` / name-2.1 rows. Hub WF `579280`*; GGUF/INT4 appendix ids still the AMD path; **new** thin WFs `2951814`, `2952715`. Do not attach 2511 Lightning/angles to 2.1.
6. **Pixel:** Z-Image/Qwen Pixel Refiner `10706` (1503👍 SFW), Hard Edge `681332`, Soft Pixel `685038`, PixelArtRedmond Klein/Qwen/ZIT vers `144684`, YeiYeiArt CPS II `620687`.
7. **Creators:** EauDeNoire **NSFW-biased** (Hands/Skin/Perfection lvl 15–31; only God Rays `289500` is clear SFW in top20). VelvetS / YeiYeiArt / reakaakasky easy SFW-leaning keepers. motimalu Aesthetic Best/Complete soft lvl15.
8. **AMD-safe:** Klein Pro Hi/Lo VRAM `2213699`, Klein 4B GGUF simple `2325916`, Unsloth Klein-4B-GGUF `2400928`, Rebels Klein 9B KV GGUF+fp8 `2464133`, Z-Image quant/FP8/GGUF above, Qwen 2.1 INT4 `2951557`* / GGUF WF `2952100`*. Strip SageAttention / Triton-CUDA / DLSS / RTX VSR.
9. **API notes:** `baseModels=Flux.2` / `Flux.2 Klein` / `Animagine` → empty. `username=` works. Prefer list/search over direct id (1015 risk).
10. **Counts:** **73** model ids cited · **58** new vs batch 1 · 15 overlap · weight downloads **0**.


## FLUX.2 / Klein LoRAs & workflows

Kept only versions whose `baseModel` mentions Klein / Flux.2 / FLUX.2. Rejected pure Flux.1 D unless a Klein version also exists.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Klein Anatomy / Quality Fixer | 2324991 | Klein 9B v1.5 | 651 | 24.7k | **SFW** (lvl 1) | https://civitai.com/models/2324991 |
| Klein 4B/9B Base to Turbo Lora | 2324315 | 9B rank 128 | 475 | 17.4k | **SFW** (lvl 1) | https://civitai.com/models/2324315 |
| [Flux2Klein 9B] Anything2Real lrzjason | 2121900 | F2K 9B Anything2Real A | 1.1k | 21.8k | NSFW-capable (lvl 15) | https://civitai.com/models/2121900 |
| Portrait Engine FLUX / FLUX 2 KLEIN / Z-Image, Detailed Skin - [LORA] | 2067704 | V 4.0_Flux_klein | 686 | 22.4k | NSFW-capable (lvl 15) | https://civitai.com/models/2067704 |
| Flux2 Klein_Anything to Real Characters | 2343188 | v1.0 | 418 | 6.4k | Soft/mature (lvl 7) | https://civitai.com/models/2343188 |
| Klein Detail Slider | 2334190 | Klein 9B | 266 | 6.1k | **SFW** (lvl 1) | https://civitai.com/models/2334190 |
| Elusarca's Detail Enhancer | Flux Klein 9B | 2442399 | v1.0 | 263 | 7.6k | **SFW** (lvl 1) | https://civitai.com/models/2442399 |
| [KLEIN 9b] Detail Slider | 2438659 | v1.0 | 248 | 4.9k | Soft/mature (lvl 13) | https://civitai.com/models/2438659 |
| Klein-9b-Turn2Real | 2406218 | v1.5 | 337 | 4.8k | Soft/mature (lvl 9) | https://civitai.com/models/2406218 |
| FLUX2 Klein_9b Pro Grade Workflow (High & Low VRAM), w/ Controlnet, GG | 2213699 | v10.0.1 Updates | 254 | 9.1k | NSFW-capable (lvl 15) | https://civitai.com/models/2213699 |
| ComfyUI beginner friendly Flux.2 Klein 4B GGUF Simple Fast Consistent  | 2325916 | Flux2k_4B_GGUF_CCDB_v1 | 96 | 2.4k | Soft/mature (lvl 7) | https://civitai.com/models/2325916 |
| Unsloth - FLUX.2-Klein-4B-GGUF (Distilled) | 2400928 | FP16 | 52 | 2.7k | Soft (lvl 3) | https://civitai.com/models/2400928 |
| Rebels Flux Klein 9B-KV (GGUF+fp8) | 2464133 | EDIT Klein 9b-kv | 29 | 1k | **SFW** (lvl 1) | https://civitai.com/models/2464133 |
| Aesthetic Quality Modifiers - Masterpiece * | 929497 | v3.1 [klein-4b] | 11.9k | 162k | NSFW-capable (lvl 31) | https://civitai.com/models/929497 |
| Flat Color - Style * | 1132089 | v2.1 [klein-4b] | 6k | 52.1k | NSFW-capable (lvl 15) | https://civitai.com/models/1132089 |
| PixelArtRedmond - Pixel Art Loras | 144684 | v1.0 - Flux klein 9b | 821 | 10.8k | Soft/mature (lvl 5) | https://civitai.com/models/144684 |

## Z-Image (checkpoints / LoRAs / workflows)

Prefer Low VRAM / FP8 / GGUF. Moody + Pro WFs remain daily drivers from batch 1.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Z-Image Turbo - Quantized for low VRAM | 2169712 | svdq-int4_r256 (legacy) | 1.1k | 37k | Soft/mature (lvl 5) | https://civitai.com/models/2169712 |
| Z-Image [fp8] | 2172944 | Turbo rev1.1 | 382 | 9.9k | **SFW** (lvl 1) | https://civitai.com/models/2172944 |
| Z-Image Turbo FP8 [Kijai] | 2170391 | FP8 Scaled e4m3fn | 283 | 5k | Soft/mature (lvl 5) | https://civitai.com/models/2170391 |
| Z-Image-Turbo-Anime | 2259646 | AIO-BF16 | 360 | 7.3k | Soft/mature (lvl 7) | https://civitai.com/models/2259646 |
| Z-Image Base & Turbo Pro Grade Workflow I2I/T2I (Low or High VRAM) * | 2184844 | v27.1 LIghting Fix | 848 | 33.6k | NSFW-capable (lvl 31) | https://civitai.com/models/2184844 |
| Z Image Turbo Workflow by Stable_Yogi🔥 | 2186721 | ZImage Turbo V3.1 | 558 | 28.6k | NSFW-capable (lvl 31) | https://civitai.com/models/2186721 |
| Z_image_turbo t2i  i2i workflows (6G VRAM can run it!) | 2170193 | v2.1 t2i i2i | 81 | 2.9k | Soft (lvl 3) | https://civitai.com/models/2170193 |
| Z-Image GGUF with Detail Daemon | 2343982 | v1.0 | 96 | 2.1k | **SFW** (lvl 1) | https://civitai.com/models/2343982 |
| Lonecat's Simple Workflows (MiniMax H3, Krea 2, ZIT, Klein_9b, Illustr | 2600919 | Simple Krea V3.0 | 363 | 20.5k | NSFW-capable (lvl 31) | https://civitai.com/models/2600919 |
| Z-Image-Turbo_clear | 2197598 | BF16 | 96 | 3k | **SFW** (lvl 1) | https://civitai.com/models/2197598 |

## Animagine XL 4 LoRAs + workflows

Character LoRAs dominate search — prefer utility Aesthetic/Stabilizer. Only Animagine WF hit was Blink universal.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Aesthetic Quality Modifiers - Complete | 1003636 | v3.0 [animagine v4] | 2.6k | 23.7k | NSFW-capable (lvl 15) | https://civitai.com/models/1003636 |
| Aesthetic Quality Modifiers - Best Quality | 977115 | v1.0 [noobai-e-pred-1] | 2.8k | 23.7k | NSFW-capable (lvl 15) | https://civitai.com/models/977115 |
| Stabilizer AnimagineXL 4.0 * | 1319919 | zero v0.10 | 194 | 1.8k | **SFW** (lvl 1) | https://civitai.com/models/1319919 |
| Animagine XL V3 Detail Enhancer | 321576 | v1.0 | 327 | 4k | Soft (lvl 3) | https://civitai.com/models/321576 |
| Blink's universal workflow | CivitAI metadata, upscaling, FaceDetailer * | 1621455 | v5 | 75 | 1.8k | NSFW-capable (lvl 31) | https://civitai.com/models/1621455 |

## RealVis companions (photoreal SFW-leaning preference)

`query=RealVis` types=LORA ≈ empty. SDXL photoreal / skin / cinematic companions that load on RealVis V5.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Realistic Skin Texture style (Detailed Skin) XL + SD1.5 + F1D + Pony + * | 580857 | Skin Texture ZBase v2.1 | 7.5k | 186k | NSFW-capable (lvl 15) | https://civitai.com/models/580857 |
| Realistic Skin & Face - Professional_photography | 1426727 | SDXL | 1.1k | 23.6k | NSFW-capable (lvl 31) | https://civitai.com/models/1426727 |
| Cinematic Shot ✨ * | 432586 | XL v1.0 | 4.2k | 57.4k | Soft (lvl 3) | https://civitai.com/models/432586 |
| Cinematic Photography Style XL + F1D + Illu + Pony + zit | 214956 | Cinematic DSLR zit v1.5 | 1.6k | 21k | NSFW-capable (lvl 15) | https://civitai.com/models/214956 |
| Skin Tone (Glamour Photography) Style (Human skin color) XL + F1D + SD | 562884 | Skin Tone zib v1.1 | 1k | 19.7k | NSFW-capable (lvl 31) | https://civitai.com/models/562884 |
| Sofia – Photorealistic Portrait LoRA | Olive Skin, Brown Eyes | SDXL / | 2605632 | v1.0 | 16 | 1.4k | **SFW** (lvl 1) | https://civitai.com/models/2605632 |
| Detailed Perfection style (Hands + Feet + Face + Body + All in one) XL * | 411088 | Perfection zib v1.0 | 6.8k | 133k | NSFW-capable (lvl 31) | https://civitai.com/models/411088 |
| Chiaroscuro (Contrasted) Lighting Style XL + F1D + Illu + Pony + zit + | 280472 | Chiaroscuro zib v1.0 | 1.4k | 14.7k | NSFW-capable (lvl 15) | https://civitai.com/models/280472 |
| Rembrandt (Low-Key) Lighting Style XL + SD1.5 + F1D + Illu + Pony + zi | 280454 | Rembrandt zit v2.1 | 1.2k | 13.6k | Soft/mature (lvl 9) | https://civitai.com/models/280454 |
| Cinematic Volumetric (God Rays) Lighting Style XL + F1D + Illu + Pony | 289500 | Volumetric F1D v1.0 | 622 | 6.3k | **SFW** (lvl 1) | https://civitai.com/models/289500 |

## Qwen-Image-2.1 (strict — not 2511)

Only name/base suggesting **2.1** / baseModel `Qwen 2`. Generic `Qwen` LoRAs are NOT auto-kept as 2.1.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Qwen image 2.1 | LTX25 | MM H3 | Krea2 | ideogram 4 WF collection * | 579280 | QW21加速器(Native acceler) | 686 | 36.3k | NSFW-capable (lvl 31) | https://civitai.com/models/579280 |
| Qwen Image 2.1 Workflows (T2I + Edit) with SageAttention * | 2951890 | v1.1 (Edit Resolution) | 9 | 365 | Soft/mature (lvl 5) | https://civitai.com/models/2951890 |
| Qwen Image 2.1 GGUFs * | 2952100 | EDIT | 5 | 60 | **SFW** (lvl 1) | https://civitai.com/models/2952100 |
| Qwen Image 2.1 GGUF * | 2952547 | v1.0 | 4 | 43 | Soft/mature (lvl 5) | https://civitai.com/models/2952547 |
| Qwen Image 2.1 INT8/INT4 * | 2951557 | INT8 | 23 | 342 | Soft (lvl 3) | https://civitai.com/models/2951557 |
| qwen 2.1 with prompt enchancer - 100% of understanding. | 2951814 | v1.1 | 4 | 145 | **SFW** (lvl 1) | https://civitai.com/models/2951814 |
| Qwen 2.1 2K Upscale Workflow | 2952715 | v1.0 | 4 | 78 | **SFW** (lvl 1) | https://civitai.com/models/2952715 |

## Pixel art LoRAs (+ Z-Image / Qwen refiners)

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| [LuisaP❤️] Z-IMAGE AND QWEN! PIXEL ART REFINER | 10706 | Z-IMAGETURBO | 1.5k | 11.3k | **SFW** (lvl 1) | https://civitai.com/models/10706 |
| PixelArtRedmond - Pixel Art Loras | 144684 | v1.0 - QWEN IMAGE | 821 | 10.8k | Soft/mature (lvl 5) | https://civitai.com/models/144684 |
| Hard Edge Pixel Art | 681332 | Z-Image v1.0 | 409 | 4.4k | **SFW** (lvl 1) | https://civitai.com/models/681332 |
| Soft Pixel Art | 685038 | Z-Image v1 | 174 | 1.7k | Soft/mature (lvl 5) | https://civitai.com/models/685038 |
| Retro Game (CPS II) - Pixel Art - STYLE - | Illustrious XL | Pony XL | | 620687 | - Illustrious XL - | 1.6k | 11.2k | Soft/mature (lvl 7) | https://civitai.com/models/620687 |
| Elusarca's Detailed Pixel Art LoRA for Z-Image | 2190363 | v1.0 | 93 | 868 | **SFW** (lvl 1) | https://civitai.com/models/2190363 |
| Game Boy Camera Pixel Style - ZIT, Flux, & Qwen | 1487247 | Krea2 Turbo | 133 | 1.1k | Soft (lvl 3) | https://civitai.com/models/1487247 |
| Pixel Art Style Lora | 1770073 | v1.0 - Z Image Turbo | 204 | 3.3k | NSFW-capable (lvl 15) | https://civitai.com/models/1770073 |

## Creator: EauDeNoire (NSFW bias)

Top Hands/Skin/Perfection/Feet are lvl 15–31. Below = softest keepers beyond batch-1 utilities.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Cinematic Volumetric (God Rays) Lighting Style XL + F1D + Illu + Pony | 289500 | Volumetric F1D v1.0 | 622 | 6.3k | **SFW** (lvl 1) | https://civitai.com/models/289500 |
| Cinematic Photography Style XL + F1D + Illu + Pony + zit | 214956 | Cinematic DSLR zit v1.5 | 1.6k | 21k | NSFW-capable (lvl 15) | https://civitai.com/models/214956 |
| Chiaroscuro (Contrasted) Lighting Style XL + F1D + Illu + Pony + zit + | 280472 | Chiaroscuro zib v1.0 | 1.4k | 14.7k | NSFW-capable (lvl 15) | https://civitai.com/models/280472 |
| Rembrandt (Low-Key) Lighting Style XL + SD1.5 + F1D + Illu + Pony + zi | 280454 | Rembrandt zit v2.1 | 1.2k | 13.6k | Soft/mature (lvl 9) | https://civitai.com/models/280454 |
| Cinematic "Warm Light" 3200k Lighting Style XL + F1D + Illu + Pony | 290860 | warm light F1D v1.0 | 1.2k | 12.4k | Soft/mature (lvl 13) | https://civitai.com/models/290860 |

## Creator: VelvetS (SFW-leaning)

Mythic Fantasy `599757` already batch 1.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| The Space Marines Warhammer 40K | Flux + Pony + illustrious + Anima +  | 632900 | Space Wolves Krea2 | 1.9k | 34.3k | Soft (lvl 3) | https://civitai.com/models/632900 |
| Jinx (Arcane / League of legends) | FLUX + Zimage | 679697 | Flux v2.0 | 321 | 2.9k | Soft (lvl 3) | https://civitai.com/models/679697 |
| Queen Marika (Elden Ring) | FLUX + Z-Image Turbo | 954220 | Z-Image Turbo | 321 | 2.3k | Soft/mature (lvl 7) | https://civitai.com/models/954220 |
| Fangs Concept | FLUX | 690505 | v1.0 | 314 | 2.3k | Soft (lvl 3) | https://civitai.com/models/690505 |
| Adepta Sororitas (Sisters of Battle) Warhammer 40K | Flux + Anima + Kr | 1119858 | Krea 2 | 265 | 1.7k | Soft (lvl 3) | https://civitai.com/models/1119858 |

## Creator: motimalu (SFW-leaning)

Masterpiece `929497` + Flat Color `1132089` already batch 1 (now with Klein vers).

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Aesthetic Quality Modifiers - Best Quality | 977115 | v1.0 [noobai-e-pred-1] | 2.8k | 23.7k | NSFW-capable (lvl 15) | https://civitai.com/models/977115 |
| Aesthetic Quality Modifiers - Complete | 1003636 | v3.0 [noobai-v-pred-1] | 2.6k | 23.7k | NSFW-capable (lvl 15) | https://civitai.com/models/1003636 |
| Frieren フリーレン  - 葬送のフリーレン | 333139 | v1.0 [qwen] | 1.1k | 11.2k | Soft (lvl 3) | https://civitai.com/models/333139 |
| Anime Style Backgrounds for Pony Diffusion | 337060 | v2.0 [AutismMix] | 934 | 8.6k | **SFW** (lvl 1) | https://civitai.com/models/337060 |
| Granblue Fantasy Style [SDXL+Pony] | 293472 | v2.0 [AutismMix] | 944 | 8.6k | Soft/mature (lvl 7) | https://civitai.com/models/293472 |

## Creator: YeiYeiArt (SFW-leaning)

Skipped T-Rex Studio V2 `960593` (explicit hentai style).

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Character Design Sheet (HELPER) (3-PERSPECTIVES)+(COLOR PALETTE) - Z-I * | 100435 | -Z-IMAGE TURBO- | 11.5k | 100k | Soft (lvl 3) | https://civitai.com/models/100435 |
| Alice In Wonderland! Disney - FLUX | SD 1.5 | XL PONY | Illustrious XL | 35930 | -Illustrious XL- | 3.9k | 35.2k | Soft (lvl 3) | https://civitai.com/models/35930 |
| Definitive Disney Studios - STYLE - Z-IMAGE TURBO | Illustrious XL | P | 404277 | Z-IMAGE-TURBO | 3.5k | 38.6k | Soft/mature (lvl 7) | https://civitai.com/models/404277 |
| Ariel (The Little Mermaid) Disney Princess - | Illustrious XL | XL PON | 46315 | - Illustrious XL - | 3.1k | 26.1k | Soft/mature (lvl 7) | https://civitai.com/models/46315 |
| Retro Game (CPS II) - Pixel Art - STYLE - | Illustrious XL | Pony XL | | 620687 | - Illustrious XL - | 1.6k | 11.2k | Soft/mature (lvl 7) | https://civitai.com/models/620687 |

## Creator: reakaakasky (utility / SFW-leaning)

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Stabilizer IL/NAI/CK * | 971952 | cknb02 v0.304a | 10.9k | 156k | Soft (lvl 3) | https://civitai.com/models/971952 |
| RDBT | Anima | 2356447 | b1 v2.3 | 1k | 27.5k | Soft (lvl 3) | https://civitai.com/models/2356447 |
| RDBT | Anima [lora] | 2364703 | b1 v2.1 base | 780 | 22.1k | Soft (lvl 3) | https://civitai.com/models/2364703 |
| Contrast Controller [IL/NAI] | 1523055 | v1 | 687 | 5.9k | **SFW** (lvl 1) | https://civitai.com/models/1523055 |
| Style Strength Controller [IL/NAI] | 1519509 | illus01 v1 | 603 | 6k | Soft (lvl 3) | https://civitai.com/models/1519509 |
| Z-Image [fp8] | 2172944 | Turbo rev1.1 | 382 | 9.9k | **SFW** (lvl 1) | https://civitai.com/models/2172944 |

## AMD-safe (GGUF / FP8 / low VRAM) — Klein / Z-Image / Qwen 2.1

Strip SageAttention / Triton-CUDA / DLSS / RTX VSR from NVIDIA-branded graphs.

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Z-Image Turbo - Quantized for low VRAM | 2169712 | svdq-int4_r256 (legacy) | 1.1k | 37k | Soft/mature (lvl 5) | https://civitai.com/models/2169712 |
| Z-Image Base & Turbo Pro Grade Workflow I2I/T2I (Low or High VRAM) * | 2184844 | v27.1 LIghting Fix | 848 | 33.6k | NSFW-capable (lvl 31) | https://civitai.com/models/2184844 |
| FLUX2 Klein_9b Pro Grade Workflow (High & Low VRAM), w/ Controlnet, GG | 2213699 | v10.0.1 Updates | 254 | 9.1k | NSFW-capable (lvl 15) | https://civitai.com/models/2213699 |
| ComfyUI beginner friendly Flux.2 Klein 4B GGUF Simple Fast Consistent  | 2325916 | Flux2k_4B_GGUF_CCDB_v1 | 96 | 2.4k | Soft/mature (lvl 7) | https://civitai.com/models/2325916 |
| Unsloth - FLUX.2-Klein-4B-GGUF (Distilled) | 2400928 | FP16 | 52 | 2.7k | Soft (lvl 3) | https://civitai.com/models/2400928 |
| Rebels Flux Klein 9B-KV (GGUF+fp8) | 2464133 | EDIT Klein 9b-kv | 29 | 1k | **SFW** (lvl 1) | https://civitai.com/models/2464133 |
| Z-Image GGUF with Detail Daemon | 2343982 | v1.0 | 96 | 2.1k | **SFW** (lvl 1) | https://civitai.com/models/2343982 |
| Z_image_turbo t2i  i2i workflows (6G VRAM can run it!) | 2170193 | v2.1 t2i i2i | 81 | 2.9k | Soft (lvl 3) | https://civitai.com/models/2170193 |
| Qwen Image 2.1 GGUFs * | 2952100 | EDIT | 5 | 60 | **SFW** (lvl 1) | https://civitai.com/models/2952100 |
| Qwen Image 2.1 INT8/INT4 * | 2951557 | INT8 | 23 | 342 | Soft (lvl 3) | https://civitai.com/models/2951557 |
| Z-Image [fp8] | 2172944 | Turbo rev1.1 | 382 | 9.9k | **SFW** (lvl 1) | https://civitai.com/models/2172944 |
| Z-Image Turbo FP8 [Kijai] | 2170391 | FP8 Scaled e4m3fn | 283 | 5k | Soft/mature (lvl 5) | https://civitai.com/models/2170391 |

## Ranking reminder
Thumbs primary; downloads noted only. nsfwLevel bitmask: 1≈clean · 3–7 soft/mature · 15–31 explicit-capable gallery even when `nsfw:false`.
