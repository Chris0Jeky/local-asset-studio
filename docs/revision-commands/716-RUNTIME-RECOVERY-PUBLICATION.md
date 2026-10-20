# Runtime recovery publication (#716)

## Scope and cause

`RuntimeRecovery` owns `.runtime/runtime-recovery.json`. Its former `_record`
changed memory before using the historical rename-only JSON writer, then appended
a diagnostic log. Reset and healthy observations also removed startup/breaker
fields before publication. A write error could therefore expose an uncommitted
observation or acknowledge a reset that had not completed its required barriers.

Simply moving the memory update later would introduce a more serious failure:
recovery launched a runtime before charging its attempt. A failed terminal write
would leave the old allowance available on the next monitor pass. The recovery
owner now publishes an attempt intent before its existing launcher can run.

`app/recovery_state.py` is specific to this owner. It does not replace
`Studio._write_json_atomic`, BackendManager's ownership protocol, ordinary job
saves, Production materialization or any other persistence owner. #716 remains
open for those remaining domains and stronger Windows directory durability.

## Publication and launch ordering

1. The existing opt-in, selected-profile, current endpoint refusal, exact process,
   shared backend state, GPU lease, fresh-work, readiness and attempt-limit checks
   still govern recovery. The final predicates remain under the Studio lock.
2. Under that same lock, construct a unique `last_attempt` with a version, UUID,
   selected backend, attempt number and timestamp. Publish `launch_pending: true`
   and charge the attempt through the required barriers before calling the
   existing `BackendManager.launch_recovery` once.
3. Its existing `on_spawn` callback captures the exact returned process PID before
   pidfile work. The callback adds only observed evidence to a private pending
   record. It grants no further launch authority and performs no runtime action.
4. After the launcher returns, publish the startup PID/time and
   `launch_pending: false`. Only a normal publication return commits that record
   to live state. A successful same-process terminal publication preserves the
   previous bounded retry policy if a later observation proves the process absent.
5. Any intent, launch or terminal-publication error holds further automatic
   attempts. Later reconnecting, leased, other-backend or monitor-error records
   preserve the pending identity, charged allowance and observed PID. A fresh
   healthy observation or explicit Reset recovery must successfully publish before
   this process releases its hold. Neither operation discards `last_attempt` or
   retained legacy attempt evidence.

The state publisher encodes finite JSON within **128 KiB**, creates a same-directory
temporary file exclusively, checks the complete write, flushes and synchronizes
its contents, closes it, replaces the target, then performs the supported parent
directory barrier. The budget covers this small observation/attempt record; it
does not constrain recipes or workflow graphs. Unknown bounded JSON metadata is
retained. Live state and log publication follow a normal return, with no readback
promotion after an error.

Cleanup checks the temporary file's recorded device/inode before removal. It
preserves collisions, substituted occupants and a new occupant of a consumed
temporary name. Cleanup failures are attached to the primary exception; remaining
temporary evidence is not automatically swept. Temporary-file or directory-close
failure does not mask an earlier write, flush or synchronization failure.

## Failure evidence and authority

| Boundary | Live observation | Retained evidence and next action |
| --- | --- | --- |
| Intent write/flush/file-sync/replacement fails | Previous committed record | No launcher call. This process holds further attempts; inspect and explicitly reset or obtain fresh healthy publication. |
| Intent replacement is visible but parent sync fails | Previous committed record | Visible pending intent is unconfirmed. Later polls preserve it, and restart holds it. |
| Launcher throws before callback | Charged pending intent | Spawn outcome is not inferred from an exception. Preserve the intent and inspect. |
| Launcher throws after callback or pidfile work | Charged pending intent | The snapshot retains the observed PID; the next successful diagnostic publication retains it on disk. No second automatic launch. |
| Terminal record fails before replacement | Charged pending intent | Retain the observed PID and uncertainty. No second automatic launch. |
| Terminal replacement is visible before an error | Charged pending intent | Readable startup bytes do not acknowledge the operation. Restart treats the retained attempt as historical. |
| Reset or fresh-health publication fails | Previous committed record | No reset acknowledgment or allowance release. Visible cleared fields still retain the last attempt or original legacy evidence for conservative startup. |
| Log append fails after state publication | Newly committed record | Surface `log_error`; do not undo the state or turn a diagnostic failure into another runtime launch. |

## Startup and inspection

Only a missing record is first use. Enabled recovery preserves an unreadable,
malformed, oversized, non-finite, duplicate-field or invalid-attempt record and
reports inspection required. It does not replace it with an empty allowance.
Attempt counts must be integers from 0 through the supported configuration maximum
of 10; retained timestamps, PIDs and versioned attempt evidence are validated.
Reset refuses to overwrite invalid retained bytes. The remedy names the record:
stop Studio, retain copies of `runtime-recovery.json` and `runtime-recovery.log`,
inspect the runtime, then repair or move the invalid record before restarting.

A new enabled Studio treats any saved `last_attempt`, `legacy_attempt`, pending
intent, startup PID, nonzero attempt count, or launching/startup status as
historical evidence requiring a hold. Even a saved healthy/reset record with
attempt history cannot prove to this process that its previous writer completed
every required barrier. Saved health first appears as checking; a current
unsuccessful probe exposes the held breaker. A current healthy observation or
explicit Reset recovery must publish successfully to release that hold. Both
retain the last attempt's identity and observed PID.

