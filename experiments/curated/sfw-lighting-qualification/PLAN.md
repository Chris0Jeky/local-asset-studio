# SFW lighting LoRA qualification plan — Civitai 1711037 × WAI v17

Status: **Executed comparison; results in [README.md](README.md).** The
Illustrious LoRA was downloaded on 2026-09-25; the receipt verifies
170,594,572 bytes and SHA-256
`8bf1c001b1a6ecf463df812470008264ec94bd3a2b1952546eea789eeec4f27d`.
The model is pinned in `models/library.json`. No ComfyUI package, app code,
preset, or graph change was made. Execution evidence is recorded in README and
the five result and recipe JSON files.
No preset promotion or art acceptance follows from these runs.

Date of metadata queries: 2026-09-25. Queue source:
`docs/research/LAS-IMAGE-MODELS-WAVE-QUEUE-2026-09-24.md`, row 14
(Dark/Dim lighting `1711037`, LoRA, Illustrious, fit, LAS Create **yes**,
soft, **try** — night/low-key complement after Dramatic Lighting).

## 1. Source identification and confidence

Model page: https://civitai.com/models/1711037/dark-dim-lighting-dark-background
API metadata: https://civitai.com/api/v1/models/1711037
Version API (Anima build): https://civitai.com/api/v1/model-versions/3323780
Version API (Illustrious build): https://civitai.com/api/v1/model-versions/1936270

| Fact | Value (queried 2026-09-25) | Confidence |
| --- | --- | --- |
| Model | "Dark / Dim lighting / Dark Background" by MLGnom, type LoRA | High (model page + API agree) |
| Builds listed | "Anima - v1.0" and "Illustrious - v1.0" tabs on the model page | High (page text) |
| Anima version | Version id **3323780**, file `Dark (Anima) v1.safetensors`, 87.62 MB (89723.4 KiB), fp16 SafeTensor, SHA-256 `F6ADDEFA8BA22EC003EB9806587F2F0B41871FD2044EC070B9D4F90B2A7F516C`, baseModel `Anima`, download `https://civitai.com/api/download/models/3323780?fileId=3209470` | High (version API payload) |
| Illustrious version | Version id **1936270**, file id **1833998**, file `Dark (Illustrious) v1.safetensors`, **170,594,572 bytes**, SHA-256 `8BF1C001B1A6ECF463DF812470008264EC94BD3A2B1952546EEA789EEEC4F27D`, baseModel `Illustrious` | High (coordinator queried model API and `civitai-fetch.py --version-id 1936270 --dry-run` on 2026-09-25; they agree) |
| Trigger words | `dark`, `dim lighting`, `dark background` (version `trainedWords`; card repeats them plus secondary `night`, `glowing`, `darkness`, `dark [colour]`) | High |
| Author strength guidance | **0.1–1**, usage tip strength 1; "higher weight = stronger darkness without changing composition much"; keep prompts short (≤75 tokens); avoid stacking many LoRAs; put `shiny skin` in negatives | High (card text) |
| Base-model compatibility with WAI v17 | The chosen build declares `Illustrious`, the WAI v17 family. Actual load and image quality remain untested. The Anima build declares `Anima` and must NOT be treated as Illustrious-compatible. | High for metadata, untested for execution |
| Published usage flags | Model API reports `allowCommercialUse: [Image, RentCivit]`, `allowDerivatives: false`, `allowNoCredit: false`, `allowDifferentLicense: false`; the version payload carries no separate flags. Record these as model-level metadata, not commercial clearance. WAI creator authentication/terms remain unresolved. | High for observed model API fields; legal effect unassessed |
| NSFW posture | Model `nsfw: false` in API; queue row marks it "soft". Treat as soft SFW-lab material; stop on any explicit output | Medium |

Do NOT copy example images into Git. No image was copied for this plan.

## 2. Chosen version and blockers (candidate plan)

**Candidate choice:** the **Illustrious v1.0** build of model 1711037, because
WAI v17 (`checkpoints/waiIllustriousSDXL_v170.safetensors`) is Illustrious-base
and LoRA cross-base use is unproven here. The Anima v1.0 build (version
3323780, §1) is fully identified above but is **not** the run candidate.

