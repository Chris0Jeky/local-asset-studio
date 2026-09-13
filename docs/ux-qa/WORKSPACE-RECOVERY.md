# Workspace-bound asset recovery

## Reconciled scope — 13 September 2026

This is the revised scope of PR #216, based on main
`22ec26dc549a4648a6e94f80f5d3c870f03c6520`. It extends the journal introduced by
merged #211 and the conditional metadata service from #199. #202's named-setup
source guards and #205's causal browser tests remain intact.

The initial #216 implementation at `ac9702d` overlapped #211 while both were being
written. Its parallel review-recovery modules, extra shelf, eight-record policy,
and standalone workflow are superseded, not additional features to install. The
revised tree retains one journal owner (`asset-recovery.js`), one editor
(`workspace.js`), one Workspace persistence service, and the existing browser CI
lane. The original prototype and its results remain in Git history; their test
counts do not certify this revision.

Refs #204 and #16. Neither umbrella issue is closed by this slice.

## Practical failures and expected behavior

A person saves notes in Workspace A, the response is lost, and another tab saves a
newer correction. On returning, the first person must see both their retained
work and the newer saved state. A receipt can prove the earlier mutation happened;
it cannot prove those values are still current.

A second scenario uses two separate databases with coincident asset IDs. Studio
is restarted onto B at the same address while the browser still holds A's draft
or exact save. That coincidence must not let A's command change B, read B's receipt,
or adopt B's metadata as an A conflict. Recovery remains visible for inspection
and return to the original Workspace.

The pre-change actual-script probe reproduced the historical-receipt defect:
`dirty=false`, no conflict, and a “Details saved” message while an independently
observed newer note existed. A new command-scope regression failed because its
`workspace_id` was absent. A further integration regression demonstrated that a
pending bulk command could lose its retained selection after the page selection
changed. These are separate causal checks, not a statistical quality score.

## Data ownership and transaction boundary

`AssetWorkspace` adds a singleton `workspace_identity` table in the existing
`BEGIN IMMEDIATE` migration. Its opaque, random 32-hex-character ID survives a
normal reopen and differs between independently initialized databases. The
identity is read from the connection used for each operation, never from a Python
property cached across database replacement. No filesystem path is exposed.

The Workspace snapshot carries the identity at the top level and on each asset.
Metadata GET, receipt GET, and metadata commands accept an explicit expected
identity. Validation and actual data access share one SQLite transaction:

| Operation | Transaction and result |
|---|---|
| Workspace snapshot | One read transaction returns identity and its assets. |
| Scoped metadata GET | Verify expected identity, then read metadata on that same connection. |
| Scoped receipt GET | Verify identity before looking up the receipt; return historical result plus a bounded current observation. |
| Scoped command POST | Within `BEGIN IMMEDIATE`, verify identity before receipt lookup, revision checks, or mutation. |
| Repeated exact command | Preserve original request identity, fingerprint and applied result; do not apply it again. |
| Foreign identity | HTTP 409 `asset_workspace_conflict`; no foreign metadata or receipt is returned and no mutation occurs. |

A scoped receipt response separates immutable `applied` / `revisions` from
`current`. The latter contains at most ten affected metadata records observed
within that response's transaction. It contains no media paths or recipes and is
not written back into the durable receipt. Unscoped receipt consumers retain the
original historical shape. A missing current asset is represented by its absence,
not invented metadata; the historical receipt survives deletion.

This avoids the sequence “read identity A, open another connection now pointing
to B, read B metadata.” A regression changes the service's database path after
scope verification and proves the response remains from the original connection.
Real HTTP tests also switch the service between requests and require refusal.

SQLite's transaction isolation is the relevant boundary, not two independently
successful HTTP requests. See the [SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html).

## Browser journal and interface

New records use envelope version 2 in the **existing two per-tab journal slots**:
detail and library. The established bounds remain 512 Ki JavaScript code units
per envelope and 128 Ki code units per serialized pending command. These are
string-length bounds, not a measured UTF-8 byte or browser storage quota guarantee.
No extra journal, eviction, expiry, automatic save or polling loop is introduced.

The envelope binds its metadata, immutable pending command, and any conflict
observation to one Workspace ID. Detail writes use the identity of the opened
asset, not whichever identity a later library refresh happens to observe. The
same command bytes and ID remain retained through a wrong-Workspace refusal.

Version-1 records remain readable for **inspection and deliberate local discard**.
They are not silently migrated by guessing the current Workspace. Their text is
escaped, and neither restore nor receipt lookup nor exact retry can run with an
unknown identity. Malformed data and storage failures retain existing fail-closed
behavior. A failing journal write prevents a new metadata POST; a failing clear
cannot silently forget the pending request.

The recovery panel explains a different or unknown Workspace and exposes retained
draft/command text. Discard removes only the local record. Its confirmation warns
that forgetting an unconfirmed command cannot cancel or undo a server mutation.
It remains possible to return to A and recover there.

When a receipt is confirmed, only its actually applied fields advance the form's
baseline. Favoriting does not certify unsaved notes. Newer typing is kept. If the
receipt's current observation, or a newer same-Workspace library observation,
shows a later revision, the existing comparison UI opens with “earlier save
confirmed” wording. It does not falsely say the first save was rejected or the
entire current form is saved. Rebase remains a read-only review action; a later
Save creates a new conditional command against the reviewed revision.

Library pending selection is recorded with the command, independently of later
filter/selection changes. Changing Workspace clears the current selection; it
cannot select coincident foreign IDs. Returning to the original Workspace can
restore that command's retained selection. Legacy unscoped selections are not
automatically bound even while the current identity is unavailable.

