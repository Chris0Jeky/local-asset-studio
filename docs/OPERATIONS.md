# Operating the studio

## Local installation

The launcher reuses the installed AMD ComfyUI runtime and weights. It checks whether ComfyUI is running, starts it if needed, starts the studio, and opens the page. Running it again should open the same service. The studio serves only `127.0.0.1:8191`; it is not a network deployment.

`config/local.json` holds this PC's paths and is ignored by Git. The defaults are in `config/example.json`. The current embedded Python/ROCm installation must not be upgraded casually: install experimental dependencies separately and preserve the working runtime.

This PC's `experiments_root` points to the original source checkout's `experiments`
directory, preserving its existing jobs and uploads. Back up that configured path,
not an empty `experiments/runs` in a second checkout. The desktop shortcut launches
this repository; its previous target is preserved in `.runtime`. If another
workspace occupies port 8191, the launcher reports its path. Finish and reconcile
its jobs before stopping the owned process and starting the intended workspace.

`runtime_blocks` in local config maps model families to an observed incompatibility
message. H3 is currently blocked after two Windows ROCm encoder crashes. Do not
remove that entry merely because all model files are present. First establish a
compatible encoder/runtime in an isolated test; see the Workflow Lab guide.

The studio submits jobs serially and waits for the ComfyUI queue. Avoid simultaneously pressing Generate in both interfaces. A user can still independently submit work in ComfyUI; the studio is not a global GPU lock.

## When something goes wrong

- **Offline:** use the desktop shortcut again; inspect `.runtime/` and the ComfyUI launcher logs if startup fails.
- **Missing model/reference:** confirm the configured ComfyUI root, model filename and supplied reference. The presets use exact filenames. Model weights are not bundled in Git.
- **Long job:** Qwen and other large models can take minutes. Do not repeatedly submit. The gallery tracks the existing prompt ID.
- **Uncertain submission:** if the POST response was lost, inspect ComfyUI history before trying again. The job record deliberately prevents an automatic duplicate.
- **After a Qwen-to-SDXL crash:** wait for/inspect the queue, then restart ComfyUI with the existing controls under `C:\AI`. Never kill another application's process or clear an unknown job to make a test pass.
- **Bad art:** execution success only means the graph completed. Compare the result to the brief; use the scorecard and refine one variable.

## Backup and source control

This private repository stores code, recipes, guides, manifests and curated small samples. Models, Python environments, caches, live jobs, logs, ZIPs and input uploads stay out of Git. Back up `experiments/runs/`, ComfyUI `input/` and `output/`, and local config separately if you need every run. Small `.blend`/`.glb` examples are included; keep future very large scenes outside Git or in explicitly configured large-file storage.

The migration copied the original artifacts; it did not move or delete them. `docs/migration-manifest.json` records original copies. Files modified for portability after copying naturally have newer hashes. Old absolute paths in `docs/research/` are historical evidence; current instructions start in this directory.

## Add another preset

1. Save a working API graph in `workflows/api/` and its visual counterpart in `workflows/comfyui/`.
2. Add a catalog entry mapping controls to `[node-id, input-name]`. Use `bindings_extra` when one visible control must update multiple inputs, such as FLUX scheduler dimensions.
3. Set `verified` false until a real generation succeeds. Add an honest commercial note and useful defaults.
4. Run `python scripts/validate-repo.py` and the tests. Restart the studio to reload the catalog.
5. Try one image, inspect it, and record the outcome in `experiments/curated/`.

Do not change one checkpoint dropdown to a different architecture and assume compatibility. SDXL checkpoints, FLUX, Qwen, ControlNets and LoRAs require matching graphs.

`scripts/build-expansion.py` regenerates the 20 Workflow Lab graphs from the native
node schema and the two source graphs in `workflows/sources`. It resets the new
presets' execution badges conservatively. Reconcile changed graphs with curated
recipes before recording fresh execution evidence. Validate installed native nodes
without submitting work with `python scripts/validate-live.py`.

Portable result recipes now contain the actual submitted graphs. Import rejects
older recipes without an embedded workflow and recipes that differ from the
current preset. Preserve the original JSON; use its controls deliberately in a
new setup or open the embedded graph in ComfyUI. Reference images and weights are
separate dependencies and must also be present on the destination machine.

## Batch generation and finishing

```console
python scripts/run-batch.py --graph workflows/api/realvis-api.json --out experiments/runs/manual-product-test --count 3 --seed 4200
python scripts/run-batch.py --graph workflows/api/realvis-api.json --out experiments/runs/manual-product-test --count 3 --seed 4200
```

The second command resumes/skips completed work; changing inputs requires a new output directory. This CLI records ComfyUI output descriptors but does not populate the studio gallery. It currently targets port 8188. Keep CLI and studio batches separate.

Asset finishing uses the existing Pillow/rembg environment, configured as `asset_python`. Run `scripts/assets.py --help` with that interpreter for slicing, atlas, GIF, WebP, compositing and background removal. Those operations are not all exposed in the first studio UI.
