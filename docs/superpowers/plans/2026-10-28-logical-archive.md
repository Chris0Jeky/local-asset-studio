# Reversible logical Archive Implementation Plan

> **For agentic workers:** use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Archive and unarchive Library assets without losing work or changing privacy/Trash.
**Architecture:** Add one nullable asset field; reuse the existing SQLite command, revision, receipt and recovery owners. Extend bounded reads and existing Library controls, not a second service.
**Tech Stack:** Python stdlib/SQLite, shipped plain JavaScript, Node contracts, Playwright; no runtime dependency changes.
**Spec:** `docs/superpowers/specs/2026-10-28-logical-archive-design.md`.

## Global constraints

200 IDs per command/selection; 100 per page; 128 KiB command and 2 MiB read-response bounds remain. Regular privacy defaults remain. No implicit retries, media moves, generation or owner-host changes. Preserve canonical source tree and exact-head hosted verification.

## Review focus

- Zero timestamp and malformed stored timestamps: NULL alone means not archived.
- Revision ceiling and mixed no-op batches: only changed rows consume a revision.
- Lost responses and newer observations: immutable receipts are not present state.
- Scope changes and off-page selections: no draft or pending-identity replacement.
- Legacy databases and client fixtures: existing unarchived shapes stay compatible.

## Task 1 — transaction and bounded observations

Files: `app/workspace.py`, `studio_workflow/asset_reads.py`, `studio_workflow/asset_read_client.py`, `studio_workflow/asset_read_tools.py`; tests `tests/test_asset_archive.py`, `tests/test_asset_archive_client.py`.

- [x] Write and run causal backend tests for archive/unarchive, migration, independent states, byte preservation, no-ops, stale revisions, replay, private receipts and pagination.
- [x] Add nullable `archived_at`, atomic actions and archive filtering; retain current counts and default response shape.
- [x] Write and run strict-client failures, then support the filter in typed reads, CLI and MCP schemas with timestamp and filter validation.
- [ ] Run existing Workspace, asset-read and privacy suites, then commit this coherent backend/read slice locally.

Interfaces: `update({...action:'archive'|'unarchive',...}, privacy=...)`; `asset_page(filters={archive:...})`; `AssetReadClient.page(filters=...)`. Read `selection` remains exact-ID and includes archived records.

## Task 2 — Library controls and recovery

Files: `app/static/index.html`, `app/static/workspace.js`, `app/static/asset-recovery.js`, `app/static/asset-recovery-shelf.js`, `app/static/asset-recovery-lifecycle.js`; tests `tests/asset_archive_frontend.cjs`, `tests/test_asset_archive_frontend.py`.

- [x] Add failing shipped-source contracts for filtering, receipts, retained draft/journal, scope storage, off-page selection and explicit same-run inspection.
- [x] Add labelled archive filter and actions; reuse existing mutation/recovery flow and disable controls under existing pending/conflict ownership.
- [x] Preserve unsaved details on archive; distinguish Archive/Trash labels and confirmations. Keep same-run inspection complete.
- [ ] Run existing Node-backed Library/recovery/privacy suites without weakening assertions.

## Task 3 — real HTTP/browser qualification and documentation

Files: `tests/asset_archive_browser.py`, `.github/workflows/asset-archive.yml`, `docs/ASSET-ARCHIVE.md`, `CURRENT_STATE.md`.

- [ ] Test production HTTP boundaries, archive filters and retained identities; exercise native UI archive/unarchive and lost acknowledgment with synthetic media only.
- [ ] Add Linux/Windows CI, run narrow and full suites plus `python scripts/validate-repo.py`, record executed results separately from pending hosted gates.
- [ ] Review changes against the design and current main; publish a ready-for-review PR, inspect exact-head workflows and merge only after verification. Keep #1678 open for run migration and any deferred client-write acceptance.

## Baseline

Remote main `3392d27bf0fa8ce5305bcc2c3a88009a33d87114`, verified tree
`dc2c2606338d4ac29061a5d08347f80927857926`, source run 40783819045.
37 existing Workspace tests pass. Local Git root records the verified tree,
not fabricated remote commit ancestry. Original tracked CRLF blobs are retained.


## Evidence and rulings

- Backend: all 12 new tests failed on missing Archive state/actions, then passed.
  Strict client: six new cases pass after unsupported-filter failures; the initial
  run also collected an imported fixture class, corrected to module-only import.
- Shipped frontend: eight missing-feature failures passed after implementation;
  three additional shelf/lifecycle/empty-view contracts failed then passed.
- Ruling: include Archive in bounded current metadata and recovery observations,
  not just full reads — replay/conflict must not leave a stale toggle action.
  An actual lost-acknowledgment regression reproduced the missing current field.
  Old recovery records still read without the additive field.
- Four composed production HTTP tests pass, including lost response after commit,
  exact replay, receipt-failure rollback, private cursor isolation and Host/Origin
  refusal. Three lifecycle tests pass. Focused total: 26 Python tests (one invokes
  11 Node tests); counts overlap and are not additive.
- Existing Workspace and privacy suites each pass 108 tests; recovery suite 21.
  The first 238-test asset suite exposed an outdated empty-view assumption. Keep
  the original empty-library message for a complete empty snapshot; paged empty
  Active views cannot claim no archived assets exist. No old assertion removed.
- Native local navigation is blocked with ERR_BLOCKED_BY_ADMINISTRATOR. The inert
  driver passes 24 checks, including production HTTP/SQLite and 1440/390px layout,
  with zero page/handler errors. It does not qualify native browser persistence.
  Its first run exposed missing `jobs` on the synthetic Studio facade; the facade
  now supplies an empty job registry rather than swallowing handler exceptions.
- Installed-SDK tests are optional skips locally; the new Linux/Windows workflow
  requires pinned MCP 1.30.0 and executes the official SDK and real stdio tests.
  Final-head hosted qualification and full-suite completion remain pending.

## Whole-branch review and local qualification

- The new negative-timestamp receipt test reproduced an accepted invalid Archive patch (11/12 Node cases passed before the fix). Receipt, current-metadata and strict recovery-shelf validation now agree on finite nonnegative Archive timestamps; all **12 Node cases** pass.
- The complete existing+new asset group passes: **238 tests in 32.867s**, including the unchanged Library contracts. The group deliberately tests failing synthetic browser drivers; their expected failure diagnostics are not suite failures.
- Existing Workspace **108**, privacy **108**, recovery **21**, and asset-detail **9** tests pass. Groups overlap; do not sum counts. Final full-suite and native/platform qualification remain required.
- Review was performed by the implementing session; no independent reviewer is claimed. Tests cover the shared production transaction/HTTP owner, strict typed/protocol contracts and actual shipped frontend code. Owner media, generation and human acceptance remain untouched.
