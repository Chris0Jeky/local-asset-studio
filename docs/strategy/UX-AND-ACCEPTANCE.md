# UX and owner-acceptance strategy

## Why the owner audit matters

Before 14 September, the repository had extensive browser checks and carefully documented surfaces. The owner's first-hand verdict was still that the Studio felt close to unusable for the intended creative work.

That feedback exposed a crucial distinction:

> **Correct, comprehensive and explained does not automatically mean usable.**

The latest UX work corrected several concrete defects, but the larger lesson should remain part of product governance.

## What the use-case matrix proves

[`UX-USE-CASE-MATRIX.md`](../UX-USE-CASE-MATRIX.md) drives ten owner-shaped journeys through real frontend code with synthetic data. It records clicks, view switches, dead ends, unexplained disabled controls and visible instruction load.

The dated fixture run showed examples such as:

- the three-reference route requiring seven clicks and six view switches;
- the guided character-edit path exposing roughly one thousand instruction words across the journey;
- the Workflow Studio builder carrying the highest single-panel reading load;
- Runs & Review being one of the lightest and most successful surfaces;
- successful interface completion not implying a useful generated result.

The matrix is a product instrument, not neural or artistic evidence. It should be kept because it measures failure modes ordinary functional tests miss.

## UX diagnosis

### The product exposed internal abstractions too early

Prompt profiles, recipes, compiler traces, graph nodes and experiment states are useful. They became entry decisions before the user had a clear route to the desired result.

### Explanatory tooling preceded operational tooling

Some surfaces described what should happen but did not perform or propose the obvious next action. The guided-path and Prompt Lab improvements are moving in the correct direction.

### The creative loop was fragmented

Create, Prompt Lab, Guided paths, Asset library, Runs & Review, Bundle Explorer and Workflow Studio each represented part of one task. The user had to know which surface owned the next step.

### Review was underpowered relative to generation

The historical 108-of-111 unreviewed Workspace snapshot is not only a UI defect. It indicates that selection, organisation and continuation are becoming the real bottleneck.

## Recommended interaction model

### 1. Outcome first

The default screen should ask what the user is trying to achieve and accept the brief/references directly. The system proposes a suitable route with measured or unknown cost and explains the decisive reason.

Example:

```text
Change this character image
References: identity + style
Suggested setup: Qwen Atelier 2 references
Measured time on this PC: approximately 10–12 minutes
Known limitation: identity references alone do not preserve art style
[Review setup] [Adjust route]
```

### 2. Controls on demand

Recipe, model, LoRAs, dimensions, scheduler, denoise and native graph details remain available in a clear setup review. The default action should not require understanding all of them.

### 3. Evidence when needed

Exact graph identity, profile trace, hashes, receipts and unsupported adapters belong behind explicit inspection or agent interfaces. They should never disappear, but they should not dominate ordinary creative work.

## Prompt Lab direction

Prompt Lab's useful capabilities are model-aware intent structure, preservation of locked wording, constraint diagnostics and explainable projection.

The long-term default should probably place those capabilities **inside Create**:

- one natural brief;
- references with roles;
- optional “what to avoid” and hard constraints;
- live suggested route and wording;
- explicit reviewed apply;
- an Advanced section exposing profile, compilation and trace.

A separate Prompt Lab can remain an expert/agent workspace, but it should not be a mandatory conceptual hop before generation.

## Recipe and bundle direction

The system already knows enough to propose a route from:

- task type;
- reference count and roles;
- installed models/nodes;
- backend identity;
- measured timing and resource evidence;
- known route quality and limitations.

Therefore, ordinary users should not need to choose `qwen-1ref`, `qwen-2ref` or `qwen-3ref` before attaching sources. Recipe IDs should remain stable execution identities and advanced controls.

The default picker should promote a small owner-recommended shelf, perhaps:

- fast anime character;
- high-quality anime character;
- reference edit;
- multi-reference consistency;
- repair/detail;
- upscale;
- image-to-motion;
- 3D concept.

Everything else remains available under Experimental / All workflows.

## Workspace as a creative inbox

The Asset library should support a clear state flow:

```text
Unreviewed → Keeper / Needs work / Rejected
                    ↓
          Continue / Repair / Variant / Export
```

Automatic grouping by run, recipe, character/canon and study should reduce organisation work without silently deciding quality.

The most important product event is not “job completed.” It is:

> **The owner accepted this asset for a stated role and can continue from it.**

That event should attach the decision, source/setup identity and available next actions.

## Interaction budgets

Budgets are design constraints, not hard universal pass/fail rules.

| Measure | Default target |
| --- | ---: |
| Visible standing instruction on a normal task panel | under 150 words |
| Common route to reviewed generation setup | no more than 5 meaningful interactions after brief/references |
| Three-reference selection | one picker visit, not three modal round trips |
| Disabled primary action | always has an adjacent specific reason and next action |
| Default recipe/model decisions | proposed automatically, reviewable before mutation |
| Navigation after job completion | direct link to review and continuation |
| Owner acceptance state | reachable from the candidate without opening a separate evidence tool |
| Read-only page/navigation | zero generation, install or backend-switch side effects |

When a route necessarily exceeds a budget, the interface should explain why the complexity is intrinsic rather than accidental.

## Owner acceptance protocol

Automated checks cannot close the usability loop. Each significant journey should eventually receive an owner session with:

1. a real task and real private media;
2. no developer narration unless the interface blocks progress;
3. screen/action recording or a concise interaction log;
4. owner verdicts on clarity, effort and result quality;
5. exact blockers and unnecessary steps;
6. an explicit accepted/rejected result state;
7. follow-up issues limited to observed causes.

The owner should be able to answer:

- Did I know what to do next?
- Did the Studio choose or explain a sensible route?
- Could I recover from a wrong turn?
- Was the wait justified and visible?
- Did review lead naturally to repair, reuse or export?
- Would I choose this over direct ComfyUI for the same task next time?

## Acceptance dimensions

Do not collapse these dimensions:

| Dimension | Question |
| --- | --- |
| Task success | Did the intended artifact/action happen? |
| Creative quality | Is the result worth keeping for this role? |
| Fidelity | Were identity, costume, style, geometry or protected pixels retained as required? |
| Efficiency | How much interaction, waiting and cleanup was required? |
| Recoverability | Could wrong turns and uncertain outcomes be handled safely? |
| Reusability | Can the accepted result continue into the next task with lineage? |
| Rights | Are the exact resources and intended use permitted? |

## Highest-value remaining UX work

1. Keep source affordances visible on text-only routes with a direct reference-capable alternative.
2. Explain every disabled Workflow Studio action adjacent to the control.
3. Keep negative/avoid wording visible when a recipe supports it.
4. Allow one picker visit to fill multiple ordered reference roles.
5. Reduce persistent explanation density using local “Why?” disclosures.
6. Bring accepted/reuse actions closer to candidate review.
7. Run issue #313 and let real owner friction determine the next changes.

The target is not a UI with fewer words at any cost. It is a UI in which the visible words directly enable the next decision.