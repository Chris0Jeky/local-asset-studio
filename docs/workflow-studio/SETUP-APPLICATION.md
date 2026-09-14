# Apply a reviewed setup and recover the original request

This extends [setup proposals](SETUP-PROPOSALS.md) and the ordered source chooser.
The preview still performs no mutation. **Apply reviewed setup** is a separate,
explicit command: it checkpoints Create, copies the reviewed images through the
existing Studio uploader, saves a new shared revision, and loads it into Create
only while the reviewed editor context is unchanged. Generate remains separate.

Issue ownership: #232 owns this handoff, #118 the guided experience, #123 the
headless interface and #21 reference compilation. Graph-node documents remain
with #120; no graph store, GPU executor, polling loop or alternative uploader is
introduced. Parent PR #275 supplied the preview; do not rebuild it.

## Use it in the Studio

1. Select one to three Workspace images, find recipes, set their ordered roles,
   and check. Open **Preview proposed setup**, edit the desired wording and
   contributions, then **Build proposal**. Inspect the complete comparison.
2. Press **Apply reviewed setup** and confirm the checkpoint, file copies and
   replacement. Cancel sends no shared-draft command. Preview alone is unchanged.
3. A successful operation opens **Shared setup & recovery** in Create. It shows
   the saved revision; ordinary readiness and the explicit Generate button remain.
4. **Undo applied setup** restores the checkpoint as a new revision. It refuses
   to overwrite subsequent local edits. It does not delete files or old revisions.
5. After an interrupted response, use **Inspect original request**. This is one
   GET with the retained request ID. It does not repeat copying or load anything.
   A confirmed revision can then be loaded with **Load checked Workspace revision**.

The browser retains its exact command before sending it. Reload restores the
recovery session, not an automatic write or automatic editor replacement. Session
exports include prompts, source metadata and the latest local pre-load backup;
keep them private. The ordinary browser draft/export features remain available.

The current Create draft must have no pending unuploaded File inputs or in-flight
attachment/submission. Attach or remove those inputs first. A browser File object
is not durable source storage, and this feature does not claim to preserve its
bytes across reload. Settled existing attachments are checked in both the upload
folder and active backend input folder before a checkpoint can be committed.

## Commands shared with agents

The service uses `/api/workflow-studio/setup-drafts`. All writes are explicit
POSTs with an exact Workspace identity and caller-chosen request ID. Existing
same-origin/loopback checks apply. Reads never dispatch a write.

| Operation | Required fields beyond `action`, `workspace_id`, `request_id` |
| --- | --- |
| `create` | `draft` (the complete normalized Create declaration) |
| `replace` | `draft_id`, `expected_revision`, `draft` |
| `apply` | `draft_id`, `expected_revision`, `proposal_json`, `approved_proposal_sha256` |
| `restore` | `draft_id`, `expected_revision`, `revision` (the historical target) |
| `abandon` | `draft_id`, `expected_revision`, `operation_id` (a pending request) |

`GET /api/workflow-studio/setup-drafts` lists shared IDs and current revisions.
`GET /api/workflow-studio/setup-drafts/{id}` reads the head; append
`/revisions/{n}` to read history. Append `/check/{n}` to verify a recorded revision's
current inputs, graph and backend before loading. Read
`/api/workflow-studio/setup-drafts/requests/{request_id}` to inspect an original
operation. These reads do not inspect another browser's private unsaved draft.

Python SDK, after reviewing an exported proposal:

```python
import json
from pathlib import Path
from uuid import uuid4
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient("http://127.0.0.1:8191", timeout=30)
store = client.setup_drafts
proposal = json.loads(Path("reviewed-proposal.json").read_text(encoding="utf-8"))
scope = store.list()["workspace_id"]

# These are WRITE operations, not inspection. Persist each exact command before
# calling it. Use new local filenames rather than replacing earlier receipts.
checkpoint_command = {
    "action": "create", "workspace_id": scope, "request_id": uuid4().hex,
    "draft": proposal["before"],
}
with Path("checkpoint-command.json").open("x", encoding="utf-8") as stream:
    json.dump(checkpoint_command, stream, ensure_ascii=False)
checkpoint = store.command(checkpoint_command)
assert checkpoint["status"] == "committed"

# Run only after deliberately approving the exported comparison and source copies.
apply_command = {
    "action": "apply", "workspace_id": scope, "request_id": uuid4().hex,
    "draft_id": checkpoint["draft_id"], "expected_revision": checkpoint["revision"],
    "proposal_json": proposal["proposal_json"],
    "approved_proposal_sha256": proposal["proposal_sha256"],
}
with Path("apply-command.json").open("x", encoding="utf-8") as stream:
    json.dump(apply_command, stream, ensure_ascii=False)
result = store.command(apply_command)
print(result["status"], result["request_id"])
```

