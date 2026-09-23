# Krea 2 Turbo: Q5_K_M GGUF with the text encoder on the CPU — 23 September 2026 (overnight lab)

**Question.** Is the Krea 2 Turbo Q5_K_M GGUF (8.87 GB) faster than the shipped fp8 build (13.1 GB) on this 16 GB card, and is
its output indistinguishable from fp8's?

**Answer in one line.** Yes, but only when the Krea text encoder is not resident in VRAM next to the diffusion model. With
`CLIPLoader` `device: cpu`, the GGUF samples at **2.37-2.45 s/step** against fp8's 19-66 s/step. A new prompt takes **77-101 s**
end to end, and a repeat of the same text takes **38 s**, against **175-544 s** for fp8. Blind quality was a tie on three suite
seeds, and the retro-anime LoRA behaves the same on GGUF.

## Method

All runs went straight to the primary ComfyUI 0.35.0 (PID 56556, `--reserve-vram 0.6 --disable-pinned-memory`) between 03:32
and 04:32 local. The script is `ab_krea.py`, and the graphs are in `graphs/`. The base graph is the shipped `krea-portrait`:
768x1152, 8 steps, euler/simple, cfg 1. The retro-anime LoRA is pruned except in the LoRA case. The only changes are the
diffusion loader (`UnetLoaderGGUF` with `krea2_turbo-Q5_K_M.gguf` in place of `UNETLoader` with `krea2_turbo_fp8_scaled`) and
the text encoder device (`CLIPLoader` `device: cpu`).

Prompts are the showcase suite's prose dialect (`../suite.py`) with its fixed seeds. Node and step times come from ComfyUI's
websocket events for our own client. GPU memory comes from the process timeline (1.5 s), and host commit from
`GlobalMemoryStatusEx` (1.5 s).

The GGUF is `vantagewithai/Krea-2-Turbo-GGUF` at revision `390847e2`: 8,871,195,936 bytes, SHA-256 `dcba1696…061dd`, which matches
the Hugging Face LFS oid. The model card declares `krea-2-community-license`, and its base model is `krea/Krea-2-Turbo`.

Images of famous characters and the fanservice cases are not in Git. They are in ComfyUI
`output/Research/overnight-20260923/krea-gguf/`, with a local `index.html`.

## Results: speed

| configuration | runs | text encode s | s/step (steady) | whole prompt s | peak shared MB while sampling |
| --- | --- | --- | --- | --- | --- |
| fp8, GPU encoder (shipped graph, LoRA pruned) | portrait, action, hands | 4-7 | **54.0, 38.6, 66.2** | **459.7, 343.9, 543.5** | 819-1537 (spill) |
| fp8, GPU encoder, census 03:14 (with the retro LoRA) | 1 | – | 16.9-19.4 | 209.3 | 274 |
| fp8, text encoder never loaded (probe: models unloaded, cached conditioning) | 1 | 0 | 20.7 | 175.2 | 79 |
| fp8, CPU encoder | 1 | 53.9 | 19.3 | 236.4 | 79 |
| **GGUF, GPU encoder** (normal graph) | 1 | – | **112** | **919.9** | **1899** (3.7 GB of the encoder stayed resident) |
| GGUF, text encoder never loaded (probe) | 1 | 0 | **2.37** | **37.6** | 79 |
| **GGUF, CPU encoder, new text** | action, duo, environment, pinup-swim, glamour, hands, and portrait again (a planned cached rerun that re-encoded) | **53-77** | **2.37-2.45** | **76.9-101.3** | 79 |
| GGUF, CPU encoder, same text as the previous prompt | portrait | 0 (cached) | 2.39 | **38.0** | 79 |
| GGUF, CPU encoder, retro-anime LoRA 1.0 (the shipped `krea-portrait` recipe) | 1 | 62.9 | 3.53 | 100.1 | 79 |

