# Findings and source reconciliation

## Provenance

Requested source: *Resource optimisation strategy for Local Asset Studio on the RX 9070 XT*, 26-page user-supplied PDF. SHA-256: `3264463fe9d36fbbdf4e4ebfdb6ffe80f43dd4dc2046a8997236798d03a9e25e`. Its recommendations are retained below; raw machine receipts and the PDF are not republished. Repository observations are pinned to `b9998270995bacd3c24d7b64715f8f2df5b3b49a` (tree `0ef2604906ab28af223603442adeafa899918a0b`). Read current main again before implementing a later slice.

## What changed since the report's source observations

| Report proposal / observation | Current repository evidence | Disposition |
| --- | --- | --- |
| Centralise RAM, commit, process and VRAM observation (pp. 10–11, 21–22) | `app/resource_probe.py`, `app/host_memory.py`, `scripts/profile-resources.py`; #173 delivered by #182 | Reuse these primitives. Add bounded summaries and later coordinator-owned job windows, not a second sampler. |
| Enable the 32 GiB large-job commit gate (pp. 3, 22, 25) | `Studio.host_commit_required`, `host_commit_preflight`; #129; `HUMAN_TODO.md` q-4 says enabled locally | Preserve. It is a graph-scoped installation-derived rule, not universal RAM sizing. Broader stage-aware policy remains #178. |
| 40 GiB page file / roughly 71.7 GiB commit limit (p. 3) | `HUMAN_TODO.md` records owner-authorised fixed 64 GiB page file, reboot and post-reboot verification | Historical baseline only. Never embed either commit limit in admission or claim the change fixes native crashes. |
| Add browserless operation (pp. 7–9) | `Start-Studio.ps1 -NoBrowser`, existing CLI / shared executor | Already available. Managed-browser ownership and automatic close/reopen are separate missing features. |
| Stop repeated expensive discovery and hidden polling (pp. 10, 22) | Existing schema cache; #200 preserves healthy identity-bound cache. `read-poller.js` / #182 deliver bounded visibility-aware main-page reads. | Do not claim to add these again. #175/#177 own smaller projections, deduplication and bounded media/history; AV/voice remain follow-ups. |
| Empirical peaks, cold/warm and phase timings (pp. 13–14, 18–20) | Existing finite JSONL records carry counters, sample timings and sampler hash; they do not bind a generation's lifecycle or phases | First missing slice: trustworthy offline reduction. Next: explicit job-window binding and trial manifests. Sampling duration is not inference wall time. |
| Isolated newer AMD runtime, never in-place (pp. 5–7, 19) | Stable runtime documented as ComfyUI 0.35.0 / Torch 2.9.1+rocm7.2.1; separate backend infrastructure exists | Controlled experiment, not an upgrade command. Pin a supported complete candidate before execution. |
| Full-residency boundary, reserve 0.6, partial-load/native failures (pp. 2–5) | `RUNTIME-PRECONDITIONS.md`, #77/#89 preserve workload-specific measurements | Keep existing settings. Historical correlations are not proof of a single native-crash cause. No global low-VRAM or mmap/cache change. |
| Warm retention, model locality and retained-commit cleanup (pp. 12–17) | Single coordinator and verified backend/recovery ownership already exist | Extend those owners after telemetry; FIFO remains default. A successful `/free` response is not measured resource recovery. |
| FP8, pinned memory, MIOpen, fallback graphs and resource UI (pp. 6, 15, 19–23) | #176 owns measured profile experiments; #178/#163 own stage/capacity constraints | Track distinct missing integrations; preserve image quality, approved graph and failure evidence. No presumed speed-up. |

## Counter semantics and evidence limits

Physical availability is not Windows commit headroom. `GetPerformanceInfo` supplies commit totals and limits in pages; multiply by PageSize. The existing reader performs this conversion. Process working sets include shared pages and cannot be summed into host RAM consumption. Process lifetime peaks and OS-since-reboot peaks are not peaks within a job. Comfy device free/total and Torch allocator free/total are separate observations, not browser attribution. A sampled maximum is a lower bound on the true maximum; the sampled minimum free memory can miss a lower transient value.

The profiler's documented short live idle observations are evidence of that capture only, not of today's free memory, generation-stage peaks or a causal speed-up. Its schema has no backend PID/epoch or job identity. Same-version runtime restart cannot be inferred from those receipts. The first reducer must state that limitation rather than invent continuity.

## External verification on 14 September 2026

- [Microsoft PERFORMANCE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information): page-based counters, changeable commit limit and reboot-lifetime CommitPeak semantics. This supports the distinction above, not a universal 32 GiB threshold.
- [AMD release history](https://rocm.docs.amd.com/en/latest/release/versions.html): confirms 10.0.0 dated 26 August 2026 and 7.14.1 dated 2 September 2026. Release streams must not be sorted into a compatibility guarantee by number alone.
- [AMD compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html): fresh retrieval returned HTTP 429 in this pass. The PDF's Windows/PyTorch 2.13 candidate statement is retained as a report claim, not independently reconfirmed installation guidance. Candidate selection requires fresh OS/GPU/driver/Python/Torch/custom-node evidence under the runtime experiment issue.

The installed-source DynamicVRAM gate recorded in `RESOURCE-EFFICIENCY.md` is evidence about that source revision, not a promise that a newer package will be faster or compatible. No driver, ROCm, PyTorch, ComfyUI, model or system configuration was inspected live or changed by this reconciliation.
