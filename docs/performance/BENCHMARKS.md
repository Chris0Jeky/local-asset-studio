# Benchmark protocol and experiment worksheet

## What already runs

From the repository root, the existing finite host-only observer is:

```powershell
python scripts/profile-resources.py --include-self --samples 6 --interval 5 --output .runtime/host-baseline.jsonl
```

An optional runtime observation can add `--comfy-url http://127.0.0.1:8188` when that configured service is already running and its owner has coordinated access. This GET observer does not start the runtime or authorise a generation. Choose verified PIDs explicitly; it does not discover a browser tree.

The first implementation adds `python scripts/summarize-resources.py INPUT --output OUTPUT`. Until that implementation PR lands, this is a planned command, not an existing command. It consumes one completed/partial receipt and never contacts the runtime. See [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md).

## Trial identity and comparability

Use [benchmark-plan.example.json](benchmark-plan.example.json) as a non-executable worksheet. Null bindings and zero allowance deliberately prevent treating it as an execution request. Before any live comparison, bind repository commit, exact API graph and input hashes, all model/adapter hashes, quantisation/precision, custom-node revisions, Comfy/Torch/ROCm/Python/driver/OS versions, GPU identity, launch arguments/environment and the budget. Keep personal prompt text and absolute machine paths out of published evidence.

Cold-process start, first-generation/model load, warm same-model, and model-switch measurements are separate classes. Record who established the starting condition and how; a filename containing `cold` is not evidence of cache state. Preserve failed, cancelled, OOM, native-crash and uncertain trials alongside successful ones. Runtime failure and artistic rejection are separate outcomes. Do not average first-load time into warm sampling results or compute latency only over successes without showing failures.

Resource sampling timestamps bound the observation window, not the job wall time. Phase timings require explicit source events or retained executor timestamps with provenance. Missing encode/load/sample/decode/export times stay null. Only derive per-device used bytes from a valid same-sample total/free pair. Never subtract extrema from different samples. Do not sum process working sets or Torch/device counters.

## Finite comparison procedure

1. The runtime owner approves a finite number of executions, trial identities, stopping rule and recovery authority through the existing Studio command/budget path. No alternate direct `/prompt` runner.
2. Capture a short baseline and enough coverage for the intended job window. The existing profiler caps at 120 samples with 1–60 seconds after each completed sample; plan an interval accordingly. Capture timing/counter gaps. Do not silently remove this bound to cover long video work.
3. Run one baseline case, then one candidate case under a matched starting condition. Stop on OOM/native failure, unknown prompt, unexpected queue work or loss of ownership. No automatic replay, budget refill or cleanup. Preserve receipts before operator-controlled recovery.
4. Compare like-for-like repeated pairs after initial safety proof. Use balanced order to limit thermal/cache/order bias. A small pilot is not a statistical performance claim; report all observations, spread, failure counts and instrumentation cost before expanding the budget.
5. Keep a candidate only after representative image quality, reliability, responsiveness and end-to-end latency are acceptable. A lower sampled VRAM peak alone is not a win if host commit, paging or model reloads worsen. Publish redacted summary/hash references; keep raw receipts locally.

## Ordered experiment tracks

| Track | Variable | Required invariant / rollback |
| --- | --- | --- |
| Stable vs isolated next runtime | Complete supported AMD runtime environment | Separate directories, ports and node environments; read-only model sharing only where safe; preserve stable installation hashes. No in-place package upgrade. A required shared driver change is a separate owner decision, not isolation. |
| Browser | Existing external vs NoBrowser first, managed modes after ownership feature | Same workload and foreground conditions; do not close arbitrary tabs. Browser GPU acceleration is another variable, not an assumed saving. |
| Launch policy | Preview mode, pinned memory, MIOpen, cache/offload, then narrowly chosen reserve | #176 owns version support and one-change comparisons; no global low-VRAM default. Preserve reserve 0.6 baseline until measured otherwise. |
| Representation | Supported FP16 / FP8 / GGUF alternatives | Exact model/version and quality task; quantisation can trade quality and conversion overhead against residency. Do not infer speed from file size. |
| Model transitions | Same-family warm sequence vs explicit model-switch sequence | Existing queue, explicit reorderable batch, identical item set and quality. Record loading and retained host commit. |
| Fallback graphs | Tiling, batch/reference reduction, smaller working resolution | New approved graph identity and quality/cost disclosure; original remains immutable. Respect #163 stage-specific Wan limits. |

Linux and a physical RAM upgrade remain optional later tracks, not first-pass recommendations to change the host. The report's 64 GiB RAM suggestion is a hypothesis about the captured host-pressure pattern, not a measured upgrade benefit. The completed page-file change is not a physical RAM upgrade.
