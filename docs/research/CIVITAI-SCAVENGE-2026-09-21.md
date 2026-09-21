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
- Qwen-Image-**2.1** has a follow-up appendix below (GGUF/INT4, samplers, AMD reject list). `579280` is still the traffic hub but is NVIDIA-accelerated.  
- First batch — not exhaustive; `raw/` retained.

---

## Counts (this pack)

- **Unique model page URLs cited:** ~95+  
- **Creators highlighted:** 15  
- **API JSON snapshots in `raw/`:** 50+  
- **Weight downloads attempted:** 0


---

## Appendix — Qwen-Image-2.1 depth (added after the catalog scrape)

LAS #739. These pages are the ones that are actually **base model “Qwen 2” / Qwen-Image-2.1**, not the 20B 2511 edit line in the tables above. 2.1 is a **7B** visual DiT (32 single-stream layers): T2I and edit together, **up to 10 reference images**, local edits (mask / paint / circle), **native RGBA**. Native canvas is about **2K (~4 MP)**, not 1024.

| Find | id | Type | Why it matters on 16GB AMD | URL |
|---|---:|---|---|---|
| 2.1 WF collection (EasyCache build dated 09/21, also Krea2 graphs) | 579280 | workflow | Up to 10 refs, batch LoRA controller, 2K grain cleanup. **Strip Nvidia RTX VSR and DLSS5** (20–50 series nodes). Browse card shows a **Paid** badge — confirm the JSON is free. | https://civitai.com/models/579280 |
| T2I + Edit templates, v1.1 | 2951890 | workflow | Resolution selector + prompt enhancers. Weights pointer: `Comfy-Org/Qwen-Image-2.1`. Author portable is **CUDA 13 + SageAttention + Triton** — do not install that build. | https://civitai.com/models/2951890 |
| GGUF T2I + EDIT workflows | 2952100 | workflow | Converted from Comfy-Org BF16, native tensor layout `qwen_image`. **Q4_K_M** called the balance quant; Q5/Q6 higher; Q3/Q2 quality-risky. Diffusion only — still need TE + VAE. | https://civitai.com/models/2952100 |
| GGUF checkpoint + templates | 2952547 | checkpoint | **25 steps, CFG 1, euler, simple.** ~4 GB published GGUF. Edit prompts address refs **by index**. Canvas far from the resized ref **shifts the edit** (same failure as article 19251). Loader: `molbal/ComfyUI-GGUF`. | https://civitai.com/models/2952547 |
| INT8 / INT4 (W4A8) | 2951557 | checkpoint | INT4 diffusion ~**4 GB** is the 16GB pick. INT8 diffusion ~6.9 GB plus an ~8.9 GB text file will not coexist with VAE. ConvRot — needs the matching node. | https://civitai.com/models/2951557 |

**Do not attach 2511 Lightning / multiple-angles / try-on LoRAs to 2.1** until a compatibility note exists. Keep the Edit-2511 graph in the tables above (Multi Gen `1890385`, Plus `1998998`, segment `2257259`, angles `2300308`) as the pose/try-on lane. On 16GB the 8 GB authors say you may **disable Lightning** and try ~20 steps, CFG ~2.5 — that advice is for 2511, not a 2.1 license.

**OpenPose on Qwen** today is still the 2509 graph `2030628` (`comfyui_controlnet_aux`) plus factory `2264596` (DW or Depth). Pony Union workflow `876576` states the **OpenPose preprocessor does not work on Pony** — use Xinsir / Illustrious OpenPose `1359846` / Noob OpenPose `962537` on the matching base instead.

**WAI 4-step vs normal WAI:** catalog recipe stays Euler a, CFG 5–7 (confirmed on civitai.red WAI HTML). Rectified 4-step LoRA `1355945` is a different mode: **steps 4, CFG 1–1.5, Euler or DPM (not Euler a), schedule Simple**. **A2/A3 for WAI v14–v17** (base became Illustrious 1.0 at v14); A1 is only ≤ v13.

