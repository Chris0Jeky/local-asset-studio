# Browser reference review implementation plan

**Goal:** Review a local assistant's multi-image interpretation in Prompt Lab without editing JSON or losing the current brief.

**Architecture:** Extend the #333/#336 contract and the existing `/api/prompt` handler. The server validates the report, the exact original image bytes, selected traits and current intent; it returns a non-executing transfer preview. Prompt Lab applies that preview only against its unchanged captured draft and offers a guarded one-step Undo. No model call, upload-to-generator, new queue or authoritative store is added.

**Spec:** `REFERENCE-INTELLIGENCE.md`, particularly the three separate records and optional editable descriptions. This is the review half of the shared UI sequence. The Analyze button still depends on #35/#178 resource admission. The operator CLI remains the actual analysis entry point.

**Global constraints:** Python 3.12+, stdlib/Pillow, plain JavaScript; one to four source images; 8 MiB/16 MiPixels/one frame each; reports and selections remain bounded. Preserve source hashes, all unselected current facets, explicit locks, parameters, exact words and constraints. Imported text is inert. Never silently discard excess sources or invent native graph bindings. HUMAN_TODO unchanged.

## Slice 1 — source-bound review projection

Files: `studio_prompt/reference_analysis.py`, new `studio_prompt/reference_review.py`, `studio_prompt/http_extension.py`, `tests/test_reference_review.py`.

- [ ] Add failing contracts for in-memory source verification, inspection, role-safe preview, current-field retention, lock refusal, byte/pixel limits, stale sources and HTTP dispatch with no Studio calls.
- [ ] Add a keyword-only in-memory source alternative to `draft` while retaining the file-root contract; both verify every original SHA-256.
- [ ] Implement `inspect(value)` and `preview(value)` through `/api/prompt/reference-review/inspect` and `/preview`. Preview consumes the complete current intent and explicit `adopt_brief` choice. It replaces the ordered reference set and updates only selected facets; selected tags are merged. It reports the entire change set and base/candidate identities.
- [ ] Run the focused source/vision/CLI/HTTP tests, full offline suite and validator. Record actual failures separately from inferred causes.

## Slice 2 — Prompt Lab review panel

Files: new `app/static/reference-review.js` and `.css`, existing `prompt-lab.html` and `.js`, new browser/contracts tests.

- [ ] Test a current-draft adapter before implementation: capture, changed-draft refusal, apply, guarded Undo, and imported locks.
- [ ] Add a compact report import, hash-matched original-image selection, per-picture preview/role/traits/tags/uncertainty controls, optional description edits and an explicit transfer diff.
- [ ] Apply only a preview matching both the current draft and the current report/files/selection revision. Async imports, hashing and HTTP results cannot overwrite newer work. Undo refuses after a later manual edit.
- [ ] Test actual browser at desktop and 390px, keyboard operation, inert injected text, missing/changed images, late replies, repeated clicks and zero inference/generation. Retain a no-helper/manual Prompt Lab path.

## Limits that this pass does not erase

A browser draft revision is not a shared SQLite document revision. Review does not authorize an image-generation request or certify visual quality. Original Files stay in browser memory and are sent only to the local validation endpoint; they are not staged to ComfyUI. Native style-board setup remains #335/#328/#232. Persistent shared Prompt Lab documents and scheduled Analyze execution remain #38/#35.
