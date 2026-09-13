# Running preset-compatible builder documents

Implemented slice of #122 and #123. Source reviewed at
`8f471d62a63c339429f95e6a4b55707e99949d8b` on 13 September 2026.
This does not enable arbitrary-graph execution.

## What can run

A Workflow Studio document can become an ordinary registered-recipe ticket when
its complete graph still matches a registered **image** preset except for
catalog-bound prompt, dimension, seed, sampling and LoRA controls. Layout,
names, named Steps and `_meta` annotations do not change execution.

The adapter rejects changed checkpoint selections, added/removed nodes,
rewiring, altered fixed save paths, batch-size changes, selected-output subsets
and disabled nodes. For a registered LoRA, set its catalogued strength to zero;
Studio's existing pruning removes that loader and forwards its model/clip.
Companion inputs must be edited together, not guessed from one changed field.
Unchanged companion defaults can differ and are not unnecessarily rebound.

Registered reference bindings, role-assigned references, mask presets and
`LoadImage` templates are excluded. Continue using Create for those recipes;
workspace asset handles and slot-level lineage need their own adapter. Unknown
or malformed installed node classes are refused. Native frontend/subgraph and
custom-widget fidelity are not inferred from a template match.

## Headless use

Start the ordinary Studio with its existing local configuration. Export a
builder document, retaining its source file. From the repository root:

```bash
python -m studio_workflow prepare-document --document studio-workflow.json --preset pixel-lora --out ticket.json > projection-report.json
python -m studio_workflow run --ticket ticket.json --approve
python -m studio_workflow status JOB_ID
```

Use the actual registered preset ID from `python -m studio_workflow catalog`.
`--out` writes **only the ordinary run ticket**, refusing to overwrite a file.
Stdout contains the full projection report, including source-document hash,
changed bindings, prepared graph hash, ticket hash and the expected job ID.
Omitting `--out` prints the report without writing a ticket file. To recover a
lost run response, retain/reuse the **same ticket**, never prepare a new identity
as an automatic retry. An intent without a job remains reconciliation-required.

SDK:

```python
from studio_workflow.sdk import WorkflowClient
from studio_workflow.core import decode
from pathlib import Path

client = WorkflowClient()
report = client.prepare_document(
    decode(Path("studio-workflow.json").read_bytes()), preset_id="pixel-lora"
)
# Persist report and report["ticket"] before any explicit execution decision.
```

MCP recipe execution already accepts the resulting normal ticket. This slice
does not add a workflow-prepare MCP tool or change the process's permission mode.
Agents may use the CLI/SDK for projection, then the existing approved recipe run.

## HTTP contract

`POST /api/workflow-studio/prepare-document` with exactly:

```json
{"document": {"format": "studio.workflow/v1", "...": "full document"}, "preset_id": "pixel-lora"}
```

The ellipsis is explanatory, not a valid document field. The ordinary 1 MiB
request cap, literal loopback Host and same-origin mutation checks apply.
The response is a `studio.preset-projection/v1` report containing `recipe`,
`changed_bindings`, `document_sha256`, `authored_graph_sha256`, `ticket`,
`ticket_sha256`, `prepared_graph_sha256`, `job_id`, `notice` and
`generation_submitted: false`. Malformed/incompatible requests return HTTP 400;
no ticket is returned on failure. Preparation never posts a generation.

The capability `preset_document_tickets` is true; `arbitrary_graph_execution`
remains false. Old `/prepare`, `/run` and ticket shapes are unchanged.

## Architecture and correctness

1. Copy and structurally validate a single source document.
2. Under Studio's existing lock, read the active installed schema and the
   registered template. Require the document's backend/schema identity to match.
3. Project only a declared scalar-control subset through **actual catalog
   bindings and companions**. Compare every input and connection, not just the
   changed fields or selected output closure. Do not trust `document.source` as
   authorization. New IDs or hidden unused branches cannot smuggle a graph in.
4. Bind through real `Studio.prepare`, including runtime blocks, bounds,
   dimension policies, reference restrictions and the current host-memory gate.
5. Compare the resulting executable inputs with the intended graph after only
   the same zero-strength LoRA normalization. Only `_meta` is excluded from
   semantic comparison; booleans never compare equal to numbers. Numerically
   exact int/float normalization is accepted without converting integers to float.
6. Issue the existing ticket, checking its graph/template hashes against that
   prepared result and checking schema identity again. The existing ticket
   journal and `Studio.create_job` remain the only dispatch path. The worker
   retains its pre-submit resource check and uncertainty handling.

No catalog, workflow file, model inventory, installed package or runtime setting
is modified. Readiness data is read, not a command to install or switch. The
adapter is not a competing compiler, model scheduler or HTTP `/prompt` proxy.

## Evidence limits and remaining work

The source report is a **companion artifact**, not a new durable link from a
shared document revision to a job. Keep it with the original document and ticket.
The ordinary job retains its recipe and prepared/submitted graph. Wiring source
revision references and immutable document snapshots into job lineage remains
part of #122, as do arbitrary graph plans, ownership-scoped cancellation,
progress events and selected-output budgets.

The installed schema is checked during projection, but the inherited ticket
format does not pin node-package/model file bytes or freeze future schema
changes. Runtime validation still occurs at the existing worker boundary. This
is not an execution-quality or model-licence certificate, nor exactly-once
execution under arbitrary external deletion of receipts.

Local evidence: 21 projection/ticket tests passed against byte-identical copies
of the current core and execution modules. Four full-checkout integration tests
are included for the real Studio, actual HTTP origin checks, CLI/SDK, real job
persistence and the live-code host-memory gate; they require hosted CI here.
No GPU, installed-Comfy or local workstation run is claimed.

## Primary-source research

Read 13 September 2026:

- Comfy server routes: https://docs.comfy.org/development/comfyui-server/comms_routes
  documents `/object_info` discovery and `/prompt` validation/queueing. Discovery
  is not approval, and a new raw submit proxy would bypass Studio's own receipts.
- Server overview: https://docs.comfy.org/development/comfyui-server/comms_overview
  confirms queued workflows are whole snapshots, not live links to later editor
  changes. The prepared ticket therefore represents a separate explicit decision.
- Repository `app/server.py`: catalog control binding, LoRA pruning, prepare,
  `_batch_graph`, job persistence and host-commit gates. `studio_workflow/execution.py`
  remains the retained request implementation; it is deliberately not rewritten.

The review also confirmed #134 and #136 are merged and no open PRs were returned
at the checkpoint. The configured page-file change still requires the owner's
Windows restart according to HUMAN_TODO.md; nothing in this slice changes it.
