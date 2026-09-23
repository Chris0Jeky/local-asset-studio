# Klein restyle of the throne witch: name the colours and the foot — 23 September 2026 (overnight lab)

**Question** (review judge, q-27 pre-review in PR #862). Every Klein restyle of `Style-Pose/Nova_00004_.png` drew the raised leg's
foot as a toe-less stocking tip, and the shipped source description ("long dark hair", taken from the source's own prompt)
turned her purple hair black and her blue eye violet. Do the true colours plus a foot phrase fix both? The owner ruled on
23 September 2026 that the throne witch is an adult original. Her images are pin-up framed, so none of them is in Git. They are in
ComfyUI `output/Restyle/Klein_00005_`-`00013_` with a local gallery.

**Method.** `klein_restyle.py run`: 9 Studio jobs (`restyle-klein`, `POST /api/jobs`), 05:17-05:20 local, each with the shipped
job's exact controls (job `db25b173`: 1040x1520, 6 steps, cfg 1, the same staged reference). Only the source description at the
end of the prompt changed:
- `shipped`: as submitted in `db25b173` ("long dark hair");
- `colours-barefoot`: "long purple hair, blue eyes", plus "bare feet" after "one knee raised";
- `colours-stocking`: the same colours, plus the stocking the source actually shows ("a beige thigh-high stocking on the raised
  leg, the other leg bare").

Seeds 2026091401 (the shipped seed), 2026092351 and 2026092352. Judged **blind**: `seal` shuffled the three wordings of each seed,
all nine records were written under their letters (`judgements.jsonl`, `blind: true`), and only then was the key read. Face,
eye and raised-foot crops were taken at full resolution.

## Results (unblinded)

| wording | hair and eye colour kept (3 seeds) | raised foot | verdicts | s per job |
| --- | --- | --- | --- | --- |
| `shipped` | **0 / 3**: near-black or brown-purple hair; a violet eye on seed 01 | toe-less stocking tip on 01 and 02 (bare leg); toes with a gold band on 52 | fixable ×3 | 16-36 (36 includes the model load) |
| `colours-barefoot` | **3 / 3**: purple or lavender hair, blue eyes | a bare foot with toes on 3/3 (a gold sandal band on 52) | keep ×3 | 18 |
| `colours-stocking` | **3 / 3** | the stocking kept with a proper stocking foot on 3/3, as in the source | keep ×3 | 16-18 |

- **Naming the colours the picture actually shows fixes the colour drift, 3/3.** The shipped description is the source's
  prompt, and the source's prompt disagrees with its pixels. That confirms the q-27 hypothesis: Klein follows the words.
- **The toe-less foot came from asking for a bare leg without a foot.** With "bare feet" the foot has toes (3/3). Describing the
  stocking that is really there keeps the stocking and gives a correct stocking foot (3/3). Both remove the defect. Which one
  to prefer is a look choice for the owner (R6): a bare foot, or the source's stocking kept.
- The composition, pose, wink, hat, robe and throne were kept by every wording.

## Next step (not done here)

The Studio fills `{source}` from the source's own prompt. A better default would name the colours seen in the picture. One way
is to ask the owner to confirm the colours once per source. Another is to derive them from the picture, e.g. through a
captioner; that needs a design decision and is not attempted here. For now: when a restyle drifts, type the true colours and
the footwear into the source description.

## Not verified

- One source picture and three seeds.
- The gold sandal band on seed 52 is unexplained (it appears with every wording).
- No art acceptance. q-27 stays the owner's. FLUX.2 Klein 4B is Apache-2.0.
