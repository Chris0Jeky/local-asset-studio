# Workflow modules, guarded inverses and execution identity

This is the deterministic engine slice of #120, stacked after #642 / #314. It extends the shipped document reducer, store and HTTP handler. There is no second graph store, worker, SQL schema, model invocation or native-subgraph converter.

## Three identities, not interchangeable receipts

| Field | What it binds | Presentation changes |
| --- | --- | --- |
| `document_sha256` | Entire persisted authoring revision | Change it |
| `graph_sha256` | Existing exact compiled graph, including node `_meta` | Node metadata can change it; old semantics retained |
| `graph_execution_sha256` | `studio.workflow-execution/v1`, backend, schema, and selected compiled node classes/inputs | Do not change it |

The existing `execution_inputs_sha256` remains a conservative authored-input identity, including disconnected drafts. It is not the selected compiled identity. The new execution identity is absent (`null`) for an invalid compilation. No hash certifies installed model compatibility, asset availability, a native custom node, licensing or permission to run.

The legacy graph hash is deliberately not redefined: existing tickets and receipts may depend on those exact bytes. Layout/name/Step changes retain executable identity; changing an input in the selected output closure changes it. Disconnected edits remain in the document without becoming execution dependencies.

## Portable modules

`studio_workflow.modules.export_module(document, step_id, document_id=None)` projects exactly one named Step into a `studio.workflow-module/v1` envelope. It retains node metadata, disabled states, explicit bypasses, positions, exposed controls and source declarations. It records the full source document digest, source revision and optional saved ID. The module has revision zero and is capped at 256 KiB, inside the existing JSON depth and type limits.

Every link crossing into the Step is exposed in a deterministically ordered `inputs` array. Imports require an exact explicit target binding for every exposed input and a new ID for every inserted node. The module's backend/schema must match the target. No outside consumer is rewired and copied output nodes are not selected automatically.

```python
from studio_workflow.core import digest
from studio_workflow.modules import export_module
from studio_workflow.commands import apply_commands

module = export_module(saved_document, 'pipeline', document_id=saved_id)
command = {
    'op': 'import_module',
    'module': module,
    'module_sha256': digest(module),
    'node_ids': {'pass': 'copy_pass', 'save': 'copy_save'},
    'step_id': 'copy',
    'name': 'Copied pipeline',
    'bindings': {'input1': ['existing_input_node', 0]},
}
next_document = apply_commands(target_document, [command])
```

The example IDs must match the exported module. Ports are named `input1`, `input2`, etc., sorted by inner node and input name. Inspect the envelope rather than guessing a port. Binding to an absent/newly imported node, omitting a binding, adding an undeclared binding, colliding IDs or changing the reviewed module digest refuses the entire command.

Import provenance is appended under `source.module_imports`, including the module hash, source origin, node mapping, actual external bindings and retained source/asset declarations. Existing target lineage is not replaced. Opaque non-object `source` declarations or a conflicting `module_imports` field are refused explicitly, not coerced. The retained list has a 64-import bound; removing a Step does not erase its historical provenance. Full document/depth limits still apply. Source provenance is caller-supplied evidence, not authentication; a hash is not proof of the author or access rights. Imports copy declarations, not media bytes.

These are flat reusable Step projections. Native ComfyUI visual subgraphs and arbitrary execution remain separate workstreams. Type/runtime validation still belongs to the existing compiler/backend. An unselected cyclic or disconnected draft remains inert; selecting it surfaces diagnostics.

## Guarded undo and redo

`studio_workflow.command_plan.plan_commands(document, commands)` returns the proposed document, normalized commands, before/after hashes, and two-command inverse/redo batches. Each consists of `assert_state` followed by the existing `replace` command.

The state guard hashes all authoring data except the server-assigned revision. Undo therefore survives append-only revision increments, but refuses unrelated edits to layout, metadata or lineage. The existing `expected_revision` CAS is still required for saved commands. A fresh revision number alone cannot make an old inverse overwrite unrelated state.

Whole-document inverse snapshots are intentional. They preserve disconnected nodes, dangling consumer links, disabled data, bypasses, positions, Step controls and opaque source declarations without a separate inverse implementation for every edit. Plans reserve room for the largest valid command-request envelope; an inverse that cannot fit advises saved revision restore. This opt-in bound does not narrow existing command or preview behavior.

Undo and redo append new revisions. They never roll back history, erase receipts or grant execution authority. Pure plans are not durable commands until explicitly submitted with a request ID and expected revision.

## HTTP surfaces

All paths share the existing `/api/workflow-studio/documents` prefix and handler security rules:

| Method / suffix | Body / behavior |
| --- | --- |
| POST `/modules/export` | `{document, step_id}`; pure export, no database initialization |
| POST `/modules/inspect` | `{module}`; strict validation and canonical module digest |
| POST `/plan` | `{document, commands}`; pure guarded plan |
| POST `/{id}/plan` | `{expected_revision, commands}`; read-only plan against a saved head |
| GET `/{id}/revisions/{revision}/modules/{step_id}` | Export an exact saved revision with source identity |
| POST `/reduce` | Existing pure reducer now also accepts `import_module` / `assert_state` |
| POST `/{id}/commands` | Existing atomic transaction and durable request replay |

Saved plan `document_sha256` equals the subsequent commit's hash when that expected head remains current. State-guard mismatches return 409 / `document_state_conflict` with expected/current state digests. Malformed assertions remain 400; revision/request conflicts retain their old typed contracts. Host/origin checks, strict JSON parsing, bounded bodies, no query parameters and storage-error recovery are unchanged.

## Verification and remaining acceptance

See `120-VERIFICATION.md` for exact local checks and file bindings. This engine/HTTP slice does not claim completion of the broad #120 browser work: a module picker, Guided/Step/Node UI parity, keyboard-only and 390px integrated browser acceptance, scalable canvas/catalog measurements, and workstation handoffs still require their own qualification. No frontend performance claim is inferred from Python timings. `HUMAN_TODO.md` is unchanged.
