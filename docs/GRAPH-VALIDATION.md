# Graph validation: one rule set, explicit evidence

13 September 2026. Source checkpoint: `e1ed046d04491dae42fdf5988c1117472abb6d4a`.
This slice advances #97 under #9/#10 and coordinates with #119; it does not replace
Workflow Studio, the catalog, Production admission or the generation worker.

## Reconciliation

The older descriptions of #2/#3 still include live/creative acceptance work. Model
intake #149 is now merged, and Production materialization #153 was open at inspection.
Neither is duplicated. Current source still contained all three #97 rejection paths:
exact socket equality, expansion of unset dynamic combos, and treating COLOR widgets
as opaque link-only inputs. The CLI also still implemented a second rule set and
silently selected only `workflow-lab` by default.

`Studio.validate_graph()` already delegates to `game_asset_pipeline.graph_check`.
`validate-live.py` now delegates to that same function. `build-expansion.py` continues
to use the shared `expanded_input_contract` for its visual-node input projection.
No native graph, model file, sampler setting, selected backend or executor is changed.

## Supported compatibility rules

- String sockets use trimmed comma-union overlap, with `*` on either side. Empty tokens
  and non-string socket representations refuse rather than acting as wildcards.
- V3 dynamic combos expand only when their selector is present. Only the selected
  branch contributes dotted inputs. This follows native v0.35.0 expansion, including
  unset nested required selectors and SaveVideo's optional hidden legacy flat codec.
  No default is inserted. A supplied unknown choice or inactive dotted field refuses.
  Ordinary required inputs, including scalars in an active branch, remain required.
- A custom scalar widget needs **both** `socketless: true` and a scalar `default` in
  its schema. The value must match that scalar shape; a default on a MODEL socket
  does not authorize a literal. Links to socketless widgets refuse. COLOR strings
  are shape-checked, not interpreted as a promise that every string is a valid color.
- Existing primitive types, finite numbers, enums, numeric bounds, exact large integer
  seeds, graph links, source indexes and acyclicity remain checked. Errors identify
  the node and field. Dynamic expansion is capped at eight nested levels, 1,024
  choices per selector and 4,096 expanded inputs. Graphs remain capped at 512 nodes.

An absent root dynamic selector is omitted by native schema expansion even when
marked required; that does **not** prove a node's Python execute signature accepts
its absence. Native validation/execution is a separate boundary. We do not execute
`VALIDATE_INPUTS`, custom Python string operators, frontend extensions, remote option
providers or arbitrary widget code. MatchType, autogrow and legacy enum-list output
extensions are not certified by this subset. This is not full ComfyUI parity.

## Operator commands

```sh
# Every catalog entry, against one explicitly observed endpoint schema:
python scripts/validate-live.py

# Explicit selection; this never starts or switches the backend:
python scripts/validate-live.py --backend primary --comfy-url http://127.0.0.1:8188
python scripts/validate-live.py --backend hidream --comfy-url http://127.0.0.1:8192
python scripts/validate-live.py --collection workflow-lab
python scripts/validate-live.py --preset wan22-i2v --preset trellis-rgba

# Existing saved raw object_info JSON; zero network calls:
python scripts/validate-live.py --object-info /path/to/object-info.json --json

# One graph through the same offline checker:
python scripts/game_asset_pipeline.py graph-check workflows/api/wan22-i2v-api.json --object-info /path/to/object-info.json
```

Omitted filters mean **all** collections, including uncollected and isolated-backend
presets. A single schema describes one installation: missing classes/files from
another backend are explicit failures, not evidence that its own installation is
broken. Use a recorded schema/endpoint and an explicit backend filter for that lane.
`--backend` filters catalog metadata, not processes; it does not verify endpoint identity.

Unknown IDs, duplicate catalog IDs and empty filter matches fail before discovery.
`--repo-root` selects the catalog root; graph paths must remain inside it. Every
selected preset gets a result, including missing files and invalid graphs. Each failed
graph reports its first failure, not an exhaustive native diagnosis of every node.

The default source is still `http://127.0.0.1:8188`. An explicit URL must satisfy the
existing managed IPv4-loopback contract. Discovery makes one GET to `/object_info`,
with proxies disabled, no redirects, a 30-second transport timeout and a 32 MiB body
bound. There is no retry or `/prompt`, queue, history, install or switch request.
This timeout is not a guaranteed total wall-clock deadline for a trickling response.
Saved-schema reading also has the 32 MiB bound and rejects duplicate JSON keys and
non-finite constants. The graph-check subcommand retains its older 4 MiB JSON limit;
use the catalog CLI for larger raw snapshots. No module-import network I/O occurs.

Reports include source path/URL, raw-schema SHA-256, selected/total/passed/failed
counts, declared backend per row and `inference_verified: false`. Schema identity
is not provenance authentication. Exit status is 0 when all selected graphs pass,
1 for per-graph failures, and 2 for setup/input/discovery failure. `--json` provides
machine-readable results; setup failures use JSON on stderr.

## Tests and remaining acceptance

The new focused suite has 40 tests: 36 pass in the partial local source workspace;
four require the complete catalog/Studio checkout and run in hosted CI. The original
pipeline file is byte-identical to Git blob `1ca4746f3a90bf5d30d39f1ed507091a317c97e8`.
Replaying the 21 schema test methods against that baseline yields failures in 16
methods (including message/validation-hardening cases); five controls pass.
The CLI suite includes actual inert loopback servers and a subprocess offline run.
No Comfy process or model is involved.

The fixture under `tests/fixtures/graph-validation` is **source-derived and reduced**,
not a captured installed `/object_info`. SaveGLB's long union is reduced to the two
relevant types. The catalog tests prove every row is visited, exercise structural
checks, and check actual SaveVideo/Crop/SaveGLB node inputs with inert typed upstream
sources. They do not prove every model/custom node in every graph matches the PC.
One test invokes the actual Studio validator with a supplied read-only schema seam.

```sh
python -m unittest discover -s tests -p test_graph_validation.py -v
python -m unittest discover -s tests -p test_validate_live.py -v
python -m unittest discover -s tests -p test_graph_catalog_validation.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

A Python 3.12 Linux/Windows lane runs the three new suites plus the existing game-asset
pipeline suite. The ordinary full-suite and repository validator remain required.
Actual CI results belong to the PR check records, not an inferred local full clone.

Remaining #97 evidence: capture the owner's actual installed schema with exact
backend/Comfy/custom-node revisions, review it for publication, and run the full
catalog against each appropriate snapshot. Do not claim that corpus was captured
here or that a static pass certifies model presence, memory fit, license/territory,
inference, protected pixels or creative acceptance. No user's runtimes, outputs,
configurations, downloads or human decisions changed. The existing owner-controlled
restart remains separate, after downloads finish and work is saved.

## Primary technical sources

Read 13 September 2026, pinned to ComfyUI v0.35.0 where applicable:

- [Socket validation](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_execution/validation.py):
  `validate_node_input(..., strict=False)` uses union overlap and wildcard handling.
- [V3 input implementation](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_api/latest/_io.py):
  `DynamicCombo._expand_schema_for_dynamic` includes only supplied selectors;
  `WidgetInput` serializes widget/default/socketless metadata.
- [SaveVideo](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_video.py):
  nested format/codec/optional encoding and the hidden legacy codec input.
- [SaveGLB](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_save_3d.py):
  Mesh plus File3D MultiType input, not one exact socket name.
- [ImageCropToMask](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_images.py):
  COLOR background widget and explicit scalar bounds.