**civitai.red:** browser session showed the same Civitai SPA as civitai.com (including model `2951890`). Non-browser `curl` to the red host returned **403**; the catalog scrape still pulled red HTML/API (`raw/red_wai.html`, `raw/red_lora.json`). Treat red as an alias that sometimes serves the NSFW-leaning mirror, not a second model family. Direct model-id API on civitai.com also **1015’d** during the first scrape; later GETs for `827184` (WAI, `nsfw: true`, v17 ~6.46 GB) and `257749` succeeded.

**Upscale after a ~1 MP Qwen edit:** SeedVR2 workflow `2024056` is what factory graphs call, and authors say it wants a lot of memory — run it **after** the DiT is freed. SUPIR `364115` or SDXL tile ControlNet is the fallback. Clothing workflow `1944963` states the 1 MP ceiling is the model, not the graph; denoise 0.2–0.3 for photo, 0 for digital.

No weights downloaded in either pass.

---

## Batch 2

Added ~01:35 BST 2026-09-21. See `BATCH2.md` for full tables. New unique model ids: **59**.


### FLUX.2 / Klein LoRAs & WFs

Manual filter: kept only versions whose baseModel mentions Klein / Flux.2 / FLUX.2. Rejected pure Flux.1 D unless a Klein version also exists on the same page. * = already in batch 1 catalog (new Klein version called out).

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Klein Anatomy / Quality Fixer | 2324991 | Klein 9B v1.5 | 651 | 24.7k | **SFW** (lvl 1) | https://civitai.com/models/2324991 |
| Klein 4B/9B Base to Turbo LoRA | 2324315 | 9B rank 128 | 475 | 17.4k | **SFW** (lvl 1) | https://civitai.com/models/2324315 |
| [Flux2Klein 9B] Anything2Real | 2121900 | F2K 9B Anything2Real A | 1.1k | 21.8k | NSFW-capable (lvl 15) | https://civitai.com/models/2121900 |
| Portrait Engine (Klein / Z-Image) | 2067704 | V 4.0_Flux_klein | 686 | 22.4k | Soft (lvl 15) | https://civitai.com/models/2067704 |
| Flux2 Klein_Anything to Real Characters | 2343188 | v1.0 | 418 | 6.4k | Soft/mature (lvl 7) | https://civitai.com/models/2343188 |
| Klein Detail Slider | 2334190 | Klein 9B | 266 | 6.1k | **SFW** (lvl 1) | https://civitai.com/models/2334190 |
| Elusarca Detail Enhancer Klein 9B | 2442399 | v1.0 | 263 | 7.6k | **SFW** (lvl 1) | https://civitai.com/models/2442399 |
| [KLEIN 9b] Detail Slider | 2438659 | v1.0 | 248 | 4.9k | Soft/mature (lvl 13) | https://civitai.com/models/2438659 |
| Klein-9b-Turn2Real | 2406218 | v1.5 | 337 | 4.8k | Soft/mature (lvl 9) | https://civitai.com/models/2406218 |
| Aesthetic Masterpiece (Klein 4B ver) * | 929497 | v3.1 [klein-4b] | 11.9k | 162.5k | NSFW-capable (lvl 31) | https://civitai.com/models/929497 |
| Flat Color (Klein 4B ver) * | 1132089 | v2.1 [klein-4b] | 6k | 52.1k | NSFW-capable (lvl 15) | https://civitai.com/models/1132089 |
| PixelArtRedmond (Flux klein 9b ver) | 144684 | v1.0 - Flux klein 9b | 821 | 10.8k | Soft/mature (lvl 5) | https://civitai.com/models/144684 |
| FLUX2 Klein_9b Pro Grade WF (Hi/Lo VRAM) | 2213699 | v10.0.1 | 254 | 9.1k | Soft (lvl 15) | https://civitai.com/models/2213699 |
| Klein 4B GGUF Simple Fast WF | 2325916 | Flux2k_4B_GGUF_CCDB_v1 | 96 | 2.4k | Soft/mature (lvl 7) | https://civitai.com/models/2325916 |
| Unsloth FLUX.2-Klein-4B-GGUF | 2400928 | Distilled | 52 | 2.7k | Soft (lvl 3) | https://civitai.com/models/2400928 |


