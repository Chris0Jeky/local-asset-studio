# BATCH 3 — SFW prompt / tag / wildcard playbook (2026-09-21 BST)

**Audience:** Chris LAS · WAI Illustrious v170 · NoobAI XL 1.1 (hobby NC) · Pony V6 · Animagine XL 4 Opt · RealVis V5 · 16GB AMD RX 9070 XT  
**Rule:** Page URLs + ids + quality signals only. **No weight downloads.**  
**Explicit / hentai:** → `BATCH3_EXPLICIT.md` only (never mixed here).

Ranking: thumbs + like-ratio + article bookmarks + creator signal over downloads. SFW from `nsfwLevel` + gallery intent.

---

## 0. Golden rules (cross-base)

1. **Tag order (LAS default):** `quality → subject → artist/style → general` — then pose/action → clothing → background → lighting → enhancers (`highres`/`absurdres` last if prompt is long).
2. **Never paste Pony `score_9` / `score_8_up` into Illustrious / WAI / Animagine / NoobAI.** (Articles `4248`, `8547`.)
3. **Danbooru spelling wins:** use tag as on danbooru.donmai.us (spaces OK in modern UIs; escape `\(` `\)` when needed). Character name order = Danbooru order.
4. **Earlier tags weigh more** on Illu/WAI (~248 CLIP tokens before heavy dilution). Put identity + quality early; push long scene fluff later — or flip quality to the **end** on very long OC prompts (Arctenox `23210`).
5. **AMD:** strip SageAttention / Triton / DLSS / RTX VSR from any WF JSON before load.

---

## 1. Per-base Danbooru-style tag guides

### 1.1 WAI Illustrious (v170 installed) — SFW default

| Slot | Tags / notes |
|---|---|
| Quality (front or end) | `masterpiece, best quality, amazing quality` (+ optional `very aesthetic, newest`) |
| Rating (SFW) | `general` in positive; put `nsfw, explicit` in **negative** (model page / red / MonAI) |
| Subject | `1girl` / `1boy` / `1other` (+ `solo` if needed) |
| Character | Danbooru `name \(series\)` |
| Artist/style | `by artist_name` or LoRA (USNR `176554`, Velvet Mythic `599757`) |
| General | hair/eyes → clothing → pose → background → lighting |
| Enhancers | `absurdres, highres` at end |

**Sampler reminder:** Euler a · CFG **5–7** · steps **25–40** (v17 often fine at 15–30) · Clip Skip 2 · ≥1024².

**Canonical refs:** model `827184` · mirror https://civitai.red/models/827184 · article https://civitai.com/articles/23210 · MonAI https://wiki.monai.art/en/models/wai_illustrious_15

**Effective negative (SFW):**
```
bad quality, worst quality, worst detail, sketch, censor, lowres, bad anatomy, bad hands, missing fingers, extra digits, watermark, signature, username, nsfw, explicit, nude
```

### 1.2 Illustrious family (generic / merges)

Same Danbooru grammar as WAI. Official-ish order variants:

- **SeaArt / Tensor style:** quality → rating → artist → subject count → details → pose → composition → `absurdres, highres`
- **Arctenox (`23210`):** important identity first; if prompt is long, move quality tags to the **end** so OC tags don’t get diluted.

**Do not** use Pony score tags. Artist tags need enough Danbooru mass or use a style LoRA.

### 1.3 NoobAI XL 1.1 (hobby / non-commercial)

Trained on **Danbooru + e621**. Match **EPS vs V-Pred** LoRA versions to the ckpt.

| Slot | Tags |
|---|---|
| Quality prefix | `masterpiece, best quality, newest, absurdres, highres` (+ optional `very awa`) |
| SFW rating | `safe` (or `general`) |
| Artist | `artist:name` stacks work well (HF examples) |
| Subject / char / general | Danbooru + e621 tags (spaces; escape parens) |

**V-Pred sampler:** Euler · steps **28–35** · CFG **4–5** · zero-SNR / v-prediction scheduler if required by loader · ~832×1216.

**Effective negative (SFW anime, suppress furry bleed):**
```
nsfw, worst quality, old, early, low quality, lowres, signature, username, logo, bad hands, mutated hands, mammal, anthro, furry, ambiguous form, feral, semi-anthro
```

**Refs:** ckpt `833294` · HF Laxhar READMEs · Stabilizer Noob ver `971952` · Flat Color `1132089`.

### 1.4 Pony Diffusion V6

