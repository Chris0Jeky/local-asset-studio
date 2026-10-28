# Private creation qualification implementation plan

**Goal:** Finish the existing #1677 privacy slice without losing drafts, disclosing private records, or hiding failed checks.

**Architecture:** Retain the existing per-creation classification, server-side read scopes and dedicated storage. Correct admission and transition boundaries; use the existing Make owner for explicit navigation. Keep archive/organization changes separate from this qualification.

**Tech stack:** Python loopback HTTP/SQLite, plain JavaScript, Node contracts and native Chromium fixtures.

**Spec:** `docs/PRIVATE-CREATIONS.md`; issue #1673 and accepted review comments on #1677.

## Constraints and review focus

- Never resubmit an uncertain job, mutate installed runtimes, or use real owner media in tests.
- A default read must not return private records, even with malformed or absolute-form request targets.
- Failed destination persistence must retain the visible draft and its prior recoverable bytes; another tab's newer tune is never deleted.
- Explicit finder choices must win over old recovery, without writing private selections to localStorage.
- Platform fixes retain existing assertions; synthetic tests do not establish artwork quality or owner acceptance.

## Task 1 — Admission regression fixes

- [x] Add real HTTP tests for mixed-ID job paths and noncanonical request targets through composed document handlers; run on unchanged production source and retain failures.
- [x] In `app/server.py`, resolve only canonical generic job IDs through `_scoped_job`.
- [x] In `app/creation_privacy.py`, reject non-origin-form targets before dispatch; preserve scoped validation and mutation refusal.
- [x] Run all privacy HTTP/advanced-boundary tests.

## Task 2 — Recoverable Make transitions and explicit navigation

- [x] Add native-browser quota-failure controls for picture and scene drafts using the real privacy controller (execution awaits hosted CI; local navigation is blocked).
- [x] Make `writeDraft` report verified persistence; keep unsaved private data in memory and leave prior regular recovery intact when migration fails.
- [x] Test and correct finder goal/Look handoff through the Make owner, retaining draft intent and private storage isolation.
- [ ] Run existing Make draft/privacy, source-slot, Restyle, and native smoke drivers.

## Task 3 — Existing qualification failures

- [x] Fix portable human-readable run-record paths in `app/server.py`; keep Windows expectations intact.
- [x] Remove global Thread.start mocking from the independent Node health test; resolve temporary roots in workspace fixtures.
- [x] Register genuine synthetic source identities for setup-lineage and restore missing ownership bindings in the source-sliced daily fixture.
- [x] Check the retired source-slot response assertion against current draft ownership instead of weakening the production guard.

## Task 4 — Integration and evidence

- [x] Reconcile current main #1676 documentation with the privacy branch, retaining both ledgers.
- [ ] Run complete offline suite, repository validator, targeted browser journeys and fresh final-head hosted checks.
- [ ] Publish exact changes, dispositions and remaining limitations; merge only once safe. Continue organization/archive work as a separately reviewed slice.

## Workspace provenance

GitHub Actions tracked-source artifact 12816490487 from run 40688426424, snapshot commit `976924e4a65776d6d246a87bdd7b2ade0f799ab3`, tree `9ed413622e0238354ef226300ad5681365d1551c`. All 4,600 tracked blob hashes were verified locally. Production source is the existing PR head `901e9ae30ee7e1eb10814ca273f073c17cf5409e`; the snapshot adds only the read-only export workflow. Local source checkout has synthetic Git history and is not used as authority for remote ancestry.
