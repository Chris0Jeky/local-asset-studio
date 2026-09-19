# Figure-crop acceptance hardening (#252)

This change builds on the already merged crop/lineage/editor work, including the
nearest-pixel and image-format corrections in PR #560. It does not rebuild those
features or claim their original implementation as new work.

## Corrected defects

Pillow pixel decoding alone accepted two malformed PNG containers: a file with
complete image pixels but no final IEND chunk, and a file with a damaged IDAT
checksum. Both were reproduced against the exact current-main figure module
before the correction. The source intake now checks dimensions and frame count,
verifies the container, checks a complete terminal PNG IEND (including its checksum),
closes that view, and decodes a fresh bounded view. PNG trailing bytes are refused. A
failed container check creates no child records or success receipt. Existing
PNG/JPEG/WebP format restrictions and allocation bounds remain unchanged.

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

## Local verification

```console
python -m unittest discover -s tests -p "test_addressable_figure*.py" -v
python -m unittest discover -s tests -p "test_figure_crop*.py" -v
node tests/addressable_figures_frontend.cjs
python tests/addressable_figures_browser.py --out /tmp/figure-browser-evidence
```

The first two commands ran 18 and 13 tests with no failures. The JavaScript suite
passed 10 tests. Native Chromium completed eight browser scenarios: ordered
children, exact ambiguous retry, local persistence failure, cross-source refusal,
late response binding, pointer threshold, coalesced refresh and refresh failure
with a retained confirmed receipt. The browser transport is explicitly inert;
these tests do not submit generation or establish artistic quality.

The baseline figure module was matched to main blob
`4a91957134516dd78f2330d9cdfe7f6501f05cb8` before editing. Verification was local;
no cloud Actions or Codex review was used as correctness evidence.

## Remaining broader acceptance

The existing real-workstation acceptance remains: an owner-reviewed multi-figure
sheet, a resulting child taken through a compatible repair recipe, and the actual
parent/child hashes, prompt ID and reviewed result in `experiments/curated/`.
Synthetic tests must not be published as that evidence. Therefore this PR refers
to #252 without automatically closing the broader issue.
