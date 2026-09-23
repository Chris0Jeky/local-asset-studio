---
name: studio-runtime-models
description: "Change how Local Asset Studio reaches its local runtimes and models: backend environments and ports, launchers, runtime patches, checksum-pinned model installs, provenance and licence-territory records. Use for app/backends.py, app/model_library.py, scripts/*-launch.py, runtime-patches/ and models/; not for graphs or generations."
---

# Studio runtime and models

## Use when / Do NOT use when

Use for `app/backends.py`, `app/model_library.py`, `scripts/Start-Studio.ps1`, `scripts/h3-launch.py`,
`scripts/h3_mmap_loader.py`, `scripts/hidream-launch.py`, `scripts/qwen21-launch.py`, `runtime-patches/`, `models/*.json` and
`config/example.json`. Do NOT use for presets or graphs (`studio-preset-slice`), for proving a run
(`studio-execution-evidence`), or for Krita/Blender/Godot paths (`studio-native-adapter`).

## Guardrails

- Never edit installed ComfyUI source or upgrade packages in the shared Torch/ROCm runtime. A needed
  change is a documented patch in `runtime-patches/` with before/after SHA-256 and the ComfyUI commit.
- Backend switches are explicit, one at a time, and recorded in `.runtime/backend-state.json`;
  `psutil` stops only processes the Studio owns. Ports are fixed: 8188 primary, 8191 Studio, 8192
  HiDream, 8194 H3 loader, 8196 Qwen-Image 2.1 (isolated ComfyUI v0.37.0).
- A model enters `models/library.json` only with sha256, byte count and a relative path in a supported
  folder; weights never enter Git. `.safetensors` with a huggingface/civitai URL installs automatically;
  `.gguf`, `.pth`, `.pt` and `.onnx` are pin-only (presence and size reported, installer refuses), and a
  pin with no curated origin leaves `url` empty and says why in `terms`. Provenance is not authentication:
  matching hashes do not prove the creator or grant commercial rights.
- Licence and territory terms are recorded as facts with a dated source link. Known gates: Hunyuan3D
  2.1 and HY-Motion 1.0 exclude UK use; NoobAI excludes commercial products; H3 needs an eligible
  territory. Do not infer one provider's confirmation covers another.
- Never change paging, driver or system settings to make a loader work; record the failure instead.

## Workflow

1. State the runtime change and its blast radius: which profile, port, launcher or model, and what
   keeps working untouched. Read `CURRENT_STATE.md` for the last measured state of that runtime.
2. For environments: edit the profile in `BackendManager.profiles` or the launcher script; keep the
   `primary` profile the default; make readiness checks read-only (`/system_stats`, `/api/identity`).
3. For models: add the pin with hash and URL, a `models/README.md` note on terms, and the install
   route through `ModelLibrary.start_install`; never download inside a test.
4. For patches: write the `.patch`, the JSON with source hashes, and a README paragraph naming the
   failing prompt ID that motivated it.
5. Prove offline: `python -m unittest discover -s tests -p "test_backends.py"` (the `tests.test_backends` form dies
   on import), `python -m unittest tests.test_model_library tests.test_h3_loader_header` and `python scripts/validate-repo.py`. A live switch or install is evidence work: run it once,
   capture `.runtime/*.log` and record it via `studio-execution-evidence`.
6. Update `docs/H3-WINDOWS.md`, `docs/HIDREAM.md` or `docs/OPERATIONS.md` only for what actually ran.

## Read first

`CURRENT_STATE.md` head; `models/README.md`; `runtime-patches/README.md`; `docs/H3-WINDOWS.md` when H3 is involved.
