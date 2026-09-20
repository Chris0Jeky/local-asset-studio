# Bounded asset reads implementation plan

Goal: make catalogue browsing and off-page selection inspection bounded without
replacing AssetWorkspace, metadata commands, browser recovery or the existing grid.
The contract is scoped under #177. This is one sequential implementation line.

## Decisions

Use revision-bound keyset cursors, not OFFSET (which drifts under deletion) or a
server-side snapshot session (which retains database readers and another lifecycle).
Each page is one SQLite read transaction. Any asset/collection/membership mutation
invalidates a continuation; the caller explicitly refreshes instead of silently
mixing revisions. This does not promise uninterrupted paging during writes.

Keep `snapshot()` unchanged. New summaries omit source JSON, notes, tags, lineage,
collection lists and filesystem paths; truncation of display labels is explicit.
Resolve up to 200 selected IDs separately, preserving input order and distinguishing
active, trashed and missing. Neither API checks media bytes or grants write authority.
A first page may discover the current Workspace; selection and continuation are scoped.

## Task 1: SQLite core

- [x] Prove missing `AssetWorkspace.asset_page()` / `asset_selection()` with tests.
- [x] Add `studio_workflow/asset_reads.py`: bounded inputs/cursors, SQL projections,
  immutable query identities, one monotonic change stamp in the existing database,
  and typed errors. Keep schema setup in AssetWorkspace initialization, not reads.
- [x] Add indexes/triggers transactionally; test reopen, rollback, competing writers,
  unknown schema, missing/corrupt state, and mutation between identity/row reads.
- [x] Prove 100/1,000/10,000-row paging with tied timestamps, payload bounds, SQL
  keyset index use, no full snapshot or media read, and every selected ID accounted for.
- [ ] Run focused and complete offline suites plus validator. Publish a draft PR
  against the exact reconciled main tree, with the difficult-issue/ownership map.

## Task 2: Read-only transport and client (stacked after Task 1)

- [ ] Add real loopback tests for bounded page GET and selected-ID inspection,
  malformed/repeated query fields, foreign Workspace, stale cursors and no writes.
- [ ] Add a thin handler adapter and typed Python client/CLI using the existing
  bounded loopback transport. No server, queue, auto-pagination or automatic retry.
- [ ] Exercise exact response identity and truncation, refusal propagation, response
  bounds and the same public core fixtures; run full checks and publish a child draft.

## Review focus and remaining work

SQL substrings must bound allocation before large legacy metadata reaches Python.
A cursor is a checksummed observation, not authentication or execution authority.
Rollback must roll back its change stamp; a WAL reader must not see mixed generations.
Missing/off-page are different; no retained selection or original request is rewritten.
Do not claim the old grid, history, thumbnails, heap or generation memory is bounded.
Those consumers and measurements remain #177 follow-ups. Owner decisions are unchanged.
