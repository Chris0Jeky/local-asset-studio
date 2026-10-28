# Private creations implementation plan

**Goal:** Let a person keep an unfinished or newly generated creation private, recover their choices, and deliberately browse regular, private or all work.

**Architecture:** One Studio queue and one Workspace catalogue retain explicit classification. Every persisted job chooses a fixed storage root; server readers enforce scope before projection. A per-tab browser owner separates session defaults, draft overrides and read scope.

**Tech stack:** Existing Python 3.12 stdlib server/SQLite, plain JavaScript and native Chromium fixtures. No runtime package or build dependency is added.

**Spec:** `docs/superpowers/specs/2026-10-26-private-creations.md` (implementation decisions under the owner's explicit request, not a claim of separately approved artwork).

## Constraints and review focus

- Legacy records remain regular. Private data must not enter default lists, direct reads, counts, receipts or browser caches.
- Preserve exact recipes and prompt IDs; never resubmit uncertain work or remove external engine evidence.
- Private creation can use an explicitly selected regular reference; regular creation cannot consume a private reference accidentally.
- Scope switches and asynchronous upload/poll completion must not publish into another view or change a captured creation destination.
- Private draft recovery uses tab-scoped storage. Unsupported advanced workflows refuse before side effects.
- Keep private media separate while preserving one authoritative asset/command owner; no mutable per-request Studio root.
- Existing art, model licensing, workstation qualification and `HUMAN_TODO.md` decisions remain separate.

## Task 1 — scoped Workspace and agent observations

Owner: privacy backend agent, isolated `private-assets` worktree.

Files: `app/workspace.py`, `studio_workflow/asset_reads.py`, asset read/family/recovery HTTP and client adapters, collection commands, MCP tools, focused tests.

Interfaces: `privacy='regular'` keyword on direct reads/mutations; `filters.privacy` on pages; `storage_root(privacy)`; `register` derives the admitted job's classification.

- [x] Reproduce regular-default leaks with synthetic private-tagged records.
- [x] Add additive migration, separate content roots, SQL scope before paging/counts, strict direct reads and scoped receipts.
- [x] Propagate explicit private/all through shared SDK/MCP readers and validate response scope.
- [x] Verify migration, paging, family, metadata/recovery and mixed-membership cases; commit the bounded backend slice.

## Task 2 — generation, uploads and HTTP boundaries

Owner: root, `private-creation` worktree.

Files: `app/creation_privacy.py`, `app/server.py`, `app/references.py`, `app/continuation.py`, `app/asset_thumbs.py`, new privacy unit/HTTP tests.

Interfaces: strict `normalize`, `matches`, `scope_for_handler`, `creation_for_handler`; `_job_directory(id, privacy=None)` and `_upload_path(name, privacy)`; frozen payload `privacy`.

- [x] Run failing tests for private job/run persistence, malformed/duplicate scope, scoped direct media and private reference downgrades.
- [x] Persist private jobs under `experiments/private/runs`; route all core lifecycle writes/restart recovery through the owning path.
- [x] Route uploads, snapshots, thumbnails and deliberate exports to their private roots. Preserve reference identity and ordinary image continuation.
- [x] Filter history/direct IDs and prevent unsupported private operations before staging or submission.
- [x] Verify controlled restart/corrupt records, missing/known private IDs, mixed sources and no resubmission.

## Task 3 — browser privacy and Make draft recovery

Owners: root for shared browser scope; workflow QA agent for Make and its tests.

Files: `app/static/privacy.js`, `index.html`, `app.js`, `workspace.js`, `studio-workbench.js`, `make.js`, styles and native browser fixtures.

Interfaces: `StudioPrivacy.creation()`, `.scope()`, `.storageKey(base, privacy)`, `.fetch(path, options)`, `.submitted()`; `studio:privacy-change` carries prior/current creation/scope and a reason.

- [x] Retain the observed Edit/Combine/Restyle reload-loss regression at desktop and 390px width.
- [x] Add visible session/draft privacy choices and Regular/Private/All browsing; never put private draft/run text in localStorage.
- [x] Preserve unfinished choices through private conversion/reload, clear out-of-scope UI immediately and refuse stale asynchronous reads.
- [x] Capture privacy at click time across source staging, previews and job submission. Browsing and new-creation defaults remain independent.
- [x] Run native synthetic journeys with actual action counts/timing, no model generation, no page/server errors.

## Task 4 — advanced boundary review and integration

Owner: independent boundary agent and root integration.

- [x] Audit raw SQL/direct job consumers and add causal refusal tests for unsupported private derivative/project flows.
- [x] Integrate bounded commits against the current GitHub main tree without overwriting the existing recovery/Library stack.
- [ ] Run the full unittest suite, repository validator, targeted native journeys and JavaScript syntax/contracts.
- [ ] Open a draft PR through the GitHub connector, review the complete diff independently and address material findings.
- [ ] Inspect exact published-head Actions logs and actual merge tree; merge only qualified changes with a merge commit.
- [ ] Update #1673 and #772 with delivered scope, measured journeys and precise remaining acceptance.

## Subsequent storage work

Moving an already generated run needs a whole-run preview/apply journal, sibling and receipt accounting, crash-safe publication and no silent deletion of shared blobs. Archive/restore must remain separate from privacy and trash. Do not replace these requirements with an asset-only flag edit; implement a separately tested command after the core boundary is qualified.
