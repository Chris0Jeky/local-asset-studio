# Saved inference trace implementation plan

Continuation of #364 and the decisions proposed in #365. Base inspected:
`3682803733af973cbd392afb8296c6c1878394a8`. The owner's continuation request
covers implementation and PR publication, not runtime installation or generation.

## Design

Implement a pure, offline reducer for the bounded PyTorch/Kineto Chrome trace
subset, and a CLI using the existing `resource_receipts.read_evidence_file`
reader. Do not attach a profiler to Studio, import Torch in the reducer, infer
hardware from CUDA-named fields, or replace existing job/resource evidence.

Input is at most 1 MiB, 4096 events, 128 operator identities and 64 lanes. Only
complete `X` spans in explicitly supported categories contribute durations.
Preserve unsupported/malformed/truncated distinctions; missing device events
return unavailable, never a fabricated zero. Parse timestamps as decimal
microseconds and reduce them to integer nanoseconds without binary float loss.
Never add host, device or thread timelines together as a job wall time.

Raw event arguments, device properties, user scope names, process/thread IDs,
paths and unknown operator/kernel names do not appear in the report. Retain
input hash, per-lane duration sum and interval union, static safe operator labels
and digested other identities. The output remains explicitly unbound to a job.

Alternatives rejected: a new live monitor/worker (competing ownership); a full
trace database or Perfetto dependency (unnecessary for this first bounded read);
a single summed GPU-time figure (overlap and different lanes make it misleading).

## Steps and tests

1. Add failing pure-reducer contracts for schema, integer-nanosecond conversion,
   overlap, categories, privacy, null device coverage and input/cardinality caps.
   File: `tests/test_inference_trace.py`.
2. Implement `app/inference_trace.py:summarize_trace(raw, expected_sha256=None)`.
   Return versioned JSON; refusal errors contain fixed codes only.
3. Add `scripts/inspect-inference-trace.py` with JSON to stdout, optional
   caller-supplied input hash, and existing bounded regular-file reader. No
   output-file writer, mutation, subprocess, network or model-runtime import.
   Test real subprocess/file refusal in `tests/test_inference_trace_cli.py`.
4. Feed a real small CPU-only Torch trace generated in this session's sandbox.
   Record actual producer version and hashes; do not commit raw private traces.
   A CPU arithmetic fixture does not demonstrate AMD profiling or neural speed.
5. Document format boundary, metrics, source attribution and remaining capture
   adapter/Windows qualification under #364. Run focused local tests and hosted
   full-suite/validator on the complete PR tree. Leave prior PRs unchanged.

Rollback removes the standalone reducer/CLI; no persisted schema migration,
job mutation, runtime defaults or model files are involved.
