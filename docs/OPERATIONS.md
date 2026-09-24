# Operating the studio

## Local installation

The launcher reuses the installed AMD ComfyUI runtime and weights. It checks whether ComfyUI is running, starts it if needed, starts the studio, and opens the page. Running it again should open the same service. The studio serves only `127.0.0.1:8191`; it is not a network deployment.

`config/local.json` holds this PC's paths and is ignored by Git. The defaults are in `config/example.json`. The current embedded Python/ROCm installation must not be upgraded casually: install experimental dependencies separately and preserve the working runtime.

`primary_reserve_vram` is `0.6` (GiB) by default; `"auto"` measures what other processes hold on the GPU at each launch and reserves that plus 0.7 GiB (`app/gpu_memory.py`). It helps when evicting a text encoder lets the diffusion model fit, and made Krea 2 2.7x slower by forcing a partial load (`docs/RUNTIME-PRECONDITIONS.md` §8). `primary_vram_guard` is true by default: the Studio's primary launch loads `runtime-patches/comfy-extensions/studio_vram_guard` through `--extra-model-paths-config`, so ComfyUI's model evictions count what other processes (dwm, browsers) hold on the GPU. Load decisions are unchanged, so Krea 2 still loads completely. It turns itself off, and says so in `/api/health` (`vram_guard`) and the ComfyUI log, if ComfyUI's `free_memory`/`get_free_memory` source changes (`docs/RUNTIME-PRECONDITIONS.md` §10). Set it false to launch without it. `primary_disable_pinned_memory` is false by default. Set it true only for an explicitly measured primary-runtime experiment; it adds ComfyUI's existing `--disable-pinned-memory` launcher flag and does not alter packages, models or any other backend family.

This PC's `experiments_root` points to the original source checkout's `experiments`
directory, preserving its existing jobs and uploads. Back up that configured path,
not an empty `experiments/runs` in a second checkout. The desktop shortcut launches
this repository; its previous target is preserved in `.runtime`. If another
workspace occupies port 8191, the launcher reports its path. Finish and reconcile
its jobs before stopping the owned process and starting the intended workspace.

`runtime_blocks` in local config maps model families to an observed incompatibility
message. The primary H3 loader remains incompatible, while the isolated
`H3 loader experiment` environment completed a short video using exact-file
read-only mappings. The local opt-in flag permits H3 only in that selected
environment. See [H3 on Windows](H3-WINDOWS.md); file presence alone never proved
runtime compatibility.

The studio submits jobs serially and waits for the ComfyUI queue. Avoid simultaneously pressing Generate in both interfaces. A user can still independently submit work in ComfyUI; the studio is not a global GPU lock.

## When something goes wrong

