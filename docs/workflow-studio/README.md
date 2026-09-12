# Workflow Studio: guided creation, graph authoring and headless recipes

Implementation slice and expansion plan · 12 September 2026.

Open **Guided workflows** in the shared sidebar or `http://127.0.0.1:8191/workflow-studio.html` after starting the ordinary Studio. No new service, build step, model dependency or GPU worker is introduced.

## What works in this slice

| Surface | Available now | Deliberately not claimed |
|---|---|---|
| Guided paths | Seven outcome-oriented walkthroughs; real tool links; opt-in contextual coach; back/next/pause; browser resume | Evidence-based automatic completion, recipe recommendation, owner acceptance |
| Workflow builder | Installed node search; API graph/preset import; add/remove; optional inputs; number/text/boolean/combo controls and bounded sliders; compatible connection selectors; draggable diagram and numeric positioning | Every custom widget, wire-drag connection gestures, native visual JSON/subgraph round-trip |
| Document | Explicit outputs, disabled nodes and typed bypass maps; bounded browser undo/redo; local draft; JSON save/open | Shared server persistence, multi-client revision control, reusable Step modules |
| Compiler | Selected-output closure; cycles, missing ports/classes/inputs, basic scalar/range/type checks; stable hashes; explicit unsupported-input errors | Comfy runtime VALIDATE_INPUTS, model compatibility, memory sufficiency or side-effect certification |
| Headless | JSON CLI; discovery; prepare/approve/run registered recipes through the existing Studio worker; retained-ticket replay; status/wait | Arbitrary edited-graph execution, a new MCP server, remote access, exactly-once execution |

### The everyday flow

Start with the desired result: first image, reference/character edit, setting comparison, scene/dialogue, game-asset export, custom workflow or agent execution. Each guide explains the next decision and takes you to the existing tool. Choosing a guide never installs anything or submits a job. Navigation progress is explicitly self-reported; it does not prove a generation, successful export or creative review.

For graph authoring, load the installed nodes, import a registered recipe's API graph or start empty, select a node, set its values and connect named outputs to compatible inputs. Optional fields are enabled explicitly. Select the output nodes you want. **Disabling a node is not the same as bypassing it**: a consumed disabled node needs an explicit output→connected-input passthrough of compatible types. Disconnected branches remain in the editable document, but are not included in the selected output's API graph.

Use **Check connections**, inspect diagnostics, then save the document or export the checked API graph. Editing or refreshing schemas invalidates the prior check. Unknown custom values are retained, not approximated. Native visual JSON and `/prompt` envelopes are rejected instead of being flattened incorrectly. API export is not Studio execution authorization and should not be confused with a visual workflow file.

The browser deliberately rejects documents with integers outside JavaScript's exact range. Use the Python path to retain large seeds, or deliberately change the source seed before importing. Silent rounding is not acceptable.

## Headless quick start

Run from the repository root on the configured machine, using its normal Python environment:

```sh
python app/server.py --repo-root .
```

In another terminal:

```sh
python -m studio_workflow capabilities
python -m studio_workflow catalog
python -m studio_workflow nodes
```

Choose an actual registered `preset_id` from the catalog. Create `recipe.json` with that ID, supported controls and one graph invocation. This illustrative ID is intentionally not executable as-is:

```json
{
  "preset_id": "REPLACE_WITH_AN_INSTALLED_RECIPE_ID",
  "controls": {},
  "batch_count": 1
}
```

Then prepare, inspect and explicitly approve:

```sh
python -m studio_workflow prepare --recipe recipe.json --out ticket.json
python -m studio_workflow run --ticket ticket.json --approve
python -m studio_workflow status JOB_ID
python -m studio_workflow wait JOB_ID --seconds 600
```

Preparation delegates to the normal registered-preset binding rules. It can copy existing local reference files into Comfy's input folder, just as the current preview path does; **it submits no model job**, but is not a universally side-effect-free disk operation. It refuses batch counts other than 1. One graph invocation can still produce multiple outputs through the graph itself: this is not an image-count or memory budget guarantee.

