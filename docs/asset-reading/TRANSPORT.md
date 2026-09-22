# Read-only asset transport

Refs #177. This child slice of #719 exposes its existing Workspace reads through
Studio's composed HTTP handler. It does not replace the legacy snapshot or grid.
No additional server, receipt store, mutation command, or automatic pager exists.

## Routes and bounds

`GET /api/assets/page` accepts the core filter names plus `workspace_id`, `limit`
and `cursor`. Booleans are exactly `true` or `false`. Fields must occur once and
be nonempty; unknown fields, malformed percent escapes and invalid UTF-8 refuse.
The entire request target is at most 4,096 characters. Limits remain 100 rows per
page, 2,048 cursor characters and a 2 MiB JSON response.

`POST /api/assets/selection` is an observation, not a write. Its UTF-8 JSON body
contains exactly `workspace_id` and `ids` (1..200 unique IDs). A JSON content type
and one fixed Content-Length are required; transfer coding and duplicate lengths
refuse. The body is limited to 32 KiB and a five-second absolute read deadline.
A shorter existing socket timeout is never extended; even a final complete chunk
arriving after the deadline is refused. The original socket timeout is restored.

Both routes retain Studio's existing loopback Host check. Selection additionally
uses the existing same-origin request check. GET selection and POST page return
405. Early POST refusals use the existing bounded drain-and-close helper. No CORS,
remote origin, proxy discovery, redirect following, or media loading is added.

## Python and CLI

```python
from studio_workflow.asset_read_client import AssetReadClient

client = AssetReadClient()
page = client.page(limit=20, filters={"review": "selected"})
# Only continue after a deliberate caller decision, and only for a non-null cursor.
if page["next_cursor"] is not None:
    following = client.page(workspace_id=page["workspace_id"], limit=20,
                            filters={"review": "selected"}, cursor=page["next_cursor"])
selected = client.selection(["retained-asset-id"], workspace_id=page["workspace_id"])
```

```text
python -m studio_workflow.asset_read_client page --limit 20 --review selected
python -m studio_workflow.asset_read_client selection --workspace-id WORKSPACE_ID ASSET_ID
python -m studio_workflow.asset_read_client --help
```

Replace the illustrative IDs with actual returned identities. The CLI writes one
JSON result to stdout, or a structured error to stderr with exit status 2. A null
cursor means the end of this walk; supplying null starts a fresh first page.

The client rejects duplicate JSON keys, bad framing, non-finite values, extra
schema fields, wrong Workspace/catalogue identities, reordered/duplicate assets,
foreign media URLs, invalid scalars, and incomplete or reordered selected-ID
results. It checks each continuation boundary against the exact query, page size,
last ordering key and catalogue stamp. Display truncation is explicit. Stored
asset hashes and file URLs are observations, not current media-byte verification.

The 2 MiB observation response limit is deliberately independent of the 1 MiB
workflow-authoring decoder: a valid 200-item Unicode selection can exceed 1 MiB.
Error responses are read under a separate 64 KiB bound; successful and failed
response streams are closed. HTTP conflicts preserve their status and public code.
Neither SDK nor CLI retries, refreshes, fetches another page, stages files, writes
metadata, switches a backend, or submits generation automatically.

## Conflict handling

On `asset_cursor_stale` (409), retain the user's separate selections and drafts.
Explicitly refresh the query; do not concatenate old and new catalogue pages. On
Workspace conflict, do not reinterpret old selected IDs in the new Workspace.
Malformed inputs return 400, body timeouts 408, and unavailable/corrupt storage
503. Storage failures use a generic message, not SQL text or private paths.

## Validation and remaining acceptance

```text
python -m unittest discover -s tests -p 'test_asset_read*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The focused tests use real temporary SQLite and the full production handler
composition over loopback, plus hostile response fixtures. The existing Workspace
storage workflow runs these contracts on Ubuntu and Windows. Deadline regressions
were observed failing before the fix. See the PR's final-head validation record
for actual run outcomes; this document does not assert unfinished CI success.

This is not browser/SDK/MCP parity for all of #177. Grid migration, paginated
collections, detail/media loading, thumbnails and measured browser budgets remain
separate acceptance. Original media, generation and owner creative decisions are
unchanged. See [core contract](README.md) and [ownership map](ENGINEERING-QUEUE.md).
