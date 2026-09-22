# Collection drafts and exact-command recovery

Refs #388; builds on the merged #387 typed HTTP/SQLite command owner. This is a
browser recovery layer, not another collection database. No generation, upload,
asset membership, or original media operation is added.

## Owned boundary

`collection-recovery.js` validates and stores bounded, canonical recovery evidence;
`collection-editor.js` owns explicit user actions and the existing editor session.
The existing `AssetWorkspace` collection command transaction remains authoritative.
A local record never proves that a server mutation happened or was cancelled.

Each tab uses `sessionStorage`, keyed by exact Workspace identity. Reload and dialog
close preserve this tab's records. A database replacement at the same origin cannot
adopt the old records. Independent tabs keep independent drafts; the existing server
revision compare-and-swap arbitrates competing writes. A duplicated tab may inherit
a copy of sessionStorage: any inherited pending command retains the same request ID
and exact body, so its replay still uses the same server receipt.

Closing the browser tab, clearing browser data, or changing application origin can
lose sessionStorage. This is **not** a cross-device, permanent, or tab-close backup.
The server's retained receipts are not deleted by a local discard.

## Two separate values

The editable draft retains the target ID, opened revision and baseline, current raw
name/description, and local update time. The immutable pending value retains exact
canonical request bytes, request ID, action, target/revision, first-dispatch time,
and the raw clicked fields. Raw clicked fields are separate from trimmed server
fields so a later whitespace-only edit is not silently discarded on confirmation.

Before POST, the editor validates the entire envelope, writes it, and checks exact
readback. Storage denial, quota, malformed data, changed bytes, wrong Workspace,
or a full journal sends no new collection mutation and keeps visible input.
Newer typing cannot replace, drop, or regenerate the retained pending command.

There are at most 16 entries per Workspace, eight retained Workspace records and
128 KiB total collection recovery bytes in a tab. Commands/receipts are limited to
16 KiB. Existing name/description limits are preserved. Unknown versions, duplicate
JSON keys, non-canonical bytes, invalid identities and unpaired UTF-16 surrogates
fail closed. There is no silent eviction. Explicit cleanup remains possible when
a different Workspace has exhausted the budget; an empty journal removes its key.

## User flow

Use **Recover collection draft…** in Collections, or reopen the original collection.
A retained draft is offered, not automatically applied. **Restore local draft**
restores local text and its original baseline without a request. It restores focus
to Name. Recovered pending commands keep Save and Remove locked.

**Inspect command status** sends only a GET bound to the retained request/Workspace.
Unknown is still unknown. **Retry exact command…** requires explicit confirmation
and posts the same bytes once with the same request ID; newer text is not sent.
There is no automatic retry, rebase, replacement request ID, or model job.

A committed reply is accepted only after verifying both the canonical retained
receipt SHA-256 and the command SHA-256 using WebCrypto. The original receipt's
result is the historical baseline; the separately returned current metadata is an
observation, not a replacement for that baseline. Stale/deleted/current divergence
is shown alongside the local draft and cannot silently overwrite a later writer.

Only recognized typed pre-commit refusals release pending ambiguity. An unstructured
HTTP error, mismatching receipt, request-ID conflict or response loss preserves it.
Session epochs and Workspace checks prevent late responses from populating or
unlocking a replacement dialog. Discard clears only local recovery, states that it
does not cancel server work, keeps visible text, and does not recreate the record
on close unless the user edits again.

## Verification and evidence limits

Run from repository root:

```console
python -m unittest discover -s tests -p "test_collection*.py" -v
python tests/collection_command_browser.py
python tests/collection_editor_browser.py --out .runtime/collection-editor-proof
python -u tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The focused suite runs the 21 journal and 19 recovery-editor Node contracts through
Python wrappers, alongside existing collection/SQLite/HTTP tests. New regressions
were first observed failing before implementation. Review regressions also failed
before fixes for discard-then-close, exhausted-budget cleanup, raw newer whitespace,
and restore focus.

`collection_command_browser.py` defaults to native same-origin Chromium HTTP,
sessionStorage and WebCrypto against temporary real SQLite. It covers 13 scenarios,
including lost committed responses across reload, unknown/exact retry, two tabs,
server-store reopen/identity replacement, storage refusal and keyboard operation.
The dedicated read-only workflow runs it on Ubuntu and Windows; it installs no
models and has no repository-write permission. The existing full-shell collection
browser lane remains wired separately.

In a managed browser that refuses loopback navigation, append `--inert` explicitly.
That substitutes browser transport, storage, digest and reload semantics; the real
collection HTTP and SQLite remain exercised. Local inert results are **not** native
origin/storage proof. Native exact-head CI must be reviewed before closing #388.
Local evidence: 49 focused Python tests passed, all 13 inert protocol scenarios
passed, all 28 inert actual-shell checks passed, and the repository validator passed.
The clean baseline ran 3,289 tests with 20 skips. Full changed-tree and hosted CI
results are recorded on the PR rather than inferred from these focused checks.

No human creative acceptance, inference performance, or installed-workstation
qualification is claimed. HUMAN_TODO remains unchanged.
