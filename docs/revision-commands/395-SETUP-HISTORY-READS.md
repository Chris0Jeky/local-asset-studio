# Reviewed setup history: bounded read slice

Refs #395, #232 and #737. This adds read projections to the existing `setup_*_v1`
revision owner, not another setup store or a complete history editing UI.

## Routes

All three routes are GET-only, require the exact 32-hex `workspace_id`, use the
existing loopback Host gate, and return the explicit observation flags below.

```
/api/workflow-studio/setup-drafts/<id>/history?workspace_id=<scope>&limit=20
/api/workflow-studio/setup-drafts/<id>/history?workspace_id=<scope>&limit=20&before_revision=81&expected_head=100
/api/workflow-studio/setup-drafts/<id>/compare?workspace_id=<scope>&left=1&right=100
/api/workflow-studio/setup-drafts/<id>/export?workspace_id=<scope>&revision=1
```

Python callers use `SetupHistory(workspace).page`, `.compare`, and
`.export_revision` with the same arguments and mandatory Workspace scope. `compare` and
`export_revision` also accept optional `expected_head`, including over HTTP.
Duplicate/unknown query fields, noncanonical decimal integers, excessive query
bytes, fragments and absolute URLs are refused. Older setup routes keep their
existing no-query contract. POSTs to these new read routes do not commit commands.

## SDK, CLI and MCP readers

`WorkflowClient(...).setup_drafts` and `SetupDraftClient` expose `history`,
`compare` and `export_revision` over these same routes. All require
`workspace_id`; `expected_head` is optional for a first page, comparison or
export, and mandatory with `before_revision`. The typed client validates the
returned Workspace/draft/head, exact contiguous page and continuation, observation flags,
comparison revisions and canonical export identity, including the exported
draft's own `draft_sha256`. The ordinary Studio `Client` transport applies the
1 MiB raw-response limit before decoding these three GET routes, including JSON
whitespace, and reuses the strict decoder to reject duplicate keys. Operation
receipts named `history`, `compare` or `export` keep their separate route and
transport contract. Caller-supplied decoded transports remain supported; the
typed client still validates their response identity, byte projection and shape.

The module CLI offers the same reads:

```console
python -m studio_workflow.setup_draft_client history DRAFT_ID --workspace-id WORKSPACE_ID --limit 20
python -m studio_workflow.setup_draft_client history DRAFT_ID --workspace-id WORKSPACE_ID --before-revision 81 --expected-head 100
python -m studio_workflow.setup_draft_client compare DRAFT_ID 1 100 --workspace-id WORKSPACE_ID --expected-head 100
python -m studio_workflow.setup_draft_client export DRAFT_ID 1 --workspace-id WORKSPACE_ID --expected-head 100
```

Substitute identities and revisions retained from the actual Workspace read.
The MCP adapter exposes three read-mode tools through this existing typed client:

| Tool | Required arguments | Optional arguments |
| --- | --- | --- |
| `setup_draft_history` | `draft_id`, `workspace_id` | `limit` (1–20, default 20), `before_revision`, `expected_head` |
| `setup_draft_compare` | `draft_id`, `workspace_id`, `left`, `right` | `expected_head` |
| `setup_draft_export_revision` | `draft_id`, `workspace_id`, `revision` | `expected_head` |

All revision/head arguments are integers from 1 through the existing 256-revision
limit. Booleans, unknown arguments and invalid identities refuse before HTTP.
Each invocation makes one GET. To continue history, explicitly pass the returned
`next_before_revision` as `before_revision` together with its observed
`head_revision` as `expected_head`; the adapter never follows pages itself.
Retain that head when comparing or exporting against the same observation.

The ordinary MCP envelope retains all supplied read arguments in `context`,
including on a stale-head or foreign-Workspace refusal. The existing HTTP status
and code remain visible; lost, malformed or oversized reads are read failures,
with no write-recovery instruction or automatic retry. The typed client's 1 MiB
history response bound applies before MCP encoding. Canonical JSON and hashes
are preserved in `data_json`, including seed values declared as text by the
reviewed-setup owner. MCP annotation hints mark these tools as read-only,
idempotent and closed-world; dispatch also enforces their permission scope.

