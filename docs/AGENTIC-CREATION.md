# Agentic creation programme: engineering decisions and opportunity map

## What changed after reading the reports and the actual repository

The reports are useful architectural research, but their description of LAS is incomplete. The repository already has an optional MCP facade (`studio_workflow/mcp_server.py`), provider-neutral workflow client/bridge, route qualification, stage resource admission, resource probes/receipts, provenance, and bounded native authored-prop execution. Adding a new generic agent framework, another MCP server or a competing GPU queue would fragment durable state.

This pass therefore implements an **offline research/evidence layer** and an experimental **read-only Blender observation script**, with a specific next native integration plan. It does not install a persistent worker or expose arbitrary code execution. Full private reports are preserved separately; public LAS contains reusable mechanics and generalized decisions.

### Evidence classes, not one trust score

| Class | What it establishes | What it cannot establish |
|---|---|---|
| Supplied report | What the research concluded and cited | Truth, installed compatibility or authority to execute |
| Primary document observed | What an owner documents at the observation date | Successful operation on this workstation |
| Repository source inspected | Existing contracts and integration owners | Live daemon state, current driver or installed model |
| Offline test | Behaviour of code under stated fixtures/environment | Real Blender/GPU/driver behaviour or artwork quality |
| Native receipt | A specific pinned invocation, output and measurement | Universal support, artistic approval or reuse rights |
| Human acceptance | The owner's approval of a specified output/scope | Automatic acceptance of future derivatives |

Imported references remain attached to the source assertion. Disagreements are recorded, not averaged away. A newer source does not retroactively alter the original report.

### Reconciliation register

| Question | Conflict or missing context | Decision |
|---|---|---|
| Is resource scheduling missing? | Reports propose a new GPU lease. LAS already has resource admission/observations/receipts. | Reuse that owner. **Native Blender is not automatically covered by the current Comfy graph pre-submit path**; a native identity/measurement adapter is still needed. Never fabricate a Comfy graph to get admission. |
| Is MCP missing? | Reports discuss adding a facade as though none exists. | Extend the existing `AgentBridge` only after native operations have durable owner contracts. MCP remains transport, not isolation. |
| Should more Blender versions be installed? | One report proposes additional maintained lanes; another preserves installed versions. | Preserve the explicitly installed 4.5.13 comparison lane and pinned alpha. Additional lanes need a concrete experiment and separate qualification. |
| ROCm.AI / AMD Skills identity | One report verifies them; the other could not. | AMD's current [ROCm.AI owner page](https://www.amd.com/en/products/software/rocm/rocm-ai.html) describes both. That resolves product identity, not installation, driver changes or model compatibility. |
| Persistent worker first? | Reports alternately prioritize a worker, facade and sentinel. | Evidence first. Measure useful end-to-end overhead and A/B/A state recovery before adopting persistence. |
| Autonomous corrective/face optimization? | Research proposes a constrained solver. A project's artistic policy can prohibit score-led sculpting. | Such a project policy wins. Keep the solver as an owned synthetic-rig study, not a private-character activation. |
| Warm-up count? | Reports suggest different generic numbers. | Pre-register per campaign; the proposed benchmark uses three warm-ups/five measurements and preserves cold-start evidence separately. These are proposed experiment settings, not measured results. |

## Architecture: preserve durable owners

```text
Agent / human
  |
  +-- Read supplied research --> private lossless archive + contradictory-claim register
  |
  +-- Offline dcc_lab --> validated experiment intent / pinned read-only probe intent
  |                       (implemented; no submission or execution)
  |
  +-- Existing workflow client / AgentBridge / optional stdio MCP
          |
          +-- Existing jobs, request identities, provenance and recovery
          +-- Existing resource admission + telemetry + retained receipts
          |      [native identity/measurement adapter still to implement]
          +-- Bounded native owner
                 +-- fresh Blender process, fixed script, disabled autoexec
                 +-- read-only scene observation [script exists; native test pending]
                 +-- controlled render/export/reimport [next slice]
                 +-- optional persistent worker [only after latency/recovery study]

Private workspace: source (immutable) -> tagged copy -> evidence/derivative artifacts
                                           |
                             structure + controlled views + temporal checks
                                           |
                                diagnostics -> human artistic judgment
```

