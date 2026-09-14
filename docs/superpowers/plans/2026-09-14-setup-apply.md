# Reviewed setup application

Goal: Apply an exact reviewed proposal to a revisioned Workspace draft, stage
its existing images through Studio, and restore the previous revision without
running a model or silently replacing concurrent edits.

Architecture: extend the existing Workspace SQLite connection with bounded,
append-only setup draft revisions and request receipts. Existing browser drafts
remain private until an explicit checkpoint. Reuse proposal rebuilding and the
existing asset-reference/upload path. No new executor, model store or polling.

## Contract and implementation order

1. Shared draft store: workspace-scoped create/checkpoint, immutable revisions,
   expected-revision changes, request identity recovery, bounded storage.
2. Apply: validate exact acknowledged proposal against the stored before-state;
   journal intent before copying sources; record every completed copy; commit a
   new draft only after exact inputs/runtime/graph are rechecked. Failed or
   interrupted operations never auto-retry and never change the draft head.
3. Restore: append a prior revision, retaining all history. Check old staged
   inputs and graph before allowing it to be loaded. No source deletion.
4. UI: explicit checkpoint/apply/undo/recovery, normal browser draft owner for
   synchronous adoption, capture/change-stamp checks before every awaited step.
   Do not overwrite edits made while awaiting a reply. Persist command identity
   before sending; recovery GET never repeats a write.
5. HTTP/SDK/CLI/author-MCP parity, read-only receipt inspection. Extend existing
   shortlist Windows/Linux/browser checks. Record full suite and native evidence.

## Boundaries

Initial application supports the existing proposal adapter only (static named
references and static whole-image routes). Mask and motion-mode routes remain
unsupported. Pending local File inputs/in-flight attachments must settle before
checkpoint/apply so undo does not falsely promise to persist browser File bytes.
Source copies may remain after a failed/abandoned operation; never delete them.
Studio.lock coordinates this server's backend and staging; SQL compares revisions
and active request ownership across clients. A journal/hash is not a filesystem
lease against hostile mutation or proof of creative acceptance.

Alternative rejected: call selectPreset directly from the proposal modal. It has
no shared revision or receipt and cannot recover partial staging or response loss.
Alternative rejected: use workflow-node documents as a recipe store. Their schema
and reducer do not represent the existing Create draft/reference/continuation.

Implementation record: [SETUP-APPLICATION.md](../../workflow-studio/SETUP-APPLICATION.md).
Service/HTTP/SDK/author-MCP, origin-locked browser adoption, journal recovery and
append-only restore are implemented. Tests cover SQLite competition across
independent runtime locks and the real existing Qwen compiler/uploader; CI adds
native browser/official-SDK coverage to the existing shortlist lane. Final
counts and remaining owner-machine limits are recorded in the PR/handoff.
