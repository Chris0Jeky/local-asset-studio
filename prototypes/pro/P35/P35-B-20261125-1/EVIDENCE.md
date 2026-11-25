# Software evidence — P35-B-20261125-1

## Actual result

The final one-command verification at **2026-11-25 02:41:56 UTC** passed **126 tests with zero failures, errors or skips**. Eight source-prepared graph variants matched the independent materializer. All **four deterministic reports** matched both their committed compact copies and `HASHES.sha256`. See `verification.json` for the exact source/test hashes and retained environment receipt.

This is software evidence. Every image output claim is **planned**; no owner Studio, ComfyUI model, GPU, real reference image, actual generation, artistic inspection, owner Keep or licence clearance was involved.

| Test module | Tests | Main evidence |
| --- | ---: | --- |
| `test_qualification.py` | 37 | Full denominators, all six axes, per-subject review, lineage/rubric pins, owner-mark kill rule, scoped calibration, duplicates/leakage and resource completeness |
| `test_plan.py` | 29 | Exact graph bytes/bindings, role conflicts and unsupported facets, seed limits, corrected-guide order, prospective protocol, identity validation and bounded budgets |
| `test_owner_run.py` | 32 | Actual subprocesses and inert loopback HTTP: lost replies, timeouts, concurrent starts, stale journals, interruption/process death, graph/input/model changes, native pruning, GET-only status and separate prepare timeout |
| `test_source_contract_check.py` | 3 | ASCII graph hash convention, exact source-file pins, four native routes × two seeds |
| `test_integration.py` | 5 | Independent native preparation and model-inventory resolution for all four routes with two/three seeds, Unicode prompts, CLI/HTTP completion and compiler/runner readiness |
| `test_run.py` | 20 | Public command boundary, recombined campaign/trial refusal, exact native chunk/source/model/settings coverage, deterministic evidence and failed-phase log retention |
| **Total** | **126** | **No skipped tests** |

Focused regressions were observed failing before fixes, including silently discarded references/facets, stale-journal concurrency, Unicode graph hashing, unrelated calibration scope, contradictions outside holdout, duplicate output bytes, route-specific missing costs, NUL prompt readiness, cross-campaign receipt recombination and lost verification logs. The shipped tests reproduce the corrected behavior; detailed transient red/green logs remain regenerable work under `.runtime` rather than an image benchmark.

## Exact command and environment

Actual remote command:

```bash
python -B prototypes/pro/P35/P35-B-20261125-1/run.py verify --source-root /workspace/scratch/bb51a4d8d01a/studio-context
```

Working directory: `/workspace/scratch/bb51a4d8d01a/p35-work`.

- OS: Linux 6.18.57, x86_64, glibc 2.41.
- Interpreter: Python 3.12.14, built with Clang 22.1.3.
- Compiler invoked: none. Compiler flags: none. No C/C++/MSVC build is part of this stdlib-only prototype.
- Source: selected files read through the GitHub connector at `0270760a3d4fd9e005a1788bba59d8242b77c2f4`; no sandbox GitHub network fetch, clone or full repository copy.
- Test services: inert local HTTP servers on ephemeral loopback ports; no live owner's service.
- Regenerable output: `.runtime/P35-B-20261125-1/evidence/` and temporary fixtures beneath that run's `.runtime` directory.

Owner reproduction from the full pinned branch on Windows with Python 3.12+:

```powershell
py -3 prototypes/pro/P35/P35-B-20261125-1/run.py verify --source-root .
```

The program regenerates compact deterministic JSON below `.runtime`, verifies raw UTF-8/LF bytes, retains a fresh timestamped software-verification receipt and returns nonzero on test, source, hash or output-retention failure. It does not mutate expected evidence to make a mismatch pass.

## What the source comparison proves

The checker verifies exact SHA-256 pins for `app/server.py`, `app/references.py` and `presets/catalog.json` before extracting the actual `Studio.prepare`, control/numeric/LoRA helpers and native reference compiler. It compares prepared graphs and Production's hash convention with the prototype materializer. This covers the Qwen role guidance, both conditioning branches through original graph bytes, the reversed skeleton/character placement and Klein 4B's exact trailing pruned reference record.

The independent integration fixtures resolve model pins from `models/library.json` using each actual prepared graph's loader nodes. They do not obtain their expected model set by copying the planner output. Two and three seed plans then pass through a real CLI subprocess and inert HTTP fixture with known job/prompt identities.

Explicit stubs are worker/backend admission, image decoding (synthetic bytes report 832×1248), installed-model observation, continuation/tile/parallax and Wan/i2v validators, host memory preflight, and staging uploads into ComfyUI input. These stubs are retained in `evidence/source-contract.json`. No live schema, image preprocessing pixels, model tensor, GPU kernel or power-loss behavior is verified by this source subset.

## Deterministic outputs

| File | Interpretable result |
| --- | --- |
| `evidence/qualification-summary.json` | 240 planned cells remain missing, with null observations and no qualified route |
| `evidence/calibration-demo.json` | Synthetic perfect agreement cannot gate; four inverted predictions disable; unavailable owner labels remain blocked |
| `evidence/route-summary.json` | Four current graphs/90 nodes, honest planning estimates, 12-cell smoke and disabled two-recipe frontier |
| `evidence/source-contract.json` | Exact source pins and eight prepared-graph comparisons, with all stub boundaries named |

`HASHES.sha256` contains one raw SHA-256 and repository-relative path per deterministic file. Changing code/data in a way that changes these outputs must produce a visible mismatch and a reviewed new evidence version. `verification.json` contains the variable environment/time receipt and is intentionally not represented as a deterministic cross-platform output.

## Full repository gates

No `app/`, `presets/catalog.json`, existing graph, installed model or runtime file is changed. All changes are isolated under the two requested prototype/report paths. The user-required commands for app/catalog changes remain:

```console
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Those commands were **not run locally against the selected source subset**. The repository's existing **Check studio** GitHub Actions workflow runs the full offline suite through `tests/check_full_suite_lifetime.py` (which invokes unittest discovery) with a 1,200-second resource-lifetime budget, followed by `python scripts/validate-repo.py`, on Ubuntu/Python 3.12. Its status is separate from the 126 prototype tests and is reported on PR #2047. No full-suite pass is inferred from source checks or an in-progress CI run.

## Remaining uncertainty

- The Windows/MSVC-built interpreter, `.cmd` launch behavior and Windows power-loss durability are unverified. Linux process-kill/interruption behavior is covered by fixtures.
- Actual RX 9070 XT/HIP execution, node schemas, installed byte rehashes, image/crop transforms, cold/warm timing, host RAM, VRAM and queue behavior are unverified.
- All route resource values are planning estimates; current Qwen feasibility and both frontier candidates remain conditional.
- No real owner-labelled calibration corpus was available. Owner declarations are not authentication, and numerical diagnostics do not make artistic decisions.
- The native output/resource/review/owner-mark collector and paired owner Keep report remain adoption work. The current human rubric result is not owner Keep rate.
- Unsupported multi-character and independent-facet cells remain present. Neither the 12-cell smoke nor this software check qualifies the full artistic matrix.
- Component licence names and provenance gaps are documented separately; no asset rights were cleared.
