# Reference provenance from one bounded byte capture

Fixes #229; related #21 and #9 remain broader workstreams.

## Root cause

`image_record` first read the path to calculate its hash, then opened the path
again through Pillow for dimensions. A replacement between those operations
could return the original hash and byte count with the new image's geometry.
The 20 MiB stat precheck also preceded an unbounded `read_bytes`: a growing
source could exceed the limit after the check.

The regression replaces an actual 40 x 60 PNG with an 11 x 7 PNG immediately
before `Image.open`. The old code returns mixed provenance. A second regression
grows a real file to 20 MiB plus one byte immediately before the source opens.
It previously reached the decoder and returned an oversized record.

## Implementation and choices

Keep the existing path-containment and cheap stat checks. Open the source once
and request at most `MAX_REFERENCE_BYTES + 1` bytes. Reject the sentinel byte
before image decoding. SHA-256, byte count and EXIF-oriented dimensions all
consume that same capture via `BytesIO`. Explicit contexts close the source,
in-memory stream, decoder and oriented image.

Reopening the path after hashing was rejected because it cannot establish that
both observations describe the same bytes. Merely checking size after an
unbounded read was rejected because it still allows the allocation. No new
image-format restriction, pixel limit or orientation policy is introduced.

This proves consistency of the captured buffer, not an atomic filesystem
snapshot against an in-place concurrent writer. It does not pin a mutable
reference for a later generation. Downstream byte verification and existing
reference staging remain the authority for those later boundaries.

## Regression and verification procedure

Six new methods in `tests/test_reference_byte_capture.py` cover replacement,
growth, the actual read-size bound and handle closure, EXIF orientation, the
inclusive exact-size limit, and retained path/missing/oversize refusals.
On unmodified code **three assertions failed**. The corrected reference group
runs **16 tests, 15 passed and one existing skip**.

```sh
python -m unittest discover -s tests -p 'test_reference*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
git diff --check
```

The existing Linux full-suite gate retains all tests. The Windows runtime-safety
lane now installs the already-pinned optional media dependency in its disposable
runner and runs the reference group explicitly. This changes no managed ComfyUI
Python environment. Final full-suite and hosted outcomes are recorded on the PR,
not inferred from the workflow definition.

## Compatibility and rollback

The returned field names, source-relative filename, exact encoded-byte digest,
20 MiB limit and oriented width/height semantics are unchanged. There is no
migration. Reverting the source change restores the former double-open behavior.

## Primary references

- [Pillow Image.open](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open): accepts a binary file-like object and lazily reads image data.
- [Pillow ImageOps.exif_transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose): applies EXIF orientation; it is not a new transform added by this patch.

## Reconciliation and operating boundary

Inspected main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, tree
`5e920817385cf6c6d4aef2154267eb6c0d0c4511`. The downloaded tracked-source
archive reproduced that tree before edits. No PR was open at the initial
check. The untouched offline suite ran **1,674 tests, 16 skipped, no failures**.
Optional/live cases were not executed. Existing Pillow deprecations, deliberate
storage-fault diagnostics and the exit-time socket ResourceWarning were retained.

This is a software-only maintenance slice. No owner database, source media,
configuration, model, runtime process or HUMAN_TODO decision was changed.
No generation, upload, download or new artistic/rights acceptance follows from
the fixtures. Independent review and owner-runtime acceptance remain separate.

## Native Windows fixture follow-up

The first hosted Windows lane passed the product compatibility cases but exposed
two path-interception fixtures that never reached their hooks: they compared an
unresolved temporary-directory spelling with production's resolved path. An
aliased-directory reproduction on Linux produced the same two failures. The
fixture now canonicalizes its temporary root before constructing its expected
source path; the same alias reproduction passes. No production code or assertion
was weakened. Native Windows rerun evidence is recorded separately on the PR.
