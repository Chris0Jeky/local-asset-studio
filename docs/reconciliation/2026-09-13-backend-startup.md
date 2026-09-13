# Oldest-issue reconciliation: backend startup

Checkpoint: 13 September 2026, main `8f471d62a63c339429f95e6a4b55707e99949d8b`.
This is an offline implementation/evidence record, not a workstation deployment receipt.

## Start with issue #2, not a replacement backend manager

The oldest open issue is #2. Its original description is older than the code:
`app/backends.py` already implements explicit primary/HiDream/H3 switching, queue and
process-identity checks, retained startup records and backend-pinned observations.
`docs/HIDREAM.md` already records API/native visual workflows and two actual eight-step
Studio executions, including the reference-restyle prompt. Those features must not be
rebuilt or described as unimplemented.

The issue is not wholly complete. The documented higher-step same-seed comparison is
still unrendered, and the native transition crash / upstream warning must not be
converted into a success claim. Endpoint readiness, inference, art approval and terms
remain separate. Leave #2 open for that evidence.

Issue #3 is the next chronological open item. It is a controlled experiment backlog,
not authorization to call a mocked render an accepted character animation. Its actual
Qwen comparison, interactive Krita and target-engine checks need the configured
workstation and retained outputs; this pass does not manufacture those receipts.
`CURRENT_STATE.md` and `HUMAN_TODO.md` take precedence over old issue descriptions.

## Confirmed remaining switch defect

Explicit switching inspected listeners plus the PID from the last switch operation.
It did not reuse recovery's `configured_processes()` scan. A known launcher started
outside that operation can be alive before opening its port, including after Studio
restarts. Refused `/queue` plus no listener was then treated as absence. A switch could
stop the healthy family and attempt a second launch despite the first still starting.
A duplicate pre-listen process beside an already-ready target was also invisible.

The change reuses the existing exact-command scanner; it adds no scheduler, polling
loop, package mutation or alternate process-identity implementation. One observed
configured process must match the listener by both PID and creation time. Extra,
unbound or ambiguous configured processes refuse the switch while preserving them.
The check runs at request admission, after worker preflight, after the final idle
check before termination, and after the saved start intent before launching.

This is a bounded observation interlock, not an operating-system-wide atomic lock:
a manually launched process or direct Comfy job can still race after a final check.
Finish manual work before switching. The patch neither kills unbound processes nor
retries a failed/uncertain generation, and it never interprets a ready endpoint as
proof of model compatibility or artistic success.

## Reproducible offline proof

```sh
python -m unittest discover -s tests -p test_backend_startup_interlock.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The focused suite has 11 tests. Against the exact baseline `backends.py` blob
`bdb6c40812706194c79f0bd7240e5f492fc1d98b`, nine assertions fail; the manual-queue
and healthy-reuse controls pass. With the change, all 11 pass. Coverage includes
unrecorded target/other-family startup, duplicate processes beside a ready listener,
PID reuse, unknown identity, admission-to-worker and late-preflight races, failure
persistence, restart without a retained PID, healthy reuse and manual queue preservation.
Process and HTTP doubles are inert; no actual process is launched/terminated and no
`/prompt` request is made. Full-repository tests and validation run in the existing PR CI;
read that run's result separately from the focused local proof.

## Human / live boundary

No generated art was accepted and no choices in `HUMAN_TODO.md` changed. Its creative
choices are already answered; do not re-open them. The configured 64 GiB page-file
activation still requires the owner's saved-work Windows restart and a fresh headroom
check. No restart, dependency change, GPU job or workstation operation was performed
by this pass. An owner-run explicit switch with a deliberately delayed inert launcher
is a useful next validation; it is not claimed here.