The returned ticket pins the recipe/template, prepared graph, preset metadata, workspace, backend identity/URL, prepared reference metadata and staged `LoadImage` bytes. It does **not** pin every model weight, arbitrary custom-node external input, package version or future file change. Review those through existing runtime and provenance processes. There is no new hardware-readiness claim.

The ticket has a request identity and maps to one Studio job identity. Its intent receipt is written under the existing ignored `experiments/runs/workflow-requests/` tree **before** calling `Studio.create_job`. A repeat with the same retained ticket returns that job, including an uncertain job; it does not enqueue another attempt. An intent with no loaded job stays `reconciliation_required`. Changing content under an already-used request identity is rejected.

**Do not generate a replacement ticket to work around a timeout.** Retain the original ticket and inspect/reconcile it. After a transport failure, a repeat of that exact ticket may dispatch only if no intent was ever retained; if there is a retained intent, it returns the existing job or parks for reconciliation. This is an at-most-one dispatch attempt per retained intent, not a distributed exactly-once promise. Filesystem loss, deletion and multiple independent Studio processes are outside that guarantee.

`--out` refuses to overwrite files. JSON is printed to stdout. Global options precede the command, for example:

```sh
python -m studio_workflow --url http://127.0.0.1:8191 --http-timeout 30 capabilities
python -m studio_workflow import --graph workflow-api.json --out imported.json
```

`import` returns an envelope containing `document`. Save that inner value as `studio-workflow.json` for `compile --document studio-workflow.json`; similarly, a compile result includes `graph` rather than being a graph itself. UI Save document writes the document directly. Node definitions require the active Comfy backend to be reachable. Guides/capabilities do not.

Exit statuses: `0` successful command (not necessarily finished generation), `2` validation/read failure, `3` uncertain execution/reconciliation, `4` observation timeout, `5` observed failed/partial/cancelled job. An observation timeout does not cancel the job. Argument-parser usage failures use its normal exit 2. The client uses literal loopback HTTP only, disables environment proxies, refuses redirects and never automatically retries a mutation.

## HTTP contract

The new handler composes at the existing extension seam. It preserves the base Host and same-origin mutation checks and a 1 MiB POST body limit.

| Method | `/api/workflow-studio` suffix | Meaning |
|---|---|---|
| GET | `/capabilities`, `/guides` | Inert discovery |
| GET | `/nodes` | Normalize the active Studio-cached `/object_info` snapshot |
| POST | `/nodes/refresh` with `{}` | Explicit fresh schema read |
| GET | `/presets/{id}` | Import registered API template into an authoring document; no binding/submission |
| POST | `/open` with `{content: "JSON text"}` | Strict duplicate-key/size-aware document or API-file intake |
| POST | `/import` with `{graph, name?}` | API node map → document envelope |
| POST | `/compile` with `{document}` | Structural diagnostics and checked graph, no submission |
| POST | `/prepare` with `{recipe}` | Registered-recipe run ticket |
| POST | `/run` with `{ticket, approved: true}` | Existing shared worker or retained-request reconciliation |

Existing `/api/catalog` and `/api/jobs/{id}` remain discovery/observation sources. The `arbitrary_graph_execution`, `native_visual_roundtrip`, `server_saved_workflow_documents` and `custom_frontend_widgets` capability flags remain **false**.

## Engineering and next work

[Architecture and decisions](ARCHITECTURE.md) · [Research](RESEARCH.md) · [Roadmap and issues](ROADMAP.md) · [Verification and limits](VERIFICATION.md) · [Agent skill](../../agent-skills/workflow-studio/SKILL.md).

The next substantial step is a revisioned document/command service and reusable Step modules, then native compatibility and shared-runtime promotion. Do not solve those by adding a raw `/prompt` proxy or a second queue.
