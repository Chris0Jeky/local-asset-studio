# Shared workflow documents: humans, CLI and agents

Implementation slice of #120 and #123, following #126. This is persistent **authoring**,
not permission to run an arbitrary graph. MCP, external module libraries, realtime
collaboration and native Comfy visual/subgraph parity remain separate work.

## Where the state lives

Workflow heads, immutable revisions and request receipts are namespaced tables in
**the existing `AssetWorkspace` `assets.sqlite3`**, using its connection/transaction
helper. There is no second workspace database, port, scheduler, or model worker.
Initialization creates the three tables lazily on first document access; ordinary
reads then change no document state. No document operation calls ComfyUI, discovers
nodes, stages reference files, installs software or authorizes generation.

Limits: 1 MiB JSON request/document, 256 nodes, 256 commands per batch, 256 saved
workflows, 1,024 revisions per workflow, 128 MiB total encoded revision history.
Reaching a limit refuses the write; no history is silently pruned. Archive/retention
management is not supplied by this slice. List returns bounded head metadata without
loading every graph. Byte budgets use stored UTF-8 sizes rather than rescanning graph
contents at every save. These are application bounds, not a SQLite disk quota.

## Transactions and identity

```text
UI draft / SDK / CLI
        | request_id + expected_revision + commands
        v
same-origin document handler
        v
AssetWorkspace connection -> BEGIN IMMEDIATE
  retained request? -> exact saved revision (+ current head revision)
  stale expected_revision? -> HTTP 409; no edit
  valid command batch? -> append revision + receipt + advance head
        v
COMMIT -> structured result
```

All three writes commit or roll back together. No network I/O occurs inside this
transaction. Independent processes/connections sharing this database use the same
SQLite write lock; a Python-only mutex is not the concurrency guarantee.

A `request_id` is a caller-chosen stable key (1–96 letters/digits/underscore/dot/hyphen).
It is unique across this document service. Retain it **with its exact payload** before
sending a write. A repeated identical request returns the original committed revision;
a changed payload with the same key is a conflict. A lost response is not permission
to invent another key. The receipt may describe revision 2 while `head_revision` is 4:
that is recovery evidence, **not the latest document**, and must not overwrite newer work.

Server revisions start at 1. Incoming browser revision counters are not authority.
`expected_revision` is mandatory for mutation and restore. Restore appends a new
revision containing an older snapshot; it never rewinds the head or deletes later
history. Fork pins an exact source revision/hash in server-recorded `origin`, while
preserving the document's existing source metadata. These hashes establish byte
identity, not author authentication, visual quality, permissions or model compatibility.

`document_sha256` includes document/revision metadata. `execution_inputs_sha256`
excludes positions, display labels, step presentation and source annotations, but
conservatively includes disconnected nodes. It is **not** a prepared plan hash. Use
the existing compiler's `graph_sha256` for a valid selected-output closure, and the
registered-recipe ticket boundary for currently supported execution.

## HTTP contract

All paths below are relative to `/api/workflow-studio/documents`.

| Method and path | Payload / response |
| --- | --- |
| `GET` prefix | Saved workflow head metadata and limits |
| `POST` prefix | `{request_id, document}` → new workflow, revision 1 |
| `GET /{id}` | Latest document and its server revision |
| `GET /{id}/revisions/{n}` | Immutable historical revision, plus current head |
| `GET /{id}/history` | Revision hashes, timestamps, request IDs, change summaries |
| `POST /{id}/commands` | `{request_id, expected_revision, commands}` |
| `POST /{id}/preview` | `{expected_revision, commands}` → proposed document/diff; no commit |
| `POST /{id}/restore` | `{request_id, expected_revision, revision}` |
| `POST /{id}/fork` | `{request_id, revision, name}` |

Read/create use exactly the prefix, not `/documents/documents`. Query parameters,
unknown fields and unknown commands are rejected. Errors include `code`; stale edits
are `revision_conflict` (409), reused request keys `request_conflict` (409), absent
revisions `not_found` (404), malformed operations 400, storage errors 503. A storage or
transport error can make commit observation ambiguous: inspect or repeat **the exact
retained request**. None of these operations can submit generation.

### Commands

The pure `apply_commands(document, commands)` reducer is the same function used by
server commits and previews. Every intermediate document must remain structurally
valid. Draft execution errors (cycles, missing classes, dangling connections) remain
editable and are separately reported by the existing compiler.

```json
[
  {"op":"set_input", "id":"1", "input":"seed", "value":12345},
  {"op":"set_position", "id":"1", "position":[80,120]},
  {"op":"rename", "name":"Character lighting study"}
]
```