| Slot | Tags |
|---|---|
| Quality | `score_9, score_8_up, score_7_up` (+ optional lower `score_*_up`) — **Pony only** |
| Source / rating (optional) | `source_anime`, `rating_safe` (see article `8547`) |
| Subject / char / style | Booru tags; huge char coverage (articles `5102`, `6555`) |
| Style shortcuts | Gothic Neon `888231`, Velvet Portrait `599757`, Dramatic Lighting `661736` |

**Sampler:** Euler a / DPM++ often fine · CFG typically **6–8** · don’t expect Illu negatives to behave the same (Pony is less negative-sensitive).

**Effective negative (SFW lean):**
```
score_4, score_5, score_6, source_pony, source_furry, rating_explicit, rating_questionable, bad anatomy, bad hands, text, watermark, worst quality
```
(Tune `source_*` / `rating_*` to taste; see `8547`.)

### 1.5 Animagine XL 4.0 Opt

Official tag-order training (CagliostroLab):

```
1girl/1boy/1other, character, series, rating, {general…}, artist tags…, masterpiece, high score, great score, absurdres
```

**Put quality tags at the END** (front placement can kill artist triggers — Opt guideline).

**Sampler:** Euler a · CFG **5** · steps **28**.

**Effective negative:**
```
lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry
```

**Refs:** ckpt `1188071` · HF `cagliostrolab/animagine-xl-4.0` · Aesthetic Complete Animagine-v4 `1003636` (2.6k👍) · Stabilizer `1319919`.

### 1.6 RealVis V5 (photoreal — not Danbooru)

Natural language + light SDXL tags. Prefer EauDeNoire lighting stack from Batch 2 (`214956`, `280472`, `280454`, `289500`, Skin&Face `1426727`). Negatives: plastic skin, deformed hands, oversharpen, watermark.

---

## 2. Character vs general vs artist — quick matrix

| Base | Character | Artist/style | General |
|---|---|---|---|
| WAI / Illu | Danbooru char + series early | `by name` after subject or via LoRA | appearance → clothes → pose → bg |
| NoobAI | Danbooru/e621 char | `artist:name` stacks near quality | same + e621 species tags if wanted |
| Pony | Booru char (huge list `5102`) | style tags / LoRA; score block first | clothing lists in `6555` |
| Animagine | char + series after count | after general, **before** quality tail | any order mid-prompt |

---

## 3. High-bookmark / high-signal articles (SFW-usable)

| id | Title | Signal | URL |
|---:|---|---|---|
| 23210 | Arctenox Illustrious prompt guide | primary Illu/WAI | https://civitai.com/articles/23210 |
| 4248 | What is score_9 (Pony) | bm~82 / 370👍 | https://civitai.com/articles/4248 |
| 8547 | score_ / source_ / rating_ syntax | Pony grammar | https://civitai.com/articles/8547 |
| 6555 | Pony XL tips (chars/clothes/styles) | bm~446 | https://civitai.com/articles/6555 |
| 5102 | Pony recognized characters | bm~529 | https://civitai.com/articles/5102 |
| 10242 | Illustrious recognized characters | bm~369 | https://civitai.com/articles/10242 |
| 7972 | BG tags Pony + Illustrious | bm~328 | https://civitai.com/articles/7972 |
| 7484 | Samplers explained | bm~625 | https://civitai.com/articles/7484 |
| 3296 | Camera angles | bm~185 | https://civitai.com/articles/3296 |
| 1250 | Wilder wildcards + Dynamic Prompts | bm~75 | https://civitai.com/articles/1250 |
| 3527 | Quality stacking / multi-model | bm~179 | https://civitai.com/articles/3527 |
| 7036 | How I generate images | bm~405 | https://civitai.com/articles/7036 |
| 5545 | ZyloO LoRA training preset | bm~1031 | https://civitai.com/articles/5545 |

External (high signal, non-Civitai):  
- https://cagliostrolab.net/posts/optimizing-animagine-xl-40-in-depth-guideline-and-update  
- https://huggingface.co/cagliostrolab/animagine-xl-4.0  
- https://huggingface.co/Laxhar/noobai-XL-1.1  
- https://wiki.monai.art/en/models/wai_illustrious_15  
- https://whatlab.ai/guides/illustrious-prompting-guide  

---

## 4. SFW wildcard packs (Dynamic Prompts / Comfy)

