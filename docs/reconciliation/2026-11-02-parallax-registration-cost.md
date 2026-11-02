# Parallax registration cost — 2 November 2026

Refs [#1882](https://github.com/Chris0Jeky/local-asset-studio/issues/1882).

## Trigger and retained failure

The full suite for comparison PR #1910, head
`1c231a9536ce7ffbe48eeae95acdca67480c76de`,
[run 41390327206, job 125100145768](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41390327206/job/125100145768),
exited 124 after **1200.05 seconds**. Its log records 6,751 completed tests and
ordinary progress into `test_workspace_run_labels`; it contains no reported
assertion or resource-warning failure. This remains a failed qualification.

The adjacent passing #1909
[run 41390323454, job 125100062783](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41390323454/job/125100062783)
completed 6,776 tests in 882.399 seconds. Its matching 6,751 completed tests took
846.825 seconds, versus 1139.251 in the failed run: broad slowdown across several
modules. Parallax's completed tests account for 165.912 seconds versus 112.876;
two existing real split route tests account for 60.979 and 60.515 seconds in the
failed run. The final Workspace-label module separately passed all nine tests.

The failed checkout was merge `71b7ba2da6e861d4fa3e7181eb9858a9fb783c51`, tree
`7c0189ff3d98a35234c04779d8840ee4f1c4f373`. The dedicated local baseline
`c76dc26a3898ddf84b91dbb2aa22ea45f5dbc622` has that exact tree. Both downloaded job
logs and the per-test timing comparison are retained outside Git. Their SHA-256s:

- Failed log: `9455476714b06ff4592e2529e5f6768fdd1353e421669c5844dd9611896f7095`.
- Adjacent passing log: `409d38220fe2f6a120d9fbcdabe38fab49d4dd750b22c32890c519d5c914cdf0`.

## Bounded change

Each registration candidate built two weighted histograms merely to sum the
difference and window pixels. `edge_map` supplies 8-bit, single-channel `L`
images. Summing their raw bytes gives the same exact integer masses directly.
The 64-by-64 fine patches have at most 1,044,480 units of edge mass; the coarse
patches are smaller. These totals and their combined denominator are far below
the range where the former floating-point histogram totals lose integer precision.

Only the two per-candidate totals and the once-per-search patch total change.
Candidate enumeration, energy ranking, tie order, coarse/fine radii, 48-patch
limit, scoring formula, affine fitting, registration fallbacks and layer
construction retain their existing code. `ImageStat` remains in use elsewhere.

## Causal checks and workload equality

The new operation-count regression failed on the original implementation:
one full 361-candidate search constructed **723 histograms**. Its five companion
tests already passed, covering every grey level, random edges, black/white
images, equal-score ties, clipped and empty windows, full coarse/fine searches,
and unchanged input bytes. All six pass after the change; the same 361 scores
now need no histogram construction. There is no wall-clock threshold in these tests.

The manual benchmark compares the retained original histogram search with the
production search, alternating which runs first. It checks every search's
ordered scores, winning offset and call sequence; complete registration/layer
records; raw image pixels and encoded PNG bytes; and input bytes before and after.
Both room splits compare all nine returned/intermediate PNG images. All six
workloads are exactly equal, including the fallback decisions and the largest
1536-wide multiple-of-16 canvas below the existing pixel bound: 1536 by 1040.

One local observation with Python 3.12.14, Pillow 13.0.0 and `tracemalloc=1`:

| Workload | Original seconds | Byte totals seconds | Original histogram calls | Byte totals histogram calls |
| --- | ---: | ---: | ---: | ---: |
| All 48 coarse and fine searches, 19,680 candidate scores | 9.166 | 1.808 | 39,456 | 0 |
| Shifted room, both registered edits and full layer split | 35.828 | 7.852 | 152,552 | 1,163 |
| Unchanged room, both registered edits and full layer split | 31.672 | 7.953 | 153,344 | 1,163 |
| Unrelated resized edit, fallback | 6.778 | 1.663 | 35,091 | 288 |
| Flat image, fallback without candidate searches | 0.051 | 0.043 | 288 | 288 |
| Largest bounded canvas, registration and residual check | 18.640 | 6.895 | 84,016 | 5,104 |

Remaining histogram calls belong to unchanged energy ranking, colour and mask
operations. Timings include identical trace-digest collection and PNG encoding.
They are observations on one host, not a throughput guarantee or an estimate of
the complete hosted suite. The benchmark receipt SHA-256 is
`89637643d2473c6be64e6bdb52dcaf2641b9440aefede8ff17fa8839ac5f025d`.

The complete focused `test_parallax*.py` group passed **46 tests in 65.791 seconds,
with no skips**, through the existing lifetime worker with allocation tracing,
resource warnings and coroutine warnings enabled. It reported no retained
non-daemon thread or active child process at shutdown, and the complete log has
no resource warning or unawaited-coroutine warning. The two existing full split
route tests passed in 17.522 and 14.662 seconds on this local run. The static
repository validator also passed: 98 preset bindings and 194 pinned assets.

Reproduce in the repository's Python/Pillow environment:

```console
python -m unittest discover -s tests -p "test_parallax_registration_cost.py" -v
python -X tracemalloc=1 tests/benchmark_parallax_registration.py --out .runtime/parallax-cost/benchmark.json
python -u -X tracemalloc=1 -X faulthandler -W always::RuntimeWarning -W always::ResourceWarning tests/full_suite_lifetime_worker.py --pattern "test_parallax*.py" --traceback-after 570 --shutdown-traceback-after 15
python scripts/validate-repo.py
```

The existing test cases, fixture dimensions, worker waits, lifetime instrumentation
and 1,200-second hosted gate are unchanged. Fresh qualification of the new combined
head is required before merge; the earlier timeout cannot qualify it. This is
offline algorithm/route evidence, with no GPU generation or owner art acceptance.
The open `parallax-layers-1219` decision remains in `HUMAN_TODO.md`.
