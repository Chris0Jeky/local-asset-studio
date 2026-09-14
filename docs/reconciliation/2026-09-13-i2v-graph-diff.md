# Preserve connection identity in offline I2V graph comparisons

Maintenance for #242. This is the existing offline actual-versus-canonical
report, not a change to graph validation, workflow documents or execution.

## Reproduction

Two `LoadImage` nodes load different files. Changing a consumer from the first
to the second previously produced an empty diff because normalization retained
only the producer's class and output slot. Nested connections had the same
problem. Unequal node counts reversed added/removed wording and the
actual/canonical IDs. A present null and an absent input were also treated as
equal by `.get()`.

## Correction

Compute the existing ordered node positions once and retain `ref_position`
alongside `ref_class` and `slot` in normalized connections. Consistent node-ID
renumbering with the same order remains equivalent, while two same-class
producers remain distinct. Recursive list/object input values use the same map.
Only a true integer slot is a connection; a boolean is not normalized as one.

An actual-only node is `added` with an actual ID/value; a canonical-only node
is `removed` with a canonical ID/value. Input changes additionally retain
`actual_present` and `canonical_present`, so a missing input differs from a
present null without an ambiguous invented sentinel value.

This still compares node order and class position. It is **not general graph
isomorphism**, order-independent matching, a schema validator, or proof of
semantic equivalence. Literal input objects that resemble normalization records
and other unsupported graph encodings are outside this bounded correction.
No original graph is mutated and no network/native/model operation is added.

## Tests

Seven new methods: same-class rewiring, nested rewiring, both change directions,
null versus missing, stable renumbering/input preservation, output-slot changes,
and boolean non-connections. Five failed against unchanged source; all seven
pass after the correction. The **14-test existing/new I2V group passes** on this
independent branch. CI correctness does not rely on timing benchmarks.

```sh
python -m unittest discover -s tests -p 'test_i2v*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

## Reconciliation and verification environment

Final independent-branch full suite: **1,700 run, 1,684 passed, 16 skipped, zero failures/errors**, 117.198 s. Repository validation passed **66 graphs/bindings, 121 pins and 86 LoRA names**.

Inspected main `3d3135a17811d2e4846ada05aae35e06f60d92f4` / tree
`b34502d889ba5ffc356eb74b2ec15de8a498fd76`. The reconstructed tracked
source matched that tree before editing. Existing open reference-byte,
snapshot-publication, HTTP-framing, library/shortlist and mixed-batch/schema
work was inspected; this slice does not replace those implementations.

Unchanged baseline: **1,693 tests, 16 skipped, no failures/errors**, 114.044 s.
Local environment: Linux, Python 3.13.5, Node 22.16.0, Pillow 12.3.0.
Existing Pillow deprecation and exit-time socket warnings and deliberate
fault-injection diagnostics remain visible. Skipped cases are unverified,
not counted as executed passes. Hosted CI is a separate gate; final-head
results are recorded in the PR rather than presumed from a workflow file.

## Compatibility and rollback

The diagnostic adds producer positions and field-presence flags, while fixing
incorrect existing side labels. Historical reports are not reinterpreted or
rewritten. Consumers must not promote an empty diagnostic diff into execution
permission. Revert for the old report behavior; no database, recipe or stored
command migration is involved. No owner data/configuration, runtime or
HUMAN_TODO/creative decision changed.
