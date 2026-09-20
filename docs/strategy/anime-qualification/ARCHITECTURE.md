# Architecture decisions for research integration

Status: proposed integration decisions under #552, except where explicitly described as existing implementation. The report's architecture delta is intentionally small. The objective is better decisions and more reliable accepted assets, not a new abstraction around every paragraph.

## ADR 1: one owner for each kind of truth

| Existing owner | Information or action it owns | What the research adds, not another owner |
| --- | --- | --- |
| `models/library.json` and current model intake | Declared asset identity, source, hash, terms and installation provenance | Exact architecture/prediction, encoder/VAE relationships and configuration distinctions, keyed by existing IDs. Live loaded-byte attestation remains separate. |
| `presets/settings-kb.json`, Prompt Lab profiles/compiler | Sourced parameter guidance and model-specific language projection | Family/exact-version/local-workflow source scope, negative-channel semantics, conditional accelerator knowledge and deliberately versioned dialects. |
| Reference Intelligence and reviewed CreativeIntent | Metadata, visual observations, confidence, role suggestions, immutable source identity and reviewed intent | Outfit/costume compatibility, background/composition ownership, transforms and an explicit capability projection. Analysis never approves generation. |
| Workflow Studio, registered catalog and paired graphs | Validated control bindings and exact native node contracts | Evidence-carrying slot order, precomputed-guide bypass, supported controls and representation conversions. A valid graph is not a successful neural task. |
| Existing coordinator and backend manager | Admission, queue/job state, backend transitions and ambiguous-response recovery | Consume the selected qualified setup; do not delegate admission to a client “idle” flag, a benchmark planner or the resource observer. |
| Workspace | Asset lineage, revisions, review, collections and reuse | Owner-approved canon and its immutable references, per-subject identity, analysis/pose/mask derivatives and acceptance history. |
| Experiment Lab / Production | Bounded candidate plans, review and comparison | Closed task-cell manifests, failure-inclusive outcomes and effort/resource comparisons. Do not create another benchmark database. |
| `app/job_resources.py`, resource probes and `app/host_memory.py` | Listener-bound observations and the existing Windows commit gate | Attested model/configuration context, phase and cleanup evidence where available; no new sampler daemon. |
| Existing SDK/CLI/MCP | Thin validated read/plan/command access | Stable inspection and qualification planning over the same owners. No arbitrary filesystem or install/execution bypass. |

**Why not a central qualification engine?** It would duplicate library status, graph authority, reviews and job admission while creating new opportunities for stale or contradictory state. A qualification view should instead be a projection with source identities and explicit unknowns. Persist actual evidence in its existing owner, not a mutable “qualified=true” spreadsheet that can override it.

## ADR 2: distinguish evidence dimensions, not one promotion boolean

A model may be installed, have a working loader and still be slow, unreliable, unsuitable for a particular control, visually wrong or unaccepted. Conversely, a useful historical image is not a current runtime guarantee.

| Dimension | Example evidence | Invalid inference |
| --- | --- | --- |
| Source specificity | Family card, exact source revision, authored workflow | A matching model hash makes family prose exact-version advice. |
| Artifact identity | Declared manifest hash; separately verified disk bytes | Same filename or file size proves loaded model identity. |
| Mechanical compatibility | Architecture, prediction and node/input contract | An SDXL-compatible adapter necessarily works well on every derivative. |
| Runtime | Exact environment, graph/components, listener epoch and outcome | One successful load establishes cold/warm/switch/cleanup reliability. |
| Task performance | Frozen brief, every candidate, hard checks and independent review | Completed job or benchmark mean is owner acceptance. |
| User acceptance and reuse | Explicit review for a role, accepted canon and downstream lineage | A high critic score or chosen default silently makes the image canon. |
| Intended use | Retained terms/reference provenance and reviewed use context | Byte identity, API flags or an embedding clears all downstream rights. |

Unknown is a value, not a failure to be overwritten with a plausible default. A known failure remains attached to its exact configuration; it is not silently generalized to the whole model family. Recommendations can choose a next experiment but cannot mutate these facts.

The first software slice uses the existing resource-guidance evaluator. Optional `source.scope` distinguishes `family`, `exact_version`, `local_workflow` and `unrecorded`. Specific declarations require a pinned `source.revision` identity. Explanations separately report resource applicability and source scope, using existing UI reasons. Even a declared exact scope is not authenticated merely because it passes schema validation.

