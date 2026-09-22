# Reproducible route inspection

Implementation slice under #552, #34/#144 and #302. Research freeze: **2026-09-15**;
repository reconciliation: **2026-09-21**, `f16ed8ea2fbb23e9bf64b726745790de5909577f`.

## Design and authority

The missing artifact is a **derived, read-only route report**, not another model
registry or a readiness gate. Join the existing catalog, API graph, library pins
and Prompt Lab profiles. Reuse `guidance.resource_context`, `guidance.bindings`,
and `studio_prompt.graph_provenance.inspect_graph`. Do not instantiate Studio,
ModelLibrary, a coordinator, Workspace, an HTTP client, or an installed runtime.

A recipe name is not a configuration identity. Hash the complete preset, graph,
selected library declarations and applicable compiler profiles. Report raw input
file hashes separately from canonical JSON identities. A default-Q4 graph with an
active accelerator must stay distinct from the same graph without it, from native
BF16, from another encoder, and from a changed reference order. Do not infer tensor
precision, prediction type, upstream revision or hardware memory from filenames.

The report preserves author declarations as declarations. Catalog `verified`, a
source URL, matching pins, an exact compiler template, static reference slots and
a graph inspection are **not** fresh installation, GPU execution, role fidelity,
licence clearance or owner acceptance. Unknown measurements remain null, including
`restart_required`; zero would falsely claim a measurement. No aggregate score.

## Implementation plan

1. Add `tests/test_route_qualification.py`: real catalog tests for Anima, Animagine,
   Pony, Noob and Qwen; drift in graph/pins/profiles/role order; ambiguous and missing
   pins; malformed structures; independent returned snapshots. Observe failure
   before implementing the new module.
2. Add `studio_workflow/qualification.py` with `inspect_route(preset, graph,
   manifest, profiles)` and `inspect_repository(root, preset_ids)`. Export declared
   model components, sampler/loader settings, prompt-profile template match,
   ordered reference declarations, unknown runtime/node revisions and independent
   evidence/result dimensions. Bounded inputs and output; no dispatch method.
3. Add the offline module CLI. Constrain reads to exact catalog-owned API graph
   paths and fixed catalog/library/profile files; reject absolute/traversal/link
   paths and duplicate/unknown recipe IDs. JSON goes to stdout only, with no
   implicit output directories or overwritten records.
4. Run focused and existing guidance/profile/graph tests, repository validation,
   and the strict full-suite lifetime gate. Retain failures and distinguish
   baseline/tooling limitations from regressions. Publish reviewed source via PR.

## Usage

```sh
python -m studio_workflow.qualification --root . \
  --preset anima-portrait --preset anima-v1-baseline --preset anime \
  --preset pony --preset noob --preset qwen-1ref --preset qwen-2ref --preset qwen-3ref
```

The CLI returns zero when inspection succeeds, **not** when qualification passes.
Use shell redirection only to an explicitly chosen local evidence destination.
It does not fetch URLs, open the user's model directory, measure VRAM, or submit a
warmup. Run it before preparing a finite Experiment Lab campaign; actual Start
continues through the existing admission/coordinator. Retain the report beside the
campaign's existing artifacts, not in another database.

## Consumer contract and follow-through

- Prompt Lab: `prompt_profiles` reports legacy association versus an exact
  template/binding match. Even an exact match is not upstream-source verification.
- Workflow Studio: graph resources/settings and catalog reference roles are
  inspectable. `native_slot_maximum` remains unknown; an authored three-image
  graph cannot establish an architecture limit or successful outfit/style transfer.
- Reference Intelligence: crop policy and take/ignore declarations remain
  separate from observed transformations, input hashes and human-reviewed intent.
- Experiment Lab: bind retained run IDs, failed attempts, resource receipts and
  independent reviews to this configuration. Never promote from this report alone.
- Trusted operator: attest actual loaded files, node commits and runtime identity;
  authorize installation or execution separately. #302/#303 own measurement.

Changes to settings, source metadata, components, roles, graph or profile invalidate
this report's configuration digest. An unrelated library addition changes the
input-file digest but does not change an unaffected route's configuration digest.
This is content identity, not a signature, lease, atomic filesystem snapshot or CAS.
