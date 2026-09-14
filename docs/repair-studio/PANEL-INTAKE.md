# Reviewed panel proposals, previews and exact extraction

Implementation under #244 / #243, stacked on source-intake PR #268. This is a working CPU-only tool chain, not another declaration-only scaffold or a neural repair claim. It consumes the verified source packet from [source intake](SOURCE-INTAKE.md). The existing `character_media.py` and Studio server are unchanged.

## One-command synthetic demonstration

```console
python scripts/repair_panels_demo.py --out experiments/runs/repair-panel-demo-001
```

Choose a new directory. This creates an original synthetic nine-panel source (six figures, three portrait boxes), normalizes it, previews a reviewed manual layout, extracts the panels and verifies every decoded crop against the retained normalized master. Inspect `preview/preview.png`, `extracted/`, and `result.json`. These are geometric fixtures, not anatomical or artistic acceptance. No user artwork, model, network or native application is involved.

The demo intentionally includes partial layout variety and hidden RGB under transparent pixels. Its source and every crop remain unreviewed. `verified_exact_crops:true` is a mechanical result only. A failed demo leaves its partial directory for inspection; it never reuses or overwrites a previous run.

## Real source workflow

First create a source packet. No changes are made to `original.png`:

```console
python scripts/repair_source.py capture --image original.png --out experiments/runs/source-001
```

Make a grid proposal, with explicit horizontal/vertical gutter widths. A `--region x0 y0 x1 y1` can restrict the grid to one part of the page. Output is ASCII JSON. Save it as UTF-8/ASCII without a byte-order mark. The following redirection works in Bash, cmd and modern PowerShell:

```console
python scripts/repair_panels.py grid --source experiments/runs/source-001 --rows 2 --columns 5 --gutter 4 4 > layout.json
```

Windows PowerShell 5.1 uses a different default file encoding. There, replace `> layout.json` with `| Out-File -Encoding ascii layout.json`. Escaped JSON preserves non-ASCII labels without depending on the console code page. See the [official encoding reference](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding).

Alternatively, propose rectangles from near-white full-width/full-height separators:

```console
python scripts/repair_panels.py suggest --source experiments/runs/source-001 --min-gutter 4 > layout.json
```

**The whitespace proposal is not a panel or subject detector.** It examines at most two million normalized pixels, does not downsample, and may mistake whitespace inside a panel for a separator. For a larger source it explicitly asks for grid/manual boxes. A page without suitable separators becomes one whole-canvas proposal rather than a fabricated confident layout. Inspect every proposal. Nonwhite decorative frames, text, crossing artwork and incomplete figures need manual adjustment.

Edit `layout.json` as needed, then create a preview:

```console
python scripts/repair_panels.py preview --source experiments/runs/source-001 --layout layout.json --out experiments/runs/panel-preview-001
```

Inspect the numbered boundary overlay and the original. Copy the returned `layout_sha256` value into the extraction command below in place of `ACTUAL_REVIEWED_DIGEST`:

```console
python scripts/repair_panels.py extract --source experiments/runs/source-001 --layout layout.json --out experiments/runs/panels-001 --reviewed-layout-sha256 ACTUAL_REVIEWED_DIGEST
python scripts/repair_panels.py verify --source experiments/runs/source-001 --packet experiments/runs/panels-001
```

The digest acknowledges the exact layout bytes supplied, including serialization. It is **not authenticated reviewer approval**, not proof somebody looked at the preview, and not authorization for generation. Changing the layout after obtaining the digest requires a new acknowledgement. Outputs remain `review_state:unreviewed` even when a caller declares visibility `complete` or supplies a canon ID.

Each output directory must be new. The original source packet must remain available for verification. Read/propose/preview/extract perform no neural jobs, no Workspace metadata writes and no campaign registration.

## Layout contract

Root schema: `studio.repair-panels/v1`. Required fields: `schema`, `sheet_id`, `source`, `method`, `panels`, `overlaps`; unknown fields fail. Source identity contains normalized PNG hash, oriented dimensions and the exact source receipt hash. Changes are rejected, not silently rebased.

Every panel has an `id`, `box`, `role`, `label`, `instance_id`, `canon_id` and `visibility`. Coordinates are half-open normalized-source pixels: `[left, top, right, bottom]`. Grid partitioning uses integer boundaries and preserves the requested gutters without introducing a resize. `view`, `portrait` and `action` roles match the existing extractor. IDs, labels, bounds, counts and scalar types are checked before output publication; booleans are not coordinates.

A character appearing repeatedly has a distinct instance ID in each panel. Those instances can reference the same canon ID. Null instance/canon fields support a non-character panel. These IDs are caller declarations for downstream binding, not validation of an actual approved canon file or automatic recognition of which character appears.

