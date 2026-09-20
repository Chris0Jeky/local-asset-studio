# Bounded reviewed-setup history: read-only foundation

Refs #395; parent #232. This is a deliberately partial service slice over #298's
existing `setup_drafts_v1`, `setup_versions_v1` and `setup_operations_v1` ownership.
It does not create a store, migrate schema, alter commands, rewrite receipts or
synchronize browser drafts. The old setup service and its compatibility behavior
remain unchanged. The new inspector is opt-in and stricter about retained bytes.

## API and consistency

```python
from studio_workflow.setup_history import SetupHistory

history = SetupHistory(existing_setup_drafts)
page = history.page(draft_id, workspace_id=workspace_id, limit=20)
if page["next_before_revision"] is not None:
    following = history.page(
        draft_id, workspace_id=workspace_id, limit=20,
        before_revision=page["next_before_revision"],
        expected_head=page["head_revision"])
diff = history.compare(draft_id, 1, 2, workspace_id=workspace_id)
export = history.export_revision(draft_id, 1, workspace_id=workspace_id)
```

Use an existing initialized `SetupDrafts` instance. Constructing the read adapter
performs no I/O. All three calls require an explicit Workspace identity. Every
call starts one SQLite read transaction before observing identity, head, retained
revision numbers or record bytes. WAL writers may advance the database, but cannot
mix a new head with old rows inside one response. No connection remains held
between calls, and the adapter never acquires a runtime/generation lock.

Pages descend by immutable revision number. The default is 20 summaries, maximum
25. A continuation is the exclusive `before_revision` plus its observed
`expected_head`; the latter is mandatory on continuation. A changed head returns
`setup_revision_conflict` rather than silently mixing walks. Optional
`expected_head` also binds first-page, comparison and export observations. There
is no automatic pagination, restart, refresh or selection/draft mutation.

Summaries contain revision, exact record hash/byte count, draft hash, graph hash,
staged-input count and recorded backend ID. They do not expand draft text, input
records or runtime paths. Responses also identify the observed current head and
its record digest. A historical selected revision is not claimed to be current.

## Integrity and allocation bounds

The existing owner permits at most 256 revisions per line. The inspector reads
at most 257 small revision scalars to detect holes, unsupported heads and orphan
future rows. This bounded structural check is not a full audit of every historical
payload: only the current head and requested records are decoded and validated.
An off-page damaged record is detected when requested; its presence is never
silently repaired or purged.

SQLite bounds raw record materialization to 1 MiB and stored digest text to 64
bytes before Python receives them. The inspector verifies exact UTF-8 bytes,
SHA-256, canonical encoding, recorded byte count, supported record fields and the
existing normalized-draft schema. A matching hash alone does not validate a future
schema. Invalid requested evidence returns `setup_history_corrupt` (503), while
an absent setup returns `setup_not_found` (404). Workspace conflicts reuse the
existing Workspace error contract. Unsupported or noncanonical legacy evidence
is retained, not rewritten to make it pass the new inspector.

Other limits are 16 KiB of combined canonical values per displayed diff section,
1 MiB per canonical export document, and 2 MiB per canonical response. These are
UTF-8 canonical-byte limits, not a claim about a future HTTP serializer or browser
heap. The limits are independent of existing command/receipt/storage budgets;
there is no retention policy change, implicit compaction or evidence deletion.

## Typed comparisons

Seven sections cover recipe/graph, wording, other controls, reference slots and
staged-input declarations, parent/continuation lineage, batch/pending inputs, and
recorded runtime. Each carries before/after canonical hashes, byte counts and an
exact `changed` fact. Within the display budget it also carries complete typed
values. Above that budget it reports `omitted: true` and excludes both values;
truncated content is never presented as a complete comparison.

## Exact metadata export

The response's `export_json` is the canonical UTF-8 `studio.setup-revision/v1`
document. `export_sha256` and `export_bytes` describe exactly those bytes. The
document records original Workspace/draft/revision identity, the validated record
and its digest/accounting. Current-head observation is outside that document,
so exporting the same revision after later appends or reopen produces identical
export bytes. No graph or staged-media files are opened or copied.

Metadata is not automatically public or portable: wording, reference names,
lineage, local runtime paths and endpoints may be present. Review before sharing.
No current graph/source/backend compatibility is checked. Both response and export
explicitly state `observation_only: true`, `dependencies_checked: false`,
`generation_submitted: false` and `staging_performed: false`. An export is neither
an import command nor execution approval. Importing it is not implemented here.

## Verification and remaining work

```text
python -m unittest discover -s tests -p 'test_setup_history.py' -v
python -m unittest discover -s tests -p 'test_recipe_shortlist_apply.py' -v
python -m unittest discover -s tests -p 'test_revision_consistency*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The focused tests use real shared setup commands and temporary SQLite, including
100 revisions, held WAL reads, reopen, corruption and byte-accounting refusal,
query-only connections, typed diff omission and export stability. They compare
all setup tables before/after observations and forbid runtime/media helper calls.
The existing Recipe shortlist contracts workflow runs history and consistency
checks on Ubuntu and Windows, without introducing another workflow or runtime.
Actual final-head outcomes belong in the PR validation record.

Remaining #395 work is substantial: revision-to-command/proposal receipt lineage,
bounded multi-revision bundles and import inspection, fork/import commands with
expected-head checks and durable recovery, HTTP/SDK/CLI/MCP parity, browser
history/local-draft UX and accessibility. Existing append-only restore stays on
its current command path. Any future compaction needs explicit reachability proof;
no compaction is attempted here. Dependency checks and explicit import commands
must not treat an unverified export as a successful load or staging operation.
Owner creative acceptance and unsupported mask/I2V bindings remain separate.
