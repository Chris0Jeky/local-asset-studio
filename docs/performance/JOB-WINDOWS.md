# Optional job-bound resource windows

14 September 2026. Implementation increment of #302 under #172. Builds on merged
#300/#310, the existing `resource_probe` producer and `performance_history` reducer.
This records evidence for generations already authorised through Studio. It is not
a benchmark runner, new queue, admission policy, cache purge or performance claim.

## Operator path

The default is disabled. To opt in on a configured machine, add this block to its
ignored `config/local.json`, then reload Studio through the established safe idle
restart procedure. Do not restart a busy or uncertain backend to enable telemetry.

```json
"performance_telemetry": {
  "enabled": true,
  "interval_seconds": 5,
  "max_samples": 120
}
```

The example configuration leaves `enabled: false`. Interval must be finite, 1–60
seconds; count must be an integer, 1–120. Unknown enabled settings are refused by
the observer without changing a generation outcome. Disabled operation performs no
telemetry observation, source Git query or sidecar creation.

Prepare and run an ordinary job or approved Production comparison through existing
commands. Inspect `GET /api/jobs/<job-id>/resources` on the loopback Studio service.
The GET does not probe ComfyUI or modify files. It returns a maximum of eight windows,
current job status separately from the historical window result, and
`execution_authority: false`. The existing Host restriction and `Cache-Control:
no-store` remain in force; unknown jobs return 404.

No browser page or poller is added. Raw sidecars live beside the existing run:

```text
experiments/runs/<job-id>/resources/01/
  manifest.json
  samples.jsonl
  events.jsonl
  result.json
```

`resources/` inherits the ignored run storage, not a new authoritative database.
The existing `summarize-resources.py` can independently reduce `samples.jsonl`.
Do not publish raw local receipts without inspecting them for private information.

## Recording and ownership

`Studio._run` opens an optional `job_resources.observe` context after saving the
existing waiting state. The sole generation worker records queue-ready, actual
submission intent, acknowledged prompt ID, history receipt and worker-return events.
Intent and acknowledgement follow their corresponding existing durable job writes.
Telemetry does not grant consent, refund reservations, alter the recipe or retry.

Samples occur before the fresh pre-submit admission check, on opportunities in the
existing history loop, and once on worker return if sampling had started. They are
completion-spaced, synchronous and nonoverlapping. There is no timer, separate
thread, new `/object_info` call or change to the real Comfy queue. A long network
operation or model stage can leave a sampling gap. Queue refusal has zero samples.
The producer uses its existing bounded read-only `/system_stats` request plus host
counters and explicitly nominated process IDs.

The backend identity reuses BackendManager's configured executable/entry/cwd/listener/
argument matcher and verifies a fresh matching listener after reading arguments.
Identity is checked before and after a sample; changed or newly unknown identity
stops sampling and discards that sample. Missing identity stays explicitly unbound,
not a process lease. The manifest retains profile and argv hashes, PID and creation
time, not argv strings or absolute paths. Creation-time resolution, process changes
after the final check, missing process identity and source-file races remain limits.
The independent #319/#321 profiler correction protects PID attribution inside the
sampler itself; both changes should be deployed together for strongest observation.

## What is bound, and what is not

The manifest binds job ID, window ID, preset, prepared graph hash, controls hash,
batch count, source-file hashes, optional Git HEAD, configuration hash and observed
backend identity. Git/source observations describe files on disk, not proof of the
running interpreter's bytecode or a clean checkout. Exact submitted graphs have
separate hashes per acknowledged batch index; the prepared graph is not confused
with its seed-adjusted executions. Existing recipes still retain full controls,
reference transforms, graph and prompt IDs.

For actual associated Production attempts, verify project, immutable plan digest,
unique stage/job relation, real stage graph digest, preset and backend URL/root.
Retain existing model/input hashes, byte counts, plan/bundle/schema identities.
They are labelled `bound_preflight`: telemetry never rehashes model weights or
claims a current package audit. Ordinary standalone jobs remain `not_bound` for
model/input pins; it does not fill gaps with catalog filenames or other jobs.

Cold process, cold model, warm model and model-switch conditions stay `unknown`.
They require explicit benchmark starting-condition evidence, not inference from
file labels, first job, or same model name. Driver/OS/GPU UUID, full custom-node/
package revisions and byte-verified standalone input/model binding remain #302.