**Checks the coordinator must complete before a run:**

1. Recheck `python scripts/civitai-fetch.py --version-id 1936270 --dry-run`
   before transfer; require the same file id, bytes and SHA-256 as above. If
   they differ, stop and reconcile the version instead of downloading.
2. Retain the model-level usage flags above and the downloader's terms note in
   the receipt. Nothing here is license clearance; a flag is not a license.
3. Download only via `python scripts/civitai-fetch.py --version-id 1936270`
   with `CIVITAI_API_TOKEN` from the environment (never argv/config/print),
   into `loras/`, verifying SHA-256. Keep the receipt in
   `.runtime/downloads/receipts.json`. This was completed on 2026-09-25 with
   `--file-id 1833998`; the SHA-256 and bytes match the listing. Allow at least
   171 MB plus headroom on a new host.
4. If only the Anima build is obtainable, **do not run it on WAI v17** —
   record "wrong-base, not run" and stop. Cross-base (Anima LoRA on
   Illustrious) behavior is untested in this repo.

## 3. Exact route (no invented controls)

- Installed checkpoint: `checkpoints/waiIllustriousSDXL_v170.safetensors`
  (6,938,040,682 bytes; HF mirror
  https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170; creator
  authentication and original commercial terms unresolved per
  `presets/catalog.json` `wai.commercial_note`).
- Preset: **`wai`** (`presets/catalog.json`, `verified: false`) on graph
  `workflows/api/wai-api.json`.
- Graph inputs that hold the LoRA already exist — no graph/preset change is
  needed for this plan:
  - Node `8` (`LoraLoader`): `lora_name` ← downloaded file; `lora`
    binding = node `8` `strength_model` (+ `strength_clip` via
    `bindings_extra`), i.e. preset controls `lora_name` + `lora`.
  - Node `9` (`LoraLoader`, chained after node 8, feeds the KSampler):
    stays at **0** for all runs (slot off, pruned as in the 2026-09-12 run).
  - Positive node `2` text, negative node `3` text, width/height node `4`,
    seed/steps/cfg/denoise/sampler/scheduler node `5` — all bound by the
    `wai` preset today.
