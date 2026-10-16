**Published bundles:** [GitHub source delivery](https://github.com/Chris0Jeky/local-asset-studio/pull/1269#issuecomment-5955931912). Every archive was downloaded back and its bytes and SHA-256 matched. See GITHUB-DELIVERY.json for verified links.

# Atelier source-art pack · 2 October 2026

Six catalogue IDs are represented by three generated source images and three direct master derivatives. The lead selected all six IDs as source art after reviewing the originals and the full crop contact sheet. Source-art selection is separate from source/license clearance, runtime qualification and release selection.

## Delivery

Extract both ZIPs into the same directory. They share the top-level folder `atelier-source-art-20261002/`.

- `atelier-source-art-20261002-originals.zip`: unchanged original PNGs and metadata
- `atelier-source-art-20261002-renditions-review.zip`: lossless native crops, encoded renditions and compact QA previews

No image binaries or archives are intended for ordinary repository commits. The text-only repository additions are listed in `REPO-FILES.txt`, under `docs/adaptive-studio/assets/production/20261002-atelier/`. The planning catalogue, profiles and existing documents are unchanged.

## Honest limits

- Master and quiet are 1672×941; wall is 1536×1024. Provider output did not fulfill the requested larger source sizes. No upscaling was used
- Native hero is 1668×695; the 960×400 encode is supplied. The 1920×800 target is absent because it would require upscaling
- Native card crop is 941×941, below the 1024×1024 target. The required 512 and 256 encodes are supplied
- A conservative master heading zone is x=.16–.48, y=.18–.62. Foliage, diagonal light/shadow and texture make the full left 60% unsuitable for an unqualified text-safe claim
- Quiet shares the canvas and matches all 20 sampled geometric landmarks at 0 px integer shift. Lighting and fine detail differ; this is not whole-image pixel identity or crossfade acceptance
- No actual editor slots, HTML contrast, accessibility, first-screen 350 KiB aggregate, decoded memory, offline loading, fallback behavior or inference contention were tested

## What to review

Start with `review/atelier-contact-sheet.jpg`, then `review/atelier-composition.jpg`. Registration evidence is in `metadata/QUIET-REGISTRATION.json`, `review/quiet-landmarks.jpg` and `review/quiet-edge-overlay.jpg`. Red represents master contours; cyan represents quiet contours; neutral overlap indicates aligned edges. Light/color changes also alter edge strength, so colored texture is not a direct displacement measurement.

`generation-prompts.json` preserves the exact supplied prompts. Receipts record exact master input hashes for both edits, actual dimensions/bytes/hashes and nulls for unavailable provider model, seed, output/job ID and timestamps. The `exec-` handles are orchestration references, not provider job IDs.

The pinned production plan routes Atelier master/quiet to local ComfyUI; this pack truthfully records the actual OpenAI image_gen.imagegen dot-run route. It is source art, not evidence of Local Asset Studio or any local recipe generation. It does not assert completion of the plan’s W5 runtime gates or replace accepted Night Shift art.

## Reproduce the deterministic derivatives

With Pillow 12.3.0 and the recorded WebP encoder, run `python metadata/replay_derivatives.py <pack-root> <new-output-directory>`. The script verifies source hashes, recomputes every crop/encode from the original and compares resulting hashes. It never contacts a provider. Other encoder versions may produce different bytes; inspect before accepting any discrepancy.

The portrait crop is a plan only in `CROP-PLAN.json`. Keep headings on a separate solid surface for narrow layouts rather than assuming the wide header’s negative space survives.
