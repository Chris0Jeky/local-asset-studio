# Archive finished Library work without deleting it

Archive puts an asset away from the default Library view. **It is independent
of privacy and Trash.** It does not move, encrypt or delete the original; direct
links, lineage, recipes, reviews, titles, notes and collection membership remain.
Private work stays private; archiving regular work does not make it private.

## Library controls

Use the **Archive state** selector beside media type:

| Choice | What it shows |
| --- | --- |
| Active assets (default) | Assets not archived, under the current source, privacy, search and Library scope |
| Archived assets | Archived assets under those same filters |
| Active & archived | Both, still respecting privacy and Trash |

Open an asset and choose **Archive**. The same button becomes **Return to active**.
Unsaved detail wording stays in the open editor and is **not** silently saved or
discarded. Save details remains a separate action. Selection has equivalent bulk
actions; the existing off-page confirmation includes every selected ID. Changing
the Archive filter does not clear the selection. A no-op target keeps its revision.

Trash remains a separate scope: restoring from Trash does not unarchive an asset;
returning an archived asset to active does not restore it from Trash. Collection
counts remain non-Trash membership counts, **including archived assets**; changing
the view does not remove memberships. Same-run inspection explicitly includes
active and archived non-Trash siblings, instead of silently losing outputs.

The Archive preference follows the existing storage owner: Regular preferences
can persist on this device; Private and All preferences use their own tab stores.
Archive is not an additional privacy boundary or a new storage location.

## Interrupted commands and conflicts

The ordinary Workspace command owns Archive too: exact Workspace identity,
explicit IDs, expected metadata revisions and a unique request ID, in one SQLite
transaction. Archive changes only `archived_at` and the changed rows' revisions.
Unarchive sets the timestamp to null. NULL alone means active; timestamp zero is
still archived. Legacy catalogues acquire the nullable column without media moves.

The Library retains the exact request bytes **before** dispatch. After an unknown
response, use **Check receipt**; it reads status and never automatically replays.
A historical receipt confirms that command, not today's state. The separate
current metadata and lifecycle observation include Archive state. A newer revision
requires comparison before another command; newer local wording stays retained.
An explicit retry uses the original ID and bytes, never a fresh mutation identity.

A stale or missing target refuses the whole batch. A failed receipt write rolls
back the metadata update. Already-archived/already-active rows are no-ops, including
at the revision ceiling. Archive does not cancel a pending generation or turn an
uncertain submission into retry authority.

## API, SDK, CLI and MCP reads

Bounded `GET /api/assets/page` accepts `archive=active|archived|all`. Omission means
active. This is independent of `visibility=active|trash|all` (the existing Trash
filter) and `privacy=regular|private|all`. Every non-default Archive choice binds
pagination; a cursor cannot be reused under a different filter. Private changes
do not invalidate a Regular cursor. Page limits, response bounds and explicit
caller-owned continuation are unchanged.

```python
from studio_workflow.asset_read_client import AssetReadClient

client = AssetReadClient("http://127.0.0.1:8191")
page = client.page(filters={"archive": "archived"}, limit=25)
# Inspect page['next_cursor']; a further page is a separate explicit call.
```

```console
python -m studio_workflow.asset_read_client page --archive archived --limit 25
python -m studio_workflow.asset_read_client page --archive all --privacy private
```

MCP `asset_page` accepts the same filter inside `filters`. It remains read-only;
the separate [reviewed agent Archive workflow](workflow-studio/AGENT-ARCHIVE.md)
adds read-only preview/recovery and author-only apply, not broad write access.
`asset_selection` and direct
asset reads remain exact-ID observations and can include archived assets.
Unarchived summaries retain their previous field shape; archived summaries add a
finite `archived_at` timestamp. Full editor metadata/current conflict observations
include `archived_at`, including null, so a conflict cannot conceal a newer Archive
state. Recovery imports accept older records without this additive field.

Writes reuse `POST /api/assets/update`, with action `archive` or `unarchive`,
`ids`, `workspace_id`, `expected_revisions` and `request_id`. Keep the original
privacy scope and bytes for receipt inspection/retry. There is no physical-move
command, automatic reclassification or delete-after-retention policy here.

## Qualification and limits

The tests exercise real SQLite, the composed production asset HTTP boundary,
strict SDK/CLI/MCP reads, shipped Library/recovery JavaScript and a native browser
journey on Linux and Windows. The browser journey uses disposable synthetic images
and startup catalogues; it performs no model generation. Its receipt records served
source hashes, every assertion, requests, page errors and handler errors. The
optional `--inert` mode explicitly substitutes browser origin/storage/transport and
**cannot qualify native reload or browser storage**.

Completed-run Regular/Private migration, plan/apply/status migration journals,
physical relocation and broader agent organization writes remain separate work
under #1678 / #123. No owner artwork, licensing, GPU, configured-workstation or
runtime-restart acceptance is supplied by this feature.