**Ingest formats LAS/Comfy can use:**
- **Dynamic Prompts / A1111-style:** files under `wildcards/*.txt` (one entry per line); prompt token `__filename__`; combinators `{a\|b\|c}`, `{2$$__artist__}` (article `1250`).
- **Comfy:** Impact Pack / `ComfyUI-DynamicPrompts` / custom wildcard nodes reading the same `.txt` (or YAML packs).
- Prefer packs with **Illustrious / NoobAI / Pony / SDXL** in `baseModel` over pure SD1.5-only when possible.

### Keepers (SFW-leaning / utility)

| Model | id | 👍 | lvl | Bases | Why | URL |
|---|---:|---:|---:|---|---|---|
| Full Feature Fantasy Prompts - Characters | 45448 | 3846 | 7 | Illustrious, SD1.5 | Top fantasy char wildcards | https://civitai.com/models/45448 |
| Billions of Wildcards | 138970 | 1226 | 7 | SDXL/Other | Scenery/creatures/buildings | https://civitai.com/models/138970 |
| Female Poses Wildcard (400) | 83971 | 1131 | 3 | Other | Pose library SFW-usable | https://civitai.com/models/83971 |
| Wildcards - Camera Views | 24940 | 815 | 1 | Other | Multi-angle language | https://civitai.com/models/24940 |
| Face Expressions | 242487 | 468 | 1 | SD1.5 | Expression swaps | https://civitai.com/models/242487 |
| Camera Perspectives (507) | 286127 | 443 | 23 | SDXL | Angles (check gallery) | https://civitai.com/models/286127 |
| PonyXL Wildcards Vault | 615967 | 694 | 15 | Pony | Pony-native vault | https://civitai.com/models/615967 |
| artist style for noobxl1.0 | 949270 | 141 | 15 | Illu/Noob/SDXL | Artist stacks for Noob | https://civitai.com/models/949270 |
| Sunvibe Danbooru Poses/Actions | 1051581 | 102 | 7 | Illustrious | Danbooru pose tags | https://civitai.com/models/1051581 |
| Sunvibe Danbooru Locations | 1062164 | 71 | 7 | Illustrious | BG locations | https://civitai.com/models/1062164 |
| Posing Dynamics | 1994536 | 129 | 7 | Illu/Qwen | Pose dynamics | https://civitai.com/models/1994536 |
| Poses/Angles/BG/Clothing/Chars | 1926228 | 123 | 7 | Illustrious | All-in pack | https://civitai.com/models/1926228 |
| **SFW Prompt Pack** | 2409619 | 82 | 15 | Illu/Noob/Pony | Explicitly SFW-labelled | https://civitai.com/models/2409619 |
| Fantasy AutoPrompt | 48601 | 206 | 1 | SD1.5 | Fantasy lists | https://civitai.com/models/48601 |
| Fantasy origins + monsters (Pony) | 422735 | 152 | 3 | Pony | Fantasy/monster | https://civitai.com/models/422735 |
| Biome wildcards | 125114 | 141 | 1 | SD1.5 | real/fantasy/sci-fi biomes | https://civitai.com/models/125114 |
| Statement Outfits | 1952576 | 131 | 7 | Illustrious | Outfit variety SFW | https://civitai.com/models/1952576 |

**Quarantine from SFW defaults:** Prompt Builder `115347` (lvl 31), NSFW Pose Wildcard `289285` → explicit file; “Revealing Outfits” `1975903`, Japanese 1girl dump `1061871` (lvl 31) — review before SFW queues.

### Example LAS seed wildcards (drop into `wildcards/`)

`quality_illu.txt`:
```
masterpiece, best quality, amazing quality
masterpiece, best quality, amazing quality, very aesthetic, newest
```

`lighting_fantasy.txt`:
```
volumetric lighting
god rays
cinematic lighting
rim light
moonlight
bioluminescence
candlelight
dramatic shadows
```

`armor_sfw.txt`:
```
plate armor
ornate plate armor
leather armor
scale mail
knight armor
magical armor
cloaked armor
```

`magic_fx.txt`:
```
glowing runes
mana particles
arcane circle
floating magic books
energy aura
spell sparks
frost magic
fire magic
```

Prompt sketch:
```
__quality_illu__, general, 1girl, solo, __artist__, elf ranger, green cloak, __armor_sfw__, holding staff, __magic_fx__, forest, __lighting_fantasy__, absurdres
```

---

## 5. Proven SFW workflows (character sheet / multi-angle / outfit)