Visibility is `unknown`, `complete`, `occluded`, `out_of_frame` or `ambiguous`. The tool never infers missing feet, correct anatomy or full-body completeness from a box. `source_edges` only reports geometric contact with the normalized canvas edges. Rectangular crops retain backgrounds, props and neighboring fragments. Subject segmentation, matting and hidden-body reconstruction remain separate #246/#248 operations.

Every pair of overlapping rectangles must appear exactly once in `overlaps`. Missing, extra or duplicate pairs are refused. Overlaps are permissible reviewed extraction geometry; they do not establish safe overlapping repair masks. Final write support and protected candidate composition remain #245.

Limits are 64 panels, 256 KiB layout JSON, 48 million total cropped pixels, and the shared 100 MiB aggregate artifact budget plus separately bounded receipt. Both writing and verification enforce the aggregate bound, not merely a per-file cap. An extraction that duplicates a large master in many crops may exceed the budget even if the source itself is valid.

## What is retained

An extraction packet contains:

- `master.png`: exact normalized-source bytes, not a recompressed copy;
- `layout.json` and `source-receipt.json`: exact captured inputs;
- `panel-<id>.png`: independently encoded RGBA crops with original decoded samples and supported colour chunks;
- `legacy-manifest.json`: a v1 handoff to the existing character-media extractor;
- `receipt.json`: final completion marker, individual byte/pixel hashes, source identity, coordinates, instance declarations and limitations.

The source module owns exclusive packet publication. It claims the new directory, writes/fsyncs artifacts, and publishes the final receipt without overwriting. Failed/partial directories stay inspectable. This is a cooperative single-user filesystem contract, not a hostile-writer or universal power-loss guarantee.

Verification uses the **same captured normalized bytes** it verified, not a later path reopen for crops. It re-derives every panel's expected RGBA pixels from its source box and checks metadata, manifests and the complete receipt. Updating a wrong crop's hash cannot make it valid. Alternate lossless PNG encoding is allowed only when the recorded byte identity, decoded samples and supported colour metadata match. Symlinked packet members, stale source receipts, changed master/layout, undeclared metadata and over-budget artifacts fail visibly.

Previews may be reduced to at most 1280 pixels in each dimension; the master and extracted panels are never resized. Preview coordinates derive from that scale only. The overlay is diagnostic and explicitly not colour managed; retained colour chunks on crops do not constitute ICC certification or general native-editor colour support.

## Compatibility with existing tools

The emitted v1 manifest can be passed to the unchanged extractor:

```console
python scripts/character_media.py extract --root experiments/runs/panels-001 --manifest experiments/runs/panels-001/legacy-manifest.json --out experiments/runs/legacy-panels-001
```

A real integration test invokes the repository's actual `character_media.extract` and compares every resulting panel's decoded pixels. The new extraction receipt is not passed to the fixed 13-panel review-card compositor; generic final-sheet composition remains #256. Do not infer a rig, sprite animation or neural repair from either extraction.

The implementation uses small source/panel modules instead of expanding the old combined extractor/compositor into an independent Studio. It creates no server, queue, model registry or database. Future #251 UI/SDK commands should call these boundaries through existing Workspace ownership rather than maintain another source copy as authoritative project state.

## Verification and causal findings

At the local final check, the two implementation slices ran **62 tests: 61 passed, one skipped**. The local skip is the actual legacy-extractor test because the container could not clone the complete repository (GitHub DNS failed). It must run in the full hosted checkout. No local full-repository pass is claimed.

Additional adversarial tests reproduced and corrected two panel verifier gaps: an externally symlinked layout was followed; and per-file byte limits did not enforce the aggregate completed-packet limit. Both now fail before a false valid result. A related source-packet aggregate verification gap was corrected in parent PR #268 with its own regression. A deliberately altered pixel, rather than identical re-encoded bytes, is used for the changed-master fixture.

Coverage includes grid arithmetic and gutters, manual mixed aspects, source/receipt replacement, same-canon distinct instances, exact overlap declarations, stale raw layout digest, original/alpha/colour retention, rehashed wrong crops, symlinked members, bound exhaustion, real CLI subprocesses, no network calls and the complete synthetic demonstration. The nine-panel annotated preview was visually inspected; this supports layout readability for that fixture, not general Studio/browser accessibility or art acceptance.

```console
python -m unittest discover -s tests -p "test_repair_*.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The existing Repair intake contracts lane runs the focused tests on Linux and Windows; ordinary Check studio runs the full repository suite. Record their actual final-head results in the PR. Skips and synthetic evidence must not be counted as real GPU, owner-art or native application acceptance.

## Remaining #244 work

The CPU path now supplies explicit normalized intake, proposals, editable layouts, previews, exact extraction and verified legacy handoff. The issue remains open for the guided browser boundary editor/Workspace integration and a privately reviewed real-sheet workflow. Source formats beyond the deliberate PNG subset require explicit normalization policies. Neural masked repair, scaled candidate transforms and model quality are not implemented by this slice; #245 is the next mechanical dependency.
