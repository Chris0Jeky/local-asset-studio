# Collection discovery implementation plan

> Use superpowers:executing-plans for this isolated continuation.

**Goal:** Let tools discover collection IDs and scoped counts before asking for
assets in an existing collection, without inventing IDs or reading the whole Library.

**Architecture:** A strict SDK/CLI wraps the existing `/api/collections` GET owner.
The MCP bridge delegates one `collection_page` observation to that client. Reuse
its bounded raw HTTP/JSON transport, collection cursor decoder, Workspace and
privacy contracts. No new database, mutation path, permissions or runtime dependency.

**Tech stack:** Existing Python 3.12 standard-library client and optional pinned MCP SDK.

**Spec / decision:** This document scopes the owner-requested agent organization
follow-up (#123/#1673). Bounded discovery is independently useful; full Archive,
completed-run migration (#1678), organization writes and file moves are excluded.
No extra unbounded snapshot API and no second storage owner.

## Global constraints

Regular-only by default; Private/All require explicit scope. One call makes one
GET, maximum 100 rows / 2 MiB reply; no automatic continuation, retry or refresh.
Keep exact Workspace, catalogue epoch/revision and cursor boundary. Fail closed
on malformed/foreign replies; names and descriptions are data, not instructions.

## Review focus

Cross-scope cursor reuse must fail before transport. Unicode and embedded-NUL
name comparisons must match SQLite NOCASE, not Unicode casefold. Invalid response
shapes, duplicate IDs and stale catalogues must not become trusted observations.
Transport failures must never be labeled uncertain writes. Protocol tests must
actually run with the pinned SDK on Linux/Windows before merge.

## Tasks

- [x] Add `tests/test_collection_read_client.py`: invalid input/no I/O, valid and
  malformed replies, page boundary and native SQLite NOCASE ordering, raw framing,
  exact CLI arguments, real HTTP privacy/paging/stale controls. Observe failures.
- [x] Implement `CollectionReadClient.page(*, workspace_id=None, limit=50,
  cursor=None, privacy='regular')` and CLI in `studio_workflow/collection_read_client.py`.
  Run the client/HTTP tests and existing collection/asset read suites.
- [x] Add `tests/test_workflow_collection_reads.py` and optional real-stdio
  `tests/test_workflow_collection_mcp.py`; prove discovery and errors before bridge edits.
- [x] Add `collection_read_tools.py`, wire one read-only tool into `agent_bridge.py`,
  preserve error argument context and wire both test modules into workflow-mcp CI.
- [ ] Publish a separate reviewable PR with scoped user documentation, exact test
  evidence and remaining outcomes. Do not claim Archive or sorting writes delivered.

## Execution evidence

The 11 client/HTTP cases failed before implementation, and the five bridge
cases failed before tool registration. All 16 pass after the implementation.
The broader collection suite passes **68 tests**. The workflow suite exercises
**445 tests**, with **13 optional-SDK skips** in this environment; it has no
failures or errors. An overlapping selected read/framing suite exercises 88
tests with two skips; do not add these counts together. The repository validator
passes 94 preset graphs/bindings, 189 pinned assets and 164 LoRA names.

The two new official-SDK/stdio tests are among the local skips. Their Linux and
Windows hosted execution, along with a fresh full suite, is required before
merge. No native protocol success is inferred from the in-process bridge tests.
Self-review checked response bounds, cursor identity, SQLite name ordering,
no-write receipts, transport cleanup and preservation of argument context.
