# Output-port authoring contracts — 13 September 2026

Continuation of #119, based on main `aebe10c58c7fa3ce8f89276740096eaf98c2cc20`.
The merged #156 runtime graph checker remains authoritative for runtime preflight;
this change fixes the separate authoring catalog's malformed-output boundary.

## Reproduced defects

A legacy `output: "IMAGE"` became five character-named ports. An integer output
container or malformed `output_name`/`output_is_list` could raise while discovering
all nodes. NodeDef-v2 records accepted boolean/fractional or duplicate slot indices,
non-text types and truthy non-boolean list flags. `output_node: "false"` was treated
as an output sink. These defects could hide valid nodes or offer nonexistent links.

`node_outputs.outputs` now produces presentation ports plus node-local
`schema_errors`. Invalid containers do not fall back to another format. Invalid
slots do not shift the indices of later slots. Explicit v2 indices are retained,
unique, integer and within this adapter's 0–9999 range. Types and names are text;
list/sink flags are actual booleans. Short or absent legacy name/list arrays keep
the established defaults. Outputless sinks, union strings and list annotations
remain supported.

The original schema is never mutated and its raw fingerprint remains unchanged.
Unsupported workflow input data is preserved. The existing compiler rejects a
selected dependency closure containing a malformed class, but can still export an
unrelated valid closure. Nothing installs code, contacts a model or submits a job.

## Tests and limits

`python -m unittest discover -s tests -p test_workflow_output_schema.py -v`
runs ten synthetic contract tests with parameterized malformed variants. Against
the original `core.py` they produce 23 assertion failures and three errors; all ten
pass with normalization. This is synthetic interface evidence, not an installed
custom-node capture or proof of native execution. The full repository suite and
`python scripts/validate-repo.py` remain required; see PR checks for their exact
commit and environment results.

This is not a full JSON-schema validator. Dynamic outputs, native JavaScript,
custom validators and list execution semantics still need their declared adapters.
No node's absence from these diagnostics establishes that its models fit memory or
that a generated asset is accepted. #119 remains open for its wider deliverables.

## Primary-source reference

ComfyUI's [Node Definition JSON](https://docs.comfy.org/specs/nodedef_json), inspected
13 September 2026, describes outputs as an array of records with type, index, name
and list metadata. This adapter retains its existing omitted-name/index defaults
and explicitly bounds supported indices; it does not claim full schema parity.
