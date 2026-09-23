# Second judge: the automatic hand repair (detector route) at stronger settings (23 September 2026)

This is an independent second judgement of the lab's `hand-fix` experiment (#890). The route under test is the shipped
`anime-hand` graph: Impact Pack FaceDetailer on `bbox/hand_yolov8n.pt`, with WAI v17. It needs no hand-drawn mask. The
lab ran it straight against ComfyUI with a generic hand prompt, seed 2026092395, and three settings:

| Setting | denoise | guide_size | crop factor |
| --- | --- | --- | --- |
| authored | 0.4 | 512 | 2.5 |
| 0.6 | 0.6 | 512 | 2.5 |
| 0.6 + guide 768 | 0.6 | 768 | 3.0 |

It was run on four sources, all fully clothed adult original characters. Their prompts were checked before viewing.

| Source | Hand defect |
| --- | --- |
| `Studio/noob_00004_.png` | the six-digit raised hand |
| `Studio/noob_00005_.png` | the witch's smeared cloak hand |
| `Studio/CSTati-v3-Baseline_00003_.png` | two fingerless mitten hands |
| `Studio/YumeFlux-ILv1-Baseline_00002_.png` | mitten hands |

**How it was judged.** The review agent (Claude Opus 5.5) judged all 12 outputs blind:

- per source, under its own shuffle (X/Y/Z), with metadata stripped;
- every hand cropped at 3–4× beside the source;
- a difference map against the source for each output, to see what was repainted;
- all records written before the key or any lab record was read.

It scored with R8 and R8a. R8a enters the rubric with #891, which merges before this. Under them, `adherence` means the
named hand defect was fixed, `control` means everything else was kept, and a pass that leaves the defect is a reject.
Untouched defects were scored `adherence` 2, which the coordinator later adopted as R8b (see below). The records are in [hand-fix.judgements.jsonl](hand-fix.judgements.jsonl).
No images are committed.

## Results

| Source | What the detector repainted | authored 0.4 | 0.6 | 0.6 + guide 768 |
| --- | --- | --- | --- | --- |
| noob4 | the raised hand | reject: six digits | reject: six digits | reject: six digits |
| noob5 | only the lantern fist; the smeared cloak hand is untouched | reject | reject | reject |
| CSTati | **nothing**: all three outputs are pixel-identical to the source | reject | reject | reject |
| Yume | both hands, lightly | fixable: fingers begin to separate on one hand only | **keep**: fingers on both hands, with pale vein shading | fixable: fingers, but white crack-like veins on one hand |

Notes on individual results:

- **noob4.** At 0.6 the hand was redrawn more crisply, and a bright blob and sparkles appeared on the light streak beside
  the fingertips. The digit count never changed.
- **noob5 at 0.6 (guide 512).** The fist was redrawn, and the lantern handle's ring behind the fist was mostly lost. At
  0.6 + guide 768 the fist was redrawn with the handle kept.
- **Changes stayed local.** On every output the change is confined to the detected hand silhouette: pixels outside the
  changed region moved by 0.01 grey levels on average, and there is no crop-box seam.

**Answer to the lab's claim.** Confirmed in substance: the detector route does not repair hand defects. It misses bad
hands entirely (CSTati) or boxes the wrong one (noob5). Where it does find the bad hand, it redraws the same structure:
the six digits stay six at every setting. More denoise changes the rendering before the anatomy, as on Yume.

The two judges differ on one picture, Yume at 0.6:

- **This judge:** a keep. At 1.5× the veins read as shading.
- **The lab:** off-style, so fixable, not fixed.

So the route fixed at most one of the four defects.

**The working alternative** is the feathered masked repair, `anime-masked-repair` at denoise 0.6 with a hand-drawn,
feathered mask:

- In research it fixed the same six-digit noob4 hand on 3 of 3 seeds.
- Its Studio proof (#885, job `1f9b3e11`, `Studio/Anime-Masked-Repair_00007_.png`) gave five digits with no seam: seam
  excess p90 2.0, and pixels more than 20 px outside the mask unchanged.
- This judge judged the Studio proof "keep" under R8 ([hand-inpaint.md](hand-inpaint.md), last section).

Use that route for hand defects. `anime-hand` should not be described as a hand fix.

## Agreement with the lab's judge

The lab's records are in its PR #890 (`experiments/curated/overnight-20260923/hand-fix/judgements.jsonl` there).

| Measure | Result |
| --- | --- |
| What each setting did to each source | agree on all 12: the same hands named, at nearly the same crops |
| Picture verdicts | **2 of 12** agree: Yume at 0.4 and at 0.6 + guide 768, both fixable |
| Criteria exactly equal | 41 of 72 |
| … technical | 11 of 12 |
| … adherence | 3 of 12 |

Nine of the ten verdict differences are one scoring difference. On every picture whose named defect was left in place,
the lab gave `adherence` 3 and called the picture fixable. R8 says a pass that leaves the defect is a reject, and this
judge gave `adherence` 2. Both judges saw the same things:

- six digits on noob4;
- the cloak hand untouched on noob5;
- nothing repainted on CSTati.

The tenth difference is the Yume 0.6 style call above.

**R8b.** The coordinator adopted this split as rule R8b, now in the [rubric](../JUDGING-RUBRIC.md): a correction pass that
leaves the named defect untouched scores `adherence` 2 and is a reject. Its worked examples come from this experiment:
noob4, where six digits remain, and CSTati, where the output is pixel-identical because nothing was detected.

**After the lab's rescore.** The lab then rescored its records to R8b in #890: the 10 outputs that left their named defect
untouched are now rejects with `adherence` 2. Agreement after the rescore:

| Measure | Result |
| --- | --- |
| Picture verdicts | **10 of 12** agree |
| Criteria exactly equal | 49 of 72 |
| … adherence | 11 of 12 |

Two differences remain, both on Yume:

- **Yume at 0.4.** The lab gives a reject: its named defect is the viewer-right hand, and that hand is still a mitten.
  This judge's record reads the same hand as "still a block", but it counted both hands and credited the partial finger
  separation on the other one, so it gave `adherence` 3, fixable. Measured against the lab's named hand alone, R8b would
  make this a reject too. The blind record is left as written.
- **Yume at 0.6.** The style call described above.

Across the night's lab-against-review comparisons:

| Experiment | Picture verdicts agreeing |
| --- | --- |
| VAE decode | 5 of 7 subjects |
| Krea GGUF | 15 of 15 |
| Combine | 12 of 12 |
| Hand inpaint | 10 of 18 |
| Restyle | 8 of 9 |
| Krea refine foxes | 3 of 6 |
| Style+Pose pack | 18 of 18 |
| Hand fix | 2 of 12; 10 of 12 after the lab's R8b rescore |

The three lowest are all correction passes. Each time, the judges agreed on what the pictures show and split on how to
score a pass that did not do its job.

## Not verified

- One seed per setting, four sources.
- Other detector models or a lower detection threshold might find the missed hands.
- Nothing here is art acceptance. q-2 stays the owner's.
