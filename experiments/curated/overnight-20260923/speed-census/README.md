# Speed census of eleven verified presets — 23 September 2026 (overnight lab)

**Question.** Which of the most-used verified routes are slow on this PC, and why?

**Method.** One Studio job per preset (`POST /api/jobs` with empty controls, so every value is the authored graph default),
one at a time, 03:02-03:17 local, against the primary ComfyUI 0.35.0 (PID 56556, `--reserve-vram 0.6 --disable-pinned-memory`,
restarted about 02:58 after #854; RX 9070 XT 16 GB, ROCm 7.2.1, about 14 GB free VRAM and 14-16 GB free RAM). Presets
sharing a model family ran back to back, so each preset's first job includes its own model load from disk (realistic for a
preset switch). While each job ran, `census.py` (through `../labkit.py`) sampled the ComfyUI process's dedicated and shared
GPU memory every 1.5 s (`app/gpu_memory.py`; timelines in `timelines/`) and read ComfyUI's own log (`/internal/logs/raw`).
Records: `results.json` (job ID, prompt ID, Studio elapsed seconds, peaks, output SHA-256), exact submitted graphs in
`graphs/*.recipe.json`, the phase split in `phases.json` (`phase_table.py`). Every output was inspected at full resolution
with face and hand crops and scored with the shared rubric: `judgements.jsonl` (open judgements, not blind; a census has
nothing to compare against).

## Results

| preset | model | size, steps | total s | submit → sampler s | sampling s | decode + save s | s/step | peak shared MB (sampling / decode) | verdict (agent) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `wai` | WAI v17 | 832x1216, 30 | 50.3 | 34 (first load after restart) | 10 | 5 | 0.24 | – / 1822 overall | fixable |
| `anime` | Animagine XL 4 | 1024², 28 | 43.4 | 19 | 9 | 13 | 0.23 | 158 / **4047** | fixable |
| `pony` | Pony V6 | 1024², 30 | 42.3 | 20 | 9 | 13 | 0.23 | 79 / **4431** | **reject** |
| `noob` | NoobAI XL 1.1 | 832x1216, 28 | 46.3 | 23 | 9 | 13 | 0.24 | 79 / **4991** | fixable |
| `cstati-v3-baseline` | CSTati v3 | 832x1216, 30 | 44.5 | 21 | 10 | 13 | 0.25 | 79 / **4607** | fixable |
| `yumeflux-ilv1-baseline` | YumeFlux ILv1 | 832x1216, 30 | 38.4 | 16 | 9 | 13 | 0.24 | 79 / **5119** | fixable |
| `anima-portrait` | Anima aesthetic 1.1 | 768x1152, 30 | 34.2 | 14 | 16 | 3 | unverified (~0.53 from the 16 s window) | 102 / 3018 | fixable |
| `anima-artist-stack` | Anima base + 6 LoRAs | 832x1216, 30 | 34.3 | 9 | – | – | unverified | 79 overall | fixable |
| `janima-v1-baseline` | JANIMA v1 | 832x1216, 30 | 32.2 | 8 | – | – | unverified | 79 overall | **keep** |
| `zimage` | Z-Image Turbo **bf16** | 1024², 8 | **308.1** | 39 | 246 (incl. 16 s load) | 21 | **28.6** | **715** / 1803 | keep |
| `krea-portrait` | Krea 2 Turbo fp8 + retro LoRA | 768x1152, 8 | **209.3** | 12 | 183 (incl. 29 s load) | 12 | **16.9** | 81 once loaded / **5377** | keep |

