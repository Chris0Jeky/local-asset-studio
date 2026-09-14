# Saved inference traces: bounded offline inspection

Implementation slice of #364; source/architecture intake remains PR #365. This is
an executable reader for **already saved** traces, not a profiler attached to
Studio, a model runner, or a hardware-compatibility detector.

## Use

```bash
python scripts/inspect-inference-trace.py .runtime/short-trace.json
python scripts/inspect-inference-trace.py .runtime/short-trace.json --sha256 <exact-file-sha256>
```

The command writes a JSON summary to stdout. Exit 0 means this supported subset
was inspected; it does not mean a complete capture or a successful generation.
Exit 2 returns a fixed error code. Missing/unreadable/changed/non-regular files
use the existing `resource_receipts.read_evidence_file` boundary. Input files
are never modified, and no output files or directories are created by the CLI.
The reader inherits that boundary's conservative plain-directory/reparse checks;
it is not a sandbox against malicious concurrent filesystem changes.

## Supported contract

`schemaVersion: 1` object with a `traceEvents` array, as emitted by the inspected
PyTorch/Kineto producer. Only complete `ph: X` events in `cpu_op`, `cuda_runtime`,
`hip_runtime`, `kernel`, `gpu_memcpy` and `gpu_memset` contribute durations.
Begin/end spans, counters, flow edges, user annotations and unknown categories
are counted as ignored, not converted or guessed. Unsupported duration events
have their own count. Malformed recognized spans invalidate the input instead
of quietly disappearing from a plausible result.

Bounds are 1 MiB input, 4096 events, 64 category/process/thread lanes, 128
category/name identities, 32 displayed operator rows, 32 JSON levels and 64 KiB
encoded report. The report states the number of omitted operator rows. Oversized
input/cardinality is refused without a partial success report; the source stays
intact. The parser materializes one **bounded** document; it is not a streaming
multi-gigabyte trace processor. Duplicate keys, non-finite values, invalid Unicode,
negative/Boolean timings, unknown schema and excess precision are refused.

Timestamps and durations are decimal microseconds, converted exactly to integer
nanoseconds. The cosmetic `displayTimeUnit` does not change their unit. Per-span
duration is capped at 300 seconds. Decimal arithmetic must not round a tiny
fraction into a false exact nanosecond; exponent/digit checks precede integer
construction. Absolute timestamps are not returned.

## Read the measurements correctly

Each lane is **category + typed process ID + typed thread/stream ID**. Its opaque
identity is stable within the same input identity values; no raw IDs are echoed.

| Field | Meaning | Not a claim of |
| --- | --- | --- |
| `inclusive_duration_ns` | Sum of recognized spans; may include nested/overlapping work | Wall time or self time |
| `active_union_ns` | Union of spans within that one lane | Device-wide utilisation or total GPU time |
| `span_ns` | First recognized start to last recognized finish on that lane | Complete capture window or job duration |
| Operator rows | Counts, inclusive totals and longest span for that category/name | Critical-path ranking or a kernel recommendation |
| `device_timing` | Device-category spans observed, otherwise unavailable | Hardware identity, valid coverage, or zero GPU work |

Do not add lanes together. Host dispatch is not device completion; different
streams and categories can overlap. Clock alignment, dropped-event detection and
capture completeness remain unverified. Missing device events are **unavailable**,
not zero. A real zero-length device span remains an observed zero-length span.

Every report is `observed_subset` or `no_supported_events`, `job_binding: unbound`,
`job_wall_time_ns: null`, and `causal_speedup_qualified: false`. Trace content hashes
prove exact bytes, not provenance, authenticity, job association or model/runtime
identity. No filename, category or matching time range upgrades that status.

## Public-data boundary

Arguments, shapes, stacks, environment/device metadata, user annotations, trace
paths and raw process/thread identifiers are omitted. Only a fixed allowlist of
standard CPU operator labels is returned verbatim. Other names, including all
kernel names, become digested identities with label `redacted`. This permits
private trace lookup without forwarding arbitrary labels into an agent prompt.
Hashes are linkable and potentially guessable: this is **redaction, not anonymity**.
The tool does not publish anything. Raw traces remain local and require review
before sharing; a later capture adapter must not log tensor payloads or prompts.

## Evidence from this pass

The pure reducer had 23 causal missing-feature test failures before implementation.
A later precision regression exposed Decimal-context rounding; the test failed
before the integer construction correction. Final pure contracts pass, including
nested spans, multiple device streams, category separation, exact nanoseconds,
unknown-device coverage, private-data canaries, bounds and unchanged input.

A real saved CPU-only trace was generated in this sandbox using **Torch 2.10.0+cpu**,
Python 3.13.5, with a 16x16 matrix multiply and clone; no model, download or GPU
activity. Producer configuration explicitly requested CPU activity and disabled
shape, stack and memory capture. The 4295-byte trace contained 21 events: 10 CPU
operator spans recognized, 11 other events ignored. Device timing correctly stayed
unavailable. Input SHA-256:
`c4361751a3e132d6030e8d60be61cb8b674c9202cc5dfc8a1ed428ce1e297bfd`.
The raw trace was not committed. This is producer-format compatibility evidence,
not observer-overhead measurement, inference performance or Windows/HIP support.

Local checkout acquisition failed DNS resolution. Local tests therefore cover the
new isolated reducer; complete-repository CLI, existing-reader, full-suite and
validator evidence must come from the actual hosted PR tree. Do not call the
partial local workspace a full repository test run.

## Source versus adaptation

The supplied audit pp. 13–18, 22 and 30 calls for distinct stage scopes, byte/copy
observations and reproducible workloads. This trace format, strict parser, privacy
projection and non-additive metrics are **repository-specific adaptations**, not
claims that the report already implemented an inference profiler.

Primary sources inspected 14 September 2026:

- [PyTorch profiler API](https://docs.pytorch.org/docs/stable/profiler.html): activity
  selection and Chrome export; shape/stack capture overhead and retained tensors.
- [Kineto JSON producer](https://github.com/pytorch/kineto/blob/main/libkineto/src/output_json.cpp):
  schema version, complete events, decimal microsecond timestamp formatting and
  the separate display unit. A moving upstream reference is not the installed build.
- [PyTorch profiler internals](https://github.com/pytorch/pytorch/blob/main/torch/csrc/profiler/README.md):
  CPU collection, device collection and clock alignment are separate concerns.

## Remaining #364 scope and next adapter design

The existing coordinator, not this CLI, must own any finite future capture:
prepare exact job/runtime/graph/model/input and process-epoch identity -> confirm
allowed activities in an isolated environment -> explicitly allocate a capture
budget -> observe the already-owned execution -> finalize bounded local artifacts
-> attach exact hashes to existing job evidence. Observation failure never changes
a job outcome, drops its prompt ID, or causes resubmission.

Still required: exact installed Windows/HIP activity qualification; bounded capture
lifetime and disk/event overflow recovery; observed backend/clock/identity drift;
separately counted profiler-on/off overhead controls; hash-bound job association;
real model/transfer traces; and one intervention selected from that evidence.
The read cap does not retroactively bound a producer's in-process trace memory.
No kernel, precision, cache, transfer or runtime default is changed here.
