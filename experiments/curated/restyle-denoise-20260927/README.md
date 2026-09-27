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

Both were uploaded to ComfyUI `input/` as `lab0927-src-*.png`. I submitted straight to ComfyUI on the primary (06:43-07:00 local) with `.runtime/lab-0927/comfy_run.py`.

I judged the eight outputs blind with `docs/quality/JUDGING-RUBRIC.md`: shuffled per source, with every judgement written before reading `key.sealed.json`. `control` means how much of the source was kept (layout, pose, costume, props), graded under R9. The light-novel recolouring is the recipe's purpose, so a change of palette was not held against `control`. The source and all four denoise levels are side by side in `sheet.jpg`.

## Results (revealed after judging)

| Denoise | platform | carto |
| --- | --- | --- |
| 0.60 | keep, control 4 (train and sun added; canopy, pose and coat kept) | keep, control 4 (closest: arch, dome, both lanterns, compass, pack, dusk colour) |
| 0.75 | keep, control 4 (least pastel) | keep, control 4 (all props kept, lighting turned to day) |
| 0.85 (default) | fixable, control 3 (platform redrawn wider, canopy framing partly lost) | fixable, control 3 (compass missing, arch reduced) |
| 0.95 | fixable, control 3 (canopy replaced by an open platform and a train) | fixable, control 3 (second lantern and compass gone, arch lost) |

Style (light-novel finish) scored 4-5 at every level; 0.60 did not look under-restyled. Faces were clean at all levels (face crops checked). Each job took 107-198 s, including FaceDetailer, at 79-80 % host commit. That is slower than the 86-93 s recorded on 14 September. The IP-Adapter + ControlNet graph did not crash (#89) with about 9 GB of free RAM.

## Reading

On both sources, **0.75 kept the named props and layout** that 0.85 dropped, with no visible loss of the restyle. The recipe already ships 0.75 as the variant "Keep more of the picture". This is a proposal to make 0.75 the default, not a change. The evidence is two sources and one seed. The look is the owner's open q-27, and the Klein route (`restyle-klein`) remains the stronger keeper according to the #351 pre-review. The three-picture board and the Nova variant are still untested.

## Status

These results are generated and agent-judged only; none of it is art acceptance. Licences are not cleared: WAI's creator terms are unresolved, and the Mishima LoRA carries civitai flags (see `models/library.json`). The pictures stay local under ComfyUI `output/Research/lab-20260927/restyle-denoise/`.
