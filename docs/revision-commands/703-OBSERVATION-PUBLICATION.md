# Observation state publication (#703, #716)

## Scope

Ordinary and stopped-tracking Resume observation own retained prompt IDs. Each publishes a
prospective `state.json` before changing the live job or adding one `observe`
queue item. Recipe/workflow bytes, IDs, resource holds and submission authority
are unchanged. The command remains serialized by the existing Studio lock.

Stop tracking and local abandonment also use `app/observation_state.py` for their
state-only operator dispositions. Neither command queues work or cancels a remote job.
The historical `Studio._write_json_atomic()` helper, mixed-batch writes,
backend state and other save paths are **not** changed. Their wider
durability review remains open under #716; the umbrella remains open.

## Publication and failure protocol

The publisher serializes finite JSON within a 16 MiB encoded budget, exclusively
creates a same-directory temporary file, writes and flushes it, synchronizes its
file descriptor, then replaces the state path. The containing directory is
synchronized where the platform contract below requires it. Only a normal return
permits the command to publish the prospective job and enqueue observation.

**Exact readback is not proof of a successful durability barrier.** Every writer
exception propagates without changing live/queue state, even when replacement
bytes are visible. A later explicit Resume observation call republishes and
synchronizes before queueing once. There is no automatic retry or generation
replay. On restart, existing recovery retains prompt IDs, marks queued known
work uncertain and does not reconstruct a worker queue.

Cleanup is limited to the exclusive temporary file's recorded device/inode.
Pre-existing collision entries and substituted temporary-path occupants are not
removed. After successful replacement the old temporary pathname is no longer
owned. Cleanup failure is attached to the original exception instead of hiding
its cause; an orphan can remain for inspection. This is not a general defense
against malicious cross-process filesystem races or a multi-file transaction.

## Platform evidence, not a physical-media guarantee

- POSIX: complete file flush/fsync, successful replacement and successful parent
  directory fsync are required. Directory open/sync failures propagate rather
  than being treated as evidence of success. The descriptor is always closed.
- Windows: complete file flush/fsync and successful replacement are required.
  This implementation does not open/fsync a directory there. The helper result
  explicitly reports `directory_synced: false`; it does not claim POSIX-equivalent
  directory-entry or power-loss durability. Stronger Windows crash durability is
  still a separate #716 concern, not silently attested by the command.

A return records completion of those software barriers, not a guarantee about
hardware caches, network filesystems or power-loss survival. The helper result
is internal, not an execution ticket, persisted receipt or new public API.

## Regression and continuation evidence

The two original #717 tests fail on the unchanged main server because neither
file-sync failure nor parent-sync failure is observed. They pass with the scoped
publisher. The earlier #705 post-replacement-readback test now requires an error,
unchanged live state and an explicit successful retry: its previous acceptance
rule was the defect, not a contract to preserve. The concurrent test still
requires at most one queued observation, with no backend calls.

Additional native-file tests exercise content-sync/replacement/barrier order,
write/replace/cleanup failures, temporary collisions and changed ownership,
finite/size validation, the explicit Windows boundary and directory-descriptor
cleanup. Restart and retained-reference-hold tests use the production methods.
The lightweight admission fixture now creates its retained state and delegates
to the real scoped writer rather than replacing that new seam with a mock.

Run `python -m unittest discover -s tests -p 'test_observation*.py' -v`, the existing
reference-hold, server, worker/submission recovery suites and repository validator.
The dedicated workflow runs the affected contract matrix on exact Ubuntu and
Windows heads. Complete hosted `Check studio` and review remain merge gates;
focused snapshot tests alone do not qualify the entire branch.

## Stopped-tracking Resume continuation

Both Resume paths now call the same scoped publisher. The stopped-tracking path
constructs the prospective resumed disposition and appended history first, but
publishes neither to the live job nor to the worker queue until the writer
returns. A failed attempt does not consume the live stop disposition or append a
live resume event. Explicit retry builds from the unchanged live history, not
from visible replacement bytes, so repeated or concurrent attempts publish one
new history event and one observation item. Stop-event tokens, retained prompt
IDs, submissions, recipe/workflow bytes and resource holds remain unchanged.

