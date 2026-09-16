# Inspect a shared setting in Workflow builder

15 September 2026. Refs #384, #119, #120 and #123. This panel consumes the
[shared control preview](CONTROL-PREVIEW.md); it is not a second validator or an
Apply command. The separate Step-ordering UI tracked by #382 remains unpublished.

## Walkthrough

Open **Guided workflows → Workflow builder**, load installed nodes and open or
create a workflow. Expand **Preview a shared setting across nodes** beneath the
builder. Choose a readable name, then select a node and its exact input and press
**Add target**. Repeat for the inputs that should share the proposed value.

Enter a whole/decimal number, multiline text, checkbox value or listed choice.
Press **Preview shared setting**. Inspect each current/proposed pair, mixed-value
notice, common range/choices and any incompatibility. The expandable command list
shows the exact proposed `set_input` batch. It does not run or apply that batch.

The result is deliberately separate from the editable graph. Removing a target,
changing the proposed value or opening another workflow does not write to the
document. There is no autosave, local recovery store, staging, installation or job
submission. Reloading drops this ephemeral proposal, not the saved workflow.

## Why a proposal can be blocked

The server checks every target against its configured schema. Connected, missing,
ambiguous, custom/native-only or incompatible inputs produce diagnostics and zero
commands. A common numeric range or listed choice must satisfy every input. A
model filename choice is only a literal metadata check, not file/terms/resource
readiness. A `ready` report still is not execution authority or a full graph check.

The first selected input determines the editor type; the server checks all others.
Changing the schema refreshes the editor, and old evidence is invalidated. Removing
the first target rebuilds the type-specific field rather than silently coercing the
old value. Different current values stay visible; none is chosen as a hidden default.

The browser explicitly refuses values outside its safe-integer range, including
wide numeric choices and returned metadata. It does not display rounded enum digits
as exact values. Python SDK clients retain wide integers. This is a conservative
browser limitation, not a claim of lossless browser int64 editing under #119.
Integer-valued numeric COMBO choices also require the SDK: native JSON parsing
cannot retain the distinction between an option authored as 1 and one authored as
1.0. The browser labels that ambiguity and refuses before transport rather than
proposing a different literal type. String/boolean and fractional choices remain
available; a typed scalar wire contract remains #119 work.

## Async and resource contract

Each explicit Preview captures the current draft snapshot and epoch. Any workflow
render/replacement or proposal edit invalidates the result and aborts its observation.
Late replies cannot restore an old report or steal focus. Key order in JSON objects
is irrelevant; ordered target identities, value and proposed commands must match.
Errors stay visible; there is no automatic replay. A 15-second transport deadline
is an observation limit, not a claim of remote cancellation.

Requests and streamed response bytes are capped at 1 MiB; over-limit results refuse
rather than retaining a partial command list. Targets are capped at 32, node/input
selector rendering at 256, and supported choice lists at 256. Long value previews
are labelled as display-shortened; exact commands remain available on deliberate
expansion. Server limits remain authoritative. No background polling is introduced.

The backend `expected_revision` compares the caller's supplied document revision,
not a saved Workspace head. This panel does not claim persistence concurrency.
Reviewed application remains future work through the existing Workspace CAS and
retained-request service, with fresh document/schema validation at that boundary.

## Verification

The browser fixture loads the shipped JavaScript/CSS into real Chromium DOM and
uses the actual Python planner. Only editor state, transport and installed schemas
are synthetic. It tests typed input, mixed values, rejection, wide integers, hostile
labels, keyboard actions, stale responses, schema refresh, request failure, byte
limits, 390px and 200%-CSS-zoom layout. Both mismatched target rows and altered
command payloads refuse. A new workflow clears the proposal rather than inheriting
another document's targets. The fixture traps unexpected network access and
attempted editor mutation; it makes no model or Workspace calls.

```bash
python -m unittest discover -s tests -p 'test_workflow_control*.py' -v
python tests/workflow_control_preview_browser.py --out .runtime/control-preview-proof -v
python tests/workflow_control_precision_browser.py --out .runtime/control-precision-proof -v
```

Use `--browser-path /path/to/chromium` for an already installed browser. The existing
Guided journey browser lane runs these commands alongside the full-page journeys
and publishes the bounded JSON receipts. No product dependencies are added.

The local source environment is partial; its full handler-composition case is
explicitly skipped until hosted CI. The isolated browser fixture does not prove
native page navigation, live SDK/MCP deployment, actual installed custom widgets,
owner-machine model quality or screen-reader acceptance. Existing full-checkout
CI and guide journeys are still required. Original workflow HTML was matched to
Git blob `30f1cec0d338a64c3c0bcd89e879d6f1cb41bd17` before adding the two asset links.

## Remaining work

#384 retains full-editor/owner acceptance until recorded. Broader #120 covers
persisted reusable interfaces and a separately reviewed application path; #119
covers the installed corpus and wider widget/precision support. #123 owns expanded
CLI/MCP parity beyond this shared HTTP/SDK entry. This preview does not substitute
for those gates. HUMAN_TODO choices and generation allowances remain unchanged.
