# Qwen-Image 2.1 Pareto: seed audition with B0, Pruna F0 and the 2.1 Fix LoRA (Q1) — 27 September 2026 (18:07-18:22 local)

Refs #1028. This is the smallest matrix that answers the question the earlier rungs left open.
- The step ladder (`qi21-steps-20260927`) parked F0-by-steps and Q1-by-steps; B0 at 25 steps holds.
- The Pruna lab (`qi21-lab2-20260927`) found that Pruna saves sampler time but not job time, because the 8.9 GB text encoder
  evicts the diffusion model on every new prompt. It said Pruna "becomes worth another look when the text encoder can stay
  resident (… batches that reuse one prompt)".

This run is that seed audition: the prompt text is unchanged within each block. It also gives the untested **2.1 Fix LoRA**
(downloaded 23 Sep, civitai 2957332 / version 3350008, sha256 `e4a36915…`) its first quality+ run.

**Setup.**
- Backend: the Studio switched explicitly to `qwen21` (isolated ComfyUI v0.37.0, port 8196) with `POST /api/backends/switch`
  at 18:05. The switch checked idle queues and no active Studio work.
- Weights: the installed Comfy-Org INT8 model (`qwen_image_2.1_int8_convrot`), the `qwen3vl_8b_int8_convrot` text encoder,
  and the bf16 VAE, at 1024², euler/simple, CFG 1. Nothing was downloaded.
- Prompts: the ladder's `char` and `prop` prompts. The `scene` prompt comes out photographic by wording, so it is skipped.
- Seeds: three fresh seeds (2026092731-33), run in the order B0 ×3, F0 ×3, Q1 ×3 per prompt.
- Submission: straight to ComfyUI, one POST per cell, none resubmitted (`run.py`).
- Commit guard: host commit sampled every 0.5 s, with a stop at 92 %. The peak was 86.3 %; starting points were 46-78 %.

| Condition | Graph |
| --- | --- |
| **B0** | no LoRA, 25 steps |
| **F0** | Pruna 8-step v0.1 (`p_qwen_image_2.1_8step_v0.1`, sha256 `f0865d68…`) at strength 2.0, `KSampler` 8 steps. This is the lab's p2 recipe, which was not worse than the card's sigmas |
| **Q1** | 2.1 Fix LoRA (`qwen-image-2.1-fix-1.0-comfy`) at strength 1.0, 25 steps, no trigger word (none is recorded) |

## Timing (whole prompt `exec_s` from ComfyUI history; sampler times from the backend log)

| | B0 | F0 (Pruna) | Q1 (Fix) |
| --- | ---: | ---: | ---: |
| Sampler | 15-16 s (25 steps, ~1.55 it/s) | 4-5 s (8 steps, ~1.6 it/s) | 15-16 s |
| Mean exec_s, all 6 cells | 53.9 s | 44.9 s | 42.0 s |
| Cells where the text encoder did **not** run (conditioning served from cache) | 26.0, 35.5 s | 40.6 s (the first run after the LoRA patch) | none |
| Cells where it re-ran without a text-encoder reload | 41.3 s | 27.9, 32.4, 33.1 s | 36.6-46.2 s |
| Cells that reloaded the text encoder (2 logged, 3 inferred) | 70.0-79.9 s | 58.2-77.2 s | — |

**The premise failed on this PC.** With the prompt text unchanged, the conditioning node was still recomputed in 15 of 18
cells (`cached_nodes` in `runs.jsonl`). ComfyUI's cache dropped it. The log shows a whole text-encoder reload
("Requested to load QwenImage21TEModel_", `qwen21-log-1808-1822.txt`) for prop-B0-32 (70.0 s) and prop-F0-31 (58.2 s). Three
earlier 70-80 s cells (char-B0-31, the cold first run; char-B0-33; char-F0-32) predate the log's ring buffer, which begins at
18:09:55, so their reload is inferred from the time alone. In every cell
the diffusion model was requested again ("Requested to load QwenImage21") before sampling. That costs about 15-20 s per prompt
even when the text encoder stays out.

So even in a seed audition, the per-image floor is about 25 s of paging. Pruna's ~11 s sampler saving does not show up in the warm cells:

