# Profiler qualification without a model run

15 September 2026. Scoped #378 slice under #364/#302/#172. The saved trace
interpretation follows the v2 reader in #376. This command qualifies a **fixed
16x16 arithmetic probe**, not ComfyUI, a model, driver compatibility or a job.

## Commands

Use a trusted Python executable in an existing isolated candidate environment.
The supervisor uses the selected path as written (made absolute), not its resolved
symlink target: resolving a virtual environment's executable can bypass that
environment. The path is hashed in the report, not printed as runtime identity.

```bash
# CPU default; imports Torch only in the new worker, never in the Studio process.
python scripts/probe-inference-profiler.py --python /path/to/candidate/bin/python

# PowerShell example; explicitly opted-in device workload, only when the GPU is idle.
python scripts/probe-inference-profiler.py --python 'C:\candidate\python.exe' --device cuda --allow-device-probe --timeout 30
```

PyTorch HIP uses the `cuda` interface too. That spelling is not proof of NVIDIA
hardware, AMD support or actual device trace events. The command does not install
packages, fetch models, contact Studio/ComfyUI, attach to a running process, clear
caches, alter launch flags or submit a generation. It does not acquire Studio's
queue or prove another process is idle; the operator chooses an idle candidate.
A trusted interpreter can run startup hooks and native code: `-I` is Python
isolation, **not an OS security sandbox**.

The only workload is `ones(16,16) @ ones(16,16)` (the same input reused), clone,
and an all-elements equality check against 16. Shape/stack/memory recording is
off. The worker uses one CPU thread. Device synchronisation is confined to this
explicit tiny probe; nothing adds per-operation synchronisation to generation.
There is no automatic CPU fallback when device activity is unavailable.

Exit 0 means `cpu_observed` or `device_observed` for that arithmetic probe; exit 2
means refused, unsupported or failed. JSON contains fixed error codes and last
entered stage, not exception messages. A timeout or native exit is not
retried. Driver identity, job binding, inference performance and observer overhead
remain unqualified even after exit 0.

## Ownership and protocol

```text
explicit CLI request
  -> validate device opt-in, interpreter and finite deadline
  -> one new owned Python worker (-I -B), never an existing PID
  -> import -> capabilities -> allocate -> capture -> export -> verify
  -> atomic, bounded stage record + temporary trace
  -> reap child -> inspect exact hash-bound trace through the existing reducer
  -> discard temporary artifacts -> emit redacted JSON
```

`app/profiler_probe.py` owns supervision and result assessment. The fixed
`scripts/profiler_probe_worker.py` owns the tiny Torch operation. Public CLI
`scripts/probe-inference-profiler.py` exposes no arbitrary workload, model path,
module or shell command. The internal supervisor seam accepts inert commands for
fault tests; this is not a new general-purpose Studio executor.

The worker reports advertised CPU/CUDA activities separately from the recorded
trace. Success requires a completed state, checked arithmetic, exact trace hash,
CPU operator spans, and (for a device request) actual device-kernel spans. A
supported-activities flag alone does not qualify device observation. Versions
are self-reported Python/Torch/HIP/CUDA-build strings; HIP/CUDA build versions
are not driver versions. Reported architecture and device-name hash, when present,
are observations of that worker's selected device, not full system attestation.
Unknown driver identity stays null. Ordinary saved-trace producer identity remains
unverified; this wrapper does not turn arbitrary standalone traces into trusted
job evidence.

## Bounds and failure behaviour

| Boundary | Implemented limit | Important limitation |
| --- | --- | --- |
| Workload | One 16x16 float32 matmul/clone, fixed verification, one CPU thread | Native library startup/workspace can cost much more than tensor bytes |
| Child wait | 5–120 seconds, default 30; at most five additional seconds for reap after kill | OS process creation/uninterruptible I/O is not a hard real-time bound |
| Raw stdout/stderr | Discarded to null, **zero retained bytes**, no pipes or spool files | Native diagnostic text is intentionally unavailable; use stage/exit code |
| Stage record | 16 KiB, fixed keys/values, atomic replacement | Disk-full can prevent the newest stage from persisting |
| Trace input | At most 1 MiB read after export; existing event/lane/operator/report caps | Does not bound Kineto's internal buffers or bytes written before export ends |
| Temporary lifetime | Removed after a reaped child; cleanup failure is explicit | Unreaped worker retains its private temporary directory; no false clean result |