- **Idle model-cache release (on by default):** ComfyUI keeps every model family it loaded in host RAM after the VRAM is freed, so a session that touched Klein 9B, its text encoder, Anima and Klein 4B held 25.8 GB committed on an idle queue (measured 16 September 2026, recorded in `CURRENT_STATE.md`; one `POST /free` brought it to 5.7 GB and freed 15 GB of physical RAM; the earlier note in `RUNTIME-PRECONDITIONS.md` that `/free` "is not reliable on its own" was about commit headroom after a native allocation failure, a different state). The Studio's worker therefore asks ComfyUI to release that cache (`POST /free` with `unload_models` and `free_memory`) once per idle stretch: after `idle_cache_release_minutes` (default 10) without any Studio job, only when ComfyUI's own queue is empty, and never again until the next job. The next job reloads its models from disk (about 30 s for Klein 9B), which is the price of the freed RAM. `/api/health` reports it under `cache_release` (count, last time, last error, idle seconds, whether a release is pending); set the key to `0` in `config/local.json` to keep the cache resident. Only the primary backend is released; the isolated backends (8192, 8194) are not touched. ComfyUI answers `/free` with an empty 200, which the Studio reads as success.
- **Unload before a model change (on by default):** when the next graph no longer uses a model file the previous Studio graph loaded on the same ComfyUI process (a checkpoint, UNet, text encoder, VAE or other model switch; a LoRA change alone re-patches the loaded model and does not count), or when that idle process already has 512 MB or more in WDDM shared memory (not repeated once an unload has failed to clear it, because the cause is then outside ComfyUI), the worker posts `/free` with `unload_models` only, waits up to 30 s for ComfyUI's `torch_vram_total` to fall, and then submits. Without it ComfyUI leaves part of the previous checkpoint on the GPU, because its free-VRAM figure ignores the desktop's ~3 GB, and each new checkpoint spills further into system RAM (0, 3.7 and 6.0 GB on three SDXL jobs in one process, 23 September 2026; `docs/RUNTIME-PRECONDITIONS.md` §8). The node cache stays warm, so the unloaded model reloads from RAM rather than disk. Each run records what happened under `model_evictions` in its `state.json` (reason, dropped models, shared and reserved bytes before and after, outcome; `nothing resident` when PyTorch held 1 GiB or less, and no `/free` is sent); a busy ComfyUI queue or an unreachable ComfyUI is recorded and the prompt is submitted as before. Primary backend only. Set `"unload_models_on_change": false` in `config/local.json` to turn it off.
- **Runtime recovery (opt-in):** set `runtime_auto_recover: true` in local config only if you want Studio to monitor the selected configured backend. It observes the fixed loopback endpoint at a bounded three-second probe deadline and records `.runtime/runtime-recovery.json` plus `.runtime/runtime-recovery.log`. The page refreshes this status with routine health polling; a disabled monitor never presents a saved enabled/startup state, and **Reset recovery** appears only while the enabled breaker is open. It may start that selected profile only after connection refusal, an exact launcher scan finds no retained process, and no fresh Studio work is queued, submitting or running. For blank protected psutil names, the scan asks Windows for that observed PID's process name with a bounded hidden read-only lookup. A resolved non-Python name is excluded; an unresolved name or protected configured-Python identity remains ambiguous and blocks recovery. It never changes backend family, scans or rewires ports, stops a process, clears a queue, or submits/replays a prompt. An uncertain job is retained as evidence and does not trigger replay; a truly dead backend can still be started while it is retained. A live-but-unhealthy or foreign/ambiguous listener is preserved and reported for inspection. Startup is retained through its timeout and failed starts open the bounded breaker; use **Reset recovery** after inspection to clear the breaker for the next monitor pass.
- **Studio worker unavailable:** health reports this separately and generation is refused. Restart Studio; recovery only covers the selected ComfyUI runtime and never starts a second Studio worker.
- **Offline:** use the desktop shortcut again; inspect `.runtime/` and the ComfyUI launcher logs if startup fails.
- **Missing model/reference:** confirm the configured ComfyUI root, model filename and supplied reference. The presets use exact filenames. Model weights are not bundled in Git.
- **Long job:** Qwen and other large models can take minutes. Do not repeatedly submit. The gallery tracks the existing prompt ID.
- **Uncertain submission:** if the POST response was lost, inspect ComfyUI history before trying again. The job record deliberately prevents an automatic duplicate.
- **After a Qwen-to-SDXL crash:** wait for/inspect the queue, then restart ComfyUI with the existing controls under `C:\AI`. Never kill another application's process or clear an unknown job to make a test pass.
- **Bad art:** execution success only means the graph completed. Compare the result to the brief; use the scorecard and refine one variable.

## Backup and source control

This private repository stores code, recipes, guides, manifests and curated small samples. Models, Python environments, caches, live jobs, logs, ZIPs and input uploads stay out of Git. Back up `experiments/runs/`, ComfyUI `input/` and `output/`, and local config separately if you need every run. Small `.blend`/`.glb` examples are included; keep future very large scenes outside Git or in explicitly configured large-file storage.

