# Chronological reconciliation: a known batch prefix and an unknown submission

13 September 2026. Initial source: `268fc8fa4803374878c976c8af859f0200e1d155`.
The initial issue snapshot contained 53 open issues. This is a software-contract
implementation of #187 under the older #10 workstream, not an inference run,
remote-cancellation mechanism, or creative acceptance record.

## What was already delivered

| Issue / workstream | Reconciliation | Remaining acceptance |
| --- | --- | --- |
| #2, first open issue | Explicit backend switching, pinned observations, visual/API workflows and startup interlocks already exist. | Higher-step HiDream and native/runtime/creative evidence; do not build another backend manager. |
| #3, second open issue | Controlled experiments, source-bound continuation, actual image baselines and a native mechanical Krita revision have recorded evidence. FLUX files are not simply all missing. | The requested controlled model/animation comparisons and reviewed native/game assets. |
| #9, third open issue | Intake/publication, shared validation, exact dependency readiness and newer loader-role guidance (#203/#218) are merged. | Broader exact source/provenance and hardware evidence. Do not duplicate intake or mislabel a filename as a verified model family. |
| #10, fourth open issue | Production materialization, single-worker execution, reservations, recovery clocks and local job dispositions are implemented. #186 resolved #93/#94; #198 resolved #95/#98/#110 and is merged. | Mixed known/unknown batch recovery is the concrete remaining software gap addressed here. Accepted creative exports and broader multistage demonstrations remain separate. |
| #97 | The validation implementation is already in #156. Its discussion explicitly retains installed-schema corpus acceptance. | Actual per-backend workstation schema evidence; a reduced fixture is not that evidence. |
| #187 | The original guard prevents false completion, but also leaves no explicit read/disposition path for the mixed case. No open PR covered it at selection. | Implement and prove the receipt, concurrency, restart, no-replay and operator-action contracts below. |

Initial open #216/#217/#219 work was inspected for overlap. The later source
snapshot includes #217's prerequisite-aware recipe shortlist and #219's baseline
recipe labels in main `f1283853bbc918ee5d93161a25bf92fcb3596640`. Those changes
are retained, not replaced. Subsequent open #220/#222 Workspace changes, #221
control layout, #223 CLI output and #216 asset recovery retain their owners.
The final PR head records any later integration and verification.

## Failure and chosen boundary

An ordinary batch can complete one item, persist the second item's submission
intent, then lose that second POST response. Its state contains a known prompt
ID and exact graph, retained output descriptors, and a separate pending graph
whose remote outcome is unknown. A third item may never have been submitted.

The existing ordinary observation guard must not certify the whole batch from
the known prefix. The existing no-ID abandonment path must not discard known
receipts. Removing either guard is the wrong fix. Matching prompts by approximate
text, resending the pending graph, refunding reservations, or guessing remote
cancellation is also outside this contract.

`app/mixed_batch.py` adds two explicit operations over the existing job, storage
and shared worker. It introduces no new queue, database, scheduler or model
runtime. An operator can check known receipts and then optionally record a
local disposition acknowledging **all** unresolved remote outcomes. Disposition
can be chosen without another history check; it is never a completion claim.

```text
uncertain mixed batch
  GET/list                 -> read-only summary, exact revision, no mutations
  Check known receipts     -> persist request -> shared queue -> bounded GETs
                              terminal known receipts/results retained
                              whole job remains uncertain
  Local disposition        -> reason + explicit unknown acknowledgement
                              atomic state publication -> abandoned locally
                              pending graph and reservations remain intact
  Production reconciliation-> existing explicit command -> failed project
                              no worker, preflight, clock entry or new stage
  New work                 -> separate explicit repair branch and existing caps
```

## Evidence and command contract

The supported shape is a contiguous known prefix of a two-to-four-item batch
(the current Create limit), with
unique nonempty prompt IDs, matching indexed submission records and nonempty
retained graphs, followed by exactly one pending submission marker. Malformed
or ambiguous historical records remain held and display an explanation. An
empty marker is not evidence of an unsubmitted request.

Each command requires `request_id` (8–80 ASCII letters, digits, underscores or
hyphens) and `expected_revision` from the current public `mixed_batch` summary.
The revision hashes the full in-memory job snapshot. It proves equality of
retained evidence, not authentication, remote completeness or artistic quality.
The receipt binds the request payload, action and accepted evidence. A repeated
identical request returns its current result; reusing its identity for different
arguments is rejected. A stale new request is rejected without mutation.

The public summary distinguishes each known submission's status, the unknown
submission index, and the declared never-submitted remainder. It excludes graph
bodies. The complete originals remain in the job directory. Public eligibility
is advisory; the command revalidates under the existing Studio lock.