A non-committed status is not success. After any transport/server failure, retain
the command and call `store.recover(apply_command["request_id"])`. Do not mint a
new identity to "retry" the application. `get`, `check`, `create`, `replace`,
`apply`, `restore` and generic `command` are also exposed on this same SDK object.
An agent can edit an existing shared ID using `replace` with its expected revision;
it cannot silently change a browser-local editor that has not loaded that revision.

CLI examples (the Studio must already be running):

```console
python -m studio_workflow.setup_draft_client list
python -m studio_workflow.setup_draft_client command checkpoint-command.json
python -m studio_workflow.setup_draft_client command apply-command.json
python -m studio_workflow.setup_draft_client recover ORIGINAL_REQUEST_ID
python -m studio_workflow.setup_draft_client get SHARED_DRAFT_ID --revision 1
```

The optional `--url` precedes the subcommand. A command file is strict bounded JSON
(maximum 1 MiB), not executable code. Exit 0 means the requested read or committed
operation returned; exit 3 means a failed/pending/abandoned operation or unknown
write outcome; exit 2 means an input/known HTTP/read error. No error exit is an
authorization to repeat a write. Server errors after a possible write are reported
as `setup_outcome_unknown` with the original request ID. These exits do not describe
model execution: no model work is submitted here.

MCP read mode adds `setup_draft_list`, `setup_draft_get` and
`setup_draft_recover`. Author mode additionally exposes `setup_draft_command`,
with a `command_json` string containing the same exact command. It is marked as
mutating: applying it copies files even though it does not generate. Existing
`recipe_setup_proposal` remains read-only. Capability discovery now reports
`shared_setup_drafts`, `setup_request_recovery` and `recipe_setup_apply`.
The preview report's own `can_apply:false` is retained: that document is not a
mutation credential; the explicit command has its own revision and approval fields.

## Persistence and failure contract

`SetupDrafts` stores three namespaced tables and one index inside the existing
AssetWorkspace SQLite database. Revisions and original request receipts have
canonical content hashes. Each request ID is scoped to the Workspace and bound to
the complete command. A repeat with identical content returns the old result;
different content under the same ID refuses. It never initiates another copy.

A `BEGIN IMMEDIATE` transaction checks the expected head and active-operation
ownership. The shared revision—not a browser timestamp—controls writes from UI
and agents. The existing Studio lock coordinates this process's selected backend
and uploader. Before application, a durable receipt records `checking`; before
each file operation it records `staging`, the Picture number and the possibility
that a copy occurred. Known filenames are retained before further verification.

All staged bytes and geometry must match the approved sources in both local
locations. The proposal is rebuilt before and after staging; changes to source,
graph, catalog, backend or prerequisite observations refuse the application. A
new revision and the committed receipt are published together only after all
checks pass. Invalid proposals and partial failures never advance the draft head.

Every checkpoint retains a server-observed graph hash, even if Create had no
browser template hash. Undo/load verifies that graph, backend and original staged
bytes; it does not pretend an old filename is still the same source.

| Observed outcome | Meaning and next action |
| --- | --- |
| `committed` | The named revision exists. Inspect/load explicitly after recovery. |
| `failed` | No new revision committed; retained copies and attempt details may exist. Review before a new operation. |
| `checking` / `staging` | The outcome remains pending. It may be running or interrupted. Read, do not replay. |
| `abandoned` | Explicitly released pending ownership without committing a draft or deleting copies. |
| No receipt / unreadable storage | No reliable conclusion about the original request. Retain/export it and inspect storage. |