### Z-Image (ckpt / LoRA / WF)

Prefer Low VRAM / FP8 / GGUF mentions. Moody `2253524` + Pro `2184844` remain daily WFs from batch 1.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Z-Image Turbo Quantized (low VRAM) | 2169712 | fp8_scaled_e4m3fn_KJ / svdq-int4 | 1.1k | 37k | Soft/mature (lvl 5) | https://civitai.com/models/2169712 |
| Z-Image [fp8] (reakaakasky) | 2172944 | Turbo rev1.1 | 382 | 9.9k | **SFW** (lvl 1) | https://civitai.com/models/2172944 |
| Z-Image Turbo FP8 [Kijai] | 2170391 | FP8 Scaled e4m3fn | 283 | 5k | Soft/mature (lvl 5) | https://civitai.com/models/2170391 |
| Z-Image-Turbo-Anime AIO | 2259646 | AIO-BF16 | 360 | 7.3k | Soft/mature (lvl 7) | https://civitai.com/models/2259646 |
| Z-Image Base & Turbo Pro WF (Lo/Hi VRAM) * | 2184844 | v27.1 | 848 | 33.6k | NSFW-capable (lvl 31) | https://civitai.com/models/2184844 |
| Moody Simple Zimage Turbo * | 2253524 | — | 957 | 47k | NSFW-capable | https://civitai.com/models/2253524 |
| Z Image Turbo WF (Stable_Yogi) | 2186721 | — | 558 | 28.6k | NSFW-capable (lvl 31) | https://civitai.com/models/2186721 |
| Z_image_turbo t2i/i2i (6G VRAM) | 2170193 | v2.1 | 81 | 2.9k | Soft (lvl 3) | https://civitai.com/models/2170193 |
| Z-Image GGUF + Detail Daemon | 2343982 | v1.0 | 96 | 2.1k | **SFW** (lvl 1) | https://civitai.com/models/2343982 |
| Z-Image-Base GGUF | 2344616 | v1.0 | 36 | 1.3k | **SFW** (lvl 1) | https://civitai.com/models/2344616 |
| Z-Image-Turbo_clear | 2197598 | BF16 | 96 | 3k | **SFW** (lvl 1) | https://civitai.com/models/2197598 |
| Lonecat Simple WFs (ZIT/Klein/Krea) | 2600919 | Simple ZIT v2.0 | 363 | 20.5k | NSFW-capable (lvl 31) | https://civitai.com/models/2600919 |


### Animagine XL 4 LoRAs + WFs

Highest Rated Animagine LoRA search returned empty on Year page 1 (cursor quirk); AllTime + XL 4.0 query used. Character LoRAs dominate — prefer utility Aesthetic/Stabilizer. Workflow search only hit Blink universal.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Aesthetic Complete (Animagine v4 ver) | 1003636 | v3.0 [animagine v4] | 2.6k | 23.7k | Soft (lvl 15) | https://civitai.com/models/1003636 |
| Aesthetic Best Quality (Illu/Noob) | 977115 | v1.0 [Illustrious] | 2.8k | 23.7k | Soft (lvl 15) | https://civitai.com/models/977115 |
| Stabilizer AnimagineXL 4.0 * | 1319919 | zero v0.10 | 194 | 1.8k | **SFW** (lvl 1) | https://civitai.com/models/1319919 |
| Animagine XL V3 Detail Enhancer | 321576 | v1.0 | 327 | 4k | Soft (lvl 3) | https://civitai.com/models/321576 |
| Blink universal WF (incl. Animagine) * | 1621455 | — | 75 | 1.8k | NSFW-capable (lvl 31) | https://civitai.com/models/1621455 |


### RealVisXL companions (photoreal SFW-leaning preference)

