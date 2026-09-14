# Optional observations attached to Studio jobs

This first slice of [#302](https://github.com/Chris0Jeky/local-asset-studio/issues/302)
connects the existing generation coordinator to the finite resource profiler and
[offline reducer](TELEMETRY.md). It adds no generation allowance, submission path,
automatic recovery, backend switch, runtime restart or model import.

Observation is **off by default**. These optional keys in `config/local.json` take
effect at the next normal Studio start:

```json
{
  "observe_job_resources": true,
  "resource_observation_samples": 120,
  "resource_observation_interval_seconds": 5
}
```

Keep the rest of the existing configuration. Samples must be an integer from 1 to
120; the interval must be a finite number from 1 to 60 seconds. Invalid options
disable observation. This implementation does not change the running Studio or
its configuration. Coordinate any eventual restart with its current owner and
preserve active jobs and the ComfyUI queue.

## What happens during a job

The normal queue and preflight checks run first. After the coordinator saves the
pending submission, it hands an immutable projection to the observer before the
existing `/prompt` request. Each actual expanded batch graph gets its own SHA-256.
The validated prompt response is recorded as a received response, before the next
core state save; that receipt does not claim the core save succeeded. The exit
event records the coordinator's status at that moment. A later outer error handler
can still change a running snapshot to uncertain.

One background observer handles file writes, process inspection and read-only
statistics requests. Completion signals stop and returns immediately. An in-flight
sample that crosses that signal is discarded. A stuck observer prevents additional
observers until it exits; it cannot prevent the next generation. Sampling has a
finite count and does not refill after exhausting it. The helper can retain later
response/exit events until job exit or the four-hour-and-one-minute window ceiling.
It never starts a new window during Resume observation.

Telemetry exceptions do not change the job, its pending marker, known prompt IDs,
outputs, budget or recovery behavior. Disabled observation does no hashing, file
work, process inspection, HTTP or thread creation. The enabled submission path
does bounded event projection and locking; background I/O has no completion join.

## Retained evidence

Files live under the configured experiments root, defaulting to
`experiments/resource-observations/observation-00/`. The allocator exclusively
reserves one of 32 fixed slots. It refuses new observation when full, preserves
existing files and rejects unknown entries or linked directories at the slot root.
Move whole receipts explicitly when making space; there is no automatic deletion.

| File | Meaning |
| --- | --- |
| `context.json` | Job ID, first intent, graph/control/reference-manifest hashes, capture-time source facts and explicit unknown identities |
| `events.jsonl` | At most nine source events: intent and received response for each of four admitted batch outputs, plus coordinator exit |
| `profile.jsonl` | Existing `studio.resource-profile/v1` envelope; at most 120 samples and 4 MiB |
| `summary.json` | Existing reducer result, including exact raw receipt hash, observed counts, missing counters and sampled extrema |
| `result.json` | Stop reason, captured runtime binding and byte counts/SHA-256 hashes tying the other four files to this job |

Each non-profile file is capped at 256 KiB, each event at 8 KiB. New writes are
bounded to at most 5 MiB per slot (160 MiB for 32 slots, excluding filesystem
overhead). These limits are retention bounds, not a disk-space reservation.
Hashes identify bytes; they do not authenticate the producer or authorise work.
Keep all five files together and check their result hashes before associating a
summary with a job. No receipt is added to authoritative `state.json`, and there is
no new HTTP projection or browser attachment; that remains with #175.

To inspect the raw profile independently, use the existing command with the actual
slot path:

```powershell
python scripts/summarize-resources.py experiments/resource-observations/observation-00/profile.jsonl
```

An early exit can leave a valid profile with zero or fewer-than-requested samples.
Completed JSONL records remain usable by the reducer after interruption. A torn
record is rejected and retained; it is never silently repaired. File or disk
failures can leave missing/partial context, events, summary or result files. Such a
set is incomplete job evidence even if the raw profile alone reduces successfully.
No receipt, or a missing final result, means observation unavailable/incomplete.

## Identity and interpretation limits

Before and after each ComfyUI statistics GET, the observer checks that the configured
listener still has the captured PID, process create time and command hash. A lost
bracket, process replacement, PID reuse, changed command, version or device layout
permanently removes ComfyUI counter coverage for that window. The observer never
rebinds. Initial process-counter attachment must also match that epoch. These are
non-atomic observations, captured after dispatch preparation; they do not attest
the exact process at dispatch or authenticate an endpoint.

The source receipt records Git HEAD and tracked-change status at capture. It does
not attest already-loaded Python code, untracked files or a clean checkout.
Graph hashes identify the expanded graph; control/reference-manifest hashes do not
prove installed model, adapter or input-file contents. Those content identities,
actual output geometry, precision, approval attestation and cold/warm state remain
explicitly unknown. These receipts are not yet sufficient to qualify matched
benchmark trials.

The coordinator's elapsed value, when available, includes queue waiting. Sample
duration and sample-window span are not inference, encode, load or decode timing.
The sample count can be complete while some counters remain unknown; sampling can
miss peaks. Resource observation, successful generation, art acceptance and model
licensing remain separate facts.

Executed verification for this slice uses CPU-only synthetic fixtures: coordinator
success and dropped replies, state-write failures, four distinct batch graphs,
blocked sampling, partial receipts, retention/byte/event/time bounds and runtime
identity loss. No real Windows/GPU overhead, performance improvement, installed
runtime adoption, model execution or generation is claimed. Finite benchmark
planning/execution through the existing Production budget owner, complete trial
identity and an authorised real baseline remain open under #302.