These tools return metadata for inspection. They do not load a browser draft,
write an export file, initialize setup tables, verify live dependencies, copy
media, stage inputs, switch backends, install models or submit generation.
Restore remains a separate explicit setup command. Fork/import commands and the
browser history surface remain under #395.

## Canonical v2 results and error policy

The two unmerged v1 proposals used the same page format for different shapes.
They are replaced, not served side by side. The constructor is only
`SetupHistory(workspace)`; do not pass `SetupDrafts` or select a legacy variant.

- Page: `studio.setup-history-page/v2`.
- Comparison: `studio.setup-history-compare/v2`.
- Export envelope: `studio.setup-history-export/v2`.
- Immutable export document: `studio.setup-revision-inspection/v2`.

Every success envelope contains Workspace/draft identity, `head_revision`,
`head_record_sha256`, `observation_only: true`, `dependencies_checked: false`,
`generation_submitted: false`, and `staging_performed: false`. Page envelopes
also carry the accepted `limit`. The inspection document carries the same flags
but no head observation. Hashes are integrity observations, not authentication.

Invalid requests retain the existing HTTP 400 `invalid_setup_command` envelope;
foreign Workspace retains its existing scoped 409. The read owner emits
`setup_not_found` (404), `setup_history_head_changed` (409),
`setup_history_corrupt` (503), `setup_history_response_too_large` (413), or
`setup_history_export_too_large` (413), with observation flags and read-only
recovery wording. Underlying SQLite/I/O failures retain the handler's
`setup_storage_unavailable` (503). No failure triggers a refresh, repair or retry.
A supplied stale head is rejected before payload decoding. Without that guard,
every successful operation verifies the current head as well as requested data.

## Snapshot and pagination

Each call opens a query-only connection to the existing Workspace and checks its
identity inside an explicit read transaction before touching revision rows. The
head, contiguous revision accounting and requested rows share that snapshot.
The current head payload is always validated, even for historical-only or empty
pages, and is reused instead of decoded twice when also requested.
Neither schema initialization nor migration runs on this read path; a Workspace
without setup history reports unavailable history, without creating tables.

History pages return at most 20 summaries in descending revision order. Summaries
include exact revision/record/draft/graph hashes, canonical record byte length,
preset/backend identity and input count, not complete drafts or private runtime
roots/endpoints. Follow `next_before_revision` with the observed `expected_head`.
Any changed head refuses continuation; explicitly restart rather than mixing
observations. No automatic refresh, polling or mutation follows a stale page.
The inherited owner still limits a line to 256 immutable revisions. Missing or
invalid revision accounting is refused rather than silently skipped. Returned
rows and bytes are bounded; database execution time is not an OS resource quota.

Stored record text and scalar columns are SQL-bounded before Python allocation.
The reader temporarily asks `sqlite3` for SQLite's UTF-8 text representation as
bytes, regardless of whether the database stores UTF-8, UTF-16LE or UTF-16BE.
It restores the connection's original text factory immediately after the row is
materialized. Strict UTF-8/ASCII decoding then occurs inside the typed corruption
boundary, so malformed text cannot escape as a generic storage outage and valid
UTF-16 workspaces retain the canonical UTF-8 byte/hash identity written by the
setup owner. The SQL storage bound allows the maximum two-byte expansion of
valid UTF-8 text in SQLite's UTF-16 encodings. Canonical JSON, digest, stored byte
length and supported fields are then checked. Malformed/oversized head or
selected records refuse the whole read. Other unselected revision payloads are
not decoded. Listing is not a full audit of every historical payload.

## Comparison and export

Nine typed domains cover recipe/graph/backend, wording, references/inputs,
controls, lineage, batch, pending inputs, authoring timestamp and recorded runtime. Each side has a
canonical SHA-256, byte length and at most 1,024 Unicode characters of preview.
Truncation and the exact count of omitted UTF-8 bytes are explicit. The runtime
domain exposes only hashes/byte lengths: its preview is null and `redacted` is
true, so root/endpoint changes remain detectable without revealing those fields.
Preview text is not a complete JSON value unless `truncated` and `redacted` are
both false, and is never a replacement revision or execution instruction. Absent keys remain distinguishable from keys with empty values.

