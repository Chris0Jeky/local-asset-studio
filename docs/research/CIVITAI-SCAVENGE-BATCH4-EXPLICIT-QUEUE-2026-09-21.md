# BATCH 4 EXPLICIT QUEUE — deepen (2026-09-21 BST)

**QUARANTINE FILE.** Do **not** merge into `BATCH4.md`, `BATCH3.md`, `PRESETS.md` SFW defaults, or SFW link dumps without explicit user opt-in.

Expands **`BATCH3_EXPLICIT.md`** (keep both). Page URLs + ids + `nsfwLevel` only. **No weight downloads.** civitai.red OK as mirror. NoobAI character-NSFW = **hobby NC only**.

Chris bases for this lane: WAI Illustrious v170 · NoobAI XL 1.1 hobby NC · Pony V6. Match LoRA `baseModel` + EPS/V-Pred.

---

## 0. Relation to Batch 3 explicit

B3 covered: WAI rating taxonomy, short skeletons, NSFW pose wildcards `289285`, Prompt Builder `115347`, Noob month Enigmata list (9 chars), Pony rating_explicit note.

**B4 adds:** fuller **tag skeletons** per base, more wildcard/WF/LoRA keepers with quality signals, expanded Noob/Illu/Pony month charts, Smooth*/Detail utility quarantine notes, e621 hobby guidance.

---

## 1. Base-matched tag skeletons (copy-paste)

### 1.1 WAI Illustrious — rating tags
| Tag | Use |
|---|---|
| `general` | SFW only (not this file) |
| `sensitive` | swimsuit / light exposure |
| `nsfw` | nudity |
| `explicit` | sexual / graphic |

Put target rating in **positive**. Describe acts/anatomy with **Danbooru tags** — rating alone often will not undress. For SFW filtering, put `nsfw, explicit` in negative (see PRESETS / B3). Do **not** blanket-negative all four rating tags.

**Explicit skeleton (WAI / Illu):**
```
masterpiece, best quality, amazing quality, explicit,
1girl, solo, [character \(series\)], [hair], [eyes],
nude, [breast size tags], [pussy / nipples as needed],
[pose / sex act Danbooru tags], [camera: from below / looking at viewer],
[bg], absurdres, highres
```
**Sensitive / nsfw variants:** swap `explicit` → `sensitive` or `nsfw`; adjust clothing (`bikini`, `lingerie`, `nude`).

**Neg (quality; allow the act):**
```
bad quality, worst quality, worst detail, lowres, bad anatomy, bad hands,
missing fingers, extra digits, watermark, signature, username,
censored, bar censor, mosaic censoring, text
```

Sampler: Euler a · CFG **5–7** · steps **25–40** · Clip Skip 2.  
Mirrors: https://civitai.com/models/827184 · https://civitai.red/models/827184 · MonAI WAI wiki.

### 1.2 Pony V6 — score + rating
```
score_9, score_8_up, score_7_up, rating_explicit, source_anime,
1girl, solo, [character], [appearance],
[act / anatomy tags], [bg]
```
Optional: `score_6_up` if you want looser quality; drop `source_anime` for furry/`source_furry`.

**Neg (keep explicit allowed):**
```
score_4, score_5, rating_safe, source_pony, bad anatomy, bad hands,
text, watermark, worst quality, censored
```
(Tune `source_*` to taste — article `8547`.)

Sampler: Euler a / DPM++ · CFG **6–8**. **Never** paste `score_9*` into WAI/Illu/Animagine/Noob.

### 1.3 NoobAI XL 1.1 — Danbooru + e621 (hobby NC)
```
masterpiece, best quality, newest, absurdres, highres, explicit,
artist:[name], 1girl, solo, [character],
[Danbooru act tags], [e621 tags if anthro/feral intended],
[camera], [bg]
```
- **Human-only hentai:** keep furry-suppress in neg: `mammal, anthro, furry, ambiguous form, feral, semi-anthro`
- **Want e621 anthro:** **remove** those furry-suppress negatives; use e621 species/act tags
- Match LoRA **V-Pred vs EPS** to ckpt · Euler · CFG **4–5** V-Pred · ~832×1216  
Ckpt: `833294` (nsfwLevel 31, hobby/non-commercial).

**Neg (human explicit, quality):**
```
worst quality, old, early, low quality, lowres, signature, username, logo,
bad hands, mutated hands, censored, bar censor, mosaic censoring,
mammal, anthro, furry, ambiguous form, feral, semi-anthro
```

---

## 2. Popular wildcard packs / workflows (flagged NSFW)

| Item | id | 👍 | lvl | Notes | URL |
|---|---:|---:|---:|---|---|
| NSFW Pose Wildcard (Depth) | 289285 | 1343 | 25 | B3 keeper — ControlNet depth poses | https://civitai.com/models/289285 |
| The Prompt Builder | 115347 | 1554 | 31 | B3 — mixed NSFW-capable | https://civitai.com/models/115347 |
| Run七八造-Wildcards | 530531 | 578 | 31 | B3 | https://civitai.com/models/530531 |
| Japanese 1girl dump | 1061871 | 321 | 31 | B3 — review lines | https://civitai.com/models/1061871 |
| Wildcard Pose/Action Collection | 2908018 | 50 | 23 | **B4** booru pose/action rolls (Anima) | https://civitai.com/models/2908018 |
| Illu/Pony/SDXL Pro Grade SFW&NSFW WF | 2282970 | 506 | 31 | Dual — use explicit prompts only here | https://civitai.com/models/2282970 |
| Pro Grade Low/High VRAM | 2189190 | 424 | 31 | B3 | https://civitai.com/models/2189190 |
| ANIMA Pro Grade SFW/NSFW + CN/Regional | 2382239 | 368 | 31 | **B4** Anima daily NSFW-capable WF | https://civitai.com/models/2382239 |
| Krea2 Uncensored I2P + enhancer + 4K | 2738703 | 741 | 23 | **B4** prompt enhancer (SFW/NSFW switch) — mirror galleries on .red | https://civitai.com/models/2738703 |
| SDXL Pony Illu DMD2 WF | 1215102 | 950 | 29 | Fast WF; gallery NSFW | https://civitai.com/models/1215102 |
| Blink universal WF (meta/upscale/FD) | 1621455 | 75 | 31 | NoobAI-capable universal | https://civitai.com/models/1621455 |