## ADR 3: native contracts, not architecture-by-name

Each selected route needs model/encoder/VAE/adapter/control identities, prediction and precision/distillation details, exact graph bytes, custom-node versions, runtime and effective reference transforms. API and human-readable graph twins should remain paired through existing repository validation.

Do not apply SDXL LoRAs or ControlNet weights to Anima, Qwen or FLUX because similar ComfyUI node names exist. A depth image and a depth-conditioning model are different resources. Distinguish raw photograph, rendered depth, corrected skeleton and segmentation mask. In particular, an already-corrected guide must not be run through DWPose again when the contract promises bypass.

The paper's exclusive `native|quantised|distilled` configuration suggestion should become orthogonal attributes or the existing equivalent representation: a quantized Qwen model can simultaneously use a distilled Lightning adapter and a differently quantized encoder. Model-specific parameter names and scheduler semantics are not normalized by guessing.

## ADR 4: immutable canon, explicit role ownership

Keep original source bytes and observations immutable. An owner-selected portrait becomes canon only through explicit Workspace review; each crop, mask, skeleton, embedding, face correction or refined image is a derivative with parent identity and transform provenance. A generated variation does not replace canon automatically. Character sheets should repeatedly anchor to that canon, not use each generated view as the next truth and accumulate drift.

For two-character work, bind separate subject IDs, identity references, left/right placement, contact/action and controlled geometry. One overall similarity score can conceal exchanged identities or the wrong hand making contact. Preserve per-subject take/ignore choices and unresolved occlusion.

Reconcile the paper's `outfit` with the current schema's `costume` explicitly. Keep saved-brief compatibility and revision semantics. A name alias does not authorize changing the source slot, crop or prompt. WD tags, OCR text and VLM captions remain observations with confidence; recovered prompt metadata has a different origin and neither record can overwrite reviewed intent.

## ADR 5: runtime comparison is an operator-created experiment

Keep the current working environment. A Windows ROCm comparator and Linux comparator each need separate fingerprints and identical *intended* task/component sets. The corrected Radeon kernel tuple does not establish wheel availability, compatible custom nodes or performance. Do not assume Windows and Linux share the same package build merely because both list the same PyTorch release.

A meaningful comparison separates cold load, warm inference, model switch, queue wait, analysis, cleanup and restart. Sampling gaps or a changed listener epoch must remain visible. File size does not establish allocation peaks; process RSS does not establish Windows commit headroom; lower VRAM from offload does not establish host safety.

No explicit cold-start experiment follows from a request to unload an active user job. Uncertain dispatch is reconciled through existing durable receipts. A failed optional observer cannot grant recovery authority or relabel an uncertain execution successful.

## ADR 6: workflow-led UX, progressive disclosure and thin agents

Primary choices are creative outcomes, reference roles, desired change and protected content. Show the next actionable blocker and a small set of task-compatible routes. Keep exact model/version, representation, source scope and cost evidence inspectable rather than filling the main page with registry fields.

Use the existing workbench, guide, setup proposal, reference-review and job owners. The adjacent adaptive UX proposals (#539/#549/#551/#556) can test a typed boundary and an isolated frontend island, but this research does not justify a framework rewrite. Preserve offline Python startup and the current user environment; do not make npm/CDN access a normal launch prerequisite. No new skin, image or video asset is needed for this integration.

Agents should inspect capabilities, propose a bounded plan, obtain the existing review/authorization and invoke the same checked commands. They cannot install custom nodes, approve their own imagery, expand an attempt cap, bypass host-memory admission or reinterpret an ambiguous response as a safe retry.

## ADR 7: integrate knowledge without publishing private material

Store this report's title, freeze, page references and artifact digest, plus concise derived decisions and corrections. Keep source character images, original references, embeddings, runtime paths, credentials and owner Workspace data out of the public repository unless separately approved. An experiment manifest can bind opaque local identifiers and hashes without publishing its media.

The report is a frozen source. These documents are the adaptation. Current operational status remains in CURRENT_STATE/STATUS and evidence owners. Do not copy the report's JSON into a second catalogue or maintain another daily status list. Refresh only when a tracked source, component, graph, role binding, runtime, purpose or owner decision changes.
