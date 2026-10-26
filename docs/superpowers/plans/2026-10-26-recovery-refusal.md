# Retained Refusal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a bounded explanation of the last refused metadata POST beside its exact pending command.

**Architecture:** The existing journal remains the owner; the optional shelf copies its payload. Explicit carries at the two Workspace reconstruction points preserve the annotation only for the same pending operation.

**Tech Stack:** Existing plain JavaScript, Node contracts, Playwright and temporary Python HTTP/SQLite fixtures; no dependencies or services added.

**Spec:** `docs/superpowers/specs/2026-10-26-recovery-refusal-design.md`

## Global constraints

- Keep immutable command/body/request/targets/revisions and newer drafts unchanged.
- Admit only the strict version-1 annotation bounds from the design; old records remain readable.
- No automatic requests, focus calls, additional store, runtime/model actions or owner decisions.
- Implement in the isolated refusal worktree; reconcile the exact frozen Library version before Workspace hooks.

## Review focus

- A refusal written after newer typing must read and preserve the latest journal payload.
- Null/empty foreign identities and Workspace A→B→A must not bypass ownership.
- A storage failure after a POST cannot be described as an unsent request.
- Non-BMP text, unknown annotation versions and digest tampering must remain bounded and preserved on refusal.
- Current cleanup must not silently delete historical shelf snapshots.

### Task 1: Journal and shelf carrier

**Files:** `app/static/asset-recovery.js`, `app/static/asset-recovery-shelf.js`, `tests/asset_recovery_annotation.cjs`, `tests/test_asset_recovery_refusal.py`.

**Interfaces:** `validRefusal(annotation, operation, workspaceId)` validates the strict schema; `lastRefusal(payload, operation)` returns an independent annotation only for matching exact pending bytes; `journal.recordRefusal(slot, operation, error, {current, observedAt})` returns the updated payload or null when ineligible/stale, and uses existing verified persistence.

- [x] Write causal tests for retained annotation, exact-body/newer-draft writes, explicit foreign/stale refusal, strict schema, storage faults and shelf round-trip/identity.
- [x] Run `node --test --test-isolation=none tests/asset_recovery_annotation.cjs`; retain expected RED failures.
- [x] Implement the bounded helpers and shelf projection using the shared validator; retain old payload compatibility.
- [x] Run the new tests and existing journal/shelf/session/checkpoint/restore contracts; inspect every failure.

### Task 2: Existing Workspace presentation and lifecycle

**Files:** `app/static/workspace.js`, `tests/asset_recovery_refusal.cjs`, `tests/asset_recovery_session.cjs`, `tests/asset_recovery_shelf_restore.cjs`.

**Interfaces:** Carry `last_refusal` at existing reconstruction points; call `recordRefusal` only from a current explicit POST-refusal branch; render escaped text with existing panel ownership.

- [x] Reconcile the frozen Library Workspace file before editing it.
- [x] Add RED cases for typing/reopen/reload, both slots, GET unknown, replacement/ABA/foreign refusals, secondary persistence errors, confirmation/conflict/discard cleanup and unchanged focus.
- [x] Implement narrow hooks and persistent explanatory paragraphs; retain existing conflict behavior and historical shelf semantics.
- [x] Run affected editor, refusal, recovery, shelf and frontend-handoff contracts.

### Task 3: Native qualification, documentation and integration

**Files:** `tests/asset_recovery_refusal_browser.py`, `docs/revision-commands/393-REFUSED-RETRIES.md`, `docs/revision-commands/393-ASSET-RECOVERY-LIFECYCLE.md`, one evidence document.

- [x] Extend the real HTTP/SQLite/browser refusal journey for annotation persistence, literal text, focus and GET-only confirmation; retain original request counters.
- [x] Execute the native fixture and inspect its receipt/screenshots; preserve causal and setup failures separately.
- [x] Run syntax and repository validator on the integrated frozen candidate; retain the earlier complete-suite log as interrupted before review corrections, at the coordinator's direction.
- [ ] Qualify the final candidate's complete suite through the publication coordinator's exact-head hosted CI gate before merge; do not claim the interrupted local run as a pass.
- [x] Document executed evidence, old-reader compatibility, current-versus-historical cleanup and remaining #393 accessibility/owner work; obtain independent review and causally correct its two presentation findings.
- [ ] Complete the corrected candidate's independent re-review before publication.
