# Bounded asset observations through MCP

Refs #177. This adapter follows #719's Workspace reads and #721's HTTP/client
contract. It extends the existing workflow MCP server; it does not add a server,
store, receipt, media reader, background task or second pagination implementation.

## Tools

Both tools are available in `read`, `author` and `execute` modes. They have
read-only and idempotent annotations; neither is destructive or open-world.
The underlying selection POST is an observation, not a metadata command.

- `asset_page`: one page, default 50 and maximum 100 summaries. Optional
  `workspace_id`, `limit`, `cursor` and `filters`. Filters support `visibility`
  (`active`, `trash`, `all`), `media_type`, `review`, `favorite`, `collection_id`.
- `asset_selection`: one observation of 1–200 **unique** `ids`, in their supplied
  order, with a required `workspace_id`. Active, trashed and genuinely missing
  assets are distinct; an unloaded page is not evidence that an asset is missing.

The tool schemas reject unknown arguments and malformed IDs before HTTP.
Integer limits do not accept booleans. The filters object cannot be null; its
optional media type, review, favorite and collection fields can be null, matching
the existing SDK. IDs retain the asset contract's 128-character alphabet rather
than the separate workflow-document identifier contract. No IDs are pruned.

Start the normal Studio separately. In the existing isolated tools environment:

```text
python scripts/workflow-mcp.py --describe
python scripts/workflow-mcp.py --mode read --url http://127.0.0.1:8191
```

`--describe` performs no HTTP request and does not load the optional MCP SDK.
For an MCP client, call `asset_page` with this arguments object:

```json
{"limit":20,"filters":{"review":"selected"}}
```

Decode the returned `data_json`, and retain its exact `workspace_id`, filters,
limit and non-null `next_cursor`. A deliberate next call supplies those same
values and the returned cursor. Do not send a null cursor to mean continuation:
null is invalid tool input; omitting the cursor starts a new first page. When
`next_cursor` is null the current walk is complete. No tool walks automatically.

Call `asset_selection` with the original Workspace and retained IDs to inspect
an off-page selection. It does not load that selection into the browser, restore
an editable draft, rebase a command or authorize an action on the selected assets.

## Transport, errors and evidence

The adapter binds the bridge's existing raw `Client` origin, timeout and opener to
`AssetReadClient`. It deliberately does **not** forward through generic
`Client.request()`, whose response decoding/budget is not the asset contract.
Normal literal-loopback, no-proxy and no-redirect defaults remain in force.
Embedders injecting a client must supply a `Client` instance (or subclass), not
just a duck-typed callback returning already-decoded dictionaries.

Success bodies retain the strict 2 MiB HTTP observation limit; errors retain the
separate 64 KiB limit. A valid 200-item Unicode selection may exceed the authoring
API's 1 MiB budget and is not truncated or mistaken for authoring input. These are
body/data bounds, not total MCP wire or host-memory budgets: the existing MCP
protocol wraps the JSON text in structured and text content. The exact
`data_json`/`data_sha256` envelope remains unchanged. Titles and labels are data,
not agent instructions. Hashes detect changed evidence, not authenticate a server.

The shared SDK verifies raw UTF-8, duplicate keys, framing, fields, scalar types,
Workspace/catalogue identities, ordering, selection accounting and continuation
boundaries. Both successful and failed response streams close. Stored media hashes
and file URLs stay unverified observations; the adapter never follows them.

Local input/cursor mismatch is `invalid_arguments` and sends no request. A
transport or successful-response validation failure is `request_failed` after
one attempted read. A valid HTTP refusal preserves its status and public code,
including `asset_cursor_stale` and `asset_workspace_conflict` (409). An over-budget
or unreadable error body remains a failed read without a claimed server verdict.
Even a lost selection POST cannot become `outcome_unknown` or acquire mutation
recovery instructions. There is no automatic retry, refresh or replacement scope.

On stale continuation, preserve independent local selections/drafts and explicitly
refresh; never concatenate different catalogue revisions. On Workspace conflict,
retain the original scope and evidence rather than interpreting its IDs elsewhere.
The bridge's existing four-call semaphore also bounds these reads. A fifth call
returns `gateway_busy` without I/O. This is shared in-process concurrency, not
physical RAM reservation or an end-to-end wall-clock deadline.

## Verification and remaining acceptance

```text
python -m unittest discover -s tests -p test_workflow_asset_reads.py -v
python -m unittest discover -s tests -p test_workflow_asset_mcp.py -v
python -m unittest discover -s tests -p test_workflow_agent_bridge.py -v
python -m unittest discover -s tests -p 'test_asset_read*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The first suite covers the actual bridge, strict raw replies and the full composed
production handler with temporary SQLite. The optional official-SDK suite checks
annotations, invalid-input admission and actual subprocess stdio → production
asset routes → SQLite, including stale/foreign scope. Its fixture adapts only the
Host/Origin spelling to an ephemeral loopback port. Generation routes are never
called, original bytes remain unchanged, and asset command counts remain zero.

The existing MCP workflow requires its pinned SDK on Ubuntu and Windows and now
runs both suites from the exact PR head. Ordinary offline discovery can skip the
optional protocol suite; a skip is not protocol evidence. Read the PR's exact-head
record for observed outcomes, not this runbook as a promise of passing CI.

#177 remains open for the actual grid/snapshot migration, paginated collections,
detail/media loading, immutable thumbnails/proxies, browser selection/focus/draft
continuity, and measured 100/1,000/10,000-record DOM/heap/decode budgets. No artistic,
licensing, owner workstation, model runtime or HUMAN_TODO decision is made here.
Review order: #719, #721, then this adapter; retarget and validate the integrated
base after the parents land. The #395 history drafts are separate work.
