# Architecture decisions

Decisions for #243, 14 September 2026. These select an implementation direction; they do not mark future integrations or neural quality as verified. Sources and current code are recorded separately.

## ADR-01 — A task extension, not a second Studio

**Decision:** reuse Workspace, Production, Review Desk, existing character-edit clients and native adapters. Add task-specific contracts and adapters at their existing seams.

**Alternatives:** a monolithic new Comfy graph; an independent Python orchestrator; a multi-agent service with its own database. A graph is useful inside one candidate operation but does not own user revisions or uncertain remote effects. A second service duplicates budgets, recovery and reference authority. More agents add opinions, not guarantees.

**Consequence:** integration is initially narrower and depends on existing owners. The benefit is one visible job/revision/budget history across manual and automated actions.

## ADR-02 — Separate exact repair from remaster and reconstruction

**Decision:** preservation mode is explicit and versioned. Localized edits protect normalized source pixels; global resizing uses a derivative contract; missing geometry is a reconstruction decision.

**Rejected:** one Improve button whose hidden pipeline changes pose, face, framing and texture together. This prevents meaningful review and creates impossible promises.

**Consequence:** some changes require a reviewed branch. The UI explains the conflict rather than silently weakening constraints.

## ADR-03 — Model access is wider than write permission

**Decision:** independent context, subject matte, sampler mask, final write coverage and protection. The authoritative compositor checks effective support after transforms/feathering.

**Rejected:** use a bbox as a matte; assume alpha always means edit; save the full decoded candidate; trust a keep-everything-else prompt.

**Consequence:** more spatial metadata, but useful context can be retained without allowing collateral writes. Conditioning contamination still needs separate review.

## ADR-04 — Explicit, testable crop geometry

**Decision:** record actual rounded sizes and rational pixel-centre maps; qualify model preprocessing with synthetic fiducials and real outputs. Reject undeclared resizing or registration mismatch.

**Rejected:** resize every candidate to fit after generation, or assume all same-sized inputs share framing. Such fixes can hide a shifted limb and invalidate protection masks.

**Consequence:** some native routes remain unsupported until an adapter proves its geometry. Coordinate invertibility is not lossless raster reconstruction.

## ADR-05 — Instance and contact scopes, not a global character prompt

**Decision:** separate canon, costume and occurrence. Use per-instance references and local contact regions; choose joint versus sequential repair explicitly.

**Rejected:** one shared reference pile, arbitrary collage to fit reference limits, or global depth ordering for every crossed limb.

**Consequence:** repeated sheets are easier to process independently, while interacting subjects get deliberate coupled work. More than three semantic reference roles does not imply the current Qwen bridge accepts them.

## ADR-06 — Deterministic policy before learned automation

**Decision:** begin with a small ordered strategy policy and explicit failure hypotheses. Evaluate optional VLM proposals through #35/#66; never allow a model to approve its own repair.

**Rejected:** repeatedly increase denoise/steps until a critic likes the image, or train a routing policy before a useful baseline exists.

**Consequence:** understandable decisions and fewer hidden costs. Add learned ranking only after task-specific accepted-effort data and holdout tests justify it.

## ADR-07 — Reuse native creative tools

**Decision:** Krita supplies brush/layer/selection work; Blender may supply an authored geometry proxy. Keep proposed result layers reversible and source-revision-bound.

**Rejected:** rebuild a painting app or expose arbitrary shell/eval as the default agent interface.

**Consequence:** native integration needs real application evidence and supported-format limits. Existing flat RGBA8 proofs do not certify every Krita layer/group/profile.

## ADR-08 — Capability evidence outranks model popularity

**Decision:** qualify exact model/encoder/VAE/patch/node/runtime bundles per task. Start with installed routes. Current settings, native/full versus accelerated variants and AMD feasibility are separate observations.

**Rejected:** rank repair quality from model parameter count, a polished gallery or a single successful detector run; transfer SD1.5 geometry weights to SDXL; assume a PNG's generating family restricts every repair model.

**Consequence:** a small reliable portfolio before expansion. Source/terms/availability records remain in the existing model library, not a new registry in this programme.

## ADR-09 — Conservative uncertainty and shared allowance

**Decision:** use existing durable intents and campaign roots. Unknown execution cannot create a retry entitlement. Add per-case repair allocation within the current owner, and expose finite auxiliary analysis budgets.

**Rejected:** exactly-once claims over ordinary Comfy HTTP; a separate retry daemon; treating timeout as cancellation; creating a fresh campaign to recover an old unknown job.

**Consequence:** an ambiguous run may need an operator decision. Its original artifacts and identity remain available. Availability never takes priority over silently duplicating expensive work.

## ADR-10 — Mechanical proof and art evidence are separate

**Decision:** combine deterministic invariants, real adapter/native/browser tests and human-reviewed defect outcomes. Report by class with denominators, failure/abstention rates and total effort.

**Rejected:** unit-test counts as proof of anatomy, aesthetics as a substitute for contact correctness, paired ground-truth metrics on images with no unique original, or auto-promotion from one critic score.

**Consequence:** release gates are task-specific. A useful experimental route can remain accessible with clear limits while a qualified route earns a stronger recommendation.

## ADR-11 — Incremental delivery before framework expansion

**Decision:** the first live milestone is one successful local repair, with no automatic segmentation required. This PR ships an offline proposal checker rather than speculative production endpoints or placeholder model calls.

**Rejected:** wiring an unqualified giant graph into the UI merely to claim end-to-end support; implementing an entire scheduler before the first candidate is useful.

**Consequence:** explicit scaffolding boundaries, smaller reviewable PRs and a practical way to discover the actual quality bottleneck before building around it.