Prompt IDs, in order: `7a90cba2`, `759f3f24`, `b4cfb4ff`, `e4a38468`, `7d2f9491`, `40d97aba`, `2f60f01c`, `954ebe85`,
`948d3400`, `507a7765`, `8aed29b6` (full IDs and Studio job IDs in `results.json`). "–": the log lines for that window were
pushed out of ComfyUI's 300-entry log buffer by a custom node's "Civitai Link: Connection error" warning that fires every
~5 s. s/step is the job's own sampler run from ComfyUI's progress lines (steady state between step timestamps; zimage and
krea-portrait are tqdm's own average over 8 steps); the three Anima rows are unverified (see the correction below).

## Findings

1. **SDXL presets are decode- and load-bound, not sampler-bound.** Sampling takes 9-10 s (0.23-0.25 s/step), but a job takes
   38-50 s: about 20 s to reach the sampler (checkpoint load from disk after a switch) and **13 s in VAE decode + save**, during
   which the ComfyUI process holds **4.0-5.1 GB in WDDM shared memory**. ComfyUI first logs "Unloaded partially: 1.3-1.9 GB" of
   the UNet to make room for the VAE, and the decode still lands in shared memory. The first job after the restart (`wai`)
   decoded in 5 s with a smaller spill, so the spill grows once the model cache is warm. This is the cheapest speed lever in
   the Studio: every SDXL/Illustrious preset pays it. Follow-up: `../sdxl-vae-decode/`.
2. **Z-Image Turbo bf16 thrashes.** 28.6 s/step with 715 MB of the diffusion weights in shared memory during sampling: the
   11.7 GB file plus ~1.5 GB of other processes' VRAM overfills the 16 GB card. 308 s per 1024² image. The installed fp8
   build (`z-image-turbo_fp8_scaled_e4m3fn_KJ`, 6.2 GB, SHA-256 matches civitai version 2445746) is the obvious fix.
   Follow-up: `../zimage-fp8/`.
3. **Krea 2 Turbo fp8 fits now, but is still slow.** 12.5 GB loaded completely with no spill during sampling (81 MB shared)
   and 16.9 s/step, half of tonight's earlier 35.4 s/step (the owner closed other GPU apps). Its decode spilled 5.4 GB.
   Follow-up: `../krea-gguf/` (Q5_K_M GGUF, 8.87 GB).
4. **Anima-family presets are the fastest complete routes** (32-34 s, no sampling spill) and JANIMA gave the only `keep`
   among the character presets.
5. **Quality at defaults (agent-judged, not accepted).** 11 outputs: 3 keep (`janima`, `zimage`, `krea-portrait`), 7 fixable,
   1 reject (`pony`: the fox adventurer's head is a faceless black silhouette; the owner called an earlier Pony output "a
   complete mess" too). Hands were the worst defect in 5 of the 9 character pictures (mitten hands, fused fingers), which is the
   owner's standing complaint (HUMAN_TODO q-2). Follow-up: `../hand-fix/`.

Nothing here is art acceptance or licence clearance; the census judgements are one agent's scores on one seed each.

## Correction after review (Codex on #859, 23 September 2026)

The census ran with a `labkit.py` that did not yet filter ComfyUI's log by submission time, so every record's `sampler_runs`
also carried the earlier jobs still in ComfyUI's 300-entry log buffer (for example, `anime` carried WAI's 30-step run).
`repair_sampler_runs.py` now keeps only a job's own, latest run when its step count matches the submitted recipe and its
elapsed time fits the job's own load-to-decode window; the originals stay in `sampler_runs_contaminated`. Result: the six
SDXL rows, `zimage` and `krea-portrait` keep their numbers (each was already its own last run). The three Anima rows are now
**unverified**, because their progress lines were pushed out of ComfyUI's log buffer; the earlier "~0.5", "0.57" and "~0.6" s/step
were inferences and have been withdrawn. `zimage` reads 28.6 (tqdm's average) rather than 28.7 (the steady-state estimate).
Totals, phase windows and spill peaks never used `sampler_runs` and are unchanged. `labkit.py` now compares parsed datetimes
and refuses to submit when the Studio's `/api/jobs` cannot be read (it used to treat that as idle). Later experiments time
steps and nodes from ComfyUI's websocket events for their own prompt, not from the log.

## Not verified

- One seed per preset; timings are single observations, and the first job of each family includes its model load.
- The per-phase split relies on log lines at 1 s resolution; two Anima rows lost their lines to the log-buffer flood.
- Whether the decode spill costs time on every SDXL job or only after a model switch is measured in `../sdxl-vae-decode/`.
