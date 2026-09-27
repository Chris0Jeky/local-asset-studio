# Qwen-Image 2.1 lanes: GGUF Q4 and the smaller w4a8 text encoder — 27 September 2026 (21:55-22:37 local, paused 22:00-22:20)

Refs #1028. This run follows the seed audition in `../qi21-pareto-20260927/` (B0 holds; Pruna F0 and the Fix LoRA are
parked). It measures the two lanes that became runnable once the owner authorised downloads (27 Sep 2026): a 4-bit GGUF
diffusion model (F1 "Fast+") and Comfy-Org's smaller `qwen3vl_8b_w4a8` text encoder. The FP8 diffusion model and the FP8
text encoder are still downloading at the time of writing; they are the remaining #1028 lanes.

**Setup.**
- Backend: the isolated qwen21 backend (ComfyUI v0.37.0, port 8196), switched to explicitly through the Studio.
  ComfyUI-GGUF is pinned at city96 `6ea2651e`, as installed on 27 Sep (runtime-patches/qwen21-gguf-20260927).
- Workload: the ladder's `char` and `prop` prompts, seeds 2026092741-42, 25 steps, euler/simple, CFG 1, 1024².
- Submission: straight to ComfyUI, one POST per cell, never resubmitted (`lanes.py`).
- Order: seed audition within each condition (text unchanged). Host commit sampled every 0.5 s, with a stop at 92 %.
- The driver was stopped between cells at 22:00 for a higher-priority task. The cell it had already posted (`char-GR-41`) ran
  to completion and was recorded afterwards from `/history`. The rest resumed at 22:20 and skipped cells already done.

| Condition | Diffusion model | Text encoder |
| --- | --- | --- |
| **B0** | INT8 ConvRot (Comfy-Org) | INT8 ConvRot 8.9 GB |
| **GU** | unsloth `qwen-image-2.1-Q4_K_M.gguf` | INT8 |
| **GR** | realrebelai `Qwen-Image-2.1-Q4.gguf` | INT8 |
| **W** | INT8 | **w4a8** 6.3 GB (Comfy-Org) |
| **GW** | realrebelai Q4 GGUF | w4a8 |

The downloads are in `download-receipts-*.json`. Each was SHA-256 verified against the Hugging Face LFS oid, and the three
completed files are pinned in `models/library.json`.

## Results (from `runs.jsonl` and the backend log; one agent judge, blind, key read after judging)

| | B0 | GU | GR | W | GW |
| --- | --- | --- | --- | --- | --- |
| Loads? | yes | **no**: "This model is not currently supported - (Unknown model architecture!)" (prompts `e10f3f75`, `c84e35f0`) | yes | yes | yes |
| Sampler, 25 steps | ~16 s (1.5 it/s) | — | **~37-40 s (1.6 s/it)** | ~16 s; one cached cell ran 46 s (1.9 s/it) | ~36-48 s |
| Mean exec_s (4 cells) | 73.7 | — | 104.7 | 73.9 | 70.3 |
| Blind keeps (of 4) | 2 | — | 2 | **4** | **4** |
| Mean rubric score | 4.22 | — | 4.22 | 4.35 | 4.35 |

**Reading against the #1028 tiers:**
- **GU (unsloth Q4_K_M): parked.** ComfyUI-GGUF at `6ea2651e` (upstream `main` = HEAD on 27 Sep) cannot detect the
  Qwen-Image 2.1 architecture in this file. Support exists only in the unmerged PR city96/ComfyUI-GGUF#483. Installing
  unmerged third-party code is not covered by any approval (coordinator decision, 27 Sep), so the lane waits for upstream.
- **GR (realrebelai Q4): F1 fails on speed.** It loads and matches B0 on the blind sample: the same verdicts, and within a
  seed the pictures are near-identical to B0. But dequantising GGUF on this ROCm card makes each step about 2.5× slower
  (~1.6 s/it against ~1.5 it/s), so the job is about 1.4× slower than B0, not faster. It would only matter as a low-VRAM
  lane.
- **W (w4a8 text encoder): the most interesting result, not yet a pin.**
  - Time: the same as B0 (73.9 against 73.7 s mean). The encoder loads faster (6.0 GB against 8.9 GB).
  - Quality: 4 of 4 keep against B0's 2 of 4 on this sample. The difference is the prop: both INT8-encoder conditions drew
    pseudo-numerals or glyph marks on the compass ring despite "no text", and both w4a8 conditions drew only ticks.
  - The w4a8 encoder also changed the conditioning visibly (seed 42's eyes went from green to grey), so it is not a neutral
    swap.
  - With 2 seeds per prompt this is a lead, not a Q1 pass. It needs more seeds and the text-heavy prompts, because the
    encoder is what spells.
- **GW:** the fewest reloads (the conditioning stayed cached in 2 of 4 cells, and the diffusion model often stayed loaded),
  but the GGUF sampler cost cancels the gain (70.3 s mean). Quality is as W.
- **Residency (#1218):** with the 6 GB encoder, a cached cell skipped the diffusion-model reload (log 22:31:04). But the
  sampler then ran at 1.9 s/it, which suggests the encoder and model shared VRAM with part of the model offloaded. Keeping
  both resident is not free on 16 GB.
- Host commit peaked at 80-85 %. B0 and GR ran near 80 %; W and GW at 72-77 %.

**Remaining for #1028:**
- the FP8 diffusion model and the FP8 text encoder (downloading);
- more seeds plus the text-heavy prompts for W;
- GU after upstream ComfyUI-GGUF#483 merges;
- the owner's eye;
- the #739 comment.

Licences: Qwen-Image 2.1 and its quantisations are under the Qwen Research License (non-commercial). The realrebelai card
declares no licence of its own. Nothing here is licence clearance or art acceptance.

## Files

- `runs.jsonl`: every cell, with its graph, prompt ID, `exec_s`, cached nodes, error text and commit readings.
- `judgements.jsonl`, `key.sealed.json`, `blind-*.jpg`, `crops-*.jpg`: the blind judging and its evidence.
- `qwen21-lanes-log-tail.txt`: the last 300 backend log entries (the loads, unloads and sampler rates quoted above).
- `lanes.py`, `blind.py`, `dl.py`: as-run scripts with local paths.
- Full PNGs stay local in the qwen21 checkout, under `output/Research/qi21-lanes-20260927/`.
