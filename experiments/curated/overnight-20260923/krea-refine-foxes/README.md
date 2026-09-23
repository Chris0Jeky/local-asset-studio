# krea-refine on the fox shrine with its own prompt: 0.25 against 0.35 — 23 September 2026 (overnight lab)

**Question** (review judge, PR #866). The owner said the style-lab fox shrine (`Studio/krea-style-lab_00001_.png`) "loses detail,
the fox faces are morphed". The recorded `krea-refine` proof had used the preset's own example prompt ("two red foxes on a
snowy hill"), not the shrine's, and it turned the foxes into two and added snow specks. Does the refine pass fix the faces
without losing foxes when it gets the shrine's own prompt, at denoise 0.25 and 0.35?

**Method.** `krea_refine.py run`, 05:31-06:09 local: 6 Studio jobs (`POST /api/jobs`), seeds 2026092381-83. Each job is the
shipped `krea-refine` graph with the source staged through `POST /api/upload`:
- TextFusion + Niji Sweet Spot + the 4-step distill LoRA at 0.85;
- 4 steps euler/simple, cfg 1;
- the positive is the shrine's own recipe prompt ("a fox spirit shrine on a cliff at dawn, paper lanterns and drifting petals,
  soft mist over the valley, airy anime watercolor style");
- only the denoise changes.

`seal` shuffled each seed's two refines together with the source. The source is the same picture in every group, so it is
recognisable and its records are effectively open; the two refines were blind to each other. Judged with R8: `adherence` means
the faces were fixed without losing foxes, and `control` means the rest of the picture was kept. Crops of the fox group at full
resolution. Original content (foxes, a shrine): Git-safe.

## Results (unblinded)

| denoise | four foxes kept | faces clear | verdicts (seeds 81 / 82 / 83) |
| --- | --- | --- | --- |
| source | – | soft, partly smeared (the owner's complaint) | fixable |
| **0.25** | **3 / 3** | 3 / 3 (one fox with oversized flat ears and an added red cloth on seed 83) | **keep, keep, fixable** |
| 0.35 (the old default) | **1 / 3**: two foxes left on 81, three on 83; four on 82, but one of them a translucent double | 3 / 3 where present | reject, reject, fixable |

- **0.25 does what the preset promises:** it tightens the fox faces (readable eyes and muzzles, closed-eye smiles) and keeps the
  count, the shrine, the tree, the petals and the watercolour finish.
- **0.35 is too strong for small repeated subjects:** it recomposed the fox group on every seed.
- **Speed.** 338-420 s per job, because the fp8 Krea build sampled with up to 5.6 GB of the ComfyUI process in WDDM shared
  memory (timelines in `timelines/`). A GGUF + CPU-encoder variant of this preset should bring that under a minute and a half
  (see `../krea-gguf/`), but it was not run here.

## Proposed change (this PR)

- `krea-refine`: default denoise **0.35 → 0.25** (`workflows/api/krea-refine-api.json` node 7).
- The "Light touch (denoise 0.25)" variant becomes "Stronger (denoise 0.35, the old default)".
- The description, the execution note and the atelier guide say why.

The six jobs above are Studio executions of the preset at 0.25 and 0.35, so the preset stays `verified: true`, with the execution
note extended.

## Not verified

- One source picture and three seeds per setting.
- Only the fox group was judged in detail; the background was checked at the whole-frame level.
- No art acceptance.
