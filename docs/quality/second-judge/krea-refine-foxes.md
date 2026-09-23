# Second judge: krea-refine on the fox shrine, denoise 0.25 against 0.35 (23 September 2026)

This is an independent second judgement of the lab's `krea-refine-foxes` experiment (#886). The owner said the style-lab fox
shrine (`Studio/krea-style-lab_00001_.png`) "loses detail, the fox faces are morphed". The lab ran the Studio's `krea-refine`
preset on it with the shrine's own prompt, at denoise 0.25 and 0.35, three seeds each (2026092381–83; Studio jobs
`36e5d833`, `0cba57ec`, `0887896e`, `9602e836`, `36537036`, `f5427eb8`).

**How it was judged.** The review agent (Claude Opus 5.5) judged the six refines blind:

- under its own shuffle, with metadata stripped;
- by counting the foxes in the whole frame and at 2.5–4× crops of each fox, against the source;
- under rule R8 for correction passes, as the coordinator set it for this experiment: `adherence` means the fox faces were
  fixed, and `control` means all four foxes, the composition and the style were kept;
- with denoise and seed read from its sealed key only after the records were written, and before any lab record was read.

The records are in [krea-refine-foxes.judgements.jsonl](krea-refine-foxes.judgements.jsonl). No images are committed.

In the source, two of the four faces are the problem:

- the step fox's face is lost in its chest;
- the standing fox's face is a faint sketch.

## Results

| Seed | 0.25 | 0.35 |
| --- | --- | --- |
| …81 | **keep**: four foxes, all faces clear | reject: two foxes; a floor lantern replaces the left fox |
| …82 | **keep**: four foxes, all faces clear | fixable: four foxes, plus a translucent ghost double of the standing fox |
| …83 | reject: the standing fox is now a fox head on a red cord post, with no body and an orange ball beside it (crop 520,470–680,610) | reject: three foxes; the standing fox is gone |

- **Faces.** Every fox that survives, at either strength, has a readable face: closed eyes, a nose and a muzzle. The refine
  does fix the faces.
- **Count.** 0.25 keeps four whole foxes on 2 of 3 seeds, and 0.35 on 1 of 3, where it adds a ghost.
- **The rest of the frame.** It is redrawn at both strengths, with the composition and the watercolour finish kept. Clouds,
  petals and the far valley change: the mean pixel change is 17.5 grey levels at 0.25 and 21.7 at 0.35.
- **Means.** 0.25 averages 4.22 against 3.78 for 0.35. That is beyond the 0.3 tie margin, and 0.25 wins or ties on every
  seed.

**Answer to the lab's claim.** Confirmed in direction, qualified in count:

- 0.25 is the better default. It gives the only keeps (2 of 3), and 0.35 recomposes the fox group on every seed.
- The claim that 0.25 keeps all four foxes on 3 of 3 depends on counting the seed …83 figure as a fox. The lab read it as
  "a pale fox with oversized flat ears and a red cloth added below it". This judge re-examined it once after unblinding,
  with contrast raised 3× on 490,440–690,700. The source's standing fox has a white body outlined down to the rail. In
  the refine there is no body outline under the head, only the red cord running down to the steps. This judge's blind
  record stands: three foxes and an ornament.
- So a refine at 0.25 still needs a look at every output: one seed in three lost a fox's body.

## Agreement with the lab's judge

The lab's records are in its PR #886 (`experiments/curated/overnight-20260923/krea-refine-foxes/judgements.jsonl` there).
Merge that first so this comparison can be traced in the tree.

| Measure | Result |
| --- | --- |
| Which denoise is better | agree: 0.25 (lab means 4.22 against 3.67; this judge 4.22 against 3.78) |
| Keeps | agree: seeds …81 and …82 at 0.25, and none at 0.35 |
| Picture verdicts | **3 of 6** agree |
| Criteria exactly equal | 26 of 36 |
| … style | 6 of 6 |
| … anatomy, technical, composition | 5 of 6 each |
| … control | 3 of 6 |
| … adherence | 2 of 6 |

The three verdict differences:

| Picture | Lab | This judge | Cause |
| --- | --- | --- | --- |
| 0.25, seed …83 | fixable (control 4) | reject (control 2) | a fox with a scarf, or a fox head on a cord (see above) |
| 0.35, seed …82 | reject (anatomy 2) | fixable (anatomy 3) | both named the same ghost double; they differ on its severity |
| 0.35, seed …83 | fixable (control 3) | reject (control 2) | how much one lost fox costs; the lab gave 2 for two lost foxes |

**Where the scoring split.** The low adherence agreement comes from where each judge put a lost fox:

- The lab's README defines `adherence` as "the faces were fixed without losing foxes", so a lost fox cost adherence as
  well as control.
- This judge followed the coordinator's split: a lost fox costs `control` only. The adherence of 4 on those pictures
  records that the faces of the foxes that remain are clear, while the lost foxes' faces were removed, not fixed.

Both readings give the same configuration answer. The rubric does not yet say whether a correction pass that removes
part of the subject is "fixable", with "re-run at a lower strength" as the fix, or a reject. This judge gives any lost
subject `control` 2, which makes it a reject. The owner or the coordinator may want to settle that in R8.

The lab also judged the source three times, each time fixable with anatomy 3 for the soft, smeared faces. This judge wrote
no source record, but read the source the same way.

Across the night's lab-against-review comparisons:

| Experiment | Picture verdicts agreeing |
| --- | --- |
| VAE decode | 5 of 7 subjects |
| Krea GGUF | 15 of 15 |
| Combine | 12 of 12 |
| Hand inpaint | 10 of 18 |
| Restyle | 8 of 9 |
| Krea refine foxes | 3 of 6 |

The two lowest are both correction passes, and in both the split is in how the judges scored the pass, not in what they saw.

## Not verified

- One source picture, three seeds per strength.
- Only the fox group was judged in detail. The background was checked at the whole-frame level and by pixel statistics.
- Nothing here is art acceptance.