`query=RealVis` types=LORA is nearly empty on Civitai (1 portrait hit). Used SDXL photoreal / skin / cinematic companions that load on RealVis V5.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Realistic Skin Texture (EauDeNoire) * | 580857 | skin texture XL v4 | 7.5k | 186.5k | Soft (lvl 15) | https://civitai.com/models/580857 |
| Realistic Skin & Face Pro Photography | 1426727 | SDXL | 1.1k | 23.6k | NSFW-capable (lvl 31) | https://civitai.com/models/1426727 |
| Cinematic Shot * | 432586 | XL v1.0 | 4.2k | 57.4k | **SFW-leaning** (lvl 3) | https://civitai.com/models/432586 |
| Cinematic Photography Style (EauDeNoire) | 214956 | Cinematic Film XL v2 | 1.6k | 21k | Soft (lvl 15) | https://civitai.com/models/214956 |
| Skin Tone Glamour (EauDeNoire) | 562884 | skin tone XL v4 | 1k | 19.7k | NSFW-capable (lvl 31) | https://civitai.com/models/562884 |
| Sofia Photoreal Portrait (RealVis-tagged) | 2605632 | v1.0 | 16 | 1.4k | **SFW** (lvl 1) | https://civitai.com/models/2605632 |
| Detailed Perfection * | 411088 | Perfection SDXL v1.0 | 6.8k | 133.8k | Soft · 39 comments | https://civitai.com/models/411088 |


### Qwen-Image-2.1 (strict — not 2511)

Only keep if name/base suggests **2.1** / baseModel `Qwen 2`. Generic `Qwen` base LoRAs (Famegrid, Emotional Photography, etc.) are NOT auto-kept as 2.1. Do not attach 2511 Lightning/angles to 2.1.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Qwen image 2.1 WF collection * | 579280 | QW21加速器 | 686 | 36.3k | NSFW-capable (lvl 31) | https://civitai.com/models/579280 |
| Qwen Image 2.1 T2I+Edit (SageAttention) * | 2951890 | v1.1 | 9 | — | CUDA-leaning | https://civitai.com/models/2951890 |
| Qwen Image 2.1 GGUF WFs * | 2952100 | EDIT / T2I | 5 | — | **SFW** tooling | https://civitai.com/models/2952100 |
| Qwen Image 2.1 GGUF ckpt * | 2952547 | v1.0 | 4 | — | **SFW** | https://civitai.com/models/2952547 |
| Qwen Image 2.1 INT8/INT4 * | 2951557 | INT4 (W4A8) | 23 | — | **SFW** | https://civitai.com/models/2951557 |
| qwen 2.1 + prompt enhancer | 2951814 | v1.1 | 4 | — | baseModel Qwen 2 | https://civitai.com/models/2951814 |
| Qwen 2.1 2K Upscale WF | 2952715 | v1.0 | 4 | — | baseModel Qwen 2 | https://civitai.com/models/2952715 |


### Pixel art LoRAs (+ Z-Image/Qwen refiners)

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Z-IMAGE AND QWEN! PIXEL ART REFINER | 10706 | Z-IMAGETURBO / QWEN! V2 | 1.5k | 11.3k | **SFW** (lvl 1) | https://civitai.com/models/10706 |
| PixelArtRedmond (multi incl. Klein/Qwen) | 144684 | v1.0 - QWEN IMAGE / Flux klein 9b | 821 | 10.8k | Soft/mature (lvl 5) | https://civitai.com/models/144684 |
| Hard Edge Pixel Art (Z-Image ver) | 681332 | Z-Image v1.0 | 409 | 4.4k | **SFW** (lvl 1) | https://civitai.com/models/681332 |
| Soft Pixel Art (Z-Image) | 685038 | Z-Image v1 | 174 | 1.7k | Soft/mature (lvl 5) | https://civitai.com/models/685038 |
| Retro Game CPS II Pixel (Illu/Pony) | 620687 | - Illustrious XL - | 1.6k | 11.2k | Soft/mature (lvl 7) | https://civitai.com/models/620687 |
| Elusarca Detailed Pixel Art (Z-Image) | 2190363 | v1.0 | 93 | 868 | **SFW** (lvl 1) | https://civitai.com/models/2190363 |
| Game Boy Camera Pixel (ZIT/Flux/Qwen) | 1487247 | Krea2 Turbo / Qwen | 133 | 1.1k | Soft (lvl 3) | https://civitai.com/models/1487247 |
| Pixel Art Style LoRA (Z-Image/Qwen) | 1770073 | v1.0 - Z Image Turbo | 204 | 3.3k | NSFW-capable (lvl 15) | https://civitai.com/models/1770073 |


