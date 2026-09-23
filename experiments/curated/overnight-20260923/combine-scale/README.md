# Depth Combine face loss: not a portrait-scale effect — 23 September 2026 (overnight lab)

**Hypothesis** (from `../combine-adult/`, PR #875). `combine-klein-9b-depth` drew a blank skin-oval face on seed 2026092341 and a
dark, featureless face on seed 2026092343 when the character picture was the pack's three-quarter **portrait**. If the gap in
scale between a portrait and a full-body target is the cause, a **full-body** character picture should keep the face.

**Method.** `combine_scale.py run`, 05:26-05:31 local: 3 Studio jobs, `combine-klein-9b-depth` at the default cut. Everything
matched the combine-adult depth runs:
- the same pose picture (`b72d60be…_adult-stance-pose.png`);
- the same wording fills;
- the same seeds 2026092341-43;
- the only change is the character picture: the pack's full-body render `Studio/Anima-v1-Baseline_00005_.png` (the same adult
  traveller, lantern at her side), staged as `5d0f00dd…_adult-traveller-fullbody.png`.

Judged open, with face crops at full resolution (`judgements.jsonl`). Job and prompt IDs are in `results.json`.

## Result

| seed | portrait as the character (combine-adult) | full body as the character (this run) |
| --- | --- | --- |
| 2026092341 | blank skin-oval face, grey hands (reject) | **blank skin-oval face, grey glove-like hands (reject)** |
| 2026092342 | face kept (keep) | face kept (keep) |
| 2026092343 | dark skin, featureless face (reject) | **dark skin, featureless face (reject)** |

**The hypothesis is falsified.** The same two seeds lose the face in the same way whichever character picture is used. Only the
coat length changed: the full-body picture kept the long coat. The failure follows the seed together with the depth map, not the
scale of the character picture. A plausible cause is that the depth map of the pose picture's face region (a smooth, closed-eye
face) is followed literally on some seeds. That is untested. The practical rule for now: audition three seeds on the depth
route and reject faceless results. The drawn-skeleton route kept the face 3/3 on the same pair (`../combine-adult/`).

## Not verified

- One pose picture. A pose picture whose face has open eyes and more relief might behave differently. That is the next test.
- Three seeds.
- No art acceptance. FLUX.2 Klein 9B is non-commercial per its card.
