# Blender 5.4 splats and the Blender Lab MCP: trial results, 2 Nov 2026

Executed evidence from the frontier-lab lane of the 2–3 Nov R&D night. The test machine is the Studio PC: Windows 11,
RX 9070 XT, Adrenalin 26.8.1. Blender builds:

- 5.4.0 Alpha `67c9bdddb88b` (built 2026-11-01).
- 4.5.13 LTS, used only as a control.

Lab scripts and renders stay outside Git, in `E:/local-asset-studio-labs/rnd-20261102/frontier-lab/`.

## Gaussian splats in 5.4 alpha

### What the build has

Found by inspecting the RNA (Blender's runtime type data), not inferred from the version number:

- `wm.spz_import`, described as "Import an SPZ file as a gaussian splat point cloud object".
- `PointCloud.type`, an enum with `POINTS` and `GAUSSIAN_SPLAT`.
- `wm.ply_import`, which recognises an INRIA 3DGS PLY and imports it as `GAUSSIAN_SPLAT`.
- No splat export: `wm.ply_export` writes meshes only.
- 4.5.13 has none of these.

### Sample splat

- `nianticlabs/spz` `samples/hornedlizard.spz`: a metal lizard sculpture on a stone plinth, captured inside a garden.
- The repository licence is MIT. The samples carry no separate licence note.
- Commit `bf30541872`, sha256 `a076ca6a…bc6a`, 18.1 MB.
- Import takes 0.37 s and yields 786,233 splats.
- Attributes: `position`, `radiance:base` (FLOAT4: SH DC plus a sigmoid opacity), `scale`, `rotation` (quaternion),
  and `radiance:sh_0..14` (spherical harmonics, degree 3).

### Colour

- I wrote a known-colour 3DGS PLY: 4 spheres of 6,000 isotropic Gaussians, DC only.
- Cycles (CPU) renders them exactly:
  - pure red, green and blue become (255,0,0), (0,255,0) and (0,0,255);
  - 50 % grey becomes (128,128,128);
  - each matches an emission mesh reference of the same colour (Standard view transform).

### Hybrid stage (mesh props beside the lizard)

Cycles CPU, 960×540, 64 spp, 11.5–13.9 s per frame.

- **Depth compositing works both ways.**
  - A mesh cube and cylinder in front of the plinth hide it.
  - A sphere half-buried in the plinth is hidden by the plinth splats, with a clean edge.
- **Splats light meshes in Cycles.** With no lamps and a black world, a white cube still renders grey. With the splat
  hidden, the cube renders black. So the capture works as image-based lighting for meshes placed in it.
- **Mirrors reflect splats.** A mirror sphere reflects the splat garden.
- **Splats receive no light or shadow.** Their radiance is baked, so a sun gives the cube no visible shadow on the splat
  ground. Mesh-on-splat contact shadows need a shadow catcher.
- **On the GPU**, with the same scene and no lamps:

| engine | per frame | cold frame |
|---|---:|---:|
| EEVEE | 0.55 s | 3.06 s |
| Cycles HIP | 1.33 s | 2.02 s |
| Cycles HIP RT | 1.50 s | 2.03 s |

  - EEVEE colour is exact on the known-colour splat, and occlusion is correct both ways.
  - **EEVEE does not use splats as lighting or in reflections:** the white cube renders black and the mirror reflects
    nothing. Cycles on CPU, HIP and HIP RT looks the same in each case and does use them. For EEVEE hybrids, light the
    meshes explicitly, for example with lamps or an HDRI matched to the capture.

## Training a splat on this PC

Brush v0.3.0 (Apache-2.0; Windows zip sha256 `b68e3e9c…bcfcd6`) runs on wgpu/Vulkan. Its log confirms the RX 9070 XT.

### Pipeline

1. `scripts/splat_orbit_dataset.py` renders a GLB in NeRF-synthetic format:
   - 100 training views on a Fibonacci upper hemisphere and 20 held-out views on a separate ring;
   - 512², RGBA, `transforms_*.json` holding Blender's camera matrices.
   - For procgen-lab's shrine-00 this took 2 min 8 s on the CPU.
2. Train:

```bash
brush_app.exe <dataset> --total-steps 30000 --growth-grad-threshold 0.00002 --export-every 10000
```

3. `scripts/splat_eval.py` imports each export into 5.4 and renders the held-out cameras (EEVEE, about 3.4 s for 20).
   `score` composites over white and reports PSNR plus the render critic's pixel-diff count.

### Results

| run | steps | wall | splats | held-out PSNR mean (min) |
|---|---:|---:|---:|---:|
| Brush defaults | 10k | 55 s | 4,980 | 19.0 (15.9) |
| growth threshold 2e-5 | 10k | — | 6,787 | 27.8 (24.8) |
| growth threshold 2e-5 | 20k | — | 9,549 | 30.0 (28.3) |
| growth threshold 2e-5 | 30k | 149 s for the whole run | 9,549 | **30.3 (28.4)** |

- The camera convention needs no conversion: Blender matrices go into Brush, out as PLY and back into Blender, and they
  line up.
- At the defaults, densification stalls on a small synthetic scene. The growth threshold is the setting that matters.
- Remaining differences: cast shadows are softer and lighter (radiance is baked from the training views), and there is
  some speckle along edges.
- The critic's parity gate flags every view (on average 4.5 % of pixels change). That is correct: its thresholds are
  for exact parity, not splat fidelity.

## Blender Lab MCP (`projects.blender.org/lab/blender_mcp`)

### Setup

- Commit `dbbf836` (2026-09-29), version 1.0.2, GPL-3.0-or-later.
- Cloned to a disposable folder and installed in a Python 3.12 venv with `mcp` 1.30.0.
- Run against 5.4 alpha with a throwaway `BLENDER_USER_RESOURCES`.
- Every probe opened a throwaway `.blend`; no Studio or MIRA asset was opened.

### What I measured

- **26 tools**:
  - arbitrary `execute_blender_code`, plus a `_for_cli` variant that runs a background Blender;
  - blend-file summaries (data blocks, missing files, linked libraries, usage guess);
  - object summaries, screenshots, viewport jumps and render-to-path;
  - full-text search over the bundled Blender API and manual.
- **Windows stdio bug, reproduced** (upstream #42, #58, #60, all open):
  - `get_blendfile_summary_datablocks_for_cli` over stdio timed out after 122.1 s.
  - Adding `stdin=subprocess.DEVNULL` to `tools_helpers/blender_cli.py::run_blender_cli` in the disposable clone fixed
    it: 4.0 s, correct result.
- **Online access required:**
  - `blender --online-mode -b f.blend --command blender_mcp --port 9876` starts the background add-on server.
  - Without `--online-mode` it refuses with "Online access must be enabled".
- **Latency:** typed tools over TCP answer in 0.00–0.03 s. API search takes 0.9 s warm and 30 s on the first call.
- **No sandbox:**
  - `execute_blender_code_for_cli` listed the home folder and could see the Studio checkout.
  - The "weak sandbox" blocks `sys.exit` and `wm.read_factory_settings`, but `os._exit(0)` killed Blender (the client
    got WinError 10054).
  - Upstream calls the sandbox a slap on the wrist.
- `get_python_api_docs("bpy.types.Object.location")` returns not found (upstream #62).
- Screenshot tools need the GUI.

### Verdict

Study it and borrow from it; don't adopt it as the Studio's Blender boundary. Its value:

- A persistent process: answers come back in milliseconds.
- A fast offline API and manual search.
- Typed read tools that match what a scene manifest wants (missing files, linked libraries).
- The `--command` background server, a ready pattern for a persistent worker.

Its centre is unguarded `exec`, running with the user's full filesystem rights and leaving no receipts. If someone wants
to explore with it, run it disposably: a throwaway user-resources folder, copied files only, and the one-line
`stdin=DEVNULL` patch on Windows.

### Not tested

- GUI add-on mode (screenshots, deferred tools).
- An LLM driving it end to end.
- The `render_*_to_path` tools.
- The upstream fix was not filed (an outward-facing action; it is a one-line PR for #42).
