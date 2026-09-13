# Asset metadata concurrency — design and implementation record

## Outcome and decision

Extend the existing Workspace SQLite boundary, not a separate project or job store.
Every browser/agent metadata command must carry the exact revisions it read and a
unique request identity. Checking revisions, writing all selected assets, incrementing
revisions and saving the success receipt belong to one immediate transaction.

A per-asset revision is deliberately more conservative than automatic field merging:
even disjoint-field changes require explicit review. Browser-only locking is rejected
because another tab or agent can write concurrently. Re-reading the latest revision
immediately before a blind write is rejected because it conceals a stale form.

## Implementation sequence

1. Reproduce stale-form loss with two actual Workspace clients. Add revision migration,
   strict command validation, atomic compare-and-write, request receipts and bounded
   conflict projections. Test concurrency, migration, bulk rollback, identity reuse,
   trash/restore, missing assets and injected receipt failure.
2. Expose the same command through existing `/api/assets/update`; return structured
   conflicts and precondition errors, and add a read-only receipt lookup. Check actual
   production Host/Origin rules with no Studio/GPU construction.
3. Wire detail and library mutations to the same protocol. Retain drafts on conflict;
   offer explicit read-current or keep-edits rebase, with a field comparison. Never
   retry a write automatically; a response-loss retry keeps the exact request bytes.
4. Run real browser scenarios against actual SQLite/production command handlers with
   synthetic non-generation APIs. Retain receipts/screenshots, run the complete offline
   suite and repository checks, publish a PR and record hosted CI separately.

## Contract

`metadata_revision` starts at zero and advances for edit, favorite, review, trash,
restore and membership changes. Deleting a collection advances member asset revisions.
Unconditional legacy metadata HTTP writes fail with 428; reload the Studio and update
agent callers rather than silently bypassing protection. Source media and recipes do
not change. Existing setups/collection-name commands are separate interfaces.

`request_id` is an opaque UUID-like token; `expected_revisions` maps every selected ID
to one nonnegative safe integer. The entire batch fails if any asset is missing or
changed. The same successful request can be observed or explicitly resent: the stored
receipt is returned without another mutation, even after restart or a newer edit.
Reusing its ID with different content is a conflict. A missing receipt is unknown,
not proof that a delayed request cannot still commit. Receipt insertion failure rolls
back the metadata too. This guarantee is local to one Workspace database, not ComfyUI
or distributed exactly-once execution.

Browser review offers current saved fields beside the local draft. Taking current
values or rebasing the user's changed fields sends no write. A subsequent Save uses
that reviewed revision and remains conditional if another client wins the race again.
Lost responses expose receipt lookup and exact-request retry; no model, generation,
installation, process or acceptance operation is part of metadata recovery.

## Evidence

Pinned base: `06bd93aed2f019cb978eb5795e9f116cfb7ff749`, tree
`9561db4b2bf6bba7178f10554bcc95479f0d6a7d`. A connector-delivered source
archive was normalized by Git attributes and verified against that entire tree.
The helper snapshot workflow is isolated outside the product branch.

The original stale-form regression failed before implementation: no conflict was
raised and the confirmed note was overwritten. After implementation, 18 actual SQLite
cases, six production HTTP cases and a wrapper containing ten real-script frontend
contracts pass. The previous 17 asset-session contracts also pass. The full offline
suite ran **1,488 tests: 1,473 passed, 15 skipped, no failures** in 170.846 seconds.
An existing exit-time socket ResourceWarning remains visible in the retained log.
Repository validation passed (66 preset graphs/bindings, 121 pins, 86 LoRA names).

Local Chromium passed **21 new two-client/recovery expectations** against production
metadata HTTP plus SQLite, and **30 previous asset-detail expectations**. Both local
runs explicitly used inert browser storage/transport after native navigation returned
`ERR_BLOCKED_BY_ADMINISTRATOR`; the new CI step runs native HTTP, with its actual
result recorded in the PR rather than inferred here. The recovery tests caught a
lost-Trash/newer-notes regression before publication and now pin its fix.
Screenshots and JSON receipts are in ignored `.runtime/metadata-browser/` and
`.runtime/asset-detail-regression/`, with source identities summarized in
[METADATA-RESULTS.json](METADATA-RESULTS.json).

This is a single-agent implementation and self-review, not an independent model-review
claim. Native hosted integration is a separate gate. These fixtures cannot establish
owner-PC inference, artwork quality, screen-reader behavior or native-editor acceptance.

## Sources reviewed 13 September 2026

- SQLite transaction control: https://www.sqlite.org/lang_transaction.html
- Conditional requests and lost updates (428): https://www.rfc-editor.org/rfc/rfc6585#section-3
- Status messaging: https://www.w3.org/WAI/WCAG22/Understanding/status-messages

## Agent and API integration

