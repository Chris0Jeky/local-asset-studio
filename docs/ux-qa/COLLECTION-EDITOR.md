# Collection editing without losing the working context

## Delivery and reconciliation — 14 September 2026

The practical journey is **create or rename a collection → review the saved result →
continue browsing with the same selection**, with explicit choices to show or remove
that collection. A collection groups assets; saving its name does not add the current
checkbox selection, move original files, approve artwork or start any model work.

This slice extends the existing collection form and `AssetWorkspace.collection`.
It is stacked on the reconciled grid-continuity PR #273, head `1938177336bca6b09c0c69f06acda9a68c713024`,
whose complete source tree is `98945362e3003a0ab86e2beb0f833afc5b3653d5`.
The independently inspected main was `20c46dd45044a6f9193b3e562df5bee4e5fc8912`.
Merge the parent first; then retarget/reconcile and rerun the child against main.
The parent renderer and all its browser checks remain; no second library store exists.

## Root causes observed

The old form dispatched on every submit and closed on every successful response. It
had no submitted-snapshot baseline, no in-flight or leave guard, and no current-session
check. Cancel/Escape discarded text; reopening even the same collection repopulated the
form. Failures were written outside the modal. Deleting a collection required no
confirmation. The API also accepted collection requests from an old page after the
served database changed.

Before/after tests exercise the actual scripts and the complete Studio shell, rather
than a replacement design. The **same 26 browser expectations** improved from **8 pass /
18 fail** to **26 pass / 0 fail**. These are expectations, not 18 independent defects.
All **16 actual-script scenarios** failed on the old handlers and pass on the candidate.
Four SQLite scope tests separately exercise protocol compatibility, wrong/invalid scope
and changing the service database path after scope observation.

## Implemented interaction contract

| Event | Result |
|---|---|
| Open an existing collection | Capture its name/description and Workspace identity in one transient session. Missing target leaves the current draft untouched. |
| Open the same collection again | Keep the form and focus; do not repopulate it. |
| Cancel, Escape or switch while dirty | Ask before discarding. Stay retains both fields. |
| Save | Capture one snapshot. Disable duplicate submissions; keep ordinary fields editable. Hold close/switch until the outcome is known. |
| Confirmed Create | Become an Edit session using the returned ID. Keep the modal and library scope/checkbox selection unchanged. |
| Confirmed Save | Advance only the submitted baseline. Newer typing remains unsaved. No-change Save does not dispatch. |
| Definite validation/scope refusal | Show the error inside the modal and keep edits. Existing pre-commit 400/403/409 refusals allow correction; unknown errors do not. |
| Lost, malformed or timed-out response | Say **not confirmed**, retain edits and disable further writes in this session. No automatic or blind exact retry is offered. |
| Close after uncertainty | Explain that local discard cannot cancel a server change; ask for consent and direct the user to inspect the collection list. |
| Show collection | Explicit navigation, with the existing selection-clearing behavior stated on the button. A not-yet-observed saved collection asks for a refresh, not another save. |
| Remove collection | Ask about the named grouping and membership removal. Keep originals and recipes. Pause fields during deletion; failures stay in the dialog. |

The native dialog keeps status next to fields in a polite, atomic status region. The
390px layout is inspected. Actual screen-reader behavior, browser zoom, complete focus
return across a concurrently replaced collection sidebar and native light-dismiss
variants are not certified by those checks.

## Ownership and boundaries

`collection-editor.js` owns **only the open form session**: collection ID, opened
Workspace ID, acknowledged fields, busy/uncertain flags and a session epoch. The old
inline collection handlers are removed from `workspace.js`; its library, selection,
refresh and asset command/recovery responsibilities are unchanged. There is no extra
polling, database, persistence layer or framework.

An explicit 15-second request deadline races the actual HTTP read and aborts its
controller. This releases the UI even when a transport does not cooperate with abort.
It cannot roll back an already committed transaction. A queued callback from an older
closed session cannot modify a new session. A slow library refresh cannot hold the
confirmed save busy or make it close a different editor.

