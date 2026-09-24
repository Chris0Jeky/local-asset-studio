# Civitai scavenge 2026-09-23 (LAS research)

> Repo mirror of handoff `civitai-scavenge-2026-09-23/FINDINGS.md`. No weights. No secrets.

# Civitai / LAS FINDINGS — Wave 2026-09-23 (BST)

**Audience:** Chris Local Asset Studio (LAS) → docs PR into `Chris0Jeky/local-asset-studio`  
**GPU:** AMD RX 9070 XT 16GB · Comfy portable · Studio LAS  
**Rule:** Page URLs + ids + version names + quality signals only. **No weight downloads. No API tokens.**

**Delta vs 2026-09-21 pack:** Do **not** rehash B1–B4 primary rows (Hands `200255`, Masterpiece `929497`, Stabilizer `971952`, Velvet `599757`, Gothic Neon `888231`, Dramatic Lighting `661736`, Flat Color Illu `1132089`, Character Sheet `100435`, Qwen Edit Multi Gen `1890385`, Plus 8-step `1998998`, Segment `2257259`, Multiple-Angles `2300308`, Klein official `2322332`, etc.). This wave = **Week/Month NEW + gap-fill** after LoRA smoke winners (#846 / #757–#759).

**nsfwLevel:** `1–3` SFW · `5–15` soft/mature possible · `≥23` NSFW-capable gallery (even if `nsfw:false`).

**Scrape window:** ~02:14–02:16 BST 2026-09-23 · public list/search only (no model-by-id; avoids CF 1015).

---

## Executive TLDR (Top 10 signals)

1. **Lighting gap fill (Illustrious):** Lighting/darkness slider `1280702` (@Mraclet, **5701👍**, r≈0.999, soft) — best new utility after smoke Dramatic Lighting; pairs with WAI v170 / Noob / Pony multi-base stacks.
2. **Style bridge creator `@zura_janai`:** Multi-base 90s anime pack (Retro Sci-fi `912942` 2984👍, Dark Art `1380736` 2452👍, Dark Fantasy `1108959`, 90s aesthetic `1357076`, melancholy `1738546`) spanning **Illustrious + Krea2 + Z-Image Turbo** — ideal LAS style-preset candidates without duplicating Velvet/Gothic Neon.
3. **`@Zoropaton` Anime-in-real `1979448`** (3062👍, Illustrious/Krea2) + Niji oil `1188058` / Niji anime `1261988` — semi-real bridge for WAI↔RealVis look tests.
4. **AI styles dump `723360` (@bakariso, 4173👍)** — multi-base Illustrious/Noob/Anima style pack; NSFW-capable gallery — use SFW triggers only in LAS presets.
5. **Qwen-Image-2.1 week surge (newest WFs):** All-in-One `2956235`, Inpaint `2956061`, Character Sheets/Face Swap `2957471`, Dataset gen `2957451`, Fixed WF `2957353` — low thumbs yet (**≤11**) but **directly answers #739 / #760** since B2.
6. **Qwen Edit stack beyond B2:** Consistence Edit LoRA `1939453` (**1928👍**, Klein 9B-base + Qwen variants), Multi-view Character Gen `2275805` (320👍), Swap Anything `2287824`, One-click three-view `2254072`, Blend Images `2260473`, Lightning 8-step `2047657` — character-consistency gold for LAS studio features.
7. **Klein anatomy/edit gap (#764):** Anatomy/Quality Fixer `2324991` (652👍 SFW), Base→Turbo `2324315`, Body Weight `2318844`, Skeleton Pose Extractor `2413760` (pairs #761 OpenPose work), Ultimate 6-in-1 `2543188`, dual Klein+Qwen edit WF `2579807`.
8. **Character sheet / multi-ref (LAS studio):** Illustrious turnaround `2925755` (**SFW lvl1**, new), Krea2 Helper `2933017`, Anima/Krea2 sheet `2626052`; plus Qwen multi-view WFs above — fills sheet gap beyond evergreen `100435`.
9. **Z-Image Turbo depth:** Official Turbo `2168935` (8663👍 SFW) still canonical; DemonAlone all-mode WF `2221604`; Radiant Realism `2395852`; Asian Consistent Character `2175402`; ControlNet 6GB WF `2192289` (16GB AMD-friendly).
10. **AMD/ROCm:** Prefer FP8/GGUF + Lightning; no attention flag needed (PyTorch attention is already selected on gfx1201; see [RUNTIME-PRECONDITIONS](../RUNTIME-PRECONDITIONS.md) §4); **strip SageAttention / Triton / DLSS / RTX VSR / Nunchaku** from imported WFs. Lonecat Pro Grade Illustrious/Pony/SDXL `2282970` / `2189190` and Klein/Z-Image WFs are strong but often NVIDIA-node heavy — sanitize before LAS import. MiniMax AMD HIP tip WF `2857584` is low-signal (7👍) but AMD-tagged.

---

## Ranking method

| Signal | Weight | Use |
|---|---|---|
| thumbsUpCount | Primary | Sort within base |
| thumbsUp/(up+down) | Primary | Prefer ≥0.99 |
| commentCount / multi-base versions | Secondary | Creator/WF trust |
| downloadCount | Noted only | Popularity ≠ quality |
| nsfwLevel | Flag every row | SFW queue quarantine |
| NEW vs prior 138 ids | Gate | Skip B1–B4 primaries. Review note (25 Sep): several "new" rows below repeat earlier-pack IDs (`1280702`, `1754132`, `723360`, `810000`, `1324671`, `669571`, `2925755`); check an ID against the 21 September packs before queuing it |

Period focus: **Week** + **Month** for hot; **Year** only for gap utilities not in prior pack.

---

## 1. Illustrious / WAI gap-fill (post-smoke)

Smoke winners already covered: Masterpiece, Stabilizer, Velvet, Gothic Neon, Hands, Dramatic Lighting, Flat Color Illu. **New utilities / styles:**

| Model | id | Version | Base | 👍 | Ratio | Flag | URL |
|---|---:|---|---|---:|---:|---|---|
| Lighting / darkness slider | `1280702` | Illustrious | Illustrious | 5701 | 0.9993 | SFW-leaning / soft | [1280702](https://civitai.com/models/1280702) |
| Slider - Shadowed with Backlighting - vxnLowKey | `2309544` | illust | Illustrious | 256 | 1.0 | SFW | [2309544](https://civitai.com/models/2309544) |
| Lighting slider | `1754132` | IL v1.0 | Illustrious | 331 | 0.997 | SFW-leaning / soft | [1754132](https://civitai.com/models/1754132) |
| Eyes outward slider | `1854678` | v1.0 | Illustrious | 322 | 1.0 | SFW | [1854678](https://civitai.com/models/1854678) |
| Skinny-Voluptuous Slider | `318990` | Illustrous | Illustrious | 820 | 0.9976 | NSFW-capable gallery | [318990](https://civitai.com/models/318990) |
| AI styles dump (Anima/Illustrious/RouWei/Noob) | `723360` | MIO-anima-b1_v6 | Anima | 4173 | 0.9993 | NSFW-capable gallery | [723360](https://civitai.com/models/723360) |
| Anime in real | `1979448` | v2.0 - Krea2 | Krea 2 | 3062 | 0.999 | SFW-leaning / soft | [1979448](https://civitai.com/models/1979448) |
| Retro Sci-fi 90's anime style Krea2/IllustriousXL/Anima | `912942` | Krea 2 | Krea 2 | 2984 | 1.0 | SFW-leaning / soft | [912942](https://civitai.com/models/912942) |
| Dark Art Style Krea2/Anima/illustriousXL/ZImageTurbo/Fl | `1380736` | Krea2 | Krea 2 | 2452 | 0.9996 | SFW-leaning / soft | [1380736](https://civitai.com/models/1380736) |
| Dark Fantasy 90's anime style Krea2/Anima/illustriousXL | `1108959` | Krea2 | Krea 2 | 1252 | 1.0 | SFW-leaning / soft | [1108959](https://civitai.com/models/1108959) |
| 90s anime aesthetic Krea2/Anima/illustriousXL/ZImageTur | `1357076` | Krea2 | Krea 2 | 1127 | 1.0 | SFW-leaning / soft | [1357076](https://civitai.com/models/1357076) |
| NEW FANTASY CORE - ILL-FLUX-PONY-SDXL- ZIT(detailer) | `810000` | V4 NFC-ILL | Illustrious | 2206 | 0.9991 | SFW-leaning / soft | [810000](https://civitai.com/models/810000) |
| Krekkov Style \| Goofy Ai | `1133519` | v1.0 | Illustrious | 3519 | 0.9994 | NSFW-capable gallery | [1133519](https://civitai.com/models/1133519) |
| Takorin Style \| ILXL & Anima | `878386` | v2.0 | Illustrious | 1788 | 1.0 | SFW-leaning / soft | [878386](https://civitai.com/models/878386) |
| Create Concept - Concept (Illustrious \| Pony \| Flux.1 D | `1324671` | v3.0_Illustrious | Illustrious | 1508 | 0.9993 | NSFW-capable gallery | [1324671](https://civitai.com/models/1324671) |
| Niji anime style [illustrious\|Flux\|Pony] | `1261988` | illustrious v3.0 | Illustrious | 2754 | 0.9989 | SFW-leaning / soft | [1261988](https://civitai.com/models/1261988) |

**VRAM (16GB AMD):** SDXL Illustrious + 1–2 LoRAs @0.6–0.85 + Xinsir OpenPose/Union = daily driver. Avoid stacking Micro Details + Smooth + style + CN all at once.

**WAI prompt reminder:** Euler a · CFG 5–7 · `masterpiece, best quality, amazing quality` · neg `bad quality, worst quality` · safety `general` — never Pony `score_9*` on WAI.

---

## 2. NoobAI / Pony Month deltas (quality-first; NSFW skew)

Month Most Liked Noob/Pony lists are **heavily Enigmata character-NSFW**. Do **not** promote those into SFW LAS queues (see EXPLICIT addendum). Useful **non-duplicate** SFW-leaning / multi-base hits:

| Model | id | Notes | Flag | URL |
|---|---:|---|---|---|
| AI styles dump (Noob ver) | `723360` | NoobAI V-Pred + Illustrious versions; style pack | NSFW-capable | https://civitai.com/models/723360 |
| Niji oil painting (Pony ver) | `1188058` | @Zoropaton; also Illustrious/Anima | soft | https://civitai.com/models/1188058 |
| Art Nouveau | `562604` | Pony MJ7 · 1202👍 · SFW-leaning | soft | https://civitai.com/models/562604 |
| Pony & Anima Add more details | `669571` | Detail utility · 1002👍 | soft | https://civitai.com/models/669571 |
| Lighting/darkness (Illu→test on Noob) | `1280702` | Multi-use slider | soft | https://civitai.com/models/1280702 |

**Hobby NC gate (#758):** NoobAI base remains non-commercial; keep watermark/license note in presets.

**Pony:** Keep `score_9` stack **Pony-only** (article `/articles/4248`).

---

## 3. Qwen-Image-2.1 / Edit advancements (since B2)

### 3a. Qwen Image 2.1 — newest Week workflows (low thumbs, high LAS relevance)

| Model | id | Version | 👍 | Flag | URL |
|---|---:|---|---:|---|---|
| 【Qwen Image 2.1】All-in-One Multi-Functional Workfl | `2956235` | v1.0 | 8 | SFW-leaning / soft | [2956235](https://civitai.com/models/2956235) |
| Qwen Image 2.1 Inpainting Workflow | `2956061` | v1.0 | 11 | SFW | [2956061](https://civitai.com/models/2956061) |
| Qwen Image 2.1 Workflow | `2956566` | v1.0 | 11 | SFW-leaning / soft | [2956566](https://civitai.com/models/2956566) |
| Qwen2.1 Can Do EVERYTHING! Character Sheets, Face  | `2957471` | v1.0 | 4 | SFW | [2957471](https://civitai.com/models/2957471) |
| Dataset generator Qwen2.1 | `2957451` | v1.0 | 9 | SFW | [2957451](https://civitai.com/models/2957451) |
| Qwen Image 2.1 Fixed Workflow v1.0 | `2957353` | v1.0 | 4 | SFW | [2957353](https://civitai.com/models/2957353) |
| Wikked Qwen 2.1 Workflow | `2956679` | v1.0 | 6 | SFW | [2956679](https://civitai.com/models/2956679) |
| Qwen Image 2.1 in ComfyUI \| Qwen Text-to-Image | `2955609` | v1.0 | 6 | SFW | [2955609](https://civitai.com/models/2955609) |

**Note:** Prior pack already listed enhancer WF `2951814` — still valid; this wave adds **inpaint / AIO / sheet / dataset** coverage for #739.

### 3b. Qwen-Image-Edit-2511 — new since B2 (consistency / multi-view)

| Model | id | Type | 👍 | Flag | URL |
|---|---:|---|---:|---|---|
| Consistence Edit Lora | `1939453` | LORA | 1928 | SFW-leaning / soft | [1939453](https://civitai.com/models/1939453) |
| Qwen_Edit_2511 Multi-view Character Generation | `2275805` | Workflows | 320 | SFW-leaning / soft | [2275805](https://civitai.com/models/2275805) |
| Qwen 2511 2509 Swap Anyting (head, face, body, o | `2287824` | Workflows | 246 | SFW-leaning / soft | [2287824](https://civitai.com/models/2287824) |
| Qwen_Edit_2511 One-click three-view drawing of a | `2254072` | Workflows | 119 | SFW-leaning / soft | [2254072](https://civitai.com/models/2254072) |
| Qwen_edit_2511 Character Replacement Workflow (K | `2307126` | Workflows | 133 | SFW-leaning / soft | [2307126](https://civitai.com/models/2307126) |
| Qwen Image Edit — Blend Images LoRA | `2260473` | LORA | 74 | SFW | [2260473](https://civitai.com/models/2260473) |
| Qwen-Image-Edit-2511 - Manga to anime Coloring F | `2272945` | LORA | 104 | NSFW-capable gallery | [2272945](https://civitai.com/models/2272945) |
| Qwen Image Edit Lightning | `2047657` | LORA | 83 | SFW-leaning / soft | [2047657](https://civitai.com/models/2047657) |
| Qwen-Image-Edit F2P | `2094349` | LORA | 200 | SFW | [2094349](https://civitai.com/models/2094349) |
| QwenEditUtils2.2 Optional Mask | `1939540` | Workflows | 340 | SFW-leaning / soft | [1939540](https://civitai.com/models/1939540) |
| Qwen Edit - face swap, head swap, anything swap  | `2045000` | Workflows | 171 | SFW-leaning / soft | [2045000](https://civitai.com/models/2045000) |
| Qwen Image Edit - Remix | `2338517` | Checkpoint | 324 | NSFW-capable gallery | [2338517](https://civitai.com/models/2338517) |

**Already installed / B2 (do not re-queue):** Lightning 4-step LoRA · Multi Gen `1890385` · Plus 8-step `1998998` · Segment `2257259` · Multiple-Angles `2300308`.

**16GB tip:** Qwen Edit FP8/GGUF + Lightning 4/8-step · CFG 1 · **do not** stack BF16 Edit + heavy TE + CN + 3 refs.

---

## 4. FLUX.2 Klein stack (#764)

| Model | id | Type | 👍 | Flag | URL |
|---|---:|---|---:|---|---|
| Klein Anatomy / Quality Fixer | `2324991` | LORA | 652 | SFW | [2324991](https://civitai.com/models/2324991) |
| Klein 4B/9B Base to Turbo Lora | `2324315` | LORA | 476 | SFW | [2324315](https://civitai.com/models/2324315) |
| Klein 9B Body Weight Slider | `2318844` | LORA | 344 | SFW-leaning / soft | [2318844](https://civitai.com/models/2318844) |
| Klein-9b-Turn2Real | `2406218` | LORA | 338 | SFW-leaning / soft | [2406218](https://civitai.com/models/2406218) |
| Flux 2 Klein Image Edit Skeleton Pose Extractor | `2413760` | LORA | 93 | SFW-leaning / soft | [2413760](https://civitai.com/models/2413760) |
| FLUX.2-klein-9B-R2I | `2417505` | LORA | 99 | SFW | [2417505](https://civitai.com/models/2417505) |
| FLUX.2 Klein 9B — Ultimate 6-in-1 Workflow (Face | `2543188` | Workflows | 174 | SFW | [2543188](https://civitai.com/models/2543188) |
| Edit workflow 2 in one - Flux Klein 9 + Qwen edi | `2579807` | Workflows | 44 | SFW | [2579807](https://civitai.com/models/2579807) |
| Flux 2 Klein Precise Face/Head Swap | `2356189` | Workflows | 211 | SFW-leaning / soft | [2356189](https://civitai.com/models/2356189) |
| FLUX 2 Klein 4B vs 9B Multi Camera Angles - One  | `2323627` | Workflows | 205 | SFW | [2323627](https://civitai.com/models/2323627) |
| FLUX.2 [klein] image edit 9B distilled 8 ref ima | `2327242` | Workflows | 111 | SFW | [2327242](https://civitai.com/models/2327242) |
| Flux.2 Klein / Ultimate AIO Pro (t2i, i2i, Inpai | `2390013` | Workflows | 165 | SFW | [2390013](https://civitai.com/models/2390013) |
| Flux.2 Klein Mix Workflow. Consistency, Enhanced | `2443743` | Workflows | 84 | SFW | [2443743](https://civitai.com/models/2443743) |
| FLUX.2-klein-9b-fp8 | `2363950` | Checkpoint | 260 | SFW | [2363950](https://civitai.com/models/2363950) |

**Verify base:** Many community LoRAs still tag `Flux.1 D` — only load versions marked **Flux.2 Klein 4B/9B** (or base/turbo match). Chris has Klein FP8 + FLUX.2-dev GGUF.

**Skeleton Pose Extractor `2413760`:** Bridges Klein edit ↔ OpenPose/#761 pose guide work.

---

## 5. Z-Image Turbo

| Model | id | Type | 👍 | Flag | URL |
|---|---:|---|---:|---|---|
| Z Image Turbo | `2168935` | Checkpoint | 8663 | SFW | [2168935](https://civitai.com/models/2168935) |
| Z-image turbo TXT2IMG, IMG2IMG, inpaint, outpain | `2221604` | Workflows | 118 | SFW-leaning / soft | [2221604](https://civitai.com/models/2221604) |
| Z Image (Turbo & Base) Workflow | `2170134` | Workflows | 317 | SFW-leaning / soft | [2170134](https://civitai.com/models/2170134) |
| Z-Image Turbo UltraReal workflow | `2190193` | Workflows | 274 | SFW-leaning / soft | [2190193](https://civitai.com/models/2190193) |
| [Z-Image-Turbo] Asian Consistent Character \| Ins | `2175402` | LORA | 238 | SFW-leaning / soft | [2175402](https://civitai.com/models/2175402) |
| Z-Image Turbo Radiant Realism Pro (Realistic, Ma | `2395852` | LORA | 186 | SFW-leaning / soft | [2395852](https://civitai.com/models/2395852) |
| Z-Image Turbo Lightning | `2409672` | LORA | 204 | NSFW-capable gallery | [2409672](https://civitai.com/models/2409672) |
| Z_Image_turbo Controlnet (6G VRAM can run it!) | `2192289` | Workflows | 164 | SFW-leaning / soft | [2192289](https://civitai.com/models/2192289) |
| [Z Image Turbo] Anime Style Lora | `2186398` | LORA | 219 | SFW-leaning / soft | [2186398](https://civitai.com/models/2186398) |
| Z-Image Base & Turbo Pro Grade Realism Workflow  | `2231181` | Workflows | 223 | SFW-leaning / soft | [2231181](https://civitai.com/models/2231181) |

---

## 6. Krea2 (#762 audit)

| Model | id | Type | 👍 | Flag | URL |
|---|---:|---|---:|---|---|
| Kreamania | `2729631` | Checkpoint | 1142 | NSFW-capable gallery | [2729631](https://civitai.com/models/2729631) |
| [Krea2 Turbo] AsianMix Lora | `2746042` | LORA | 548 | SFW-leaning / soft | [2746042](https://civitai.com/models/2746042) |
| Krea 2 Pro Grade w/ Image Edit, Style Transfer,  | `2726952` | Workflows | 395 | NSFW-capable gallery | [2726952](https://civitai.com/models/2726952) |
| Krea2 ID Edit Pro Grade Character Dataset Creato | `2805529` | Workflows | 362 | SFW | [2805529](https://civitai.com/models/2805529) |
| Lonecat's Krea2 Identity Edit & Head Swap | `2803688` | Workflows | 146 | SFW-leaning / soft | [2803688](https://civitai.com/models/2803688) |
| Krea2-SAT-DirtyRealism | `2796522` | Checkpoint | 525 | SFW-leaning / soft | [2796522](https://civitai.com/models/2796522) |
| Krea2 Turbo Workflow + Upscale + Edit + Uncen | `2169381` | Workflows | 528 | NSFW-capable gallery | [2169381](https://civitai.com/models/2169381) |
| Character sheet Helper | `2933017` | LORA | 171 | SFW-leaning / soft | [2933017](https://civitai.com/models/2933017) |

**B2 already covered:** Turbo ckpt family, Identity Edit, Detail Slider — audit disk vs these pages for #762; prefer **ID Edit Dataset Creator `2805529`** (SFW, 362👍) for LAS character pipelines.

---

## 7. Character consistency / sheet / multi-ref (LAS studio)

| Model | id | Base | 👍 | Flag | Why LAS |
|---|---:|---|---:|---|---|
| Character Sheet / Turnaround [Illustrious] | `2925755` | Illustrious | 50 | **SFW** | New Illu turnaround helper (beyond `100435`) |
| Character sheet Helper | `2933017` | Krea2 | 171 | soft | Krea2 sheet |
| Character Design Sheet ANIMA/Krea2 | `2626052` | Krea2 | 132 | soft | Design sheet |
| Consistence Edit LoRA | `1939453` | Klein 9B-base | 1928 | soft | Multi-image identity lock |
| Qwen Multi-view Character Gen | `2275805` | Qwen | 320 | soft | Sheet-like multi-view |
| Qwen One-click three-view | `2254072` | Qwen | 119 | soft | Turnaround |
| Qwen2.1 Sheets + Face Swap WF | `2957471` | Qwen 2 | 4 | SFW | Week-new; smoke for #739 |
| Klein 8-ref edit | `2327242` | Klein 9B | 111 | SFW | Multi-ref edit |
| Klein Skeleton Pose Extractor | `2413760` | Klein 9B | 93 | soft | Pose→edit bridge |

Evergreen still primary: Character Design Sheet `100435` (YeiYeiArt) — already in prior pack.

---

## 8. AMD / ROCm-safe workflow notes

| Practice | Detail |
|---|---|
| Attention | Nothing to add: PyTorch attention is already selected on gfx1201 (RX 9070 XT). Never use `--use-split-cross-attention`, which disables the AOTriton path ([RUNTIME-PRECONDITIONS](../RUNTIME-PRECONDITIONS.md) §4) |
| Strip from WFs | **SageAttention, Triton, DLSS, RTX VSR, Nunchaku/SVDQ, torch.compile inductor** |
| Quant | FP8 / GGUF Q4–Q5 for Klein, Qwen Edit, FLUX.2-dev; Z-Image Turbo native is light |
| VRAM budget | 16GB: one diffusion + one TE + ≤2 LoRAs + optional CN; don't BF16-stack Edit |
| Lonecat / Pro Grade WFs | Excellent features (Low VRAM branches) but often NVIDIA-centric nodes — sanitize |
| AMD-tagged WF | `2857584` MiniMax HIP tips — low thumbs; treat as tip sheet not production |

Refs: AMD ROCm ComfyUI FA backends blog · Comfy-Org#9910 (gfx1201 pytorch-cross-attention).

---

## 9. Creator watchlist deltas (since 2026-09-21)

| Creator | Delta | Action |
|---|---|---|
| **@zura_janai** | **NEW watch** — multi-base 90s anime (Illu/Krea2/Z-Image) | Add to style-preset scouting |
| **@Zoropaton** | Anime-in-real + Niji family still climbing | Semi-real bridge tests on WAI |
| **@bakariso** | Styles dump `723360` Month-hot | SFW-trigger only |
| **@lonecatone23** | Krea2 ID Edit Dataset `2805529`; Klein/Z-Image Pro Grade updates | #762 / #764 WF sanitize |
| **@Mraclet** | Lighting/darkness slider `1280702` | Gap utility after smoke |
| **@xiaozhijason** | Consistence Edit `1939453` + QwenEditUtils WF | #739/#760 consistency |
| **@Zovetry** | Qwen multi-view / three-view / ControlNet 6G | Sheet + low-VRAM |
| **@l226** | Klein Anatomy Fixer + Body Weight | #764 |
| Prior keep | EauDeNoire, VelvetS, motimalu, YeiYeiArt, CitronLegacy, L_A_X, PurpleSmartAI, WAI0731 | Unchanged |

---

## 10. Animagine / RealVis (thin Month signal)

Public Month LoRA queries for Animagine/RealVis returned **empty/near-empty**. Year hits remain thin vs Illustrious. **Gap stance:** keep prior Stabilizer Animagine `1319919` + RealVis skin/cinematic from B2; no strong NEW Month displacer. Optional clear Opt mirror `2110148` still SFW.

---

## Counts

| Metric | Value |
|---|---|
| Weight files downloaded | **0** |
| API tokens in pack | **0** |
| Prior pack ids excluded | 138 |
| Primary NEW rows tabulated | ~80 |
| Explicit quarantine file | yes (Noob Month character-NSFW skew) |
| GitHub issues filed | **0** (comments only on existing) |

---

## Pointers

- Prior pack PRESETS: `/workspace/handoffs/civitai-scavenge-2026-09-21/PRESETS.md`
- Prior FINDINGS: `/workspace/handoffs/civitai-scavenge-2026-09-21/FINDINGS.md`
- This wave github-docs: `github-docs/docs/research/CIVITAI-SCAVENGE-*.md`