### Check known receipts

```http
POST /api/jobs/<job-id>/observe-known
Content-Type: application/json
Origin: http://127.0.0.1:8191

{"request_id":"operator-check-0001","expected_revision":"<64 hex characters>"}
```

This queues **observation only** (HTTP 202), never generation. The ordinary
worker-liveness and backend-switch admission guards apply. Each unresolved
known ID gets at most one history GET per check, with the exact ID encoded as
one path component. Already-terminal receipts are not re-observed. There is no
automatic polling loop or remote attempt to find the lost unknown ID.

Success requires explicit native success/completion evidence. Explicit engine
error evidence can mark that known receipt failed; absent, malformed or
transport-failed history stays observing/unknown. No known result can mark the
whole batch completed while its pending tail remains.

Commands are checked again before dispatch. In-flight results cannot overwrite
changed pending or known graphs. Output descriptors are persisted before using
the existing Workspace indexer. Indexing works on a prospective job copy and
publishes only if the job still matches, preserving existing output membership.
An indexing failure does not authorize a new render or another already-terminal
history request. A later explicit check can reattempt materialization only.

The check is bounded by the supported batch size, a 15-second timeout per GET,
1,024 recognized descriptors per response, and 64 retained observation commands.
The existing transport's response-byte behavior is unchanged; this is not a
new byte-limited HTTP client. After the command limit, the local-disposition exit
remains available and no old receipt is evicted.

A restart does not automatically requeue an accepted check. Repeating that
request ID retrieves its existing disposition, not a new queued read. After
inspection, a new explicit check uses a fresh ID and the current revision.
A queued record is therefore not a promise that its read completed.

### Record a local disposition

```http
POST /api/jobs/<job-id>/dispose-mixed
Content-Type: application/json
Origin: http://127.0.0.1:8191

{"request_id":"operator-dispose-0001","expected_revision":"<64 hex characters>",
 "reason":"Keep the known result and preserve the unresolved tail.",
 "acknowledge_unknown":true}
```

The acknowledgement must be literal JSON `true`, not a truthy string or number.
The reason is required and bounded to 1,000 characters. A queued/running check
blocks new disposition commands. This action needs no live worker or backend
because it changes only local records. One atomic `state.json` publication is
the commit point; memory is updated only after success. Original `recipe.json`
and `workflow.json` bytes are never rewritten by either command.

A mixed-observation error uses the same state-only publisher, including when
Workspace indexing fails. It never falls back to the general job serializer,
which also rewrites source files. A causal worker test retains non-canonical
original JSON bytes through this failure. Secondary persistence failure still
uses the existing non-durable worker alert and never terminates the consumer.

The existing `abandonment` field records `basis: mixed_batch_unknown`, the
accepted prefix, pending hash, reason, request identity and local timestamp,
with `remote_cancelled: false` and `new_work_authorized: false`. The pending
marker is **not** deleted. Revisions also bind known graphs; a changed disposed
record cannot certify an owning project's reconciliation.

For a linked legacy comparison, **every** mixed stage must have a matching local
disposition before `can_reconcile_batch` is true. The existing
`POST /api/production/<id>/resume` then performs one idempotent local project
write and records `batch_terminal_reconciliation`. Its HTTP 202 response does
not imply queueing: inspect the returned failed project state. It preserves
plan bytes, root reservations, time accounting and stop/continuation history.
The stale-dispatch guard performs this reconciliation before preflight or clock
entry and prevents any later stage from being created.

Live backend queue/process interlocks still apply after abandonment. A local
label does not prove that ComfyUI is idle or make it safe to terminate a process.
Existing #110 known failed/partial reconciliation remains separate, and ordinary
observation still rejects any unknown pending tail.

## Operator and agent use

In Create's recent run card, open **Recover mixed batch**. Review the known,
unknown and never-submitted parts; choose **Check known batch receipts** for an
explicit read. Inspect retained outputs separately. To stop local recovery,
enter a reason, acknowledge unresolved remote outcomes and choose **Abandon
remaining batch locally**. A linked Production project then offers
**Reconcile outcome only**. Starting a repair remains a separate action.

The browser serializes commands per job and retains an unconfirmed request's
exact identity and payload for a manual retry within that page session. It does
not blindly retry. Definitive 4xx errors permit a fresh command after refreshing
evidence. A page reload retains durable server receipts but does not persist
unsent form text or the browser's request cache. Agents must retain their own
request IDs/payloads and inspect the job after a lost response.

An unrelated Gallery rerender preserves an open same-revision reason/checkbox
draft. A changed revision invalidates that acknowledgement. HTML is escaped;
no source metadata becomes executable UI or generation instructions.

