# Workflow Studio

[Reviewed setup application and recovery](SETUP-APPLICATION.md) extends the preview with explicit shared revisions, copy-only Apply, Undo and original-request inspection. Preview remains read-only; see that guide for supported routes and remaining #232 limits.


Current entry point, reconciled on **13 September 2026** against main
`06bd93aed2f019cb978eb5795e9f116cfb7ff749`. Historical implementation notes below
retain their original verification dates; use this page and [ROADMAP.md](ROADMAP.md)
for the current boundaries. No GPU generation or owner-machine acceptance is
established by this reconciliation.

For an outcome-based shortlist of current default routes and their prerequisites,
use **Create → Recipe library → Help me choose a recipe**. The same read-only
[recipe shortlist](RECIPE-SHORTLIST.md) is available to CLI, SDK and MCP clients.

For one to three actual images in a deliberate order, use the library's
**Find recipes for selected images** action and [ordered source advice](ORDERED-SOURCES.md).
It checks every chosen source and proposed slot without staging or applying anything.
Visual-only multi-picture routes have separate prompt, slot and recovery semantics;
see [Style-board setup and recovery](STYLE-BOARDS.md).

For a complete before/after comparison without replacing Create, choose
**Preview proposed setup** on a source-bound suggestion; see
[SETUP-PROPOSALS.md](SETUP-PROPOSALS.md). This is review/export only, not Apply.

## What you can use now

Open **Guided workflows** in the Studio navigation.

| Surface | Implemented | Important boundary |
| --- | --- | --- |
| Guided paths | Seven opt-in journeys; stable stages; focus the actual control; explicit recipe/reference/readiness/output/review checks; pause/resume | Navigation is not completion. Some stages require manual review; recommendations based on current installed capabilities are not complete. |
| Nodes | Installed-node search, numeric/combo/checkbox controls, optional inputs, typed connections, disabled nodes, declared bypass, selected outputs, static checks | Only the supported schema/widget subset is editable. Unknown data stays preserved/inert. Native visual/subgraph import is not supported. |
| Steps | Named node groups, exposed controls, enable/disable, duplicate and undo; same document as Nodes | These are named groups, not a general native subgraph/module library. Disabling a producer needs an explicit valid passthrough. |
| Shared workflows | Workspace SQLite storage, immutable revisions, compare-and-swap writes, command preview/apply, restore/fork, conflict and interrupted-save recovery | Browser draft recovery is local. Save to Workspace explicitly to share a revision with an agent. |
| Execution | Existing registered-recipe tickets; compatible non-reference image-document projection; saved-revision run preparation/history; exact retained ticket review and dispatch | Arbitrary rewiring, native widgets, reference-bearing authored graphs and selected-output subsets are not promoted to execution. There is still one Studio worker. |
| Agents | JSON CLI, Python SDK, optional stdio MCP with read/author/execute modes; shared commands and saved-run recovery | MCP is a client of the ordinary Studio server, not a hosted MCP endpoint or second runtime. Installation, runtime readiness and creative acceptance remain separate. |

The guide now invalidates prior observations on programmatic recipe/setup changes,
including changes that do not fire a browser `input` event. Native Back/Forward
restores the destination stage without mistaking its paired hash event for a new
edit. Actual tool/input changes still invalidate evidence. See
[GUIDE-CONTEXT.md](GUIDE-CONTEXT.md) for the regression record and test boundaries.

## A practical human workflow

Start a guided path and use **Show the control** to locate the actual field. Use
**Check this step** for fresh evidence; the guide does not operate the control.
Choose sources deliberately, inspect readiness, and submit only through the normal
Generate/run controls. Select the exact run when checking outputs and record the
artistic decision separately.

For custom authoring, load installed nodes and import a recipe/API graph. Expose
useful controls in named Steps; switch to Nodes for the actual connections. Check
the draft, **Save to Workspace**, and retain its ID and server revision. A saved
workflow is not automatically runnable. For a supported image recipe, prepare a
saved-revision run, inspect its exact retained ticket, then decide whether to run.

## Start an agent without browser clicks

Use the ordinary configured Studio service; do not start a second worker beside an
already running one. From this checkout:

```bash
python -m studio_workflow --help
python -m studio_workflow capabilities
python -m studio_workflow guides
python -m studio_workflow documents list
python scripts/workflow-mcp.py --describe
```

The last command is **offline tool-schema discovery**: it neither contacts Studio
nor imports the optional MCP package. The other commands need the ordinary local
Studio at `http://127.0.0.1:8191`; change its literal loopback origin using the global
`--url` option before the subcommand. Start the service with the normal launcher,
or `python app/server.py --repo-root .` on an already configured machine.

Use [AGENT-QUICKSTART.md](AGENT-QUICKSTART.md) for the shared-revision edit → prepare →
review → run → recover sequence, including the exact CLI shapes and authority
boundaries. Use [MCP-AGENTS.md](MCP-AGENTS.md) to configure the optional stdio host.
The HTTP capabilities response's legacy `mcp: false` does not mean that this local
stdio client is absent; do not infer installed host/dependency readiness from a
server capability boolean.

## Read the right implementation note

- Guidance: [EVIDENCE-GUIDES.md](EVIDENCE-GUIDES.md),
  [GUIDE-NAVIGATION.md](GUIDE-NAVIGATION.md), [GUIDE-CONTEXT.md](GUIDE-CONTEXT.md).
- Authoring: [SHARED-DOCUMENTS.md](SHARED-DOCUMENTS.md),
  [STEPS-AND-SAVING.md](STEPS-AND-SAVING.md), [SCHEMA-CONTRACTS.md](SCHEMA-CONTRACTS.md),
  [OUTPUT-SCHEMAS.md](OUTPUT-SCHEMAS.md).
- Execution: [PRESET-EXECUTION.md](PRESET-EXECUTION.md),
  [SAVED-RUN-BUILDER.md](SAVED-RUN-BUILDER.md), [SAVED-RUN-DISPATCH.md](SAVED-RUN-DISPATCH.md),
  [SAVED-RUN-CLIENTS.md](SAVED-RUN-CLIENTS.md).
- Strategy and research: [ROADMAP.md](ROADMAP.md), [ARCHITECTURE.md](ARCHITECTURE.md),
  [RESEARCH.md](RESEARCH.md). The latter two describe the original architecture,
  not a claim that all later increments remain unimplemented.

## Verification

```bash
python -m unittest discover -s tests
python scripts/validate-repo.py
python -m unittest discover -s tests -p test_studio_guide.py -v
python tests/studio_guide_browser.py --out .runtime/guide-proof
```

The native browser command requires test-only Playwright and permission for local
HTTP navigation. CI provides its isolated browser environment. Unit contracts with
synthetic DOM/HTTP seams are not native rendering evidence. Neither kind of test
proves a model produces useful artwork on the owner's machine.

Selected-source route advice: [Find recipes for an image](SOURCE-AWARE-SHORTLIST.md)
checks one primary Workspace identity and proposed role without modifying Create.
