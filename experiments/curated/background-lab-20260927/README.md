# Background-technique lab: parallax layers, seamless tiles, backdrop variety — 27 September 2026 (18:29-19:03 local)

Refs #422. The owner's answer on what game backgrounds must be (27 Sep 2026, in chat): "A mix, a very ambitious mix, with
experimentation, this will allow me to push in the direction that I most desire". Context: the research doc on branch
`claude/research-experiment-loop`, `docs/research/EXPERIMENT-LOOP-RESEARCH-2026-09-27.md`, sections 4-6.

This is a small, SFW, measured set with installed tools only, on the primary ComfyUI 0.35.0: Depth Anything V2, MAT inpaint,
Z-Image Turbo fp8 and FLUX.2 Klein 4B. Nothing was installed or downloaded for it. All scenes use the owner-accepted Night Shift
anchor `retro-anime-master-z2` (sha256 `c22b723c…`) as the look.

Everything here is **generated and agent-judged only** (`judgements.jsonl`, docs/quality/JUDGING-RUBRIC.md). Nothing is art
acceptance or licence clearance. Times come from receipts:
- Studio `elapsed_seconds` for Studio jobs (`receipts/studio-runs.jsonl`, plus `studio-jobs/<key>/`);
- ComfyUI `exec_s` for direct prompts (`receipts/runs.jsonl`).

## (a) Parallax layers from one scene — `parallax-sheet.jpg`

Three layers (far = the window view, mid = the room shell, near = desk, chair, lamp and CRT). Each is shown as a 3-frame
strip, camera left / centre / right, with layer shifts of 3, 10 and 24 px at 1344x768.

| Route | What it does | Receipts | Verdict |
| --- | --- | --- | --- |
| **A (naive depth)** | Depth Anything V2 vitl (prompt `0d379811`, 25.1 s), 3 depth bands, MAT fills behind (`617de47c`, `ecaa2b94`) | `parallax.json` A | **reject**. The depth map reads the rainy window as a near side wall. The window view, frame and furniture move as one slab: the view never slides behind its frame, and the desk never moves against the wall |
| **B** | Clean plate: Studio `flux-edit` "remove the desk, chair, lamp and monitor" (jobs `99fa529a` / prompt `c8cbd1a1` 48.4 s and `d05ad540` / `d3135576` 30.4 s), registered to the anchor (affine; mean \|shift\| 4.04 / 1.69 → 0.23 / 0.58 px). Near = difference matte | `parallax.json` B | not judged separately: the difference matte misses the dark chair and desk legs against the dark plate (see C) |
| **C** | B's plate plus a second `flux-edit` that isolates the furniture on white (job `c19a163a` / prompt `5f987dd6`, 50.1 s), registered the same way; near = non-white pixels | `parallax.json` C | **fixable**: a black ring behind the frame in the far layer (MAT extended the black context) and a lighter desk silhouette in the plate |
| **C2** | C, plus: the far ring filled from the nearest window-view pixel (no MAT), the CRT excluded from the view, and the plate colour-matched to the anchor (24 px ring) with a 6 px feathered blend | `parallax.json` C2, recomposite error 0.36/255 | **keep**. Worst defect: a faint lighter area behind the desk's right edge at full offset. The two window-glass polygons were drawn by hand from a grid view |

**What worked:** generative clean plates plus a generative matte from the same edit model. Both are registered back to the
anchor, because Klein returns about 0.6-1.3 % larger and a few pixels off. The recomposited layers reproduce the anchor
(mean abs error 0.36/255).

**What didn't:** depth thresholds on a painted interior, a difference matte for dark objects, and MAT with black context.

**Still manual:** the window-glass mask. The layers are 1344x768; the 4K versions were not made.

## (b) Seamless tiles — `tiles-sheet.jpg`

**Method:** roll the texture by half in both axes, so the wrap seam becomes a centre cross. Repaint the cross with Z-Image
img2img plus `SetLatentNoiseMask`, using the texture's own prompt (direct prompt). Composite with a soft mask. Then an optional
deterministic *circular* Gaussian lighting flatten (sigma 96 px, FFT, so the correction tiles too).

The seam score is the mean \|difference\| across the wrap edges. Its reference is the texture's own neighbour gradient
(`tiles.json`, `flat-*.json`).

