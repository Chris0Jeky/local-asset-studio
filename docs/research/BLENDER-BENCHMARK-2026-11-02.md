# Blender GPU benchmark, 2 Nov 2026 (RX 9070 XT)

Executed evidence from the frontier-lab lane of the 2–3 Nov R&D night. Script: `scripts/blender_bench.py`.

## Setup

- Windows 11, i5-13600K, 32 GB, Radeon RX 9070 XT 16 GB (gfx1201), Adrenalin 26.8.1.
- Blender 4.5.13 LTS (`daeeeca98fb0`) and 5.4.0 Alpha (`67c9bdddb88b`, built 2026-11-01), portable, `--factory-startup -b`.
- Run under the night's GPU lease. See Results for which rows other GPU work disturbed.
- Scene: the script's generated stress scene, 1280×720. It has 100 linked-duplicate subdivided monkeys (~1.57 M
  triangles instanced) in diffuse, metal and glass, plus two area lights.
  - Cycles: 128 spp, adaptive sampling and denoising off, seed 0.
  - EEVEE: 64 samples, raytracing on.
- Each row is a fresh process: one cold render (kernel and shader compile, BVH), two warm-ups, then five timed renders.
- Memory: peak private bytes of the Blender process tree is sampled every 0.25 s. VRAM is the sampled peak of the
  Windows `GPU Adapter Memory` counter over the pre-run baseline, with one query about every 1.5 s on its own thread.
  It is adapter-wide.
- Each run writes its frames to its own folder. A run counts only if Blender printed its result and exited 0 within
  `--timeout`.
- Reproduce:

```bash
python scripts/blender_bench.py --blender <blender.exe> --engine cycles --device HIPRT --out bench.jsonl
```

```bash
python scripts/blender_bench.py --blender <blender.exe> --engine eevee --gpu-backend vulkan --out bench.jsonl
```

```bash
python scripts/blender_bench.py --table bench.jsonl
```

## Results

The matrix ran twice.

- **Run 1** (05:46–06:05):
  - The GPU was idle apart from 5.8 GB of resident VRAM.
  - Blender's on-disk shader cache was empty.
  - It used the first sampler, whose memory samples stalled during each VRAM query, so its memory peaks are low and
    are not shown.
- **Run 2** (06:14–06:20), with the fixed sampler:
  - The shader cache was warm.
  - The 5.4α Cycles rows were disturbed by other GPU work. Renders swung between 7 and 12 s, although no other lane
    held the GPU lease.
  - A third run of those two rows (06:22) was disturbed too: one HIP RT render took 35 s and the cold HIP render 19 s.
  - The run-2 numbers for those rows are therefore marked *contended*.

| Blender | engine | device/backend | cold s, run 1 (cache cold) | cold s, run 2 (cache warm) | warm median s, run 1 | warm median s, run 2 | peak private MB (run 2) | VRAM +MB (run 2) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 4.5.13 | Cycles | HIP | 7.36 | 6.79 | 5.79 | 5.66 | 3455 | 3240 |
| 4.5.13 | Cycles | HIP RT | 5.46 | 5.75 | **4.77** | 4.90 | 2710 | 3479 |
| 5.4α | Cycles | HIP | 6.84 | *contended* | 5.74 | *contended* (re-run median 6.23) | 2372 | 2162 |
| 5.4α | Cycles | HIP RT | 6.13 | *contended* | 5.56 | *contended* (re-run median 5.40) | 1895 | 3368 |
| 4.5.13 | EEVEE | OpenGL | 13.59 | 5.25 | 0.93 | 0.69 | 4774 | 3554 |
| 4.5.13 | EEVEE | Vulkan | 13.76 | 0.63 | 0.90 | **0.42** | 2351 | 1730 |
| 5.4α | EEVEE | OpenGL | 21.62 | 3.35 | 0.81 | 0.51 | 3493 | 2825 |
| 5.4α | EEVEE | Vulkan | 11.01 | 2.79 | **0.52** | 0.62 | 2090 | 1598 |

## What it says

- **"Cold" has two meanings and they differ by up to 20×.**
  - A fresh process with an empty shader cache took 11–22 s for the first EEVEE frame.
  - A fresh process with a warm cache took 0.6–5 s.
  - Report the cache state with every cold number.
  - On 4.5.13 OpenGL, the warm-ups after a cold start still took 4.9 s and 3.5 s (run 1) and 4.2 s (run 2), because
    shader compilation spills past the first render. Two warm-ups is the minimum.
- **HIP RT** cut the warm Cycles time on 4.5.13 by 18 % in run 1 and 13 % in run 2. On 5.4α the uncontended run 1
  shows only 3 %. One scene; HIP RT gains depend on the scene.
- **EEVEE warm:**
  - Vulkan beats OpenGL on 4.5.13 in both runs (0.90 vs 0.93 s, then 0.42 vs 0.69 s).
  - On 5.4α the order flips between runs (0.52 vs 0.81 s, then 0.62 vs 0.51 s).
  - So 5.4α has no consistent speed winner between the two within this noise.
  - Vulkan uses the least VRAM in every pair (1.6–1.9 GB vs 2.8–3.6 GB) and the least private memory.
- **The GPU lease is not enough isolation.** Other GPU work changed 5.4α Cycles timings by up to 6× without anyone
  holding the lease. A benchmark needs the GPU's utilisation counter watched for the whole run, not only checked at
  the start.
- **Determinism:**
  - Cycles GPU repeats are never bit-identical; they drift by up to one 8-bit level.
  - HIP and HIP RT frames differ by a mean |Δ| of 0.019, in sparse noise pixels.
  - 4.5.13 and 5.4α frames differ by a mean |Δ| of about 0.16, roughly 8× more.
  - EEVEE repeats drift by up to 2–3 levels (22 on 4.5.13 with Vulkan). OpenGL and Vulkan frames have identical
    channel means.
  - So compare renders with a tolerance, never by file hash. PNG metadata (render time, date) also changes the bytes
    of identical images, which is why the script hashes decoded pixels.
- **Backend check:** run once with `--debug-gpu`. Blender then logs `gpu.vulkan … AMD Radeon RX 9070 XT … 26.8.1
  (LLPC)` or its OpenGL debug hook.
- **Vulkan risk:** 5.4α with `--gpu-backend vulkan --debug-gpu` raised `VK_ERROR_DEVICE_LOST` once on a 64 px EEVEE
  render. The same backend without `--debug-gpu` rendered every benchmark frame. It was not repeated, because a device
  loss can disturb other GPU users.

## Not measured

- Viewport interaction, which needs a window.
- The Blender demo files (this run used the generated scene only).
- 5.2 LTS, which is not installed.
- Denoised quality.
- Thermal or clock state.
- An uncontended 5.4α Cycles run with the fixed sampler.
- The VRAM column is adapter-wide, so it is approximate whenever anything else allocates during a run.