**Release pending operation** is a distinct acknowledged command. It is not
cancellation of a filesystem copy already in progress and cannot prove an absent
side effect. SQL ownership is checked again before publishing a revision. A
crash after creating a file but before recording its returned name can leave
unidentified copies: the pre-copy receipt records that uncertainty. No automatic
cleanup, compensating deletion, background retry or exactly-once claim is made.

The browser uses an origin-scoped exclusive Web Lock and storage readback before
writes. It does not steal locks or wait behind another tab indefinitely. A
30-second fetch deadline stops waiting; it does not cancel an accepted command.
The pending identity stays available for recovery. Browsers without required
storage, Web Locks or WebCrypto refuse browser application; use the explicit
headless contract instead. The read-only proposal remains usable independently.

When a response arrives, revision and receipt integrity are checked. Before
loading Create, the workbench owner rechecks its current change stamp, submission
and attachment state, catalog representation and backend. A late result cannot
overwrite new local edits. Rendering errors leave the saved revision and browser
backup intact and hold Generate until the operator resolves the editor state.

## Bounds, tradeoffs and residual work

There are at most 128 shared drafts, 256 revisions per draft, 1,024 requests per
draft and 128 MiB of accounted revision/receipt JSON. Admission checks headroom
before copying, but this is not a filesystem space reservation or a universal
power-loss guarantee. Histories and media are never pruned to create room.
The existing uploader retains its own byte/pixel/type limits. All production
source paths remain inside the configured local stores; no arbitrary URL fetch,
custom-node execution or new database location is accepted.

The initial adapter supports the statically represented routes already accepted by
setup proposals. Masks, dynamic/mode-dependent I2V, native visual/subgraph imports
and arbitrary graphs remain unsupported. Source role names are semantic guidance,
not geometric control or identity/art/licensing acceptance. Stored hashes are
integrity evidence, not authentication or filesystem leases against later mutation.

The browser currently follows one shared draft per retained session. Agent-created
or historical IDs can be inspected headlessly; an in-product shared-draft browser,
explicit new-session/fork/import controls and bounded retention management remain
future UX. New unuploaded File preservation and truly live multi-editor sync also
remain outside this slice. The existing #232 tracks these limits and owner-machine
acceptance; #118 still requires a separately reviewed real creative result.

Rejected alternatives: directly call legacy `applySaved` from the modal (its
asynchronous restoration has no revision/CAS/recovery contract); stage before
journaling (a lost response could invite duplicate copies); reuse workflow-node
documents for Create recipes (different schema and semantics); automatically
retry or delete partial files (would lose uncertainty and possibly user media).

## Verification and local handoff

```console
python -m unittest discover -s tests -p 'test_recipe_shortlist*.py' -v
node --test tests/setup_apply_client.cjs
python tests/setup_apply_browser.py --out .runtime/setup-apply-proof
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The browser driver uses actual Studio UI, Workspace SQLite and uploader copies
with synthetic model dependencies. It checks explicit confirmation, all reference
roles/bytes, full Undo, post-commit response failure, original-request recovery and
checked load. Native mode additionally exercises Web Locks and reload storage.
`--inert` is explicitly labelled component transport/storage/crypto/lock injection
for policy-restricted containers; it is not evidence of a native browser origin.
Existing read-only shortlist/proposal tests are retained separately in CI.

New causal regressions include no browser-template graph pin, malformed command
shapes, server-error uncertainty, origin-lock admission, response revision mismatch
and deferred workbench mounting. Initial scaffolding and fixture-only missing
button-label/test UUID problems are distinguished from product failures in the
handoff logs. Exact run counts and hosted receipts belong to the final PR record,
not an assumed future passing run. Optional SDK skips are not executed evidence.

Primary contract references: [SQLite transactions](https://www.sqlite.org/lang_transaction.html)
for explicit write transactions and failed commits, and [Web Locks](https://www.w3.org/TR/web-locks/)
for lock lifetime and `ifAvailable`. File authority and reference semantics remain
the repository's existing `app/workspace.py`, `app/server.py` and
`app/references.py` contracts. Reverting the application UI/service does not remove
the namespaced tables or uploaded files; preserve/export them before any later
schema/retention migration. No owner runtime or HUMAN_TODO decision is changed.
