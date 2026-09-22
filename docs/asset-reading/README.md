# Bounded asset observations

This is the backend read-contract slice of #177. The existing `snapshot()` and
Studio grid remain unchanged and unbounded. The APIs below neither read media nor
modify assets, collections, metadata receipts, selections, or model jobs.

## Core API

Given the existing `AssetWorkspace` instance, call:

```python
page = workspace.asset_page(limit=50, filters={"visibility": "active"})
# Keep the returned Workspace identity and the exact filters/page size.
next_page = workspace.asset_page(
    workspace_id=page["workspace_id"], limit=50,
    filters={"visibility": "active"}, cursor=page["next_cursor"])
selection = workspace.asset_selection(
    ["one-retained-id", "another-retained-id"],
    workspace_id=page["workspace_id"])
```

Only call for another page when `next_cursor` is not null; null starts a new
query. The first page may discover scope. Every continuation binds its returned
scope; selected-ID inspection always requires explicit scope. A different database
identity refuses before returning its assets. These identities are concurrency and
provenance checks, not credentials or database authentication.

Pages use `(created_at DESC, id DESC)`, a bounded keyset seek, and one look-ahead
row. This tie ordering is explicit for the new API; the legacy snapshot ordering
is unchanged. `limit` is a strict integer in 1..100 (default 50). Selection takes a
list of 1..200 unique IDs and returns exactly one item per ID in caller order:
`active`, `trashed`, or `missing`, plus a summary or null. A valid off-page asset is
not missing. Even a zero-valued trash timestamp means trashed. No selected IDs are
silently removed and no retained write command is rewritten.

Supported filters are `visibility` (`active`, `trash`, `all`), `media_type`,
`review` (`unreviewed`, `selected`, `needs_work`, `rejected`), boolean `favorite`,
and exact `collection_id`. Omitted optional filters normalize to null; unknown
keys, invalid types, empty identities, and duplicate selected IDs refuse. A missing
collection is a typed conflict, not an empty successful result. No search, count,
offset, membership expansion, or arbitrary SQL option is exposed.

## Response and consistency contract

Responses carry `format` (`studio.asset-page/v1` or `studio.asset-selection/v1`),
`workspace_id`, `catalogue: {epoch, revision}`, and the explicit flags
`observation_only: true`, `media_bytes_verified: false`,
`generation_submitted: false`. A summary includes the asset ID/hash, byte count,
media type, creation/trash timestamps, preset ID, metadata revision, review,
favorite, display labels, `truncated_fields`, and the existing relative file URL.
It excludes notes, source JSON, tags, lineage, filesystem paths, and collections.
A stored hash is not proof that current media bytes were re-read or verified.
SQL projection bounds and display-label decoding use the connection's SQLite
text encoding (UTF-8, UTF-16LE or UTF-16BE). Stored rows are not transcoded or
rewritten; labels retain embedded NULs and report truncation explicitly.

SQL bounds every selected string/scalar before Python materialization. Titles and
preset names retain at most 200 Unicode characters, filenames 256; truncation is
explicit and never applies to identities. NULs in labels are preserved, not treated
as string terminators. Invalid identities/scalars refuse the whole observation
rather than aliasing another asset or labelling corruption as absence. The maximum
serialized response is 2 MiB using the existing handler's default JSON escaping.

Each read begins a SQLite transaction before observing Workspace identity,
catalogue stamp, or asset rows. No reader is held between calls. A cursor binds
scope, epoch/revision, normalized filters, page size, and the last ordering key.
It is strict, bounded (2,048 characters), canonical JSON wrapped in URL-safe base64
with a checksum. It is **not signed**; a caller can construct a read position, but
cannot acquire write authority or bypass scope/row validation with it.

All asset, collection, and membership inserts/updates/deletes advance one shared
stamp in the same transaction. A rollback rolls back the stamp. A concurrent WAL
writer cannot mix new rows with an old identity/stamp inside a page read. After a
committed mutation, continuing an earlier cursor returns `asset_cursor_stale`
(409). The caller must explicitly refresh, preserving its separate selection and
draft state. There is no automatic restart, retry, rebase, mutation, or promise of
uninterrupted paging during writes. Even an unrelated or no-op row update can
conservatively invalidate a cursor. The stamp is not a user-command count.

Other typed refusals include `asset_cursor_invalid` (400),
`asset_cursor_mismatch` (409), `asset_workspace_conflict` (409),
`asset_collection_unavailable` (409), and `asset_read_unavailable` (503).
Malformed ordinary inputs use `asset_read_invalid` or the existing Workspace
scope error. Refusals carry no selected foreign asset data.

## Migration, failure, and rollback

Initialization adds one versioned stamp table, two ordering indexes, and nine
fixed-name triggers to the existing database under its initialization writer
transaction. Existing asset/collection/receipt schemas and response shapes stay
unchanged. Reads never create or repair schema. Reopen retains epoch and revision;
existing unknown, missing-row, or invalid state refuses rather than silently
resetting. The monotonically increasing revision is limited to `2**53 - 1`.

If the stamp is corrupt, absent, or exhausted, its triggers abort covered writes
and the Workspace connection maps that specific refusal to a typed 503. The
entire caller transaction rolls back, including metadata/receipt changes. This is
intentional: allowing a write without cursor invalidation would make the read
contract false. Diagnose and restore the database from an appropriate backup; do
not delete the stamp as a repair. Filesystem publication is not made atomic with
SQLite, and this migration does not redefine existing file-publication recovery.

Code rollback can leave the additive table/indexes/triggers in place: older SQL
writers continue to advance the stamp. Never drop the table while its triggers
remain. Removing this feature's schema requires exclusive maintenance, dropping
all nine `asset_read_*_v1` triggers before the stamp and indexes, and invalidating
all retained cursors. This is not performed automatically. Restoring a whole old
database backup with the same identity/epoch/revision cannot be distinguished from
that old database by these local identifiers; they are not an anti-rollback seal.

## Verification and remaining work

```text
python -m unittest discover -s tests -p 'test_asset_reads.py' -v
python -m unittest discover -s tests -p 'test_workspace*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The real temporary-SQLite matrix covers 100/1,000/10,000-row walks, tied ordering,
rollback, reopen, concurrent writers, WAL snapshot isolation, corruption, legacy
migration, query-only reads, missing/off-page selection, and response bounds.
It forbids full snapshot and media reads on the tested summary path. The existing
Workspace storage workflow runs the new contracts on Ubuntu and Windows.

Bounded returned rows/bytes are not a claim of constant query time: sparse filters
may scan many index entries, while the ordinary continuation is an indexed seek.
No browser heap, decoder, GPU, wall-time speed-up, thumbnail quality, or owner art
acceptance is inferred from these fixtures. Transport/client integration is the
next stacked slice. Grid migration, paginated collections, detail loading,
thumbnail/proxy work, job history and measured browser budgets remain #177 work.

See [implementation plan](PLAN.md) and [engineering queue](ENGINEERING-QUEUE.md).
