# minimal-pro source-art pack · 2 October 2026

All six IDs are selected as source art by the lead assistant after full contact-sheet review: master, quiet, wall, hero, poster and card. Three generated original PNGs are unchanged; hero, poster and card are deterministic exact-master derivatives. This source-art selection does not clear source/license, runtime or release gates.

## Delivery and scope

Extract both `minimal-pro-source-art-20261002-originals.zip` and `minimal-pro-source-art-20261002-renditions-review.zip` into the same parent directory. They share the `minimal-pro-source-art-20261002/` root. Originals and metadata are in the first archive; native crops, encoded renditions and compact review images in the second. Every ZIP is below 10 MiB and has a verified per-member hash roundtrip.

Media and archives remain outside ordinary Git commits. The proposed repository additions are text-only and enumerated in REPO-FILES.txt under production/20261002-worlds-final. No catalogue, profiles or existing planning document is changed. Review scripts are optional offline inspection tools, not executable theme-import content.

## Dimensions and targets

- Scene/quiet originals: 1672×941. Wall original: 1536×1024. Native 4K and 2400×1600 wall targets were not fulfilled
- Exact 16:9 scene and poster crops remove 0.25 source pixel at the top and bottom during one isotropic downsample; original PNGs remain unchanged
- Hero native crop: 1668×695, with 960×400 WebP. The 1920×800 target is omitted rather than upscaled
- Card native crop: 941×941, below the 1024 px target; 512 px and 256 px encodes are included
- Eleven WebPs decode at their recorded dimensions and meet the individual profile byte budgets; no upscaling or nonuniform scaling

## Composition and quiet alternative

Warm stone/ivory is deliberately retained rather than the originally requested deep graphite.

Conservative master heading proposal: [0.08, 0.18, 0.5, 0.64]; wall control-area proposal: [0.1, 0.24, 0.7, 0.82]. Coordinates are normalized source rectangles and are visual recommendations only. They are not actual HTML contrast or accessibility passes.

- The actual palette is warm grey stone/ivory with a wooden chair, lighter and warmer than the requested matte graphite; fine plaster texture is visible.
- The conservative heading proposal is x=.08-.50, y=.18-.64 (42% of width), not an automatic full-left 60% claim; brighter diagonal skylight falloff lies to its right.
- The wall retains tactile plaster and soft skylight illumination. Its top-right bevel and stronger bright area should remain outside real controls.
- Full 12% overscan is not met: desk right edge and chair legs approach or intersect the canvas. Hero retains the desk/chair core but deliberately crops lower legs and much of the skylight.
- Any CSS scrim or solid heading surface is a recommendation only, not tested contrast.

Quiet edit: Cooler and more evenly lit still preserves the same room and object layout. Sampled local offsets reach 3.1623 px around a paper edge; small generative geometry/detail changes remain, so no pixel-exact registration or crossfade acceptance.

Twenty high-pass local template samples yield median shift 1.0 px, maximum 3.1623 px, median NCC 0.90847 and minimum NCC 0.65693; no search-boundary hits. See QUIET-REGISTRATION.json for raw points and limitations. The red/cyan edge overlay supports interpretation but is also affected by lighting and texture. Neither original has been warped or registration-corrected.

LIGHTING-SUMMARY.json records 8-bit grayscale summaries. In the proposed heading rectangle, master→quiet mean is 133.356→151.732, and standard deviation is 13.33→11.407. These are descriptive image statistics, not physical luminance or a WCAG contrast result.

## Provenance and acceptance boundaries

The actual provider route was OpenAI image_gen.imagegen on dot-run. Master is one independent generation; quiet and wall each used that world's exact candidate-1 master as the edit input. Receipts bind every source and derivative by SHA256. Exact supplied prompt text and original combined prompt-record bytes are retained. Provider model/build, seed, provider output/job ID and generation timestamp were unavailable and remain null. The exec handles are local orchestration references, never provider IDs.

The pinned production plan routes these scenes/quiet edits to local ComfyUI. This pack records the actual different producer honestly and makes no claim of local recipe execution, app inference or completion of W5 runtime gates. Existing accepted Night Shift artwork is not replaced.

No actual editor slots at 390×844, 1440×900 or 1920×1080 were tested. Heading/control contrast, accessibility, first-screen 350 KiB aggregate transfer, decoded memory, loading/fallback, offline use, active-inference contention and runtime crossfade remain unqualified. No layer, loop, audio or promotional assets were made.

## Review and replay

Start with review/minimal-pro-contact-sheet.jpg (includes the card at 96 px), then review/minimal-pro-composition.jpg and the quiet landmark/edge overlays. The sources and renditions have no QA labels baked in.

Run `python metadata/replay_derivatives.py <pack-root> <separate-output-directory>` with the recorded Pillow/WebP versions. It verifies inputs and byte-replays all 13 crops/encodes. Run `python metadata/check_registration.py <pack-root> <separate-analysis-directory>` with Pillow, NumPy and SciPy to reproduce the raw sampled comparison. Different encoders may produce different bytes and require review. The portrait crop in CROP-PLAN.json is only a plan; use a separate solid heading surface in narrow layouts.
