# Figure splitting: one crop in flight

15 September 2026. #399 under #360/#177/#172. Inspected main
`b29205cfc95ca4e64d72ae38d53df30c83968997`; original module blob
`ac2ac637ea27237c4e08e75bd0423f825b0d5ae2`.

## Source and decision

The supplied *Low-Level Engineering Optimisation Audit and Roadmap*, pp. 8-9,
recommends allocating by lifetime and avoiding decode/conversion copies; p. 22
proposes a copy ledger. Those principles motivate this implementation. The
Python/Workspace call sites and results here are repository-specific evidence,
not claims that the source report inspected them.

The existing figure splitter encoded every requested crop into retained PNG
bytes before publishing any snapshots. This pass changes only that preparation
boundary, leaving the ongoing #379 browser work and split API unchanged.

| Lifetime | Previous preparation | New preparation |
| --- | --- | --- |
| Decoded parent | Full RGB/RGBA canvas | Same full canvas |
| Pixel crops | Relied on scope/GC | Explicitly closed after each snapshot |
| Encoder buffer | Per crop, implicit release | One explicitly scoped BytesIO |
| Encoded payload | List containing every crop | Borrowed buffer view during one snapshot |
| Retained results | Rectangles, boxes and PNG bytes | Rectangles, boxes, paths, hashes, lengths |
| Publication | After every crop encoded | After each crop, before the next encode |

First derive all integer boxes and check the aggregate 80 MP budget. A budget
refusal performs no crop, PNG encode or snapshot publication. Then crop -> encode
-> snapshot -> release -> next crop. `BytesIO.getbuffer()` supplies a borrowed
view to the existing hash/write path; the view is released before closing the
buffer. This removes aggregate encoded-byte retention, not source decoding or
Pillow's internal allocations. The parent still supports up to 40 MP and each
single crop can remain large. Concurrent requests are not globally memory-budgeted
by this change; #178 retains that responsibility.

## Storage and fidelity contract

The helper returns private metadata rather than bytes. The only production caller
consumes it directly, preserving authored order, UUID derivation, source geometry,
PNG encode options and resulting content hashes. The final `BEGIN IMMEDIATE`
still rechecks Workspace, request and parent before adding all children plus the
receipt in one transaction. Hash, lineage, alpha, ICC and exact-replay behavior
remain unchanged. No recipe/model/generation/acceptance state is changed.

Filesystem publication is **not atomic with SQLite**. If crop 2 fails after crop 1
has been snapshotted, crop 1's immutable PNG may be unreferenced. Earlier code had
the same possibility on snapshot/DB failure; this now also applies to later encode
failure. Never delete a hash-named snapshot on rollback: another operation may
already reference it. Temporary `.part` files retain the existing cleanup rule.
The parent, DB rows and existing receipts are not deleted. Exact retry can reuse
those snapshots without creating duplicate child identities.

## Tests and measurement

Nine focused tests first produced 11 expected assertions/subtest failures on the
verified original module; the candidate passes all nine. Tests observe real crop
and snapshot sequencing, preflight-before-work, buffer views, real PNG/hash
parity for RGB/RGBA and hidden RGB, duplicate content, 32 selections, encoder/
fsync/snapshot faults and explicit crop/canvas/buffer closure.

Four additional tests use the actual Workspace SQLite service: second snapshot
failure followed by exact retry, receipt-write rollback, aggregate preflight and
parent lifecycle changes before commit. They and existing HTTP/split tests run in
the complete hosted tree. The new Windows lane explicitly includes these files;
local focused tests are not represented as a full-checkout suite.

A synthetic duplicate-heavy workload uses one deterministic 2048x2048 RGBA canvas
and four identical full-canvas selections. Each selection must encode; snapshots
deduplicate by content. There are three fresh processes per implementation, in
alternating order. The original measured path includes its separate snapshot pass;
the candidate includes snapshots inside preparation. No database or source decode
is timed. Every output PNG/box/order/hash matches. [All six trials](evidence/figure-crops-2048.json).

| Measurement | Original | Candidate |
| --- | ---: | ---: |
| Median process peak RSS | 221.96 MiB | 174.04 MiB |
| Median crop preparation + snapshot time | 2648.16 ms | 2638.49 ms |
| Time range | 2574.00-2737.08 ms | 2635.82-2705.89 ms |

Observed median RSS reduction: **47.92 MiB**. Python 3.13.5, Pillow 12.3.0, Linux
x86-64. Process peaks include fixture generation/imports. Timings overlap: no
speed improvement is established. This is neither Windows commit/VRAM, model
inference, a normal non-overlapping-sheet baseline nor whole-workflow performance.
Do not add this saving to other microbenchmarks. Three samples do not qualify tails.

## Reproduce and rollback

```bash
mkdir -p .runtime
git show b29205cfc95ca4e64d72ae38d53df30c83968997:studio_workflow/addressable_figures.py > .runtime/addressable_figures_baseline.py
python -m unittest discover -s tests -p 'test_figure_crop*.py' -v
python tests/benchmark_figure_crops.py --baseline .runtime/addressable_figures_baseline.py --candidate studio_workflow/addressable_figures.py --edge 2048 --crops 4 --repeats 3
```

Revert the preparation helper and its single caller together. No DB migration,
source rewrite, model change or stored-receipt rewrite is needed. Final full-tree
CI evidence is recorded in the PR discussion. Local GitHub DNS prevents cloning;
the local source was reconstructed and verified against the pinned Git blob.

The remaining #360 error-class/schema coupling/rounding observations are separate;
this slice does not silently resolve them. Creative and first-use decisions in
HUMAN_TODO remain with the owner.
