# BATCH 4 — SFW leftovers + depth (2026-09-21 BST)

**Audience:** Chris LAS · WAI Illustrious v170 · NoobAI XL 1.1 (hobby NC) · Pony V6 · Animagine XL 4 Opt · RealVis V5 · RX 9070 XT 16GB  
**Rule:** Page URLs + ids + quality signals only. **No weight downloads.**  
**Explicit / hentai:** → `BATCH4_EXPLICIT.md` (+ `BATCH3_EXPLICIT.md`). Never mixed here.  
**Copy-paste presets:** → **`PRESETS.md`** (1-page).  
**Do not re-list Batch 3 primary rows** — this file deepens / fills gaps only.

Ranking: thumbs + like-ratio + article bookmarks/collects + creator signal over downloads. SFW from `nsfwLevel` + gallery intent.

---

## 0. What Batch 4 adds (vs B3)

| Gap in B3 | B4 fill |
|---|---|
| Tag dictionaries / autocomplete for Danbooru+e621 | `950325`, `2018479` |
| Sunvibe trio incomplete (poses+locations only) | Time/Weather `1095284` |
| Extra SFW wildcard vaults | `2151015`, `2765483`, `2717968`, `1752893`, `2231696`, `2012099` |
| RealVis prompt depth thin | Article `11432` + skin `580857` + camera language |
| Animagine Opt prompt depth thin | HF/Cagliostro reconfirmed + Detail Enhancer `321576` + Opt clear `2110148` + CN `1208930` |
| Noob/Pony/Illu stack gaps | Fantasy Core `810000`, People's Works `1400090`, Pony detail `669571`, BG enhancer `633524`, lighting sliders |
| Simple SFW Comfy SDXL suite | UmeAiRT `870368`/`871897`/`872149`/`956162` + article `17080` |
| Presets one-pager | **`PRESETS.md`** |

---

## 1. Strong wildcards / tag packs (NOT in BATCH3 primary)

| Model | id | 👍 | lvl | Bases | Why | URL |
|---|---:|---:|---:|---|---|---|
| Danbooru/e621 autocomplete tag lists (+ aliases, Krita) | 950325 | 736 | **1 SFW** | Illu/Noob/Anima/Other | **Primary tag dictionary** for WAI/Noob stacks | https://civitai.com/models/950325 |
| Danbooru tag complete csv (JP+EN) | 2018479 | 133 | **1 SFW** | Illustrious | TagComplete / dictionary ingest | https://civitai.com/models/2018479 |
| Random SFW Poses | 2151015 | 206 | 7 soft | Illustrious | Explicitly SFW-labelled pose rolls | https://civitai.com/models/2151015 |
| Sunvibe Danbooru Time/Weather | 1095284 | 52 | 7 soft | Illustrious | Completes Sunvibe with B3 `1051581`/`1062164` | https://civitai.com/models/1095284 |
| BUNNY’s SFW Wildcards (~16.5k prompts) | 2765483 | 41 | 7 soft | Krea 2 | Huge SFW English vault (phased release) | https://civitai.com/models/2765483 |
| Wildcard Prompt Suite (thousands) | 2717968 | 41 | **1 SFW** | Other | Lonecat drop-in modules; pair with Illu WFs | https://civitai.com/models/2717968 |
| Wildcards du Jour | 1752893 | 49 | 7 soft | Other | Brainstorm / theme rolls | https://civitai.com/models/1752893 |
| Portrait & Selfie Wildcards 15k+ (SFW) | 2231696 | 209 | 7 soft | ZImageTurbo | Qwen/Z-Image portrait language (SFW labelled) | https://civitai.com/models/2231696 |
| Anime boys wildcard (~2k Danbooru) | 2012099 | 26 | **1 SFW** | Other | Male char coverage gap | https://civitai.com/models/2012099 |
| Wildcard Gallery Extension | 611924 | 323 | 3 soft | Other | A1111 gallery UX for wildcards (management) | https://civitai.com/models/611924 |
| Prompt-libraries | 2812454 | 45 | 3 soft | Krea 2 | Prompt library bundle | https://civitai.com/models/2812454 |

**Still prefer B3 primaries for daily fantasy:** `45448`, `2409619`, `615967`, `949270`.

**Quarantine (do not put in SFW defaults):** Pose/Action Collection `2908018` (lvl 23) → explicit file; any pack titled NSFW / undress.

