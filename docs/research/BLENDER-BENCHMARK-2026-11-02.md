# Blender GPU benchmark, 2 Nov 2026 (RX 9070 XT)

Executed evidence from the frontier-lab lane of the 2–3 Nov R&D night. Script: `scripts/blender_bench.py`.

## Setup

- Windows 11, i5-13600K, 32 GB, Radeon RX 9070 XT 16 GB (gfx1201), Adrenalin 26.8.1.
- Blender 4.5.13 LTS (`daeeeca98fb0`) and 5.4.0 Alpha (`67c9bdddb88b`, built 2026-11-01), portable, `--factory-startup -b`.
- GPU otherwise idle under the night's GPU lease (~1 % utilisation, 5.8 GB VRAM resident from other processes).
- Scene: the script's generated stress scene, 1280×720. It has 100 linked-duplicate subdivided monkeys (~1.57 M
  triangles instanced) in diffuse, metal and glass, plus two area lights.
  - Cycles: 128 spp, adaptive sampling and denoising off, seed 0.
  - EEVEE: 64 samples, raytracing on.
- Each row is a fresh process: one cold render (kernel and shader compile, BVH), two warm-ups, then five timed renders.
- Memory: peak private bytes is sampled every 0.25 s. VRAM is the Windows `GPU Adapter Memory` peak over the pre-run
  baseline.
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

| Blender | engine | device/backend | cold s | warm median s (min–max) | peak private MB | VRAM +MB |
|---|---|---|---:|---:|---:|---:|
| 4.5.13 | Cycles | HIP | 7.36 | 5.79 (5.71–5.88) | 3419 | 3267 |
| 4.5.13 | Cycles | HIP RT | 5.46 | **4.77** (4.74–4.86) | 2695 | 3378 |
| 5.4α | Cycles | HIP | 6.84 | 5.74 (5.53–5.81) | 2414 | 2779 |
| 5.4α | Cycles | HIP RT | 6.13 | 5.56 (5.47–6.06) | 1883 | 3271 |
| 4.5.13 | EEVEE | OpenGL | 13.59 | 0.93 (0.84–1.08) | 4537 | 3637 |
| 4.5.13 | EEVEE | Vulkan | 13.76 | 0.90 (0.75–0.97) | 2818 | 1902 |
| 5.4α | EEVEE | OpenGL | 21.62 | 0.81 (0.63–0.89) | 3758 | 2824 |
| 5.4α | EEVEE | Vulkan | 11.01 | **0.52** (0.49–0.56) | 2444 | 1598 |

## What it says

- **HIP RT:**
  - It cuts the warm Cycles time by 18 % on 4.5.13 but only 3 % on 5.4α.
  - 5.4α with HIP RT is 16 % slower than 4.5.13 with HIP RT on this scene.
  - Both are one-scene results; HIP RT gains depend on the scene.
- **EEVEE on 5.4α with Vulkan is the fastest configuration measured:**
  - 36 % faster warm than 5.4α OpenGL, and 44 % faster than 4.5.13.
  - It uses the least VRAM.
  - Its cold start is half that of 5.4α OpenGL.
- **Warm-up:** on 4.5.13 OpenGL, the two warm-ups still took 4.9 s and 3.5 s because shader compilation spills past the
  first render. Two warm-ups is the minimum; report cold and warm separately.
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
- The VRAM column is adapter-wide, so it is approximate whenever anything else allocates during a run.
