# Style + Pose re-proof for the fantasy pack — 23 September 2026 (overnight lab)

**Question** (review judge, PR #866). Re-prove `style-pose-wai` on the pack's own adult original: the look-B portrait as the style
board, a standing pose and an action pose, at pose strengths 0.7, 0.9 and 1.0, on three seeds.

**Method.** `stylepose_pack.py run`, 06:11-06:21 local: 18 Studio jobs (`POST /api/jobs`).
- **Style board:** `Studio/Anima-v1-Baseline_00004_.png`, the pack's three-quarter portrait, one picture.
- **Standing pose:** the pack's full-body render `Studio/Anima-v1-Baseline_00005_.png`.
- **Action pose:** `../combine-adult/`'s stance render (one arm raised).
- **Controls:** pose strength 0.7 / 0.9 / 1.0; style weight at the preset default (0.7, `linear`); seeds 2026092371-73; a WAI tag
  prompt describing the pack character.
- **Judging:** open (the configuration is known from the file order). Full frames and strips per pose, and one full-resolution frame.

## Results

| pose | strength 0.7 | 0.9 (authored) | 1.0 |
| --- | --- | --- | --- |
| standing (walk, hand at the scarf) | held 3/3 (second judge: 1/3) | held 3/3 (second judge: 2/3) | held 3/3 (second judge: 2/3) |
| action (one arm raised overhead, wide stance) | raised arm lost 3/3 | held 2/3 | held 2/3 |

**Every one of the 18 renders is a `reject` on the finish.** The colours are burned into neon teal, magenta and hot orange blocks,
with hot orange or pink backgrounds and magenta-tinted hands and faces. It is far from the painterly board and far from WAI's
normal look (compare the census `wai` output). The coat, scarf, brass buttons, earrings and boots do come through, and faces
are adult.

- **The pose route works:** 0.9 and 1.0 hold even the raised arm on 2 of 3 seeds, and 0.7 loses it every time.
- *Second judge (#891), 23 September 2026:* it agrees with all 18 rejects for the burn, but counts the standing pose held on
  5 of 9, not 9 of 9. Seed 73 stands square with both arms down at every strength, and at 0.7 seed 71 drops the hand from the
  strap. It also found red or pink hair on seed 73, red legs where dark trousers were asked, mismatched boots, and ghost
  extra fingers on `WAI_00029_` and `WAI_00032_`. My pose counts were read from the strips and were too generous.
- **The style route does not work with this board at the default weight.** The PR #311 notes for this adapter say that
  over-driven style boards saturate; the IP-Adapter at 0.7 `linear` with a single painterly Anima portrait over-drives WAI's
  palette here.
- **Speed:** 18-20 s per job warm (199 s for the first, with the model loads).

## Next step (not run)

The same 18 jobs at style weight 0.4 and 0.5 (the preset's "Style lighter" variant is 0.5 with pose 0.7). Without that, this is
not a usable pack route. The pose half of the evidence (strength 0.9 or 1.0 for dynamic poses) holds regardless.

## Not verified

- One board, two poses, three seeds.
- The style-weight fix is a hypothesis.
- No art acceptance.
