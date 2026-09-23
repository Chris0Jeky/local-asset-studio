# SDXL VAE decode: plain against tiled — 23 September 2026 (overnight lab)

**Question.** The speed census (`../speed-census/`) found every SDXL preset spending 9-10 s sampling but 13 s in VAE decode + save
after a checkpoint switch, with 4.0-5.1 GB of the ComfyUI process in WDDM shared memory during the decode. Does
`VAEDecodeTiled` avoid the spill and the time without visible seams?

**Method.** `ab_vae.py render`, 03:24-03:31 local, straight to the primary ComfyUI (PID 56556, `--reserve-vram 0.6
--disable-pinned-memory`). The shipped `wai` graph (WAI v17, 832x1216, 30 steps euler_ancestral/normal, cfg 5) on the seven
showcase cases of `../suite.py` (fixed seeds 2026092301-07; tag dialect; the SDXL adult-only negative on every case). Per case,
three prompts that differ only in the decoder node: `plain` = `VAEDecode`, `tiled512` = `VAEDecodeTiled` (tile 512, overlap 64),
`tiled1024` = `VAEDecodeTiled` (tile 1024, overlap 64). The first prompt of each case samples; the other two reuse ComfyUI's
cached latent, so they time the decoder alone on an identical latent. The decoder order rotates across cases. Node times come
from ComfyUI's websocket events for our own prompts (`ws.node_seconds` in `results.json`); GPU memory from the 1.5 s timeline.
`ab_vae.py switch` repeats `plain` against `tiled512` right after a checkpoint switch (the census condition) on the `hands` case.
`ab_vae.py diff` compares pixels (`pixel-diff.json`). Blind judging: `seal` shuffled the three decodes of each case under letters;
21 judgements were written before the key was read (`judgements.jsonl`, rubric with R1-R6).

Images of famous characters and fanservice cases are not in Git: they are in ComfyUI
`output/Research/overnight-20260923/sdxl-vae-decode/` with a local `index.html`.

## Results (same latent, decoder only)

| decoder | decode s, 7 cases (median / range) | peak shared MB inside the decode | quality (blind, mean of 5 scores) |
| --- | --- | --- | --- |
| `VAEDecode` (shipped) | 2.35 / 1.62-8.45 | 79-2303 (2.3 GB on 2 of 7 cases; those decoded in 5.9 and 8.5 s) | 4.31 |
| `VAEDecodeTiled` 512/64 | **1.31 / 1.23-1.84** | **79 on every case** (no spill observed in its own window; see below) | 4.31 |
| `VAEDecodeTiled` 1024/64 | 12.95 / 9.09-16.67 | 2815-4183 on every case | 4.31 |

KSampler: 0.233-0.252 s/step (30 steps, 7.95-9.94 s per case). The first prompt of the night on WAI also paid a 23.9 s
checkpoint load.

**Reading the spill column.** The peak is taken inside each prompt's own decode window. Two `tiled512` records carry a
higher `peak_shared_mb` in `results.json` (1447 and 2303), but in both the value is the first sample, taken before the prompt
started, and it is memory left over from the previous prompt's plain decode. Inside their own window both read 79 MB. The main
run sampled every 1.5 s, and a tiled decode lasts about 1.3 s, so a shorter spill could be missed. The after-switch rows below
were therefore sampled every 0.25 s (Codex review of #868).

**After a checkpoint switch (the census condition).** `ab_vae.py switch` and `switch2`: seven checkpoint switches across
Animagine 4, NoobAI 1.1, WAI v17, CSTati v3 and YumeFlux ILv1, on the `hands` case. Each switch sampled once and then ran both
decoders on the same latent, and the decoder that ran first alternated.

| decoder | decode s, 7 switches (median / range) | spill inside the decode window |
| --- | --- | --- |
| `VAEDecode` | 6.79 / 2.14-8.72 | 2.3 GB on 6 of 7 (0.7 GB on the 7th) |
| `VAEDecodeTiled` 512/64 | **1.30** / 1.22-12.52 | none on 4 of 7; **1.2 GB on 3 of 7**, which took 8.2, 8.3 and 12.5 s |

After a switch, tiled 512 is usually fast, but not always: in 3 of 7 it spilled 1.2 GB and took as long as plain
or longer (12.5 s once). Its median is 5x lower than plain's. So the claim is "faster and usually
spill-free", not "never spills".

**Pixels.** `tiled512` against `plain` on the same latent: mean absolute difference 1.5-2.3 levels of 255 (99th percentile 7-13),
spread along edges and fine detail; no straight seam lines in an amplified difference map, and the rows/columns with the largest
differences do not sit on a tile grid. `tiled1024` is closer to plain (mean 0.9-1.4) but slow.

**Blind judging.** The three decodes of each case were indistinguishable at full size (whole frame and side-by-side crops of the
faces, hands and the worst-defect regions); every case got identical scores for its three letters. That is a tie, not a ranking.
The judgements name the cases' own defects (Yor's stub hand at the thigh, the Raiden Shogun's katana where a naginata was asked,
an empty market street), which the decoder does not change.

## Verdict

`VAEDecodeTiled` at tile 512 / overlap 64:
- **Without a switch:** it decoded an 832x1216 SDXL latent in 1.23-1.84 s with no spill observed on 7 of 7 cases, against
  1.6-8.5 s for the shipped `VAEDecode`.
- **After a checkpoint switch:** median 1.30 s against plain's 6.79 s, but in 3 of 7 it still spilled 1.2 GB and took 8-12.5 s.
- **Quality:** no visible difference. The review judge's independent blind second judge (#867) agreed on all 7 subjects and found
  no seams; by its measure tile 1024 is about twice as close to plain as tile 512.
- **Tile 1024** is the slowest of the three here and spills 2.8-4.2 GB every time.

Adopting tile 512 in the SDXL presets is supported by this evidence as a speed gain on most jobs. It is not a guarantee against
the shared-memory spill: that still depends on what the previous job left in VRAM.

## Not verified

- One checkpoint (WAI v17) at one size (832x1216) for the main comparison; five SDXL checkpoints only in the after-switch rows,
  one case each; seven switches are few for a 3-of-7 effect.
- Tile seams were checked on these seven pictures; flat gradients (sky-only frames) are the hardest case and were not targeted.
- Speed through the Studio (the preset path) is inferred from the direct runs; the graph change itself is a separate PR.
