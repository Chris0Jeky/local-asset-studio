# Repair Studio

Architecture and delivery programme for extracting, repairing and finishing imperfect artwork in Local Asset Studio. Programme: [#243](https://github.com/Chris0Jeky/local-asset-studio/issues/243). Research checked 14 September 2026; the initial source baseline is recorded in [RECONCILIATION.md](RECONCILIATION.md). Consult live issues and each implementation runbook for later delivered scope.

## The outcome

Select an image or sheet, identify the subject and the problem, see exactly what may change, compare a bounded set of repairs, keep the useful correction and export a higher-resolution asset. The Studio carries references, masks, coordinates, decisions and recoverable job identities between these steps. A failed model attempt must leave the original intact and explain the next useful intervention.

This is not a promise that a generative model can infer every intended limb, hidden garment or original pixel. Reliability comes from strict editing boundaries, evidence-aware decisions, controlled reconstruction, reversible native work and measured task-specific model performance. The system may confidently preserve work while honestly asking for a pose decision or native correction.

## Working offline tools

| Task | Tool and contract |
|---|---|
| Retain the original and normalize PNG orientation/alpha explicitly | [Source intake](SOURCE-INTAKE.md) |
| Propose and preview panel boundaries, then extract exact source crops | [Panel intake](PANEL-INTAKE.md) |
| Prepare scaled working pixels and compose a separately supplied candidate through effective coverage | [Pixel transforms](PIXEL-TRANSFORMS.md) |
| Inspect effective scope, retain the mask identity and export a separate inverse-alpha mask carrier | [Scope review](SCOPE-REVIEW.md) |

These tools perform actual CPU image operations and reconstructive checks, not model generation. A valid packet is not accepted artwork, proven candidate alignment or a qualified native model workflow. The static scope-review page is not the interactive Studio mask editor.

For an original synthetic end-to-end example on a checkout containing these tools:

```console
python scripts/repair_scope_demo.py --out experiments/runs/scope-demo-001
```

Choose a new directory. The demo retains the source, context, supplied synthetic candidate, protected composite and review; open `scope-review/scope-review.html` inside that output. No model, ComfyUI connection or user artwork is required.

## Architecture foundation (#264)

The original architecture delivery includes preservation, instance, mask and geometry contracts; primary-source research; adapter and UX/agent designs; decisions with alternatives; a release/evaluation plan; implementation issues; and a tested **offline proposal checker** with synthetic examples. The proposal checker checks declarations only; it neither inspects image pixels nor runs the pipeline. The working tools above are separate, subsequent implementations.

Existing protected composition, the Qwen character-edit client, shared campaign registration and native Krita revision guards are reused. Their existence is not evidence of high-yield neural repair. Installation, successful execution, image acceptance and usage clearance remain separate. No planning document or synthetic test extends an old study allowance or changes a HUMAN_TODO decision.

## Read by task

| Need | Start here |
|---|---|
| Understand the system and why it is structured this way | [Architecture](ARCHITECTURE.md), [decisions](DECISIONS.md) |
| Implement source, masks, references and coordinate handling | [Contracts](CONTRACTS.md) |
| Choose a technique without confusing capability and evidence | [Research](RESEARCH.md), [adapter qualification](ADAPTERS.md) |
| Build the guided and headless experience | [UX and agents](UX-AND-AGENTS.md) |
| Prove safe mechanics and useful output | [Reliability](RELIABILITY.md), [evaluation](EVALUATION.md) |
| Pick the next reviewable implementation slice | [Implementation plan](IMPLEMENTATION-PLAN.md) |
| Run the declaration scaffold and understand its limits | [Runbook](RUNBOOK.md) |

## Delivery order and next gate

R0 contracts → R1 one accepted local repair → R2 difficult crops/occlusion → R3 sheets and contacts → R4 bounded guided automation → R5 qualified finishing and delivery. These are evidence-gated milestones, not calendar promises. R1 must produce useful artwork before broad automation or another model shelf is built.

Source/panel intake and scaled composition now have offline implementations. #244 still includes browser/Workspace integration and a privately reviewed real sheet. #245 still needs native mask-consumer/registration evidence and a real accepted repair; the scope review makes its effective-mask decision inspectable but does not complete those requirements.

The next useful outcome is **one qualified existing-model repair route (#248) connected to the guided journey (#251)**, carrying the actual source, reviewed scope and existing campaign identity through to a retained, reviewed result. #257 supplies evidence throughout. #246 isolation and #249 coupled contacts follow; #250 adds bounded strategy changes; #256 finishes and recomposes accepted masters. Existing #66/#72 retain critique and evaluation ownership.
