# Workflow Studio: remaining work after reconciliation

[Reviewed setup application and recovery](SETUP-APPLICATION.md) extends the preview with explicit shared revisions, copy-only Apply, Undo and original-request inspection. Preview remains read-only; see that guide for supported routes and remaining #232 limits.


**13 September 2026; inspected main `06bd93aed2f019cb978eb5795e9f116cfb7ff749`.**
All six original issues remain open for real residual acceptance. Their foundation
paragraphs predate several merged implementations; do not use those paragraphs as
instructions to build another store, SDK, MCP bridge or saved-run journal.

## Ordered-source continuation

The chooser now checks one to three ordered Workspace images and proposed roles;
see [ORDERED-SOURCES.md](ORDERED-SOURCES.md). This advances the observation portion
of #232 and preserves legacy single-source/count-only requests. Complete reviewed
setup diffs, expected-draft concurrency, explicit staging/apply and persisted
undo/reload remain unimplemented in that slice. Neither the original #118/#123
workstreams nor #232 are complete. The historical reconciliation below is retained.

## Reviewed setup proposal continuation — 14 September 2026

[SETUP-PROPOSALS.md](SETUP-PROPOSALS.md) adds complete read-only setup diffs over
the ordered advice service, shared with SDK/CLI/read-MCP. Its captured browser
draft identity is not server CAS. Explicit staging/apply, shared expected-draft
concurrency, partial-failure recovery and persisted undo/reload remain #232 work.
The source was integrated over main `ff6c0f4`, including merged #237/#258.

## Issue disposition and existing ownership

