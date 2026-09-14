# Protected-pixel comparison: bounded scratch evidence

14 September 2026; #363; source intake/architecture PR #365. This PR is stacked on the review-copy PR #366 to reuse its finite CPU benchmark harness. The implementations change different production functions.

## Change

`scripts/character_edit_pixels.py:changed_mask` delegates to a pure Pillow helper. It compares at most 512×512 pixels at a time, converts only those regions to RGBA, takes the maximum difference over **all four channels**, and returns the same full-size binary L mask. Hidden RGB under alpha zero is still significant. Input images, full decoding/compositing and the necessary L output remain full-size; this is a bound on scratch, not a claim of streaming the entire edit workflow.

The helper uses `contextlib.closing` and explicit retirement of intermediate maxima. Inspection and failing fault tests showed that the installed Pillow base Image context manager does not release image-core storage; a bare `with image` was not sufficient to prove deterministic scratch closure. The implementation was corrected before publication, and the final benchmark was rerun. Caller-owned images and the returned mask remain usable.

No changes to `_verify_bundle`, source hashes, profile equality, masks, output publication, approval state or model execution. Reverting the delegation restores the previous algorithm without migrating any stored data.

## Correctness and resource gates

Initial red run: 10 helper tests, six expected subtest/assertion failures covering unbounded difference work and missing failure-path cleanup. The final local run has **12 passing helper tests**, including normal and exceptional ownership, all channels/alpha values, nine image modes, mixed modes, palette/tRNS, odd/wide/tall/boundary and empty sizes, source immutability and unchanged dimension errors. Allocation-shape checks inspect real Pillow difference calls; injected failures cover difference, channel extraction, reduction, threshold and paste.

Two additional tests exercise the **actual protected-edit entry point** in the complete repository; those and the existing protected-edit/full offline suites run through hosted CI. They are not represented as locally executed in the extracted-module environment.

## Synthetic CPU evidence

Python 3.13.5/Pillow 12.3.0 on Linux x86-64; two fixed 4096² RGBA inputs; five fresh processes per implementation in alternating order. Exact mask parity holds across all ten samples. [All trials and common identities](evidence/pixel-diff-4096.json).

| Metric | Original full-image algorithm | Tiled helper |
| --- | ---: | ---: |
| Median process-lifetime peak RSS | 414.92 MiB | 241.91 MiB |
| Median timed comparison | 650.00 ms | 177.19 ms |
| Timed comparison range | 378.40–752.06 ms | 168.67–404.56 ms |

Observed median peak reduction: **173.00 MiB** in this fixture. These are noisy, small-sample CPU measurements, not a guaranteed speed multiplier, Windows commit measurement, GPU saving or inference improvement. They compare a standalone extraction of the original algorithm with the helper, excluding the original module's other imports and the full edit pipeline.

The frozen baseline fixture preserves the original conversion/difference/split/reduction algorithm from `character_edit_pixels.py` at `1c9c1f85b69cbb26e5dd0ea6c1f3fa60969eb80a` (original file blob `7d62cf1273aafdade80316c8a18049c630854924`); its `require` dimension check is inlined as the equivalent ValueError guard. It is test/benchmark data only, not a runtime fallback.

```bash
python -m unittest discover -s tests -p test_pixel_diff.py
python -m unittest discover -s tests -p test_character_edit_copies.py
python tests/benchmark_cpu_copies.py --operation changed_mask --edge 4096 --repeats 5 \
  --baseline tests/fixtures/cpu_copy_pixel_baseline.py --candidate scripts/pixel_diff.py
```

The complete candidate still needs the existing hosted full offline lifetime suite and repository validator. Final CI evidence belongs in the PR discussion. No owner's Windows/AMD run or finished-art acceptance is claimed; #177/#178 and native-failure investigations remain open.
