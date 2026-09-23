# Second judge: Style+Pose at a lower style weight (23 September 2026)

This is an independent second judgement of the lab's style-weight follow-up (#893) to the Style+Pose pack
([stylepose-pack.md](stylepose-pack.md)). It ran six Studio jobs, `Style-Pose/WAI_00043_.png` to `WAI_00048_.png`, all on
`style-pose-wai`:

- the same style board and the action pose;
- pose strength 0.9;
- style weight 0.3 or 0.45, against the default 0.7;
- seeds 2026092371–73.

The prompt describes a fully clothed adult original, and it was checked before viewing.

**How it was judged.** The review agent (Claude Opus 5.5) judged the six blind:

- under its own shuffle, with metadata stripped;
- with every hand cropped at 2.5×, the upper body at 0.75×, and saturation measured against the board;
- before reading any lab record.

The normal rubric applies, with R9 for `control`. The records are in
[stylepose-weight.judgements.jsonl](stylepose-weight.judgements.jsonl).

## Result: the burn is gone on 6 of 6

| Seed | weight 0.3 | weight 0.45 |
| --- | --- | --- |
| …71 | reject: the pose is ignored (a walking figure) | reject: the pose is ignored |
| …72 | keep (a V sign where the pose has an open palm) | keep |
| …73 | keep | keep |

- **Colour.** Only 2.3–12.6 % of pixels sit above HSV saturation 200. That compares with 17–31 % at weight 0.7 and 2.7 %
  in the style board.
- **Everything the prompt asked for now arrives:** the navy coat, the teal scarf, dark hair, dark legwear and brown
  lace-up boots.
- **The finish is still flat cel shading,** flatter than the painterly board: `style` 4 throughout.
- **Seed …71 ignores the action pose** at both weights, as it did at 0.7. Both weights give the same result on every
  seed.

## Agreement with the lab's judge

| Measure | Result |
| --- | --- |
| Burn gone | agree: 6 of 6 |
| Picture verdicts | 2 of 6 agree (the two keeps on seed …72) |
| … style, technical | 6 of 6 each |
| … composition | 0 of 6 (the lab gave 4, this judge 5) |

The verdict splits:

- **Seed …71, both weights.** The lab gave `control` 3, fixable. This judge gave `control` 1, reject: the walking figure
  keeps neither the raised arm nor the wide stance, which R9 scores 1, "ignored".
- **Seed …73, both weights.** The lab calls the raised hand limp or clawed, with merged fingers: `anatomy` 3, fixable.
  This judge read it as thin and a little crude: `anatomy` 4, keep. This is a severity call on the same hand, and the
  blind records stand.

**Answer to the lab's claim.** Confirmed: weight 0.45 or 0.3 removes the burn on 6 of 6. The route still needs a
picture-by-picture check, because one seed in three ignores the pose.

## Not verified

- Three seeds, one board, one pose.
- Whether 0.45 or 0.3 is the better default. They tie on this evidence.
- Nothing here is art acceptance.