`sessionStorage` scopes this mechanism to the current browser origin and tab;
ordinary reloads are covered, not a guaranteed backup after closing the tab or
clearing browser data. An opener can initially copy session storage, so this is
not a unique-tab security identity. See the [browser storage documentation](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage).

## Protocol examples and compatibility

Discover `workspace_id` from `/api/workspace`, retain it with the snapshot and
include it in the exact command before dispatch:

```json
{
  "action": "edit",
  "ids": ["asset-id"],
  "notes": "Preserve the revised costume",
  "expected_revisions": {"asset-id": 4},
  "request_id": "64ba2f8be62647c7863b5ca4e84ca6a4",
  "workspace_id": "d60743cbec5c4e88b44f6c5e9ba98b87"
}
```

These are illustrative IDs; use the actual snapshot. Scope read-only recovery too:

```text
GET /api/assets/asset-id/metadata?workspace_id=<retained-workspace-id>
GET /api/assets/commands/<original-request-id>?workspace_id=<retained-workspace-id>
```

Blank, malformed or repeated query scope values are rejected. An unknown receipt
remains unknown, not proof a new request ID is safe. Explicit exact retry retains
the original body, ID and expected revisions. Scope participates in the command
fingerprint; adding scope to an old already-submitted command changes its identity
and must not be treated as its exact retry.

The server field is additive and optional for historical callers. Those callers
still need the existing revision/request-ID preconditions but **do not gain
cross-Workspace isolation until they supply scope**. This is not a claim of
universal human/agent parity. Restore/export migration for old unscoped journals
is future work; this UI deliberately does not rebind them.

No receipt expiry or retention policy changes. A physical database copy preserves
the identity; independently operating cloned databases are not distinguished by
this mechanism. Identity is neither authentication, authorization, media integrity,
nor protection from an attacker editing local storage.

## Implementation and acceptance sequence

1. Recover surviving PRs and inspect #216's two review findings against merged
   #211. Reproduce absent command scope and the historical-receipt clean-state bug.
2. Add the database identity, same-transaction scope checks, additive GET/POST
   protocol and immutable-receipt/current-observation separation. Exercise actual
   SQLite, reopen, deletion, invalid scope and a deterministic mid-read service switch.
3. Extend the existing journal/editor. Preserve legacy inspection, exact retry,
   storage refusal and bulk selection. Test actual shipped JavaScript with held
   responses, two workspaces, newer typing and current-revision conflicts.
4. Exercise the complete shell with production metadata HTTP and two temporary
   SQLite databases: commit-then-drop, pre-commit failure, reload, another tab's
   edit, status-only lookup, exact retry, Workspace switching, legacy inspection,
   explicit discard, denied storage, keyboard controls and a 390px conflict view.
5. Rerun retained asset-detail/metadata/reload checks and the full offline suite.
   Extend the existing native Actions matrix rather than introducing another lane.
6. Publish a merge commit over main and the old #216 head, retaining all merged
   work. Request the second and final scoped review; record actual native CI
   evidence separately from local component evidence.

## Verification checkpoint

`WORKSPACE-RECOVERY-RESULTS.json` records the source identity, matching expectation
IDs and limitations. Final local full suite: **1,584 run; 1,569 passed, 15 skipped,
no failures** (131.065 seconds). The focused suite has **13 unittest cases**:
9 SQLite + 3 HTTP + one wrapper executing 11 JavaScript scenarios. The JavaScript
scenarios are not counted again in the full-suite total.

The new browser driver passes **25 expectations**. Retained browser drivers pass
**21 metadata, 30 detail, and 19 reload** expectations. Local native navigation was
blocked with `ERR_BLOCKED_BY_ADMINISTRATOR`; these local browser results use
explicit `--inert` transport/storage and document recreation. Actual metadata
requests still reach the real production HTTP handlers and temporary SQLite.
They do **not** prove native `sessionStorage` or `page.reload`. The default driver
and existing Actions workflow perform those native checks. Hosted results must be
read from the current-head receipt, never inferred from this local checkpoint.

The fixture initially inspected text inside a collapsed details element and
assumed a returned function retained its binding; both fixture mistakes were
corrected through actual user interaction/invocation, not weakened assertions.
Those failed attempts are retained alongside red/green and final logs. The narrow
wrong-Workspace screenshot is captured after explicitly setting the recreated
page to 390px. Screenshots are synthetic UI evidence, not generated artwork.

Pillow deprecation and an exit-time unclosed test-socket ResourceWarning remain
visible. Deliberately injected worker-failure diagnostics are not suppressed.

```sh
python -m unittest discover -s tests -p 'test_asset_workspace*.py'
node tests/asset_workspace_scope.cjs
python -m unittest discover -s tests
python scripts/validate-repo.py
# Use development/CI Python, never a managed model environment:
python tests/asset_workspace_browser.py --out .runtime/asset-workspace-proof
# Only for explicitly labelled component evidence when native navigation is blocked:
python tests/asset_workspace_browser.py --inert --out .runtime/asset-workspace-component
```

Fixtures refuse an occupied loopback port rather than attaching to a running
Studio. They never submit generation, switch a backend or install a model.

## Remaining work

#204 remains open for durable export/import, closed-tab and crash recovery,
complete deleted/trashed/collection lifecycle acceptance and broader accessibility.
This slice tests deleted receipt behavior at the store boundary, not every deleted
asset UI route. Screen-reader and actual 200% zoom acceptance are not claimed.
Collection rename concurrency, named setup concurrency and arbitrary document
journaling are different state owners.

The pre-existing concurrent **fresh** database WAL-initialization gap is #215.
The identity migration test here uses an already initialized database; it is not
advertised as resolving that separate contention problem. No live workstation,
model, native editor, output-quality, licensing or artistic acceptance follows
from these software tests. No new human creative decision or HUMAN_TODO change is
required.