- **Why the GGUF needs the CPU encoder.** On this card, sampling slows down whenever anything spills into WDDM shared memory:
  - The Krea text encoder (`qwen3vl_4b_fp8_scaled`, 5 GB) plus the 8.8 GB GGUF plus activations overfill the card.
  - ComfyUI kept 3.7 GB of the encoder resident because its own estimate said the rest would fit. The first GGUF prompt then
    ran at 112 s/step.
  - Loading the text encoder on the GPU also slows fp8 afterwards: 38-66 s/step after an encoder load, against 19-21 s/step
    with the encoder never loaded.
  - With `device: cpu`, the encoder never touches VRAM, and the GGUF's 8.8 GB runs clean every time.
- **Where the time goes on GGUF with the CPU encoder.** The CPU encode dominates, at 53-77 s per new prompt. It is skipped when
  consecutive prompts share the text (the Studio's "3-seed audition" shape). Sampling is 19 s for 8 steps and decode about 5 s.
- **fp8 got slower through the night.** It ran 16.9 s/step at 03:14 and 66 s/step at 04:24 with the same graph. Over that time
  dwm.exe grew from 0.97 to 1.62 GB of VRAM. A 12.5 GB model has almost no headroom on this card, while the 8.8 GB GGUF does.
- **Host memory.** Commit was 57.6-62.9 % before the GGUF + CPU-encoder runs (62.9 % before the first, which followed the fp8
  runs) and peaked at **62.4-62.8 %** during the seven suite runs, with 10.3-12.8 GB of RAM free; the retro-LoRA run peaked at
  **70.1 %** (from 58.1 %). The fp8 runs peaked at 69-78 %. On the ~77 GB commit limit these runs stayed clear of the ceiling
  documented in the host-memory note, though above its ~55 % starting guidance for Qwen/FLUX-class jobs.

## Results: quality (blind, rubric R1-R6)

`seal` shuffled every (case, seed) that exists in more than one configuration. Ten judgements were written before the key was
read; the portrait seed 2026092302 pair was not blind, because it had been viewed with its labels before sealing.

| group | configurations (unblinded) | mean score | verdicts |
| --- | --- | --- | --- |
| action, seed 02 | GGUF + CPU encoder / fp8 | 4.4 / 4.4 | keep / keep |
| hands, seed 07 | GGUF + CPU encoder / fp8 | 4.8 / 4.8 | keep / keep |
| portrait, seed 01 | GGUF + CPU encoder / GGUF / fp8 + CPU encoder / fp8 | 4.8 each | keep ×4 |
| portrait, seed 02 (not blind) | GGUF / fp8, both with no encoder | 4.8 / 4.8 | keep / keep |

**A tie on every group.** The pictures at the same seed share composition, pose and palette, and differ only in hair strands,
the blade length and small lighting details. No group had a defect in one configuration that the other lacked. The worst
defects are the same in each pair:
- the skirt-flare framing in the action case;
- a plastic-looking highlight on Makima's shirt;
- illegible book text.

The retro-anime LoRA on GGUF + CPU encoder reproduced the census's fp8 output of the same recipe and seed: the same
composition, pose, palette and 1980s cel look.

Single-configuration showcase pictures (open judgements, GGUF + CPU encoder):
- duo, environment, pinup-swim and glamour were all `keep`;
- Krea drew the Raiden Shogun's naginata as briefed (WAI drew a katana);
- Aerith holds the flowers as the prose asks;
- the environment has every briefed element, crowds included.

## Mechanism check (for a preset change)

- `CLIPLoader` in this ComfyUI 0.35 has the optional input `device: ["default", "cpu"]` (`/object_info/CLIPLoader`). The shipped
  Krea graphs (`krea-portrait`, `krea-environment`, `krea-anime-atelier`, `krea-style-lab`, `krea-refine`) all encode through
  `CLIPLoader` node `2` (`type: krea2`, `device: default`). `UnetLoaderGGUF` (ComfyUI-GGUF) lists `krea2_turbo-Q5_K_M.gguf`.
- When it loads this GGUF, ComfyUI logs `unet unexpected: ['last.down.weight', 'last.up.weight']`. The outputs are
  indistinguishable from fp8, so the two unused tensors do not matter here; this is recorded, not explained.

## Verdict and next step

- **Speed.** Same-case pairs with a fresh text encode on both sides: action 343.9 s (fp8, GPU encoder) against 97.4 s (GGUF,
  CPU encoder) = 3.5x; hands 543.5 s against 76.9 s = 7.1x. Against tonight's best fp8 run (the census, 209.3 s at 03:14) the
  GGUF's slowest new prompt (101.3 s) is 2.1x faster. With the text cached (consecutive prompts sharing it) GGUF takes 38.0 s,
  against 175.2 s for fp8 with no encoder at all (4.6x).
- **Quality.** Blind tie with fp8 on three suite seeds; the retro-LoRA case matched the fp8 census output in a labelled (not
  blind) comparison.
- **The trap.** GGUF with the encoder on the GPU is the worst configuration of all.
- **Proposal (in this PR):**
  - pin the GGUF in `models/library.json` (`krea-turbo-q5km-gguf`, pin-only like every `.gguf`);
  - add two new presets, `krea-portrait-gguf` and `krea-anime-atelier-gguf`: the same graphs with `UnetLoaderGGUF` and
    `CLIPLoader` `device: cpu`, the same bindings and variants, and `verified: false`. The fp8 presets stay as shipped;
  - prove each new preset through the Studio (once the running Studio has loaded this catalog) before it is marked verified.
- **Worth measuring later:** a GPU encoder that is explicitly unloaded before sampling (ComfyUI `--disable-smart-memory` or a
  larger `--reserve-vram`). Either could remove the CPU encode's 55-75 s, but both are global runtime flags for the coordinator.

## Not verified

- Each speed row is a single observation at tonight's VRAM state, and three blind seeds is the minimum for the claim.
- The atelier target stack (TextFusion + Niji Sweet Spot + koukouya, 15 steps) was not run on GGUF in this experiment.
- The CPU encode time depends on the CPU and on what else is running.
- The effect of the two unexpected tensors is untested.
- None of this is art acceptance or licence clearance. The Krea 2 Community License terms are recorded, not cleared.

## Update, 23 September 2026 05:14-05:26: the target stack on GGUF, and Studio proofs

The "not verified" lines above about the atelier target stack and the unproved presets are kept as written at the time; this
section supersedes them. Records: `gguf-proofs.json` (flat summary), `results.json` + `graphs/gguf-cpute-atelier-target-stack.json`
+ `timelines/` for the direct run, `proofs/` for the two Studio jobs, `prove_gguf_presets.py` for the proof script.

| run | job / prompt | settings | time | s/step | shared-memory peak | agent verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Target-stack recipe `krea-atelier-target-stack`, direct | – / `976da1a8` | 832x1248, 15 steps euler_ancestral, TextFusion 1.0 + Niji Sweet Spot 1.0 + koukouya 1.0, seed 20260912 | 173.2 s (CPU encode 76.8, sampling 86.5, decode 7.2); fp8 Studio job `7d589f47`: 827.6 s on 12 September | 4.66 | 1813 MiB (decode) | fixable: `@NJSW33T` painted as visible text; the cat has no face |
| `krea-portrait-gguf` Studio proof, authored defaults | `c6049b90` / `268f4be5` | 768x1152, 8 steps, retro-anime LoRA 1.0, seed 2026091103 | 133.3 s | 3.5 | 79 MiB (no spill) | keep: near-identical to the fp8 preset's output of the same defaults |
| `krea-anime-atelier-gguf` Studio proof, authored defaults | `29e468ca` / `6a856a23` | 768x1152, 15 steps, TextFusion + Niji Sweet Spot, seed 281715418 | 114.6 s | 3.43 | 4.35 GiB (the Studio reports 4.3 GB), within the last 6 s of the job | fixable: a faint `@NJSW33T`-style watermark on the cloak |

Both Studio proofs ran through `POST /api/jobs` on the Studio restarted to serve #873's catalog, and the presets are marked
`verified: true` with notes that say exactly the above. **Two of two Niji Sweet Spot runs on GGUF painted the trigger word into
the picture.** Hypothesis, untested: the trigger at the start of the prompt is rendered as text, helped by the TextFusion LoRA
(built for text rendering). The fp8 renders of the same recipes were not re-checked for it. Next step: a fixed-seed test of the
trigger position (start / end / omitted) with TextFusion on and off. The preset's trigger advice is unchanged until that runs.
