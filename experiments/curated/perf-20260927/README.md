# Back-to-back Qwen-Image 2.1 jobs: release-then-remeasure at the commit gate, 27 September 2026

This is the lab3 GPU session (08:46-09:05 local). It covers issue #305, with refs #306 and #308. The change is `commit_gate_release_seconds` on branch `claude/lab3-commit-release`: before the 32 GiB host-commit gate refuses a measured shortfall, the Studio frees the job's own idle backend and measures again. The gate, its scope and its message are unchanged, and only a fresh passing reading admits a job.

The workload was preset `qwen21-rgba` on the isolated `qwen21` backend (port 8196). Every render was 1024x1024 at the preset's default 25 steps. The same positive prompt was used every time (the folio/frame/star line illustration from `asset-kit-20260927`'s `state-blank`; the exact text is in `receipts/backtoback.py` and in each `recipe.json`), and each job had its own seed. No input images. Commit limit throughout: 95.73 GiB (64 GiB page file).

Receipts:
- `receipts/*.jsonl`: one file per run, written by `receipts/backtoback.py`. Commit was sampled every 0.5 s from create to completion. A job ID is logged at create and a prompt ID as soon as the Studio reports it.
- `receipts/studio-jobs/<key>/`: the Studio's own `state.json`, holding the exact submitted graph, the `host_commit_readings` and any `commit_releases`, plus `recipe.json` for each job. `index.jsonl` maps keys to job IDs.
- `receipts/release-transient.jsonl`: one manual `/free`, sampled every 0.2 s, with no generation.

## Before: main code without this change (the Studio process started 26 Sep 22:24 from the main checkout; restarted on main `bb4dc273` for the batch)

| Run (window) | What happened |
| --- | --- |
| `before` (08:46:31-08:50:31) | `before-1` completed: job `7c20bc88`, prompt `27312c98-1491-439c-a32f-a84692f449d7`, 56.4 s, the first load after the switch. It left 26.58 GiB of headroom. The next four creates, two keys with two attempts each, were **refused**: "Host commit headroom 26.5 GiB is below the required 32 GiB" (26.9 GiB on the last). The driver's `/free` in between returned HTTP 403 because of a driver bug: it sent a Studio `Origin` to ComfyUI. So nothing released anything, and headroom stayed at 26.5-26.9 GiB for 3 min 1 s. The qwen21 cache does not release on its own; the Studio's idle release covers only the primary backend, after 10 min. |
| `before-manual` (08:50:58-08:53:13) | Today's workaround: refused, then `POST /free` by hand, then create again. Headroom crossed 32 GiB 11.04 s and 8.01 s after the `/free`. `before-manual-1`: job `4b652de6`, prompt `15e5ffe5-4e73-48e8-802a-ac181c1066b1`, 54.7 s. `before-manual-2`: job `94083679`, prompt `717e8893-e212-4b63-a5e7-38cdd365e1fb`, 53.6 s. |
| `before-batch` (09:03:43-09:04:47) | Refused, `/free` by hand (32 GiB after 7.01 s), then one job with `batch_count` 3: job `66353ab7`, **partial**. Output 1 completed (prompt `b3a81b85-6b55-4b63-bb26-ea6c85b281ec`). Output 2 was stopped by the gate: "Host commit headroom 27.6 GiB is below the required 32 GiB ... No prompt was submitted for output 2." |

## After: this branch, `commit_gate_release_seconds: 45`

The Studio was run from the branch worktree against the same repository root, config and experiments store. The sequential run used commit `286d6122`. The batch used `677449f0`, which adds the floor described below; the floor did not trigger. That run used an 18 GiB floor. Review then raised it to 22 GiB, skipped at or below, and the releases measured here would still pass it: headroom before each release was 26.9-27.6 GiB.

| Run (window) | Job, prompt ID(s) | Headroom at create or before release → after release | Release wait | Job elapsed (includes the release) |
| --- | --- | --- | --- | --- |
| `after-1` (08:53:55-08:55:09) | `60210246`, `f3801bb7-e31b-4a73-a037-1fc230dc7710` | 27.00 → 36.65 GiB | 10.5 s | 71.2 s |
| `after-2` (08:55:10-08:56:24) | `a146e6cf`, `85d0f8a6-537b-48b6-ae37-9077f143773a` | 26.90 → 38.15 GiB | 7.0 s | 70.8 s |
| `after-3` (08:56:24-08:57:34) | `5d5c6c2c`, `8d431fc8-2e40-494f-bd03-b59d8b87225a` | 27.37 → 36.18 GiB | 9.1 s | 66.1 s |
| `after-batch` (08:59:30-09:02:43), `batch_count` 3 | `2c0a35f0`, `5872c64a-be7e-4661-9a07-bbc5b10809dd`, `6e5df8d0-9e47-47d6-9673-c1a70357cd3d`, `a7b637fc-619a-4c9e-a368-01ea946abbf2` | output 1: none needed (46.43 GiB); output 2: 27.55 → 34.67; output 3: 27.53 → 39.23 GiB | 11.5 s, 8.0 s | 189.1 s |