### Creator: EauDeNoire (NSFW bias — galleries often lvl 15–31)

**NSFW bias:** top Hands/Skin/Perfection/Feet are lvl 15–31. Below = softest keepers beyond batch-1 utilities.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Cinematic Volumetric God Rays | 289500 | XL+F1D | 622 | 6.3k | **SFW** (lvl 1) | https://civitai.com/models/289500 |
| Cinematic Photography Style | 214956 | Cinematic Film XL v2 | 1.6k | 21k | Soft (lvl 15) | https://civitai.com/models/214956 |
| Chiaroscuro Lighting | 280472 | Chiaroscuro zib v1.0 | 1.4k | 14.7k | Soft (lvl 15) | https://civitai.com/models/280472 |
| Rembrandt Low-Key Lighting | 280454 | Rembrandt zit v2.1 | 1.2k | 13.6k | Soft/mature (lvl 9) | https://civitai.com/models/280454 |
| Warm Light 3200k | 290860 | warm light F1D v1.0 | 1.2k | 12.4k | Soft/mature (lvl 13) | https://civitai.com/models/290860 |


### Creator: VelvetS (SFW-leaning keepers)

Mythic Fantasy `599757` already batch 1.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Space Marines Warhammer 40K | 632900 | Flux+Pony+Illu | 1.9k | 34.3k | Soft (lvl 3) | https://civitai.com/models/632900 |
| Jinx Arcane (FLUX+Zimage) | 679697 | — | 321 | 2.9k | Soft (lvl 3) | https://civitai.com/models/679697 |
| Queen Marika Elden Ring | 954220 | FLUX+Z-Image | 321 | 2.3k | Soft/mature (lvl 7) | https://civitai.com/models/954220 |
| Fangs Concept FLUX | 690505 | — | 314 | 2.3k | Soft (lvl 3) | https://civitai.com/models/690505 |
| Adepta Sororitas 40K | 1119858 | Flux+ | 265 | 1.7k | Soft (lvl 3) | https://civitai.com/models/1119858 |


### Creator: motimalu (SFW-leaning keepers)

Masterpiece `929497` + Flat Color `1132089` already batch 1.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Aesthetic Best Quality | 977115 | v1.0 [Illustrious] | 2.8k | 23.7k | Soft (lvl 15) | https://civitai.com/models/977115 |
| Aesthetic Complete | 1003636 | v3.0 [animagine v4] | 2.6k | 23.7k | Soft (lvl 15) | https://civitai.com/models/1003636 |
| Frieren | 333139 | v1.0 [qwen] / Illu | 1.1k | 11.2k | Soft (lvl 3) | https://civitai.com/models/333139 |
| Anime Style Backgrounds (Pony) | 337060 | v1.0 | 934 | 8.6k | **SFW** (lvl 1) | https://civitai.com/models/337060 |
| Granblue Fantasy Style | 293472 | SDXL+Pony | 944 | 8.6k | Soft/mature (lvl 7) | https://civitai.com/models/293472 |


### Creator: YeiYeiArt (SFW-leaning keepers)

Skipped T-Rex Studio V2 `960593` (explicit hentai style).

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Character Design Sheet * | 100435 | multi-base | 11.5k | 100.8k | **SFW** (lvl 3) | https://civitai.com/models/100435 |
| Alice In Wonderland Disney | 35930 | FLUX|PONY|Illu | 3.9k | 35.2k | Soft (lvl 3) | https://civitai.com/models/35930 |
| Definitive Disney Studios STYLE | 404277 | Z-IMAGE TURBO|Illu | 3.5k | 38.6k | Soft/mature (lvl 7) | https://civitai.com/models/404277 |
| Elsa Frozen | 42668 | Illu|Pony | 2.4k | — | Soft (lvl 3) | https://civitai.com/models/42668 |
| Retro Game CPS II Pixel | 620687 | Illustrious | 1.6k | 11.2k | Soft/mature (lvl 7) | https://civitai.com/models/620687 |


