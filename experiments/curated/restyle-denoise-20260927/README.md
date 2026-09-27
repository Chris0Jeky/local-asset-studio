# Restyle a picture (WAI): denoise sweep 0.6-0.95, blind — 27 September 2026

Refs #351 (the "denoise sweep beyond 0.75/0.85 (0.6, 0.95) on the shipped recipe" follow-up).

## Method

The shipped `restyle-wai` graph ran unchanged except for:

- the picture to restyle (node 11);
- its tag description (node 42 `string_a`);
- the seed (2026092761, also on the FaceDetailer);
- the denoise: **0.6, 0.75, 0.85 (shipped default) and 0.95**.

Everything else stayed at the authored defaults: Mishima Kurone 0.8, Style weight 0 (the unchanged example board picture), OpenPose ControlNet 0.9, 30 steps, CFG 4.5 and FaceDetailer.

There were two SFW sources, both original adult characters rendered earlier the same morning for the recipe thumbnails:

- `platform`: `anima-v1-base`, PNG SHA-256 prefix a3ee765d1dc1d281. A woman in a trench coat on a station platform.
- `carto`: `anima-screenshot-stack`, prefix d2a2a453995b6f3d. A cartographer with two lanterns, a compass, a pack, an arch and an observatory dome.

Both were uploaded to ComfyUI `input/` as `lab0927-src-*.png`. I submitted straight to ComfyUI on the primary (06:43 local; the last run finished at 07:04:21 per `runs.jsonl`) with `.runtime/lab-0927/comfy_run.py`.

I judged the eight outputs blind with `docs/quality/JUDGING-RUBRIC.md`: shuffled per source, with every judgement written before reading `key.sealed.json`. `control` means how much of the source was kept (layout, pose, costume, props), graded under R9. The light-novel recolouring is the recipe's purpose, so a change of palette was not held against `control`. The source and all four denoise levels are side by side in `sheet.jpg`.

## Results (revealed after judging)

| Denoise | platform | carto |
| --- | --- | --- |
| 0.60 | keep, control 4 (train and sun added; canopy, pose and coat kept) | keep, control 4 (closest: arch, dome, both lanterns, compass, pack, dusk colour) |
| 0.75 | keep, control 4 (least pastel) | keep, control 4 (all props kept, lighting turned to day) |
| 0.85 (default) | fixable, control 3 (platform redrawn wider, canopy framing partly lost) | fixable, control 3 (compass missing, arch reduced) |
| 0.95 | fixable, control 3 (canopy replaced by an open platform and a train) | fixable, control 3 (second lantern and compass gone, arch lost) |

Style (light-novel finish) scored 4-5 at every level; 0.60 did not look under-restyled. The judge reported clean faces at all levels, but no face or hand crop was recorded (see Evidence limits), so that statement cannot be audited. Each job took 107.4-198.1 s `exec_s` (108.5-201.6 s wall), including FaceDetailer. Host-commit peaks were 79.3-80.3 % on six runs, 81.5 % on `carto-d85` and 85.3 % on `carto-d95` (`runs.jsonl`). That is slower than the 86-93 s recorded on 14 September. The IP-Adapter + ControlNet graph did not crash (#89) in these eight runs; free RAM was not recorded in these receipts.

## Evidence limits

These judgements do not meet the rubric's crop-evidence requirement (`docs/quality/JUDGING-RUBRIC.md`, "How to look" and "The verdict"):

- No record lists a face or hand crop, though the rubric asks for every face and hand to be cropped.
- Four of the eight name only a whole-frame comparison with the source: platform-A/d95, platform-C/d85, carto-A/d75 and carto-D/d60.
- The other four give one crop each: platform-B/d60 and platform-D/d75 `0,300-300,900`; carto-B/d95 `640,500-1040,1000`; carto-C/d85 `380,500-700,800`.

The records are left as written, not back-filled. The regions actually inspected were not logged, and inventing them would be worse than the gap. Weigh them accordingly:

- The `anatomy` scores and the "clean faces" statement are unaudited.
- The `control` findings (which props and framing survive each denoise) are whole-frame comparisons, readable in `sheet.jpg`, but not crop-verified.
- A re-judge with recorded crops is needed before these verdicts carry rubric weight.

## Reading

On both sources, **0.75 kept the named props and layout** that 0.85 dropped, with no visible loss of the restyle. The recipe already ships 0.75 as the variant "Keep more of the picture". This is a proposal to make 0.75 the default, not a change. The evidence is two sources, one seed and whole-frame judgements without recorded crops. The look is the owner's open q-27, and the Klein route (`restyle-klein`) remains the stronger keeper according to the #351 pre-review. The three-picture board and the Nova variant are still untested.

## Status

These results are generated and agent-judged only; none of it is art acceptance. Licences are not cleared: WAI's creator terms are unresolved, and the Mishima LoRA carries civitai flags (see `models/library.json`). The pictures stay local under ComfyUI `output/Research/lab-20260927/restyle-denoise/`.

## Second seed (lab 2) — 27 September 2026 (08:29-08:33 local)

Seed 2026092762 (on the KSampler and the FaceDetailer) at 0.75 and 0.85 only, with the same graphs and sources and no other change
(`seed2-lab2/graph-*.json`). The four cells ran straight to ComfyUI on the primary, serially: `platform-d75` `5e206d1b` 83.3 s,
`platform-d85` `c72f866d` 52.3 s, `carto-d75` `4cb2e6f3` 50.9 s and `carto-d85` `a84e184a` 44.6 s `exec_s`, with host commit peaking at 78-81 %
(`seed2-lab2/runs.json`). They were judged blind as source + A/B per picture before `seed2-lab2/key.sealed.json` was read. This time the face, hand and
prop crops are recorded in `seed2-lab2/judgements.jsonl`.

| Denoise | platform | carto |
| --- | --- | --- |
| 0.75 | keep, control 4 (canopy, coat, hands in pockets, boots kept; a train added) | fixable, control 3 (arch lost; **compass kept**, moved from the waist onto the pack) |
| 0.85 | keep, control 4 (same keeps; near tie with 0.75) | fixable, control 3 (arch lost; **compass dropped to the ground**) |

Faces were clean and hands readable at both levels (crops listed per record). Seed 2 therefore partly replicates seed 1. On
platform, 0.85 did not lose the canopy this time, and the two levels tie. On carto, 0.75 again kept a named prop that 0.85
dropped. Across 2 sources × 2 seeds, **0.75 kept more of the picture in 3 of 4 comparisons and tied in 1, never worse**, with no
loss of the light-novel finish. The proposal to make 0.75 the default stands, a little firmer. It is still one agent judge and
no owner review; the owner's q-27 decides the look.