### Example seed files (additive to B3 `wildcards/`)

`time_weather_sfw.txt` (mirror Sunvibe intent):
```
morning, sunlight
golden hour
overcast, soft light
night, moonlight
rainy day
foggy morning
sunset, warm light
```

`camera_photo_sfw.txt` (RealVis / SDXL photo):
```
shot on Canon EOS 5D Mark IV, 85mm lens
shot on Sony A7 III, 50mm f/1.8
shallow depth of field, f/1.8, bokeh
golden hour, warm skin tones
studio softbox lighting
over-the-shoulder shot
```

---

## 2. RealVis V5 prompt depth (was thin in B3)

RealVis is **natural language + light SDXL tags**, not Danbooru. B3 only pointed at EauDeNoire lighting; B4 adds structure.

### Article (concrete)
| id | Title | Signal | URL |
|---:|---|---|---|
| 11432 | Ultimate Guide to Creating Realistic SDXL Prompts | collected~178 · views~17k · tipped | https://civitai.com/articles/11432 |

**Recipe from `11432` (SFW):** camera model/lens → DOF → lighting → composition → persona → clothing textures → quality NL.  
Avoid empty “ultra realistic / masterpiece” alone; prefer photographic language.

**Positive skeleton (RealVis V5):**
```
photo of [subject], [age/look], wearing [fabric/outfit details],
shot on Sony A7 III, 85mm lens, shallow depth of field f/1.8, natural bokeh,
soft natural lighting, golden hour, realistic skin texture, sharp eyes,
8k uhd, highly detailed
```

**Negative skeleton:**
```
cartoon, anime, illustration, painting, 3d render, plastic skin, wax figure,
deformed hands, extra fingers, mutated hands, oversharpen, oversaturated,
watermark, logo, text, blurry, lowres, ugly
```

**Sampler:** DPM++ 2M Karras / Euler · CFG **5–7** · steps **25–40** · ≥1024².

### Companion assets (SFW-usable; galleries may be mature)
| Item | id | 👍 | lvl | Notes | URL |
|---|---:|---:|---:|---|---|
| Realistic Skin Texture (Detailed Skin) | 580857 | 7513 | 15 mature | Multi-base incl. SDXL/Illu/Pony — skin detail | https://civitai.com/models/580857 |
| Skin&Face (Batch2) | 1426727 | — | — | already catalogued | see BATCH2 |
| EauDeNoire cinematic stack | 214956 / 280472 / 280454 / 289500 | — | — | Batch2 | see BATCH2 |
| Background Detail Enhancer | 633524 | 2879 | 3 soft | Pony/Krea — BG fill | https://civitai.com/models/633524 |

Ckpt ref: RealVisXL V5.0 `139562` (18111👍, lvl15 — use SFW prompts).

---

## 3. Animagine XL 4 Opt — prompt depth

B3 had order + neg; B4 locks official HF numbers and utility companions.

### Official structure (HF `cagliostrolab/animagine-xl-4.0` + Cagliostro Opt post)
```
1girl/1boy/1other, [character], [series], [rating], {general tags…}, [artist…], masterpiece, high score, great score, absurdres
```
**Quality block at END** (front placement weakens artist triggers on Opt).

| Setting | Value |
|---|---|
| Sampler | Euler a (Euler Ancestral) |
| CFG | **5** (range 4–7) |
| Steps | **28** (25–28) |
| Res | 1024² or portrait 832×1216 / 896×1152 |

**Negative (HF canonical):**
```
lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry
```

### Companions (not B3 primary)
| Item | id | 👍 | lvl | Notes | URL |
|---|---:|---:|---:|---|---|
| Animagine XL V3 Detail Enhancer | 321576 | 327 | 3 soft | Detail stack (V3-era; test on XL4 Opt) | https://civitai.com/models/321576 |
| Stabilizer AnimagineXL 4.0 | 1319919 | 194 | **1 SFW** | Stability (also in B3 refs) | https://civitai.com/models/1319919 |
| Aesthetic Complete Animagine-v4 | 1003636 | — | — | B3 keeper | see BATCH3 |
| Animagine-XL_4.0_Opt_clear | 2110148 | 60 | **1 SFW** | Clear/Opt variant checkpoint page | https://civitai.com/models/2110148 |
| Animagine XL 4.0 ControlNet | 1208930 | 35 | **1 SFW** | Pose/CN for Anim4 | https://civitai.com/models/1208930 |

