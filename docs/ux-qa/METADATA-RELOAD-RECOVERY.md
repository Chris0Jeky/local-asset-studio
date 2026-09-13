# Metadata draft and save recovery across reloads

The conditional metadata commands and SQLite receipts introduced in PR #199
now have a per-tab browser journal. An editor draft retains its opened metadata
revision, baseline, current fields, conflict snapshot, and any exact pending
command. Library updates retain their immutable command and selected IDs.
The journal contains metadata text only, not media files or generation recipes.

Before sending an asset metadata POST, the client writes and reads back its
recovery record. Unavailable storage, quota errors or an unreadable existing
record prevent a new metadata request. Storage failures during newer typing
leave that text visible and tell the operator to keep the tab open; that newer
text is not promised to survive a reload until it can be stored successfully.
Malformed stored data is retained for inspection, never silently replaced.

Reloading reads the journal and displays a recovery control in the library.
It does not POST, retry, poll a receipt, or automatically open the editor.
**Review retained draft** restores the original revision, even if a background
workspace read has already seen a newer version. **Check save status** reads
the durable receipt; **Retry exact save** explicitly resends the original bytes
and request ID. Newer typing is not included in that retry.

A conflict keeps both versions available across reloads. Choosing a saved
snapshot or rebasing local edits is read-only. A later explicit save creates
a new command against the reviewed revision. Confirmation of a lost Trash
reply preserves any text entered after that request instead of closing the
editor. An unresolved command cannot be replaced by opening another asset.
Ordinary draft discard still requires consent. If the asset is unavailable,
the library recovery panel retains an escaped copy of its draft text.

Storage is `sessionStorage`, scoped to the browser tab and origin. This covers
page reloads within that tab. Closing the tab, clearing browser data, private
browsing policies and browser/OS crash restoration have browser-specific
retention behavior; this is not a cross-device or permanent draft backup.
No journal entry starts generation or changes a Production allowance.

## Verification

`node tests/asset_recovery_contracts.cjs` recreates the actual workspace script
with retained storage across 14 scenarios: in-flight and lost replies, exact
retry, unsent and newer drafts, conflict rebasing, Trash, batch selection,
quota/read/clear failures, explicit discard and missing assets. Existing detail,
metadata and handoff contracts remain part of the offline gate. Browser evidence
is recorded separately with its native or injected-storage mode stated.

**Refs #204.** This per-tab/origin draft-recovery slice does not close the
workspace-identity, native-browser, real-SQLite or server-restart acceptance
work. Its in-memory browser fixture cannot show that different Workspace
identities are isolated, that a browser retains its actual storage, or that an
actual SQLite receipt remains recoverable after a controlled server restart.

Successful metadata persistence does not record artistic, licensing or owner
acceptance. Existing choices remain in [HUMAN_TODO.md](../../HUMAN_TODO.md).
