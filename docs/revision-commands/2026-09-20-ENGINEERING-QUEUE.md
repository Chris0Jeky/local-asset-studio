# Difficult-work map — 20 September 2026

Inspection anchor: main `f8fcc40f7388c23d13309c20c2776017a20004b2`, matching the
owner-supplied ZIP archive comment. Live issue/PR state was checked through the
GitHub connector. This is a dated engineering assessment, not a live status feed.
An open parent issue is not evidence that its original implementation is missing.

## Highest engineering difficulty

| Lane | Why it is difficult | Reconciled state / next boundary |
| --- | --- | --- |
| #245 protected crop transforms and effective write masks | Pixel-centre transforms, noninteger scales, interpolation support, padding, alpha/tRNS, provenance and stale-source refusal must agree without hidden resizing. | No replacement compositor. Start from #244 normalized-source/extraction contracts; preserve the legacy packet path. Synthetic pixel proof and private seam/hand review are distinct. |
| #314 shared revision commands and receipts | Canonical identity, immutable revisions, durable replay, ambiguity and journal bounds across domain adapters without building an event-sourcing framework. | Shared values/adapters and verification documents already exist on main. Audit retained contracts; do not implement a second toolkit merely because the parent remains open. |
| #671 mutable narration-profile CAS | Competing processes, predecessor identity, registry+receipt atomicity, crash points and response-loss replay. | A genuine missing mutation boundary. It is not the read-only catalogue overlay. Reconcile the #653 → #669 → #676 stack first. |
| #388 collection draft / pending-command recovery | Browser-local intent, exact replay, current versus historical receipts, two-tab revisions, replacement Workspace, storage failures and late replies. | #387 server transactions are already merged. This pass implements the missing browser recovery layer and a native verification lane. |
| #673 pinned Qwen3-TTS producer | Exact runtime/model/reference identity, resource admission, stable reusable voice versus design, artifact production and uncertain Start recovery. | Depends on the narration stack/policy. Offline contracts can be implemented here; actual workstation execution and subjective voice qualification cannot be replaced by synthetic WAVs. |
| #638 aggregate Spoken Brief production | Parent/child identities, partial completion, explicit Start, no duplicate inference, segment replacement and deterministic reassembly. | Reuse the existing worker and coordinator; no second inference queue. Source/profile/artifact identity is the critical integration seam. |
| #178 staged resource admission | Reservations for exact graph/backend/model demand, concurrency, rollback and durable ownership of holds. | Active #656 → #674 stack already owns implementation and publication hardening. Do not duplicate it; machine calibration remains separate. |
| #120 workflow modules and reversible execution | Exact inverse preconditions, document/module identity and execution snapshots across client/server. | Substantial implementation and verification already exist on main. Remaining acceptance is not a blank architectural task. |

## Execution order for unowned, testable work

1. **#388 first:** finish the browser half of an already-merged durable server
   protocol. Deliver code, exact-receipt tests, native CI, and an honest recovery
   boundary. Do not close the parent based only on inert-browser evidence.
2. **#608 next:** separate known-prompt observation from resource-consuming admission
   in the ordinary resume path. Require behavioral tests both ways: retained holds
   admit known observation and still reject new work. This is a bounded remaining
   child of #458, not permission to relax all worker guards.
3. **#245/#244 next substantial architecture lane:** first freeze normalization,
   transform/coverage representation and legacy compatibility; then implement exact
   synthetic pixel tests before any model adapter. Real artistic evidence stays open.
4. **#671 after its stack:** add an owned mutable update boundary, not more CAS prose
   around catalogue-bound overlays. Gate concurrent-writer and crash outcomes first.

This ordering considers dependency readiness and existing ownership as well as raw
technical difficulty. It deliberately avoids opening another implementation of
already-active resource, narration or pose work.

## Preserve existing work

The inspection found active #647 → #675 figure-intake hardening, #660 pose-route
reconciliation, #670 pose redo correction, #654 shortlist keyboard focus, #672
reference-review state protection, and the narration/resource stacks above. Their
existence is not merge approval. Review exact heads and branch bases before reuse.

#661 records unique stale branch recovery candidates. No unique branch is deleted
by this pass. #595's concern about self-patching write-permissioned CI is respected:
publication uses GitHub-native blobs/trees/commits; CI only tests.

The product outcome remains #313's accepted character-pack workflow. Software
correctness, actual GPU/runtime execution, human visual/voice acceptance and licence
scope are different evidence classes. Open HUMAN_TODO decisions are unchanged.
