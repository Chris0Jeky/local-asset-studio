# Workflow engine: local verification

Base: `67f995f245518b36fb0192a61da780d337d53028`, with shared values from #642 (`3fc1ac001fa7b06159b5db0f6a35dfdffc679222`). Linux / Python 3.13.5; no hosted Actions, Codex review, model backend or native application.

## Executed checks

* Initial new engine regressions: **25 failures** on the unextended implementation, for missing module/planner/identity behavior.
* First implementation: **25 passed**, including real `AssetWorkspace` SQLite transactions.
* HTTP regression-first run: **4 failures** for the missing routes; after handler integration, all passed over real loopback HTTP.
* Self-review added explicit external-binding provenance, boolean-versus-integer boundary validation, full-node-budget refusal and nested/cyclic draft coverage. The provenance test exposed a missing `bindings` field; the receipt now retains it.
* A legacy v1 noncanonical JSON row is read and replayed without rewriting its exact bytes before or after a new module import. No table or persisted-version migration is needed for these additive commands.
* Final `python -m unittest discover -s tests -v`: **52 passed** in this selected-source checkout: 19 shared-value tests, 29 workflow engine/store tests and 4 HTTP tests. This is not the complete repository test suite.
* `python -m compileall -q studio_workflow app tests` and `git diff --check`: passed for the materialized files.

The tests cover historical replay after later undo/redo, stale guards and CAS, two competing real SQLite clients, receipt-insert rollback, explicit external bindings, lineage retention, immutable earlier revision bytes, safe bounds and actual same-origin HTTP refusal. Source modules were checked against GitHub blob hashes before editing. Full repository validation, installed runtimes and integrated browser/SDK behavior were not exercised.

## Informational core timings

25 iterations per case, same local Python process, synthetic small scalar nodes, one selected two-node closure. These are observations, not portable thresholds and not canvas/DOM benchmarks. Planning validates/hashes all authored nodes; compilation validates the document but emits only the selected closure.

| Authored nodes | Document bytes | Compile median / max ms | Plan median / max ms |
| --- | --- | --- | --- |
| 50 | 2730 | 0.296 / 0.405 | 1.947 / 2.252 |
| 150 | 7830 | 0.799 / 3.426 | 5.351 / 6.827 |
| 256 | 13342 | 1.3 / 2.369 | 8.903 / 10.347 |

## Tested file bindings

| File | Git blob SHA |
| --- | --- |
| `studio_workflow/commands.py` | `7880b2529d599c0512594a9c0ee06ed7657e8013` |
| `studio_workflow/core.py` | `e4c41b875094b174989fe1a40de56b23857ff05c` |
| `studio_workflow/documents.py` | `eeef4ff43cbe9873f191c6dcc9dbd845b8250565` |
| `studio_workflow/document_http.py` | `58cccf76d91b81696182dda9e8d25552fefba68c` |
| `studio_workflow/command_plan.py` | `d2c9de055503d08892c4c291f92b686e9e30871e` |
| `studio_workflow/modules.py` | `bd6c8ba174b27f769ea1be3713bffa7e05104f33` |
| `tests/test_workflow_module_commands.py` | `7b97590559317f61c7a4169eeb6ca991b927eed4` |
| `tests/test_workflow_module_http.py` | `3123a9f2f3837b3984aaa805324a7da6b98c8fa2` |

## Disposition

Refs #120. The deterministic module/inverse/hash engine and HTTP path are delivered, not the entire issue's frontend acceptance. The full offline suite, validator, 390px/keyboard integrated browser scenarios and actual asset handoffs remain unqualified here. Flat Step modules do not implement native visual-subgraph conversion or arbitrary graph execution. Existing owner decisions and creative acceptance remain unchanged.
