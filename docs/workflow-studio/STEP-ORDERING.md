# Arrange workflow Steps with shared commands

15 September 2026. Implements the shared-command portion of #382; advances #120
and #123. The broader workstreams and the UI portion of #382 remain open.

## Delivery boundary

This PR adds `move_step` to the existing reducer, with nine backend/compiler tests.
A matching Move up/down UI and six real-DOM/shared-reducer tests were implemented
and passed locally, but the GitHub UI write was blocked twice by an indeterminate
OpenAI safety-status result. Those UI changes and tests are **not in this PR**.
Do not advertise Move buttons as shipped.

The local UI prototype uses the same reducer, boundary-disabled buttons, keyboard
focus restoration and the existing stale-response guard. Its source and test driver
are retained in the session handoff for independent review and a later UI PR.

## Shared command for agents

The operation uses stable IDs, not presentation indexes:

```json
{"op":"move_step","id":"refine","before":"export"}
```

This places `refine` immediately before `export`. Both must already exist.
`"before": null` moves the Step to the end. Moving before itself, immediately
before its current successor, or from last to last is a no-op. An omitted `before`,
unknown ID, non-string/non-null destination or extra field is rejected.

The existing unsaved-draft route accepts `{document, commands}` at
`POST /api/workflow-studio/documents/reduce`. Saved-document preview/apply use the
same reducer, with their existing expected-revision and request-identity rules.
There is no new CLI executable, MCP permission mode or HTTP execution endpoint.

For an existing saved document, use the SDK read/preview flow below. Substitute
actual document and Step IDs; the example intentionally performs no write:

```python
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient()
document_id = "ACTUAL_DOCUMENT_ID"
current = client.get_document(document_id)
commands = [{"op": "move_step", "id": "ACTUAL_STEP_ID", "before": None}]
preview = client.preview(document_id, commands,
                         expected_revision=current["revision"])
print(preview)
```

Inspect the proposed display order. An authorized apply uses `client.apply` with
that expected revision and a caller-retained request ID plus the exact commands.
Retain those before the request; recover the original request after response loss,
never invent a replacement write automatically. See [AGENT-QUICKSTART.md](AGENT-QUICKSTART.md)
and [SHARED-DOCUMENTS.md](SHARED-DOCUMENTS.md). This slice does not change the
server's concurrency or interrupted-save protocol.

## Implementation and tests

`steps.py` validates both IDs, removes the source from a copied order, then inserts
it at the requested destination. `commands.py` routes `move_step` through the same
structural validation and atomic batch path as other Step edits. No document-format
change is needed. The unpublished UI prototype calculates the neighboring stable ID from a fresh snapshot and uses
the existing epoch/token guarded reducer request; this PR does not modify that UI.

The execution-input and compiled graph hashes remain unchanged. The full document
hash changes because it includes presentation; clients should not confuse the two.
A saved presentation edit may append a normal revision. It must not be treated as
permission to reuse a stale run-preparation revision.

```bash
python -m unittest discover -s tests -p test_workflow_step_order.py -v
```

Nine reducer/compiler tests cover every source/destination pair, no-ops, malformed
commands, atomic failure, 64 groups, legacy documents, preservation and graph/hash
identity. Six local Chromium tests execute the proposed Steps UI with the real Python
reducer: keyboard moves, boundary controls, retained focus, one-call mutations,
newer-edit races and failures. Both new suites failed on the pinned pre-feature
source and passed after implementation; only the nine-test Python suite is published
in this PR.

The browser fixture supplies synthetic editor/session-store and transport seams.
It is not a full Studio page, real session persistence, saved-document HTTP test or
live SDK/MCP round-trip. Browser seed fixtures use safe integers; the Python
preservation test also retains a wide integer without claiming browser precision
support. Existing full-checkout CI remains required. No GPU generation, runtime
readiness, native ComfyUI round-trip or creative acceptance was tested here.

The existing Check studio suite discovers the new Python tests. The local browser
fixture is not added to CI without its matching UI implementation. In the retained
UI handoff, run `python tests/workflow_step_order_browser.py --browser-path /path/to/chromium -v`.