Export preserves the exact validated draft and staged-input metadata, plus source
revision/record identity, backend ID and graph SHA-256. Runtime root/endpoint are
excluded. The export's canonical JSON and digest identify that projection, not
the original private record. Both are returned separately. It is an inspection
artifact, **not an importable or portable setup bundle**. User-authored text and
lineage may themselves contain private information; export does not redact it.
Export includes exact canonical `export_bytes`; its immutable identity excludes
current-head observation, so later appends/reopen do not change an older export.
The canonical inspection document also has a separate 1 MiB cap.
No media bytes are included. All JSON responses are limited to 1 MiB in the
actual ASCII-escaped HTTP representation, not only their canonical UTF-8 form.
The default SDK/CLI/MCP transport enforces that raw byte bound before materializing
JSON. Page validation requires every expected revision up to the requested limit,
and an explicit continuation exactly when older revisions remain. An empty page
is valid after `before_revision=1`; an empty first page for a known positive head
or a prematurely missing continuation is refused.

Reads deliberately do not check live files, graphs, runtime readiness or models.
They remain usable when a historical input is absent or the runtime is busy.
A valid historical digest is not authenticity, present availability, artistic
acceptance or permission to apply the revision.

## Verification and next boundaries

```
python -m unittest discover -s tests -p 'test_reviewed_setup_history*.py' -v
python -m unittest discover -s tests -p test_recipe_shortlist_apply.py -v
python -m unittest discover -s tests -p 'test_revision_consistency*.py' -v
python -m unittest discover -s tests -p test_workflow_setup_history_mcp.py -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Real SQLite tests cover a 100-revision walk, concurrent head change, interleaved
WAL writer, query-only connections, unchanged rows, invalid counters/digests,
missing revisions, strict routes, typed preview bounds and metadata export.
The read-only Ubuntu/Windows CI lane checks out the exact PR head.
The separate Workflow MCP contracts lane installs the pinned optional SDK and
executes the three-reader bridge, official SDK and real stdio/HTTP/SQLite tests.
Those tests include a 100-revision explicit walk, context-preserving refusals,
raw transport framing and byte bounds, nested export integrity, no retries and
unchanged history/staging state. Ordinary discovery may skip its two optional
SDK tests when that tools dependency is absent; the dedicated lane requires it.

## Browser history panel (read-only)

`app/static/setup-history.js` adds a "Workspace history (read-only)" disclosure inside the
"Shared setup & recovery" panel (the only browser surface that holds a Workspace and draft
identity; the legacy named "Saved setups" are browser-local and have no revisions). Opening it
issues GETs through the routes above: the newest 20 summaries, then explicit "Load older
revisions" with the observed `expected_head`, and a two-revision comparison. Responses are
validated (format, Workspace and draft identity, read-only flags, contiguous order, exact
continuation) and rendered with `textContent` only; truncation and redaction notes are shown
as text. Each row links the existing export route for download. It sends no body, no POST and
no storage or Create-draft call, so it cannot load, restore, fork, import or apply anything.
The list shows identities and neighbour-to-neighbour differences, not save times: the page
summary carries no timestamp, and the comparison shows the recorded authoring time.
Contract: `tests/setup_history_client.cjs`; real routes: `tests/setup_apply_browser.py`.

Remaining #395 work: deliberate browser load/restore/fork/import commands,
operation/proposal receipt lineage, save times in history summaries, browser history
accessibility qualification (screen reader, 390px, 200% zoom), strict import validation and retention/compaction review. No new write authority
or pruning is introduced. #394 selected browser-File preservation is separate.
Owner creative/licensing/workstation acceptance in HUMAN_TODO is unchanged.

Reconciliation decisions and scenario mapping: [737-HISTORY-RECONCILIATION.md](737-HISTORY-RECONCILIATION.md).
