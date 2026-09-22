# Observation state publication (#703, #716)

## Scope

Ordinary and stopped-tracking Resume observation own retained prompt IDs. Each publishes a
prospective `state.json` before changing the live job or adding one `observe`
queue item. Recipe/workflow bytes, IDs, resource holds and submission authority
are unchanged. The command remains serialized by the existing Studio lock.

`app/observation_state.py` is the scoped publication primitive. The historical
`Studio._write_json_atomic()` helper, Stop tracking itself, mixed-batch writes,
backend state, abandonment and other save paths are **not** changed. Their wider
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
