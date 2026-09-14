# EXIF-oriented Wan source planning and offline preview

Maintenance for #241, separate from #229/#234's reference byte-capture race.
Only `app/i2v_diagnostics.py` changes in product code; `Studio.prepare` already
consumes its image metadata and does not need a second orientation rule.

## Reproduction and behavior

An encoded 12x8 PNG tagged EXIF orientation 6 displays as 8x12. Preparation
previously treated it as landscape and changed the authored, already-correct
512x768 pair to 768x512. The offline first-frame preview then resized/cropped
the unrotated encoded pixels. Tests reproduce both independently, without
submitting a job.

`image_metadata` now uses the EXIF tag to report displayed width/height,
dimensions, aspect and portrait/landscape identity. Additive
`encoded_dimensions` and `exif_orientation` fields retain the source's encoded
geometry/tag. Orientations 5 through 8 swap axes; the others do not. JPEG
metadata does not decode or allocate a transformed pixel canvas merely to
choose dimensions. Pillow can still decode some formats to obtain late EXIF
metadata; this is not a universal header-only guarantee.

`render_preprocessed` applies EXIF rotation/mirroring first, then computes the
existing centered crop and Pillow bilinear resize in that oriented coordinate
space. The transformed output does not retain a stale orientation tag. All
opened/derived image buffers close on exit. Untagged source pixels, original
files, interpolation policy, graph recipes and resource limits remain unchanged.

The existing capacity admission and manual orientation controls stay
independent. This fixes source geometry and the portable diagnostic, not model
anatomy, motion quality or failed Wan inference.

## Primary references and scope

Reviewed 13 September 2026:

- [Pillow ImageOps.exif_transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose)
  documents applying orientation and removing the tag.
- [ComfyUI v0.3.60 core LoadImage](https://github.com/Comfy-Org/ComfyUI/blob/v0.3.60/nodes.py)
  applies EXIF transpose before RGB conversion in the established PIL loading
  path. This is a pinned reference contract, not an observation of the owner's
  installed runtime or a claim about every newer/custom decoder.

No exact Pillow-versus-Torch resampling parity, native loader parity or
subjective first-frame/model quality is certified by these tests.

## Regression evidence

Four initial methods produced **17 failing subcases** against unchanged code.
The earliest fixture attempt used direct indexing for new fields and generated
four missing-key errors; the corrected before run uses assertions throughout.
Five final methods cover all eight rotations/mirrors, encoded and oriented
geometry, exact preview pixels against independently applied transform/crop,
untagged behavior, original-byte preservation and the actual non-submitting
Wan `prepare` path. A review-added JPEG no-decode test failed before the
metadata-only implementation and now passes.

All **12 existing/new I2V tests pass** on this independent branch. Existing
Linux/Windows readiness contracts now include the I2V group. Browser readiness
checks remain unchanged; no new UI interaction acceptance is claimed.

```sh
python -m unittest discover -s tests -p 'test_i2v*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

## Reconciliation and verification environment

Final independent-branch full suite: **1,698 run, 1,682 passed, 16 skipped, zero failures/errors**, 114.233 s. Repository validation passed **66 graphs/bindings, 121 pins and 86 LoRA names**.

Inspected main `3d3135a17811d2e4846ada05aae35e06f60d92f4` / tree
`b34502d889ba5ffc356eb74b2ec15de8a498fd76`. The reconstructed tracked
source matched that tree before editing. Existing open reference-byte,
snapshot-publication, HTTP-framing, library/shortlist and mixed-batch/schema
work was inspected; this slice does not replace those implementations.

Unchanged baseline: **1,693 tests, 16 skipped, no failures/errors**, 114.044 s.
Local environment: Linux, Python 3.13.5, Node 22.16.0, Pillow 12.3.0.
Existing Pillow deprecation and exit-time socket warnings and deliberate
fault-injection diagnostics remain visible. Skipped cases are unverified,
not counted as executed passes. Hosted CI is a separate gate; final-head
results are recorded in the PR rather than presumed from a workflow file.

## Rollback

Revert the change to restore encoded-axis planning. No stored-state migration
is needed; old diagnostic reports remain historical and are not rewritten.
No owner image, model, runtime, configuration or HUMAN_TODO decision changed.
