# Product thesis

## One-sentence thesis

**Local Asset Studio is a reliable local creative workstation that coordinates generative models, conventional creative tools, reusable assets and agents around a persistent, reviewable creative process.**

It should not be judged primarily as a prettier ComfyUI picker. Its value is that it knows what is being made, which inputs and revisions are authoritative, what can run on this machine, what changed, what remains uncertain, what the owner accepted and how to continue from that result.

## Primary user

The primary user is the owner of one Windows/Radeon workstation who wants to create and reuse visual assets without surrendering control to a hosted service or learning every model/runtime/node detail before producing useful work.

That user is technically capable and may use ComfyUI, Krita, Blender, Godot, CLI tools and agents directly. The Studio should reduce coordination cost, not conceal useful power or recreate those applications badly.

## Core jobs to be done

1. **Create from intent.** Turn a brief and optional references into a suitable local setup and a reviewed generation request.
2. **Change an existing asset.** Preserve identity, style, geometry or protected pixels as explicitly requested.
3. **Review and select.** Reduce a growing output set into keepers, needs-work items, rejected candidates and accepted sources.
4. **Repair or refine.** Apply the smallest useful intervention while retaining the original and exact change scope.
5. **Continue from accepted work.** Reuse an accepted asset as canon, reference, variation source, animation input or native-tool handoff.
6. **Understand failure.** Know whether a route is blocked, refused, uncertain, technically completed or creatively poor without blind retries.
7. **Coordinate tools and agents.** Let UI, CLI, SDK and MCP operate on the same revisioned state and evidence boundaries.

## The core loop

```text
Intent
  ↓
Reviewed setup
  ↓
Explicit generation or native operation
  ↓
Review and comparison
  ↓
Repair / variation / deterministic finishing
  ↓
Owner acceptance for a stated role
  ↓
Reuse with lineage
```

Every major surface should support a stage of this loop or an explicit escape hatch from it. A feature that cannot name its place in the loop needs a strong reason to exist.

## Default experience

The default product should organise entry points by outcome rather than model family:

- Create a character or illustration;
- Change an existing image;
- Repair or refine an asset;
- Work on one figure or build a sprite sequence;
- Animate a finished image;
- Build a prop or 3D draft;
- Review and continue existing work.

The Studio may select or propose a recipe because it already knows the reference count, roles, installed resources, measured timing and route evidence. Recipe IDs, node classes and model dialects remain inspectable implementation detail, not obligatory first decisions.

The recommended interaction hierarchy is:

1. **Outcome layer** — brief, references, expected result, approximate cost, explicit action;
2. **Control layer** — recipe, model, settings, stages, alternatives and resource implications;
3. **Evidence layer** — exact graphs, hashes, receipts, schema identities, raw traces and recovery state.

Ordinary work should succeed in the first layer. Advanced users and agents must be able to descend without information loss.

## Product identity

### It is

- local-first and loopback-only by default;
- a controller over one trusted execution owner;
- an asset and evidence workspace;
- a task-oriented route selector;
- a review and continuation environment;
- a coordinator for ComfyUI, Krita, Blender, Godot and later specialised tools;
- an agent-operable system with the same commands people use.

### It is not

- a hosted creative SaaS;
- an autonomous infinite reroll engine;
- a universal node/widget implementation before installed compatibility is proven;
- a replacement painting application, 3D editor, NLE or DAW;
- a generic model manager that treats downloaded files as compatible;
- a guarantee that successful inference produces acceptable art;
- a licensing authority;
- a reason to mutate a working shared runtime automatically.

## First-class product concepts

The current Workspace asset is a strong foundation, but the product is increasingly expressing richer concepts indirectly. Over time, the following should become explicit where evidence justifies them:

- **Asset** — immutable source or derived media plus lineage;
- **Character / canon revision** — approved identity and costume state;
- **Instance** — one occurrence of a canon in a panel, pose or scene;
- **Setup** — reviewed recipe/model/settings/reference state;
- **Project / study** — bounded multi-stage or comparative work;
- **Operation** — revisioned command with durable evidence;
- **Candidate** — completed or failed output under one attempt identity;
- **Acceptance** — owner decision for a stated purpose, separate from execution and rights;
- **Export** — derivative packaged for a named native tool or engine contract.

Do not introduce a generic ontology merely because these nouns exist. Promote one only when multiple shipped flows need its identity and lifecycle.

## Differentiation

Local Asset Studio's strongest differentiators are not the number of models or controls. They are:

1. **Evidence-aware execution.** Submitted, uncertain, completed, inspected, accepted and rights-reviewed remain distinct.
2. **Local runtime safety.** Isolated backends and explicit switching protect a working AMD environment.
3. **Durable recovery.** Ambiguous responses retain identities instead of generating duplicates.
4. **Cross-tool continuity.** Assets can move to native tools with source and revision guards.
5. **Human/agent parity.** Agents propose and operate through the same bounded commands rather than hidden shell state.
6. **Persistent creative lineage.** Accepted work can be reused with its source, setup and review context intact.

These advantages compound only when the ordinary creative loop is usable. Reliability around a workflow the owner avoids is not sufficient product value.

## Product principles

1. **Optimise accepted results, not completed jobs.**
2. **Make the next useful action obvious.**
3. **Default to task language; expose implementation language on demand.**
4. **Preserve originals and branch explicitly.**
5. **Never infer acceptance, rights or remote outcome from technical success.**
6. **Prefer one trusted owner for queues, persistence and runtime state.**
7. **Use deterministic tools for deterministic work.**
8. **Explain uncertainty and unsupported capability rather than guessing.**
9. **Measure interaction cost and cleanup effort, not only inference speed.**
10. **Expand only after a smaller vertical slice produces a useful accepted asset.**

## Near-term thesis test

Issue #313 is the immediate product thesis test. If the current Studio can produce, review, repair, accept and reuse a compact four-artifact character pack with bounded effort, the architecture is beginning to pay for itself. If it cannot, the failures should directly determine the next small product slices.

The test should not be rescued by adding a new subsystem. It should reveal whether the existing control plane actually reduces the work of making accepted assets.