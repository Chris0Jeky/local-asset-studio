# Review decode: scoped minimum-copy evidence

14 September 2026; #362; architecture/source intake in PR #365. Baseline repository `1c9c1f85b69cbb26e5dd0ea6c1f3fa60969eb80a`, `app/review_media.py` blob `0f4687f16fbc8f212f01f265c15a7538f43b15d1`. The locally extracted baseline was verified against that Git blob hash before testing.

## Change and correctness

Avoid `ImageOps.exif_transpose` only for missing/normal/unrecognised orientation; EXIF 2–8 keeps the existing path. Return pixels, transform, stripped metadata and refusal rules are unchanged. No generation settings, caches, API routes or dependencies change.

`python -m unittest discover -s tests -p test_review_decode_copies.py`: baseline **12 tests, five expected subtest failures** (the redundant call for missing/0/1/9/65535 orientation); candidate **12 tests passed**. Coverage includes 66 supported-mode/orientation combinations, RGB/palette transparency, hidden RGB, JPEG/WebP, independent returned images, pixel cap, unsupported 16-bit input, animated PNG and malformed/truncated bytes.

## Measured synthetic CPU experiment

Python 3.13.5, Pillow 12.3.0, Linux x86-64; five fresh processes per implementation with alternating order. Fixed 4096×4096 RGBA PNG without EXIF. All input, decoded-output and transform identities match across the ten samples. [All samples and common identities](evidence/review-decode-4096.json).

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Median process-lifetime peak RSS | 284.64 MiB | 220.63 MiB |
| Median timed decode | 262.21 ms | 181.97 ms |
| Timed decode range | 186.72–334.72 ms | 162.84–339.02 ms |

Observed median peak reduction: **64.01 MiB** for this fixture. Timings are noisy and overlap; this is not a stable percentage speed-up, a tail-latency result or an inference measurement. RSS includes process setup and is captured before output verification; it is not an exact allocation ledger, Windows commit or GPU memory. The benchmark explicitly closes generated fixture pixels before decoding, rather than assuming Pillow's image context manager frees them.

## Reproduce

```bash
mkdir -p .runtime
# Preserve the real baseline module; do not compare a hand-written fast path.
git show 1c9c1f85b69cbb26e5dd0ea6c1f3fa60969eb80a:app/review_media.py > .runtime/review-baseline.py
python tests/benchmark_cpu_copies.py --operation decode --edge 4096 --repeats 5 \
  --baseline .runtime/review-baseline.py --candidate app/review_media.py
```

The manual harness caps edge/repeats, uses fresh child processes, checks output parity, retains all trials and returns unavailable memory on platforms without `resource.getrusage`. It does not run in the ordinary unit suite or contact a backend. `--edge 0` was also checked to refuse with exit 2.

Local tests used extracted target modules, not a full clone. The complete candidate must additionally pass the repository's existing hosted full offline lifetime suite and validator; final CI evidence belongs in the PR discussion. No owner's Windows/AMD runtime execution or art acceptance is claimed. Rollback is the scoped decode branch only; stored sources and receipts need no migration.
