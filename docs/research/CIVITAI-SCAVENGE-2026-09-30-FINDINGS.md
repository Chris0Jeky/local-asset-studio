# FINDINGS — LAS Create / SFW stack week-delta 2026-09-30

Research only. No weights. Scrape window ~23:44–23:47 BST (Europe/London, UTC+1).  
Prior exclusion: 382 ids from 09-21 / 09-23 / 09-24 / 09-27 packs → `raw/_prior_ids.txt`.  
Unique models seen this run: **304** · NEW (not in prior): **~165** (noisy; curated below).

Stack match targets: WAI v170 / Illustrious · NoobAI · Pony V6 · Animagine · RealVis V5 · Klein FP8 · Z-Image · Qwen Edit-2511 / QI-2.1 · Pixel Art XL · Xinsir ControlNets.

---

## A. Qwen Image 2.1 / Edit-2511 (primary Create delta)

| id | name | type | signal | disposition | AMD / Create notes |
|---:|---|---|---|---|---|
| **2969143** | QI-2.1 Consistency LoRA | LORA | th≈103 · week NEW #1 quality | **try** | Identity hold for sheets/Create; start 0.6–1.0 |
| **2967375** | QI-2.1 Outpaint LoRA | LORA | th≈77 | **try** | Extend-any-side; pair with WF |
| **2964810** | QI-2.1 Outpaint WF | WF | th≈66 | **try** | Sanitize CUDA/Sage nodes |
| **2967979** | QI-2.1 Turbo 8-step LoRA | LORA | th≈28 · newest | **try** (compare) | **Not** a Pruna replacement; Pruna stays parked |
| **2962616** / **2965021** / **2969862** / **2966883** | QI-2.1 Edit / Realign / Rotate+Outpaint | WF | week newest cluster | **try** (sanitize) | Strip SageAttention (known in related WFs) |
| **2960962** | QI-2.1 TE Qwen3-VL 8B (card: uncensored) | TE | th≈34 | **try w/ gate** | Prior pack wanted fp8 TE; if uncensored leaks → Uncensored quarantine only |
| **2397289** | Blender Light Transfer for Edit 2511 | LORA | th≈29 | **try** | Lighting craft vs Remap `2305167` |
| **2031587** | Consistent character pose changer (2509) | WF | th≈167 | **try** | Verify on 2511 |
| **2182923** | Qwen Edit versatile photo poses | LORA | th≈164 | **try** | Pose utility |
| **2962344** / **2969889** | Pruna few-step LoRA + 8-step WF (Civitai mirrors) | LORA/WF | catalog | **park** | HF Pruna still parked after 2026-09-27 DESKTOP smoke (#934) — TE eviction kills wall-clock; quality below base |
| (prior) 2957332 / 2957912 / 2960750 / 2960890 | Fix · Nvfp4 · Sheet makers | — | prior wave | keep prior | Prefer **pinned int8** over NVFP4 on RDNA4 |

**Pruna continuity:** HF card unchanged (Qwen RESEARCH · ~320 MB 8-step · `x-linked-size: 335606104`). Do **not** re-queue as Create default.

---

## B. Illustrious / WAI / craft LoRAs

| id | name | signal | disposition | notes |
|---:|---|---|---|---|
| **2451718** | WAI-illustrious-Mix-FP8 | th≈87 | **try** | AMD FP8 stack-match |
| **2544636** | WAI-ANIMA | th≈5562 | **park** | Popular Anima WAI; later A/B vs v170 |
| **989367** | WAI-SHUFFLE-NOOB | th≈4630 | **park** | Noob hobby NC watch |
| **2714697** | Smooth Rotation Slider | th≈90 | **try** | Craft yaw after Smooth Detailer `1145743` |
| **1076338** | Zaush Art Style Illu/Pony | th≈1607 | park/optional | Style; not utility-first |
| Month Illu ckpt charts | One obsession / Unholy Desire / MiaoMiao / WAI-Mature / Equinox… | high thumbs | **EXPLICIT** | Do not promote to SFW Create |

Lighting/skin year searches mostly resurfaced priors (`1280702`, `1711037`, Hands `200255`, Smooth `1145743`) — no major NEW Illu lighting slider this week.

Pixel Art XL / Xinsir / RealVis month queries thin or prior-only — no Create flip candidates.

---

## C. Klein / Z-Image / Krea (Create-adjacent)

| id | name | disposition | notes |
|---:|---|---|---|
| **2712664** | Klein FinalCut (FP16/FP8/INT8) | **try** | Prefer FP8/INT8 on 16GB |
| **2964128** | FLUX.2 Klein 9B Outpaint | **try** | Week NEW; sanitize |
| **2394566** | Klein Style Selector WF | park | Low urgency |
| Z-Image Turbo family | mostly PRIOR | **park** daily Create | Separate family budget |
| Krea2 Turbo FP8 `2723583` etc. | see EXPLICIT / #1176 | **park Uncensored** | Not SFW Create |

---

## D. Ming (light)

| id | name | disposition |
|---:|---|---|
| **2975857** | Ming Poster retro 1950s WF | note on #1174 — Create **no** until AMD INT8 smoke |

---

## E. Anti-patterns confirmed this week
1. Month Most-Liked Illustrious checkpoints remain porn-leaning gravity wells → quarantine.  
2. Pruna Civitai mirrors ≠ permission to un-park DESKTOP verdict.  
3. “Uncensored” TE cards must not land in SFW Create without gate.  
4. FinePorn / FineCorn / SNOFS **list search still empty** (CF/index) — avoid by-id hammering.  
5. NVFP4 remains NVIDIA-skew; AMD path = pinned int8 / FP8/GGUF.

---

## F. Quality vs downloads
Prioritized thumbs + craft fit over raw downloads. Highest Create value this week is **QI-2.1 consistency + outpaint + FP8 WAI**, not month ckpt download kings.