**Local-only example media.** Most of `examples/` is committed, but the pictures in four folders are not: `examples/nsfw-lab/` and `examples/civitai-intake/` hold the 21 September 2026 adult-lab contact JPEGs, `examples/combine-research/` holds combine research sheets built on fan pictures, and `examples/local-only/` holds committed pictures later found to contain nude or near-nude renders (both local-only since 23 September 2026); the owner decided those pictures stay on this PC rather than going to GitHub. `.gitignore` refuses `*.jpg`, `*.jpeg`, `*.png`, `*.webp` and the generated `index.html` in all four folders (the list is `LOCAL_MEDIA` in `scripts/validate-repo.py` and `FOLDERS` in `scripts/lab-media.py`); the tracked record is `examples/<folder>/MANIFEST.json`, one entry per picture with its id, file name, sha256, byte count, pixel size, job id, prompt id, source PNG under the ComfyUI output folder, and the one-line inspection note. The Studio still shows them, because `/api/examples/<path>` is served from disk and does not care what Git tracks. Use `python scripts/lab-media.py verify` to check every listed picture is present and unchanged, `restore` to rebuild missing ones from their job PNGs (Pillow at quality 85 with `optimize`, which reproduces the recorded sha256 byte for byte) or from a git ref with `--from-ref`, and `index` to write a gitignored `index.html` contact sheet you can open straight in a browser. `scripts/validate-repo.py` fails if an `/api/examples/` reference has no manifest entry or if an image binary is ever tracked in any of them; it deliberately does not require the files to be present, so CI and a fresh clone stay green with no pictures at all.

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

## Installing another model

The readiness panel and health response now share [exact-path model requirements](MODEL-REQUIREMENTS.md),
including declared inpaint heads/patches. Unknown folders are reported rather than guessed. Install
appears only when the existing installer explicitly supports that pin and the selected backend root;
pin-only or unsourced dependencies explain the manual/source-review path instead. File presence is
not a content-hash, model-compatibility or creative-acceptance claim.

Three standard-library scripts put a weight into the configured ComfyUI folders. None starts ComfyUI or the
studio. The HF/Civitai acquisition scripts download named resources, retain failed `.part` transfers, and
append their receipts to `.runtime/downloads/receipts.json`. Browser intake instead creates an independent
copy and a per-operation journal under `.runtime/downloads/intake/`, preserving its original. It shares the
pinned installer's exclusive lease and no-clobber publication; the other acquisition scripts are not made
lease-aware here, so do not run competing writers. See [intake and recovery](MODEL-INTAKE.md).

```console
python scripts/fetch-hf.py --repo Comfy-Org/Krea-2 --path loras/krea2_darkbrush.safetensors --dry-run
python scripts/fetch-hf.py --repo ilkerzgi/fal-Krea-2-Style-LoRAs --path comfy/dark-fantasy-film.safetensors --name fal-krea2-dark-fantasy-film.safetensors
python scripts/civitai-fetch.py --version-id 3211621 --dry-run
python scripts/intake-downloads.py --dry-run
```

- **`fetch-hf.py`** asks the repository tree API for the file's LFS oid and byte count first, then streams the
  download while hashing it. A mismatch preserves the `.part` file and installs nothing. If the tree advertises
  no oid the script says so before downloading; that copy is unverified against its source.
- **`civitai-fetch.py`** resolves the filename and SHA-256 from `https://civitai.com/api/v1/model-versions/<id>`.
  The metadata is public, so `--dry-run` works with no credentials; the download endpoint is not. The API token
  is read **only** from the `CIVITAI_API_TOKEN` environment variable — never from the command line, never from
  `config/local.json`, never printed, and never forwarded when civitai redirects the download to its CDN host.
  A 401, a 403 (including region blocks) and a 429 each produce a specific message; nothing is installed.
  Pass `--resume` only when the named `.part` file already exists. The script verifies a complete partial
  against the pinned size and SHA-256 and publishes it with a receipt without requesting another body; a
  missing or corrupted partial is refused and retained. An incomplete partial resumes only after strict
  HTTP range and identity-encoding checks.