Read `GET /api/assets/<id>/metadata` or the existing Workspace snapshot. Preserve
that returned revision alongside the draft; never fetch a newer revision merely to
force an old form through. Prepare the command once, then retain its exact bytes and
request ID until the result is known:

```json
{
  "ids": ["example-asset-id"],
  "action": "edit",
  "notes": "Review the right hand against the source crop.",
  "expected_revisions": {"example-asset-id": 3},
  "request_id": "c640ab0711bf43f3b79a9c7b2f497bcbd6"
}
```

Send to the existing `POST /api/assets/update`, using Studio's unchanged loopback
Host/Origin rules. A 200 response contains `status: applied`, the same request ID,
`updated` IDs, resulting `revisions` and normalized `applied` fields. HTTP 409 with
`asset_revision_conflict` contains all conflicting/missing IDs and at most ten
current metadata snapshots. No media paths, recipes or graph payloads are included.
All assets in that command remain unchanged. Other 400/409/428 responses describe
invalid input, identity reuse or missing preconditions; do not auto-fix them.

On response loss or 5xx, use `GET /api/assets/commands/<request_id>`. A matching
receipt confirms the original command only, not the current state after later edits.
`status: unknown` authorizes no new command. An explicitly requested retry may resend
identical bytes with the same request ID; SQLite's journal makes that retry harmless
whether the original commit happened or not. To modify intent, resolve the earlier
operation first, read/review current metadata and use a new ID. These IDs are integrity
and reconciliation keys, not authentication or an art-approval identity.

The JavaScript client rejects mismatched/invalid success receipts and keeps their
outcome unconfirmed. The UI does not share a helper model or generate new suggestions
as part of conflict resolution. The ordinary Save button submits only dirty fields;
this reduces accidental changes but does not replace the revision check.

## Recovery and interaction details

The initial conflict comparison includes local text, text when the editor opened and
text saved elsewhere. Editing during a conflict updates the comparison. **Keep my
edits for review** preserves locally changed fields and adopts remotely changed,
untouched fields; it does not persist anything. Both same-field and disjoint-field
changes require the subsequent explicit Save. Another intervening client still
causes a fresh conflict rather than being overwritten.

Favorite and Trash are separate intents, never replayed by the conflict choice.
During an unconfirmed save they stay disabled. The original command can be checked or
retried exactly; text typed after a lost response is not sent with that retry. A
recovered Trash command updates its acknowledged state but cannot close the editor
and discard text entered after the first attempt. The new regression tests caught
and fixed that recovery edge case. Malformed conflict snapshots remain unavailable,
not silently converted into empty metadata. A confirmed library mutation does not
wait for a stalled library refresh before releasing its operation lock.

## Rollout, retention and limits

The migration adds one column and one receipt table to the existing database;
original media, setup records, recipes and lineage are not rewritten. Migrations are
idempotent and serialized. Existing Python/HTTP callers of `AssetWorkspace.update`
must adopt the same conditional contract; old unconditional callers fail visibly.
Reload already-open Studio pages after updating. No compatibility path reads the
latest revision on the caller's behalf and then blindly writes.

Use SQLite's backup API for a consistent pre-rollout backup, rather than copying only
a live main database file while ignoring WAL data. No backup, runtime restart or
user-database migration was performed by this QA session. Reverting to an older
writer removes the revision guard and can invalidate receipt assumptions; retain
conditional writes or restore a consistent, operator-approved backup at an idle
boundary. Do not delete receipts to make a request run again.

Receipts are compact but retained indefinitely in this first implementation. A future
retention policy needs explicit expired/tombstoned request semantics before pruning;
silent expiry could make a previously successful request look absent. Browser drafts
and pending-operation objects remain transient across reload/crash. The dialog warns
before leaving an unconfirmed write, but this is not reload-draft recovery. Database
receipts survive restart and remain queryable by the retained request ID. There is no
claim of network-distributed exactly-once generation or general multi-editor document
synchronization. Collection names and setup saves remain separate commands.

## Reproduction commands

```sh
python -m unittest discover -s tests -p 'test_asset_metadata*.py' -v
node tests/asset_detail_contracts.cjs
python tests/asset_metadata_browser.py --out .runtime/asset-metadata-proof
python tests/asset_detail_browser.py --out .runtime/asset-detail-proof
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Browser dependencies belong in a separate test environment. The metadata browser
fixture creates its own server on port 8191 and refuses to start if occupied; it must
never be pointed at a running Studio. Non-generation routes use synthetic responses,
but metadata mutations, conflict detection and receipt lookup use the production
HTTP handler and actual temporary SQLite storage. One test deliberately drops the
HTTP connection **after** a successful commit. `--inert` is explicitly separate:
Chromium still renders the actual HTML/scripts/styles but storage and browser API
transport are injected, not native-origin behavior. Native mode is the CI default.
