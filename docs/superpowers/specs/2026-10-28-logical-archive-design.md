# Reversible logical Archive

## Intent

First delivery slice of #1678: put finished Library pictures away without
trashing them, changing privacy, relocating bytes, or losing their recipes,
lineage, reviews and collection memberships. This is not completed-run privacy
migration. The owner delegated continuation; implementation choices below are
agent choices within that issue's stated boundaries, not new owner approvals.

## Approaches and choice

Reuse Trash: rejected because putting work away must not change its Trash state.
Move media directories: rejected because names and organization must not own
canonical content-addressed paths. Add a nullable `assets.archived_at` field and
reuse existing revisioned commands: selected. One SQLite transaction, the same
request receipt and the same recovery journal remain authoritative.

## Contract

- `archive` / `unarchive` actions use `AssetWorkspace.update`, with the original
  Workspace, exact IDs, expected revisions and request identity. They change
  only the Archive timestamp and revisions, atomically. No-op rows do not burn
  revisions, including at the revision ceiling. Replay returns the original
  receipt; newer state appears separately in its observation. No automatic retry.
- Archive and Trash are independent. Archiving a trashed asset does not restore
  it; restoring Trash does not unarchive it. Legacy assets start unarchived.
  Originals, IDs, output order, recipes, lineage and collections remain intact.
- Bounded asset pages accept independent `archive=active|archived|all`, default
  `active`. The legacy `visibility` filter still means non-Trash / Trash / both.
  Privacy remains regular/private/all. Archive, privacy, search and sort bind
  the cursor; private changes do not invalidate regular pagination.
- Summaries include `archived_at` only when archived, retaining the legacy
  unarchived response shape. Malformed non-null Archive metadata is refused,
  not silently treated as active. Explicit selection and family inspection can
  still retrieve archived IDs. Same-run siblings explicitly request all Archive
  states, and collection counts retain their documented non-Trash membership
  semantics (including archived members), rather than becoming view-dependent.
- Current metadata/conflict and lifecycle observations include `archived_at`,
  including null, so an old receipt cannot hide newer Archive state. Older
  recovery records without that field remain readable.
- Library has a labelled Active / Archived / All archive filter, single-item
  Archive / Unarchive and bulk actions. Filter changes preserve selection,
  off-page IDs, current editor text and exact pending command bytes. Privacy
  preference storage remains owned by the existing scope. Archived items are
  labelled when shown alongside active ones. Archive does not close or discard
  an unsaved details draft. No generation or installation follows any action.
- Typed asset reads, CLI and MCP understand the filter and validate every returned
  timestamp/filter. A separate agent mutation slice may expose the same command
  owner; no new write authority is implied by read-mode discovery.

## Not included

Physical moves, completed-run reclassification, migration plans/journals,
retention deletion, new execution queues, archive-specific collection counts,
model work and owner art/licensing acceptance. Archive is organization, not a
privacy or access-control boundary. Existing direct links and media remain usable.

## Verification

Causal tests must fail on the unmodified main snapshot, then pass on the change.
Cover reopen/migration, exact-byte retention, mixed and no-op batches, revision
conflicts, same-request replay, receipt recovery, independent privacy/Trash,
private-stamp isolation, search/pagination and strict clients. Exercise real
shipped JS and native browser journeys, including a lost acknowledgment, retained
notes and off-page selection. Run the full suite and validator. Hosted Linux and
Windows results qualify native behavior; renderer-only tests do not replace them.
