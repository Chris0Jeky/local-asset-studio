# Second judge: repairing the six-finger hand (23 September 2026)

This is an independent second judgement of the lab's `hand-inpaint` experiment (#881). The experiment took the NoobAI
portrait that the owner flagged for six fingers (`Studio/noob_00004_.png`). A hand-sized RGBA mask covered the raised hand
(box 12,535–181,793). The hand was then repaired six ways, at three seeds each (2026092361–63):

- `anime-masked-repair` at denoise 0.4;
- `anime-masked-repair` at denoise 0.6;
- `anime-masked-repair` at 0.6 with a feathered, 12-pixel grown mask;
- `sdxl-inpaint-fix` (Fooocus) at 0.5, 0.7 and 1.0.

**How it was judged.** The review agent (Claude Opus 5.5) judged all 18 outputs blind, under its own shuffled labels:

- It counted the digits on a 2× finger crop.
- It looked at the mask outline at 4× nearest-neighbour, where the background light streak crosses it.
- It measured a seam step: at 303 points on the outline's background stretches, it compared the jump between the pixels
  3 px inside and 3 px outside the mask, in the output against the original.
- It wrote its records before reading any lab record.

The digit count and the seam step are recorded per picture in
[hand-inpaint.judgements.jsonl](hand-inpaint.judgements.jsonl). No images are committed.

## Results by configuration

| Configuration | Five digits | Gesture and style kept | Seam at the mask edge | This judge's verdicts |
| --- | --- | --- | --- | --- |
| masked repair 0.4 | **0 / 3** (six remain) | yes, nearly unchanged | a step in the streak on 2 of 3 | 3 reject |
| masked repair 0.6 | **3 / 3** | yes (one seed curls the fingers) | **visible on 3 of 3**: a vertical cut in the light streak at x ≈ 180 | 3 fixable |
| **masked repair 0.6, feathered** | **3 / 3** | style yes; gesture kept on 2 of 3 (seed …62 curls the fingers) | **none visible on 2 of 3**; a slight streak smear on seed …62 | 2 keep, 1 fixable |
| Fooocus 0.5 | 1 / 3 | yes | small | 2 reject, 1 fixable |
| Fooocus 0.7 | about 5, but a new gesture | **no**: semi-real, a different hand | varies (one hard seam) | 3 reject |
| Fooocus 1.0 | – | **no**: a mangled hand, a second hand, or the hand gone | – | 3 reject |

Seam step, as the 90th percentile of the excess jump over the original:

| Configuration | Per seed |
| --- | --- |
| masked repair 0.6 | 4.6, 11.3, 9.6 |
| feathered 0.6 | 2.0, 3.6, 3.3 |

**Answer to the lab's claim.** Confirmed:

- The feathered masked repair at 0.6 gives five digits on 3 of 3 seeds, keeps the style (and the gesture on 2 of 3), and removes the
  seam, in this judge's reading on 2 of 3 seeds, with a slight smear on the third.
- 0.4 fixes nothing.
- Fooocus is worse at every strength.

This is the first correction route on record that actually fixes this hand. `anime-detail-fix` (`14caa4fb`) did not; see
the [quality backlog](../QUALITY-BACKLOG.md).

## Agreement with the lab's judge

| Measure | Result |
| --- | --- |
| The experiment's question, per configuration (digits fixed? seam?) | agree on all six configurations |
| Picture verdicts | **10 of 18** agree |
| Criteria exactly equal | 41 of 90 |
| … adherence | 2 of 18 |
| … style | 14 of 18 |

This is the lowest agreement of the night, and the cause is how each judge read a correction pass, not what the pictures
show:

1. **Adherence.** The lab scored adherence against the picture's prompt, where the six-finger picture still shows the
   sorceress, so 5. This judge scored it against the repair's job: fix the hand.
2. **Control.** This judge also scored `control` as "was the job done", 2 for a six-finger result. The lab left control
   empty.
3. **R3.** This judge scored the unchanged six-finger hands `anatomy 2`, which breaks rule R3. One extra finger on a
   readable hand is 3, and the lab applied that correctly. These records were blind and are left as written; with R3
   applied, the 0.4 results would be anatomy 3.
4. **Style on Fooocus 0.7.** The lab gave style 3 to its semi-realistic redraws; this judge gave 2.

Because of points 1 and 2, the same six-finger picture is "fixable" to the lab and "reject" to this judge.

**Rule R8, for correction passes.** Proposed here, adopted by the coordinator on 23 September 2026, and now in the [rubric](../JUDGING-RUBRIC.md).

- `adherence` scores whether the named defect was fixed.
- `control` scores whether everything else was kept: gesture, style and the rest of the picture.
- `anatomy` follows R3 as usual.

Under R8 a pass that leaves the defect is a reject, whatever the rest looks like. The owner may still override the
adoption.

## Not verified

- One picture, one hand, three seeds.
- Other feather widths.
- Whether the seam shows on busier backgrounds.
