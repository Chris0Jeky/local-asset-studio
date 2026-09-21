# BATCH 3 EXPLICIT QUEUE — hentai / NSFW only (2026-09-21 BST)

**QUARANTINE FILE.** Do **not** merge into `BATCH3.md`, SFW defaults, LAS SFW presets, or chat-ready SFW link dumps without an explicit user opt-in.

**Rules:** Page URLs + ids + `nsfwLevel` flags only. **No weight downloads.** civitai.red OK as mirror. NoobAI month character-NSFW = **hobby-only** (NC license).

Chris bases that *can* run this lane: WAI Illustrious v170 (rating tags), NoobAI XL 1.1 hobby NC, Pony V6. Prefer matching LoRA `baseModel` + EPS/V-Pred.

---

## 1. Rating / tag taxonomies

### WAI Illustrious safety rating tags
| Tag | Meaning (model docs / reviews) |
|---|---|
| `general` | Fully SFW / no exposure |
| `sensitive` | Light exposure (swimsuit/underwear territory) |
| `nsfw` | Nudity |
| `explicit` | Sexual / graphic |

**Usage notes:**
- For **explicit gens**, put the target rating in the **positive** prompt (`nsfw` or `explicit`) and describe acts/anatomy with Danbooru tags — don’t rely on the rating tag alone to undress (swimsuit vocabulary can stick).
- For **filtering**, put `nsfw` / `explicit` in **negative** (WAI page expectation). Avoid blanket-negative-ing all four rating tags (highly populated; hurts gens — bex guide).
- Mirror: https://civitai.red/models/827184 · canonical https://civitai.com/models/827184

### Illustrious / Danbooru classic ratings (some merges)
`safe` / `sensitive` / `questionable` / `explicit` — confirm which set your merge trained on (WAI uses general/sensitive/nsfw/explicit).

### Pony
`rating_explicit`, `rating_questionable`, `rating_safe` + `score_9, score_8_up, score_7_up` (articles `4248`, `8547`). Keep score stack **Pony-only**.

### NoobAI
Danbooru + **e621** NSFW tag vocabulary is strong. Official SFW prefix uses `safe`; for explicit, drop `safe`, add target tags, and **remove** furry-suppress negatives if you *want* anthro — or keep them for human-only hentai.

---

## 2. Prompt patterns (base-matched)

### WAI / Illustrious explicit skeleton
```
masterpiece, best quality, amazing quality, explicit,
1girl, solo, [character \(series\)], [appearance],
[clothing removal / nude tags], [pose / act Danbooru tags],
[camera], [bg], absurdres
```
**Neg (keep quality; don’t block the act you want):**
```
bad quality, worst quality, worst detail, lowres, bad anatomy, bad hands, watermark, signature, censored, bar censor, mosaic censoring
```

### Pony explicit skeleton
```
score_9, score_8_up, score_7_up, rating_explicit, source_anime,
1girl, …, [act tags]
```

### NoobAI explicit skeleton (hobby NC)
```
masterpiece, best quality, newest, absurdres, highres, explicit,
artist:…, 1girl, …, [Danbooru/e621 act tags]
```
Match LoRA to **V-Pred vs EPS**. Sampler CFG 4–5 V-Pred.

---

## 3. Wildcards / workflows popular for NSFW (flagged)

| Item | id | 👍 | lvl | Notes | URL |
|---|---:|---:|---:|---|---|
| NSFW Pose Wildcard (Depth Map) | 289285 | 1343 | 25 | Pose library for ControlNet depth — **explicit queue** | https://civitai.com/models/289285 |
| The Prompt Builder | 115347 | 1554 | 31 | Mixed; treat as NSFW-capable | https://civitai.com/models/115347 |
| Run七八造-Wildcards | 530531 | 578 | 31 | Illustrious/Other | https://civitai.com/models/530531 |
| Japanese 1girl wildcard dump | 1061871 | 321 | 31 | Illustrious; review lines | https://civitai.com/models/1061871 |
| Illu/Pony/SDXL Pro Grade WF | 2282970 / 2189190 | 506 / 424 | 31 | Dual SFW&NSFW WF — use explicit prompts here only | https://civitai.com/models/2282970 |
| Flux2 Klein Swap Anything (NSFW spelling in title) | 2313997 | 337 | 5 | Outfit/face swap; gallery may include NSFW | https://civitai.com/models/2313997 |
| Qwen Swap Anything | 2287824 | 246 | 7 | head/face/body/outfit | https://civitai.com/models/2287824 |