The existing native authored-prop operation is a useful owned fixture and integration example, not a universal character exporter. Its current inspection renders are source views; its metadata verifies GLB reimport structure, **not a second set of reimported renders**. Do not retrofit a parity claim onto those historical outputs. The new comparator consumes independently supplied evidence; it does not yet produce that missing second capture.

### Execution and recovery contract for the next adapter

The durable job identity must bind the asset copy, actual executable, probe/capture script, export profile, camera/light/pose contract and resource profile. Hash the script itself, not just its filename or Blender version. Recheck the pins immediately before execution. Persist the intent before launching. Retain stdout/stderr, return code, timeout/crash status, partial outputs and admission/measurement receipts.

Do not reuse a failed/uncertain attempt directory. Recovery reads retained state; it never launches again because a UI request or MCP call timed out. Extend the current owner instead of building a second retry loop. A process boundary helps terminate work but is not an OS sandbox for untrusted native files or generated Python.

GPU resource exclusivity must cover the actual native operation and its lifetime before it is claimed. The existing graph-stage mechanism is a foundation, not proof that Blender, every local VLM and all external processes are already coordinated. Unknown current headroom must remain unknown, not inferred from total VRAM.

## What the current code does

`research_intake` preserves exact report bytes and Markdown, derives link-bearing reading copies and indexes, verifies hashes and derivation, retains unresolved references, and never fetches links. Archive creation is exclusive; `manifest.json` is written last as the completion marker.

`dcc_evidence` compares recorded scene content and controlled PNGs. It detects same-count connectivity changes, coordinate/UV/weight/morph differences when observed by the probe, missing objects and known findings. It refuses changed artifact hashes, unsafe member paths, symlinks and inconsistent image sizes. Missing required/hold-out captures are incomplete; different camera/settings contracts are incomparable. Candidate-controlled tolerances or flattering camera realignment are not introduced.

`blender_scene_probe` stays stdlib-only: the Blender Python interpreter never imports LAS, Torch, or ComfyUI. It runs through the one Blender Lab entry point, `blender_lab_bpy.py scene-v1` (see `docs/BLENDER-LAB.md`, "Which tool for what"). It reads layered action channelbags where available, falls back to a legacy action collection when actually present, and refuses an unknown animation representation. It never calls `fcurve_ensure_for_datablock`, which is an authoring operation, not a read-only lookup.

The probe's semantic snapshot is deliberately partial. Base meshes are not evaluated deformations. Shader/socket inspection is not arbitrary graph translation. Image existence is not texture fidelity. Rest bones are not skinning acceptance. This avoids claiming that a detailed JSON file has solved visual or temporal QA.

## Fine-grained agent operations: proposed contracts

Build commands around constrained intent, not arbitrary generated code:

- **2D:** edit an approved mask/layer, preserve protected pixels and layer topology, retain the native editable source, reopen and compare. Treat SVG parameters and text layout as structured edits, not raster repainting.
- **3D:** allowlisted object/mesh-region IDs, expected semantic prehash, fixed topology policy, bounded displacement/transform/material fields, and explicit output copy. No retopology or remeshing hidden inside an aesthetic request.
- **Animation:** named pose/curve ranges, allowed channels, contact targets, derivative/velocity bounds, held-out stress poses and an untouched rest pose.
- **Materials:** separate authoring graph from portable target profile; record each baked/approximated/omitted feature. Preserve UV coverage and seam evidence.

These are implementation targets, not exposed tools today. Each needs a prepare/run/recover contract and regression tests before appearing in MCP. Scene inspection should precede every version-sensitive edit; the live API and actual object IDs are facts, model recollection is not.

### Multi-agent division without a swarm dependency

A planner chooses the objective and immutable constraints; a read-only researcher resolves source/version questions; one operator owns the asset copy and native job; a structural reviewer checks manifests; an image/temporal critic gives scoped observations; the human decides identity, form and artistic acceptance. All roles communicate through the same durable job/artifact IDs. More agent instances do not create more writing authority or independent evidence. No particular subscription, API entitlement or local model availability is assumed.

## Opportunity map and priority

The machine-readable map includes 24 entries. The near-term value is concentrated in reusable mechanisms:

