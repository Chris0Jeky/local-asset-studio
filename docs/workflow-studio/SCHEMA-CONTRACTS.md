# Installed-node authoring contracts

Focused #119 slice. The Studio authoring compiler is not the Comfy runtime
validator, and this does not resolve #97's independently owned runtime checks.

## Reproduced gaps

Against core.py blob `0955cbd3ea1d414e88864442cb8b5fcb64221f60`:

- An unrecognized input descriptor produced an `unsupported` record without the
  `hidden` key. The compiler indexes that key while selecting visible inputs, so
  it raised KeyError instead of returning its native-adapter diagnostic.
- A non-mapping required/optional group raised from `.items()` during discovery,
  preventing unrelated valid nodes from being listed too.
- Nonnumeric bounds/steps or inverted bounds were exposed as editable numeric
  controls. Range comparison could then raise or the UI could render an invalid dial.

These are synthetic schema/fault reproductions, not observed crashes of the
owner's installed nodes. No custom node was installed, modified or executed.

## Changes

All normalized input records now contain `hidden`, including unsupported ones.
Unsupported values remain in the workflow document. Compilation returns
`native_adapter_required` rather than throwing for the unknown descriptor.

Malformed required/optional **group containers** are recorded on the affected
node as `schema_errors`; unrelated catalog entries remain accessible. Compiling a
selected output closure containing the affected node returns `invalid_node_schema`.
There is no synthetic input name or inferred default inserted into the graph.

Numeric input controls require finite numeric min/max/step metadata, ordered
bounds, and positive step when present. Invalid metadata is native-adapter-only;
it is neither silently coerced nor presented as a runnable numeric setting.
This is a presentation/authoring rule, not a claim that all native plugin validation
has been duplicated. Server-injected hidden inputs remain separate from user fields.

The existing node-catalog unsupported badge and compiler diagnostics consume the
new failure classification. No new browser renderer, node evaluator, dependency
installer or request route was added. Raw schema fingerprints still cover the
actual discovered definitions, not the presentation-normalized projection.

## Fixture coverage

`tests/test_workflow_schema_contracts.py` covers eight tests with parameterized
cases: unknown descriptors, malformed group containers, invalid numeric metadata,
legacy and V3 combos, NodeDef-v2 dictionary inputs/outputs, strict typed choices,
forceInput, hidden metadata, list-output annotations, int64/uint64 preservation,
unset unsupported optional inputs, dynamic/custom/rawLink/remote adapter boundaries.

The first seven tests produced five assertion failures and six subtest errors
against the baseline; after the patch those seven passed. The additional top-level
NodeDef-v2 fixture also passes. The unaffected legacy/V3/opaque-value tests are
compatibility guards, not claims that each case was broken before.

Run:

```bash
python -m unittest discover -s tests -p test_workflow_schema_contracts.py -v
python -m unittest discover -s tests -p test_workflow_studio.py -v
python scripts/validate-repo.py
```

The source environment ran the eight isolated contracts. Full-checkout CI must
establish the existing tests and validator result. No installed Comfy schema
snapshot, custom-widget browser parity, real inference or art acceptance is claimed.
#119 remains open for real installed fixtures, dynamic widgets, image/mask controls,
wide-integer browser editing, adapter negotiation and native semantic compatibility.

## Primary references

Reviewed 13 September 2026:
- Built-in datatypes and control metadata:
  https://docs.comfy.org/custom-nodes/backend/datatypes
- Server-injected hidden inputs, custom types and flexible inputs:
  https://docs.comfy.org/custom-nodes/backend/more_on_inputs

The fixture values are authored test data informed by these interfaces and the
existing normalizer, not copied workstation metadata or execution evidence. A
schema match does not certify model availability, resources, licensing or image
quality. HUMAN_TODO and all actual runtime/model files remain unchanged.
