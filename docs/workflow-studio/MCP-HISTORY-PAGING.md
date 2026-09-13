# MCP history pages and review correction

Follow-up within #134 to review thread 3998113774 (13 September 2026).

The shared document service has bounded summaries, but a supported 1,024-revision
history can still exceed the bridge's 2 MiB reply-data limit. The initial bridge
returned a read error with no way to request less history. This was a real adapter
coverage gap, not a storage failure and not a lost revision.

`workflow_history` now accepts `limit` (50 default, 1–100) and an optional positive
`before_revision`. Results are newest-first and carry `next_before_revision`.
Pass that cursor back as `before_revision` until it is null. The cursor is exclusive
and follows immutable revision numbers: a later appended revision cannot shift or
repeat entries on older pages. Each page retains `id`, the currently observed
`head_revision`, and each summary's omission metadata. Reading subsequent pages
is not a claim that the head stayed fixed.

Example tool arguments for a subsequent page:

```json
{"document_id":"ACTUAL_WORKFLOW_ID","limit":50,"before_revision":975}
```

Use the cursor actually returned by the preceding result, not the example number.
Decode the `data_json` result with an exact-integer parser as documented in
[MCP-AGENTS.md](MCP-AGENTS.md).

This is bridge-side paging of the existing bounded HTTP history. It does not add
another database query API, alter Workspace retention or silently omit revisions.
The Studio HTTP response still obeys its own 16 MiB cap. The bridge's data cap stays
2 MiB; tool schemas now explain the available paging controls.

Three regression tests cover all 1,024 synthetic large summaries across 11 pages,
no skipped/duplicate revisions, preserved omission metadata, append-stable cursors,
empty final ranges and argument bounds before any request. The first two fail on
the original bridge; all three pass after the correction. The earlier read-route
fixture now returns a real empty history shape rather than an unrelated status
object. No existing route, request ID or write behavior changed.

Local combined continuation contracts: 40 run, 36 passed, four optional SDK tests
skipped in the source environment. This count also includes the separate #119
schema and #131 history-owner tests; it is not a claim that this commit added 40
tests. Hosted CI verifies the repository and runs official SDK protocol checks on
Windows and Ubuntu separately. No user-workstation setup or generation occurred.