There is deliberately no claimed hard worker-memory or producer-output cap; both
fields are null. A larger real model trace still needs #364's separate bounded
capture/chunk/overflow design. The 128-operator saved-reader limit is unchanged.
Raw traces and stage records are temporary, never committed or published by the
command. Hashed identifiers remain linkable, not anonymous.

The supervisor kills only its own `Popen` handle on timeout, never by process name
or a stale stored PID. It retains nonzero/native exit codes. A stage record is
read only after supervision returns; invalid, duplicate-key, oversized or missing
state cannot manufacture a successful observation. Cancellation cleans up the
owned child where the OS permits. No user work, job identity or retry budget is
owned by this probe, so no failure can replay generation.

## Executed evidence

The first 15 contract tests failed before implementation. A later real-venv
regression failed before preserving the selected interpreter path. Final local
contracts cover 28 tests: actual child timeout/reaping, nonzero exit and noisy
output, virtual-environment selection, stage-file size/duplicate keys, missing
Torch/activity/device, private-data canaries, arithmetic/trace-hash gates, cleanup
failure and CLI opt-in/argument handling. Two injected interruption/reap-timeout
regressions also prove that cancellation returns an explicit cleanup verdict
instead of losing it through an exception. A separate Windows/Linux CI lane runs
these contracts without installing Torch; the ordinary full suite remains intact.

A real local probe on Python 3.13.5 / Torch 2.10.0+cpu produced `cpu_observed`,
eight CPU spans, checked arithmetic, no device timing and a reaped child. An
explicit device-mode probe on the same CPU build returned `unsupported` /
`activity_unavailable`; it did not fall back or claim GPU support. Both temporary
directories were removed. [CPU result](evidence/profiler-probe-cpu.json) and
[unsupported-device result](evidence/profiler-probe-device-unavailable.json)
retain the exact observed hashes and metadata. Their supervision elapsed times
include startup/capture/export and are **not inference latency or profiler overhead**.

Local GitHub DNS failed, so local work used source-hash-checked extracted modules.
Full-repository CLI integration, validator and Windows contract evidence belongs
to the actual PR's hosted checks, not this partial local snapshot. No owner-machine
Windows/HIP device or model benchmark was performed.

## Source basis, rejected alternatives and next integration

The supplied audit pp. 13–18 and 29–31 puts scoped observations and reproducible
workloads before advanced optimisations. This arithmetic qualification protocol
is a repository-specific inference adaptation, not its renderer implementation.
Primary mechanisms checked 15 September 2026: [PyTorch profiler](https://docs.pytorch.org/docs/main/profiler)
(activity selection, export and shape/stack overhead), and
[HIP semantics](https://docs.pytorch.org/docs/main/notes/hip.html) (CUDA-interface
reuse). Those pages do not certify this workstation's installed configuration.

Rejected alternatives: importing Torch in the Studio server (shared-process risk),
attaching to a live backend (unproven lifecycle), retaining unbounded stderr
(memory/privacy risk), inferring support from advertised activities (false success),
and automatically falling back after failure (changes the question being tested).

Next, the existing coordinator needs a separate capture adapter, not another
queue: bind exact graph/model/reference/runtime/process epoch -> establish a
finite approved capture allowance -> record already-owned work -> retain bounded
artifacts and failure state -> link exact hashes to existing job receipts. Add
profiler-on/off controls, capture completeness/clock tests and real Windows/HIP
qualification before choosing a kernel/layout/transfer intervention. Neither #364
nor #302 is completed by this probe. Rollback removes this standalone tool; it
requires no persisted-job migration or installed-runtime change.
