# Inspect a saved job resource observation

Implementation follow-up to #318 under #302. The existing recorder and its off-by-default
configuration remain unchanged. This command checks the actual saved sidecars before a
consumer uses their numbers; it does not sample resources, run a job or contact a service.

## Use

From the repository root, nominate one existing observation directory:

```powershell
python scripts/inspect-resource-observation.py .runtime/job-resource-observations/observation-00
```

The command prints an inspection report. Add `--output .runtime/inspection.json` to create
a **new** report file. An existing destination is never overwritten. It is safe to inspect
an old capture with Studio and ComfyUI stopped; no configuration or model files are read.

The successful report includes `result_sha256` and `job_id`. Later consumers can require
those exact values using `--expected-result-sha256` and `--expected-job-id`. A digest that
you capture independently anchors that specific result; calculating a new digest from a
replacement and accepting it does not establish that it is the original.

Python callers use `resource_receipts.inspect_observation(directory,
expected_result_sha256=..., expected_job_id=...)`. Both pins are optional for initial
inspection. `EvidenceError.code` is a bounded diagnostic. Missing `result.json`, or a short
`artifact_hashes` manifest that does not yet list all four named artifacts, is
`incomplete=True` (still writing — retry). A complete four-name manifest whose listed sidecar
is gone is `artifact_missing` with `incomplete=False` (`invalid`): a broken finished claim,
not an in-progress capture. CLI `integrity: incomplete` is not a reason to wait on a deleted
listed file. No exception message includes receipt content or the nominated path.

Exit 0 means the recorded artifact set passed these integrity checks and the report was
written. Exit 2 prints an `invalid` or `incomplete` JSON diagnostic to stdout and creates no
output file. Exit 1 means output could not be written; a storage failure may leave a partial
**new** report. Keep the original observation intact. There is no repair, retry or deletion.

## What is verified

The inspector reads exactly `result.json`, `context.json`, `events.jsonl`, `profile.jsonl`
and `summary.json`. It never follows filenames supplied by the artifact manifest. Each
non-profile input is bounded to 256 KiB; the raw profile is bounded to 4 MiB. Event lines
are bounded to 8 KiB and nine records. The existing reducer also enforces its 120-sample,
1 MiB-line, 16-process and eight-device limits. No directory-wide history scan is performed.

Files must be regular files in plain directories; links/reparse points, FIFOs, unexpected
manifest paths, oversized content and changed file identities are refused. Reads themselves
are bounded, not merely a preceding `stat`. The result bytes are captured again after
validation, and the other file identities/lengths/timestamps are rechecked. This rejects
ordinary concurrent modification, not a hostile filesystem race or an atomic cross-file
snapshot. OS/filesystem stalls do not have a portable hard wall-time bound.

The existing strict Studio JSON decoder rejects duplicate/reserved keys, nonfinite numbers
and excessive nesting. Hashes and byte counts in the result must match all four named
artifacts. Context, first intent and every event must name the same job. Indexed intents
and responses preserve ordering and exact graph/control/reference-manifest hashes. Response
hashes use the producer's ASCII-escaped JSON convention, including for Unicode prompt IDs.
Repeated responses and duplicate prompt identities are refused. A missing response is
`not_recorded`, never proof that the request was not submitted.

The stored summary must equal an **independent reduction of the captured raw profile**,
including numeric types. Changing a sampled maximum and rehashing the summary in result.json
cannot make that changed number agree with the raw evidence. A `true` substituted for count
`1` also cannot pass. Sample count/interval must match context limits; sample timestamps must
fall within the recorded observation window. Observable event/timestamp/identity conflicts
are refused rather than silently reconciled.

This directly addresses the #318 review follow-up: `summary_available` means file presence.
A torn summary can be present and hash-bound. The inspector does not reinterpret that
producer field as validation; only successful parsing and exact re-reduction set
`summary_verified: true`. It changes no legacy receipt or producer behavior.

## Reading the report

`studio.job-resource-inspection/v1` contains:

