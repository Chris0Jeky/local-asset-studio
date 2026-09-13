# Headless workflow editing and execution

Use the ordinary Studio service and the same saved document the UI opens. This is a
current CLI/SDK runbook, not a new executor. Run from the repository root. Commands
below use placeholder IDs/hashes in uppercase: substitute the actual values from
the preceding JSON response. Never send the placeholders literally.

## Discover without model work

```bash
python -m studio_workflow --help
python -m studio_workflow capabilities
python -m studio_workflow documents list
python scripts/workflow-mcp.py --describe
```

Only `--describe` is fully offline and needs no optional MCP dependency. The other
commands require the configured Studio. `nodes` can request the existing ComfyUI
schema cache; it is not an installation or generation request. Retain the selected
backend/schema identity; never silently switch to satisfy a desired graph.

For a nondefault origin, put the option before the command:

```bash
python -m studio_workflow --url http://127.0.0.1:8191 documents list
```

## Read, preview and deliberately edit

```bash
python -m studio_workflow documents get DOCUMENT_ID
python -m studio_workflow documents history DOCUMENT_ID
python -m studio_workflow documents --help
```

The Python SDK avoids shell quoting and edits the exact shared document. Run the
read/preview part first, inspect the diff, then make the explicitly authorized write.
This example deliberately does not auto-apply a preview:

```python
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient()
current = client.get_document("ACTUAL_DOCUMENT_ID")
print(current)  # Inspect the real server revision and node/input names.
# Example only: select actual IDs and a currently supported input.
commands = [{"op": "set_input", "id": "ACTUAL_NODE_ID", "input": "seed", "value": 42}]
# Use the revision returned by get_document, not an invented or browser revision.
# preview = client.preview(document_id, commands, expected_revision=revision)
# After explicit edit authorization, retain request_id and exact payload first:
# result = client.apply(document_id, commands, expected_revision=revision,
#                       request_id=retained_edit_request_id)
```

`preview` does not commit. `apply` requires the current expected revision and a
retained caller-generated request ID. HTTP 409 means conflict; inspect the latest
state, do not silently rebase or overwrite the user's work. An ambiguous save is
recovered using the original identity and exact payload. A deliberate new edit
gets its own identity. See [SHARED-DOCUMENTS.md](SHARED-DOCUMENTS.md) for real command
JSON and CLI file shapes.

## Prepare a saved revision, inspect, then decide

Use a registered non-reference image preset whose full graph matches the saved
document except for supported catalog-bound controls. Do not infer this from its
name or `source` annotation. Unsupported rewiring/references fail preparation.
Retain `PREPARATION_REQUEST_ID` with these exact arguments before requesting:

```bash
python -m studio_workflow runs prepare DOCUMENT_ID --expected-revision REVISION --preset PRESET_ID --request-id PREPARATION_REQUEST_ID --ticket-out retained-ticket.json
python -m studio_workflow runs get PREPARATION_REQUEST_ID
python -m studio_workflow runs review PREPARATION_REQUEST_ID
```

Preparation does **not** approve or submit generation. It may persist a preparation
record and uses ordinary validation/resource checks. `--ticket-out` refuses an
existing path. Read the returned `record_sha256` and `ticket_sha256`, the actual
recipe/controls, source revision, warnings, and retained job identity. Do not
regenerate or deserialize/re-encode a wide-integer ticket through JavaScript just
to inspect it.

Only after execution is authorized for that exact reviewed content:

```bash
python -m studio_workflow runs run PREPARATION_REQUEST_ID --record-sha256 RECORD_SHA256 --ticket-sha256 TICKET_SHA256 --approve
python -m studio_workflow runs observe PREPARATION_REQUEST_ID
```

Hashes identify reviewed content; they are not human authentication or permission.
`runs observe` is one observation, not a hidden retry or endless watcher. For a
retained actual job ID, `status JOB_ID` and bounded `wait JOB_ID --seconds 600`
observe through the original Studio routes. Stopping observation does not cancel
the job. A partial output still needs explicit inspection and review.

## Recover rather than repeat

After a timeout, lost response, crash, uncertain status or export failure, keep the
original preparation request ID. Use `runs get`, `runs review`, and `runs observe`.
Use `runs by-job JOB_ID` when the actual job ID is what survived. Do not invent a
replacement request or freshly prepare as an automatic retry. A record can exist
without a confirmed dispatch; keep the distinction visible. See
[SAVED-RUN-CLIENTS.md](SAVED-RUN-CLIENTS.md) and
[SAVED-RUN-DISPATCH.md](SAVED-RUN-DISPATCH.md).

## MCP and new-machine checks

The optional stdio adapter exposes the same operations, constrained by `read`
(default), `author`, or `execute` mode. `--describe` proves local schema discovery,
not that a host can connect or that dependencies are installed. Follow
[MCP-AGENTS.md](MCP-AGENTS.md) for its pinned **separate tools environment** and
absolute interpreter/script paths. Do not install into ComfyUI's Python.

Before live use, separately establish: configured Studio reachable; chosen backend
and installed schema available; required model files and resource admission; saved
document/revision match; intended MCP permission mode and host approvals; retained
request storage. Unknown status is a reason to inspect, not a license to install,
restart or run. Useful outputs, artistic acceptance and licensing remain distinct.