- All three creates were accepted, each with a `deferred` prepared reading and the message "Queued. Memory headroom is 27.0 GiB and this job needs 32 GiB; before sending it the Studio will free ComfyUI's cached models and measure again". Each job's pre-submit reading was a fresh pass of the unchanged gate: 36.65, 38.15 and 36.49 GiB.
- Outcome: **6 of 6 outputs sent and completed with no refusal and no manual step**. The before runs had 7 refused creates: 4 in `before`, 2 in `before-manual` and 1 in `before-batch`. Every job after the first needed a manual `/free`, and the batch ended `partial` after output 1.

### Timing: no speed-up, and one unexplained difference

- The model reload after a release is the same cold-load cost that the manual workaround pays, so nothing got faster. From refusal to completion, the manual workaround took 66.7 s and 62.6 s (the `/free` wait plus the job wall time). The automatic path took 66.1-71.2 s from create to completion.
- The generation part alone (pre-submit reading to finish, from `state.json`) was 57.0-63.7 s after (60.5, 63.7, 57.0) and 53.5-56.3 s before (56.3, 54.6, 53.5, and 53.8 for batch output 1). The cause of the 3-10 s gap was not isolated, and three samples per side cannot separate it from noise. One candidate: the Studio posts as soon as the reading crosses 32 GiB, while the release was still finishing. In the transient run, headroom went from 32.7 to 46.2 GiB in the following second.

### Commit peaks: the release briefly uses more commit before it frees any

The before windows peaked at 76.4-77.3 % commit (21.74-22.64 GiB left) during the job. The after windows peaked at 86.8-87.4 % (12.09-12.68 GiB left). Each after peak came **during the release, before the prompt was posted**:
- `after-1`: peak 08:54:02, pre-submit 08:54:06
- `after-2`: peak 08:55:15, pre-submit 08:55:17
- `after-3`: peak 08:56:31, pre-submit 08:56:33
- batch output 2: peak 09:00:38, pre-submit 09:00:39

The manual workaround has the same transient. The before windows simply did not sample it, because the driver's sampler started at create, after the manual `/free`.

`release-transient.jsonl` measured this directly with no generation. The `/free` was posted at 08:58:09 with 27.36 GiB of headroom. Headroom fell to **12.65 GiB (86.8 %) 6.6 s later**, reached 32.72 GiB at +8.0 s, and settled at 46.2 GiB from +9 s to +25 s. ComfyUI moves the GPU-resident weights into host RAM before it drops them.

This is why the release is skipped at or below **22 GiB** of headroom (`COMMIT_RELEASE_FLOOR_BYTES`). That is a 16 GiB budget for the transient (the whole card, since only VRAM-resident weights can move; 14.7 GiB was measured here) plus a 6 GiB margin. This host fails near 97 % commit, which is about 2.9 GiB left of 95.73 GiB. A release started with less headroom could exhaust commit on its own. The same transient applies to any manual or idle-timer `/free`. The idle timer (#470) does not check headroom first.

## Outputs

These are 1024x1024 RGBA PNGs in `C:/AI/experiments/qwen-image-21/ComfyUI/output/Studio/`, kept local. Each is listed as file, then SHA-256 prefix:
- `qwen21-rgba_00009_` (before-1): `fe9699f5`
- `_00010_` (before-manual-1): `16031bf2`
- `_00011_` (before-manual-2): `2d0180a7`
- `_00012_` (after-1): `ff7d1d54`
- `_00013_` (after-2): `816fec99`
- `_00014_` (after-3): `6490ab1c`
- `_00015_` to `_00017_` (after-batch): `c4076879`, `a39b5efd`, `47f8ba9d`
- `_00018_` (before-batch output 1): `d98ff238`

All ten have a real alpha channel, with 20.2-85.6 % of pixels fully transparent. Only `_00012_` was opened: it shows the folio, frame and star. This was a scheduling benchmark. Nothing was judged for quality: not art acceptance, not licence clearance, and the Qwen Research License is non-commercial.

## Not verified

- The failure paths were not exercised on the GPU: an insufficient release, the 22 GiB floor, a failed commit read after `/free`, a busy queue, a running switch and a failed `/free`. They are covered by `tests/test_server.py` with FakeStudio.
- Production plan stages still call `prepare()`, which keeps the old refusal at the plan's own preflight. Only `create_job` and the worker's pre-submit check changed.
- Releases on the primary backend and on Qwen-Image-Edit or FLUX.2 graphs were not measured.
- Warm retention, meaning keeping Qwen resident between jobs, was not attempted. The gate cannot admit it with this machine's current baseline.
