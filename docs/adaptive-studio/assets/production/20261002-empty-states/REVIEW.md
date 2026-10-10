# Empty-state candidate art review

QA preparation: 2026-10-02T15:04:32Z. LAS PR1269: https://github.com/Chris0Jeky/local-asset-studio/pull/1269

Selected for candidate illustration exploration under delegated aesthetic authority: blank 1, no-match 2 with explicit fit-with-padding, source-required 1. No-match 1 is retained as a superseded alternative.

Selection is limited to these candidate illustrations. The accepted illustration family permits exploration; accepted Claude Design/state-system output was not supplied. Source/terms, state-system design acceptance, runtime qualification and release gates remain separate.

## state-blank--candidate-1

Open ivory folio and an inviting empty picture frame read clearly at 384x256, with restrained cyan cover and graphite edging.

- Matches the supplied workflow-create anchor's paper/frame language, while omitting the anchor's reward star and tabletop.
- No lettering, completed picture, button, arrow, progress signal, face or mascot observed.
- Whole meaningful object group remains visible with comfortable margins on light and dark composites.

## state-no-match--candidate-1

Search magnifier is readable, but the two empty frames overlap rather than remaining separate.

- This fails the intended quiet-gap arrangement and is not selected.
- Kept unaltered for provenance and comparison; no attempt was made to extract or rearrange its objects manually.

## state-no-match--candidate-2

The two empty frames are now separate; the small cyan magnifier keeps the search metaphor clear. Explicit fit-with-padding improves the outer margins.

- The native layout had narrow side margins. The selected rendition uniformly fits the complete native canvas into a nominal 90% area and centres it on transparent padding.
- At 384x256 the exact 3:2 fit is 345x230, with 19px left/20px right and 13px top/bottom canvas padding; one-pixel asymmetry is integer centring.
- The nearest alpha>=128 gap is approximately 6px in the unpadded 384x256 rendition; the fit does not increase that gap and the requested approximately 6% gap is not met. The narrower gap was accepted for candidate exploration because the frames are clearly separate.
- No fake background, lettering, warning cue, arrow, progress signal, face or mascot observed.

## state-source-required--candidate-1

One clean empty ivory frame and a separate cyan right-angle bracket read as an image slot at 384x256.

- The bracket remains distinct from the frame on light and dark composites.
- No upload arrow, button, lettering, scenery, warning cue, progress signal, face or mascot observed.
- The composition is calm, consistent with the selected illustration family, and does not substitute for accepted UI/state-system design.

## Transparency and size QA

- All four native originals are 1536x1024 RGBA and copied byte-for-byte. All have actual zero-alpha pixels; these are not opaque checkerboard renders.
- Every original alpha channel ranges from 0 to 254, with no fully opaque pixel. This was not normalized to 255.
- Alpha-1 dust reaches some original canvas edges. Bounding boxes for alpha >= 1, 8, 32, 128 and 250 are reported for measurement only. No threshold, cleanup, matte, background replacement or hidden crop was applied.
- Light (#f7f5ef) and dark (#182027) composites show clean readable silhouettes at 384x256 without obvious glow, opaque background rectangles or edge cutoffs. The plain transparent-image viewer alone can misleadingly expose latent RGB around transparent pixels; review conclusions use proper alpha composites.
- Derivatives are 768x512 RGBA PNG and 384x256 RGBA WebP. Each 384x256 file is <= 60 KiB. The 768x512 PNGs have no 60 KiB target.
- Lanczos resampling legitimately produces some alpha=255 pixels through filter ringing despite source maximum=254. This is disclosed resampling, not alpha normalization. PNG/WebP decode alpha equals the resampled alpha exactly.
- For no-match 2, nominal 90% fit is represented with exact 3:2 integer sizes: 690x460 in 768x512 and 345x230 in 384x256, effective 89.84375%. All original content is scaled uniformly; transparent canvas padding is explicit.

## Gate summary

- Candidate art: selected blank 1 / no-match 2 padded / source-required 1
- Source provenance: prompt/reference/hash recorded; source terms and license clearance not independently determined
- State-system design: accepted Claude Design output absent, gate outstanding
- Rendition: local dimensions, alpha, size, decode and light/dark review checked
- Runtime: not qualified; no browser integration or heavy CI
- Release: not selected

## Deliverables

- inbox/: four untouched native PNGs
- candidate-renditions/: three selected 768x512 PNGs and three selected 384x256 WebPs
- review/: selected contact sheet, explicitly composited for review
- docs/adaptive-studio/assets/production/20261002-empty-states/: ordinary text production records
- docs/adaptive-studio/assets/receipts/: four ordinary JSON receipts
- SHA256SUMS.txt: every payload except itself; archive hash is external to avoid circularity