### Character sheet
| Item | id | 👍 | Flag | Notes | URL |
|---|---:|---:|---|---|---|
| Character Design Sheet (HELPER) | 100435 | 11463 | **SFW** lvl3 | Multi-base incl. Illu/Pony/Flux — YeiYeiArt | https://civitai.com/models/100435 |
| Character sheet (Pony LoRA) | 368139 | 2927 | soft | Pony sheet | https://civitai.com/models/368139 |
| Character Sheet / Concept Illu | 1041336 | 305 | soft | Illustrious | https://civitai.com/models/1041336 |
| GC-Character Sheet | 1774438 | 188 | soft | Illustrious | https://civitai.com/models/1774438 |
| Turnaround Generator Illu | 2925755 | 47 | **SFW** | Illustrious | https://civitai.com/models/2925755 |
| Quiron Character Design sheet | 834362 | 788 | soft | Illu+Flux | https://civitai.com/models/834362 |
| 3-View Consistency Sheet WF | 2194148 | 23 | SFW-lean | Illustrious Comfy | https://civitai.com/models/2194148 |
| Brie's Qwen Edit Lazy Sheet | 2078957 | 204 | soft | Edit-lane sheet | https://civitai.com/models/2078957 |
| KiraNugget Multiview Sheet | 2564795 | 25 | soft | Qwen | https://civitai.com/models/2564795 |

### Multi-angle (prefer edit lane on 16GB)
| Item | id | Notes | URL |
|---|---:|---|---|
| Multiple-Angles LoRA (Qwen Edit) | 2300308 | Batch1 keeper — re-shoot | https://civitai.com/models/2300308 |
| Qwen Multi-angle Storyboard | 2096307 | 213👍 | https://civitai.com/models/2096307 |
| Multi-angle control Qwen Edit | 2313745 | | https://civitai.com/models/2313745 |
| Multi-Angle Dataset WF 2511 | 2303045 | **SFW** lvl1 | https://civitai.com/models/2303045 |
| Klein multi-angle consistent | 2349397 | Flux.2 Klein | https://civitai.com/models/2349397 |
| Camera Views wildcards | 24940 | prompt-only | https://civitai.com/models/24940 |
| Camera angles article | 3296 | | https://civitai.com/articles/3296 |

### Outfit change (non-explicit)
| Item | id | Notes | URL |
|---|---:|---|---|
| Outfit try-on LoRA (Qwen+Klein) | 2367983 | already in LINKS | https://civitai.com/models/2367983 |
| Outfit Transfer Helper | 2111450 | 228👍 **SFW** | https://civitai.com/models/2111450 |
| Flux2 Easy Swap head/face/outfit | 2322506 | Klein 9B; no LoRA | https://civitai.com/models/2322506 |
| Statement Outfits wildcards | 1952576 | Illu | https://civitai.com/models/1952576 |
| Clothes wildcards (review) | 73184 / 78026 | older SD1.5; filter SFW lines | https://civitai.com/models/73184 |

**Illustrious daily WFs (16GB — strip CUDA-only):** Pro Grade Low/High VRAM `2282970` / `2189190` (nsfwLevel 31 galleries — use with SFW prompts + `general`); Eazy Illustrious `2421536`; essentials `2349309`.

---

## 6. Fantasy SFW-leaning (Velvet deepen + creatures/armor/FX)

### Style stacks
| Item | id | 👍 | Notes | URL |
|---|---:|---:|---|---|
| Velvet's Mythic Fantasy Styles | 599757 | 14680 | Illu / Pony / Flux / Anima / Krea2 / ZiT vers — **primary fantasy style** | https://civitai.com/models/599757 |
| Velvet Mythic Style Illu v1 | 1819791 | 33 | Illu-specific deepen | https://civitai.com/models/1819791 |
| Fantasy Graphite Sketch | 580163 | 1027 | Illustrious sketch fantasy | https://civitai.com/models/580163 |
| USNR thin-paint | 176554 | 10861 | soft illustration polish | https://civitai.com/models/176554 |
| Aesthetic Masterpiece | 929497 | 11911 | quality stack | https://civitai.com/models/929497 |
| Flat Color | 1132089 | 5985 | clean cel look | https://civitai.com/models/1132089 |

### Armor / creature / magic (Illu)
| Item | id | 👍 | Flag | URL |
|---|---:|---:|---|---|
| armored dress | 92654 | 760 | soft | https://civitai.com/models/92654 |
| Armored Maiden Core | 2171000 | 179 | soft | https://civitai.com/models/2171000 |
| Gothic game armors | 2392248 | 70 | **SFW** | https://civitai.com/models/2392248 |
| Magical Princess | 1227404 | 266 | **SFW** | https://civitai.com/models/1227404 |
| Fantasy wildcards 45448 / 422735 / 48601 | — | — | see §4 | — |

