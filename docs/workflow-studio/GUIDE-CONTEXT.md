# Guide context, history and continuation QA

**13 September 2026.** Scope: guide defects #185 and #190, plus reconciliation of
original workstreams #118–#123. Inspected baseline:
`06bd93aed2f019cb978eb5795e9f116cfb7ff749`, canonical tree
`9561db4b2bf6bba7178f10554bcc95479f0d6a7d`. The isolated tracked-source checkout's
Git tree matched that baseline before edits, including normal Git EOL handling.
No owner configuration, model, output, queue or HUMAN_TODO state was modified.

## Reconciliation before implementation

PR #169 was merged and already supplied versioned stages, evidence predicates and
same-page navigation. The two focused follow-up issues were still open and their
reported defects were present in the current source. Current shared documents,
Steps, SDK/MCP and saved-run implementations were also inspected before changing
the old overview and agent instructions. All six broad issues remain incomplete;
[ROADMAP.md](ROADMAP.md) records existing owners and actual residual acceptance.

## Defect #185: a changed recipe retained old readiness

The coach listened for DOM input/change and workflow events. `selectPreset`, setup
application and saved/imported recipes write state and controls programmatically.
They did not necessarily emit any of those events, so the displayed observation
could remain attached to the previous recipe until another check.

The Create state owner now emits **`studio:recipe`** when the selected preset
changes and after programmatic setup/import, variation, seed or notified I2V-mode
changes. This event has no payload, receipt, snapshot or approval. Selection emits
as soon as `selected` changes, before rendering, so a failed render cannot preserve
old successful evidence. Setup/import emit again after applying their fields.
Rejected selections do not emit a successful transition.

The coach consumes the notification through its existing invalidation epoch and
unknown-state path. It does not poll, automatically recheck, change controls, save,
switch environments or dispatch a job. Even A → B → A during one delayed check
invalidates the old response: final snapshot equality alone would miss that case.
No event is emitted on unchanged periodic readiness polling.

## Defect #190: history was misidentified as a fresh tool change

Same-document Back/Forward can emit popstate followed by hashchange. Popstate
already cleaned the old panel and mounted the destination stage. Its new hashchange
listener then erased the manual-stage label despite belonging to that destination.

Each mounted coach now remembers its own `pathname + hash`. A hash event invalidates
only when the current tool differs from that mount's last observed tool. There is
no timer, global event suppression flag, persisted evidence or rewritten browser
history. A genuine hash change still invalidates; an input event between popstate
and its paired hashchange remains invalidated. This preserves the **manual-stage
classification**, not a stored human approval or previous successful observation.
Pause/remount remove the exact event callbacks and abort owned reads as before.

## Executable scenarios

`tests/studio_guide_context.cjs` executes the shipped Create transition functions and
coach. It uses small explicit DOM/history/HTTP seams, not a substitute browser or
network bypass. Rendering helper functions are isolated in this contract fixture;
the separate native test exercises the full actual pages.

| Scenario | Expected contract |
| --- | --- |
| Observe A, select blocked B programmatically | Old observation becomes unknown immediately; explicit recheck reports B's blocker. |
| Apply same-preset setup or saved/imported settings | Invalidation without a DOM input event; notification after final fields are applied. |
| Reject unknown preset | Existing state and observation are not falsely changed. |
| A → B → A while readiness is delayed | Original response discarded; no automatic second health request. |
| Back/Forward: popstate, then hashchange | Destination manual stage remains manual; exactly one coach. |
| Real tool or input change after restoring history | Unknown state retained; paired event cannot erase a newer invalidation. |
| Return to previously checked stage | Success is not restored from navigation history or localStorage. |
| Repeat remount, then Pause | One live callback while mounted, none afterward; no HTTP mutation. |
| Actual picker/variation/seed/mode handlers | Programmatic setting changes notify the real coach without text-input events. |

The expanded `tests/studio_guide_browser.py` also checks real setup/import transitions
and waits for **both** native history phases on Back and Forward, rather than
passing as soon as the destination panel exists. It keeps the original seven-path,
keyboard, 390px, 200%-zoom and zero-forbidden-write checks.

## Verification record

- Final nine-contract suite against original baseline scripts: **6 failed, 3
  passed**, reproducing the missing notifications/history handling. Against patched
  scripts: **9 passed**. No fixture exception is counted as the intended failure.
- `python -m unittest discover -s tests -p test_studio_guide.py -v`: **4 passed**,
  including both Node contract suites and manifest/anchor checks.
- Full isolated suite: **1,464 tests, OK, 15 skipped**. Optional/live skips are not
  claimed as executed. Existing Pillow deprecation/socket warnings were observed.
- `python scripts/validate-repo.py`: 66 preset graphs/bindings and 121 pinned assets
  validated. The final staged path count is reported by the command/CI.
- `node --check` for modified JavaScript and the pre-existing handoff contract pass.
- CLI help for the documented saved-run/document commands and offline
  `python scripts/workflow-mcp.py --describe` succeed. This is not a live MCP host
  handshake or a model run.
- Native local browser navigation is restricted (`ERR_BLOCKED_BY_ADMINISTRATOR`).
  No native-browser pass is claimed from this container. The PR's **Guided journey
  browser** job is the separate hosted native-browser gate; use its result/artifact.

## Research and boundaries

Checked 13 September 2026: [MDN input event](https://developer.mozilla.org/en-US/docs/Web/API/Element/input_event)
documents that assigning a value in JavaScript does not itself fire input.
[MDN popstate](https://developer.mozilla.org/en-US/docs/Web/API/Window/popstate_event)
and the [HTML history traversal standard](https://html.spec.whatwg.org/multipage/browsing-the-web.html#apply-the-history-step)
describe the history event sequence. These inform the notification and semantic
location comparison, not any new engine authority.

No native/subgraph adapter, recommendation engine, wide-integer browser codec or
arbitrary authored execution is added here. Those remain explicit #118–#123 work,
not capabilities inferred from passing UI tests. Generated output, creative review
and licensing remain separate evidence.
