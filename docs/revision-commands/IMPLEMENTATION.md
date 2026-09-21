# Revision command implementation and compatibility plan

Source checkpoint: `67f995f245518b36fb0192a61da780d337d53028` (19 September 2026).
Issue order: #314, #120, #387. One explicit stack, with local verification; no hosted test or automated-review result substitutes for author verification.

## Shared values (#314)

The extraction already exists in `studio_workflow/revision_consistency.py`, and both `documents.py` and `setup_drafts.py` consume it. Preserve those migrations, their public error contracts, and their existing canonical-digest receipts. Do not introduce a storage framework.

Add an opt-in `exact_stored_value(raw, stored_sha256, *, max_bytes)` fact for new byte-bound receipts. It must retain the received bytes, enforce a caller-selected bound before JSON decoding, use the strict existing decoder, and compare the digest of those exact bytes. The existing `stored_value()` deliberately continues comparing canonical JSON, including legacy whitespace compatibility. Domain code owns refusal, table names, schema versions, transaction boundaries and recovery advice.

Proving checks: existing value tests plus exact UTF-8 boundaries, malformed JSON, duplicate/reserved keys, nonfinite/deep JSON, exact-byte versus canonical identity, invalid limits, digest mismatch, and architecture independence.

## Workflow documents (#120)

Keep append-only revisions, request identity, the existing commands, graph compiler, named Steps and durable restore. Extend the same model rather than inventing a parallel graph engine.

* Add explicit reversible command planning over complete authoring state. Undo must retain disconnected/disabled nodes, dangling consumer links, Step controls, positions, bypasses, metadata and source lineage. A stale expected revision must still refuse at the existing transaction boundary.
* Add versioned, bounded portable Step modules with explicit mappings for every inserted node and every external input. Never guess a connection, rewire an outside consumer, select a copied output, change backend identity or stage an asset automatically. Preserve source revision provenance. Import is one atomic command through the same preview/commit path.
* Separate selected executable identity from the existing exact compiled-graph identity. Keep legacy `graph_sha256` unchanged so stored execution proofs are not invalidated. Layout, node labels and Step presentation must not change the new execution-only identity; actual executable input changes must.

Proving checks: pure commands, export/import isolation, missing/extraneous bindings, collisions, cyclic/dangling drafts, nested/oversized inputs, all-or-nothing failure, reversible state, exact historical replay, two real SQLite writers, reopen, and transport-level tests with no model backend.

## Collections (#387)

Keep authority in `AssetWorkspace` and its database. A separate domain module owns collection validation and SQL; the shared layer owns only values. Migrate existing collections deterministically without changing IDs or media. Add a separate versioned receipt journal, strict Workspace-scoped request envelopes and revision preconditions. Preserve the explicitly documented legacy path only where it cannot silently downgrade a versioned request.

For each new command: validate bounded JSON; `BEGIN IMMEDIATE`; check the Workspace identity in that transaction; inspect the typed receipt before allocating any ID or reading current entity state; return the original exact result or refuse changed content; enforce expected revision and safe-integer limits; mutate; persist the byte-bound receipt; commit together. A failure to confirm commit is ambiguous, not permission to allocate a new request ID. Unknown status cannot cancel an in-flight writer.

Collection deletion preserves media, removes membership through the existing foreign key, and increments every affected asset's metadata revision exactly once. Refuse the entire deletion before any write if a collection or asset revision would overflow. Current observations remain outside immutable historical receipts. Journal limits refuse new writes, never erase evidence or make old IDs reusable.

Expose read-only status through the existing handler-composition seam with loopback checks, strict query parsing and structured storage errors. No second server, queue, runtime or automatic retries.

Proving checks: migration/reopen, ordered canonical replay, changed reuse, historical-current divergence, response loss, two connections, replaced Workspace scope, deletion preservation and overflow, rollback after injected receipt failure, corruption without repair, exact bounds, status with no writes, malformed HTTP bodies and origin checks.

## Evidence and remaining acceptance

Each PR records actual local commands and outcomes, tested blob identities, self-review findings and remaining issue acceptance. A selected-source local checkout is not a full repository suite. Browser/native creative acceptance is never inferred from Python tests. `HUMAN_TODO.md` remains owner-controlled and unchanged.
