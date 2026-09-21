# Collection commands: verification and review

Base: #645 / `dfe98e9e930fe7cde82c45b018f389a933c19260`, ultimately main `67f995f245518b36fb0192a61da780d337d53028`.

## Executed local checks

Linux, Python 3.13.5, Node 22.16.0 and Chromium 144.0.7559.96. No hosted Actions, Codex review, model backend or native creative runtime was used.

* `python -m unittest discover -s tests -v`: **107 passed** in the selected-source checkout. Breakdown: 19 shared values, 33 workflow engine/HTTP, 30 collection transaction/migration, 11 collection HTTP, 4 migrated scope and 10 existing Workspace/snapshot tests. This is not the full repository suite.
* `node tests/collection_editor_contracts.cjs`: **16 passed**. Existing scenarios retained, fixtures migrated to revisions and typed receipts. The fixture now depends on the real collection script, not unrelated asset editor/recovery scripts.
* `node tests/collection_editor_reopen_contract.cjs`: **1 passed**, retaining the delayed-close/replacement-dialog regression.
* `python tests/collection_command_browser.py`: **6 passed** at a 390px viewport, running the actual editor script and real collection HTTP/SQLite through the disclosed bridge below.
* `node --check app/static/collection-editor.js`, `python -m compileall -q app studio_workflow tests`, and `git diff --check`: passed for the materialized source.

Do not add parent-PR totals again: those tests are included in the 107. Node and opt-in browser scenarios are additional local checks, not hidden extra Python test cases.

## Causal checks and review corrections

The first 25 transaction/migration tests failed on the original implementation and passed after adding the typed journal. Initial 9 HTTP tests failed without the new handler and passed after wiring it. The old scoped browser request failed against the new preconditions, then the migrated client passed all 6 scenarios. Old positional SQL/scope fixtures failed for the explicit schema/protocol changes and were updated without dropping their assertions. The original Node receipt fixtures produced 2 failures, then all 16 scenarios passed using the typed result.

Self-review found two HTTP connection-state problems. First, using the existing rejection helper after the body had already been consumed drained the first four bytes of a pipelined GET. The regression failed with malformed next-request parsing and passed after distinguishing unread from consumed bodies. Second, ambiguous duplicate length headers left the unread body eligible for connection reuse. A separate regression observed a second 501 response before the fix; early refusals now close the connection. Fully consumed malformed JSON still leaves an unambiguous subsequent request intact.

Additional checks prove status works under SQLite `query_only`, valid historical evidence survives corrupt current metadata, rehashed duplicate/reserved/nonfinite JSON is refused, oversized stored text is rejected before loading it, and the exact journal byte boundary is accepted while one byte under the required capacity refuses atomically.

Fault coverage uses real temporary SQLite connections, including competing writers, simultaneous migration, a writer paused before commit while status returns unknown, rollback after injected receipt-insert failure, and database-path replacement after identity observation. Transport tests actually drop a committed response and separately raise after a successful commit; status/replay recovers the original evidence. Deletion verifies source/snapshot bytes, other memberships, single member revision increments and overflow rollback.

## Browser boundary

Managed Chromium rejected direct `http://127.0.0.1` navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`. No browser policy was changed. The passing fixture uses an inert DOM at `about:blank`, injects the **actual unchanged-at-runtime editor source**, supplies test-unique UUIDs because that page lacks the secure-context UUID method, and bridges its API helper to real loopback HTTP in Python. Origin/framing/response-loss behavior is separately tested over actual sockets. This is not a native browser networking test, full Studio shell test, screen-reader test or overall Workflow Studio canvas qualification.

The browser cases cover keyboard submission, create/rename/delete revisions, a competing rename retaining the local draft, absent revision refusing dispatch, lost response blocking repeats while preserving the server receipt, newer typing surviving an earlier response, mismatched receipt identity and unchanged library selection. The six scenarios contain multiple assertions; they are not six discovered defects.

## Source bindings

Original sources were retrieved through the GitHub connector and checked against full Git blob hashes before editing. Native Git DNS/network access was unavailable; no full repository checkout was obtained. Published trees must extend the full remote parent tree, never the selected-source local Git tree.

| File | Tested Git blob SHA |
| --- | --- |
| `app/workspace.py` | `d8050567f51a790ecebcb4495bd89c2352b6010f` |
| `app/static/collection-editor.js` | `8389ea7a2c7848888cbaf91a332a4d440d726f93` |
| `studio_workflow/collection_commands.py` | `1f5e860f3ce2fad349dceb2a3674691b086318d6` |
| `studio_workflow/collection_http.py` | `b7064f0cc08f2e3ae8ac2ca13597537cd69edea4` |
| `studio_workflow/http_extension.py` | `5c90888f8d8673c24619213cc9cc7c983cd297c8` |
| `tests/test_collection_commands.py` | `32a000ca3914a5be111b90731cb1532b4ab867af` |
| `tests/test_collection_command_http.py` | `0b752fca31c81a898f4a3fda547163852207b918` |
| `tests/test_collection_scope.py` | `c17135f54011329051d26eadb986697d3db6ec13` |
| `tests/test_workspace_snapshot_counts.py` | `4157f151ea3fb6ab5ba1b4302adf3e565101915b` |
| `tests/collection_editor_contracts.cjs` | `09047972f9f0ba70b2bd94ae4dc94e23400ee201` |
| `tests/collection_editor_reopen_contract.cjs` | `21ad068d1d82b9a0dea1e90a9704e1d88551f900` |
| `tests/collection_editor_fixture.cjs` | `0a82a75d8eede73799c00d464d068e19e3de4ca7` |
| `tests/collection_command_browser.py` | `4e3599cdad12e067f13a252603557f83483eac9e` |

## Unqualified / not delivered

The complete offline repository suite, `scripts/validate-repo.py`, full application import/startup, the existing full-shell browser driver and native browser networking were not run here. Root handler composition was changed at its existing seam and compiled, but component loopback tests do not establish complete shell startup. No claim is made about hosted CI or automated review results. Browser persisted-command recovery remains #388; collection membership-set CAS, journal rotation and downgrade tooling are not silently included. Broad #120 frontend acceptance and #314 full two-domain requalification remain as recorded in their own PRs.

Refs #387; no issue was closed automatically. Owner-controlled `HUMAN_TODO.md` remains unchanged.