External: https://huggingface.co/cagliostrolab/animagine-xl-4.0 · https://cagliostrolab.net/posts/optimizing-animagine-xl-40-in-depth-guideline-and-update

---

## 4. High-signal SFW gaps — WAI / Noob / Pony stacks

### Tag / style utilities
| Item | id | 👍 | lvl | Stack | URL |
|---|---:|---:|---:|---|---|
| People's Works: SDXL | 1400090 | 5780 | 7 soft | **NoobAI** style corpus | https://civitai.com/models/1400090 |
| NEW FANTASY CORE | 810000 | 2203 | 7 soft | Illu/Pony/SDXL/Flux/ZIT detailer | https://civitai.com/models/810000 |
| Pony & Anima Add more details | 669571 | 998 | 7 soft | **Pony** detail booster | https://civitai.com/models/669571 |
| Lighting temperature slider | 1647230 | 437 | 3 soft | Illustrious (pairs with B3 `1280702`) | https://civitai.com/models/1647230 |
| Lighting Slider (Pony) | 502254 | 1611 | 13 mature | Pony lighting control | https://civitai.com/models/502254 |
| Smooth Lighting Enhancer | 1204179 | 3149 | 31 **gallery NSFW** | Illu/Noob — **utility**; keep prompts SFW | https://civitai.com/models/1204179 |

> `1204179` / many “Smooth*” EauDeNoire-adjacent utilities are **nsfwLevel 31 galleries** — usable as quality tools in SFW queues if prompts stay `general` / SFW; do not treat as SFW content packs.

### Workflows (SFW-friendly; strip CUDA)
| Item | id | 👍 | lvl | Notes | URL |
|---|---:|---:|---:|---|---|
| 【SDXL】TXT to IMG | 870368 | 179 | 3 soft | UmeAiRT simple suite | https://civitai.com/models/870368 |
| 【SDXL】INPAINT | 871897 | 196 | **1 SFW** | | https://civitai.com/models/871897 |
| 【SDXL】IMG to IMG | 872149 | 141 | **1 SFW** | | https://civitai.com/models/872149 |
| 【SDXL】ControlNet | 956162 | 125 | **1 SFW** | | https://civitai.com/models/956162 |
| Simple ComfyUI SDXL/Pony/Illu/Flux (article+JSON) | 17080 | bm~212 | — | Attachments on article | https://civitai.com/articles/17080 |
| Consistency characters (img+prompt) | 2047895 | 256 | 15 mature | Illu consistency | https://civitai.com/models/2047895 |
| FULL Character Sheet & Location Sheets | 2861120 | 124 | **1 SFW** | Fast sheets (MiniMax H3 — check AMD) | https://civitai.com/models/2861120 |
| Character Expression Editing 2511 | 2515418 | 46 | **1 SFW** | Qwen Edit expressions | https://civitai.com/models/2515418 |

**AMD:** strip SageAttention / Triton / DLSS / RTX VSR / Nunchaku from any imported WF. MiniMax H3 / CUDA-only branches may not run on RX 9070 XT — prefer UmeAiRT SDXL suite + B3 Illu Pro Grade with CUDA nodes removed.

### Articles (new vs B3 table)
| id | Title | Signal | URL |
|---:|---|---|---|
| 11432 | Realistic SDXL prompts | collected~178 | https://civitai.com/articles/11432 |
| 17080 | Simple ComfyUI SDXL/Pony/Illu/Flux | bm~212 | https://civitai.com/articles/17080 |
| 2054 | Comprehensive SD / AI gen guide | bm~257 | https://civitai.com/articles/2054 |

(B3 guides `23210`/`4248`/`8547`/… remain canonical — not re-tabled.)

---

## 5. Pointers

- **SFW copy-paste presets:** `PRESETS.md`
- **Explicit deepen + base-matched skeletons:** `BATCH4_EXPLICIT.md` (also expands `BATCH3_EXPLICIT.md`)
- **Full Batch 3 playbook:** `BATCH3.md`
- **PR:** Grok updates **#756** only — no new issues

---

## Counts
- New SFW wildcard/tag packs: ~11  
- RealVis depth: 1 article + skin/lighting companions  
- Animagine depth: HF lock + 4 companions  
- Stack gap LoRAs/WFs: ~15  
- Weight downloads: **0** · New GH issues: **0**
