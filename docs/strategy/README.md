# Strategic consolidation bundle — 14 September 2026

This directory consolidates the product, engineering, UX and delivery conclusions that emerge from the repository's current implementation, evidence ledger, owner feedback and recent development history.

It is a **decision aid**, not a replacement for runtime truth. Exact executed facts remain in [`CURRENT_STATE.md`](../../CURRENT_STATE.md), current goal status remains in [`STATUS.md`](../STATUS.md), and human creative decisions remain in [`HUMAN_TODO.md`](../../HUMAN_TODO.md).


## 18 September research integration

The [anime and multi-reference qualification integration](anime-qualification/README.md) adapts the
owner-supplied 15 September report to a later repository checkpoint under #552. It adds a page-addressed
knowledge crosswalk, role/configuration portfolio, architecture decisions, finite testing protocol, source
corrections and existing-issue implementation map. It preserves #313 and the historical snapshot below;
research priority is not model promotion or creative acceptance.

## Snapshot boundary

This assessment was reconciled against `main` at commit `368886191434433eb5205d54688ce0093a4adb7f` on 14 September 2026. At that checkpoint the repository had no open pull requests, so this bundle is not written against an unresolved implementation stack. Later changes must be evaluated separately.

Historical measurements cited here come from the dated assessment, owner UX audit and use-case matrix. They remain historical evidence unless remeasured; they are not silently promoted into current live facts.

## Executive judgement

Local Asset Studio has become substantially more than a simplified ComfyUI front end. It is an emerging **local creative control plane and creative workstation** that coordinates:

- model and runtime selection;
- reviewed workflow setup;
- bounded execution and recovery;
- asset lineage, review and reuse;
- native creative tools;
- agent, CLI, SDK and MCP access;
- evidence about what ran, what changed and what was actually accepted.

The project is strongest where most generative tooling is weakest: provenance, failure semantics, local ownership, recovery, model isolation and explicit separation between execution, artistic acceptance and usage rights.

The central risk is the inverse: engineering sophistication is ahead of the ordinary creative experience. The next phase should therefore be **convergence**, not another broad capability expansion.

The recommended core loop is:

> **Intent → reviewed setup → generate → review → repair or vary → accept → reuse with lineage.**

The project should prove that loop repeatedly before treating voice, music, NLE, broader autonomous critique or additional model families as mainline priorities.

## Reading order

| Document | Purpose |
| --- | --- |
| [PRODUCT-THESIS.md](PRODUCT-THESIS.md) | What the product is, who it serves and the experience it should optimise |
| [SYSTEM-ASSESSMENT.md](SYSTEM-ASSESSMENT.md) | Current strengths, liabilities, architecture and maturity judgement |
| [UX-AND-ACCEPTANCE.md](UX-AND-ACCEPTANCE.md) | What the use-case evidence means and how owner acceptance should drive design |
| [CONVERGENCE-PROGRAMME.md](CONVERGENCE-PROGRAMME.md) | Recommended delivery order, WIP policy and stop conditions |
| [ENGINEERING-INTELLIGENCE.md](ENGINEERING-INTELLIGENCE.md) | Reusable architectural patterns emerging from the implementation |
| [METRICS-AND-GATES.md](METRICS-AND-GATES.md) | North-star metrics, evidence states and release gates |
| [OPPORTUNITY-REGISTER.md](OPPORTUNITY-REGISTER.md) | Prioritised ideas mapped to existing issues and proof obligations |
| [DECISIONS-AND-NON-GOALS.md](DECISIONS-AND-NON-GOALS.md) | Decisions to retain, changes to make and work deliberately deferred |

## Immediate recommendation

1. Use issue #313 as the convergence gate and produce a four-artifact accepted character pack with current capabilities.
2. Complete the highest-value remaining UX friction exposed by the use-case matrix rather than adding another explanatory surface.
3. Implement the addressable-figure primitive in #252 because it unlocks sheet → figure → repair → reuse without a new subsystem.
4. Prioritise resource admission and validation consistency through #178, #77, #89 and #97.
5. Widen authored-graph execution only through the narrow registered-template boundary in #122.
6. Require one real owner-accepted Repair Studio R1 result before expanding repair automation.
7. Apply the operating model in #315 so high agent throughput does not recreate large PR stacks and status drift.
8. Extract shared revision/receipt infrastructure only after proving the common invariants in #314.

## Evidence base

This bundle synthesises, rather than replaces:

- [`STUDIO-REVIEW-2026-09-13.md`](../STUDIO-REVIEW-2026-09-13.md) — broad correctness and capability assessment;
- [`UX-AUDIT-2026-09-14.md`](../UX-AUDIT-2026-09-14.md) — the owner's first-hand usability verdict;
- [`UX-USE-CASE-MATRIX.md`](../UX-USE-CASE-MATRIX.md) — measured interface journeys;
- [`STATUS.md`](../STATUS.md) — goal-by-goal current-state view;
- [`RESOURCE-EFFICIENCY.md`](../RESOURCE-EFFICIENCY.md) and [`performance/`](../performance/README.md) — resource strategy;
- [`workflow-studio/`](../workflow-studio/README.md), [`repair-studio/`](../repair-studio/README.md), [`character-consistency/`](../character-consistency/README.md), [`bundle-studio/`](../bundle-studio/README.md), [`prompt-studio/`](../prompt-studio/README.md) and [`av-studio/`](../av-studio/README.md) — programme-specific architecture;
- recent PRs and issues, especially #97, #118–#123, #172–#178, #232, #243–#257 and #278.

## Newly seeded cross-cutting owners

The existing product epics remain authoritative. This consolidation adds only three owners for gaps that cut across those epics:

- **#313 — accepted-asset convergence milestone**;
- **#314 — shared revisioned-command and durable-receipt toolkit**;
- **#315 — issue taxonomy, WIP limits and generated repository state**.

None of these issues closes or supersedes the feature programmes they coordinate.

## How to use this bundle

Before opening a major new issue or programme, check three questions:

1. Does the proposal improve the accepted-asset loop, reduce a measured failure, or unlock a currently blocked next step?
2. Does an existing issue already own the underlying capability?
3. What finite proof would justify promotion, and what should stop the work?

If the answer is primarily “more models”, “more controls”, “more test count” or “more documentation” without a concrete accepted outcome, the work should normally remain parked.

## Update policy

Update this bundle when the product thesis, delivery sequence or architectural decisions change. Do not edit it for every PR. Stable measurements should eventually be generated through #315; subjective judgements and owner acceptance remain authored prose.