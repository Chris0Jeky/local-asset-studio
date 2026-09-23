# Klein restyle of the throne witch: naming the colours and the foot — 23 September 2026 (overnight lab)

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

Seeds 2026091401 (the shipped seed), 2026092351 and 2026092352. **Only partly blind.**
- `seal` shuffled the three wordings of each seed, and all nine records were written under their letters (`judgements.jsonl`,
  `blind: true`). Nothing records when the key was read, beyond my own sequence (judgements first, then the key); the nine records
  were written in one batch within a second.
- The shuffle did not hide much. The shipped wording drew letter A on all three seeds, and the hair colour it produces reveals the
  wording anyway. So the colour scores are effectively open, and only the foot readings had a real blind element.
- Face, eye and raised-foot crops were taken at full resolution.

## Results (unblinded)

| wording | hair and eye colour kept (3 seeds) | raised foot | verdicts | s per job |
| --- | --- | --- | --- | --- |
| `shipped` | **0 / 3**: near-black or brown-purple hair; a violet eye on seed 01 | a toe-less foot on 01 (a wrapped stocking tip) and 02 (wrapped in a gold band), both on a bare leg; toes with a gold band on 52 | fixable ×3 | 16-36 (36 includes the model load) |
| `colours-barefoot` | **3 / 3**: purple or lavender hair, blue eyes | a bare foot with toes on 3/3 (a gold sandal band on 52) | keep ×3 | 18 |
| `colours-stocking` | **3 / 3** | the stocking kept with a proper stocking foot on 3/3, as in the source | keep ×3 | 16-18 |

- **Both treated wordings kept the colours, 3/3; the shipped one lost them, 3/3.** The shipped description is the source's
  prompt, which disagrees with its pixels. The result is consistent with the q-27 hypothesis (Klein follows the words), but it
  is an association, not a proven cause: both arms changed the colour words and added footwear words at once.
- **The shipped wording never mentions the legs or feet.** The restyle removed the source's stocking but kept its toe-less
  shape on 2 of 3 seeds. With "bare feet" the foot has toes (3/3). Describing the stocking that is really there keeps the
  stocking and gives a correct stocking foot (3/3). Which one to prefer is a look choice for the owner (R6): a bare foot, or the
  source's stocking kept.
- **The colour and foot phrases changed together**, so this run cannot credit the foot fix to the foot phrase alone: naming the
  true colours may also have steered the model back towards the source. The next step is a split test on the same seeds:
  colours only, foot only, and both.
- The composition, pose, wink, hat, robe and throne were kept by every wording.

## Next step (not done here)

The Studio fills `{source}` from the source's own prompt. A better default would name the colours seen in the picture. One way
is to ask the owner to confirm the colours once per source. Another is to derive them from the picture, e.g. through a
captioner; that needs a design decision and is not attempted here. For now: when a restyle drifts, type the true colours and
the footwear into the source description.

## Not verified

- One source picture and three seeds.
- The split test was not run. `klein_restyle.py split` (colours only and foot only, the same three seeds, records to `split/`)
  was written on 23 September 2026, but the lab paused for the owner's wrap-up before its first job, and no job was submitted.
  The foot fix is still confounded with the colour wording.
- The gold sandal band on seed 52 is unexplained (it appears with every wording).
- No art acceptance. q-27 stays the owner's. FLUX.2 Klein 4B is Apache-2.0.
