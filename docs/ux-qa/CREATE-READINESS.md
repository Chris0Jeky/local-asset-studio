# Create readiness: actionable blockers and current inspection

Checkpoint: 13 September 2026. Refs #16 and #118; neither broad workstream is closed.

## A practical journey

Open a three-reference edit, keep the written brief, and ask why Generate is disabled. Follow
**Attach missing reference** to the first incomplete role, return to the same draft, inspect
missing files, recover from an unavailable check, then review the remaining conditions.
For animation, **Review motion settings** exposes the existing mode control without changing it.

A blocker should answer both “what is missing?” and “where can I address it?” Following the
answer must not itself upload a reference, install a model, change environment, spend a generation
or certify readiness. The existing controls and server admission still own those decisions.

## Delivered behavior

| Situation | UI response | What does not happen |
|---|---|---|
| No selected recipe | Focus the existing recipe search | No automatic recipe selection |
| Offline, unknown connection, worker or environment hold | Open Models and focus the existing environment control when available | No launch, restart or switch |
| Missing model/node/runtime requirement | Open and focus the current Required files disclosure | No installation; the existing installability guard remains |
| Incomplete role board | Focus the first missing role's file input | No file-picker click, upload or guessed replacement |
| Missing first/last-frame input | Focus the corresponding existing input | No change to already attached inputs |
| Animation admission hold | Open Parameters and focus the motion-mode control | No automatic smaller mode or altered dimensions |
| Continuation wording/source hold | Reveal the editable wording or source context | No prompt suggestion application or source reattachment |
| A control is hidden or unavailable | Report that the control could not be shown | No fallback to an unrelated control or action |
| Repeated state poll with identical blockers | Retain the rendered controls and focused action | No repeated live-region update from an identical summary |
| No current client blockers | Say the server still validates Generate | No model, memory-fit, art or licensing approval |

**Recheck connection** explicitly invokes the existing health read owner. Repeated activation
while its UI is waiting is coalesced. After 15 seconds the UI releases with a message explaining
that the shared read may still finish. This UI deadline does not cancel that shared request or
replace the read scheduler. No retry is automatic.

The source summary now counts both staged first and last frames for slotless recipes. Role-board
attachments retain their existing count and lineage handling. This is a count, not byte validation.

## Root causes and implementation boundaries

### One blocker policy, two projections

`StudioUX.readinessItems()` adds stable codes and allowlisted presentation destinations to the
existing policy in `studio-core.js`. The legacy `readiness()` result stays exactly
`{ready, blockers}` with the same blocker text and order. Existing callers and deep-equality
contracts therefore retain their shape. The workbench adds its already-existing motion and
continuation conditions to this projection; Generate retains all those conditions.

Action values are tokens such as `references` and `dependencies`, not supplied selectors, URLs,
commands or functions. `studio-workbench.js` resolves them against current state when clicked.
A stale action that no longer belongs to a current blocker is inert. Targets are existing controls;
the adapter opens ancestor disclosures, rejects hidden/disabled elements, focuses and reveals.
It never dispatches the target's click/change handler. All generated message text is escaped.

The run summary is a polite atomic status region associated with Generate. The list is only
rebuilt when its markup changes, retaining a keyboard user's focus on unchanged controls.
A separate status records the explicitly requested navigation/check result. These are interaction
improvements, not a claim of complete screen-reader or accessibility conformance.

### Dependency results belong to a particular check

The former inspector checked only the selected recipe ID on success. An A→B→A response or an
older same-recipe recheck could replace newer data. Its failure branch had no context check and
left an earlier presence count, graph and node list visible beside an error.

`inspectSelected()` now captures a request epoch and the selected recipe object. Each new check
invalidates the previous request, aborts its signal, and immediately clears the previous count,
node list and graph. The panel shows Checking while pending. A complete current response is
constructed before its presence count is published; only `present === true` contributes to it.
Both success and failure check ownership before updating the panel.

A 15-second inspector deadline aborts the actual request. A Promise race also releases the UI when
a test or transport ignores abort. Late completion cannot change the timed-out panel. Failure
shows Unavailable plus **Recheck required files** for the currently selected recipe. That explicit
retry makes one GET, does not install and does not loosen Generate's independent health/model gate.
The counter is transient request ownership, not persisted freshness evidence or concurrency control.

### Existing owners remain

- `app.js` owns health/inspection and the existing polling manager; no new timer loop is added.
- Reference and continuation components own inputs, prompts, attachments and lineage.
- The guide/shortlist remains advisory. Open #237's source-aware chooser is separate.
- Production and server preparation own execution admission. A rendered inspector result grants no permission.
- Workspace, metadata commands and #216's recovery journal are unchanged. Open #233's library selection is untouched.

