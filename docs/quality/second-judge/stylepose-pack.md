# Second judge: Style+Pose on the fantasy pack's adult original (23 September 2026)

This is an independent second judgement of the lab's `stylepose-pack` experiment (#890). The experiment re-proved
`style-pose-wai` (WAI v17, an IP-Adapter style board and an OpenPose ControlNet) on the pack's own adult original:

- **Style board:** `Studio/Anima-v1-Baseline_00004_.png`, the look-B portrait.
- **Standing pose:** `Studio/Anima-v1-Baseline_00005_.png`, the full-body render, a stride with one hand at the strap.
- **Action pose:** the combine-adult stance picture, one arm raised overhead and a wide stance.
- **Settings:** pose strength 0.7, 0.9 and 1.0, three seeds (2026092371–73), style weight at the preset default.

That gives 18 Studio jobs, `Style-Pose/WAI_00025_.png` to `WAI_00042_.png`. Both input pictures were checked to be
pixel-identical to the pack renders named above; the review judge had judged both "keep" in the
[q-30 pre-review](../pre-reviews/q-30.md). Every prompt describes a fully clothed adult original.

**How it was judged.** The lab judged these open. The review agent (Claude Opus 5.5) judged them blind:

- under its own shuffle, with metadata stripped;
- knowing each picture's pose input, since `control` has to be scored against it, but not its strength or seed;
- by looking at every frame at 0.75×, the upper body at 1×, and the hands at 2.2×;
- by measuring saturation against the style board;
- before any lab record was read.

The normal rubric applies, since this is not a correction pass. The records are in
[stylepose-pack.judgements.jsonl](stylepose-pack.judgements.jsonl). No images are committed.

## Results

**All 18 are rejects, on the finish:**

- The colours are burned: neon teal coats, glowing yellow buttons, hot orange or pink backgrounds, and coloured halos on
  the outlines.
- In every output, 17–31 % of pixels are above HSV saturation 200, against 2.7 % in the style board.
- In 11 of the 18, 11–76 % of pixels are at full brightness (HSV value above 250), mostly the saturated background.
- The flat, poster-like finish is far from the board's dark, painterly look.
- Every picture scores `style` 2 and `technical` 2.

**Pose (control)**, by seed:

| Pose | Strength | Seed …71 | Seed …72 | Seed …73 |
| --- | --- | --- | --- | --- |
| standing | 0.7 | stride only, arms down | followed | stands square, arms down |
| standing | 0.9 | followed | followed | stands square, arms down |
| standing | 1.0 | followed | followed | stands square, arms down |
| action | 0.7 | **ignored**: a walking figure | stance only, arms down | stance only, arms down |
| action | 0.9 | **ignored**: a walking figure | followed | followed |
| action | 1.0 | **ignored**: a walking figure | followed | followed |

The raised arm holds only at 0.9 and 1.0, and on 2 of 3 seeds. Seed …71 ignores the action pose at every strength, and
seed …73 ignores the standing pose's stride and hand at every strength. So on this board, the seed decides as much as
the strength does.

**Other defects:**

- **Colours asked for but not given.** Seed …73 gives red or pink hair where dark hair was asked: on all three standing
  renders and on the 0.7 action render, with a magenta streak at 1.0. Many outputs give red or maroon legs where dark trousers were asked. The boots are usually orange, red
  or navy rather than brown, and often a mismatched pair.
- **Hands.** Most of the walking figures have crude, mitten-like fists. Two have a pale-blue ghost cluster of extra
  fingers: 1.0 seed …72 (`WAI_00032_`) and 0.9 seed …72 (`WAI_00029_`). The raised hands in the action pose read
  cleanly, with five fingers.

## Agreement with the lab's judge

The lab's records and README are in its PR #890 (`experiments/curated/overnight-20260923/stylepose-pack/` there).

| Measure | Result |
| --- | --- |
| Picture verdicts | **18 of 18** agree: all rejects, on the burned finish |
| Criteria exactly equal | 67 of 108 |
| … style, technical, composition | 18 of 18 each (2, 2 and 4 throughout) |
| … anatomy | 10 of 18 (the lab gave 3 throughout; this judge gave 4 where the hands read) |
| … adherence | 3 of 18 (the lab gave 4 throughout; this judge gave 2–3 where the hair or the trouser colour was wrong) |
| … control | 0 of 18 (see below) |

**Action pose.** Both judges found the same outcome: the raised arm is lost at 0.7 and held at 0.9 and 1.0 on 2 of
3 seeds. They scored it differently:

- The lab gave control 2 to every failure and 5 to every success.
- This judge gave control 1 where the pose was ignored entirely (seed …71), 3 where only the stance was kept, and 4 where
  it was followed.

**Standing pose.** The judges differ here. The lab reads it as "held 3/3" at every strength. This judge reads it as
held on 5 of 9:

- Seed …73 stands square with both arms down at all three strengths.
- 0.7 seed …71 drops the hand from the strap.

**Answer to the lab's claim.** Confirmed in substance:

- The style half fails with this board at the default weight.
- The pose half needs 0.9–1.0 for the raised arm.

One qualification: pose-following on this board is seed-dependent. One seed in three ignored each pose outright, so a
pose run should be checked picture by picture.

The lab's proposed next step is a lower style weight (0.4–0.5). This judge agrees it is the first thing to try, but it
is untested. The burn could also come from the board's own dark, high-contrast palette being pushed onto WAI.

## Not verified

- One board, two poses, three seeds.
- Whether a lower style weight removes the burn.
- Nothing here is art acceptance.
