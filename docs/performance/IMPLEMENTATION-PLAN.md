# Bounded resource-receipt summaries implementation plan

**Goal:** Make existing profiler evidence useful without touching a live runtime.

**Architecture:** A standard-library streaming reducer reads one `studio.resource-profile/v1` receipt and emits `studio.resource-summary/v1`. A thin command writes a new JSON file or stdout. It never samples resources itself. Existing `resource_probe.py`, `host_memory.py`, server, configuration and launcher remain unchanged.

**Spec:** [ARCHITECTURE.md](ARCHITECTURE.md), decisions D1–D3. **Stack:** Python 3.12+, unittest, no new dependencies. This is PERF-01 only; per-job persistence, execution manifests and policy are PERF-02/#178.

## Contract and files

- `app/performance_history.py`: `summarize_resource_profile(stream: BinaryIO) -> dict`; malformed envelope/oversize/identity drift raises `ValueError` without echoing payloads. Use a fixed 1 MiB line ceiling and at most 121 lines (one metadata plus 120 samples), maximum 16 process identities and 8 devices per receipt. Reject unknown schemas, duplicate metadata/JSON keys and concatenated runs. The declared sample count is authoritative for completeness, never job success.
- `scripts/summarize-resources.py`: positional input and optional `--output`; input must be a regular local file; refuse overwrites; no `--execute`, URLs, configuration reads, service discovery or retries. Parse fully before creating output. Return nonzero for invalid receipt or I/O errors without a traceback/payload dump.
- `tests/test_performance_history.py`: real producer integration, deterministic receipts, malformed/partial/identity/counter limits, CLI round trip and no-side-effect import/subprocess checks.
- `docs/performance/TELEMETRY.md`: exact schema, runnable command, unknown/partial states and limitations. Add after implementation, not as a fake completed feature in this plan.

## Task 1 — Reducer, red then green

- [ ] Build deterministic metadata and samples using the existing field names (`host_commit.available_bytes`, not free physical RAM).
- [ ] Assert that samples with 100 then 80 bytes commit headroom produce a minimum of 80; a missing third value leaves coverage at 2/3, not a fabricated zero.
- [ ] Assert that per-device used maxima are calculated per sample; total/free changing together must not combine unrelated extrema.
- [ ] Assert that process lifetime peaks never replace the observed-window working-set maximum and working sets are not summed.
- [ ] Run `python -m unittest discover -s tests -p 'test_performance_history.py'` and retain the initial failure for the absent feature.
- [ ] Implement bounded parsing and reduction, run the same command, and review each emitted field for source/meaning. Null and invalid counters contribute unknown coverage; structural corruption rejects the receipt.

## Task 2 — Adversarial envelopes and actual producer

- [ ] Cover empty/metadata-only/truncated sample counts, exact maximum and one-over limits, oversized line, duplicate keys, non-finite JSON, booleans, contradictory total/free and committed/headroom, extra metadata, unsupported schema, reversed timestamps and runtime/device identity drift.
- [ ] Preserve distinct PIDs only when their create-time identity matches; reject identity replacement in one receipt. Missing initial identity cannot later become invented ownership.
- [ ] Exercise `resource_probe.write_samples` with an injected deterministic sampler, no real endpoint. Feed the resulting bytes to the reducer and prove schema compatibility.
- [ ] Demonstrate that unknown input fields and raw notes do not enter output, including errors. Summarising input never mutates input bytes.

## Task 3 — CLI and proving gate

- [ ] Add subprocess tests for a valid receipt from outside the repository, invalid/missing input, existing destination, same input/output, directory/non-regular input and stdout output; no output is created after parse failure.
- [ ] Implement the CLI. Test import/CLI with network/process creation blocked and assert no Torch/server/resource sampler import.
- [ ] Run the new focused suite, existing resource-probe suite, `python -m unittest discover -s tests` and `python scripts/validate-repo.py`. Separate environmental skips/failures from regressions; use hosted CI to verify the full checkout.
- [ ] Review bounds and identity semantics independently of happy-path tests; add a failing regression before correcting any discovered issue.
- [ ] Publish the implementation PR separately from planning. Include actual CLI output from a clearly synthetic fixture, not a claimed Windows/GPU benchmark. Record no runtime/model/config/job changes.

## Deliberate limits

No prediction model or universal memory threshold. No job IDs, phase timings, backend epoch or outcome are inferred from v1 profiler samples. The tool handles one finite observation window; comparison and coordinator binding need their own reviewed schemas. Receipt SHA-256 provides identity, not authenticity or proof of correct sensor data. Removing the optional tool is the rollback.