- **`intake-downloads.py`** inspects `.safetensors` files already sitting in `~/Downloads` (or `--from <dir>`).
  LoRA key/training-metadata hints take precedence, followed by checkpoint, VAE and text-encoder signatures.
  The supported diffusion-backbone hint requires all three key groups: `blocks.*`, `img_in.*` and
  `final_layer.*`, optionally under `diffusion_model.` or `model.diffusion_model.`. Unrecognised or incomplete
  signatures produce **SKIP / Unknown model role**, preserving the candidate before hashing, copying or writing
  a receipt; a familiar filename is not evidence. Mixed batches still process recognised candidates.
  `--dest-folder` explicitly selects a folder for the **whole batch** and bypasses header inspection; use an
  isolated directory of reviewed candidates, preferably with `--dry-run` first. The CLI and receipt label
  `folder_basis` as `header-hint` or `operator-selected`, neither of which proves model identity, lineage or
  compatibility. Browser receipts retain `verified: false`, `expected_sha256: null` and
  `runtime_compatible: null`; record actual provenance separately. Recognised candidates are **copied, not
  moved**, with source identity rechecks and staged byte verification before publication. Browser originals
  remain in place; full copy space plus the existing 20 GiB reserve is required. Per-operation receipts retain
  interrupted evidence. See [the publication contract and recovery steps](MODEL-INTAKE.md), extending the
  earlier [role-classification checkpoint](reconciliation/2026-09-13-oldest-open-issues.md).

After an install, restart ComfyUI (or refresh its model lists) so the new file appears in the node dropdowns,
then add the pinned entry to `models/library.json` and run `python scripts/validate-repo.py`. The entry needs a
lowercase-kebab id, the relative `.safetensors` path, byte count, 64-hex SHA-256 and a huggingface or civitai
URL. Licence and territory facts belong in `models/README.md` next to the pin: record them, never infer them.

## ComfyUI Manager and the Civitai node pack (installed 12 September 2026)

- **Manager.** ComfyUI 0.35 ships the Manager as the `comfyui_manager` pip package (`manager_requirements.txt`
  pins 4.2.2) and only loads it with `--enable-manager`. The owner's launcher `C:/AI/Start-ComfyUI.ps1` now
  passes that flag; the package was installed into the embedded Python with the additions listed in
  [runtime-patches/README.md](../runtime-patches/README.md). Proof it is alive: `GET /v2/manager/version`
  on port 8188 answers `V4.2.2`; the Manager button appears in the ComfyUI sidebar.
- **Civitai node pack.** `custom_nodes/civitai-comfy-nodes` is a plain `git clone` of
  github.com/civitai/civitai-comfy-nodes (its `requirements.txt` needs `requests` and `python-socketio[client]`).
  It reads the API key from the `CIVITAI_API_TOKEN` environment variable first (then `~/.civitai/...`, then a
  browser sign-in), so no key is typed into the panel. The Studio never touches these nodes; they exist for
  the owner's own browsing, cloud generation and model downloads inside ComfyUI.
- **The token lives in the user environment.** `CIVITAI_API_TOKEN` is set at Windows user scope
  (`setx`), so every new process started from Explorer or a fresh shell inherits it, including
  `Start Studio.cmd` and the ComfyUI launcher. `scripts/civitai-fetch.py` reads the same variable. A shell
  that was open before the value was set does not see it until reopened. Rotate it at
  `civitai.com/user/account`; never write it into `config/local.json`, the repository, or a command line.
- **Undo.** Remove `--enable-manager` from the launcher and delete the `custom_nodes/civitai-comfy-nodes`
  folder; the added pip packages are inert without them.