### Creator: reakaakasky (utility / SFW-leaning)

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Stabilizer IL/NAI/CK * | 971952 | illus01 v1.198 | 10.9k | 156.7k | SFW-leaning (lvl 3) | https://civitai.com/models/971952 |
| RDBT | Anima (ckpt) | 2356447 | — | 1k | 27.5k | Soft (lvl 3) | https://civitai.com/models/2356447 |
| RDBT | Anima [lora] | 2364703 | — | 780 | 22.1k | Soft (lvl 3) | https://civitai.com/models/2364703 |
| Contrast Controller [IL/NAI] | 1523055 | — | 687 | 5.9k | **SFW** (lvl 1) | https://civitai.com/models/1523055 |
| Style Strength Controller [IL/NAI] | 1519509 | — | 603 | 6k | Soft (lvl 3) | https://civitai.com/models/1519509 |


### AMD-safe (GGUF / FP8 / low VRAM) for Klein / Z-Image / Qwen 2.1

Strip SageAttention / Triton-CUDA / DLSS / RTX VSR from any NVIDIA-branded graphs.

| Name | id | Version | 👍 | DL | Flag | URL |
|---|---:|---|---:|---:|---|---|
| Z-Image Turbo Quantized low VRAM | 2169712 | fp8 / int4 | 1.1k | 37k | Soft/mature (lvl 5) | https://civitai.com/models/2169712 |
| Z-Image Pro WF Low/High VRAM * | 2184844 | v27.1 | 848 | 33.6k | NSFW-capable | https://civitai.com/models/2184844 |
| FLUX2 Klein_9b Pro Grade Hi/Lo VRAM | 2213699 | v10.0.1 | 254 | 9.1k | Soft (lvl 15) | https://civitai.com/models/2213699 |
| Klein 4B GGUF Simple Fast | 2325916 | GGUF | 96 | 2.4k | Soft/mature (lvl 7) | https://civitai.com/models/2325916 |
| Unsloth Klein-4B-GGUF | 2400928 | Distilled | 52 | 2.7k | Soft (lvl 3) | https://civitai.com/models/2400928 |
| Rebels Flux Klein 9B-KV (GGUF+fp8) | 2464133 | — | 29 | 1k | **SFW** (lvl 1) | https://civitai.com/models/2464133 |
| Z-Image GGUF + Detail Daemon | 2343982 | v1.0 | 96 | 2.1k | **SFW** (lvl 1) | https://civitai.com/models/2343982 |
| Z_image_turbo 6G VRAM WF | 2170193 | v2.1 | 81 | 2.9k | Soft (lvl 3) | https://civitai.com/models/2170193 |
| Qwen Image 2.1 GGUF WFs * | 2952100 | EDIT/T2I | 5 | — | **SFW** | https://civitai.com/models/2952100 |
| Qwen Image 2.1 INT4 * | 2951557 | INT4 W4A8 | 23 | — | **SFW** | https://civitai.com/models/2951557 |
| Z-Image [fp8] | 2172944 | Turbo rev1.1 | 382 | 9.9k | **SFW** (lvl 1) | https://civitai.com/models/2172944 |


### Batch 2 counts
- Model ids cited in primary Batch 2 tables: ~75 (+ ~45 supplement net-new)
- New unique vs batch 1 (primary): ~59; merged pack ~100+ unique across tables+supplement
- Creators deep-dived: 5 (EauDeNoire, VelvetS, motimalu, YeiYeiArt, reakaakasky)
- Weight downloads: 0
- No PR opened / ISSUES.md not re-seeded

---


### Batch 2 supplement (executor merge — net-new only)

