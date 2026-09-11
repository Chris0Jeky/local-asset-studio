---
paths:
  - "presets/**"
  - "workflows/**"
  - "models/**"
---

# Catalog, graph and model-pin region

- `presets/catalog.json` is the allow-list: only inputs bound there (`[node_id, input_name]`, plus
  `bindings_extra`) are ever written by the server. A graph edit that renames or moves a bound input
  breaks the preset silently at runtime; `python scripts/validate-repo.py` catches it, so run it.
- API graphs live only under `workflows/api/`, visual graphs under `workflows/comfyui/`; the validator
  refuses paths outside them. Do not confuse the two formats.
- New or changed presets start with `verified: false` and an honest `commercial_note`. `verified: true`
  only after a real generation was inspected and recorded (`studio-execution-evidence`).
- Do not swap a checkpoint to a different architecture inside an existing graph; SDXL, FLUX, Qwen,
  ControlNets and LoRAs need matching graphs.
- `models/library.json` entries need a lowercase-kebab id, a 64-hex sha256, positive byte count, a
  relative `.safetensors` path and a huggingface, civitai or civitai.red URL. Weights themselves never enter Git.
- Licence and territory facts are data, recorded next to the pin (`models/README.md`, provenance JSON),
  never inferred from an open-weights badge.