| Workstream | Existing implementation to preserve | Remaining acceptance / next increment |
| --- | --- | --- |
| [#118 Guided creation](https://github.com/Chris0Jeky/local-asset-studio/issues/118) | `guides.py`, `studio-guide-state.js`, `studio-guide.js`: seven evidence-aware paths; #169. This pass addresses focused #185/#190. | Capability-backed recipe proposals with explicit missing/unknown prerequisites; specialist comparison/scene/export/reference predicates; owner-run separately reviewed journey. |
| [#119 Installed-node controls](https://github.com/Chris0Jeky/local-asset-studio/issues/119) | `core.py`, `node_outputs.py`, existing builder fields. #156/#167/#168 already advance validation/output normalization/resource diagnostics. | Installed-version golden corpus; declared adapter support levels; dynamic/list/union/native-widget fidelity; lossless wide-integer editing; shared compatibility reports. |
| [#120 Shared authoring](https://github.com/Chris0Jeky/local-asset-studio/issues/120) | `commands.py`, `documents.py`, `steps.py`, `workflow-projects.js`: revisions/CAS/receipts/preview/restore/fork, Steps and inverse commands. | Typed reusable module interfaces/fan-out; actual workflow reference handles and slot lineage; measured 50/150/256-node interaction budgets and large-catalog rendering. |
| [#121 Native interoperability](https://github.com/Chris0Jeky/local-asset-studio/issues/121) | Separate API-document contract; native visual import is deliberately refused. | Record installed frontend/backend/node versions; preserve original native artifacts; measured bidirectional adapters for widgets, reroutes, mode semantics and nested subgraphs. |
| [#122 Authored execution](https://github.com/Chris0Jeky/local-asset-studio/issues/122) | `preset_adapter.py`, `document_runs.py`, `saved_dispatch.py`: supported image projection, revision-bound run records, exact-ticket/hash review, existing worker. | Reference/source binding and broader authored-graph adapters; native/resource/side-effect admission; full failure matrix and owner-run evidence before arbitrary execution. |
| [#123 Headless agents](https://github.com/Chris0Jeky/local-asset-studio/issues/123) | `sdk.py`, `agent_bridge.py`, `mcp_server.py`, document/run CLIs: shared command parity, permission modes, retained-request recovery. | New-machine capability/runbook acceptance, bounded output/artifact access and provenance, reconnectable progress with ownership/cancellation semantics; live mixed human/agent acceptance. |

No broad issue is complete merely because one of its foundations merged. #185 and
#190 are bounded guide defects, not substitutes for all #118 acceptance. Runtime
recovery, source continuation and resource profiling retain their existing owners;
this guide patch does not claim those issues.

## Architecture to keep

```text
Guided observation ──────────► existing feature state/read endpoints
Steps / Nodes / CLI / SDK / MCP
             │ one studio.workflow/v1 document and command vocabulary
             ▼
     Workspace immutable revisions + expected_revision + retained request IDs
             │ only a supported execution adapter
             ▼
     saved revision + immutable run record + exact ticket review
             ▼
     existing Studio admission / worker / prompt IDs / Workspace outputs
```

Guidance does not own jobs. A Step control references an existing node input, not a
second value. A future compatibility projection must label editable, serializable,
executable and native-only support separately, and must not become a replacement
for the authoritative runtime validator. A fresh schema or connected diagram is
not sufficient evidence for execution.

## Next implementation sequence

### 1. Capability-backed choice, within #118/#119

Extend the current guided launcher rather than introducing a wizard with its own
recipe state. Start with new-image versus source-preserving edit. Read the actual
catalog/capability records and the selected source role. Produce a deterministic
shortlist with explicit reasons and **unknown**, **needs setup**, or **candidate**
status; a candidate is not a readiness approval. Reuse existing dependency and
continuation checks. Do not rank a blocked preferred preset ahead of alternatives
without showing the blocker, or infer editing capability from a name substring.

First write pure fixtures for: missing source, unsupported source role, inactive
backend, missing model, unavailable health, schema drift, and no suitable recipe.
Then add opt-in UI rendering and keyboard tests. Selecting a suggestion must use
the normal reviewed handoff/selection path. A delayed shortlist cannot replace a
newer choice; page load and inspection must create zero jobs/installs/switches.
Publish the same explanatory result for agents rather than inventing a separate
LLM-only recommender. No LLM is needed for this deterministic first increment.

### 2. Installed-schema corpus and adapter support, within #119

Capture only schema/version evidence from the configured runtime; do not upgrade
it to match current online documentation. Redact local paths/tokens where present
before checking in fixtures. Extend `core.py`/existing normalization seams using
one adapter at a time: union/list semantics, optional/forced inputs, dynamic
choices, then model/image/mask widgets. Each adapter needs lossless unsupported
retention, browser and Python precision tests, stale-schema refusal, bounded
rendering, and explicit execution support status. Coordinate the real graph
checker with #97 rather than adding another divergent checker.

### 3. Reference-bearing shared workflows, within #120/#122

Specify a versioned asset-handle contract before changing execution. Bind Workspace
identity and source bytes to exact node/input/role; preserve original-source and
staged-copy identities separately. Add stale asset/mask/revision tests before
allowing a compatible saved reference workflow. Use the existing prepare/dispatch
journal and source-continuation ownership, including concurrent human/agent edits
and uncertain submission. Do not enable general graph execution as a side effect.

### 4. Native format and agent acceptance, within #121/#123

Decide between explicit native handoff and a version-pinned adapter using the
installed corpus, not an iframe proof. Preserve original opaque native data before
any conversion. Start with one supported visual graph, then nested/subgraph cases.
For agents, run the same saved revision through CLI/SDK/MCP; inject response loss,
conflict and restart; observe the original request. Test a clean tools environment
without touching ComfyUI packages. Record owner artistic review separately.

## Primary-source checks

Checked 13 September 2026: [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes)
distinguish node descriptions (`/object_info`) from prompt validation/submission
(`POST /prompt`). This supports keeping schema-driven authoring separate from
execution admission. It does not establish the installed version's widget or
subgraph support. Existing `RESEARCH.md` retains the broader native-format research.

## Source-aware guidance continuation, 13 September 2026

Merged #217 supplies count-based default-recipe advice. The next source adapter
checks one actual primary Workspace image and an explicitly proposed role through
the same UI/HTTP/SDK/CLI/read-MCP service. See
[SOURCE-AWARE-SHORTLIST.md](SOURCE-AWARE-SHORTLIST.md) for delivered boundaries and
the ordered multi-source, reviewed reversible-handoff acceptance still remaining
in #232 under #118/#21/#123. This adds no native round-trip or arbitrary execution support.
