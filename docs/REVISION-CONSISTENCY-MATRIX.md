# Revision consistency fault matrix

Issue: #386. This document records the frozen, pre-refactor behavior that #385 must preserve.

## Scope

`tests/test_revision_consistency_matrix.py` runs the same fact-level assertions against the real SQLite-backed public services for:

- `WorkflowDocuments`;
- `SetupDrafts`.

The adapters remain deliberately small and domain-typed. They translate only four observable facts: current head, retained revisions, retained request receipts, and bytes counted by that domain's existing history budget. They do not introduce a generic command endpoint or claim that file copies, model state, or any external side effect are atomic with SQLite.

## Shared matrix

| Fault or transition | Required observation |
| --- | --- |
| Same request identity and same canonical bytes | Original historical result is replayed; no new row or head change. |
| Same request identity with changed bytes | Domain request-conflict code; no mutation. |
| Stale expected head | Domain revision-conflict code; no request receipt or revision. |
| Two interleaved writers | Exactly one revision commits; the other observes the moved head. |
| Response lost after commit | A newly opened store recovers the original receipt by request identity without repeating the write. |
| Corrupt stored JSON or digest | Read fails closed; no repair, pruning, or replacement occurs. |
| Storage budget exhausted | Existing head, revisions, requests, and accounted bytes remain unchanged. |
| Restore | A third revision is appended; revisions one and two remain readable and unchanged. |

The corruption rows are intentional discriminating faults. Removing the digest/JSON checks, moving replay behind head checks, recording stale requests, or mutating before budget validation makes the matrix fail.

## Semantics intentionally not unified

- Workflow integrity failures are surfaced as `DocumentError(storage_unavailable, 503)`; setup currently retains its existing bounded `ValueError` integrity refusal. #385 must not change either outward contract accidentally.
- Workflow history budgeting counts revision document bytes. Setup budgeting counts both version records and operation receipts and also reserves bounded headroom before copy-capable apply operations.
- Setup lifecycle states (`checking`, `staging`, `committed`, `failed`, `abandoned`) and explicit abandon/reconcile behavior stay in setup-owned tests.
- Workflow command diffs, execution-input identity, and HTTP/SDK/CLI/MCP parity stay in workflow-owned tests.

## Migration gate for #385

A shared value-level utility may replace duplicated canonicalization, stored-hash checks, request reuse classification, expected-head precedence, and exact byte arithmetic only when this matrix and both domain-owned suites remain green. SQL, callbacks, copy lifecycle, domain error construction, table schemas, and public payloads remain outside that utility.