- Note: the graph's checked-in placeholder names (`cinematic
  lighting.safetensors`, `manga-ink-screentone.safetensors`, both strength 0)
  are replaced by the real filename only at submission time through the
  preset's `lora_name` binding. If the Studio prunes zero-strength slots as
  it did on 2026-09-12, the baseline runs with no LoRA file referenced.
- Settings-KB context (`presets/settings-kb.json`, WAI v17 family):
  quality tail at the END, short negative, euler_ancestral/normal default,
  steps band 15–30 (authored graph = 30), cfg band 5–7, `max_active` 2 LoRAs
  (this plan uses at most 1).

## 4. Fixed prompt and settings (held constant)

Original character, clearly adult, fully clothed. No named copyrighted
characters, no artist-style names. Trigger words are part of the fixed
prompt so the baseline measures "trigger words alone" and each LoRA run
differs by LoRA strength only.

- Positive (node 2):
  `1woman, adult woman, mature face, original character, long dark auburn hair, amber eyes, high-collared dark green travelling coat, leather gloves, brass lantern in raised right hand, standing on a stone bridge over a night river, moonlit mist, dark, dim lighting, dark background, cowboy shot, fantasy, masterpiece, best quality, amazing quality`
- Negative (node 3):
  `bad quality, worst quality, worst detail, sketch, censor, shiny skin, nsfw`
  (`shiny skin` per the LoRA card; kept short per the family notes.)
- Size 832×1216, steps 30, cfg 5.0, sampler `euler_ancestral`, scheduler
  `normal`, denoise 1.0 — the current `wai-api.json` graph values (also the
  2026-09-23 smoke values for WAI).
- Seed: one fixed seed first (e.g. `2026092501`). A second seed runs only
  if the first pass is informative (see §6).

## 5. A/B matrix (3 runs first, +2 conditional)

| Run | LoRA slot 8 | Slot 9 | Seed | Purpose |
| --- | --- | --- | --- | --- |
| A — baseline | 0 (off/pruned) | 0 | S1 | Trigger-words-only control |
| B — moderate | downloaded file at **0.6** (model+clip) | 0 | S1 | Mid-card lighting effect |
| C — strong | downloaded file at **1.0** (card usage tip) | 0 | S1 | Author-recommended strength |

Strength rationale: card range 0.1–1 with tip 1.0; 0.6 sits inside the
0.5–0.7 moderate band this repo's WAI smokes used before overshoot
(`experiments/curated/lora-smoke-20260923/README.md`).

**Second seed (S2, e.g. `2026092502`) only if the first pass is
informative:** B and/or C show a visible dim/night shift with subject
intact and no stop condition tripped. Then repeat **A and the best of
B/C** on S2 (2 runs, not the full grid). Otherwise stop after S1 and
write up why.

## 6. Measurement, stop conditions, review rubric

Intended measurement per run: (a) lighting quality — dim/night read,
single stable light source (lantern), no extra random lights;
(b) subject preservation — pose (standing, lantern raised), costume
(dark green coat, gloves), face/hair, bridge/river scene intact;
(c) artifact rate — hands, brightness boxes (card warns adetailer box
models brighten; this plan uses no adetailer), washed-out or collapsed
frames; (d) wall time and VRAM/peak memory **only if observed** (never
estimated).

Stop conditions (stop the whole qualification, record, do not work around):
wrong-base symptoms (style collapse, plastic render, lost prompt
adherence suggesting a base mismatch); any explicit or
youthful-looking output; missing-file or loader errors (diagnose, never
blind-retry); queue/backend unhealthy at preflight.

Plain-language review rubric (per run, recorded in the receipt):
Lighting 0–2 (0 = no dim shift vs baseline, 1 = visible night/dim shift,
2 = strong single-source low-key); Preservation 0–2 (0 = costume/pose
lost, 1 = minor drift, 2 = intact); Artifacts 0–2 (0 = clean, 1 = minor,
2 = run-breaking). Advance a strength only on Lighting ≥ 1 with
Preservation ≥ 1 and Artifacts ≤ 1 on S1.

## 7. Execution protocol (per `studio-execution-evidence`)

- **Preflight:** `GET /api/health` and `/api/backends` (or
  `.runtime/backend-state.json`); confirm primary ComfyUI healthy, queue
  empty (empty at coordinator preflight; re-check — it may have changed),
  disk headroom for the 171 MB weight plus outputs; note machine/GPU state.
- **Submission:** one Studio submission per run with `run.py baseline|moderate|strong`
  (`POST /api/jobs` with preset id `wai` + controls). Capture the Studio
  **job id** and ComfyUI **prompt ID**
  immediately for each run.
- **Exactly-once:** submit each job once. On timeout/lost connection/missing
  history, recover the prompt ID from `experiments/runs/<job>/` or ComfyUI
  `/history`; **never resubmit to find out** ("never retry an uncertain
  submission").
- **Inspection:** open every PNG (full resolution, not thumbnails/contact
  sheet only); record dimensions and what was actually seen, in plain words.
- **Receipt per run** (into `experiments/curated/sfw-lighting-qualification/`,
  small files only; dated paragraph in `CURRENT_STATE.md` keeping plan
  separate from results): submitted recipe JSON (also via
  `/api/jobs/<id>/recipe`), prompt ID, backend, wall seconds, peak memory
  if measured, LoRA file SHA-256, output SHA-256, inspection notes with the
  §6 scores.
- **Three states, kept apart:** *Generated* (render completed) ≠
  *Accepted* (owner art acceptance, stays in `HUMAN_TODO.md`, never
  inferred) ≠ *Licensed* (nothing cleared here; record flags verbatim).
  No catalog `verified` flip and no preset change follow from this plan.

## 8. Unresolved facts (for the coordinator)

1. WAI-mirror creator authentication and commercial terms remain unresolved;
   the model-level Civitai flags above do not clear them.
2. Trigger position in the prompt (card gives words, not positions; this
   plan embeds them mid-prompt before the framing tags — untested).
3. Whether S2 runs (depends on S1 outcome); S2 seed value.
