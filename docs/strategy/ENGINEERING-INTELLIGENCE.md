# Engineering intelligence and emerging architecture

This document captures patterns that are becoming visible across several implementations. They are opportunities for careful consolidation, not permission for a broad rewrite.

## 1. Revisioned commands and durable receipts

### Observation

Multiple domains now need the same reliability properties:

- immutable revisions;
- expected-head compare-and-swap;
- canonical command identity;
- identical replay returning the original result;
- changed bytes under the same identity refusing;
- committed-response loss remaining recoverable;
- append-only restore rather than destructive rollback;
- browser recovery state kept separate from server authority.

These behaviours appear in workflow documents, asset metadata, reviewed setup application, collections and planned project services.

### Direction

Issue #314 should extract a small Workspace-backed toolkit after comparing exact semantics. Domain services should retain validation, payload types and user-facing state names. The shared layer should own only persistence, conflict and receipt invariants.

### Avoid

- a generic JSON command endpoint;
- speculative event sourcing;
- pretending filesystem/model operations are transactionally atomic with SQLite;
- rewriting every service before two migrations prove value.

## 2. Safe captured media

### Observation

Recent fixes repeatedly concern the same boundary:

- bounded byte capture before allocation;
- encoded versus EXIF-oriented dimensions;
- animation/still contracts;
- frame count;
- pixel and canvas budgets;
- alpha and hidden RGB semantics;
- colour/profile declarations;
- source hash and derivative identity;
- explicit ownership and closing of decoded buffers.

Repair Studio already defines much of this rigor, while reference intake, I2V diagnostics, native export and Workspace publication have solved related pieces separately.

### Direction

Define an internal **captured media record** with explicit byte identity, geometry, frame/mode/alpha facts, declared limits and normalised derivative references. Consumers may impose stricter policies, but should not reimplement capture consistency.

The record must not imply colour certification, decoder equivalence with every native node or a lease on mutable source files.

## 3. One canonical Comfy schema normaliser

### Observation

Repository validation, live validation, Workflow Studio and execution preflight have historically interpreted Comfy descriptors differently. Dynamic V3 widgets, union sockets, socketless literals and native-only controls make duplicated rule sets unreliable.

### Direction

Create one source-derived schema normalisation and compatibility library consumed by:

- catalog validation;
- live/backend-specific graph checks;
- Workflow Studio diagnostics;
- authored-graph preparation;
- adapter capability reporting.

Every adapter should declare support as one of:

```text
editable | serialisable | executable | native-only | unsupported
```

Preserve raw descriptors and backend identity. Normalisation must not execute third-party node code or imply installed model compatibility.

Issue #97 remains the immediate correctness owner; #119/#121/#122 own broader authoring and execution capability.

## 4. Semantic graph roles above raw node IDs

### Observation

The catalog's `[node_id, input_name]` allow-list is simple and effective, but important meanings are increasingly hidden in raw identifiers. The face/hand denoise conflict in #254 is an example: two targets had different authored intent while one shared control fanned out mechanically.

### Direction

Gradually annotate important authored controls with semantic roles such as:

- `primary_sampler.seed`;
- `face_detail.denoise`;
- `hand_detail.denoise`;
- `identity_reference.image`;
- `final_output.image`.

Resolve roles to raw graph fields at validation time. Execution still uses exact graph bytes and IDs. Semantic roles should improve stability, review and diagnostics without claiming arbitrary third-party graph understanding.

## 5. Stage-aware resource admission

### Observation

A graph can fit model loading and sampling yet fail in decode or host-side movement. Physical RAM, Windows commit and VRAM are different limits. Browser cost is only one contributor.

### Direction

#178 should represent observed feasibility per exact workflow shape, backend/build/model identity and stage:

```text
load | encode | sample | decode | export
```

Admission should use fresh state after queue wait, record why it allowed/refused and retain unknowns. Estimates are not guarantees; old success under a different runtime is not current proof.

The initial benefit is not maximum throughput. It is avoiding predictable long-running failures and deferring competing Studio-owned background work.

## 6. Cheap projections over authoritative state

### Observation

Full Workspace, job and health payloads are expensive to poll and parse as history grows. The browser should remain a disposable observer, not a second state owner.

### Direction

Continue #175/#177 with bounded summaries, revision/epoch identities and conditional reads. Push events, if justified, should be invalidation hints followed by authoritative reconciliation. Do not introduce another job journal or forward binary previews by default.

## 7. Explicit browser state ownership

### Observation

Plain JavaScript remains viable, but complexity is now expressed through request epochs, local drafts, cross-tab locks, dialogs, recovery envelopes and several global surfaces.

### Direction

Keep the no-build deployment for now while strengthening:

- module ownership of each state object;
- JSDoc types and `// @ts-check` where practical;
- pure projection functions for rendering decisions;
- named lifecycle/disposal methods;
- request deadline/epoch helpers;
- fewer ambient globals and direct cross-surface mutations.

A framework rewrite is justified only if measured maintenance cost exceeds the migration risk. Current evidence does not establish that.

## 8. Domain modules, not framework replacement

`ThreadingHTTPServer`, SQLite and plain files are appropriate to the deployment model. The pressure is module size and responsibility, not scale-out infrastructure.

Refactor when a domain has its own persistence, commands, tests and failure vocabulary. `production.py`, `server.py` and large browser files should lose responsibilities to already-visible domains rather than be reformatted wholesale.

## 9. Testing and CI as a product subsystem

### Direction

Use four evidence tiers:

1. **Focused causal tests** — required for the changed seam;
2. **Shared contract tests** — required where a common owner changes;
3. **Merge/full suite** — broad integration confidence;
4. **Owner/native/neural acceptance** — explicit, finite and never inferred from CI.

PR workflows should avoid rerunning every expensive lane for unrelated files, while a merge queue or periodic full run protects integration. Persistent `ResourceWarning`s and full-suite-only interference should be treated as owned defects, not normal noise.

## 10. PR evidence architecture

Detailed evidence is valuable, but its reader location matters.

- PR first screen: outcome, user impact, risk, changed files, verification and remaining gap.
- Reconciliation document: causal history, commands, hashes and compatibility.
- CI artifact: generated receipts, screenshots and raw logs.
- `STATUS.md`: current product truth, not per-PR narration.
- `CURRENT_STATE.md`: historical evidence ledger.

Issue #315 owns this operating model.

## Recommended extraction order

| Priority | Consolidation | Trigger |
| --- | --- | --- |
| P0 | canonical schema normalisation | #97 correctness and #122 execution depend on it |
| P0 | stage-aware resource admission | prevents known expensive failures |
| P1 | safe captured media record | at least three current consumers share invariants |
| P1 | revision/receipt toolkit | #314 proves two real domain migrations |
| P1 | semantic graph roles | apply to high-value maintained graphs first |
| P1 | bounded read projections | Workspace/history scale evidence justifies it |
| P2 | stronger JS typing/module lifecycle | incremental maintenance improvement |
| Park | framework/backend rewrite | no demonstrated product benefit |

The purpose of consolidation is to make proven behaviour easier to retain. It should not become another architecture programme detached from accepted creative work.