# Performance programme: RX 9070 XT

14 September 2026. An extension of [resource efficiency #172](https://github.com/Chris0Jeky/local-asset-studio/issues/172), not a second programme or executor.

The owner supplied *Resource optimisation strategy for Local Asset Studio on the RX 9070 XT*. This package turns its recommendations into reviewable increments while preserving work already delivered. It does not authorise workstation changes or record a performance improvement.

| Read | Purpose |
| --- | --- |
| [FINDINGS.md](FINDINGS.md) | Report-to-current-code reconciliation, historical evidence and verified external references |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Observation, evidence, policy and lifecycle boundaries; failure and ownership rules |
| [BENCHMARKS.md](BENCHMARKS.md) | Reproducible comparisons, budgets, stop rules and rollback |
| [ROADMAP.md](ROADMAP.md) | Existing owners, missing slices, dependencies and acceptance gates |
| [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | First implementation: bounded offline resource-receipt summaries |
| [benchmark-plan.example.json](benchmark-plan.example.json) | Non-executable experiment worksheet; deliberately unbound, zero generation allowance |

Start with the existing [profiler and operator guide](../RESOURCE-EFFICIENCY.md). The first implementation is submitted separately in [PR #310](https://github.com/Chris0Jeky/local-asset-studio/pull/310), including the offline reducer, CLI, telemetry contract and regression tests for [#301](https://github.com/Chris0Jeky/local-asset-studio/issues/301). It consumes existing JSONL receipts rather than introducing another monitor. Submission is not a claim that the PR has merged or that inference is faster.

The later [job-telemetry adapter #302](https://github.com/Chris0Jeky/local-asset-studio/issues/302) will reuse the same reducer through the existing coordinator. No new polling thread, GPU import, process killer, policy default or runtime profile is introduced by this planning PR.

The report's priority remains appropriate: prevent unsafe residency/host-memory transitions, measure representative workloads, then optimise throughput. The required order is evidence foundation -> finite benchmark integration and advisory policy -> isolated experiments -> independently opted-in lifecycle features. Browser/projection work can proceed independently under its existing issues.