### Lighting / atmosphere
| Item | id | 👍 | Notes | URL |
|---|---:|---:|---|---|
| Lighting / darkness slider (Illu) | 1280702 | 5694 | primary Illu lighting control | https://civitai.com/models/1280702 |
| GOBO Lighting | 1020411 | 623 | soft | https://civitai.com/models/1020411 |
| Lighting slider | 1754132 | 331 | | https://civitai.com/models/1754132 |
| S1 Dramatic Lighting (Pony) | 661736 | 6425 | 31 comments | https://civitai.com/models/661736 |
| EauDeNoire rays / chiaroscuro | 289500 / 280472 | — | Batch2; RealVis+SDXL | see BATCH2 |
| BG tags article | 7972 | — | Pony+Illu locations | https://civitai.com/articles/7972 |

**Fantasy prompt recipe (WAI/Illu SFW):**
```
masterpiece, best quality, amazing quality, general,
1girl, solo, elf knight, silver plate armor, ornate pauldrons, glowing runes,
holding longsword, mana particles, ancient ruins, volumetric lighting, god rays,
by [artist or Velvet Mythic LoRA], absurdres, highres
```
Neg: WAI SFW neg from §1.1.

---

## 7. Sampler / CFG cheat-sheet (no cross-contamination)

| Base | Sampler | CFG | Steps | Quality block | Forbidden |
|---|---|---|---|---|---|
| WAI v170 | Euler a | 5–7 | 25–40 | masterpiece, best quality, amazing quality | score_9* |
| Illustrious | Euler a / ancestral | 5–7 | 20–30 | same | score_9* |
| NoobAI EPS | Euler a | 5–7 | 25–35 | masterpiece, best quality, newest… | score_9* |
| NoobAI V-Pred | Euler (+ v-pred sched) | 4–5 | 28–35 | same + safe | score_9* |
| Pony V6 | Euler a / DPM++ | 6–8 | 20–30 | score_9, score_8_up, score_7_up | Illu-only rating misuse |
| Animagine Opt | Euler a | 5 | 28 | masterpiece, high score, great score, absurdres (**end**) | score_9*; quality-at-front |
| RealVis V5 | DPM++ 2M Karras etc. | 5–7 | 25–40 | NL quality phrases | anime score/rating tags |
| Qwen Edit Lightning | euler/simple | 1 | 4 | NL instructions | don’t assume Illu tags |

Samplers deep-dive: article `7484`.

---

## 8. AMD 16GB notes (CUDA strip)

When importing Comfy WFs from `2282970`, `2189190`, `2078957`, `2096307`, `2322506`, etc.:
- Remove / bypass: **SageAttention**, **Triton**, **DLSS**, **RTX VSR**, Nunchaku/SVDQ NVIDIA paths.
- Prefer FP8/GGUF branches already listed in Batch 2.
- ROCm: `--use-pytorch-cross-attention` preferred.

---

## 9. Top SFW signals (Batch 3)

1. WAI/Illu tag order + rating `general` / neg `nsfw` — articles `23210` + MonAI/red.  
2. Animagine Opt quality **at end** — `high score, great score` (not Pony scores).  
3. NoobAI `newest` + `safe` + furry-suppress neg; match EPS/V-Pred.  
4. Pony `score_9` stack **only** on Pony (`4248`/`8547`).  
5. Fantasy style king: Velvet Mythic `599757` + Fantasy wildcards `45448`.  
6. Character sheet: YeiYei `100435` (11.4k👍 SFW).  
7. Multi-angle: Qwen Edit `2300308` + storyboard WF `2096307`.  
8. Illu lighting slider `1280702` (5.6k👍).  
9. SFW Prompt Pack wildcards `2409619` + Sunvibe Danbooru poses `1051581`.  
10. Illu Pro Grade WF `2282970` for daily driver (prompt SFW; gallery is NSFW-capable).

**Explicit content is quarantined in `BATCH3_EXPLICIT.md`.**

---

## Counts
- Articles cited: ~15 (+ HF/MonAI externals)  
- Wildcard packs listed: ~18 keepers  
- Workflow / sheet / angle / outfit ids: ~25  
- Fantasy/lighting LoRAs: ~12  
- Weight downloads: **0**  
- New GitHub issues: **0** (PR #756 only)
