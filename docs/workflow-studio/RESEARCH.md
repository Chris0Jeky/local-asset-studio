# Research and repo findings

Reviewed 12 September 2026. External sources below are primary Comfy documentation, not proof of the user's installed version. No model/package install, GPU benchmark, native frontend audit or generation was performed in this pass.

## Comfy integration findings

### Metadata can generate useful controls, but not an entire native frontend

[Comfy data types and widgets](https://docs.comfy.org/custom-nodes/backend/datatypes) describe scalar/combo inputs, widget metadata and frontend-dependent constructs. [NodeDef JSON](https://docs.comfy.org/specs/nodedef_json) documents richer input/output definitions and presentation metadata. These support a schema-driven inspector, but do not justify interpreting every custom widget as a generic editable scalar. The implemented normalizer handles a bounded subset; rawLink/remote/custom socketless and unrecognized dynamic behaviours require adapters.

Keep raw schema fingerprints and declared presentation metadata. Numeric controls must preserve precision rather than silently round large seeds through browser JSON. A custom-node label or description is data, never markup to execute. A published descriptor is not proof that model files exist or memory is sufficient.

### API graphs and visual workflows are different artifacts

[Workflow API format](https://docs.comfy.org/development/api-development/workflow-api-format) distinguishes executable API data from frontend workflow representations. API nodes alone cannot reconstruct every frontend widget, visual group or extension state. This slice therefore accepts a node map, retains supported API metadata and rejects native visual/prompt-envelope intake. It does not label an API export a lossless native visual export.

[Subgraph guidance](https://docs.comfy.org/interface/features/subgraph) and [subgraph developer documentation](https://docs.comfy.org/custom-nodes/js/subgraphs) identify a native route toward reusable grouped workflows. The next investigation should test native subgraphs and exposed inputs against the actual installed frontend instead of inventing an incompatible group format first. Unknown native payloads must survive in original source artifacts even when Studio cannot edit them.

### Native App Mode is an architectural option, not automatic parity

[App Mode](https://docs.comfy.org/interface/app-mode) is worth evaluating alongside the Studio's outcome-oriented Step view. A version-pinned native adapter may reduce duplicated widget behaviour, while a Studio-owned module inspector offers clearer task-level semantics and shared agent commands. The decision depends on actual installation support, round-trip fidelity, extension compatibility and maintenance burden. An iframe alone solves none of command identity, provenance, headless parity or document synchronization.

### `/prompt` is not a dry-run endpoint

[Comfy server routes](https://docs.comfy.org/development/comfyui-server/comms_routes) describe `/object_info`, `/prompt`, queue/history and websocket routes. `/prompt` participates in validation **and submission**, so checking a graph by posting it would violate a no-generation inspection contract. Use pure structural checks for authoring and the established runtime validation path at explicitly approved execution. Native queue mutation and global interruption also need ownership-aware handling, not a generic UI proxy.

## Repo audit and integration choices

Inspected main at `064d6026f54b77f19fb701cee5409d2a316c993f`, including `AGENTS.md`, `CLAUDE.md`, the head of `CURRENT_STATE.md`, `HUMAN_TODO.md`, the live harness tier, active-gate notes, server preparation/submission/handler paths, Prompt's HTTP extension, shared shell, issues and recent PR activity.

The existing Studio has registered preset bindings, companion controls, reference staging, a shared worker, asset indexing, Production plans and uncertainty handling. The correct integration is to reuse these. A second headless worker or browser-side Comfy proxy would compete for ownership and could discard recovery evidence.

`Studio.prepare` is not perfectly side-effect-free: it can stage missing reference files. The documentation says “no model submission,” not “no disk writes.” Registered recipe tickets keep this existing behaviour and recheck their limited pins before dispatch.

The shared shell already works across independently served pages. One navigation entry and opt-in coach loading avoid replacing existing Create/Workspace/Production/Prompt/Scene/Voice tools. The existing handler-extension seam admits isolated routes without rewriting `app/server.py`.

There were no open PRs in the initial review. A publication-time recheck found **PR #125**, runtime recovery, touching server/backend/runtime and existing app screens. Its changed-file list does not overlap this slice's two modified integration files (`studio_prompt/http_extension.py`, `app/static/studio-shell.js`) or new modules. This work does not duplicate its recovery loop or worker-health logic; it continues to delegate to `Studio.prepare/create_job`.

## Existing issue ownership to preserve

#16 remains the broad task-oriented UI work; #9 model/capability provenance; #10 bounded experiments and reconciliation; #22 trusted shared execution; #30 AV shared project commands; #38 Prompt shared state/commands. New #118–#123 provide scoped Workflow Studio workstreams, not replacements for those owners.

Known recovery/materialization concerns #93/#94/#95/#96/#110 and schema/model-field concerns #97/#104 must remain visible when authored execution is enabled. #106 owns host-commit enforcement. This first slice does not claim to fix those issues, solve every custom-node validation rule, make art acceptable or clear model rights.

## Recommended order

Finish stable guide anchors and schema fixtures; add server-side document commands and module-based Step controls; establish native interoperability; then promote authored plans through the trusted executor. SDK/MCP can grow over the same commands as they stabilize. Enabling arbitrary graph submission before those boundaries exist would turn a UI convenience into a new execution/recovery system by accident.
