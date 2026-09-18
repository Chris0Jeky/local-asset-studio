# Experiments and release gates

Source-derived principle: the audit's pp. 13–18 and 25–31 put reproducibility, distributions, fidelity and failure evidence before optimisation claims. The concrete experiments below are new repository-specific designs.

## Measurement contract

Every result states baseline/candidate source identity, Python/Pillow or full backend versions, platform, workload shape/input identity, warm/cold definition, invocation, sample count, output verification and limitations. Use fresh child processes for peak-memory comparisons so allocator history from the other candidate cannot contaminate the result. Alternate baseline/candidate order. Keep raw trials, not only medians.

RSS high-water mark is not Windows commit or GPU memory. Linux `ru_maxrss` is KiB and macOS reports bytes; convert explicitly. A process-lifetime maximum includes imports and setup. Label it as such rather than subtracting maxima and calling the result an exact allocation. Hashing a full output may itself allocate a byte copy; measure the timed operation and capture its memory observation before verification allocation where the tool permits.

Do not report meaningful p95/p99 from five trials. For small CPU microbenchmarks report every sample, median and range; leave tails unqualified. Owner-machine generation comparisons continue through the existing BENCHMARKS/JOB-OBSERVATIONS/PAIRED-OBSERVATIONS contracts, not these synthetic scripts.

## C1 — review decode, #362

Use deterministic RGB and RGBA PNGs at 2048² and 4096² (the latter is exactly the existing pixel cap), plus small EXIF 1–8 fixtures. Compare the baseline decoder against the candidate on identical encoded bytes. Inspect pixel output, transform, metadata and input immutability. Include palette and RGB tRNS fixtures, hidden RGB and unsupported/animated/corrupt inputs.

Causal gate: a normal-orientation call must not invoke `ImageOps.exif_transpose`; an EXIF 2–8 image must still follow the real transpose path and match the baseline. Performance evidence reports total decode latency and fresh-process peak RSS. Do not claim that the orientation-bearing case improves or that fewer review allocations accelerate sampling.

## C2 — protected difference, #363

Use two deterministic RGBA images with opaque, fractional and zero alpha; alter each channel independently at corners and either side of tile boundaries. Compare the candidate mask against the original full-image algorithm byte-for-byte. Include 1×N, N×1, odd sizes, a no-change image and palette/tRNS conversions.

Causal gate: instrument the actual Pillow difference calls and verify no input to that operation exceeds 512×512 in the candidate. This bounds the relevant native image dimensions; Python tracemalloc alone does not prove Pillow's native allocation usage. Inject an operation failure and verify owned intermediates are closed while caller images remain usable. Full-image output L mask is explicitly allowed.

Benchmark at 2048² and 4096² with a small finite repeat count. Record output equality, latency and peak RSS; expose any small-image or throughput regression. Adopt only after the exactness tests and full repository gate pass, with the trade-off stated. Do not rewrite unrelated bundle byte comparisons in the same PR.

## I1 — inference attribution, #364 → #176/#307

This is an owner-run experiment design with **zero allocated neural attempts in this package**.

| Stage | Question | Candidate only after attribution | Required control |
| --- | --- | --- | --- |
| Model load | Repeated reads, page faults, dtype conversion or host copies? | Exact loader/cache/offload alternative | Same checkpoint bytes, process starting state and supported loader |
| Text/reference encoding | Repeated compatible work or excessive image transforms? | Exact conditioning reuse or bounded preprocessing | Complete reference/role/transform/tokenizer key, cold miss and warm hit |
| Attention/GEMM | Math kernel, layout conversion or real accelerated implementation? | One supported attention/matmul/layout variant | Same effective inputs, kernel evidence, dtype and independent quality review |
| Repeated sampler dispatch | Launch overhead significant relative to work? | Bounded shape-bucketed compilation | Eager baseline, first compile and warm amortisation, shape-change test |
| Host/device transfer | Stalls versus actual overlap? | One bounded pinned/nonblocking alternative | Correct completion dependency, host-memory pressure, no hidden global sync |
| VAE decode | Decode capacity dominates after sampling fits? | Existing graph-specific tiled alternative | Same intended output, seams/quality and actual peak in all memory domains |
| Export | Encode/copy overhead after useful output? | Bounded serialization/copy work | Same pixels/metadata and original retention |

Probe available activities and record an explicit unsupported result. Start with a short CPU/operator window, shape and stack retention off. Add device timing only when supported on the exact Windows/HIP build. Do not assume a graphics profiler or Linux command covers the current inference process. Record profiler-on/off overhead with separately counted attempts and retain any failure.

First freeze one already supported image route, one multi-reference route and one decode-stress case under the existing coordinator. Do not run all variants by default. Select one attributable bottleneck, one factor and a finite approved allowance; stop on the first OOM/native crash/uncertain outcome. Failed warmups and probes consume their actual experiment allowance. Model-switch trials are not warm same-model trials.

## I2 — compilation/reuse amortisation proposal

For a stable shape, report the measured break-even count rather than only warm speed:

```text
N_break_even = ceil(extra_setup_time / (baseline_per_run - candidate_per_run))
```

The expression is meaningful only when per-run savings are positive and setup is attributable. Include cache validation/load cost, failed compilations, shape changes and retained-memory interference. A favourable kernel timing that makes the desktop unusable or worsens accepted-output effort is not a promotion.

## G1 — preserve the graphics roadmap without pretending it shipped

Under #15/#24, choose one actual GLB/engine target and freeze neutral turntable/camera/lighting before trying meshoptimizer, texture compression or LOD. Validate topology, seams, tangents, alpha, colour space and supported extensions. Measure original and transformed geometry/texture/resident bytes on the actual consumer. Export compression is not equivalent to browser GPU residency, and GPU texture bytes are not model tensor bytes.

Keep ordinary loading/culling/batching as the baseline. The audit's >2 ms submission, >3× submitted/visible triangles, >3× warm-open and ≥50% texture savings are source-proposed gates/targets, not measured Studio facts. Sparse resources, mesh shaders and GPU decompression remain deferred until a real large-scene bottleneck justifies them.

## Universal release/rollback matrix

| Gate | Pass evidence | Refusal / rollback |
| --- | --- | --- |
| Exact CPU behaviour | Output parity, metadata semantics, caps, errors, input immutability | Revert the scoped function/helper; no data migration |
| Resource benefit | Scoped before/after samples, known units and overhead | Keep baseline if benefit is absent or trade-off unacceptable |
| Inference correctness | Exact effective recipe plus independent output review | No automatic graph degradation, cache substitution or retry |
| Ownership | Existing coordinator/Workspace and retained unknown outcomes | Refuse stale/unknown authority; preserve source/job evidence |
| Compatibility | Actual installed build/activities/kernel path | Unsupported stays unsupported; no package/driver upgrade |
| Repository integration | Full offline suite and validator on actual candidate | Investigate failure; do not weaken tests for performance |

No p99 claim, native-crash resolution, Windows capacity guarantee or accepted artwork is established by a synthetic CPU benchmark.