Alternatives considered: adding a second wizard would duplicate navigation and readiness ownership;
a generic “Fix everything” control would hide distinct side effects; making inspection itself an
execution gate would change authority. This slice instead exposes the current conditions through
existing controls and fixes the inspector's own request lifecycle.

## QA baseline, results and evidence

Local baseline is commit `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, tree
`5e920817385cf6c6d4aef2154267eb6c0d0c4511`. Live main was also checked at `3d3135a`:
its intervening #226 Krita-session paths do not overlap this slice. Publication/hosted comments
record the actual later merge candidate rather than relabelling the local baseline.

The same final full-shell driver recorded **27 expectations: 10 pass / 17 fail** on baseline,
then **27 pass / 0 fail** on the candidate. Its assertions include actual keyboard activation,
first/next missing role, hidden-target refusal, retained draft, explicit health/file reads,
unchanged Generate holds, focus retention, motion navigation and 1440px/390px bounds.
The observer-deadline case holds the actual handler's shared observation and accelerates only its
15-second UI timer; it does not claim cancellation of a network request.

Twelve actual-script cases initially yielded **2 pass / 10 fail**, then **12/12 pass**.
They include A→B, A→B→A, repeated checks, stale success/failure, actual abort delivery,
ignored-abort timeout, truthful unknown presence and preservation of the legacy policy shape.
These count as one unittest wrapper, not twelve extra suite cases.

The final application checkpoint's full local suite ran **1,675 tests: 1,659 passed, 16 skipped**
with no failures (118.457 seconds). Existing Pillow deprecation, deliberate fault diagnostics and
an exit-time unclosed test-socket warning remain in the logs. Validation and source hashes are
recorded separately in `CREATE-READINESS-RESULTS.json`.

**Local browser limitation:** native navigation produced `ERR_BLOCKED_BY_ADMINISTRATOR`.
Successful local browser runs use explicit `--inert`: actual Studio HTML/JS/CSS, injected storage
and transport, and synthetic readiness APIs served through Python. They do not exercise real
ComfyUI, installed models, owner files, native origin/storage or media decoding. Periodic scheduling
is paused in the test, but explicit checks still use the real read owner. The default driver in
the existing Guided journey browser Actions lane supplies separate native HTTP evidence. Do not
call that lane passed until its actual current-head receipt has been read.

Two earlier driver failures were fixture errors: trying to fill a hidden negative-prompt field
for a recipe without that input, and disposing the shared poller before asking it to run a manual
read. They were corrected by using the recipe's actual controls and pausing periodic scheduling
without disposing the read owner. Their logs are retained outside Git. The final baseline and
candidate use the same corrected driver; no runtime exception is accepted by `--baseline`.

## Repeat locally or in CI

```console
node tests/create_readiness_contracts.cjs
python -m unittest discover -s tests -p test_create_readiness_frontend.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
# In disposable development/CI Python, never managed ComfyUI Python:
python -m pip install playwright==1.57.0
python -m playwright install chromium
python tests/create_readiness_browser.py --out .runtime/create-readiness-proof
# Only for a policy-blocked native environment, with the different scope labelled:
python tests/create_readiness_browser.py --inert --out .runtime/create-readiness-component
```

`--baseline` retains failed expectations for comparison but still fails on exceptions, page errors
or incomplete runs. Receipts include source hashes, read/write records and screenshots. The existing
Guided journey browser artifact includes both retained guide and new Create evidence, with seven-day
retention. Raw local and hosted checkpoints should be kept separately in the handoff.

## Next acceptance, and limits

Keep #16/#118 open for specialist journey predicates, complete native interoperability and an
owner-run journey with separately recorded output review. This change does not retry failed
source hydration, recover files, evaluate a swapped resource's compatibility, prove runtime
identity, enforce recommendation ranges, or add a new readiness evidence store. Server errors
can still occur after client checks. Current state is an observation, not a lease.

Actual screen-reader behavior and 200% browser zoom are unverified by this driver. Narrow viewport
checks do not substitute for them. Native CI is still synthetic readiness evidence, not a model run.
No new human creative decision is required and `HUMAN_TODO.md` is unchanged.

## Primary interaction references

Reviewed 13 September 2026: [W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
informs concise progress/error messages without involuntary focus moves;
[W3C focus order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html) informs explicit,
logical target navigation; [AbortController.abort](https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort)
documents request cancellation. These are design references, not test evidence or a conformance certificate.