| Field | Meaning |
| --- | --- |
| `integrity: verified` | Fixed artifact capture, hashes, supported v1 structure and reduction agree |
| `result_sha256`, `artifact_hashes`, `job_id` | Exact supplied evidence identities, not authenticated origin |
| `profile_summary` | Recomputed sampled extrema and known/unknown coverage from the existing reducer |
| `submissions` | Ordered observed intents and received-response facts; absent response remains unknown |
| `finish_snapshot` | Coordinator status/elapsed value when its exit event was recorded, or null |
| `source_observation` | Capture-time commit/dirty observation and observer source hash; loaded-code parity stays null |
| `runtime_observation` | Recorded listener/process/profile bracket and loss state, or null |
| `warnings` | Incomplete sampling, missing exit, unresolved snapshot, bracket loss, early observer stop or index gap |
| `qualified_benchmark: false` | These v1 receipts cannot prove a matched causal benchmark |
| `execution_authority: false` | Inspection never grants submission, retry, recovery or lifecycle authority |

A fully verified artifact set can have zero samples, incomplete sampling, unavailable
counters, a missing finish event or an uncertain/running coordinator snapshot. These facts
remain visible. The coordinator event can precede its outer error handler's final state;
this is not a fresh authoritative job read. Elapsed coordinator time includes waiting and
is not sampling/load/decode time. Process working sets and device/Torch domains are not
summed. Sampled maxima may miss higher transient allocations.

Unknown model/input contents, actual geometry, precision, cold/warm conditions, loaded code,
final job state and inference-phase timings are explicitly listed as qualification gaps.
The v1 unknown fields cannot be edited into attestations while retaining v1 semantics.
Neither hashes nor agreement among locally supplied files authenticate their producer.
The inspector verifies only the captured self-consistent evidence (and any supplied pins),
not that the live machine still has those resources or that the job is owned by another store.

## Architecture, verification and next step

`app/resource_receipts.py` is a read-only consumer of #318's protocol. It reuses
`studio_workflow.core.decode`, the existing loopback URL contract and
`performance_history.summarize_resource_profile`. It does not import the recorder, server,
psutil or Torch and has no worker, queue, storage migration or network adapter. The thin
CLI handles report output; the inspection library writes nothing.

Tests create actual recorder output with injected synthetic sensors and source observations.
They also inject a real writer failure leaving a hash-bound torn summary. They cover external
pins, cross-job/mixed events, four batch graphs, Unicode identities, duplicate keys, corrupt
and oversized input, incomplete/unknown windows, links/FIFOs, disappearing files, result
replacement and no-overwrite/no-live-dependency CLI behavior. CPU fixtures are not GPU
performance measurements or owner-host acceptance. Exact-head results are recorded on the PR.

```powershell
python -m unittest discover -s tests -p "test_resource_receipts*.py" -v
python -m unittest discover -s tests -p "test_job_resources*.py" -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The next consumer is an explicit paired-observation report, not a second benchmark executor.
#302 retains full trial identity, Production-owned finite execution, measured overhead and
a real authorised Windows baseline. #175 owns future UI/API projection and #178 admission.
Rollback removes the optional consumer and its CI coverage without touching retained evidence.

Primary references: [Python JSON parsing](https://docs.python.org/3/library/json.html),
[file descriptors and stat](https://docs.python.org/3/library/os.html), and the existing
[recorder contract](JOB-OBSERVATIONS.md) and [summary contract](TELEMETRY.md).

## Native Windows and review corrections

The first Windows 3.12.10 run rejected valid captures before semantic validation.
A native probe using actual recorder output reproduced all three failures: path
`st_ctime_ns` equalled birth time, while descriptor `st_ctime_ns` equalled change
time; file identity, size, modification time and birth time agreed. A simpler
one-write file did not expose that distinction and was not used to dismiss the
failure. Capture now compares identity/size/mtime/birthtime across the two APIs,
and still compares the complete ctime-bearing signature before/after **within**
each API domain. It does not waive identity or modification detection on Windows.

The independent review also reproduced omitted `commit_at_capture` or
`tracked_changes` being normalized to null. Both keys must now be present; explicit
null remains a valid unknown observation. New causal regressions fail before these
corrections and pass afterwards. Final native results are recorded on the PR;
initial Windows failure is retained, not recast as a successful run.

Second review reproduced modification immediately after a guarded artifact read:
a later lstat could accidentally bind the modified file's signature to the old
bytes. The internal capture now returns its verified signature **with** those
bytes; the final recheck compares against that capture, not a later unrelated
lstat. The public byte-reader API is unchanged. The after-return append regression
failed before this fix; fault injection now wraps the extracted capture seam,
with the same mutation timing and unchanged refusal assertion.
