# Asset recovery: response ownership and keyboard continuity

Refs #393 and #204. This is a focused child of #710, which supplies read-only
lifecycle inspection over the #698 persistent shelf. It does not replace either
feature, modify the server command protocol or close the complete issue bundle.

## Reproduced defects

The published `workspace.js` checked an asset ID/editor epoch for a detail reply,
but did not check the current Workspace or pending operation. Its `finally`
block released global controls even if another request had replaced it. The
library handler did not bind a completion to the pending operation at all: a late
reply could clear newer local recovery and project historical metadata onto a
same-ID row from another Workspace. The same issue affected delayed refusals.

Seventeen deterministic contracts exercise the actual editor and journal code.
Fourteen failed against the published parent modules before the correction; three
were existing invariants. Success, conflict and transport failure are separately
covered, along with same-ID operation replacement, stale callback invocation,
Workspace A-to-B-to-A observations and ordinary same-Workspace refresh.

Native-DOM interaction also reproduced focus loss when receipt confirmation
removed the focused status button. A status check that finishes after newer
notes are typed must not move focus out of those notes.

## Ownership model

Each detail/library request has a transient owner token. Before accepting a
reply it checks that token, its exact pending operation and Workspace. Detail
requests also check the existing editor epoch and asset scope. A Workspace
observation generation increments only when a successful library read changes
Workspace identity, preventing an observed A-to-B-to-A cycle from reviving an
old callback. Ordinary refreshes within one Workspace do not cancel a valid save.

The token is intentionally not persisted: it owns an in-memory callback, not a
server mutation. The existing journal and shelf retain exact command bytes and
request IDs. A stale callback may release only its own in-memory request state;
it must not clear or rewrite another request's recovery or unlock its controls.
A historical receipt remains discoverable by a subsequent explicit status read.

Returning to the original Workspace leaves the pending controls operable and
requires a deliberate status check. No navigation, refresh, timeout, dropped reply
or response suppression creates a new request identity or automatically retries.
Pre-dispatch shelf checks continue to gate the original POST. Read-only status
still does not depend on optional shelf persistence.

## Keyboard behavior

Recovery panels avoid replacing identical content. When a render removes its
focused recovery button, focus moves to the matching replacement button, or to
Save details / conflict review / library Refresh when the old action disappears.
Only focus already within the replaced recovery controls is eligible for this
return: a late reply does not steal focus from newly typed notes or another view.

## Verification

```
python -m unittest discover -s tests -p test_asset_recovery_session.py -v
node tests/asset_detail_contracts.cjs
node tests/asset_recovery_contracts.cjs
python tests/asset_recovery_session_browser.py --out .runtime/asset-recovery-session
```

The new browser driver uses the actual HTTP metadata handlers and two temporary
SQLite Workspaces with identical asset IDs. It holds replies after server commit,
switches the viewed Workspace, checks byte-identical retained recovery, then
returns and explicitly inspects the original receipt. Thirteen checks cover
request counts, focus, newer typing, late detail/bulk replies and unchanged
foreign metadata/original bytes. All source and review text is synthetic.

The dedicated read-only Ubuntu/Windows workflow checks out the exact PR head.
`--inert` substitutes browser storage/transport and must never be represented as
native origin/storage evidence. Local focused testing uses the supplied ZIP with
hash-matched parent editor/journal modules; whole-parent integration is validated
by hosted CI, not inferred from that partial local reconstruction.

## Remaining boundaries

The existing retry/refusal state machine, collection recovery (#684), fatal UTF-8
import decoding (#706), durable selected-File staging (#394) and reviewed-setup
history/forks (#395) remain separate. This slice does not add receipt expiry,
reconcile physically copied databases sharing one identity, qualify all filter or
asset-removal focus paths, perform a screen-reader audit or certify browser-menu
200% zoom. It generates no images, installs no models and changes no HUMAN_TODO
creative, licensing or workstation-acceptance decisions.