## Verification and boundaries

Run from the repository root:

```sh
python -m unittest discover -s tests -p 'test_mixed_batch*.py' -v
node tests/mixed_batch_frontend.cjs
python -m unittest discover -s tests -p test_production_terminal.py -v
python -m unittest discover -s tests -p test_worker_recovery.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
python tests/mixed_batch_browser.py --out .runtime/mixed-batch-browser
```

The initial baseline ran 1,573 tests with 15 skipped and passed. The focused
candidate initially had 34 cases: a real three-item run with a simulated accepted/lost
second response, restart/command replay, exact history IDs, malformed history,
write/index failures, stale dispatch/in-flight state, concurrency, command caps,
Workspace/output preservation, project budget/time isolation, live-queue guards,
actual shared-worker dispatch, real loopback HTTP routes and shipped JS handlers.
Causal tests failed before their corresponding fixes. After integrating
`f128385`, the full local suite passed **1,640 tests: 1,624 passed, 16 skipped**
(115.394 seconds). Existing fixture diagnostics, Pillow deprecation and an
unclosed test-socket warning remain visible; this is not a warning-free claim.
The two core projection/restart cases also fail on that unpatched newer main.
Hosted Windows/Linux and browser results are recorded at the final PR head.

The Chromium fixture serves the actual Studio frontend, exercises the real
recovery commands/Production/file store, and supplies synthetic Comfy/catalog
responses. It consumes the shared queue deterministically; a separate regression
exercises the actual worker dispatch loop. Screenshots cover 1440px and 390px;
keyboard actions, required acknowledgement, same-revision draft preservation and
no unexpected mutations are asserted. Local navigation is blocked by container
policy (`ERR_BLOCKED_BY_ADMINISTRATOR`), so a local browser pass is not claimed.
The existing Production storage workflow runs the fixture in hosted Chromium.

The first hosted run passed all 1,640 tests (38 environment-dependent skips),
then exposed a real pointer obstruction: in the two-column layout the sticky
recipe picker painted above the later full-width Recent runs row. The recovery
button was visible but not pointer-reachable. The fix gives that results row
its own stacking level at the existing full-width breakpoint, matching the
existing saved-setup row treatment. The browser test now records the actual
center-point hit target before clicking; it does not hide the picker, force a
click, or replace pointer acceptance with keyboard-only execution. This failed
run published no feature source. Final follow-up results are in the PR record.

No GPU generation, new models, installed package changes, owner runtime/config
changes, new native-editor evidence, artistic acceptance or licence decision
was performed. `HUMAN_TODO.md` remains untouched. This implements software
recovery acceptance for #187; the broad oldest issues stay open at their actual
workstation and creative boundaries.

## Primary source review

Reviewed 13 September 2026, for history shape rather than installed-version
certification:

- [ComfyUI PromptQueue history and ExecutionStatus](https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py).
- [ComfyUI execution worker status publication](https://github.com/Comfy-Org/ComfyUI/blob/master/main.py).
- [ComfyUI exact history-ID route](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py).

These sources do not establish the owner's installed runtime revision. Fixtures
assert explicit success/error evidence and retain unsupported/malformed history
as unknown rather than assuming compatibility with every custom node/runtime.

## PR review and complete browser integration

PR #224's normal checks exposed a second layout case after the initial browser
proof: raising the Gallery above the sticky recipe picker made the shortlist's
**Next suggestions** button unclickable. The initial stacking-only change is
replaced, not layered with another z-index. At the existing 1480px breakpoint,
where Gallery spans the picker column, the picker remains in normal document
flow. The wider three-column layout retains its existing sticky behavior. Both
the shortlist's native clicks and mixed recovery's pointer/keyboard controls are
required; the mixed fixture additionally checks non-overlapping panel bounds at
1440px, 1100px and 390px. No force-click or hidden-UI workaround is used.

The review also identified startup source rewriting: `_load_jobs()` used the
generic serializer for an interrupted accepted mixed observation. A causal test
failed for queued, running and uncertain records, losing noncanonical original
bytes and a retained recipe extension. Startup now publishes only `state.json`
for jobs retaining both known IDs and a pending marker, including malformed mixed
records that must remain held. Source bytes and extensions, pending intent, known
IDs and command history remain intact. Restart does not enqueue a read; repeating
the original command ID retrieves its state. Another test injects a locked
startup state write and verifies that all original files remain unchanged.

The final review checkpoint has 37 focused mixed tests. Final full-suite and
hosted-browser results, the exact source identities, and the earlier failed
browser run are reported on PR #224 rather than treating a prior passing run as
proof of this corrected integration.
