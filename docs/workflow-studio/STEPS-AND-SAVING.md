# Steps view and saved workflows

Follow-up to #126 and #130, advancing #120 and the shared command portion of #123.
This is a usable UI over the same API nodes and server documents, not another graph,
queue, project database or Comfy frontend clone.

## In the Studio

Open **Guided workflows → Workflow builder**. Load installed nodes and import a
registered recipe/API document, or create an empty workflow. Nothing is generated.

1. Choose **Create named step**, give it a name/description, select its nodes and
   the inputs to expose. Give exposed inputs readable setting labels.
2. Use **Steps view** for those controls, or **Nodes view** for the underlying
   settings and typed connections. Both edit the same document. Unknown schema
   fields are retained and explained rather than silently replaced.
3. Toggle a step to enable/disable its nodes. A disabled producer still needs an
   explicit compatible bypass in Nodes; disabling is not a guessed reconnection.
   Connection diagnostics remain visible in Steps and link back to Nodes.
4. **Duplicate step** copies its nodes, controls, bypasses and layout with explicit
   new IDs. Internal connections follow the copy; external sources stay shared.
   Copies of output nodes are NOT selected outputs. No outside consumer is rewired.
5. **Save to Workspace** creates a saved document or commits a revision-checked edit.
   **Refresh saved → Open current** opens server state, while **Export document file**
   remains a portable local JSON download. Browser draft autosave is still local;
   server saves are explicit.

Empty groups are permitted: removing their last node retains the grouping metadata.
Removing a grouping does not remove or enable its nodes. Undo/redo retain the steps,
settings and disconnected draft branches. Limits are 64 groups, 32 exposed controls
per group and the existing 256-node document limit; a node belongs to one step.

## Human/agent conflicts and interrupted saves

The UI displays its attached server revision separately from the local draft counter.
A save sends the same shared service command available to SDK/CLI clients:

```json
{"request_id":"stable-request-key","expected_revision":4,
 "commands":[{"op":"replace","document":{"...":"the full local draft"}}]}
```

That example is illustrative: `document` must be a full `studio.workflow/v1` object.
Whole-document saves use compare-and-swap, never unconditional replacement. An agent
committing while a browser edits causes a visible conflict, not last-writer-wins.
The browser keeps local changes and offers **Open current** or **Save separate copy**.
A separate copy stores the local document as a new record; it is not the SDK's
exact-revision fork operation and does not invent a server-recorded fork origin.

Before a write, its exact path, payload and request ID are retained in **sessionStorage**
for that browser tab. A storage failure prevents the request. Transport/503 failures
keep the same pending request; **Retry retained save** replays that identity. The UI
never generates a fresh key automatically after an ambiguous result. A tab reload can
recover its pending request explicitly, but the resulting old receipt is not attached
to an unrelated current draft. Actual browser storage availability is a prerequisite.

A successful response arriving after further edits leaves those edits intact. A
response for a draft that has been replaced never attaches to its replacement. A
replayed old receipt whose head has advanced is a conflict, not current state. JSON
key ordering and local revision counters are excluded from dirty-state comparison.

**Load revision history → Restore revision** appends the historical snapshot as a
new server revision. It does not erase history. A stale restore is refused just like
a stale save. Read history previews as bounded summaries; exact documents remain
readable per revision. Browser draft restoration deliberately starts detached from
server state, rather than trusting a stale saved revision binding.

## Shared step contract

`steps` is an optional additive field in `studio.workflow/v1`. Old documents retain
their original form when no steps are present. An older client that rejects unknown
fields must be upgraded; do not strip the field to pretend a lossless round-trip.

```json
{"id":"refine","name":"Refine appearance","description":"Optional finishing pass",
 "nodes":["2"],"controls":[{"name":"Refinement amount","node":"2","input":"factor"}]}
```

This is an illustrative synthetic binding, not a diffusion-model recommendation.
Each control points at an existing node and input name; it stores no separate value.
Absent optional/unsupported fields can remain annotated in a draft, but they are not
advertised as executable without the matching schema/adapter. Presentation does not
change the compiled graph hash; enable/value/connection edits do.

New reducer commands are `put_step`, `remove_step`, `set_step_enabled`, and
`duplicate_step`. They are accepted by the shared SDK/CLI `apply`/`preview` contract
from SHARED-DOCUMENTS.md. `duplicate_step` requires a complete explicit `node_ids`
map, a fresh `new_id`, and a name; collisions are rejected. Node removal prunes group
membership and its exposed-control references, while preserving consumer graph errors.

The UI can apply these commands to an unsaved draft through
`POST /api/workflow-studio/documents/reduce` with `{document,commands}`. This is the
same pure reducer used inside transactions, but returns `committed:false` and
`generation_submitted:false`. It requires neither database initialization nor schema
or Comfy access. A stale asynchronous result is discarded if the draft changed.

## Integration boundary

`WorkflowStudio` exposes a narrow frozen bridge for snapshot/change/load/schema,
field rendering, validation and inspection. It does not expose execution. The new
`workflow-projects.js` uses that bridge and the shared document routes; it does not
own another graph. The original field editor supplies the same numeric/checkbox/
combo/text/socket controls in both views. `workflow-project-state.js` isolates the
save/recovery state for deterministic browser-independent tests.

No dependency/build-system change, downloaded widget code, model install, runtime
restart, graph execution adapter, native visual conversion or MCP server is added.
Registered-recipe tickets remain the only new headless execution lane. Full reusable
module libraries with typed external interfaces, fan-out macros and native subgraphs
are still #120/#121; these named/duplicable groups are their smaller first slice.

## Verification

Local isolated suite: 51 tests, 50 passed and 1 full-checkout integration skip. This
includes the parent document/ticket/review regressions plus 11 step tests and one
Node wrapper running **14 browser-state contracts**. Those contracts cover retained
writes, storage failure, stale edits, response races, cross-draft results, reload
recovery, restore, JSON ordering, and endpoint restrictions.

The opt-in fixture `tests/workflow_steps_browser.py` exercises the actual new HTML,
CSS and three JavaScript files in Chromium with synthetic node definitions and the
real SQLite/shared command service. It passes step creation with a readable setting
label, editing, save, intervening agent conflict, separate copy, explicit current
load, history/restore, disable diagnostics, duplication, undo/redo, 390px no page
overflow, and dialog Escape. Zero page errors and zero generation requests.

The fixture uses simulated transport, storage and (on an insecure blank page) UUIDs.
It does **not** establish native shell navigation, true browser-origin/session-storage
persistence, the installed Windows/ComfyUI path, real custom-node widgets, inference,
resource fitness or art acceptance. Real loopback HTTP/origin contracts are tested
separately by the parent service suite. Hosted full-checkout CI remains the integration
gate. Screenshots and evidence are produced under the selected --out directory.

```bash
python -m unittest discover -s tests -p 'test_workflow_*.py'
node tests/workflow_project_state.cjs
python tests/workflow_steps_browser.py --out .runtime/workflow-steps-browser
```

Add `--chromium /path/to/chromium` when the executable is not in Playwright's cache.
No browser or models are installed automatically. Human creative choices in
HUMAN_TODO.md remain untouched. #120 and #123 remain open for their remaining scope.