Old-format records without `last_attempt` preserve their recognized original
fields in `legacy_attempt: {version: 1, evidence: {...}}`. The evidence contains
the saved status and attempt count plus any recorded startup PID, startup time,
breaker deadline, pending flag and update time. No UUID, backend, PID or attempt
number is invented. The captured fields precede startup health normalization or
any observational status update. Every later candidate, including reset and
healthy release, retains them; they are validated on the next read and recognized
as historical evidence even if the current status is healthy or idle with zero
attempts. A visible reset/health replacement followed by a parent-barrier or
post-replacement error therefore cannot replenish legacy allowance on restart.
Constructing this historical marker in memory is no acknowledgment that its
publication or any earlier writer's barriers completed.

**Compatibility cost:** restarting Studio while a previously recovery-started
runtime remains offline now requires inspection and Reset recovery before another
automatic attempt. Restart while the selected runtime is healthy clears the hold
through a fresh successfully published observation. This deliberately avoids
reconstructing launch authority from readable terminal bytes. Legacy records with
no attempt evidence retain their existing checking/observation behavior. A legacy
count-only, pending-only or launching/startup-status-only record incurs the same
restart hold; its preserved fields express that uncertainty without claiming a
known launched process.

A disabled monitor still does not restore saved enabled status or startup identity
and does not autostart. Its public Reset method refuses before reading or writing
the state or log, preserving valid, malformed and unreadable records alike.
`POST /api/runtime-recovery/retry` returns the existing **400** error response with
the disabled message; it cannot bypass this refusal through the HTTP route.
Enabled Reset still returns **202** only after successful publication, and the
existing same-origin guard still applies.

Reset only clears this recovery owner's allowance/hold. It does not adopt a saved
backend selection, resolve another Studio's switch, stop a process, release a GPU
lease, cancel or enqueue work, or submit a prompt. A pending or stale BackendManager
selection still has its existing independent refusal and explicit remedy.

## Diagnostic log and platform limits

State commits before `.runtime/runtime-recovery.log` is appended. Log entries
include the charged attempt number, latest attempt identity and original legacy
evidence when present.
Deduplication advances only after the complete line is written, flushed and closed.
A log failure is reported in `snapshot().log_error`, and a later observation may
try its diagnostic append again. A partially written line or duplicate after an
uncertain close is possible; this log is not an exactly-once journal or launch
ticket. Its failure never reverses already committed state. A second failure while
the monitor reports an observation error still reaches the existing bounded sleep.

POSIX requires content fsync, replacement and parent-directory open/fsync. Open,
sync and close failures propagate. Windows requires content flush/fsync and
replacement and explicitly returns `directory_synced: false`; this owner claims
no Windows directory-entry barrier. Existing bounded transient replacement retries
retry only the same owned temporary-file replacement, never a runtime launch.
These are OS operation guarantees, not physical-media or power-loss guarantees.
Synchronizing the record's parent does not make creation of all ancestor
directories, its diagnostic log or backend pidfiles a single transaction.

The existing per-instance recovery and Studio locks serialize local callers.
This is not a universal runtime-launch lease or a defense against noncooperating
writers. Do not run competing recovery monitors against one workspace. Default
port ownership and the explicit preview autostart opt-in are unchanged.

## Proving checks

`tests/test_runtime_recovery_publication.py` exercises the real recovery owner and
native temporary files with inert launcher/transport fixtures. On unchanged
production, its first 18 methods produced 26 assertion failures and no errors.
The focused writer extension separately demonstrated seven failures for incomplete
writes, owned-temp cleanup and primary-error preservation before those fixes.
The later log-identity and temporary-close regressions each demonstrated one
assertion failure before their respective fixes.

Independent review identified two more causal transitions: legacy release could
erase every recognized historical field before an unconfirmed replacement, and
disabled Reset could overwrite saved bytes that its constructor had not read.
Seven new owner methods on the reviewed candidate produced **52 assertion
failures across 30 tests**, with zero errors; the legacy-reader schema regression
produced **13 assertion failures in one test**, with zero errors. They cover
successful legacy reset/health, native parent and post-replacement faults,
status-only observations, disabled valid/malformed/unreadable/missing records,
and the real retry route with an in-memory transport and its same-origin guard.
The corrected focused matrix contains **149 tests**: 54 recovery, 14 writer,
16 GPU lease, 47 backend safety, 12 startup interlock and 6 file replacement.

The dedicated `runtime-recovery-publication.yml` workflow checks out the actual PR
head on Windows and Ubuntu, then runs the recovery, writer, GPU lease, backend
safety, backend startup interlock and file replacement suites plus repository
validation. Native POSIX directory fault tests skip on Windows; the explicit
Windows limitation and post-replacement terminal/restart fault execute there.
Full `Check studio`, independently reviewed actual-head evidence and merge
qualification remain integration gates. No installed runtime, model, inference or
owner art/licensing action is exercised by this slice.