| Priority | Direction | Useful result | Main limitation |
|---|---|---|---|
| 1 | Semantic/visual evidence and fault corpus | Prevent silent regressions across every workflow | Needs native capture and calibrated target-specific mapping |
| 2 | Protected-region 2D edits, layer reopen and UV bake closure | Editable, portable output rather than screenshots | Mask/coverage quality and native reopening cannot be replaced by similarity scores |
| 3 | Procedural props, environments, LOD and material libraries | Repeatable asset factories and known ground truth | Hero aesthetics still require authoring decisions |
| 4 | Rig/morph, retargeting, contact and temporal QA | Useful animation derivatives with measurable defects | Feasible poses, rest-frame conventions and target rig semantics matter |
| 5 | Camera planning, product variants, storyboards, scientific visuals | Cheap controlled presentation and labeled data | Evidence must retain units, data sources and camera intent |
| 6 | Hair/cloth derivatives and companion acting | Editable guides/cards, expressions, gestures and playback | Engine target, performance and artistic form must be decided |
| Research | Critic calibration, counterfactuals, neural reference stages and inverse fitting | New useful methods tested against simple controls | GPU/custom-kernel availability, poor calibration and metric gaming |
| Not a baseline | Large local 3D-model training or assumed CUDA portability | No near-term advantage established here | Resource/ecosystem cost; separate external route required |

Blender's role differs per opportunity: author for procedural meshes; renderer/label generator for synthetic data; validator for exports; importer/reference stage for splats or reconstruction. Do not call importing another system's result native generation. CAD/printing require dimensional and fabrication-specific checks; robotics/digital twins require validated simulator/sensor semantics outside Blender. A paused 2D embodiment route remains a separate project decision.

## Environments and resource baseline

The reported workstation is Windows 11, i5-13600K, 32 GB RAM and RX 9070 XT 16 GB. These are owner-provided context, not measurements made by this pass. Preserve the existing Blender 4.5.13/5.4-alpha lanes and keep Blender Python 3.13.13 separate from the reported Python 3.12/PyTorch 2.9.1+ROCm 7.2.1 ComfyUI environment.

No upgrade is prescribed. Native Windows, WSL/Linux, NVIDIA and cloud are distinct execution lanes. A model's PyTorch code does not prove its custom CUDA extensions work on AMD. No model/runtime in the research catalogue is implicitly installed. Exact drivers, model files, custom-node versions, disk headroom and current queue occupancy must be observed at execution time.

## Phased delivery

**First 48 hours of local work:** verify the private archives; qualify the read-only probe on an owned prop; bind one actual controlled capture to a source copy; measure an unchanged rerun; seed omitted-part/texture/material failures. The human selects canonical/hold-out views and distinguishes acceptable artistic changes from defects. No source migration or character redesign is required.

**Two-week target:** integrate admitted native probe/capture jobs with existing durable owners and MCP, complete source/export/reimport evidence for one owned fixture, close one protected-region 2D or projection-to-UV problem, add stress-pose/temporal observations, and run one workload-specific AMD matrix. Decide persistent-worker value from measured overhead and recovery, not novelty. These are proposed milestones, not scheduled background work.

**Longer backlog:** target shader profiles, hair derivatives, contact/retargeting repair, expression/viseme/gesture libraries, synthetic datasets, scientific/printability tools, held-out critic calibration, hybrid reference representations, and explicitly permitted synthetic inverse-fit studies. Each survives only if it beats an ordinary editable baseline on usefulness and intervention cost.

## Next-agent brief

Read the programme, verification record, current repository state and the private workspace's current resume instructions. Do not treat this research snapshot as newer authority than a subsequent owner edit. Run the five focused test files and offline validation. Begin with the native parity plan below, not a new agent stack.

Preserve originals and installations. Recheck source/tool hashes. Add real camera/light/settings receipts before comparing renders. Reuse current jobs, resource observations, recovery and provenance. Do not register private derivatives through a public export route. Report failures and missing telemetry. Keep human art acceptance, engine choice, installation completion and eventual source-distribution decisions open.

## Source notes

The supplied reports and their original citation mappings are retained in the private archive. Primary references used for the implementation boundary include [Blender command-line controls](https://docs.blender.org/manual/en/5.4/advanced/command_line/arguments.html), [mesh data layout](https://docs.blender.org/api/5.4/bpy.types.Mesh.html), [layered action channelbags](https://docs.blender.org/api/main/bpy.types.ActionKeyframeStrip.html) and [AMD's ROCm.AI page](https://www.amd.com/en/products/software/rocm/rocm-ai.html). Documentation presence is not an exact-build execution test. Direct document fetches were not consistently available; indexed primary-document text was also used. No new version-support matrix or universal performance claim is asserted by this implementation.
