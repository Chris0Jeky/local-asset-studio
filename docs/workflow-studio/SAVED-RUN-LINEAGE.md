# Saved workflow run lineage

Implementation checkpoint: 13 September 2026. Advances #122; agent-facing commands
are the next #123 slice. Uses the merged #130 shared documents and #138 preset
projection. It does not broaden the graph types that #138 permits.

## What this solves

A downloaded projection report used to be the only bridge from a builder document
to its job. A new, explicit saved-run preparation now retains that bridge in the
existing AssetWorkspace database before returning a ticket. Losing the HTTP response,
closing the browser, or restarting Studio need not require a replacement ticket.

The record links an immutable **document ID + revision + document hash** to the
projector report, exact recipe ticket/hash, expected job ID and original document
store. Job observation links that identity to the existing job's prompt IDs and
output/asset descriptors. The source document is not rewritten and its next edit
cannot silently become the source of an older run.

Existing `/prepare-document` and browser tab tickets are unchanged. They are not
retroactively indexed. This first slice is available through HTTP; it does not
claim the builder's Run button already opts into persistent records.

## HTTP contract

The ordinary loopback Studio server owns these routes and its existing Host/origin
guards still apply. There is no new listener or execution endpoint.

`POST /api/workflow-studio/document-runs`:

```json
{
  "request_id": "character-study-preparation-001",
  "document_id": "ID_RETURNED_BY_DOCUMENT_CREATE",
  "expected_revision": 1,
  "preset_id": "REGISTERED_PRESET_ID"
}
```

The IDs above are placeholders. Read the current saved document and use its actual
revision and the matching registered image preset. The returned `record.report.ticket`
is an ordinary `studio.run-ticket/v1` ticket. Review it and explicitly use the
existing `/api/workflow-studio/run` route when execution is intended.

The **preparation request ID** is caller-selected and retained with these four exact
fields. It is not the generated **ticket request UUID**, and neither is the expected
**job UUID**. Reusing the preparation ID with different content returns HTTP 409.

| Operation | Route |
| --- | --- |
| Recover the committed report/ticket, without preparing again | `GET /api/workflow-studio/document-runs/{preparation_request_id}` |
| Observe the linked local job once, without submission or Comfy HTTP | `GET /api/workflow-studio/document-runs/{preparation_request_id}/observe` |
| Find the saved source from an expected job ID | `GET /api/workflow-studio/document-runs/by-job/{job_id}` |
| List metadata for one saved document | `GET /api/workflow-studio/document-runs?document_id={id}&limit=25` |
| Continue that list without offset drift | Same query plus `before={next_before}` |

Repeated preparation returns the **original committed report**, even if the head
has advanced or ComfyUI is now offline. `head_revision` and `source_is_current` are
separate from the source revision. Recovery is not renewed resource certification
or renewed execution approval; the existing run service still checks the ticket.

`dispatch_attempted: false` describes this metadata/observation call only. Historical
`generation_submitted: false` inside the original projection report describes its
preparation; it is not the current lifecycle of the linked job.

## Transaction and recovery design

1. Strictly decode the four fields. Open a read transaction, check for an exact
   retained preparation, and otherwise check the expected document revision.
2. Release that database transaction. The existing projector reads installed
   schemas, validates the catalog-bound graph and runs ordinary Studio preparation.
   **No SQLite write lock spans schema/network I/O. No job is dispatched.**
3. Start a short `BEGIN IMMEDIATE` transaction. Check for an independently committed
   identical preparation, then recheck the expected revision/hash, workspace and
   storage budget. Atomically insert the report and its small hashed summary.
4. Return only after commit. If another process won the request race, both callers
   receive that winner's ticket. A discarded, uncommitted ticket was never exposed
   or dispatched. If the commit reply is lost, GET recovers the committed record.

Preparation records and the existing disk dispatch journal have different owners.
This change deliberately does not try to transact SQLite and ComfyUI together. Only
`run_ticket` may create its durable dispatch intent and invoke the existing worker.
One retained dispatch attempt is not distributed exactly-once execution.

A stale revision before or after preparation returns 409 and leaves no preparation
record. A preparation error leaves no job. Storage/integrity failures are 503, not
requests to edit the graph. Never recover an uncertain run by preparing a new ID.

## Observation semantics

`observed` means a local job with the expected ID, preset, endpoint and exact prepared
graph was found. Its public job state, prompt IDs and outputs remain owned by Studio.
There is no Comfy history request, polling loop, status rewrite, cancellation or retry.

`not_observed` means local job evidence is absent; it **does not mean unsubmitted**.
The ticket might be unused, its dispatch journal may contain an intent without a job,
or the original job evidence may be unavailable. Inspect the original ticket and
workspace. An explicit same-ticket execution recovery remains an existing operation,
not something this GET does on the user's behalf.

`workspace_changed` refuses to join evidence from a replacement database/workspace.
`evidence_mismatch` refuses to associate a conflicting job/graph. Record retrieval
still allows inspection of the original immutable report.

## Limits and compatibility

One new namespaced table and index use the existing Workspace connection helper.
Maximum 4,096 records, 128 MiB stored report/summary payload, 1 MiB per report and
100 summaries per page. Limits refuse new writes, never prune existing evidence.
Metadata pages read small hashed summaries, not all embedded tickets. The cursor is
a descending immutable sequence, so later insertions do not shift the next page.

Source/revision/report/ticket hashes check integrity, not authenticity against an
attacker who can rewrite the whole local database. Model/package bytes are still
not frozen by this adapter. There is no migration/backfill for old tickets, source
asset-reference support, arbitrary-graph support, node-progress stream or automatic
asset metadata mutation. `arbitrary_graph_execution` remains false.

## Correctness evidence

Local tests use byte-identical copies of the inspected core, shared command/store,
preset projector and ticket service. They use actual SQLite transactions and a
synthetic runtime, never an installed model. Cases include independent concurrent
clients, pre/post-preparation edits, commit reply loss, failed inserts, corrupt
source/report/summary records, exact int64 seeds, paging during insertions, budgets,
workspace changes, existing ticket recovery and missing/mismatched job evidence.

Two additional integration cases reuse the repository's actual Studio/HTTP fixture,
including its real Host/origin predicates, host-resource rejection, job persistence
and single queued-job behavior. They require the full checkout and are skipped only
when `app/server.py` is absent. Full hosted CI results belong to the PR's tested
commit, not to this document's design claims.

No GPU inference, normal-browser run, runtime/model installation, user setting change,
workstation restart, artistic acceptance or licence clearance occurred for this slice.
The container cannot resolve GitHub for cloning; the connector supplies the files and
hosted CI must establish full-checkout integration and repository-validation results.

## Sources and decisions

- SQLite isolation: https://www.sqlite.org/isolation.html — release read snapshots
  before attempting a writer transaction; recheck after obtaining the write lock.
- SQLite transactions: https://www.sqlite.org/lang_transaction.html — short immediate
  write transactions, with the existing connection helper owning commit/rollback.
- Comfy routes: https://docs.comfy.org/development/comfyui-server/comms_routes — `/prompt`
  dispatch and `/history` observation are distinct. This adapter introduces neither.
- Comfy server overview: https://docs.comfy.org/development/comfyui-server/comms_overview
  — later editor changes do not alter an already submitted graph.
- Repository checkpoints: #138 preset projection; #145 builder controls; #139 records
  real Anima evidence/owner-selected look; #141 recovery/readiness; #146's bundle UI
  is a separate workstream. This metadata slice does not duplicate any of those.
