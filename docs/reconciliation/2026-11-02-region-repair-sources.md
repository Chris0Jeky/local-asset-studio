# Display coordinates and source limits for marked-region repair

Issue #1861, 2 November 2026. This corrects the source handling used by the
existing **Mark the region to repair** flow. All fixtures use synthetic pixels,
temporary SQLite Workspaces and a fake ComfyUI request boundary.

## Source contract

Continuation dimensions and the RGB picture used to compose a repair now use
the displayed EXIF orientation for JPEG, PNG and WebP. Orientations 5–8 swap the
axes; orientations 2–8 rotate or mirror the pixels as specified by the tag.
The prepared PNG carries those oriented pixels without a second orientation.
Boxes remain whole pixels in that displayed coordinate system, with exclusive
right and bottom edges. There is no resize, padding or crop during preparation.

The source identity remains the SHA-256 of the original encoded bytes. Neither
reading dimensions nor preparing a repair rewrites the Library source. Private
sources continue to require private creation and produce private uploads.

`continuation.source_context` reads EXIF for every supported format. JPEG, WebP
and PNG with header EXIF do not require a raster decode just to report the
dimensions. Pillow can load a PNG when its EXIF follows IDAT, or when it must
check for absent metadata. The former blanket header-only PNG assumption was
incorrect for displayed coordinates; the tests now include a valid PNG whose
EXIF chunk follows its image data. The existing encoded source limit and
Pillow safety refusals remain in force. Both context and RGB readers use the
existing `open_bounded` helper: dimensions above Pillow's configured
`MAX_IMAGE_PIXELS` raise `DecompressionBombError` before the metadata lookup or
conversion can load raster pixels, including Pillow's warning-only range.

`continuation.source_rgb` is the small shared decoder for the already
hash-checked bytes. Its Pillow import stays inside the function so static
continuation and catalog validation still work without Pillow. Both
`tiles._source` and `parallax._source` call it. Parallax is included because it
uses the same continuation dimensions: correcting the dimensions alone would
leave its source pixels and view boxes in different coordinate systems.

## Pixel modes and encoded size

| Source | Preparation behavior |
| --- | --- |
| 8-bit RGB, RGBA, grayscale or palette PNG | Preserve the oriented RGB picture using the existing Pillow conversion; replace source alpha with the owner's repair mask. |
| RGB or CMYK JPEG | Orient and use the existing Pillow RGB conversion. The CMYK fixture checks independent red, green, blue and black samples. |
| WebP | Orient and convert to RGB before adding the repair mask. |
| 16-bit PNG, including grayscale, RGB and RGBA | Refuse with instructions to convert a copy to 8-bit RGB before editing. The original remains importable and unchanged. |
| PNG with a noncanonical or repeated IHDR | Refuse before RGB conversion and ask for an 8-bit RGB copy with a supported header layout. |

The 16-bit refusal applies to marked-region repair, seamless tiles and parallax
because those operations share the RGB decoder. Raw import support does not
establish a safe reduction in sample depth. In the reproduction, grayscale
samples 256, 4096, 32768, 49152 and 65535 all became RGB `(255, 255, 255)` through
the previous conversion. Pillow also exposes 16-bit truecolour PNG as RGB8
already, so the guard reads the PNG IHDR sample depth after Pillow opens the
file instead of relying on the decoded mode. Pillow accepts metadata before
IHDR and repeated IHDR chunks, so opening alone cannot establish the depth at
a fixed offset. A bounded chunk-framing walk requires one leading 13-byte IHDR
before reading that sample depth; it neither decompresses chunks nor allocates
their declared sizes. Legal metadata after IDAT remains supported. This
introduces no colour management or tone-mapping algorithm; CMYK conversion remains Pillow's ordinary
conversion rather than an ICC-managed fidelity guarantee.

The mask is zero inside the **union** of the owner's boxes and opaque elsewhere.
An existing transparent or partly transparent source pixel does not add another
repair region. Overlapping marks count once toward the existing 60% refusal.

A source under the 20 MiB encoded limit can produce a larger RGBA PNG after
composition. Prepare now measures that encoded PNG before calling the upload
owner. An oversized result explains that the **prepared repair PNG** exceeds
20 MiB, includes its size and dimensions, and asks the owner to resize a copy,
import it and mark the region again. It writes no repair upload and creates no
job. The upload limit itself is unchanged.

## Causal regressions

The unchanged source failed 61 PNG/WebP subcases across the existing orientation
suite after its JPEG-only fixtures were expanded. The JPEG cases passed.
Independent Pillow transpose operations define expected pixels for all eight
orientations; the expectations do not use the production EXIF decoder.

The repair fixtures separately reproduced three missing 16-bit PNG refusals
(grayscale, RGB and RGBA) and the generic upload error from a synthetic
3072 × 2304 JPEG whose prepared RGBA PNG exceeds 20 MiB. Those four assertions
failed before the refusal changes. The existing union pixel test already
covered overlap geometry; the additional union test proves that two boxes
summing to 100% but covering only 56/96 of the picture are accepted, while a
union covering 64/96 is refused.

Further cases cover rotated JPEG/PNG/WebP repair boxes, a private oriented PNG,
untagged inputs, unchanged original hashes and bytes, stale dimensions,
transparent source pixels, and graph preparation without dispatch. An
intermediate private fixture omitted the explicit PNG `exif=` save option and
failed its expected dimensions; correcting that fixture supplied the intended
tag before final qualification.

Independent review reproduced six further bypasses using real imports:
leading metadata or an extra 8-bit IHDR before the 16-bit header, each with
grayscale, RGB and RGBA data. All six prepared a repair before the header guard
was added. A separate 6144-pixel PNG fixture lowers `MAX_IMAGE_PIXELS` to 4000
and patches `PNG.load`; both source readers reached that forbidden decode
before the strict guard. The new regressions now require the refusal, no
repair upload, unchanged source bytes and no engine request.

The associated checks are `test_region_repair.py`,
`test_source_exif_orientation.py`, `test_tiles.py`, `test_parallax.py`,
`test_continuation*.py` and `test_vary_routes.py`. Run each group with
`python -m unittest discover -s tests -p '<filename or pattern>'`, followed by
`python scripts/validate-repo.py`. The combined focused run on Python 3.12.14 /
Pillow 13.0.0 passed **167 tests in 136.825 seconds**, with no skips or failures.
Validation also passed with `python -S scripts/validate-repo.py`, with site
packages disabled: 98 graphs/bindings, 194 pinned assets and 167 LoRA names.
Exact-head hosted and full-suite results belong to the PR qualification record.

After the independent-review corrections, the same focused set passed
**169 tests in 134.429 seconds**, with no skips or failures. The validator again
passed with site packages disabled, including 4,737 tracked paths checked.

## Limits

These checks establish CPU source coordinates, conversion/refusal behavior,
privacy placement and non-submitting preparation. They do not qualify an
installed native engine's decoder, a browser's displayed pixels, generated
repair quality or owner art acceptance. Existing `HUMAN_TODO.md` choices remain
open and authoritative. Full-suite integration and exact-head hosted CI are
separate gates from these focused synthetic checks.
