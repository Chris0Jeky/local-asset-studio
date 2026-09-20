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

Stored record text and scalar columns are SQL-bounded before Python allocation,
then checked for canonical JSON, digest, stored byte length and supported fields.
Malformed/oversized head or selected records refuse the whole read. Other
unselected revision payloads are not decoded. Listing is not a full audit of every historical payload.

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

Reads deliberately do not check live files, graphs, runtime readiness or models.
They remain usable when a historical input is absent or the runtime is busy.
A valid historical digest is not authenticity, present availability, artistic
acceptance or permission to apply the revision.

## Verification and next boundaries

```
python -m unittest discover -s tests -p 'test_reviewed_setup_history*.py' -v
python -m unittest discover -s tests -p test_recipe_shortlist_apply.py -v
python -m unittest discover -s tests -p 'test_revision_consistency*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Real SQLite tests cover a 100-revision walk, concurrent head change, interleaved
WAL writer, query-only connections, unchanged rows, invalid counters/digests,
missing revisions, strict routes, typed preview bounds and metadata export.
The read-only Ubuntu/Windows CI lane checks out the exact PR head.

Remaining #395 work: browser history UI and accessibility, SDK/CLI/MCP exposure,
operation/proposal receipt lineage, deliberate load/restore/fork/import commands,
strict import validation and retention/compaction review. No new write authority
or pruning is introduced. #394 selected browser-File preservation is separate.
Owner creative/licensing/workstation acceptance in HUMAN_TODO is unchanged.

Reconciliation decisions and scenario mapping: [737-HISTORY-RECONCILIATION.md](737-HISTORY-RECONCILIATION.md).
