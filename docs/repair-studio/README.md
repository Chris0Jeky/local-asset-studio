# Repair Studio

Architecture and delivery programme for extracting, repairing and finishing imperfect artwork in Local Asset Studio. Programme: [#243](https://github.com/Chris0Jeky/local-asset-studio/issues/243). Research checked 14 September 2026; source baseline and concurrent work are recorded in [RECONCILIATION.md](RECONCILIATION.md).

## The outcome

Select an image or sheet, identify the subject and the problem, see exactly what may change, compare a bounded set of repairs, keep the useful correction and export a higher-resolution asset. The Studio carries references, masks, coordinates, decisions and recoverable job identities between these steps. A failed model attempt must leave the original intact and explain the next useful intervention.

This is not a promise that a generative model can infer every intended limb, hidden garment or original pixel. Reliability comes from strict editing boundaries, evidence-aware decisions, controlled reconstruction, reversible native work and measured task-specific model performance. The system may confidently preserve work while honestly asking for a pose decision or native correction.

## What this PR delivers

A reconciled architecture; explicit preservation, instance, mask and geometry contracts; primary-source technique research; adapter and UX/agent designs; decisions with alternatives; a release/evaluation plan; nine scoped implementation issues; and a tested **offline proposal checker** with synthetic examples. The checker accounts for declared crop/scale/padding and rejects contradictory declarations. It neither inspects images nor runs the pipeline.

Existing protected composition, the Qwen character-edit client, shared campaign registration and native Krita revision guards are reused. Their existence is not evidence of high-yield neural repair. No model, image or application binary is added, no runtime is changed and no previous study allowance or HUMAN_TODO decision is modified.

## Read by task

| Need | Start here |
|---|---|
| Understand the system and why it is structured this way | [Architecture](ARCHITECTURE.md), [decisions](DECISIONS.md) |
| Implement source, masks, references and coordinate handling | [Contracts](CONTRACTS.md) |
| Choose a technique without confusing capability and evidence | [Research](RESEARCH.md), [adapter qualification](ADAPTERS.md) |
| Build the guided and headless experience | [UX and agents](UX-AND-AGENTS.md) |
| Prove safe mechanics and useful output | [Reliability](RELIABILITY.md), [evaluation](EVALUATION.md) |
| Pick the next reviewable implementation slice | [Implementation plan](IMPLEMENTATION-PLAN.md) |
| Run the scaffold and understand its limits | [Runbook](RUNBOOK.md) |
| Prepare scaled pixels and compose a supplied repair offline | [Pixel transforms](PIXEL-TRANSFORMS.md) |

## Delivery order

R0 contracts → R1 one accepted local repair → R2 difficult crops/occlusion → R3 sheets and contacts → R4 bounded guided automation → R5 qualified finishing and delivery. These are evidence-gated milestones, not calendar promises. R1 must produce useful artwork before broad automation or another model shelf is built.

The shortest path is #244 source intake, #245 crop/write transforms, #248 one existing-model adapter and #251 a thin guided repair journey, with #257 tests throughout. #246 isolation and #249 coupled contacts follow; #250 adds bounded strategy changes; #256 finishes and recomposes accepted masters. Existing #66/#72 retain critique and evaluation ownership.

The recommended next PR is the **normalized source and exact crop contract** in #244, not an autonomous multi-agent repair loop.
