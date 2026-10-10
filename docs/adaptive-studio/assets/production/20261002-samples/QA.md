# Sample QA and selection

Independent visual review and delegated root selection on 2026-10-02. All six were selected for illustrative source delivery. These findings are bounded visual judgments, not execution or capability measurements.

## sample-character-canon

Illustrative adult character canon: portrait, full-body source and exact-alpha silhouette. Not a measured consistency result.

- Full body and all limbs remain inside 1024x1536 canvas; facial hair/eye/scar features follow the selected portrait closely, subject to illustration-level variation.
- Both feet are fully visible but the rightmost boot has only about 15px bottom clearance in the source.
- Real alpha is present; maximum alpha 254 and interior mostly 253 leaves slight global translucency and faint low-alpha fringe. Exact alpha is deliberately retained in silhouette.

Selection: selected by dot under owner-delegated art judgment.

## sample-pose-pair

Two separate example inputs: identity and mannequin pose. No pose-transfer output or model execution is shown.

- Inputs are deliberately different poses and distinct source roles. No transfer was executed.
- Mannequin hands/feet remain visible; it is an illustrative jointed figure, not a validated anatomical skeleton.
- The identity input inherits the canon alpha caveat.

Selection: selected by dot under owner-delegated art judgment.

## sample-outfit-study

Illustrative clothing variation using the same adult character source. Approximate visual continuity, not a measured model capability.

- Face, hair silhouette, relaxed body stance and hand positions are close between source and edit; clothing differences are clear.
- Hands appear plausible at source size; no skeleton or hand-accuracy measurement was performed.
- The changed sleeves, boot tops, trouser shape and bag contour are expected wardrobe differences. Minor rendered face/hair details differ.
- Both originals have genuine alpha but mostly alpha 253 interiors and low-alpha fringe; light/dark checker composites are included.

Selection: selected by dot under owner-delegated art judgment.

## sample-lighting-pair

Illustrative opposing light directions on an approximately consistent plaster study. Geometry is not pixel-registered.

- Upper-left versus upper-right illumination and opposing cast shadows read clearly.
- Head silhouette, facial planes, wall texture and shadow form show small deviations; not an exact registered light-only edit.
- Both remain 1254x1254; no digital mirror or registered comparison is claimed.

Selection: selected by dot under owner-delegated art judgment.

## sample-composition-pair

One source and a deterministic tighter crop. The view was cropped, not regenerated or moved in 3D.

- Chosen crop [170,125,1194,1149) is pixel-exact at 1024x1024; it replaced the initial proposed 800px crop after visual comparison.
- A useful amount of the dominant block, the complete middle cube and the distant slab remain; the left edge deliberately clips the foreground block. The 800px proposal left only a narrow strip and was rejected for weaker balance.
- The 1024px square target is met by existing source pixels without upscaling. No parallax, camera movement, regenerated viewpoint or measured model ability is implied.

Selection: selected by dot under owner-delegated art judgment.

## sample-sequence-strip

Four extracted illustrative storyboard stills with minor visible continuity drift. Not a temporal-consistency benchmark or generated video.

- Source is 1254x1254, below prompt target 2048x2048. Common-square extracted frames are 621x621, below the 1024px sample target.
- Four actions read in row-major order and identity/outfit/environment remain recognizable.
- Boot positions, stance/leg contours, shoulder/bag edges and hair change slightly; canopy/column/rail and foliage details shift. Fixed-camera, exact foot placement and pixel registration were not achieved.
- Facial scar/eye details are not reliably resolvable at frame size. No temporal or identity capability benchmark is supported.
- White gutters and boundary pixels are excluded by the documented crop boxes; whole sheet retained.

Selection: selected by dot under owner-delegated art judgment.

## Deterministic operations

- Silhouette: RGB set to zero on every pixel; original alpha copied byte-for-byte, without thresholding or opacity normalization
- Composition: [170,125,1194,1149), producing 1024×1024 source pixels; initially considered [400,300,1200,1100) and [300,150,1200,1050) were not selected
- Sequence, row-major: [0,0,621,621), [633,0,1254,621), [0,633,621,1254), [633,633,1254,1254). Each is 621×621; solid white cross observed at columns 622–631 and rows 622–630 with partly blended boundary pixels. Conservative common-square inner boxes omit those transitions and up to 1–2 adjacent content pixels
- Thumbnail: aspect-preserving Lanczos to maximum 320px, then WebP; maximum 60 KiB, no upscaling

## Transparency

Light and dark two-dimensional checkerboard composites are provided for both full-body originals. Alpha ranges 0–254; most character-interior pixels are 253. The transparent exterior is real, not baked checkerboard. Slight translucency and faint low-alpha fringe remain. Source pixels were not normalized or cleaned.

## Size honesty and claim boundary

The sequence failed its requested 2048px sheet target. Its 1254px sheet and four 621px frames are the actual deliverables; extracted frames do not meet the 1024px sample target. They are useful illustrative storyboard inputs, with stance/background drift openly recorded. No generated 1024px frames, registered animation, local route execution, or measured model ability is implied. Source/license, rendition acceptance, runtime and release gates remain independent.