Dynamic Prompts format same as SFW (`__file__`, `{a|b}`) — keep NSFW `.txt` packs in a **separate folder** from SFW wildcards so LAS defaults can’t ingest them by accident.

---

## 4. NoobAI Month character-NSFW — hobby-only quarantine

Most Liked **Month** NoobAI LoRAs skew hard into explicit character dumps (Enigmata Kangoku Senkan / Taimanin line, etc.). **Do not** seed these into SFW queues or commercial LAS presets. NC / hobby use only.

| id | Name (short) | 👍 | lvl | Creator |
|---:|---|---:|---:|---|
| 438024 | Lieri Bishop (Kangoku Senkan) | 778 | 31 | Enigmata |
| 445604 | Naomi Evans (Kangoku Senkan) | 740 | 31 | Enigmata |
| 523721 | Beatrice Kushan (Kangoku Senkan 3) | 666 | 31 | Enigmata |
| 375502 | Yatsu Murasaki (Taimanin) | 697 | 31 | Enigmata |
| 95958 | Aishwarya Ray (Annerose) | 974 | 31 | Enigmata |
| 517170 | Maya Cordelia (Kangoku Senkan 2) | 389 | 31 | Enigmata |
| 531436 | Kila Kushan (Kangoku Senkan 3) | 388 | 31 | Enigmata |
| 540081 | Kiria Jef (Kangoku Senkan 2) | 399 | 31 | Enigmata |
| 667263 | Eliza Perlman (Kangoku Academia) | 304 | 31 | Enigmata |

Also month-chart adjacent (lvl 31 utility, not always “character hentai” but NSFW-capable galleries): Micro Details `1377820`, AI styles dump `723360`, girl’s clothes `445063`.

**Base:** NoobAI `833294` (nsfwLevel 31, hobby/non-commercial).

---

## 5. Pony / Illu NSFW-leaning concepts (from Batch 1 flags)

Cross-ref FINDINGS Batch 1: body-concept LoRAs such as `139131`, `217340` flagged explicit-leaning — keep here, not in SFW playbook. Hands `200255` / Aesthetic `929497` remain **utilities** usable in both lanes but galleries are NSFW-capable (lvl 31).

---

## 6. Articles touching NSFW prompting (use carefully)

| id | Title | URL |
|---:|---|---|
| 8547 | score_ / source_ / rating_ syntax (incl. rating_explicit) | https://civitai.com/articles/8547 |
| 4248 | score_9 Pony | https://civitai.com/articles/4248 |
| 6555 | Pony tips (clothing can include revealing) | https://civitai.com/articles/6555 |
| 23210 | Illustrious prompting (notes WAI ≠ Illu 2.0 NL) | https://civitai.com/articles/23210 |

WAI rating behavior write-up (external): https://lilting.ch/en/articles/wai-illustrious-v17-review

---

## 7. AMD / workflow hygiene (same as SFW)

Strip SageAttention / Triton / DLSS / RTX VSR from imported WFs. No weight URLs in this pack.

---

## Counts
- Explicit wildcard / WF ids listed: ~10  
- Noob month character quarantine: 9 (+ utilities noted)  
- Weight downloads: **0**  
- Kept fully separate from `BATCH3.md`

---

## Batch 4 deepen pointer (2026-09-21)

Fuller **tag skeletons** (WAI `general/sensitive/nsfw/explicit`, Pony `rating_explicit` + `score_9` stack, NoobAI/e621 hobby NC), more wildcards/WFs/LoRAs, and expanded month quarantine live in:

→ **`BATCH4_EXPLICIT.md`**

Notable B4 ids: NSFW MASTER `667086`, Smooth Detailer `1145743`, Detailed Perfection `411088`, Create Concept `1324671`, Krea2 Uncensored enhancer `2738703`, ANIMA Pro Grade NSFW WF `2382239`, Pose/Action wildcards `2908018`. Keep both quarantine files; do not merge into SFW docs.
