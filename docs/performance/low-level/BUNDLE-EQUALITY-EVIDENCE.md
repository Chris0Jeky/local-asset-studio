# Bundle verification: bounded raw and RGBA equality

14 September 2026. Scoped #370 follow-up to #363/#368; stacked on #368.
Source recommendations are the supplied low-level audit pp. 8–9 and 22;
this implementation is a repository-specific adaptation, not a source claim.

## Contract and architecture

`character_edit_pixels._verify_bundle` already verifies the exact receipt,
source/plan/transform and file hashes. It then compares mode, dimensions, raw
pixels, converted RGBA pixels and ICC profile. This change retains every one of
those checks while replacing full-image byte strings with `pixel_diff.same_pixels`.

Raw and RGBA equality are **both** required: palette indices can differ while
rendering identically, or identical indices can use different palette colours.
RGB tRNS can change alpha without changing raw RGB bytes. RGB values under zero
alpha are still checked. ICC equality remains separate and caller-owned.

The helper compares at most 512x512 tiles, stops on the first mismatch and
allocates no full-size difference mask. Every owned crop/conversion closes on
success, early exit and exception. The verifier also closes its decoded candidate
image on success/refusal. Caller-owned expected pixels remain live.

Inputs, decoding, file hashing and other preparation/composition costs remain
full-size. This bounds the equality operation's scratch, not the entire edit
pipeline. There is no new cache, worker, dependency, source replacement, generation
or acceptance authority. Revert the call/import and helper to roll back; existing
sources, plans and receipts need no migration.

## Verification

Local red run: 14 tests against the original predicate, four expected failures
for full-image byte conversion, missing early exit and scratch ownership.
Final local run: **14 tests passed**, including nine modes, odd/empty/wide/tall
shapes, deterministic random cases, palettes, tRNS, hidden RGB, unchanged inputs,
normal/failure cleanup and preservation of the two-stage equality contract.

Six additional tests target the actual `_verify_bundle` function using temporary
PNGs and genuinely hashed receipts. They check bounded conversions, rehashed
hidden-RGB/transparency forgeries, ICC refusal, file-hash enforcement and decoded
image closure. These and existing protected-edit/full suites are run on the
complete hosted PR tree, not claimed as locally executed in this partial checkout.
The existing source hashing/receipt validators are not replaced with mocks.

## Measured CPU experiment

Two equal 4096x4096 RGBA images, so **every pixel is checked**; the benchmark does
not select a favourable early-exit case. Five fresh child processes per side,
alternating order; Python 3.13.5, Pillow 12.3.0, Linux x86-64. The extracted original
predicate and the candidate return the same Boolean result in all ten trials.
All input identities match. [Every trial and module hash](evidence/bundle-equality-4096.json).

| Measurement | Original predicate | Tiled equality |
| --- | ---: | ---: |
| Median process-lifetime peak RSS | 475.84 MiB | 226.76 MiB |
| Median timed predicate | 651.88 ms | 168.39 ms |
| Timing range | 235.62–913.42 ms | 159.28–183.92 ms |

Observed median peak reduction: **249.08 MiB**. RSS includes interpreter/import
and fixture setup. This is neither an exact allocation ledger nor Windows commit,
VRAM, model-generation or whole-bundle performance. Small/noisy samples do not
qualify p95/p99 or a guaranteed speed multiplier. Do not add these savings to
previous PR measurements: the operations and process peaks have different scopes.

The baseline fixture extracts the original `_verify_bundle` pixel predicate from
#368 head `897617ab586c74d5681328d2866a7db3ce89ef1f`; it does not add cleanup to the
original full-image conversions. Mode/size and both byte comparisons are included;
the caller's ICC/hash/disk work is not part of the timed predicate.

## Reproduce

```bash
python -m unittest discover -s tests -p test_pixel_equality.py
python -m unittest discover -s tests -p test_bundle_equality.py
python tests/benchmark_bundle_equality.py --edge 4096 --repeats 5 \
  --baseline tests/fixtures/bundle_equality_baseline.py --candidate scripts/pixel_diff.py
```

The manual harness reuses #366's fixture, identity, module-loading and process-RSS
helpers. It caps dimensions/repeats, runs each sample in a fresh process, retains
all rows and refuses result/input mismatches. Optional `--changed first` or
`--changed last` exposes early/late refusal cost; those are different workloads,
not mixed into the equal-image result above. On platforms without `getrusage`,
RSS is unavailable. No neural calls or private source assets are used.

Local repository acquisition failed DNS, so local tests cover extracted/isolated
modules. Final full repository and Windows integration evidence belongs in the
PR discussion with exact head/run identities. #370 remains open pending review;
#245/#71 and the wider resource/native-failure acceptance are not completed here.
