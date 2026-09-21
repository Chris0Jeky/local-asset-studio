# Civitai / civitai.red FINDINGS pack — 2026-09-21 (BST)

**Audience:** Chris Local Asset Studio (LAS) → PR into `Chris0Jeky/local-asset-studio`  
**GPU:** AMD RX 9070 XT 16GB · Comfy portable · Studio at `C:\Users\jekyt\source\local-asset-studio`  
**Rule:** Model **page URLs + ids + version names + quality signals only**. No weight download URLs.

**nsfwLevel note (Civitai bitmask):** `1` ≈ clean/soft · `3–7` ≈ soft/mature possible · `15–31` ≈ explicit-capable gallery even when `nsfw:false`. Flags below: **SFW-leaning** vs **NSFW-capable**.

---

## Executive TLDR

1. **Quality-first ranking works:** Highest Rated / Most Liked + thumbsUp/(up+down) (≥0.99 on top Illustrious LoRAs) beats raw download volume for LAS picks.
2. **WAI Illustrious v170 (installed)** pairs best with utility LoRAs: Hands (`200255`), Stabilizer (`971952`), Aesthetic Masterpiece (`929497`), USNR style (`176554`) — multi-base, ≥10k thumbs.
3. **NoobAI-XL** (`833294`, L_A_X, ~18.7k👍 / 315k DL, nsfwLevel 31) remains hobby/non-commercial anime base; match EPS vs V-Pred LoRAs; add Noob CNs (`929685`, `962537`).
4. **Pony V6** (`257749`, PurpleSmartAI, 76.8k👍 / 1.08M DL) still dominates; use `score_9` article (`/articles/4248`) — do **not** paste score tags into Illustrious/WAI.
5. **Qwen-Image-Edit-2511** is edit-first (LAS #739): Multi Gen WF `1890385`, Plus 8-step `1998998`, Segment/inpaint `2257259`, Multiple-Angles LoRA `2300308`; Lightning 4-step = CFG 1 / 4 steps.
6. **FLUX.2 Klein** official (`2322332`, `2165902`) + FP8/GGUF fit 16GB; many community LoRAs still say `Flux.1 D` — verify base before load.
7. **Xinsir Union/OpenPose** barely mirrored on Civitai (`2943879` low signal); keep installed HF weights; use SDXL Union WFs (`565145`, `1023999`, `1024555`).
8. **Krea2** surged: Turbo ckpt `2726029` (2.2k👍), Identity Edit `2761113`, Detail Slider `2729908`; bridges to Qwen/Z-Image.
9. **civitai.red reachable** (WAI v17 confirms Euler a, CFG 5–7, quality tags); treat as NSFW-leaning mirror.
10. **16GB AMD:** Prefer FP8 / GGUF Q4–Q5 / Lightning 4-step for Qwen+FLUX; SDXL+Xinsir+1–2 LoRAs as daily driver; avoid BF16 Qwen Edit + heavy TE + CN all at once.

---

## Ranking method (quality / reviews / creators)

| Signal | Weight | How used |
|---|---|---|
| thumbsUpCount | Primary | Sort within baseModel |
| thumbsUp / (up+down) | Primary | Prefer ≥0.995 |
| commentCount / article bookmarks | Secondary | Guides & WF trust |
| downloadCount | Noted only | Popularity ≠ quality |
| Creator multi-base presence | Secondary | EauDeNoire, VelvetS, motimalu, YeiYeiArt, CitronLegacy, L_A_X, PurpleSmartAI, WAI0731 |
| nsfwLevel | Flag | Every rec tagged |

Period: **Year** for evergreen utilities; **Month** noted when used. Sorts: `Highest Rated` then cross-check `Most Liked`. Live API scrape ~01:17–01:19 BST 2026-09-21.

---

## Categorized model links (PR-ready)

### WAI / Illustrious

| Model | id | Version (API) | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| WAI-illustrious-SDXL (canonical; Chris has v170) | 827184 | v17.x family | — | — | **NSFW-capable** (rating tags; red lists NSFW forks) | https://civitai.com/models/827184 · https://civitai.red/models/827184 |
| WAI-illustrious-HSWQ | 2698106 | v17.0 base | 322 | 4.5k | NSFW-capable (lvl 31) | https://civitai.com/models/2698106 |
| WAI-Simple-Illustrious | 2904237 | v1.0 | 241 | 1.6k | NSFW-capable (lvl 7) | https://civitai.com/models/2904237 |
| Hands XL… (Illustrious ver) | 200255 | Hands Illu v1.1 | 16372 | 306k | NSFW-capable (lvl 31) utility | https://civitai.com/models/200255 |
| Aesthetic Quality Modifiers - Masterpiece | 929497 | v3.0 [illustrious] | 11911 | 162k | NSFW-capable (lvl 31) | https://civitai.com/models/929497 |
| Stabilizer IL/NAI/CK | 971952 | illus01 v1.198 | 10919 | 156k | SFW-leaning (lvl 3) | https://civitai.com/models/971952 |
| 薄塗り / USNR STYLE | 176554 | USNR_STYLE_ILL_V1.0 | 10861 | 90k | Soft/mature (lvl 7) | https://civitai.com/models/176554 |
| Smooth Detailer Booster | 1145743 | Smooth Booster v5 | 9878 | 98k | NSFW-capable (lvl 31) | https://civitai.com/models/1145743 |
| Add Micro Details | 1377820 | v7.0_Illustrious | 7919 | 100k | NSFW-capable (lvl 31) | https://civitai.com/models/1377820 |
| Velvet's Mythic Fantasy Styles | 599757 | illustrious Colorful Line | 14680 | 239k | Soft (lvl 15) | https://civitai.com/models/599757 |
| Character Design Sheet | 100435 | -Illustrious XL- | 11463 | 100k | **SFW** (lvl 3) | https://civitai.com/models/100435 |
| Illustrious-XL ControlNet Openpose | 1359846 | v1.0 | 1013 | 34k | **SFW** | https://civitai.com/models/1359846 |

**Creator:** WAI0731. Prompt (red/docs): `masterpiece, best quality, amazing quality` · neg `bad quality, worst quality, worst detail` · Euler a · CFG 5–7 · steps 25–40 · safety tags `general/sensitive/nsfw/explicit`.

### NoobAI

| Model | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| NoobAI-XL (NAI-XL) | 833294 | V-Pred-1.0-Version (also EPS) | 18718 | 315k | **NSFW-capable** (lvl 31) · hobby/non-commercial | https://civitai.com/models/833294 |
| Aesthetic Masterpiece (Noob ver) | 929497 | v2.3 [noobai-v-pred-1] | 11911 | 162k | NSFW-capable | https://civitai.com/models/929497 |
| Stabilizer (Noob ver) | 971952 | cknb02 v0.304a | 10919 | 156k | SFW-leaning | https://civitai.com/models/971952 |
| Flat Color - Style | 1132089 | v2.0 [noobai-v-pred-1] | 5985 | 52k | SFW-leaning style | https://civitai.com/models/1132089 |
| MeMaXL Flat Anime | 269772 | v6.0 A-E [Noob1-Vpred] | 4360 | 61k | SFW-leaning · 16 comments | https://civitai.com/models/269772 |
| People's Works: SDXL | 1400090 | v10.5_NoobVv1.0 | 5780 | 63k | Mixed | https://civitai.com/models/1400090 |
| NoobAI-XL ControlNet | 929685 | eps-blur | 1430 | 57k | **SFW** | https://civitai.com/models/929685 |
| NoobAI-XL ControlNet-OPENPOSE | 962537 | openpose model | 1298 | 28k | Soft (lvl 5) | https://civitai.com/models/962537 |
| NoobAI Inpainting ControlNet | 1376234 | v1.0 | 698 | 11k | **SFW** | https://civitai.com/models/1376234 |

**Creator:** L_A_X. Month-liked Noob LoRAs skew NSFW character (Enigmata) — quarantine for SFW queues.

### Pony

| Model | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Pony Diffusion V6 XL (installed) | 257749 | V6 (start with this one) | 76822 | 1.08M | Soft/mature (lvl 7); community NSFW-heavy | https://civitai.com/models/257749 |
| Pony V7 base | 1901521 | v7.0 | 1055 | 12k | NSFW-capable (lvl 11) | https://civitai.com/models/1901521 |
| Vixon's Gothic Neon | 888231 | gothic neon v1.0 | 16161 | 108k | SFW-leaning style | https://civitai.com/models/888231 |
| Velvet Mythic Fantasy (Pony ver) | 599757 | Pony Portrait Style | 14680 | 239k | Soft (lvl 15) | https://civitai.com/models/599757 |
| Character Design Sheet (Pony) | 100435 | -PONY XL- | 11463 | 100k | **SFW** (lvl 3) | https://civitai.com/models/100435 |
| S1 Dramatic Lighting | 661736 | Pony v3 | 6425 | 58k | SFW-leaning · **31 comments** | https://civitai.com/models/661736 |
| Dynamic Poses slider | 438059 | Pony | 5819 | 42k | Utility · check gallery | https://civitai.com/models/438059 |
| Hands (Pony ver) | 200255 | Hand Pony v1.0 | 16372 | 306k | Utility NSFW-capable gallery | https://civitai.com/models/200255 |

**Guides:** https://civitai.com/articles/4248 (`score_9`) · https://civitai.com/articles/6555 (Pony tips).

### Animagine

| Model | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Animagine XL 4.0 (Chris has Opt) | 1188071 | v4 Opt | 4699 | 98k | SFW-leaning official | https://civitai.com/models/1188071 |
| Animagine-XL_4.0_Opt_clear | 2110148 | FP16 | 60 | 2.5k | **SFW** (lvl 1) | https://civitai.com/models/2110148 |
| Stabilizer AnimagineXL 4.0 | 1319919 | zero v0.10 | 194 | 1.8k | Utility | https://civitai.com/models/1319919 |
| Animagine XL 4.0 ControlNet | 1208930 | canny | 35 | 1k | **SFW** | https://civitai.com/models/1208930 |

Cross-use Illustrious/SDXL utilities when versions list Animagine.

### RealVis

| Model | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| RealVisXL V5.0 (Chris has fp16) | 139562 | V5.0 Lightning (BakedVAE) top listing | 18111 | 690k | Soft gallery possible; photoreal SFW-usable | https://civitai.com/models/139562 |
| Realistic Skin Texture (EauDeNoire) | 580857 | skin texture XL v4 | 7513 | 186k | Soft · often NSFW gallery | https://civitai.com/models/580857 |
| Detailed Perfection | 411088 | Perfection SDXL v1.0 | 6760 | 133k | Soft · **39 comments** | https://civitai.com/models/411088 |
| Cinematic Shot | 432586 | XL v1.0 | 4219 | 57k | **SFW-leaning** | https://civitai.com/models/432586 |

### Qwen-Image-Edit + Qwen-Image-2.1 interest (LAS #739)

| Model | id | Type | Version | 👍 | DL | Flag | URL |
|---|---:|---|---|---:|---:|---|---|
| Qwen-Image-Edit 2511 | 2247803 | Checkpoint | FP8 | 276 | 11k | **SFW** (lvl 1) | https://civitai.com/models/2247803 |
| Qwen Edit 2509 | 1981702 | Checkpoint | fp16 | 373 | 12k | **SFW** | https://civitai.com/models/1981702 |
| Qwen-Image-2512 | 2268063 | Checkpoint | fp8_e4m3fn | 666 | 13k | Soft (lvl 3) | https://civitai.com/models/2268063 |
| Qwen image 2.1 WF collection | 579280 | Workflows | QW21加速器 | 686 | 36k | NSFW-capable (lvl 31) · **2.1 interest** | https://civitai.com/models/579280 |
| Qwen Image Edit Multi Gen | 1890385 | Workflows | 2511 v1 | 510 | 15k | Soft (lvl 3) | https://civitai.com/models/1890385 |
| Qwen Image Edit Plus (2511) 8steps | 1998998 | Workflows | Qwen Edit 2511 v1.0 | 182 | 6.8k | **SFW** | https://civitai.com/models/1998998 |
| QWEN Segment Inpaint/swap/local | 2257259 | Workflows | v1.0 | 114 | 7k | **SFW** | https://civitai.com/models/2257259 |
| Qwen Image Edit 2511 Ultimate | 2301814 | Workflows | v1.0 | 97 | 3.8k | Soft (lvl 7) | https://civitai.com/models/2301814 |
| Multiple-Angles-LoRA | 2300308 | LORA | v1.0 | 229 | 4.6k | **SFW** | https://civitai.com/models/2300308 |
| Emotional Photography LoRA | 1869530 | LORA | v2.0 | 315 | 3.7k | Soft | https://civitai.com/models/1869530 |
| Lightning 4steps bf16 (community) | 2689441 | LORA | v1.0 | 10 | 722 | **SFW** · prefer installed official Lightning | https://civitai.com/models/2689441 |
| Qwen-image_union ControlNet WF | 2048956 | Workflows | — | 8 | 148 | **SFW** early | https://civitai.com/models/2048956 |

**Edit recipe:** BF16 → CFG 4 / ~40 · FP8 → CFG 4 / ~20 · **+ Lightning → CFG 1 / 4 steps** · keep Edit Model Reference Method nodes · match `<image N>` / multi-image mode to slot count · don’t stack Lightning LoRA on fused FP8 Lightning ckpt.

### FLUX.2 / Klein

| Model | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Flux.2 Klein (official) | 2322332 | 9B-Base | 1472 | 36k | Soft (lvl 3) | https://civitai.com/models/2322332 |
| Flux.2 (Dev official) | 2165902 | Dev | 778 | 11k | Soft | https://civitai.com/models/2165902 |
| Flux2-Klein-9B-True | 2339723 | v2.0-bf16 | 662 | 13k | Soft/mature (lvl 7) | https://civitai.com/models/2339723 |
| Flux Klein FP8 | 2311742 | flux-2-klein-base-9b-fp8 | 271 | 18k | **SFW** · **25 comments** | https://civitai.com/models/2311742 |
| FLUXTRAIT | 2086049 | Klein_9b_V3 | 636 | 16k | Soft/mature | https://civitai.com/models/2086049 |
| Hands (Flux.1 D ver — verify for F2) | 200255 | Hand F1D v2.0 | 16372 | 306k | Utility | https://civitai.com/models/200255 |
| Velvet Mythic (Flux ver) | 599757 | Flux Sharp Lines | 14680 | 239k | Soft | https://civitai.com/models/599757 |
| Neurocore Anime Shadow Circuit | 938811 | lists FLUX2 KLEIN 9B | high | — | Soft · cross Klein | https://civitai.com/models/938811 |
| Flux Union Controlnet Pro WF | 709352 | — | 320 | 12k | **SFW** | https://civitai.com/models/709352 |

### Krea2 LoRAs / related

| Model | id | Type | Version | 👍 | DL | Flag | URL |
|---|---:|---|---|---:|---:|---|---|
| Krea 2 Turbo Official Comfy-Org | 2726029 | Checkpoint | krea2_turbo_int8_convrot | 2199 | 44k | **SFW** (lvl 1) | https://civitai.com/models/2726029 |
| Krea2 TextFusion Refusal-Reduction | 2775340 | LORA | v1.0 | 2027 | 35k | **SFW** (policy-bypass — use carefully) | https://civitai.com/models/2775340 |
| Krea 2 Identity Edit | 2761113 | LORA | v1.2 | 1127 | 23k | Soft (lvl 3) · edit-adjacent | https://civitai.com/models/2761113 |
| [KREA 2] Detail Slider | 2729908 | LORA | v1.0 | 921 | 18k | Soft | https://civitai.com/models/2729908 |
| [KREA 2] Realism Slider | 2781697 | LORA | v1.0 | 456 | 8.4k | Soft/mature | https://civitai.com/models/2781697 |
| Krea2 / Flux - Vividly Surreal | 930804 | LORA | Krea2 | 539 | 4.7k | Soft | https://civitai.com/models/930804 |
| Krea2+Qwen2511+Z-Image Illustria Anime | 2174309 | LORA | v1.0 Krea 2 | 451 | 6.8k | Soft/mature · **cross-stack** | https://civitai.com/models/2174309 |
| Krea2 [SFW/NSFW] Uncensored WF | 2738703 | Workflows | v1.0 | 741 | 31k | **Explicit dual** | https://civitai.com/models/2738703 |
| Velvet Mythic (+ Krea2 in name) | 599757 | multi | — | 14680 | 239k | Soft | https://civitai.com/models/599757 |

### OpenPose / Union ControlNet

| Model | id | Notes | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| xinsir ControlNet OpenPose SDXL (Civitai mirror) | 2943879 | Low thumbs — prefer installed HF | 2 | 81 | **SFW** | https://civitai.com/models/2943879 |
| ControlNet Union for SDXL WF | 565145 | “1 Model Does it All” | 96 | 6.3k | **SFW** | https://civitai.com/models/565145 |
| [SDXL] Controlnet-Union Workflow (Basic) | 1023999 | a01demort | 33 | 1.2k | **SFW** | https://civitai.com/models/1023999 |
| [SDXL] IP-Adapter + Controlnet union | 1024555 | combo | 58 | 2.6k | **SFW** | https://civitai.com/models/1024555 |
| Illustrious Openpose CN | 1359846 | WAI-matched | 1013 | 34k | **SFW** | https://civitai.com/models/1359846 |
| NoobAI Openpose CN | 962537 | Noob-matched | 1298 | 28k | Soft | https://civitai.com/models/962537 |
| TTPLanet SDXL Tile Realistic | 330313 | tile companion | 1889 | 36k | Soft | https://civitai.com/models/330313 |
| HF Union SDXL 1.0 (provenance) | — | xinsir/controlnet-union-sdxl-1.0 | — | — | **SFW** tooling | https://huggingface.co/xinsir/controlnet-union-sdxl-1.0 |
| HF OpenPose SDXL | — | xinsir/controlnet-openpose-sdxl-1.0 | — | — | **SFW** | https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0 |

**LAS tip:** Xinsir Union daily for SDXL/WAI/Pony/RealVis; Illustrious/Noob OpenPose CNs when anime pose drifts.

### IP-Adapter

| Model | id | Type | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| IP-Adapter-FaceID | 301776 | Controlnet listing | 282 | 30k | **SFW** | https://civitai.com/models/301776 |
| IP Adapter Models for SDXL | 157698 | bundle listing | 174 | 20k | **SFW** | https://civitai.com/models/157698 |
| Style IPAdapter for NoobAI-XL | 1233692 | Controlnet | 187 | 3.3k | **SFW** · Noob match | https://civitai.com/models/1233692 |
| IP-Adapter Flux | 670387 | LORA (xlabs_ai) | 91 | 2.6k | **SFW** | https://civitai.com/models/670387 |
| IP Adapter Bundle | 907545 | Other | 69 | 2.2k | **SFW** | https://civitai.com/models/907545 |
| Blink's universal WF (IPA+CN+Illu/Noob/Pony/Animagine) | 1621455 | Workflows | 75 | 1.8k | Check gallery | https://civitai.com/models/1621455 |
| [SDXL] IP-Adapter + Union WF | 1024555 | Workflows | 58 | 2.6k | **SFW** | https://civitai.com/models/1024555 |

---

## Workflows (high-signal for installed stack)

| Workflow | id | What it does | 👍 / DL | SFW/NSFW | URL |
|---|---:|---|---|---|---|
| ComfyUI Image Workflows | 1386234 | Broad image pack | 2926 / 91k | NSFW-capable (31) | https://civitai.com/models/1386234 |
| Smooth Workflow (txt2img) | 1598938 | DigitalPastel smooth | 1262 / 22k | NSFW-capable | https://civitai.com/models/1598938 |
| SDXL PONY ILLUSTRIOUS DMD2 (Stable Yogi) | 1215102 | Multi-base SDXL family | 950 / 33k | NSFW-capable (29) | https://civitai.com/models/1215102 |
| Moody Simple Zimage Turbo | 2253524 | Z-Image Turbo daily | 957 / 47k | NSFW-capable | https://civitai.com/models/2253524 |
| Z-Image Base & Turbo Pro (Low/High VRAM) | 2184844 | Explicit VRAM paths | 848 / 33k | NSFW-capable | https://civitai.com/models/2184844 |
| Qwen 2.1 WF collection | 579280 | **2.1 + accelerators** | 686 / 36k | NSFW-capable | https://civitai.com/models/579280 |
| Qwen Edit Multi Gen | 1890385 | Multi-image edit | 510 / 15k | Soft | https://civitai.com/models/1890385 |
| Qwen Edit Plus 8-step | 1998998 | Multi edit 2511 | 182 / 6.8k | SFW | https://civitai.com/models/1998998 |
| Qwen Segment Inpaint/swap | 2257259 | Local edit | 114 / 7k | SFW | https://civitai.com/models/2257259 |
| ControlNet Union SDXL | 565145 | Union how-to | 96 / 6.3k | SFW | https://civitai.com/models/565145 |
| IP-Adapter + Union SDXL | 1024555 | Face/style + pose | 58 / 2.6k | SFW | https://civitai.com/models/1024555 |
| GonzaLomo Z-Image Refiner | 2172100 | Refine pass | 573 / 17k | NSFW-capable | https://civitai.com/models/2172100 |

---

## LoRA combos per base

Prefer **one style + one utility** before stacking three.

### WAI Illustrious (v170) — SFW default
1. Stabilizer `971952` @ 0.4–0.7  
2. Hands Illu `200255` @ 0.6–1.0 when hands fail  
3. Aesthetic Masterpiece `929497` @ 0.3–0.6 **or** USNR `176554` @ 0.6–0.9  
4. Optional Micro Details `1377820` @ 0.3–0.5  
**NSFW:** use WAI safety tags (`nsfw` in neg to stay clean).

### NoobAI 1.1 — SFW
1. Stabilizer Noob ver `971952`  
2. Flat Color `1132089` **or** MeMaXL `269772`  
3. Hands / Micro Details matching Noob version tags  
**NSFW:** Month chart flooded with explicit character LoRAs — quarantine.

### Pony V6 — SFW
1. `score_9, score_8_up, score_7_up` (article 4248) — **Pony only**  
2. Gothic Neon `888231` or Velvet Portrait `599757`  
3. Dramatic Lighting `661736`  
4. Hands Pony ver `200255`  
**NSFW:** body-concept LoRAs (`139131`, `217340`) explicit-leaning — flag.

### Animagine XL 4.0 Opt — SFW
1. Stabilizer Animagine `1319919` if needed  
2. Shared SDXL Hands / Cinematic Shot `432586`  
3. Danbooru-like prompts; **no** Pony score tags.

### RealVisXL V5 — SFW photoreal
1. Skin Texture `580857` lightly (0.3–0.6)  
2. Cinematic Shot `432586`  
3. Detailed Perfection `411088` if anatomy breaks  
4. Xinsir OpenPose/Union for pose lock.

### FLUX.2 Klein / FLUX — SFW
1. Prefer Klein-tagged versions (Neurocore `938811`) over blind Flux.1 D  
2. Velvet Flux Sharp Lines `599757`  
3. Character Design Sheet Flux ver `100435`  
4. Union Pro WF `709352`.

### Qwen-Image-Edit — SFW edit-first
1. Installed Lightning 4-step @ 1.0 with CFG 1 / 4 steps  
2. Multiple-Angles `2300308` for re-shoot  
3. Emotional Photography `1869530` for mood  
4. Cross: Krea2+Qwen Illustria `2174309` experimental — verify base.

### Pixel (installed Pixel Art XL)
Also: Pixel Art Refiner Z-Image/Qwen `10706` (1503👍) · PixelArtRedmond `144684`.

---

## ControlNet stacks (Xinsir + LAS)

**Daily (SDXL family: WAI / Pony / RealVis / Animagine / SDXL):** Xinsir Union 1.0 → OpenPose/Depth/Canny · strength 0.6–0.85 · optional Xinsir OpenPose-only · Tile TTPLanet `330313` for refine.

**Anime specialist:** Illustrious OpenPose `1359846` on WAI · Noob OpenPose `962537` + pack `929685` on NoobAI.

**Identity:** IP-Adapter FaceID `301776` or SDXL IPA `157698` + Union WF `1024555` · Noob style IPA `1233692`.

**Qwen/FLUX:** separate Union WFs (`2048956`, `709352`) — do not load SDXL Xinsir into those graphs.

---

## Tips (prompting / sampler / Lightning / edit)

- **WAI / Illustrious:** Danbooru tags; quality tags at end if prompt long; CFG often ≤6–7; Euler a; **no** `score_9`. https://civitai.com/articles/23210  
- **Pony:** `score_9` system https://civitai.com/articles/4248  
- **NoobAI:** Danbooru + E621; match EPS vs V-Pred LoRA versions  
- **Qwen Edit 2511:** Lightning → CFG **1**, steps **4**; without Lightning FP8 CFG 4 / ~20; Reference Method nodes on; ~1MP inputs; align multi-image count with `<image N>`  
- **Z-Image Turbo:** Low/High VRAM WF `2184844` / Moody `2253524`  
- **Samplers:** https://civitai.com/articles/7484  

---

## VRAM notes — RX 9070 XT 16GB (AMD)

| Stack | Practical mode | Notes |
|---|---|---|
| SDXL + Xinsir Union + 1–2 LoRA | FP16 daily | Headroom for FaceDetailer/upscale |
| WAI / Pony / Noob / Animagine / RealVis | FP16 | Same family profile |
| FLUX.2 Klein 4B FP8 (installed) | FP8 | Prefer over BF16 |
| FLUX.2-dev GGUF Q4_K_M (installed) | GGUF | Watch Mistral-Small 24B Q4 TE offload |
| Qwen-Image-Edit Q4_K_M GGUF (installed) | GGUF Q4 | Some guides prefer FP8 Lightning fused vs Q4 |
| Qwen + Lightning 4-step | Low steps | Wall-clock win; don’t raise CFG |
| Z-Image Turbo BF16 (installed) | BF16 | Use Low VRAM graph branches; quant mirrors `2169712` |
| Krea2 Turbo int8/FP8 | Quant | `2726029` int8 is 16GB-friendly |
| Avoid | BF16 Qwen Edit + full VL TE + Union + IPA | Spill/thrash — serialize passes |

---

## Top creators to watch

| Username | Why | Flag bias |
|---|---|---|
| WAI0731 | Illustrious checkpoint line Chris runs | Mixed; NSFW forks |
| L_A_X | NoobAI-XL + Noob ControlNets | NSFW-capable base |
| PurpleSmartAI | Pony V6/V7 + score_9 article | Mixed |
| EauDeNoire | Cross-base Hands / Skin / Perfection (~16k👍 Hands) | Galleries often mature |
| VelvetS | Mythic Fantasy multi-base incl. Krea2/Flux/Illu | Soft–mature |
| motimalu | Aesthetic Masterpiece + Flat Color | Mixed |
| YeiYeiArt | Character Design Sheet multi-base | SFW-leaning |
| reakaakasky | Stabilizer IL/NAI + Z-Image fp8 | Utility / SFW-leaning |
| CitronLegacy | Style packs across Noob/Illu/Pony | Mixed |
| gabrielx / yorgash | Qwen Edit workflows | Mostly SFW tooling |
| a01demort | SDXL Union + IPA workflows | SFW tooling |
| CagliostroLab | Animagine XL 4.0 | SFW-leaning |
| SG_161222 | RealVisXL V5 | Photoreal mixed |
| alcaitiff / Capitan01R / conrad_locke | Krea2 sliders / identity / refusal | Mixed; policy LoRAs caution |
| DigitalPastel | Smooth Detailer + Smooth WF | Mixed |

---

## Blockers / caveats

- Direct `GET /api/v1/models/{id}` intermittently Cloudflare **1015**; list/search OK — stats from those live responses (~01:17–01:19 BST).  
- civitai.red **up**; WAI HTML + red API LoRA sample OK.  
- Xinsir barely on Civitai — low-👍 mirror ≠ quality.  
- Qwen-Image-**2.1** thinner than Edit-2511; WF `579280` main breadcrumb.  
- First batch — not exhaustive; `raw/` retained.

---

## Counts (this pack)

- **Unique model page URLs cited:** ~95+  
- **Creators highlighted:** 15  
- **API JSON snapshots in `raw/`:** 50+  
- **Weight downloads attempted:** 0