New form requests include `workspace_id`. Inside the existing `BEGIN IMMEDIATE`
transaction, `AssetWorkspace.collection` validates that identity before checking the
collection or mutating it. Responses echo the identity only for scoped callers.
Legacy callers which omit it retain their old result shape and behavior. Explicit
null/invalid identity is not treated as legacy. There is no migration or new schema.
The browser validates response ID, Workspace and submitted values before announcing
confirmation. Database identity is not authentication; copies share their identity.

### Not solved: collection revisions and receipts (#282)

A temporary real SQLite reproduction still creates **two collections for two identical
Create payloads**, and a stale full rename form can overwrite another client's newer
description. The current form prevents overlapping writes and a blind repeat **within
one open session**, not across tabs or manual reopening. Closing/reloading discards this
transient collection draft; it does not recover uncertain command identity.

Do not infer success from another collection with the same name. Do not reuse asset
receipts with a different result schema. #282 specifies monotonic collection revisions,
transactional expected revisions, typed durable idempotent receipts, bounded recovery
envelopes and historical/current separation before adding retry/reload functionality.
#204's existing asset recovery and #177's paging remain separate owners.

## Alternatives and next steps

An autosaving collection form was rejected: without collection CAS and receipt recovery,
it would hide uncertainty and increase overlapping mutations. Silently closing after
Save was rejected because it loses newer typing and changes the user's browsing
context. Reusing the asset metadata journal without a typed collection contract was
rejected because IDs, deletion and membership effects have different semantics.

Next implement #282, then a reviewed **create a collection from selected assets** action
with one explicitly scoped command and atomic membership semantics. The present Save
must not be mistaken for that future operation. Sidebar/select option DOM reuse can be
added independently, preserving focused options and distinguishing missing destinations.

## Reproduce

```sh
python -m unittest discover -s tests -p 'test_collection*.py' -v
node tests/collection_editor_contracts.cjs
python tests/collection_editor_browser.py --out .runtime/collection-editor-proof
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The browser driver refuses an occupied loopback port 8191. It serves production
Workspace/collection routes over temporary SQLite, intercepting other APIs with inert
fixtures. Deliberate metadata changes affect only fixture collections. The lost-response
case commits, then closes the socket without returning a response. Original media bytes
are checked unchanged. There is no live Studio or inference.

Native HTTP is the default. Local policy blocked native navigation with
`ERR_BLOCKED_BY_ADMINISTRATOR`; successful local results use `--inert`, with the real
HTML/JS/CSS and production Python HTTP but replaced browser storage/transport. Hosted
CI runs native mode separately and stores its receipts/screenshots. `--baseline` retains
unmet expectations, but runtime errors, page errors or incomplete runs still fail.
API-in-flight instrumentation is identical on baseline/candidate; no fixed sleep is
used to stand in for the save outcome. Initial script fixtures accidentally awaited
an unresolved baseline save and were corrected before the complete red run.

Final integrated grid + collection source: **1,910 tests run, 1,892 passed, 18 skipped**,
no failures (170.711 s). The unchanged grid driver passes **31/31** and the collection
driver **26/26**, both locally in the explicitly inert mode described above. Node
scenarios count once through their unittest wrapper, not again as separate suite cases.

Raw logs, baseline/candidate/native receipts and pictures belong in the handoff/Actions
artifact, not in the public source tree. `COLLECTION-EDITOR-RESULTS.json` is the frozen
local checkpoint; later CI observations must not relabel it as native evidence.

Rollback is the feature diff after its parent, not the older grid implementation.
The optional scope field is additive; no storage migration requires rollback.
HUMAN_TODO choices are unchanged; no human art/territory/UX-feedback answer is inferred.

## Primary interaction references

Reviewed 14 September 2026: [WHATWG native dialog contract](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element),
[W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html), and
[MDN AbortController.abort](https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort).
They inform event/status/cancellation handling; they do not certify accessibility,
network timing or server rollback for this implementation.
