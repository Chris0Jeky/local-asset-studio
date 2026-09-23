# Masked hand repair on a six-digit hand — 23 September 2026 (overnight lab)

**Question.** The review judge found that none of the three recorded detail-fix passes fixed its target (PR #866). Does a masked
repaint give five clean fingers on `Studio/noob_00004_.png` (the NoobAI elf portrait whose raised hand has a thumb plus five
fingers, job `14caa4fb`) without damaging the style? This hand is the owner's standing complaint (HUMAN_TODO q-2) made concrete.

**Method.**
- **The mask.** `hand_inpaint.py stage` made the RGBA source from the original pixels: a rounded box (12,535)-(180,792) that is
  transparent over the hand (alpha 0 = repaint) and opaque elsewhere. It was uploaded through the Studio as
  `e8195781…_noob4-hand-mask.png`.
- **The first pass.** `hand_inpaint.py run`: 15 Studio jobs (`POST /api/jobs`), 05:13-05:20 local, on the seeds 2026092361-63.
  Both presets got the same hand wording plus a description of this picture:
  - `anime-masked-repair` (WAI v17, plain `SetLatentNoiseMask`, hard composite) at denoise 0.4 (its authored default) and at 0.6;
  - `sdxl-inpaint-fix` (WAI v17 + Fooocus inpaint patch) at 0.5, 0.7 and 1.0.
- **The feathered pass.** `feather.py run`: three direct ComfyUI prompts, 05:30 local. Each is the Studio's own masked-0.6 graph
  for that seed with only the mask changed, using core nodes: `GrowMask` (12 px, tapered) → `MaskToImage` → `ImageBlur`
  (radius 24, sigma 8) → `ImageToMask`. The soft mask drives both the noise mask and the composite.
- **Seam measure.** `feather.py seam` (`seam.json`) works on the change image, repair minus source, where the picture's own
  texture cancels. It takes the column-to-column jump across x 150-212 in rows 560-760, where the background light streak crosses
  the box's right edge at x 180. A hard composite shows one large jump at x 180.
- **Judging** (`judgements.jsonl`). Digit counts and seams were read from full-resolution crops; the per-seed crop sheet is
  `examples/overnight-20260923/hand-inpaint-crops.jpg`. The first-pass records were shuffled blind, but they were written just
  after the key was opened (a protocol slip), so they are all marked `blind: false`.
  - The first pass was also re-read at the mask edge and corrected before commit: four records first written as `keep` became
    `fixable` for the seam.

The source and every repair are original content (an elf in a white robe, no famous character).

## Results

| setting | five digits (seeds 61 / 62 / 63) | gesture and style kept | seam at the box edge (jump at x 180 vs median) | verdicts |
| --- | --- | --- | --- | --- |
| source | six digits on every seed | – | – | fixable |
| `anime-masked-repair` 0.4 (shipped default) | **0 / 3** (barely changed) | yes | 3.9-6.0 vs 1.3-1.8: faint | fixable ×3 |
| `anime-masked-repair` 0.6, hard mask | **3 / 3** | yes | **6.8-8.7** vs 2.1-3.3: a visible seam | fixable ×3 (seam) |
| **`anime-masked-repair` 0.6, feathered mask** | **3 / 3** | yes | **1.2-1.5** vs 1.1-1.5: none | **keep ×3** |
| `sdxl-inpaint-fix` 0.5 | 1 / 3 (one ghosted double hand) | softer, smudgier | its own mask is grown 8 px, so its edge is x 188: a 6.1 jump there on seed 61; not isolated on 62/63 | fixable, reject, fixable |
| `sdxl-inpaint-fix` 0.7 (authored) | 2 / 3 | no: back of the hand, rougher semi-real texture | 7.8 at x 188 on seed 61; not isolated on 62/63 | fixable ×3 |
| `sdxl-inpaint-fix` 1.0 | 0 / 3 (two hands on 2 seeds) | no | – | reject ×3 |

- **The shipped `anime-masked-repair` default (0.4) is too gentle to remove an extra finger.** At 0.6 the same graph redraws the
  fingers and gave five digits on all three seeds. The raised gesture, the lighting and the painterly shading carry over from the
  surrounding picture.
- **The hard mask edge was the second defect.** Every masked repaint left a vertical seam where the box edge cuts the background
  light streak. With the mask grown by 12 px and blurred, the jump at the edge fell to the picture's own texture level on 3 of 3
  seeds. Only one soft smear remains, where the new fingertips of seed 62 meet the streak.
- **The Fooocus patch is the wrong tool for this defect.** At 0.7 and above it re-imagines the hand: a different gesture, a
  different texture, or a second hand. That is useful for rebuilding a missing region, not for fixing fingers in place.

Speed: 8-26 s per repair through the Studio (26 s includes the WAI checkpoint load); the feathered graph ran in 9.2 s warm.

## Proposed preset change (this PR)

- `anime-masked-repair`: default denoise **0.4 → 0.6**, plus the feather nodes (`GrowMask` 12, `MaskToImage`, `ImageBlur` 24/8,
  `ImageToMask`), which feed both `SetLatentNoiseMask` and `ImageCompositeMasked`. All of them are core ComfyUI nodes.
- The preset stays `verified: false` until a Studio proof of the new graph is inspected after merge. The graph run here was
  submitted straight to ComfyUI, built from this preset's own Studio-submitted graph with only the mask changed.

## Not verified

- One picture, one hand and one box mask. A tighter or looser mask, and other defects (a mitten hand, a fused grip), are untested.
- The feathered graph has not been through the Studio yet.
- The grown mask repaints 12 px beyond the transparent region, blended; the region is never hard-cut. A user who needs a pixel
  outside the region untouched should know this.
- None of this is art acceptance. q-2 stays the owner's.
