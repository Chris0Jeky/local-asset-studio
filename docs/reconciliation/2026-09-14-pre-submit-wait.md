# Release a blocked pre-submit wait

Issue [#253](https://github.com/Chris0Jeky/local-asset-studio/issues/253), under
[#10](https://github.com/Chris0Jeky/local-asset-studio/issues/10). Inspected base:
`20c46dd45044a6f9193b3e562df5bee4e5fc8912`, 14 September 2026.

## Reconciliation before changing the coordinator

The 01:23 UTC snapshot contained 71 open issues. The oldest remain #2, #3, #9 and
#10. Explicit isolated switching, source intake, model readiness, comparison
planning, reservation accounting and recovery already exist. #238's schema
capture/replay and #239's mixed-batch ownership guard have merged; their code was
not recreated. #2/#3 still need the specified workstation/creative comparisons,
#9 still needs complete source/runtime evidence, and #10 still needs its accepted
multistage demonstration. Software tests do not complete those larger issues.

#253 is a concrete remaining #10 defect: one generation waiting on another
client's ComfyUI work could occupy Studio's only consumer forever. Active CLI
wait work in #270 concerns *headless observation*, not this server-side admission
boundary. Active UI, repair intake, native dependency and image diagnostic PRs
were left with their existing owners.

## Behavior and architecture

Keep the existing single consumer and `_wait_for_queue` admission check. Bound
one invocation with a 60-second monotonic budget. Before each GET, calculate
remaining time; cap the socket timeout at `min(10, remaining)` and the following
sleep at `min(2, remaining)`. Check again after the GET: a late idle response
cannot authorize submission. Both `queue_running` and `queue_pending` must be
actual lists. Missing, malformed, or unreadable queue state is not idle evidence.

The 60-second value is a scheduling policy, not a model-performance measurement.
It allows brief existing work to finish, but yields rather than occupying the
only consumer for an entire unrelated render. There is no configuration/schema
migration, second worker, background retry service or remote queue mutation.

| Observation before any prompt POST | Local job | Owning comparison |
| --- | --- | --- |
| Valid idle reply within budget | Existing normal submission path | Existing running stage |
| Busy until expiry, or idle reply arrives too late | `not_submitted` | `interrupted` |
| Transport/decode error or invalid queue collections | `not_submitted` | `interrupted` |
| Known ID, pending marker, malformed submission evidence before entry | Entry refused | Existing recovery contract |

`_run` catches only the queue-observation exception at the pre-POST boundary.
The existing evidence predicate must still prove an empty submission history
before entry. After expiry, the recipe, graph, seed, bindings and reserved
attempt remain. No retry is enqueued. Later worker items can proceed on the same
thread. This is not remote cancellation and does not clear manual ComfyUI work.

A comparison becomes interrupted only when its job is explicitly
`not_submitted` **and** `never_submitted(job)` is true. An explicit Resume reuses
the already reserved deterministic stage/job after the existing recipe, backend,
model and storage checks. It neither refunds nor expands the reservation. Time
spent waiting remains governed by the existing comparison clock; the new queue
budget is not free time or a fresh experiment allowance. If that allowance is
exhausted, its existing explicit extension/review controls still apply.

## Operator flow

A blocked job first shows Waiting. On expiry or an unavailable queue read it
shows Not submitted, an explanation, and states that no retry was queued.
For a comparison, check the real ComfyUI queue and then explicitly Resume when
appropriate. For a standalone run, the existing Abandon local job action releases
its local record while retaining its recipe. Starting replacement work is a
separate user action. A malformed/unavailable queue never becomes permission to
run merely because its local job can be abandoned.

On restart, no work is submitted automatically. A persisted clean pre-submit
record stays recoverable. If writing the timeout result fails, the existing
worker failure containment remains in charge; the diagnostic is explicitly
non-durable. A retained on-disk `waiting` record with empty receipts can be
reconciled on restart. Do not describe failed persistence as a saved timeout.

## Limits

Python's [monotonic clock](https://docs.python.org/3/library/time.html#time.monotonic)
is used for elapsed differences. `urllib`'s [timeout](https://docs.python.org/3.13/library/urllib.request.html#urllib.request.urlopen)
applies to blocking network operations, not an absolute total-transfer timer.
The policy bounds poll starts, normal sleeps and socket inactivity timeouts; it
is not a hard 60-second wall-clock guarantee under a continuously trickling
response, blocked filesystem write, OS stall or suspended process. It does not
make the observed empty queue a lease: another client can enqueue afterwards.
The existing batch policy is unchanged; this check is before the first POST,
not a new inter-item admission mechanism.

## Verification and reproduction

```console
python -m unittest discover -s tests -p test_pre_submit_wait.py -v
python -m unittest discover -s tests -p test_submission_recovery.py -v
python -m unittest discover -s tests -p test_worker_recovery.py -v
python -m unittest discover -s tests -p test_production.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The new 13-method suite covers deterministic expiry, request-time/sleep accounting,
late replies, pending-only queues, malformed responses, transport/decode failures,
actual loopback GETs, a real consumer thread, restart, failed receipt persistence,
legacy no-replay holds and explicit comparison resume with unchanged reservations.
Only the Studio module's clock is replaced; the test does not certify a measured
GPU duration or global scheduling fairness.

The initial ten-method causal suite on original code completed with 19 failing
assertions/subtests, then passed after correction. Three more coverage methods
exercise the real thread, pending-only accounting and failed persistence. The
untouched full baseline ran 1,904 tests, 18 skipped, no failures. Final independent
branch and integration counts are recorded in the PR/CI rather than replacing
these historical checkpoint counts.

An initial red-test harness accidentally reset its synthetic clock on every
oversleep and recorded an unbounded request list. That harness and a concurrently
running baseline were killed (exit 137). The test was fixed to terminate after
two late reads; the completed red run and separate untouched baseline above are
the evidence used. This is not counted as a product regression or a successful
baseline. Deliberate storage-fault messages and existing warnings remain in logs.

The existing Linux/Windows Production storage workflow runs this test module;
no duplicate CI lane is added. No owner runtime, model, GPU job, database or
configuration was touched. q5's supplied authorization has its separate #277
change; q6's received feedback is tracked by #278. HUMAN_TODO is not modified or
re-asked. Rollback is the scoped code/CI revert; retain all run and project files.
