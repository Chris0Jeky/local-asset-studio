# Offline resource receipt summaries

First implementation of [#301](https://github.com/Chris0Jeky/local-asset-studio/issues/301),
following the report reconciliation in [#300](https://github.com/Chris0Jeky/local-asset-studio/pull/300).
This consumes the existing [finite profiler](../RESOURCE-EFFICIENCY.md); it does not
sample resources, start Studio, contact ComfyUI or change execution policy.

## Use

From the repository root, first produce or locate an existing profiler receipt. A
short **host-only** observation uses the existing command (no GPU generation):

```powershell
python scripts/profile-resources.py --include-self --samples 6 --interval 5 --output .runtime/host-baseline.jsonl
```

Summarise it into a new file, or omit `--output` to print JSON:

```powershell
python scripts/summarize-resources.py .runtime/host-baseline.jsonl --output .runtime/host-summary.json
python scripts/summarize-resources.py .runtime/host-baseline.jsonl
```

The summary command accepts one finite JSONL input, not a URL, execution manifest or
list of jobs. Paths are explicit; it does not read configuration or search for services.
It uses only the Python standard library and works without psutil, Torch or Studio
running. The input must be a regular file. Existing destinations, including the input
itself or existing links, are never overwritten. Parse failure creates no output.
An output-device/disk failure can leave a partial **new** file; that file is not valid
evidence. The original receipt is unchanged. Fix the storage problem and choose a new
output path rather than automatically deleting uncertain evidence.

Exit zero means a summary was written, not that the runtime was online, every counter
was available, or a generation succeeded. Invalid/mixed/oversized receipts and file I/O
errors exit nonzero with a bounded message that does not echo the input payload.
An interrupted receipt with complete JSON records can be summarised as incomplete;
a half-written final JSON record is rejected, not silently repaired or dropped.

## Output contract: `studio.resource-summary/v1`

| Field | Meaning |
| --- | --- |
| `source.schema` | Required input schema `studio.resource-profile/v1` |
| `source.receipt_sha256` | SHA-256 of exact consumed bytes, including newlines; identity, not authenticity |
| `source.sampler_sha256` | Producer source hash supplied in the receipt metadata |
| `sampling.requested`, `observed`, `complete` | Declared and present sample counts; complete means count equality only |
| `sampling.first_observed_at`, `last_observed_at` | Valid timezone-aware sample timestamps normalised to UTC |
| `sampling.observed_span_seconds` | Last sample start minus first sample start; null for no samples, zero for one |
| `sampling.interval_seconds_after_completion` | Producer's configured completion-based interval, not measured cadence |
| `metrics` | Commit limit/used/headroom, physical total/available bytes and individual sample duration |
| `comfy.observed_samples`, `unobserved_samples` | Runtime response coverage, independent of host coverage |
| `comfy.versions` | Bounded known ComfyUI/PyTorch version strings; not a runtime process identity |
| `comfy.metrics` | Response bytes and probe elapsed seconds from observed runtime responses |
| `comfy.devices[].metrics` | Per-index device/Torch total, free and derived used bytes; no cross-device sums |
| `processes[].pid`, `created_at`, `metrics` | Nominated process identity and observed working-set/private-byte/one-core CPU counters |
| `limitations` | Fixed interpretation warnings; arbitrary input notes/paths are not copied |

Each metric has exactly `sampled_min`, `sampled_max`, `known_samples`, `unknown_samples`.
The denominator is the number of **present** samples, not the requested count. Missing
processes, absent runtime responses and invalid counters contribute unknown coverage.
There is no interpolation. Initially unavailable process identity cannot certify counters
or later silently rebind to a newly visible process. A valid zero is known, including zero
Torch/device totals; zero physical RAM or commit limit is not a valid host observation.

The reducer accepts finite, nonnegative numeric counters up to `2**63 - 1`, excluding
Booleans. Invalid scalar counters become unknown. Contradictory total/free or commit
triples are unknown as a group. Device used bytes are derived from each same-sample
`total - free` pair before reduction, never from different samples' extrema.

## Bounds and rejected evidence

Input is streamed one bounded line at a time: at most 1 MiB per line, 121 records total
(one metadata plus 120 samples), and no more samples than requested. At most 16 process
identities may appear across the whole receipt and at most eight device indices per
observed runtime response. Only running extrema/counts and these bounded identities are
retained; the tool does not keep an ever-growing history of samples.

Reject unsupported metadata/schema, duplicate JSON keys or metadata, duplicate process
or device identities in one sample, malformed collection shapes, invalid identities,
non-JSON constants, timestamp reversal, changed known runtime versions, changed observed
device-index layout and PID creation-time changes. Equal timestamps are allowed because
wall-clock resolution may be coarse. A missing/offline response is unknown, not an empty
new device layout. Device indices are producer ordinals, not stable hardware UUIDs.

Input is treated as supplied evidence, not trusted instructions. Extra fields are ignored
rather than executed or copied. There is no arbitrary prompt, path, command-line or error
payload projection. The original local receipt remains necessary for detailed diagnosis.

## What this does not establish

A sampled maximum can miss a higher transient allocation; a sampled free-memory minimum
can miss a lower transient. Process lifetime maxima are deliberately excluded. Working
sets share pages, so summing them does not measure host RAM usage. Device and Torch
allocator figures describe different domains and are not browser-specific GPU usage.

This input schema has no job/graph/model identity, phase events or backend process epoch.
A same-version backend restart or hardware replacement at the same device index can go
undetected. A compatible-looking pair of summaries is not sufficient evidence of a fair
runtime comparison. Sample span is not job wall time and sample duration is profiler
cost, not inference time. Summary hashes do not authenticate a sensor or prove admission
safety. No threshold or prediction is learned from these records.

[#302](https://github.com/Chris0Jeky/local-asset-studio/issues/302) owns binding bounded
observation windows to real jobs, retained identities, finite execution allowances and
cold/warm/phase evidence. [#178](https://github.com/Chris0Jeky/local-asset-studio/issues/178)
continues to own admission through the existing coordinator. The existing commit gate,
launch flags, browser behaviour, queue and runtime remain unchanged by this tool.

## Verification and rollback

```powershell
python -m unittest discover -s tests -p "test_performance_history.py"
python -m unittest discover -s tests -p "test_resource_probe.py"
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Tests use synthetic observations and actual `resource_probe.write_samples` output with an
injected sampler. They cover malformed/partial receipts, numeric and identity boundaries,
metadata-only results, CLI no-overwrite/non-regular files and import/network/process guards.
A review regression specifically proved that zero device/Torch totals must not inherit the
positive-total rule for host physical memory. Tests do not run an RX 9070 XT workload or
establish a performance improvement. Rollback removes this optional offline tool; no live
configuration or model state needs restoration.
