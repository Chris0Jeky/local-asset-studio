# Low-level engineering: from the supplied audit to this Studio

14 September 2026. Parent programme: #172. Inspected repository baseline: `1c9c1f85b69cbb26e5dd0ea6c1f3fa60969eb80a`.

The supplied **Local Asset Studio: Low-Level Engineering Optimisation Audit and Roadmap** is the basis of this package. It is a 33-page graphics/asset-processing proposal, not a retained call-site audit of this repository: the report itself says so on pages 1 and 32. Its durable ideas are useful here, but its renderer architecture must not silently become an inference architecture.

| Deliverable | Use |
| --- | --- |
| [Source map](SOURCE-MAP.md) | Page-by-page provenance, recommendation disposition, actual code and existing issue owners |
| [Architecture and decisions](ARCHITECTURE.md) | Separate Studio, inference and graphics ownership; cache identity, lifetimes and evidence contracts |
| [Experiments](EXPERIMENTS.md) | CPU copy tests, AMD operator/transfer qualification, numerical and quality gates |
| [Implementation plan](IMPLEMENTATION-PLAN.md) | Two bounded code slices, exact interfaces, tests, publication and rollback |
| [Roadmap](ROADMAP.md) | Ready work, prerequisites, conditional graphics work and explicit non-deliveries |
| [Machine-readable intake](../../../research/performance/low-level-audit.json) | Source fingerprint and non-executable work mapping |

## Immediate decisions

1. Extend the existing performance programme, Workspace and generation coordinator. Do not add another scheduler, authoritative asset store, model manager or polling service.
2. Implement two CPU-side minimum-copy improvements first: skip a no-op review orientation copy (#362), and bound protected-pixel comparison scratch memory (#363). Their correctness is exactly testable without model execution.
3. Qualify inference operator/transfer traces (#364) before selecting attention, matmul, layout, compilation or transfer changes. Runtime experiments remain isolated and explicitly budgeted.
4. Retain KTX2, mesh optimisation, LOD, upload rings and GPU-driven rendering as graphics/export candidates under #15/#24/#177. Do not claim they reduce diffusion tensor memory.

The PDF's performance percentages and engineering-day estimates remain proposals, not measurements or commitments for this codebase. This package creates no neural jobs, changes no launch defaults and grants no new runtime or licence authority. It leaves HUMAN_TODO unchanged.

## Verification boundary

Repository statements are grounded in the pinned files and issue snapshot listed in SOURCE-MAP. External documentation is separately labelled there. This is not a complete dependency or hot-path profile. No access to the owner's running Windows process, GPU or private receipts was available in this pass. Local synthetic CPU evidence and hosted repository tests must be reported separately from owner-machine inference evidence.
