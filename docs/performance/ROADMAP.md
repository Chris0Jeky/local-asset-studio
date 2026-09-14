# Delivery order and issue ownership

Parent: [#172](https://github.com/Chris0Jeky/local-asset-studio/issues/172). Reconcile against current main and open PRs at the start of each slice. Do not reopen delivered work just because the PDF lists it as new. Issue links for newly scoped gaps are maintained in the parent thread and added here during this pass.

## Existing owners retained

| Owner | Scope that stays there |
| --- | --- |
| #173 / #182 | Delivered finite observer; extend its output rather than duplicate it |
| #174 / #182 | Delivered main-page read scheduling; preserve signature and navigation guards |
| #175 | Bounded status/resource projections and conditional observation; no per-client heavy schema probes |
| #176 | Validated shared launch policy and measured preview/cache/offload/pinned/MIOpen/reserve variants |
| #177 | Media/history/inventory bounds and remaining observer migration |
| #178 | Stage-aware resource admission and auxiliary budgets through the existing coordinator |
| #106 / #129 | Deployed scoped host-commit gate; do not weaken it |
| #77 / #89 / #163 | Host/native failures and graph-specific Wan decode capacity; do not relabel them solved by telemetry |
| #22 / #122 / #10 / #35 | Existing executor, experiment allowances and helper coordination |

## Missing increments and acceptance

| Key / priority | Increment | Depends on | Completion evidence |
| --- | --- | --- | --- |
| PERF-01 / P0 | Offline receipt summaries | Existing #173 output | Actual producer compatibility; bounded bytes/lines/cardinality; coverage and sampled extrema; incomplete/unknown states; no network, Torch or process control |
| PERF-02 / P0 | Job-window telemetry and finite benchmark harness | PERF-01; #10/#122 | Runtime/graph/model/input identity; cold/warm separation; explicit phase provenance; bounded persistence; zero unauthorised submits/retries; approved local Windows baseline |
| PERF-03 / P0 | Isolated supported AMD runtime comparison | PERF-02; #176 | Exact support evidence, stable environment unchanged, separate candidate environment, finite paired trials and rollback, all failures and quality retained |
| PERF-04 / P1 | Optional owned browser lifecycle | Existing NoBrowser; #175 | Dedicated profile and creation identity; PID-reuse/unrelated-browser tests; durable acknowledgement before close; deduplicated reopen; no job cancellation |
| PERF-05 / P1 | Opt-in locality and warm retention | PERF-02; #178 | Default FIFO unchanged; dependency/starvation tests; measured transition savings; exact cache compatibility; no stale-history authority |
| PERF-06 / P1 | Retained-commit cleanup / prepare-large-job command | PERF-02; #178; existing recovery | Idle/ownership/uncertainty interlocks, release then remeasure, conditional verified restart, after-action readiness snapshot; no replay |
| PERF-07 / P2 | Precision/quantisation and graph-fallback evidence | PERF-02; #176/#178/#163 | Matched quality/reliability/resource trials; graph diff and approval before changed settings; no global low-VRAM assumption |
| PERF-08 / P1 | Resource panel and explainable preflight | #175/#178; PERF-02/06 | RAM vs commit vs VRAM clarity, age/unknown coverage, evidence-linked reasons, commands through existing owners; stale UI cannot bypass a hold |

M0 is planning and PERF-01 only: no live changes. M1 binds evidence to actual jobs and produces the first finite stable baseline. M2 adds advisory policy and isolated experiments. M3 independently opts into browser, locality and cleanup features; measured policies may then be promoted. Faster inference or fewer crashes cannot be a checkbox closed by an offline test suite.

Each implementation PR records the exact base/head, changed interfaces, red/green tests, full repository gate, local-vs-hosted execution limits and rollback. Use `Refs` for partial work. Close a child only when all of its acceptance criteria are satisfied, not merely when its scaffolding exists.
