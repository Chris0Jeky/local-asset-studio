# One reviewed-setup history read contract

Refs #737 and #395. This is the reconciliation child of #724. It retains that
reader and HTTP composition, not an add/add merge of both original modules.
#723's independently useful tests are adapted here; its competing service must
not also be merged. No extra store, compatibility facade or command owner exists.

## Decisions

`SetupHistory(workspace)` is the only constructor. All reads are query-only and
remain in the existing `studio_workflow/setup_history.py`. The public contract is
v2 because the original unmerged v1 page declarations contradicted one another.
No caller can silently interpret one v1 shape as the other.

The page limit is 20. Each operation first binds Workspace, head, bounded
contiguous revision accounting and the validated head payload in one SQLite read
transaction. At most 257 revision scalars are read, including an excess sentinel.
The head is decoded once and reused if requested. Other payloads are decoded only
when requested. A page is not an integrity audit of every historical payload.

The public export is **inspection metadata**, never the full private record:
the validated draft and staged handles are retained verbatim, runtime root and
endpoint are excluded, and source-record identity remains independently named.
Arbitrary user-authored wording, reference declarations and lineage are not
sanitized. Inspect before sharing. A digest is not authentication or portability.
A future importable bundle needs a different contract and explicit command owner.

## Exact result shapes

Every envelope has `format`, `workspace_id`, `draft_id`, `head_revision`,
`head_record_sha256`, and four flags: `observation_only=true`,
`dependencies_checked=false`, `generation_submitted=false`, `staging_performed=false`.

| Format | Additional fields |
| --- | --- |
| `studio.setup-history-page/v2` | `limit`, `revisions`, `next_before_revision` |
| `studio.setup-history-compare/v2` | `left_revision`, `right_revision`, `left_record_sha256`, `right_record_sha256`, `sections` |
| `studio.setup-history-export/v2` | `export`, `export_json`, `export_sha256`, `export_bytes` |

A summary has `revision`, `record_sha256`, `record_bytes`, `draft_sha256`,
`preset_id`, `backend_id`, `graph_sha256`, `input_count`.

Each comparison section has `section`, `changed`, `left`, `right`. Each side has
`sha256`, `bytes`, `preview`, `truncated`, `omitted_bytes`, `redacted`. The preview
is at most 1,024 Unicode code points of canonical JSON. `omitted_bytes` counts
UTF-8 bytes, not characters. Only an untruncated, unredacted preview is complete
JSON. Runtime sides always have `preview=null`, `redacted=true`,
`truncated=false`, and all bytes omitted; the exact hash still detects changes.
The nine sections are recipe_graph, wording, references, controls, lineage,
batch, pending_inputs, authoring and runtime.

The immutable `export` uses `studio.setup-revision-inspection/v2`, with
`workspace_id`, `draft_id`, `revision`, `source_record_sha256`,
`source_record_bytes`, `draft`, `draft_sha256`, `inputs`, `backend_id`,
`graph_sha256`, `authority="none"`, and the four flags. It intentionally contains
no current head. `export_json` is its exact canonical UTF-8 JSON and
`export_sha256`/`export_bytes` describe those bytes, not the source record.
The export document and actual ASCII-escaped response each have a 1 MiB cap;
the latter includes duplicated object/string representations. No partial output
is returned to satisfy either bound.

`expected_head` is required for page continuations and optional for all three
operations. A stale supplied head refuses before loading records. Existing
receipt IDs `history`, `compare`, `export` keep their route priority. See
[the route guide](395-SETUP-HISTORY-READS.md) for errors and commands.

## Preserved test evidence

`tests/test_reviewed_setup_history_reconciled.py` retains all 14 scenarios from
#723's `tests/test_setup_history.py`, on the existing real SetupAdapter fixture:

| Original scenario | Reconciled assertion / deliberate difference |
| --- | --- |
| 100-revision complete walk | Same ordered identities, bounded summaries, unchanged evidence |
| Continuation and concurrent append | Same refusal; canonical code is `setup_history_head_changed` |
| Scope / argument admission | Same pre-record refusal; maximum page now 20, not 25 |
| Wording / controls / lineage partition | Same typed distinctions; complete small previews decoded explicitly |
| Large comparison omission | Exact hashes/bytes retained; bounded preview with explicit truncation and omitted byte count replaces absent whole-value fields |
| Exact metadata export, zero I/O | Canonical inspection draft/inputs and source identity, not an unredacted runtime record; full no-authority flags |
| Append and reopen export stability | Byte-identical historical inspection document and digest |
| Noncanonical / bad hash / accounting / oversized record | Typed corruption refusal, retained bytes unchanged |
| Missing revision | Typed corruption, not a successful partial history |
| Export byte budget | Refusal without deleting or changing evidence |
| Interleaved WAL writer | One observed Workspace/head/history snapshot |
| Orphan future revision | Refusal without head repair |
| Rehashed unsupported schema | Refusal even with valid outer hashes |
| Query-only connections | All three observations work without writes |

All 22 original #724 tests remain unchanged. Nine additional tests cover off-page
head corruption (including empty pages), v2 flags/head identity, runtime privacy,
strict staged input failures after rehash, bounded runtime/head scalars, one-time
head decoding, and real HTTP expected-head/corruption/request-boundary behavior.

The regression checkpoint ran 23 tests against hash-matched #724 modules:
35 assertion failures, zero import errors. After correction the combined suite
runs 45 history tests. Passing counts and final-head hosted results belong in the
PR evidence, not a prediction in this document.

## Integration and remaining scope

Order: #724 then this reconciliation; do not merge #723 independently. Mark #723
superseded only after its meaningful assertions are retained and the combined
checks have passed. Preserve its original branch and review/test history.
Retarget/revalidate the child after #724 integrates into main.

This addresses the competing history read definitions, not all #395 acceptance.
Browser history/accessibility, SDK/CLI/MCP adapters, receipt/proposal association,
explicit fork/import commands, import validation and retention review remain.
No media verification, staging, generation, installation, runtime change,
compaction or HUMAN_TODO creative/licensing/workstation decision is included.
