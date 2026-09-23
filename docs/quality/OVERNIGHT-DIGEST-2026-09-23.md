# Overnight digest, 23 September 2026

One page for the owner. It adds nothing new: every line points to the PR or issue that holds the evidence.
"Agent-judged" never means accepted, and nothing here is a licence claim.

## 1. What shipped (presets and runtime)

- **Qwen-Image 2.1** runs on its own ComfyUI v0.37 backend: recipes, pins and launcher (#858). The recipes were verified
  through the Studio after the first live backend switch (#876). The three proofs were judged: text-to-image keep, RGBA
  fixable because of alpha dust, edit keep (#877; issue #878).
- **Krea 2 GGUF presets** with the text encoder on the CPU (#873): 77–101 s per prompt against 175–544 s for fp8, a
  blind tie. Proved through the Studio: the atelier stack takes 173 s against 828 s (#880).
- **`krea-refine` default denoise lowered from 0.35 to 0.25** (#886).
- **`anime-masked-repair`** now defaults to a feathered mask at denoise 0.6 (#881). Its Studio proof gave five digits
  and no seam, and the preset is verified (#885).
- **Backend switch fixes:**
  - an uncertain job whose tracking stopped no longer blocks switches (#863);
  - a probe timeout with nothing listening now counts as offline (#870).
- **Reserve default:** the primary keeps `--reserve-vram 0.6`, and a measured reserve is opt-in (#854). #845's measured
  default had made Krea 2 2.7× slower per step (95 s against 35.4 s).
- **Local-only media moves:**
  - the Combine research sheets built on student-canon fan pictures (#860, your decision);
  - the Style+Pose sheets holding S49 (#865).
- **Not merged:** tiled decode (#888, on HOLD for you) and `zimage-fast` (#893, open, not yet run in the Studio).

## 2. Findings, with numbers

- **Moving the text encoder to the CPU cures the memory spill.** Krea: the numbers above (#873). Z-Image fp8 with the
  CPU encoder takes 37–76 s per image, against 532 s with the encoder on the GPU and 308 s for the shipped bf16. The
  blind judging was a tie, with 9 keeps (#893).
- **Qwen-Image 2.1, the night's first spill cure:** the launcher's 3 GiB reserve took the 25-step text-to-image from
  686.6 s to 52.9 s. At 8 steps that is 0.68–1.0 s/step, against 12.5–17.7 s/step (#858, #876).
- **krea-refine on GGUF with the CPU encoder:** 84 s for the first fox job (38 s of it CPU encoding), then 26–28 s each
  with cached text, against 338–373 s on fp8. Blind tie at 0.25 (2 keep / 1 reject each, the same seed-83 fox head on a
  post), 3 seeds, no preset yet (lab evidence, PR to follow).
- **SDXL tiled decode at 512:** a median 1.31 s against 2.35 s, with no spill on any case (the shipped decode spilled
  2.3 GB on 2 of 7). A blind tie on quality (#868, #867).
- **Combine on an adult original pair:** the drawn skeleton is keep ×3 with five-fingered hands; Copy Pose is keep, keep,
  fixable; depth loses the face on 2 of 3 seeds, a seed effect rather than scale (#875, #879, #883).
- **Klein restyle:**
  - naming the true colours keeps hair and eyes on 3 of 3 (the shipped wording on 0 of 3 for the lab, 1 of 3 for the
    second judge);
  - naming the stocking gives a clean stocking foot on 3 of 3, and "bare feet" gives toes on 3 of 3, one with a band
    over them (#883, #884).
- **Detector hand fix (`anime-hand`)** at 0.4 or 0.6: on CSTati nothing was detected (the output is pixel-identical);
  on noob5 it repainted the wrong hand; on noob4 six digits stayed six; on Yume 0.6 gave fingers with veiny shading, a
  keep to one judge and off-style to the other (#890, #892). Use `anime-masked-repair` for hands instead (#885).
- **Style+Pose** (#890, #891):
  - At style weight 0.7, all 18 were rejects for burned colour: 17–31 % of pixels above saturation 200, against 2.7 % in
    the style board.
  - Pose strength 0.9–1.0 holds a raised arm on 2 of 3 seeds, and 0.7 loses it.
  - Weight 0.45 or 0.3 removes the burn on 6 of 6, but seed 71 still misses the arm (#893).
- **LoRA retest (q-32):** every candidate ties its control, and none earns a default (#875, #879).
- **Qwen RGBA:** alpha dust around the cut-out breaks auto-crop and atlas packing, so the output needs a cleanup step
  (#877, issue #878).
- **The Krea atelier stack paints `@NJSW33T` into the picture** wherever the trigger sits in the prompt: at the start
  2/2, at the end 2/2, with no trigger 0/2 (#893).

## 3. How far to trust agent judging

**Against you** (#861): two blind agent judges matched your verdicts on 11 and 12 of 15 pictures. A judge that always
said "fixable" would have matched 13. Their rankings correlated with your tiers at only 0.50 and 0.29 (Spearman). Both
picked Anima look A where you picked B. They find named defects well (the six fingers, the fused foxes); they do not rank
looks.

**Against each other** (lab judge against review judge, picture verdicts):

| Experiment | Agree | | Experiment | Agree |
| --- | --- | --- | --- | --- |
| VAE decode (#867) | 5/7 subjects | | Klein restyle (#884) | 8/9 |
| Krea GGUF (#874) | 15/15 | | Krea refine foxes (#889) | 3/6 |
| Combine (#879) | 12/12 | | Style+Pose (#891) | 18/18 |
| Hand inpaint (#882) | 10/18 | | Hand fix (#892) | 2/12; 10/12 after the R8b rescore |

The low scores are all correction passes. The judges saw the same things but scored them differently, and rules R8–R8b
now settle how.

**The rules** ([JUDGING-RUBRIC.md](JUDGING-RUBRIC.md)):

| Rule | What it says | PR |
| --- | --- | --- |
| R1 | the criterion of a named defect that needs fixing scores at most 3 | #861 |
| R2 | a missing or duplicated named prop caps `adherence` at 3 | #861 |
| R3 | one extra finger on a readable hand is `anatomy` 3 | #861 |
| R4 | a small edge signature is `technical` 4, fixed by a crop | #861 |
| R5 | faces are faces, animals included: a featureless face scores at most 3 | #861 |
| R6 | appeal is not scored; never choose between clean looks | #861 |
| R7 | proposed, not adopted: a record whose fix is needed cannot be `keep` | #871 |
| R8 | correction passes: `adherence` = the defect was fixed, `control` = the rest was kept | #882 |
| R8a | a pass that removes, merges or replaces part of the subject: `control` 2, reject | #891 |
| R8b | a pass that leaves the defect untouched: `adherence` 2, reject | #892 |
| R9 | `control` for a pose, depth or reference input is graded 1–5, never 2-or-5 | #892 |

## 4. Waiting for you

- **#888 (HOLD):** tiled decode in the six SDXL presets. Each needs a Studio proof right after merge.
- **#893:** the `zimage-fast` preset and its fp8 pin. It still needs a Studio proof. The `@NJSW33T` card advice is your
  call.
- **q-25, Style+Pose sheets:** keep the route? And WAI or YumeFlux as the default checkpoint (a tie).
  See [pre-reviews/q-25.md](pre-reviews/q-25.md).
- **q-27, Restyle:** both defects are fixed by wording (#883); bare foot or stocking is your look choice.
  See [pre-reviews/q-27.md](pre-reviews/q-27.md).
- **q-28, depth Combine:** depth loses faces on 2 of 3 seeds. Should Combine lead with the skeleton or Copy Pose?
  See [pre-reviews/q-28.md](pre-reviews/q-28.md) and #879.
- **q-30, fantasy pack batch:** the portrait and full body are keeps. The detail-fix pass and the depth Combine are
  rejects, and the replace renders are keeps. See [pre-reviews/q-30.md](pre-reviews/q-30.md).
- **q-32, LoRA hot path:** every candidate ties its control. See [pre-reviews/q-32.md](pre-reviews/q-32.md).
- **Klein restyle default:** switch to the stocking wording? (#883, #884)
- **Still open in `HUMAN_TODO.md`:**
  - q-31 (a policy choice, not judged tonight);
  - q-7 (your pass over the UX wave);
  - the three adaptive-Studio choices.

## 5. What was not verified

- Every experiment used 1–3 seeds and 1–4 sources. A tie is a tie, not a ranking.
- There are no Studio proofs yet for `zimage-fast` (#893) or the tiled-decode presets (#888).
- The style-weight fix rests on 6 jobs, and the trigger test on 2 seeds (#893). Neither has a second judge yet.
- The detector hand route was tested with one detector model and threshold only (#890).
- Nothing is art-accepted or licence-cleared. Every verdict here is agent-judged.
