# Procedural Assets Implementation Plan

> **For agentic workers:** Execute in the isolated integration worktree; an independent reviewer checks the whole branch before publication.

**Goal:** Connect the eight existing generators to Studio discovery, explicit Production execution and Library outputs.

**Architecture:** `app/procedural.py` owns validation, source/runtime pins, owned attempt receipts and output publication. Production owns durable projects and its existing worker. A small schema-driven page prepares projects and opens their shared execution/results view.

**Tech Stack:** Python standard library, existing SQLite/Workspace and factory, plain browser JavaScript.

**Spec:** `docs/superpowers/specs/2026-11-05-procedural-assets.md`

## Global constraints

No factory implementation changes; no user-supplied executable or output path; no execution on discovery or prepare; regular-only output storage; exact-source pins; no repeat of an uncertain native attempt; missing Godot evidence remains incomplete.

## Review focus

- Missing/changing runtime or source files must fail before native execution.
- Crash after execution but before Library publication must recover only hash-verified retained outputs.
- Failed/partial reports and symlinked/changed outputs must not become completed Library assets.
- Double submit and response loss must not execute a build twice; the UI must retain the prepared-project link.
- Non-regular requests must be refused before effects, and all existing native/scene/comparison paths must retain their behavior.

## Tasks

1. [x] Write adapter tests for catalog/defaults, typed validation, runtime preflight, immutable plans, build receipt/output verification and no-repeat recovery; observe the missing-feature failures.
2. [x] Implement `app/procedural.py` using the existing factory APIs and fixed output names.
3. [x] Write shared Production/HTTP tests; add preparation, dispatch, storage admission, native media and hash-checked downloads.
4. [x] Add the schema-driven page and shell discovery, with explicit preparation and a project link; extend existing project rendering for procedural artifacts and check results.
5. [x] Run focused backend/frontend suites and repository validation. Add the actual browser flow to the existing UX lane; local Chromium installation is unavailable in this session, so browser execution/screenshots remain a hosted gate.
6. [x] Commit the bounded change for independent review. Root handles GitHub draft PR, exact-head CI, merge and shared state reconciliation.

## Executed software evidence (5 November 2026)

- Missing-feature failures observed before adapter, HTTP and frontend implementation.
- Focused procedural adapter/HTTP/Node contracts: 26 tests passed, including retained-pack and broken-link refusal.
- Production/storage suite: 114 tests passed. Studio UX Node contracts: 8 tests passed.
- `validate-repo.py`: passed (98 preset graphs/bindings, 194 pinned assets).
- Full offline suite attempted locally, then stopped after the host process-visibility limitation was confirmed; it is not a passing run. This managed host cannot expose all process identities to psutil. Preserve process-ownership guards; exact-head hosted CI is the full/lifetime gate.
- No actual Blender 5.4, Godot or local Chromium execution. No native geometry, renderer, collision or art proof is claimed. Level/dataset/spring and dedicated SDK/MCP integration remain separate under Refs #2021.
