# Figure-crop acceptance hardening (#252)

This change builds on the already merged crop/lineage/editor work, including the
nearest-pixel and image-format corrections in PR #560. It does not rebuild those
features or claim their original implementation as new work.

## Corrected defects

Pillow pixel decoding alone accepted malformed PNG containers: a file with
complete image pixels but no final IEND chunk, a file with a damaged IDAT
checksum, and a valid image followed by bytes that Pillow ignored after the first
IEND. The first correction checked only the final 12 bytes, which a second
canonical IEND could bypass. The final source intake checks dimensions and frame
count, walks the bounded PNG chunk stream without allocating chunk copies, verifies
every chunk CRC, requires the first valid zero-length IEND to end the file, closes
that view, and then lets Pillow verify and decode a fresh bounded view. A failed
container check creates no child records or success receipt. Existing PNG/JPEG/WebP
format restrictions and allocation bounds remain unchanged.

Each new child also records `parent_metadata_revision` as observed in the final
Workspace transaction and `crop_coordinate_policy: basis-points-nearest-half-up/v1`.
The content hash remains the immutable pixel identity. Metadata revision is
provenance, not a new condition that rejects unrelated parent title edits.
Historical child receipts remain readable and exact replays are not rewritten.

Every edge uses `(basis_points * dimension + 5000) // 10000`. Pixel rectangles are
half-open. Adjacent rectangles share one rounded boundary. Empty raster crops are
refused rather than expanded; all crop boxes and aggregate size are checked before
any child PNG is published. Three-pixel RGBA fixtures reassemble exactly, including
transparent pixels and their stored color channels.

## Regression-first record

- The original branch reproduced missing-IEND and damaged-IDAT-CRC acceptance before
  the initial source-integrity correction.
- Commit `b6b7a2181101a640f49759813243f8ce9339fabe` adds the duplicate-IEND/trailing-byte
  bypass before the final parser correction.
- Commit `d4199f861c09acede7a0a616425b712aaa4ed7a0` replaces the suffix heuristic with
  the bounded chunk walk and terminal-first-IEND rule.

## Local verification

```console
python -m unittest discover -s tests -p "test_addressable_figure*.py" -v
python -m unittest discover -s tests -p "test_figure_crop*.py" -v
node tests/addressable_figures_frontend.cjs
python tests/addressable_figures_browser.py --out /tmp/figure-browser-evidence
```

The original local run completed 18 addressable-figure and 13 figure-crop Python
tests, 10 JavaScript contracts, and eight native Chromium browser scenarios:
ordered children, exact ambiguous retry, local persistence failure, cross-source
refusal, late response binding, pointer threshold, coalesced refresh and refresh
failure with a retained confirmed receipt. The browser transport is explicitly
inert; these tests do not submit generation or establish artistic quality.

The final exact-head hosted workflows are the merge gate for the additional
terminal-IEND regression and complete repository integration. No Codex review result
is used as correctness evidence.

## Remaining broader acceptance

The existing real-workstation acceptance remains: an owner-reviewed multi-figure
sheet, a resulting child taken through a compatible repair recipe, and the actual
parent/child hashes, prompt ID and reviewed result in `experiments/curated/`.
Synthetic tests must not be published as that evidence. Therefore this PR refers
to #252 without automatically closing the broader issue.
