# Read-only research discovery and comparison planning

Implementation for issue #435. The research catalog exposes the checked-in adult-illustration programme to humans and development agents without adding provider networking, acquisition, installation, ComfyUI submission or experiment authority.

## Commands

From the repository root:

```console
python scripts/studio_adult_illustration_research.py programme-status
python scripts/studio_adult_illustration_research.py catalogs
python scripts/studio_adult_illustration_research.py list routes
python scripts/studio_adult_illustration_research.py get dialects qwen-edit-2511-instruction-source-profile
```

Prepare a deterministic non-executing comparison:

```console
python scripts/studio_adult_illustration_research.py comparison-plan \
  --case adult-character-plus-pose \
  --case adult-character-outfit-style \
  --route animagine-xl-4-opt-source-review \
  --route qwen-image-edit-2511-source-review \
  --dialect animagine-xl4-ordered-tag-source-profile \
  --dialect qwen-edit-2511-instruction-source-profile \
  --technique dwpose-whole-body-geometry-candidate \
  --out experiments/plans/adult-reference-comparison.json
```

The output parent must already exist and the file is exclusive-create. The plan always declares:

- `authority: none`;
- `authorized_candidate_cap: 0`;
- no generation, execution, download, installation or training authority;
- exact input-manifest SHA-256 values;
- stable requested record IDs;
- an estimated candidate count, not an allowance;
- compatibility, source, terms, runtime and qualification gaps;
- a deterministic plan ID that changes when an input manifest changes.

A plan is therefore a review artifact. It is not an executable workflow, Production campaign, acquisition plan or resource reservation.

## Supported catalogs

| Catalog | Manifest | Records |
| --- | --- | --- |
| `controls` | `control-ontology.json` | model-independent controls and mechanisms |
| `routes` | `route-candidates.json` | exact route research candidates |
| `packs` | `genre-packs.json` | non-executing guided pack candidates |
| `cases` | `benchmark-corpus.json` | synthetic adult-only benchmark declarations |
| `dialects` | `prompt-dialects.json` | route-bound prompt profiles |
| `techniques` | `technique-candidates.json` | adapters, preprocessors, analyzers, trainers and finishing candidates |
| `sources` | `source-intake-example.json` | provider/source contract examples |

`list` returns bounded summaries sorted by stable ID. `get` returns the exact checked-in record plus its source schema and manifest hash.

## Integrity boundary

The module reads only `research/adult-illustration` under the explicit repository root. It rejects:

- unknown catalogs and records;
- duplicate JSON keys or record IDs;
- non-finite values and malformed UTF-8/JSON;
- oversized manifests;
- manifest symlinks or paths escaping the research directory;
- manifests that do not declare `executable: false` and `authority: none`;
- empty, duplicate or excessive comparison selections;
- benchmark cases whose candidate cap is not zero;
- benchmark cases containing real sources in Git;
- unknown controls;
- dialects that do not target a selected route;
- estimated campaigns beyond the bounded planning limit.

The implementation imports no provider, socket, subprocess, ComfyUI or model-runner client. It never resolves “latest,” fetches metadata, probes the workstation or mutates another Studio record.

## Library use

The importable API is `studio_prompt.adult_illustration_research`:

```python
from studio_prompt.adult_illustration_research import (
    catalogs,
    programme_status,
    list_records,
    get_record,
    comparison_plan,
)
```

CLI and library return the same domain objects. Future SDK/MCP projections should wrap these functions rather than implement another catalog parser.

## Handoff to later work

A reviewed comparison plan can later be transformed by a separate issue into:

1. exact source snapshots and file selections under #433;
2. verified Model Library bundles under #9/#144;
3. route and adapter qualification under #405/#406;
4. an explicit finite Production experiment under #10/#409;
5. shared SDK/MCP commands under #413/#123.

Every transformation requires its own expected revision, compatibility checks and authority. No downstream state is implied by a successful read-only plan.
