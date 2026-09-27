# Qwen-Image 2.1 INT8: step-count ladder — 27 September 2026

Refs #1028 (QI-2.1 quality/speed Pareto). This is a small first B0/F0/Q1 probe using only the installed Comfy-Org INT8 weights (`qwen_image_2.1_int8_convrot` with the `qwen3vl_8b_int8_convrot` encoder). It needs no downloads.

## Method

The shipped `qwen21-t2i` graph ran on the isolated `qwen21` backend (port 8196). I submitted straight to ComfyUI with `.runtime/lab-0927/comfy_run.py`, serially. There were three prompts (an anime character, a painted scene and a game prop), each at 1024x1024, euler/simple, CFG 1, with one fixed seed per prompt. Each prompt ran at **10, 16, 25 (shipped default) and 40 steps**. A 4-step warm-up ran first so the model load did not land on a measured cell.

`cells.json` holds the exact graphs. `runs.jsonl` holds the prompt IDs, `exec_s` and host-commit readings.

I judged the twelve pictures blind with `docs/quality/JUDGING-RUBRIC.md`. The pictures were shuffled per prompt and I wrote every judgement before reading `key.sealed.json`. See `judgements.jsonl`, and `sheet.jpg` for all twelve side by side. I am one agent judge, and this was one seed per cell.

## Timing (27 Sep 2026, 05:23-05:34 local)

| Steps | Sampler time (char / scene / prop) | Whole prompt `exec_s` |
| ---: | --- | --- |
| 10 | 5-6 s at ~1.65 it/s | 22-49 s |
| 16 | 10 s; one stalled to 26 s at 1.66 s/it | 19-39 s |
| 25 | 15-16 s at ~1.58 it/s | 56-58 s |
| 40 | 25 s at 1.56 it/s; two stalled to 71-88 s at 1.8-2.2 s/it | 37-100 s |

At 1 MP the sampler costs about 0.63 s per step. The text encode, model paging and VAE decode add 20-40 s of overhead, and that overhead varies more between runs than the sampler does. Host commit sat at 77-82 % during the run, so the stalls are paging, not steps. The saving is **sampler-only**: going from 25 to 16 steps saves about 6 s of sampling, and going to 10 saves about 10 s. The recorded whole-job `exec_s` does not show a clean saving. The 25-step jobs took 55.96-58.42 s, the 16-step jobs 19.26-38.45 s and the 10-step jobs 21.91-48.54 s. Those spreads come mostly from overhead: the first cell of each prompt pays the text encode, and the paging stalls vary. One seed per cell cannot separate a whole-job saving from that noise.

## Blind verdicts (revealed after judging)

| Prompt | 10 steps | 16 steps | 25 steps | 40 steps |
| --- | --- | --- | --- | --- |
| char | fixable: murky, soft face | keep | keep | keep (same as 25) |
| prop | fixable: lumpy rim, soft needle | fixable: ring of pseudo-lettering on the dial | keep | keep |
| scene | reject | reject | reject | reject |

All four scene pictures came out **photographic**, even though the prompt said "Painted anime background". Step count did not change this. The Night Shift environment prompt used for the asset kit on the same backend did come out painted. It says "hand-painted cel anime film background art" and names a camera height. So painted scenery on QI-2.1 depends on the style wording, not on steps.

## Reading against the #1028 tiers

- **F0 by steps alone (10-16 steps)** is not net-GREAT. It saves 6-10 s of a 40-60 s job and loses visible quality at 10 steps on 2 of 3 prompts; 16 steps drew pseudo-lettering on the prop. **Park.** The Pruna distill (#934) remains the F0 candidate to test.
- **Q1 by steps (40)** is "slower, no visible win" on all three prompts. **Park.**
- **B0 (25 steps) holds.** No recipe change is proposed.

## Not covered

This probe covers one seed per cell and one agent judge, with no owner review. It includes no Pruna, GGUF, FP8 or alternative encoders, and no VRAM peak. Treat it as a first ladder rung, not the Pareto answer. The pictures are local only, under the qwen21 backend's `output/Research/lab-20260927/qi21-steps/`.

## Status

- **Generated and agent-judged only.** Nothing here is owner art acceptance.
- **Licence: not cleared.** Qwen-Image 2.1 weights are under the Qwen Research License (non-commercial, per the `qwen21-t2i` catalog note). A successful render is not licence clearance, and this study does not change that.