Keep NSFW `.txt` wildcards in a **separate folder** from SFW packs so LAS defaults cannot ingest them.

---

## 3. LoRAs / concepts with quality signals (explicit lane)

| Item | id | 👍 | lvl | Bases | Notes | URL |
|---|---:|---:|---:|---|---|---|
| NSFW MASTER | 667086 | 6471 | 29 | Flux/Krea/ZIT | **B4** high-signal NSFW helper (not Illu-native — test before WAI) | https://civitai.com/models/667086 |
| Smooth Detailer Booster | 1145743 | 9878 | 31 | Pony/Anima/SDXL | Quality booster; **explicit gallery** | https://civitai.com/models/1145743 |
| Smooth Lighting Enhancer | 1204179 | 3149 | 31 | Illu/Noob | Lighting; NSFW gallery | https://civitai.com/models/1204179 |
| Detailed Perfection (all-in-one) | 411088 | 6760 | 31 | Illu/Pony/SDXL/… | Hands/feet/face/body detail — EauDeNoire | https://civitai.com/models/411088 |
| Hands XL… | 200255 | 16372 | 31 | Illu/Pony/… | Utility (B1) — gallery NSFW | https://civitai.com/models/200255 |
| Add Micro Details | 1377820 | 7919 | 31 | Noob/Illu/Pony | B3 utility note | https://civitai.com/models/1377820 |
| Create Concept | 1324671 | 1508 | 31 | Illustrious | Concept builder | https://civitai.com/models/1324671 |
| Hentai Main Character [concept] | 1084513 | 442 | 5 | Illustrious | Concept — review triggers | https://civitai.com/models/1084513 |
| AI styles dump | 723360 | 4163 | 31 | Noob/Illu/… | Style dump NSFW gallery | https://civitai.com/models/723360 |
| girl's clothes | 445063 | 1700 | 31 | Noob/Illu/Pony | Clothing — NSFW-capable | https://civitai.com/models/445063 |

---

## 4. NoobAI Month character-NSFW — hobby NC quarantine (expand)

B3 Enigmata list remains. **Additional** month-chart / red-mirror adjacent (lvl 31 unless noted) — still **hobby-only**, never SFW/commercial presets:

| id | Name (short) | 👍 | Notes |
|---:|---|---:|---|
| 438024 | Lieri Bishop (Kangoku Senkan) | 778 | B3 |
| 445604 | Naomi Evans | 740 | B3 |
| 523721 | Beatrice Kushan | 666 | B3 |
| 375502 | Yatsu Murasaki (Taimanin) | 697 | B3 |
| 95958 | Aishwarya Ray (Annerose) | 974 | B3 |
| 517170 | Maya Cordelia | 389 | B3 |
| 531436 | Kila Kushan | 388 | B3 |
| 540081 | Kiria Jef | 399 | B3 |
| 667263 | Eliza Perlman | 304 | B3 |
| 604286 | 地雷系 / jirai kei | 1744 | Style — NSFW gallery |
| 330218 | Artist: Yoneyama Mai | 1620 | Artist style NSFW gallery |
| 538535 | Artist: Rei_17 | 1172 | Artist style |

Illu month also skews character-NSFW (e.g. Celestine `1317767`, assorted char dumps) — treat **Most Liked Month Illustrious** as explicit-leaning unless `nsfwLevel≤7` and gallery checks out.

**civitai.red** Illu/Pony/Noob month mirrors: use for browsing when main site blurs; same ids.

---

## 5. Articles (NSFW-relevant — use carefully)

| id | Title | URL |
|---:|---|---|
| 8547 | score_ / source_ / rating_ (incl. rating_explicit) | https://civitai.com/articles/8547 |
| 4248 | score_9 Pony | https://civitai.com/articles/4248 |
| 6555 | Pony tips (clothing may include revealing) | https://civitai.com/articles/6555 |
| 23210 | Illustrious prompting | https://civitai.com/articles/23210 |

External WAI ratings: https://wiki.monai.art/en/models/wai_illustrious_15 · https://lilting.ch/en/articles/wai-illustrious-v17-review

---

## 6. AMD hygiene

Same as SFW: strip SageAttention / Triton / DLSS / RTX VSR / Nunchaku from WFs (`2282970`, `2382239`, `2738703`, …). No weight URLs in this pack.

---

## Counts
- New explicit wildcard/WF ids beyond B3: ~8  
- New high-signal LoRA/concepts: ~8  
- Expanded skeletons: WAI / Pony / Noob(+e621)  
- Weight downloads: **0**  
- Fully separate from `BATCH4.md` / `PRESETS.md`
