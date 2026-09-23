# Judgement: the three Qwen-Image 2.1 Studio proofs (23 September 2026)

The coordinator ran three Studio proofs on the isolated Qwen-Image 2.1 backend (25 steps, seed 2026092211). The review
agent (Claude Opus 5.5) judged them with the [rubric](../JUDGING-RUBRIC.md) and corrections R1–R6.

- **Blindness.** These are single outputs with named briefs, so the judgement is not blind to configuration; there was
  nothing to compare blind.
- **The RGBA icon.** Its alpha channel was measured, not only looked at.
- **No images committed.** The records hold the sha256 and the job and prompt IDs:
  [qwen21-proofs.judgements.jsonl](qwen21-proofs.judgements.jsonl).

| Proof | Job | Scores (adh / anat / style / tech / comp / control) | Verdict | Worst defect |
| --- | --- | --- | --- | --- |
| `qwen21-t2i` (832×1248) | `be94bd02…` | 4 4 4 4 5 – | keep | the lowered hand is soft and low-detail; the brief's teal light barely shows |
| `qwen21-rgba` (1024², icon) | `b377572d…` | 5 – 5 3 5 – | fixable | alpha dust over the background, and the bottle body not fully opaque |
| `qwen21-edit` (1024², prop) | `dc8f18f8…` | 5 – 5 4 5 5 | keep | faint paper blotches in the background; the ring turned upright |

## t2i: is it still underexposed?

**No.** At 25 steps the picture is dark in the way blue hour should be: navy sky and bridge, a lit face, and a glowing
brass lantern throwing warm light.

| Measure | 25-step proof | 8-step benchmark (same brief) |
| --- | --- | --- |
| Mean luminance | 39.7 | 27.6 |
| 95th percentile | 105 | 55 |

The face is clean and the lantern hand grips the bail readably. The hand at her side is a soft, simplified shape. The
brief asked for "teal and warm amber light", but the teal barely shows; it reads as navy and amber.

## RGBA icon: alpha, halo and edge

Alpha histogram, as shares of all 1,048,576 pixels:

| Alpha | Share |
| --- | --- |
| 0 | 60.8 % |
| 1–31 | 5.3 % |
| 32–223 | 0.4 % |
| 224–254 | 26.4 % |
| 255 | 7.2 % |

These match the coordinator's measurement (60.8 % zero, 7.2 % full, 32 % partial). The partial third breaks down into two
defects and one clean result:

- **No halo, no fringe.** At the silhouette the edge band is darker than the adjacent interior. That is the icon's dark
  ink outline, not a light or coloured fringe, and composites over magenta, black and white look clean at 3× zoom.
- **Alpha dust.** 55,164 pixels carry alpha 1–31, scattered over the whole background, with a strip along the right
  border. Beyond 32 px from the silhouette every one is below alpha 8, so it is invisible when composited. It still makes
  the icon's bounding box span the whole canvas and yields 13,968 separate specks, which breaks auto-crop and sprite
  packing.
- **The body is not fully opaque.** Most of the bottle sits at alpha 224–254 instead of 255, so it is 1–12 %
  see-through.
- **Fix.** Threshold the alpha: below 8 becomes 0, and 224 or above becomes 255. With that the icon is a clean cutout, so
  the verdict is "fixable".

## Edit: lantern cutout to anime prop

The edit keeps the shape and every colour of `examples/references/studio-lantern-cutout.png`:

- the teal cap and base;
- the orange core;
- the brass posts, ring and latch.

It adds crisp ink outlines and soft cel shading on a plain light background, as asked. The only drift is small: the ring
handle stands upright instead of slanted, and the background has a faint paper texture with a few soft blotches.

## Also noted

The t2i and edit outputs are saved as RGBA although they are opaque pictures: 9.4 % and 19.6 % of their pixels sit at
alpha 224–254. That is invisible on screen. If the Studio or a game import treats alpha literally, flattening these two
recipes' outputs to RGB would remove the question.

## Not verified

- Other seeds.
- The icon at in-game size after thresholding.
- Speed, which is recorded in the job receipts, not here.