Additional Klein LoRAs/WFs, Animagine/RealVis depth, Pixel XL ckpt, Qwen-2 LoRA, and AMD strip targets not in the tables above. Full chat dump: `BATCH2.md`.

**Klein LoRAs (extra):** Anime→Real Slider `2367207` (140👍, SFW) · Ref2Font `2361340` (139👍) · AniEdit `2332320` (130👍) · R2I `2417505` (99👍, SFW) · Skeleton Pose Extractor `2413760` (92👍) · Realistic Detail `2662689` (80👍, SFW) · Face expression transfer `2363566` (68👍, SFW) · Retro comic PULPKHOR `2413450` (44👍, SFW).

**Klein WFs (extra):** Face/Head Swap `2356189` (208👍) · 4B vs 9B Multi Camera `2323627` (205👍, SFW) · Ultimate 6-in-1 `2543188` (173👍, SFW) · AIO Pro `2390013` (165👍) · 8-ref edit `2327242` (111👍, SFW) · Rebels PiD low-vram 4B `2651727` (44👍).

**Z-Image (extra):** ControlNet 6G `2192289` (163👍) · Head Swap Low VRAM `2478306` (40👍, SFW) · Z-Image-Art LoRA `2186776` (323👍) · Aesthetic LoRA `2214707` (269👍) · Fun Distill `2362961` (307👍) · FlatAnimeStyle `2175307` (162👍) · Radiant Realism `2395852` (186👍).

**Animagine depth (extra):** V3.1 official `260267` (18694👍, SFW) · Realistic Stylistic `1378329` (600👍) · Enma Ai XL4 `275687` (152👍) · Sansei Muramasa Opt `409642` (132👍) · LimbusCompany Style `401760` (175👍) · Genshin PV flat `367351` (87👍) · Sonny Boy Style `2450218` (SFW).

**RealVis lighting (extra):** Cucoloris `391036` (1723👍) · Translucent SSS `370194` (1511👍, SFW) · Facial Expressions `541620` (1197👍) · Low-key lighting `280421` (1074👍).

**Qwen 2.1 LoRA (extra):** Randoseru backpack base=Qwen 2 `2493065` (3👍, SFW) — ecosystem still sparse.

**AMD strip targets:** Sage/Triton/DLSS/RTX VSR on `2951890`, `2170120`, `2052847`, `2173425`, `2440676`; prefer keep Low-VRAM `2184844` / `2192289`. ROCm FA backends: prefer `--use-pytorch-cross-attention`; Sage experimental on RDNA4 (gfx1201).

**Pixel Art XL stack (extra):** Pixel Art Diffusion XL Sprite Shaper `277680` (2510👍, SFW) · Super_PixelArt_XL `581162`/`822320` · PC-98 ZIT `2182113` · PixelArt Perfect `2481158` · Illustrious HaDeS Pixel `1732312`.

**Creator extras:** VelvetS Dark Lines Krea2 `2807075` · motimalu Photo BG `1252497` / Impasto `1478417` / Light Concepts `2459979` · YeiYei Robot Joints `2030402` / Marionette `2114614` / Peter-Pan Style `2359657` · reakaakasky RDBT Krea2 `2765400` / Z-Image fp8 `2172944` (also in Z-Image table).

**Supplement counts:** ~45 net-new ids beyond primary Batch 2 tables · Weight downloads: 0 · No PR / no issue re-seed.


---

## Batch 2 browser verification

See `docs/research/CIVITAI-SCAVENGE-BATCH2-BROWSER-2026-09-21.md` (and pack `BATCH2_BROWSER.md`).

Hard confirmations:
- **No Qwen-Image-2.1 LoRA ecosystem yet** — `2952100` T2I: “2.1 doesnt have a base model available in selection yet.”
- **Z-Image quant `2169712`:** AMD pick `fp8_scaled_e4m3fn_KJ` ~5.9 GB; **skip Nunchaku/SVDQ** (NVIDIA-only).
- Extra 16GB Z-Image WFs: `2176468`, `2588499`.
- Pixel Illustrious: `43820` (trigger `pixel`); ZIT shader `2481158` (8 steps, CFG 1).