| Attempt | Source (Studio `zimage-fast`) | Repaint | Seam raw → tiled (own gradient) | Verdict |
| --- | --- | --- | --- | --- |
| floor v1 | `b301976b` / `e5f48cac`, 159.1 s: came out in perspective, not top-down | `0444284d`, band 112 px, denoise 0.8, 163.0 s | 18.12 → 2.45 (1.85) | **reject**: perspective rows cannot match, and the repainted cross is a distinct band repeated every tile |
| floor v2 | `9df74338` / `45edc282`, 149.0 s, "flat orthographic … no perspective" | `b87c63ac`, band 160 px, denoise 0.65, 146.9 s; then flatten | 13.53 → 1.61 → 1.62 flattened (1.13) | **fixable**: a thin row of plank ends repeats at the tile period |
| wall | `653973c1` / `f7c9541f`, 105.4 s | `7ded7485`, band 112 px, denoise 0.8, 183.7 s; then flatten | 4.34 → 0.82 (0.95) | **keep**: no seam visible in the 3x3 |

**What worked:** offset-and-repaint removes the hard seam every time. The circular flatten removes the low-frequency
light gradient that otherwise shows as bands at the tile period.

**What didn't:** a perspective source.

**Not available:** no circular-padding or seamless-tiling node is installed (a latent-circular route would need a custom
node). Z-Image repaint jobs took 147-184 s each; the cause (CPU text encoder, cold loads) was not isolated.

## (c) Single-backdrop variety in the accepted look — `scenes-sheet.jpg`

| Attempt | Route | Receipts | Verdict |
| --- | --- | --- | --- |
| rooftop | Z-Image with the **z2 wording template** (the same structure and style words, a new place; seed 2026092752, the same as z2) | `a0e1e212` / `a2dd6448`, 206.3 s | **fixable**: the look carries (graphite, amber lamp, rose/cyan, distant train), but the left half is busy with buildings and the parapet, breaking the quiet-left rule |
| corridor | same wording route | `95fae07b` / `f5e8471e`, 192.0 s | **keep**: quiet left wall, window, train, amber lamp, cyan vending glow. Minor: the vending machine stands outside the window and its panels carry illegible marks |
| restyle | `restyle-klein-picture` (Klein 4B, verified: false): a WAI Night Shift attempt (`Studio/WAI-Illustration_00046_.png`, a rejected look) as image 1, with z2 as the look picture | `8f99fe64` / `11b93d84`, 64.0 s | **fixable**: the line work moves toward z2, but the night turns grey and washed, and a z2-style gooseneck lamp leaks in at the window |

**What worked:** the look is carried by **words on the same model**, a z2 wording template. **What didn't:** a look picture
through Klein's reference route leaks content and loses the night mood.

## Recommended background loop per type (agent proposal, not a decision)

- **Single backdrop:**
  1. Write the look as a wording template, taken from the accepted anchor's recipe.
  2. Run 2-4 seeds on the same model.
  3. Judge the quiet-left / text-safe rule first, then the look.
  4. Refine with a targeted `flux-edit`.
  5. Upscale as the Night Shift pack did.
- **Parallax:**
  1. Start from the accepted still.
  2. Make a `flux-edit` clean plate ("remove the foreground objects").
  3. Make a `flux-edit` isolate-on-white of the same objects.
  4. Register both to the still (affine fit on edges).
  5. Derive near = isolate matte, mid = still plus colour-matched plate under the matte, far = view region with a nearest-pixel ring.
  6. Recomposite and check the error against the still (≤1/255), then review a 3-frame strip at the maximum offsets.
  - Needed: an automatic view/sky mask (today drawn by hand).
- **Seamless tile:**
  1. Generate a flat orthographic texture.
  2. Roll by half.
  3. Masked repaint of the cross at denoise 0.65-0.8.
  4. Circular lighting flatten.
  5. Review a 3x3 repeat, plus the seam score against the texture's own gradient.

## Not verified

- Only one agent judge, one seed per cell.
- Not tested at 4K, in the running editor, or with an engine's parallax camera.
- The window masks are manual.
- No LayerDiffuse or native RGBA route: the qwen21-rgba route was not run, to stay on primary.
- Z-Image and Klein licences are as recorded elsewhere; none is cleared here.
- Full-size PNGs stay local under ComfyUI `output/Research/bglab-20260927/` and `output/Verified/FLUX-Edit_00020-22_`.
- The receipts' `.py` files are as-run scripts with local paths, not portable reproductions.
