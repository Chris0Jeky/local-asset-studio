# FINDINGS — LAS image-models wave 2026-09-24 (BST)

**Audience:** Chris Local Asset Studio (LAS) → docs PR into `Chris0Jeky/local-asset-studio`  
**GPU:** AMD RX 9070 XT **16GB** · Comfy portable · LAS Create tab  
**Tracking:** [#934](https://github.com/Chris0Jeky/local-asset-studio/issues/934) (cross-links #739 / #760)  
**Rule:** Page URLs + ids + version names + quality signals only. **No weight downloads. No API tokens. No preset flips.**

**Delta vs prior packs:** Do **not** rehash B1–B4 / 09-23 primaries (Hands `200255`, Masterpiece `929497`, Stabilizer `971952`, Velvet `599757`, Gothic Neon `888231`, Dramatic Lighting `661736`, Character Sheet `100435`, Qwen Edit Multi Gen `1890385`, Plus 8-step `1998998`, Segment `2257259`, Multiple-Angles `2300308`, Klein official `2322332`, Lighting slider `1280702`, zura_janai styles, Anime-in-real `1979448`, Consistence Edit `1939453`, Klein Anatomy Fixer `2324991`, Qwen 2.1 WFs `2956235`/`2956061`/`2957471`, etc.). This wave = **Reddit Pruna seed + Week/Month NEW** after 09-23.

**nsfwLevel:** `1` SFW · `3–15` soft/mature possible · `≥23` NSFW-capable gallery.

**Scrape window:** ~23:05–23:12 BST 2026-09-24 · Civitai public list/search only (no model-by-id; avoids CF 1015) · HF README + HEAD size for Pruna (no weight body).

---

## Executive TLDR (Top 10)

1. **QUEUE #1 — PrunaAI few-step LoRAs for Qwen-Image-2.1** ([HF](https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1)) — 8-step default (~320 MB LoRA) on base QI-2.1; **no CFG**; own sigma schedule; OP Comfy tip strength **2** / 8 steps vs HF card strength **1.0** — **A/B both**. Verdict **try** (not preset flip). License **Qwen RESEARCH**. See §1.
2. **Reddit secondary:** 5-step LoRA (speed, visibly worse) · community TE `qwen3vl_8b_fp8_scaled` · quality compare vs **2511-lighting 8-step** (closest Civitai: LightingRemap `2305167` + Add Lighting WFs `2291445`/`2291406`).
3. **Qwen-Image-2.1 Week surge (NEW vs 09-23):** Fix LoRA `2957332` (65👍) · Nvfp4/Q4/Q3 ckpt `2957912` (42👍, AMD-relevant) · Character Design Sheet Maker `2960750` (**SFW**, 26👍) · Character Ref Sheet `2960890` (**SFW**, 14👍) · Lonecat Fast WF `2960068` (19👍).
4. **2511 edit utilities still missing from prior primaries:** Anime2Real `2110229` / `2287977`, skin `2097058`, OpenPose 8-step WF `2030628` (**SFW**), LightingRemap `2305167` (**SFW**).
5. **Illustrious lighting gap-fill (beyond `1280702`):** Dark/Dim lighting `1711037` (1060👍, soft) — try as night/low-key complement, not replacement.
6. **Style bridge (non-zura):** Retro Neo Noir multi-base `1836542` (762👍, Illu/Krea2/Z-Image/Flux) — park-to-try for style presets after smoke.
7. **Klein delta:** IMG2IMG+Upscaler `2326676` (103👍 SFW) · Inpaint Segment Ultimate `2331118` (93👍 SFW) · week Upscale WF `2961384` (new/low thumbs). KleiNova NSFW `2547526` → **EXPLICIT** quarantine.
8. **Z-Image:** Asian Mix LoKr `2328130` (201👍 soft) — optional style; official Turbo still canonical (prior).
9. **Month Illustrious ckpt charts** = NSFW hybrid spam (One obsession, Unholy Desire, MiaoMiao Harem, WAI-Mature, etc.) → **EXPLICIT.md**; do **not** SFW-queue.
10. **AMD/ROCm:** Prefer FP8 / GGUF Q4–Q5 QI-2.1 + Pruna LoRA; `--use-pytorch-cross-attention`; **strip SageAttention / Triton / DLSS / RTX VSR / Nunchaku** (e.g. prior Sage WF `2951890` stays sanitize-before-import). Lonecat / Pro Grade WFs often NVIDIA-node heavy.

---

## Ranking method

| Signal | Weight | Use |
|---|---|---|
| thumbsUpCount | Primary | Sort within base |
| thumbsUp/(up+down) | Primary | Prefer ≥0.99 |
| commentCount / multi-base | Secondary | Creator/WF trust |
| downloadCount | Noted only | Popularity ≠ quality |
| nsfwLevel | Flag every row | SFW vs quarantine |
| NEW vs prior 218+ ids | Gate | Skip B1–B4 / 09-23 primaries |
| Reddit seed | Priority | Pruna = row #1 |

Period: **Week** + **Month** for hot; **Year** for gap utilities not in prior packs. HF used for Xinsir/Pruna/QI-2.1 card metadata.

---

## Scoring columns (every FINDINGS row)

| Field | Values |
|---|---|
| VRAM fit | `fit` · `tight` · `no` (16GB AMD practical) |
| License | `ok` · `hobby-NC` · `unclear` · `blocked` (+ note when known) |
| LAS Create-tab | `yes` · `maybe` · `no` |
| NSFW | `SFW` · `soft` · `NSFW-capable` · `explicit` |
| Disposition | `try` · `skip` · `park` |

---

## 1. SEED — PrunaAI / Qwen-Image-2.1 few-step (Reddit 2026-09-24) — FINDINGS row #1

**Sources:** [r/StableDiffusion post](https://www.reddit.com/r/StableDiffusion/comments/1wp6la7/new_fewstep_lora_adapters_for_qwenimage21_5x/) · pack `reddit-extract.md` · `SEED-PRUNA-QWEN-21.md` · HF card README (scraped; API rate-limited).

| Model | id | Version | Base | 👍 | Ratio | VRAM fit | License | LAS Create-tab | NSFW | Disposition | URL |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| **Pruna-Qwen-Image-2.1 (8-step) ★#1** | HF | `p_qwen_image_2.1_8step_v0.1.safetensors` | Qwen-Image-2.1 | — (Reddit ~43) | — | **tight** | **Qwen RESEARCH** | **maybe** | SFW card | **try** | [HF](https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1) |
| Pruna-Qwen-Image-2.1 (5-step) | HF | `p_qwen_image_2.1_5step_v0.1.safetensors` | Qwen-Image-2.1 | — | — | **tight** | Qwen RESEARCH | maybe | SFW card | **try** (secondary) | same |
| qwen3vl_8b_fp8_scaled (TE) | community | fp8_scaled | QI-2.1 TE | — | — | **tight** | unclear | maybe | SFW | **try** (with #1) | comment tip |
| 2511-lighting compare target | see §3 | LightingRemap / Add Lighting | Qwen Edit 2511 | 105 / 6 / 5 | 1.0 | fit–tight | unclear | maybe | SFW | **park** (benchmark) | `2305167` etc. |

### VRAM / disk (RX 9070 XT 16GB) — estimate, no downloads performed

| Component | Disk (HEAD / card) | VRAM practical note |
|---|---|---|
| Pruna 8-step LoRA | **~320.1 MB** (`X-Linked-Size` 335606104) | Negligible vs base when loaded |
| Pruna 5-step LoRA | **~320.1 MB** (335606144) | Same; load **one** adapter only |
| Base `Qwen/Qwen-Image-2.1` | Large (7B visual DiT + TE + VAE) | **BF16 ≈ no** on 16GB with TE; prefer **FP8 or GGUF Q4–Q5** of QI-2.1 (Civitai mirrors: `2957912` Nvfp4/Q4/Q3, prior GGUF rows) |
| TE `qwen3vl_8b_fp8_scaled` | Large | FP8 TE + FP8/GGUF DiT = **tight**; do not stack BF16 TE |

**Fit verdict:** **tight** — workable if Create/Comfy already runs QI-2.1 (or Edit-class) in FP8/GGUF on this GPU; **no** if attempting full BF16 pipeline + TE + 3 refs + upscaler.

### Comfy / Create notes

| Item | HF card (authoritative) | Reddit OP (Comfy tip) |
|---|---|---|
| Steps | 8 (default) or 5 | **8** |
| LoRA strength | **1.0** | **2** |
| CFG | **no CFG** (`true_cfg_scale=1.0`, no negative) | no CFG |
| Sigmas | Exact per-adapter schedule (8-step: `1 → 14/15 → 6/7 → 10/13 → 2/3 → 6/11 → 0.4 → 2/9 → 0`; shift=1.0, no dynamic shifting) | not specified — **must match HF** |
| Pipeline | Diffusers `QwenImage21Pipeline` + Load LoRA; CUDA quickstart | Comfy Load LoRA node works (OP) |

**LAS Create-tab:** **maybe** — if Create already loads QI-2.1 LoRAs via standard LoRA slot, strength/steps can be tried without a new pipeline; **flag** if Create lacks custom sigma injection / forced no-CFG path (then Comfy graph import first). **Do not** flip default presets until DESKTOP A/B wins (#934).

**A/B plan:** (1) HF recipe strength 1.0 + exact 8-step sigmas + no CFG · (2) OP strength 2 + 8 steps · (3) vs base ~40-step · (4) vs 2511-lighting 8-step quality (Edit stack, not QI-2.1 — cross-family compare only).

**License:** Derivative of QI-2.1 under **Qwen RESEARCH LICENSE** — use restrictions; check before redistribute. Not “ok” for unrestricted commercial redistribute.

---

## 2. Qwen-Image-2.1 Week NEW (since 09-23)

| Model | id | Version | Base | 👍 | Ratio | VRAM fit | License | LAS Create-tab | NSFW | Disposition | URL |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| Qwen Image 2.1 Fix v1.0 | `2957332` | v1.0 | Qwen 2 | 65 | 1.0 | tight | unclear | maybe | soft | **try** | [2957332](https://civitai.com/models/2957332) |
| Qwen Image 2.1 Nvfp4 Q4 Q3 | `2957912` | NVFP4 | Qwen 2 | 42 | 1.0 | **fit**/tight | unclear | maybe | soft | **try** | [2957912](https://civitai.com/models/2957912) |
| [QI 2.1] Character Design Sheet Maker | `2960750` | V1.0 | Qwen 2.1 | 26 | 0.963 | tight | unclear | **yes**/maybe | **SFW** | **try** | [2960750](https://civitai.com/models/2960750) |
| QI 2.1 Character Ref Sheet (Face+Wardrobe+Pose) | `2960890` | v1.0 | Qwen 2 | 14 | 1.0 | tight | unclear | **yes**/maybe | **SFW** | **try** | [2960890](https://civitai.com/models/2960890) |
| Lonecats Qwen 2.1 Fast WF + upscalers | `2960068` | v1.0 Beta | Qwen 2.1 | 19 | 1.0 | tight | unclear | maybe | soft | **try** (sanitize) | [2960068](https://civitai.com/models/2960068) |
| Qwen_Image_2.1 (bf16 mirror) | `2953241` | bf16 | Qwen 2 | 48 | 1.0 | **no** (bf16) | Qwen RESEARCH-ish | no | soft | **park** | [2953241](https://civitai.com/models/2953241) |
| Qwen Image 2.1 ckpt mirror | `2954443` | v2.1 | Qwen 2.1 | 28 | 1.0 | tight | unclear | maybe | **SFW** | **park** | [2954443](https://civitai.com/models/2954443) |
| QI 2.1 AIO Xiaozhi (NSFW) | `2960228` | v1.0 | Qwen 2.1 | 10 | 1.0 | tight | unclear | no | soft/NSFW-lean | **skip** SFW · see EXPLICIT | [2960228](https://civitai.com/models/2960228) |

**Still prior (do not re-queue):** AIO `2956235`, Inpaint `2956061`, Sheets/FaceSwap `2957471`, SageAttention WF `2951890` (sanitize only).

**16GB tip:** Prefer `2957912` / prior GGUF over bf16 `2953241`. Strip Sage/Triton from any imported Lonecat/Pro Grade graph.

---

## 3. Qwen-Edit-2511 gap utilities + “2511-lighting” compare set

| Model | id | Version | Base | 👍 | Ratio | VRAM fit | License | LAS Create-tab | NSFW | Disposition | URL |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| Qwen-Edit_Anime2Real | `2110229` | v1.0 | Qwen | 404 | 0.9975 | tight | unclear | maybe | soft | **try** | [2110229](https://civitai.com/models/2110229) |
| anime2real-2511 | `2287977` | v1.0 | Qwen | 303 | 1.0 | tight | unclear | maybe | soft | **try** | [2287977](https://civitai.com/models/2287977) |
| qwen-edit-skin | `2097058` | v1.1 | Qwen | 299 | 0.9967 | tight | unclear | maybe | soft | **try** | [2097058](https://civitai.com/models/2097058) |
| Qwen Edit Plus (2509) OpenPose 8 Steps | `2030628` | v1.0 (old 2509) | Qwen | 258 | 0.9961 | tight | unclear | maybe | **SFW** | **try** | [2030628](https://civitai.com/models/2030628) |
| Qwen-Edit-2511_LightingRemap_Alpha0.2 | `2305167` | v1.0 | Qwen | 105 | 1.0 | fit–tight | unclear | maybe | **SFW** | **try** (compare #1) | [2305167](https://civitai.com/models/2305167) |
| Qwen_2511 Swap Background & Fix Lighting | `2305910` | — | Qwen | 40 | 1.0 | tight | unclear | maybe | **SFW** | **park** | [2305910](https://civitai.com/models/2305910) |
| Add Lighting - 2511 Multi-Image | `2291445` | v1.0 | Qwen | 6 | 1.0 | tight | unclear | maybe | **SFW** | **park** | [2291445](https://civitai.com/models/2291445) |
| Add Lighting - 2511 Single (Anti-Drift) | `2291406` | v1.0 | Qwen | 5 | 1.0 | tight | unclear | maybe | **SFW** | **park** | [2291406](https://civitai.com/models/2291406) |
| Multi-angle Storyboard Direct Output | `2096307` | v1.0 | Qwen | 216 | 1.0 | tight | unclear | maybe | soft | **park** | [2096307](https://civitai.com/models/2096307) |

**Hygiene:** Keep Edit-2511 Lightning/angles off QI-2.1 until evidence (#739/#760). Pruna adapters are **QI-2.1-only**.

---

## 4. Illustrious / WAI utilities & styles (NEW, non-explicit)

| Model | id | Version | Base | 👍 | Ratio | VRAM fit | License | LAS Create-tab | NSFW | Disposition | URL |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| Dark / Dim lighting / Dark Background | `1711037` | Illustrious v1.0 | Illustrious | 1060 | 0.9981 | **fit** | unclear | **yes** | soft | **try** | [1711037](https://civitai.com/models/1711037) |
| Retro Neo Noir (multi-base) | `1836542` | illustriousXL | Illustrious (+Krea2/ZIT/Flux) | 762 | 1.0 | **fit** | unclear | **yes** | soft | **try** | [1836542](https://civitai.com/models/1836542) |
| 30s Technicolor Movie | `886686` | — | SDXL 1.0 | 1300 | 0.9992 | **fit** | unclear | maybe | soft | **park** | [886686](https://civitai.com/models/886686) |
| Abandoned Style | `118103` | — | SDXL 1.0 | 816 | 1.0 | **fit** | unclear | maybe | **SFW** | **park** | [118103](https://civitai.com/models/118103) |

**WAI prompt reminder:** Euler a · CFG 5–7 · quality tags · never Pony `score_9*` on WAI/Illu/Noob/Animagine.

---

## 5. FLUX.2 Klein / Z-Image deltas

| Model | id | Version | Base | 👍 | Ratio | VRAM fit | License | LAS Create-tab | NSFW | Disposition | URL |
|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| Flux-2 Klein IMG2IMG + Upscaler | `2326676` | Flux2 Klein + LoRA | Klein 9B | 103 | 1.0 | tight | unclear | maybe | **SFW** | **try** | [2326676](https://civitai.com/models/2326676) |
| Klein Inpaint Segment Ultimate Edit | `2331118` | v2.0 | Klein 9B | 93 | 0.9688 | tight | unclear | maybe | **SFW** | **try** | [2331118](https://civitai.com/models/2331118) |
| Flux 2 Klein Image Upscale (week) | `2961384` | v1.0 | Klein 9B | 2 | 1.0 | tight | unclear | maybe | **SFW** | **park** | [2961384](https://civitai.com/models/2961384) |
| [Z Image Turbo] Asian Mix LoKr | `2328130` | v7.0 R fp32 | ZImageTurbo | 201 | 1.0 | fit–tight | unclear | maybe | soft | **park** | [2328130](https://civitai.com/models/2328130) |
| KleiNova NSFW Klein | `2547526` | 5.3 | Klein 9B | 311 | 0.9936 | tight | unclear | no | **explicit** | **skip** SFW → EXPLICIT | [2547526](https://civitai.com/models/2547526) |

Verify **Flux.2 Klein** base tags before load (many community assets still say Flux.1 D).

---

## 6. ControlNet / IP-Adapter / Xinsir / AMD notes

| Note | Disposition |
|---|---|
| Civitai Xinsir OpenPose mirror `2943879` still low-signal (2👍) — **prefer HF Xinsir** (installed stack) | **skip** Civitai mirror |
| Month IP-Adapter query empty this scrape | — |
| AMD HIP tip WF `2857584` (7👍 MiniMax) — low signal | **park** |
| Upscaler Month top hit is Mac DLSS port `2925631` — **strip / skip** for AMD (DLSS/NVIDIA lineage) | **skip** |

---

## 7. Explicit Month-chart quarantine (summary)

Illustrious Month Most-Liked checkpoints skew hard NSFW (One obsession `1318945`, Unholy Desire `1307857`, MiaoMiao Harem `934764`, WAI-Mature `1359594`, Milk Factory `1882087`, etc.). Full list → **`EXPLICIT.md`**. Never into SFW Create presets.

---

## AMD RX 9070 XT checklist (this wave)

- Launch: `--use-pytorch-cross-attention` (gfx1201)
- Prefer: FP8 / GGUF Q4–Q5 / Lightning / Pruna 8-step on QI-2.1
- Strip before import: SageAttention, Triton-CUDA, DLSS, RTX VSR, Nunchaku, SVDQ
- Disk for Pruna try: ~320 MB LoRA + existing QI-2.1 quant (do **not** pull bf16 base solely for this try)

---

## Files in this pack

See `README.md`. Reddit scored. Prior packs: `civitai-scavenge-2026-09-21/`, `civitai-scavenge-2026-09-23/`.
