# Stop headless polling at its observation deadline

Issue #266. Inspected main `2f91421ecbe0e014cceef1074f4d79e4c57051df`;
tracked-source tree `25da90c8445bc5e94cc73fd814964563c256f102` was reproduced
before editing. This is CLI observation under #123/#175; neither broad
workstream is completed and the server's queue/recovery owners are unchanged.

## Reproduced behavior

The old loop checked elapsed time after a GET and slept for the remaining
interval, then issued another GET without checking time again. In a deterministic
0.2-second budget / 0.1-second interval case it polled at 0, 0.1 and 0.2.
Oversleep likewise triggered another poll after expiry. Each request retained
the full HTTP timeout even when almost no observation budget remained.

A later transport error also reused the earlier `main.result`, causing the
outer error handler to label the error `stdout_unavailable`. The received
response was real; the claim that stdout failed was not.

## Correction and error contract

A private `_wait_for_job` helper contains the polling loop and its last observed
job. It checks monotonic remaining time before every request, caps that request's
socket timeout to the smaller of configured timeout and remaining budget, and
restores the original client timeout on every exit. It does not create a new
transport, observer thread, cancellation endpoint or polling service.

| Outcome | CLI result |
| --- | --- |
| Budget expires between polls or during interval oversleep | `observation_timeout`, exit 4; no further GET |
| Socket timeout consumes remaining observation budget | Same timeout result; last received job retained, or `job: null` if none |
| Earlier socket timeout or other transport failure | Existing error exit 2, not a fictitious stdout failure |
| Received completed/uncertain/failed/partial/cancelled response | Exact response retained with existing exit 0/3/5 mapping, even when received late |
| `status` rather than `wait` | One ordinary GET; unchanged timeout and result semantics |

The timeout message states that observation stopped, not that the remote job
was cancelled. Only the original encoded job-ID route is read. No retry of a
write, replacement ticket, queue change or generation occurs.

## Proving checks

Eleven new tests include deterministic deadlines, oversleep, per-request timeout
caps/restoration, invalid inputs, early/late socket errors, terminal results and
real loopback HTTP. Before implementation eight assertion/subtest failures
reproduced the gaps. All eleven focused methods pass after the correction.
Timing assertions use an injected CLI clock rather than runner speed; the real
HTTP case forwards actual requests while recording urllib's timeout argument.

```sh
python -m unittest discover -s tests -p test_workflow_wait_budget.py -v
python -m unittest discover -s tests -p 'test_workflow*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Final full-suite and hosted Linux/Windows outcomes are recorded on the PR with
its source identity. Existing output-error handling, HTTP framing safeguards
and saved-run client protocols remain covered by their ordinary tests.

## Important boundary

`--seconds` now bounds new polling starts and the supplied socket inactivity
waits. It is **not a hard total-transfer deadline** for a peer continuously
trickling bytes, nor a guarantee against arbitrary OS stalls or delayed thread
scheduling. A complete late terminal response is still valid observed evidence.
A timeout record's nested job is the last observation, not a fresh claim about
current execution. Use a later explicit `status` or `wait` to observe again.

No owner runtime, configuration, model, database or HUMAN_TODO changes. No new
creative or licensing acceptance. Revert the CLI helper/call-site together;
there is no storage migration.

Primary references checked 14 September 2026:
[monotonic clocks and sleep](https://docs.python.org/3/library/time.html#time.monotonic),
[socket timeout semantics](https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts).