A failure after replacement can leave the attempted resumed history visible on
disk. This is not rolled back and is not evidence that the barrier succeeded.
Existing recovery loads that retained history, marks queued work uncertain and
starts no observation. Another explicit Resume republishes before enqueueing;
it does not fabricate another stop/resume event from the already retained history.
This is deliberately not a two-file consent transaction or a power-loss claim.

`tests/test_observation_tracking_publication.py` covers file and parent-sync
faults, replacement/cleanup, an exception after successful publication, barrier
ordering, multiple stop/resume cycles, concurrent retry, restart after uncertain
publication, worker/evidence refusals and byte-budget refusal. The retained-hold
fixture seeds the existing stopped job's state before exercising Resume, just
as real job creation does. It does not replace the publisher or relax admission.
The existing observation workflow discovers these tests on Windows and Ubuntu;
no additional workflow or production persistence owner is introduced.

## Stop tracking and local abandonment

These two operator commands use the same bounded publisher before changing the
live disposition or acknowledging success. Stop tracking retains known prompt IDs
and leaves the job uncertain. Abandonment retains its never-submitted versus
unknown-outcome basis, explicit acknowledgement, receipts and reservations. The
commands write only `state.json`; recipe/workflow bytes and provider authority do
not change. The global writer and restart-normalization paths remain separate.

If publication raises after replacement, memory remains unchanged and the visible
attempt is not rolled back. A subsequent explicit same-reason retry preserves its
event ID and timestamp only if the entire retained state equals the candidate
state with that identity. A stop retry also requires the exact prior history and
matching final event. Historical stopped entries under a current resumed
disposition are not reused: a new stop creates a new event. A different reason,
invalid identity, malformed/oversized state or other candidate mismatch refuses.

Reconciliation is a bounded strict read, not evidence that synchronization worked.
Even when the bytes match, the explicit retry republishes through all required
barriers before updating memory. Repeated barrier failures retain one attempted
identity without acknowledging success. Existing acknowledged same-reason calls
remain idempotent. Restart loads the retained identity and queues nothing; the
historical restart normalization writer is not migrated or given a stronger
durability guarantee by this change.

`tests/test_operator_disposition_publication.py` covers both dispositions, including
never-submitted and unknown-outcome abandonment; pre-replacement failures,
post-replacement errors, repeated failing barriers, same/different reasons,
concurrent callers, prior stop/resume history, restart, malformed state, identity
validation and global-writer exclusion. The first eight regression methods caused
31 assertion failures on the unchanged production implementation. The dedicated
observation workflow runs the new suite on both Windows and Ubuntu. #716 remains
open for multi-file saves/restart normalization, runtime/backend and production
owners, lower-authority metadata and stronger platform qualification.

## Put away (#940)

`POST /api/jobs/<id>/put-away` with `{"put_away": true|false}` publishes through the
same bounded writer and changes exactly one field: it adds or removes `put_away_at`.
Status, message, prompt IDs, submissions, outputs, reservations and tracking stay as
recorded; nothing is queued, submitted, resumed or cancelled. It is accepted only for a
settled failed, partial, abandoned or tracking-stopped uncertain job with no unknown
pending submission; an uncertain job keeps its resume path and must be stopped first.
Bringing a job back is refused only while the job is active again. The job snapshot
derives `put_away`: an owner put-away counts only while the job stays eligible (a
resumed job reappears), and a stopped-tracking uncertain job counts as put away with
`put_away_basis: "tracking_stopped"` without any new record, so Stop tracking alone
takes it off the Overview desk; Resume observation brings it back. The Create Problems
panel shows the newest five open problems, a count of the rest, and a
"Show put away (N)" toggle. `tests/test_job_put_away.py` covers it.