Use actual node IDs/input names from your document; this example does not invent a
registered preset. The command set is `rename`, `add_node`, `remove_node`, `set_input`,
`unset_input`, `connect`, `disconnect`, `set_enabled`, `set_position`, `set_bypass`,
`select_outputs`, `accept_schema`, and explicit whole-document `replace`.

A connection is `{op:"connect", id:<target>, input:<name>, source:<source>, output:0}`.
`set_input` cannot masquerade as a typed link. Disconnect removes the input and any
passthrough that referred to it. Remove-node preserves consumers' dangling links,
so it cannot silently rewire a branch. Disable never guesses a bypass. Schema
acceptance is an explicit draft change, not certification. Whole-document replace
is revision-checked just like a small edit, and is used for browser draft saves.

## CLI

Run the ordinary Studio server. Save/export a `studio.workflow/v1` document from the
builder; it need not be runnable to be saved. No browser is required after that.

```bash
python -m studio_workflow documents create --document draft.json --request-id character-initial
python -m studio_workflow documents list
python -m studio_workflow documents get DOCUMENT_ID
python -m studio_workflow documents preview DOCUMENT_ID --commands changes.json --expected-revision 1
python -m studio_workflow documents apply DOCUMENT_ID --commands changes.json --expected-revision 1 --request-id character-edit-1
python -m studio_workflow documents history DOCUMENT_ID
python -m studio_workflow documents restore DOCUMENT_ID --revision 1 --expected-revision 2 --request-id character-restore-1
python -m studio_workflow documents fork DOCUMENT_ID --revision 2 --name "Lighting variant" --request-id character-fork-1
```

Replace `DOCUMENT_ID` with the returned ID. `get` and write results contain a
`document` property, not bare document JSON; extract that property before supplying
a file to `--document`. `--out` writes the full response and refuses overwrite.
Conflict exit status is **6**; existing execution/observation exit codes are unchanged.
The shared transport remains literal-loopback HTTP, proxy-disabled, redirect-refusing,
response-bounded and non-retrying. Python preserves integer seeds beyond JavaScript's
safe range; browser editing of those documents remains explicitly refused.

## Python SDK

```python
from studio_workflow.sdk import WorkflowClient, ClientError

studio = WorkflowClient("http://127.0.0.1:8191")
current = studio.get_document("DOCUMENT_ID")
commands = [{"op": "rename", "name": "Character study — warm light"}]
proposal = studio.preview(current["id"], commands, expected_revision=current["revision"])
# Review proposal['changes'] and proposal['document'] before committing.
result = studio.apply(current["id"], commands,
                      expected_revision=current["revision"], request_id="warm-light-rename-1")
```

Do not catch `revision_conflict` and automatically retry against the new head. Present
the conflict, inspect the intervening revisions and propose a new deliberate edit.
The SDK is an HTTP client only; it cannot mutate a second on-disk representation.
MCP parity remains #123; this module does not claim to be an MCP server.

## Verification and follow-up

`python -m unittest discover -s tests -p test_workflow_documents.py` exercises real
SQLite commit/rollback, two independent concurrent connections, duplicate request
recovery, request-content conflicts, append-only restore, exact forks, corruption
boundaries, numeric preservation and real loopback HTTP/SDK/CLI routes. The injected
SQL trigger failure proves transaction rollback, not a physical disk-power-loss test.
The response-loss case discards a successful response then repeats the retained
request; it is not an uncontrolled live network outage.

Local isolated run: 28 document tests, 27 passed and one real-AssetWorkspace integration
test skipped because this environment has only the fetched feature sources. Hosted
full-checkout CI must run that integration test and the complete repository suite.
The six workspace-ticket regressions also pass (four fail on the pre-fix source).
No installed ComfyUI, inference, model changes or artistic acceptance was tested.

Next: saved-workflow UI with explicit stale-conflict recovery; named Step modules;
shared schema fixtures; MCP; finer-grained collaborative editing; bounded retention
management. #120/#123 remain open. Human creative choices in HUMAN_TODO.md are unchanged.

## Primary-source design references

Reviewed 12 September 2026:
- SQLite transactions: https://www.sqlite.org/lang_transaction.html — `BEGIN IMMEDIATE`
  reserves the write transaction before reading the head; do not hold it over network I/O.
- Python sqlite3 context manager: https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager
  — commit/rollback belongs to the existing connection helper, which also closes the connection.
- Repository seam inspected: `app/workspace.py` `AssetWorkspace.connection()` and
  `studio_workflow/http_extension.py`, rather than a parallel database or HTTP server.
