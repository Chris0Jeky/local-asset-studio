# Asset review reload recovery

## Design and scope — 13 September 2026

Refs #204, building on merged #199; this is separate from named-setup source handling in #202.

Keep a bounded per-tab recovery journal in sessionStorage: workspace database identity, asset ID,
opened metadata/revision, current draft and, separately, the exact pending command body and
click-time form snapshot. SQLite remains authoritative. Do not add a queue or sync engine.

On opening an asset with a retained envelope, offer Restore / Inspect / Discard. Do not silently
replace the form or send any mutation. Restore reads the current metadata first; a changed revision
uses the existing conflict comparison. A pending command is reconstructed with its original ID
and bytes, never regenerated from newer typing. Check save status remains read-only; exact retry
is explicit and goes through the existing idempotent command service.

A journal contains at most eight envelopes and 256 KiB of UTF-8 JSON, with at most 96 KiB per
record. No automatic eviction or expiry. Session storage is independent per tab and survives a
reload; closing the tab clears it. This is not a browser-crash backup guarantee. Copies created by
opening a duplicated tab remain independent; an inherited pending command still has the same ID.
Unknown or malformed versions are never executed. Storage failures must be visible, and cannot
advertise successful recovery. A quota failure may offer explicit in-memory-only saving when there is no older pending record.
Unreadable/malformed journals and retained older commands cannot be bypassed; their original bytes stay intact.

A persistent random identity in the existing workspace SQLite database distinguishes different
workspaces even at the same origin, without storing server paths in the browser. Copying a database
retains its identity; callers must not treat that UUID as authentication or a media-integrity check.

## Implementation sequence

1. Reproduce missing reload state and pin the journal invariants with pure Node contracts.
2. Add and test the additive database identity; expose it in the existing workspace snapshot.
3. Implement strict, bounded journal reads/writes and review-editor integration, persisting before
   dispatch. Confirmation advances only the submitted snapshot; newer typing stays unsaved.
4. Add real browser/SQLite scenarios: draft reload, two tabs, response loss then reload, receipt
   check, exact retry, stale revision, failed reads, unavailable storage, changed workspace and
   explicit discard. Assert zero mutations on restore and status checks.
5. Run existing metadata/detail regressions and the full offline suite. Publish native browser CI
   independently of local browser availability. Retain evidence and remaining acceptance honestly.

## Alternatives rejected

Unscoped localStorage mixes tabs/workspaces and needs a new concurrency protocol. Saving drafts to
server metadata confuses local intent with confirmed state. beforeunload alone cannot recover a
lost command identity. Rebuilding a request after reload creates a new identity and loses reliable
receipt reconciliation. Broad automatic retry and inferred completion are not acceptable.


## Shared command and scope boundaries

The browser sends `workspace_id` with newly prepared detail commands. The existing Workspace
transaction checks it **before receipt lookup or row writes**, so a resumed command cannot apply
to a different database that happens to contain the same asset ID and revision. The field is
optional for older clients; existing metadata revision and exact-command fingerprint checks remain.
No authentication or remote-access claim follows from this local database identity.

Only a confirmed field advances the baseline. A confirmed Favorite must not certify draft notes,
and a restored receipt for an earlier Save must not overwrite newer typing. Closing an editor with
an unconfirmed write keeps its local record; explicitly discarding it explains that this cannot
cancel a server change. Normal user-approved closing of an unsaved, nonpending draft discards that
local draft. Reload does not dispatch a write or perform this discard.

Unknown receipt means unknown, not failure or permission for a new command. Exact retry remains
explicit and carries the retained ID, body and original revision. This change adds no expiry to
server receipts. Any future receipt garbage collection must preserve the prior no-reapplication
contract through tombstones or a versioned expiry protocol before callers may reuse old identities.

## QA and reproducibility

`tests/review_recovery_core.cjs` covers eleven bounded journal scenarios; the three real-Workspace
script hook scenarios in `tests/review_recovery_hooks.cjs` prove checkpoint-before-dispatch,
no replay on opening, and retained pending identity on uncertain completion. Two unittest wrappers
run these (they are not fourteen extra tests added to the ordinary suite count).
`tests/test_workspace_identity.py` covers restart/different stores, concurrent identity migration
on an existing database, and two actual stores with the same asset ID rejecting a cross-store save.

The browser driver exercises 27 expectations against real temporary SQLite and the actual
production metadata routes. It retains source hashes, write bodies, screenshots, JavaScript errors
and mutation counts. Native mode uses actual `sessionStorage` and `page.reload` with two tabs.
The explicit `--inert` mode instead copies only the journal between fresh pages using substituted
storage/transport. This is a component simulation, **not native reload or storage evidence**.
Tests bind only a temporary loopback fixture on port 8191 and refuse an occupied port; they must
never target a running user Studio. No Studio/GPU worker or model environment is constructed.

```sh
node tests/review_recovery_core.cjs
node tests/review_recovery_hooks.cjs
python -m unittest discover -s tests -p 'test_workspace_identity.py' -v
python tests/review_recovery_browser.py --out .runtime/review-reload-proof
# Only for an environment where native browser navigation is policy-blocked:
python tests/review_recovery_browser.py --inert --out .runtime/review-reload-component
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The new CI lane installs browser-only test dependencies in an ephemeral runner, not in the
managed model Python. It uses default native mode. Native CI results must be read at the actual
published head; successful component results are not substituted for them. Exact local and hosted
checkpoints are recorded in the accompanying result file and PR conversation.

## Remaining acceptance under #204

This is per-tab **reload** recovery, not a durable backup after closing the tab or a browser/OS
crash. Bulk metadata commands remain transient. Closed-tab recovery, explicit journal repair/reset
for malformed versions, a durable user export/import path, and broader deleted/trashed-asset and
screen-reader/zoom acceptance remain separate follow-ups; #204 remains open. A missing asset is
still inspectable/discardable from the recovery shelf, without invented remote state. No inference,
artwork, native editor, account permission, or owner-PC acceptance is claimed.

An unrelated fresh-database parallel initialization race was reproduced against unchanged main and
tracked in #215 (2 failures in 24 synchronized constructor calls, not a failure-rate estimate). It occurs at the existing WAL pragma.
The identity migration test therefore explicitly uses an existing database, not a claim of safe
parallel creation. Do not add blanket retries to hide initialization failures in this UX slice.

Primary platform contract: [MDN sessionStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage),
reviewed 13 September 2026: tab/origin partition, reload retention, opener-copy behavior, closing-tab
lifetime and unavailable storage. Browser policy/quota can still invalidate local recovery.