## Time and memory semantics

The result includes the existing reducer's sampled extrema/coverage; count-complete
is not peak-complete or a successful generation. RAM, Windows commit, process memory,
GPU device counters and Torch allocator counters remain distinct. Observations cover
the shared host/backend, not allocations owned exclusively by this job.

`worker_observation_seconds` starts at observer construction after the initial job
save and ends at result construction. It includes waiting, observed requests and
indexing, not just GPU work. `retained_job_elapsed_seconds` copies the existing
job field only where valid. `overhead_seconds_observed` accumulates observer setup,
events, sampling and history processing; final summary reduction/publication is not
included. It is not a full instrumentation-cost benchmark or a hard deadline.

An engine total is derived only from exactly one matching `execution_start` and
subsequent matching success/error event with ordered finite millisecond timestamps
in the retained Comfy history. Duplicate, conflicting, reversed, missing or wrong-
prompt events leave it null. The source is named. Individual load/encode/sample/
decode/export durations remain null; polling timestamps cannot identify phases.

A real owner-host baseline is still required to assess observer overhead and useful
sampling intervals. The existing producer's socket waits and bounded body do not
constitute a hard deadline over every OS/header/filesystem operation.

## Persistence, failure and recovery

Each new window claims one of eight fixed directories exclusively. Each raw line
is at most 16 KiB; each raw file at most 2 MiB; each JSON document at most 128 KiB;
max samples 120; events 160. No eviction, overwrite, unbounded replay, recursive
history store or automatic cleanup. The eight-slot ceiling bounds new storage per
job, not total retained jobs; general history retention remains #177.

Metadata/results are written to exclusive temporary files, then hard-linked to
publish without overwriting a destination. Files are flushed/closed, not advertised
as universally power-loss durable. Hard-link unsupported/disk-full/permission errors
retain partial sidecars and print only a bounded diagnostic. Telemetry failure never
changes a completed job, discards a known prompt or changes Production reservations.
A partial raw line can invalidate the summary without changing the job outcome.

Read inspection checks fixed slot IDs, manifest/result identities and the recorded
manifest/raw hashes. `finalized` means integrity-checked recorded evidence, not job
completion or authentication. Missing result means `not_finalized`; corrupt/mixed/
linked records report `corrupt` or `unavailable`. Linked roots/files are refused,
but this is not an atomic defence against adversarial concurrent filesystem swaps.

Initial dispatch only is instrumented in this slice. Startup and `_resume` do not
create windows or backfill timings. A later resumed completion can coexist with the
original uncertain window; the GET exposes both historical and current statuses.
Never reinterpret that original window as completed or resubmit to obtain telemetry.

## Verification, reconciliation and rollback

```powershell
python -m unittest discover -s tests -p "test_job_resources.py" -v
python -m unittest discover -s tests -p "test_resource_probe*.py"
python -m unittest discover -s tests -p "test_performance_history.py"
python -m unittest discover -s tests
python scripts/validate-repo.py
```

32 focused tests exercise actual Studio runs/recipe persistence, real Production
SQLite attempts/reservations, an actual loopback HTTP handler, interrupted evidence,
identity races, sampled-byte/event limits, loss/OOM and write faults. Sensors/runtime
responses are synthetic and threads disabled except the explicit HTTP test server.
No owner-host/model invocation is part of this evidence.

Recovery found the preceding compressed transport truncated. Its complete recorder
prefix was inspected but its missing tests/docs were not assumed valid. Sixteen
new tests first failed on absent functionality. Review then reproduced/corrected
fresh-listener verification, stage-graph verification, reversed engine events and
legacy two-argument history compatibility. Later tests caught Boolean identity
aliases; a public-Projection fixture error was corrected separately, not called a
product defect. Exact full-suite/hosted results are recorded on the PR.

Rollback: disable telemetry for future worker invocations at a safe Studio reload;
retain existing sidecars and authoritative recipes. No Comfy model cache, runtime
flag, browser state or job record needs restoration. q-7/q-25 owner reviews remain
unchanged. #302 stays open for controlled paired execution, more complete identities,
real phase events, resumed windows and a finite Windows/RX 9070 XT baseline.
