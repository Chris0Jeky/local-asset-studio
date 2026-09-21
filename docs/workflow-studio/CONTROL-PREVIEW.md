# Preview one setting across several node inputs

Continuation of #384 under #119/#120/#123, 15 September 2026. The first increment
adds a pure planner, an ordinary Studio HTTP route and a Python SDK method. The
interactive panel is a separate dependent increment. Neither increment applies a
change, saves a document, stages an image or submits a generation.

## Contract and boundaries

A `studio.control/v1` descriptor contains a readable name and 1–32 ordered, explicit
node/input targets. It is an ephemeral proposal, not a new field in
`studio.workflow/v1`, a reusable module or a second value store. Existing Steps and
unknown source annotations remain untouched. Unsupported descriptor versions refuse;
older clients need not strip or migrate existing workflow documents.

The planner uses `core.catalog` over the active installation's existing schema
cache. It retains the supplied document revision and exact document, control and
raw-schema hashes. HTTP requests do not accept a replacement schema or backend.
The original document's backend/schema must match the current schema; a switching
backend refuses. No new poller, node installation or environment switch is added.

`expected_revision` checks the **supplied draft**, not a server-saved head. This is
a read-only preview of caller-owned bytes, not Workspace compare-and-swap. The UI
must additionally discard results after local edits. Saved-document application
remains a future reviewed operation through existing Workspace CAS and receipts.
A preview hash or emitted command does not confer permission to apply or execute.

## Supported first adapter

All targets must declare the same supported literal type: INT, FLOAT, STRING,
BOOLEAN or bounded scalar COMBO. INT and FLOAT are not silently unified; a FLOAT
input may accept an integer literal under the existing authoring convention.
Booleans are not numeric values. Text is limited to 65,536 characters. Python
preserves wide integers; browser consumers must refuse unsafe values, not round
and return a seemingly valid proposal.

Numeric bounds intersect; an integer interval must contain an actual integer.
Per-target `step` values are retained as widget hints, not invented divisibility
constraints. Proposed values are never rounded. COMBO intersections retain the
first target's order and compare JSON types exactly, including bool versus int.
Differing current values display as mixed. Missing optional values are recorded as
absent, not confused with null. Selecting a model filename only checks the literal
choice: it establishes neither file presence, compatibility, terms nor memory fit.

Duplicate/missing targets, ambiguous input definitions, changed identity, empty
intersections and out-of-range values block the complete command batch. Existing
connections cannot be replaced with literals through this feature. Dynamic,
forced/default sockets, lazy/raw/remote/list behaviour, hidden controls and custom
widget declarations remain inert with per-target diagnostics. Unadvertised custom
validation cannot be inferred from `/object_info`; the preview is not a runtime
validator or full-graph check, even when its state is `ready`.

## HTTP and SDK

`POST /api/workflow-studio/control-preview` is read-only despite using POST for its
bounded JSON request. It inherits the ordinary same-origin guard and one-MiB body
limit. Malformed requests return 400/`control_preview_invalid`; incompatible
proposals return 200 with `state: blocked`, diagnostics and **no commands**. The
canonical UTF-8 report also has a one-MiB cap; evidence is not silently truncated.

```python
from studio_workflow.sdk import WorkflowClient

client = WorkflowClient()
current = client.get_document("ACTUAL_DOCUMENT_ID")
report = client.preview_control(
    current["document"],
    {"format": "studio.control/v1", "name": "Shared seed",
     "targets": [{"node": "ACTUAL_FIRST_NODE", "input": "seed"},
                 {"node": "ACTUAL_SECOND_NODE", "input": "seed"}]},
    42, expected_revision=current["document"]["revision"])
print(report)  # Inspect only: this example performs no apply or generation.
```

The report includes current values, proposed value, shared constraints, diagnostics,
exact identities and an ordered batch of ordinary `set_input` commands only if all
targets pass. There is no new execution ticket. The SDK closes error responses and
returns structured `ClientError` status/code without retry. Existing CLI/MCP tools
are not silently expanded; agents can use the Python SDK or the ordinary HTTP route.

## Delivery and proof

Test-first planner cases initially failed because the feature was absent. The
planner suite covers ranges, choices, types, mixed/absent values, wide integers,
stale identity, connected/native-only inputs, atomic refusal and report limits.
Native temporary loopback HTTP tests exercise the shipped route, real SDK transport,
origin/body guards and offline/busy responses. Their fake Studio traps Workspace
access and job creation. The full-checkout composition test also verifies that the
ordinary composed handler exposes the route and capability; it is explicitly
skipped in a partial local source reconstruction and must run in hosted CI.

```bash
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_workflow_control*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

No configured workstation, ComfyUI model, GPU, source artwork, runtime package,
user Workspace or HUMAN_TODO choice is changed by these tests. Synthetic schemas
are contract fixtures, not a claimed installed-version golden corpus. #382 still
tracks the separately unpublished ordering UI; #384 remains open until its
interactive preview and full acceptance are verified.

## Research basis

The existing normalizer and command reducer remain the implementation authority.
Primary upstream descriptions checked on 15 September 2026:

- https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/comfy_types/node_typing.py
  describes `forceInput`, `lazy`, `rawLink`, widget hints and `INPUT_IS_LIST`.
- https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py
  handles list-aware execution separately from ordinary literals.

These moving upstream sources justify conservative boundaries, not support claims
about a particular installed revision. No upstream code is imported or evaluated.
