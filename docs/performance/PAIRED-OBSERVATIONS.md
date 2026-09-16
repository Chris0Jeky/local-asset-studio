# Compare explicitly paired resource observations

This is the offline comparison part of #302, layered on the [receipt inspector](RECEIPT-INTEGRITY.md).
It compares saved evidence from the existing #318 recorder. It never submits a generation, creates
an allowance, starts an observer, changes a runtime or chooses a winning configuration.

## Operator workflow

First inspect each existing observation directory. Keep the returned `job_id` and exact
`result_sha256` in your comparison manifest. Do not replace a pin just because later inspection
fails: that changes which evidence you have selected. Raw directories must still be available.

```powershell
python scripts/inspect-resource-observation.py .runtime/job-resource-observations/observation-00
python scripts/inspect-resource-observation.py .runtime/job-resource-observations/observation-01
```

Copy [paired-observations.example.json](paired-observations.example.json) outside Git, replace the
example directories, job IDs and synthetic result pins with those two inspected bindings, and keep
`generation_allowance` at zero. Paths are relative to the **manifest**, not the working directory.
The example is deliberately unbound and contains no recorded measurement or execution permission.

```powershell
python scripts/compare-resource-observations.py .runtime/pairs.json --output .runtime/comparison.json
```

Omit `--output` to print JSON. Existing destinations are never overwritten. No API or live ComfyUI
connection is needed. Missing/corrupt/stale evidence is retained in the report; the command does
not resample, repair, rebind a pin, replay a request or discard a failed observation.

| Exit | Meaning |
| --- | --- |
| 0 | All nominated artifact sets passed integrity checks and each pair permits descriptive arithmetic. This is not generation success or qualified benchmark acceptance. |
| 2 | Invalid manifest, or a written report with invalid/incomplete observations or withheld pairs. Inspect the reason codes and retain the report. |
| 1 | Output could not be written. A partial **new** file can remain after storage failure; no existing file was overwritten. |

A structurally invalid manifest creates no output file. A valid manifest with one missing observation
still produces the complete requested report (including that missing row) and exits 2. JSON is compact
so the same 1 MiB report limit applies to file and stdout output. There is no HTML rendering path.

## Manifest contract

`studio.resource-comparison-plan/v1` has exactly `schema`, `generation_allowance: 0`, and `pairs`.
Each pair has exactly `id`, `condition`, `baseline`, `candidate`. Each side names one `directory`,
`result_sha256` and `job_id`. Pair IDs must not repeat. Exact `(job_id, result_sha256, directory)`
triples may be shared across pairs; those bindings are inspected once and reported in each pair
that names them. Reusing only some of those three components (same job with a different pin or
directory, same pin with a different job, or same directory with a different identity) is still
`duplicate_trial_evidence` and is refused before any observation is read. The entire manifest is
validated before any observation directory is read.

There are at most eight pairs / sixteen observations, and the input is at most 64 KiB. Each side
inherits the inspector's bounded reads and fixed five-file capture; histories are not scanned.
One pair cannot silently adopt the other side's receipt. Reuse of an actual received prompt identity
also invalidates **all** affected rows, even when copied/rehashed artifacts have different job labels.
Partial-component reuse is still refused: the same job ID with a different pin or directory is
not two independent trials. Grouping distinct windows of one job needs a different explicit
protocol.

Conditions are `unspecified`, `cold_process`, `cold_first_generation`, `warm_same_model` or
`model_switch`. They remain caller declarations: every pair says `condition_verified: false`.
No label or folder name proves cache state, and conditions are never pooled into an average.
Unrecognized fields, nonzero or Boolean allowances, unsupported schemas, duplicate JSON keys and
nonfinite/deep/oversized inputs are refused through the existing strict decoder.

## Reading the comparison

Every requested side appears as `verified`, `invalid` or `incomplete`, with the expected pins and
bounded reasons. A verified side contains the full inspection projection, including sampled values,
known/unknown coverage, raw artifact hashes, unresolved responses and coordinator snapshots. The
report omits nominated filesystem paths. It never derives a new final job outcome from a snapshot.

The pair's `comparison.state` is `withheld` when either side is unverified, saved ordered
index/graph/control/reference-manifest hashes differ, no samples were observed, sampler source
hashes differ, the intent sequence has gaps or a runtime bracket is unavailable/lost. Both rows
remain inspectable even when arithmetic is withheld. A different runtime profile, runtime versions
or capture-time source observation is separately disclosed, not mistaken for a controlled variable.

Otherwise the pair is `descriptive`. Host memory domains and per-device counters have the original
baseline/candidate coverage plus `sampled_min_delta` and `sampled_max_delta`. Each delta is
**candidate minus baseline**, in bytes. Unknown on either side produces a null delta; a genuine zero
is retained. Device indices are only producer ordinals; they do not certify identical hardware.
Different device-index sets withhold device deltas and produce a warning. Working sets, physical
RAM, Windows commit, device VRAM and Torch allocator figures are never summed together.

A coordinator elapsed delta is included only when both recorded snapshots say completed, both have
elapsed values and every recorded intent has a received-response fact. An uncertain, failed, absent
or still-running snapshot does not become a latency improvement. The raw snapshots are always
retained. Even this completed-snapshot delta is **not** authoritative final job duration or a model
load/sampling/decode phase measurement; the recorder's outer error handling can happen later.

Unequal sample counts and different sampling intervals are warnings. Incomplete sampling remains
visible in the inspection record and does not by itself relabel a job failed. `evidence_complete`
means all artifact sets verify, not complete sampling, success or full identity attestation.
There are no means, performance percentages, rankings or success-only exclusions.

## Limits and next implementation

Every report and pair remains `qualified_benchmark: false`; the report also says
`execution_authority: false` and `generation_allowance_added: 0`. Hash integrity cannot attest actual
model/input contents, loaded code, exact output geometry, precision, cold/warm state, sensor origin
or final job outcome. Sampled extrema can miss transient peaks, and a descriptive delta is not a
causal speed-up or memory-safety guarantee. It cannot bypass #178 admission or the existing gate.

`app/resource_comparison.py` is a pure file consumer over `resource_receipts`, not a second execution
manager. Python callers use `compare_observations(manifest_path)`. The thin CLI owns only report
output. The existing Windows CI lane runs the comparison and inspector contracts; no new permanent
service or dependency is introduced. Rollback removes these optional consumers without changing
retained job evidence or runtime settings.

The remaining #302 execution work must bind complete trial identities through the existing
Production/allowance owner, record explicit starting conditions and final outcome evidence, and
stop on uncertain work without replay. Only then can an authorised finite Windows baseline support
the isolated runtime experiments in #303. The original report's recommendation to measure before
changing runtime flags remains the design basis.

## Verification

```powershell
python -m unittest discover -s tests -p "test_resource_comparison.py" -v
python -m unittest discover -s tests -p "test_resource_receipts*.py" -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Tests create actual recorder artifact sets with synthetic sensor/source data. They exercise all
sixteen maximum observations, pin changes, duplicate jobs and prompts, corrupted/missing evidence,
unknown/zero coverage, failed/uncertain results, cold/warm declarations, mismatched graphs/samplers,
parent links and standalone CLI no-overwrite/no-live-dependency behavior. These are contract and
resource-bound tests, not a Windows GPU benchmark. Exact-head results and historical failures live
on the implementation PRs.