| Measurement | B0 | F0 | F0 / B0 |
| --- | --- | --- | ---: |
| Warm cells without a text-encoder reload (B0 n=3, F0 n=4) | 25.975, 35.530, 41.345 s (mean 34.28) | 27.938, 32.378, 33.072, 40.552 s (mean 33.49) | 0.98 |
| All 6 cells (mean exec_s) | 53.9 s | 44.9 s | 0.83 |

Both ratios miss the F0 gate, which needs about 0.55×.

## Quality (blind, one agent, `judgements.jsonl`; `key.sealed.json` read after every judgement was written)

| | B0 | F0 (Pruna) | Q1 (Fix) |
| --- | --- | --- | --- |
| Keeps (of 6) | 5 | 3 | 1 |
| Mean rubric score | 3.92 | 4.12 | 3.39 |
| char | keep ×3 | keep ×2 (the best-scored char, 4.6); one fixable: the lantern hangs from a separate hooked pole | fixable ×3: a flat, low-detail finish; blocky or fat fingers on the lantern hand; one reads as a man in a suit and tie |
| prop | keep ×2; fixable ×1 (tangled extra chain loops) | keep ×1; fixable ×2 (numerals on the dial despite "no text"; background dirt speckles) | keep ×1; fixable ×2 (an arrow needle and a second ring; a melted lid) |

## Reading against the #1028 gates

- **F0 (Pruna 8-step at 2.0):** quality is level with B0 on this sample (higher mean, fewer keeps; its prop defects are dial
  numerals, as in the lab). It is **not faster**: 0.98× of B0 on warm cells (means 33.49 s against 34.28 s) and 0.83× over all six cells, against the ~0.55× gate. The DiT
  reload per prompt dominates on 16 GB. **Park (not GREAT).** This confirms the lab's reading for the seed-audition case
  too. Batched latents (several seeds inside one prompt) are what would keep the models resident; that was not tested.
- **Q1 (2.1 Fix LoRA at 1.0):** a small time tax. None of its six cells reloaded the text encoder: 36.6-46.2 s, mean 42.03 s, about 1.23× B0's warm mean of 34.28 s (inside the 1.35× Q1 budget). But it visibly **lowers** quality:
  a flatter, less painterly finish and worse hands on all three characters, and it drifted the sorceress to a
  male-presenting figure once. **Park / reject for Create** (δ is negative).
- **B0 (25 steps) holds** as the Create default. No recipe change is proposed.

**Still open for #1028:**
- the GGUF, FP8 and HQv3 lanes and the fp8 text-encoder tip: none is installed, and a download needs the owner's OK;
- a batched-latent seed audition;
- VRAM peaks (only host commit was sampled);
- the owner's eye (these are agent judgements from one judge, one seed per cell per condition);
- the #739 comment with optional recipes.

Licence: Qwen-Image 2.1 and the Pruna adapter are under the Qwen Research License (non-commercial). The Fix LoRA's civitai
version carries no permission flags; read its page before any use. Nothing here is licence clearance or art acceptance.

## Files

- `runs.jsonl`: one line per cell, with the exact graph, prompt ID, `exec_s`, cached nodes and commit readings.
- `judgements.jsonl`: blind rubric records, with the key added after judging.
- `key.sealed.json`, `blind-char.jpg`, `blind-prop.jpg`: the panels as judged.
- `qwen21-log-1808-1822.txt`: the backend log window.
- `run.py`, `blind.py`, `crops2.py`: as-run scripts with local paths.
- Full PNGs stay local in the qwen21 checkout, under `output/Research/qi21-pareto-20260927/`.

## Correction (27 Sep 2026, review of PR #1216)

The first version of this README gave F0/B0 as "about 0.7-0.8" on warm cells and B0 warm as "26-46 s". Both were wrong.
Recounted from `runs.jsonl` (warm = no text-encoder reload):
- B0: 25.975, 35.530 and 41.345 s, mean 34.28 s.
- F0: 27.938, 32.378, 33.072 and 40.552 s, mean 33.49 s.
- F0/B0 = 0.98.

The 46 s cell was a Q1 cell. Q1 was also said to have "no time tax"; its warm mean is 42.03 s, about 1.23× B0. The F0 verdict (park) stands and misses the gate by more. Q1 stays parked on quality.
