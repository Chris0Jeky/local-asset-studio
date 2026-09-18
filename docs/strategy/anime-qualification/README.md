# Anime and multi-reference research integration

**Integration date:** 18 September 2026. **Owner:** #552, under the accepted-asset convergence issue #313 and anime/fantasy atelier #14.

**Basis:** the owner's 26-page *Anime generation and multi-reference editing qualification for local-asset-studio*, frozen 15 September. This is an adaptation, not a claim that the paper's recommendations have executed. Its repository checkpoint was `b29205cfc95ca4e64d72ae38d53df30c83968997`; this integration inspected `main` at `6cdf6ab09683b37f55e1b55af582e4e28eac8100`.

## Direction

Build a studio that turns an ordinary creative intention and a few references into an **accepted, reusable asset with understandable effort and preserved lineage**. The first proof remains one original fantasy-character pack: portrait, full body, expression/pose variation and a repaired/refined derivative. At least one accepted artifact must become a subsequent source through the shipped Studio, and the journey must be repeatable without hidden agent state.

The report is valuable because it changes the question from “which model looks best?” to “which exact route reliably satisfies this task, on this machine, with this input and amount of work?” It should tighten the existing product, not create another model shelf or delay the pack until every candidate has been tested.

### Decisions made in this adaptation

1. **Keep the convergence goal.** T01-T08 become staged diagnostics behind it, not eight additional release gates. Inspect the current pack and owner review before spending another generation allowance.
2. **Retain measured baselines.** Current Klein/Combine, pose-then-face, WAI repair and Anima Base evidence stays in the comparison. The paper's preferred Qwen/Animagine portfolio does not erase it.
3. **Separate priority from qualification.** A useful research recommendation is neither a successful execution nor an accepted image. Exact-version advice, installed-byte verification, runtime reliability, artistic judgement and permitted use remain separate facts.
4. **Use existing owners.** Prompt syntax belongs in Prompt Lab and its settings knowledge; observations in Reference Intelligence; binding in Workflow Studio; bounded campaigns and comparisons in Experiment Lab; canon/reviews in Workspace; runtime authority in the existing coordinator/backend manager.
5. **Start small in software.** Expose source scope separately from resource-pin matching in the existing guidance evaluator, and correct the stale Anima documentation. Do not install a comparator or upgrade ROCm to demonstrate document intake.

## Reading path

| Read | Purpose |
| --- | --- |
| [EXTRACTION.md](EXTRACTION.md) | Page-addressed decomposition of every substantive report section, including uncertainties and examples |
| [PORTFOLIO.md](PORTFOLIO.md) | Role-based model/configuration choices, prompting, adapters, native controls and purpose-sensitive terms |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Ownership, evidence boundaries, identity/canon, UX and technology decisions |
| [QUALIFICATION.md](QUALIFICATION.md) | The eight tasks, finite experiment accounting, runtime qualification and independent review |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Existing issue crosswalk, smallest next changes, regression expectations and merge order |
| [SOURCES.md](SOURCES.md) | Original artifact identity, current divergences, primary-source checks and refresh rules |

Read together with the existing [product thesis](../PRODUCT-THESIS.md), [fantasy brief](../../FANTASY-CHARACTER-BRIEF.md), [pose screening plan](../../pose-control/SCREENING-PLAN.md), [current state](../../../CURRENT_STATE.md) and [owner decisions](../../../HUMAN_TODO.md). This directory is a dated integration layer, not a second current-state ledger.

## Corrections that affect decisions

**Runtime:** page 16 uses the wrong AMD hardware row for the Linux kernel. ROCm 10.0.0's Radeon table pairs Ubuntu 24.04.4 with **HWE 6.17**, whereas the report's GA 6.8 appears in the Instinct table. The corrected tuple is a candidate to validate under #303, not an installation instruction or proof of ComfyUI/custom-node compatibility.

**Repository evidence:** Anima Base 1.0 is already installed and has executed in the repository's atelier records. The report's “not proven” row is a limitation of that review, not evidence of absence. Likewise, the newer Combine/pose-then-face workflows must participate in a matched baseline before replacement is justified.

**Scope:** the parked adult-illustration stack is not required for this general anime integration. HUMAN_TODO q-29 remains an owner decision. The owner has already answered the private-experiment use question; this work preserves terms records without manufacturing a new commercial launch requirement.

**Compiler:** the current generic profiles and family notes are not yet the exact-version compiler proposed in the paper. In particular, Aesthetic/Base/Turbo distinctions, model-specific negative syntax and native-versus-quantized schedules still need the separately tested migration in #34/#144. Adding a source-scope label does not finish that migration.

## What success means

Report the accepted/attempted denominator for each required asset role, then the number actually reused. Report owner interaction time, clarification and prompt/reference/mask edits, compute time, waiting and cleanup/restart cost separately. Retain hard-constraint failures and rejected images. A visually attractive result that changes the wrong identity, protected text or source pixels does not pass its task.

The first delivery gate is **a usable pack and a repeatable journey**, not a larger test count, a larger model collection, a new frontend framework or a benchmark leaderboard. Candidate comparisons earn ordinary UI placement only after the relevant evidence and owner review; they do not become globally “best” models.

## This intake does not authorize

No new generation, automated reroll, model/node download, GPU helper execution, runtime switch/restart, environment upgrade, public source-image upload, commercial clearance or HUMAN_TODO answer follows from this document. Software tests and read-only inspection remain distinct from those operations.
