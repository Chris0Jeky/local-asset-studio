# Per-prompt Windows commit telemetry, proved on three families: 27 September 2026 (09:13-09:18 local)

This is the lab3 GPU session, second slice, on branch `claude/lab3-commit-telemetry` (#302). While each prompt runs, the Studio now samples Windows commit every 0.5 s on its own thread. It keeps one window per prompt in `job.host_commit_windows`: sample counts, the peak committed bytes with their time and the commit limit, and the minimum headroom. It was proved with one Studio job per family, each at the preset's authored defaults with seed 2026092701, while `receipts/families.py` ran an independent 0.5 s sampler against the same Windows counter.

| Family (backend) | Job, prompt ID | Elapsed | Studio window: samples, peak, minimum headroom | Independent sampler over the same span |
| --- | --- | --- | --- | --- |
| `wai` SDXL (primary) | `43a62885`, `e39d2c83-19d3-49bd-98f2-6c44bd9cb6f0` | 42.3 s | 84 (0 unknown), 63.1 % at 09:13:55, 35.32 GiB | 83 samples, 63.1 %, 35.33 GiB |
| `zimage-fast` (primary) | `5675d65c`, `fb5ad836-5c7a-4c20-baae-8ef6032ac22e` | 120.4 s | 231 (0 unknown), 75.1 % at 09:16:08, 23.82 GiB | 230, 75.1 %, 23.82 GiB |
| `qwen21-t2i` (qwen21) | `527cff24`, `858d462e-c0d8-4e0b-a2d4-1c32bbbccd15` | 65.4 s | 130 (0 unknown), 76.4 % at 09:17:52, 22.55 GiB | 129, 76.5 %, 22.54 GiB |

- The Studio's windows agree with the independent sampler to within 0.01 GiB and 0.1 percentage point. Commit limit: 95.73 GiB.
- The window runs from when ComfyUI accepted the prompt until observation ended: 42 s, 117 s and 65 s. It does not cover the queue wait or the pre-submit phase. Each window includes a first model load. The primary process was relaunched by the 09:05 switch back to primary, and qwen21 by the switch just before 09:17.
- None of the three fell below the 16 GiB threshold, so none of the finished-run lines added "Memory was tight". That wording is proved by `tests/workshop_daily_journeys.py` only.
- Cost: `host_memory.read()` measured 47.1 µs per call over 1,000 calls (shell Python 3.14, not the embedded runtime), which is about 0.01 % of one core at 0.5 s. End-to-end job overhead was not measured.
- Outputs, kept local and not judged for quality:
  - `WAI-Illustration_00047_.png`: `60fcbd02`
  - `Z-Image-Fast_00019_.png`: `b051bec7`
  - `qwen21-t2i_00006_.png`: `2b82794b`

  `qwen21-t2i` reported its known GPU spill (3.2 GB, 0.6 GB lingering), unchanged by this slice. None of this is art acceptance or licence clearance.

Receipts: `receipts/primary.jsonl` and `receipts/qwen21.jsonl` (the driver's log, with the Studio windows and the independent figures), plus `receipts/studio-jobs/<preset>/`, holding the Studio `state.json` (with `host_commit_windows` and the exact submitted graph) and `recipe.json`.

Not verified: a live run that falls below 16 GiB, resumed-observation windows, batch jobs with several windows, and a failure during telemetry on the real host. Each of these is covered by tests only.
