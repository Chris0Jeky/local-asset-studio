---
name: studio-preset-slice
description: Add or change a Studio preset, API/visual workflow graph, catalog binding, variant or reference slot in Local Asset Studio. Use when a request names a new recipe, model family, control or graph edit; not for running generations or installing models.
---

# Studio preset slice

## Use when / Do NOT use when

Use for edits to `presets/catalog.json`, `workflows/api/*.json`, `workflows/comfyui/*.json`, or the
binding logic in `app/server.py` (`CONTROL_KEYS`, `_bind_control`, `prepare`). Do NOT use to run the
recipe (that is `studio-execution-evidence`), to install or pin a model (`studio-runtime-models`), or
for native export paths (`studio-native-adapter`).

## Guardrails

- The catalog is the allow-list. Never make the server write an input that is not bound in the catalog.
- LoRA slots are paired controls — `lora`/`lora_name`, `lora2`/`lora2_name`, ... — a strength plus an
  installed basename. Author every slot to a file that is actually installed: ComfyUI rejects an
  unknown `lora_name` with HTTP 400 before execution, even at strength 0.
- Strength 0 means off, not "loaded at zero": `prune_disabled_loras()` drops the node from the
  submitted graph and rewires model/clip around it, repeatedly, so chains collapse. Author the graph
  as if every slot were on, then leave the optional ones at 0.
- Do not claim a preset works because the validator passed; `verified` stays `false` until a real
  generation was inspected and recorded.
- Do not swap a checkpoint to another architecture inside an existing graph.
- Never repeat an uncertain submission while proving the slice; one deliberate run, then evidence.

## Workflow

1. Name the outcome: preset id, category, modality (`image`/`video`/`3d`), backend (`primary`,
   `hidream`, `h3`) and the controls the user should see. Reuse an existing graph family when one fits.
2. Author the API graph under `workflows/api/<id>-api.json` and, when a human should learn from it, the
   visual graph under `workflows/comfyui/`. Keep authored prompt/seed/size values in the graph: the UI
   reads them back as defaults.
3. Add the catalog entry: `graph`, control bindings as `[node_id, input_name]`, `bindings_extra` for
   fan-out (scheduler dimensions, LoRA clip strength), `reference_slots` with a valid role, `variants`
   only over bound controls, `verified: false`, an honest `commercial_note`, and `backend_id` if isolated.
4. A complete named starting point (prompt, settings and the whole LoRA stack) belongs in
   `presets/recipes.json`, not in a preset's authored defaults: `preset_id` plus controls that are all
   bound on that preset, a kebab-case id, honest `sources` and `status` (`executed` only with a local
   prompt ID). The validator enforces the binding rule exactly as it does for variants.
5. Prove: `python scripts/validate-repo.py`, then `python -m unittest tests.test_server`. If the change
   touched binding logic, add a test next to the existing `FakeStudio` cases.
6. With ComfyUI running, `python scripts/validate-live.py` checks node classes without queueing work.
   Restart the Studio server so the catalog reloads.
7. Hand off to `studio-execution-evidence` for the single proving generation, then flip `verified`
   and record the outcome in `experiments/curated/` and `CURRENT_STATE.md`.

## Read first

`docs/OPERATIONS.md` "Add another preset"; the closest existing preset in `presets/catalog.json`; the
`.claude/rules/catalog.md` region rule (auto-loads on these paths). For anime/fantasy work,
`docs/ANIME-FANTASY-ATELIER.md` lists the installed LoRAs with triggers, strengths and terms, and
`presets/settings-kb.json` holds the sourced per-family sampler/step defaults.
