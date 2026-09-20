# Pose route contract verification — 2026-09-19

Issue: #597

## Scope

This pass reconciles the three corrected-pose route identifiers into one pure canonical table and makes
screening and native binding consume projections of it. It also addresses the bounded findings recorded on
the issue: runnable documentation, renderer encoder identity, backend typo refusal, PNG late-`eXIf`, WebP and
the second `contain-pad` branch.

The canonical Klein contract is:

```text
route id:              klein-geometry
mechanism:             klein-geometry-reference
source representation: precomputed-skeleton
native slot:           geometry-reference
detector behavior:     not-applicable
```

This follows the executable binding behavior: the route consumes an already rendered skeleton and the binding
receipt records zero detector invocations.

## Compatibility decision

The screening manifest and plan move from v1 to v2. Version 1 is rejected with an explicit regeneration
message rather than being silently reinterpreted. This ensures the changed Klein vocabulary receives new
manifest, plan and cell hashes.

Binding requests remain `studio.pose-route-binding-request/v1`. Their route vocabulary already matched the
canonical contract. Local renderer pins now cover the renderer implementation contract, Pillow version and
zlib compile/runtime versions. A stale local pin fails with an encoder-identity diagnosis before byte
recomputation; external renderer identities remain receipt-bound and are not represented as qualified.

## Independent local verification

The connector environment could not materialize the private repository as a complete checkout. I therefore
reconstructed the changed modules and their public dependencies locally, preserving the changed algorithms,
and ran focused deterministic checks without GitHub Actions or Codex review.

Passed:

- canonical projection/backend contract plus renderer/backend/WebP/tall-transform/late-PNG-EXIF/v1-migration
  checks: **9/9**;
- screening v2 compilation: **48 canonical cells**, with Klein cells carrying
  `precomputed-skeleton`;
- synthetic `write-example` command: created request, artifact and PNG with zero execution authority;
- documented `compile` command: created one binding exclusively;
- documented `validate-binding` command: recomputed the same binding ID;
- repeated `write-example`: refused the existing directory and left evidence unchanged;
- Python compilation of the reconstructed changed modules, CLI and focused tests.

The local run used Pillow and zlib available in the execution container. It did not load a model, prepare a
graph, invoke a detector, contact ComfyUI or submit generation.

## Review findings addressed before PR creation

- The first draft allowed only `primary`. That was narrower than the issue required. The final contract accepts
  the repository's configured backend IDs `primary`, `hidream` and `h3`, while refusing values such as
  `primry`. Route qualification remains separate evidence.
- The screening v1 hash is not reused for v2 semantics.
- The documented example is generated and validated before publication instead of referring to nonexistent
  fixture names.
- Local encoder drift is classified through renderer identity rather than surfacing only as an apparent byte
  tamper.

## Limits

No full repository suite, native Windows run, installed auxiliary renderer, exact backend qualification or
image-generation smoke is claimed here. Those are outside this zero-authority contract consolidation and
remain governed by the route qualification/campaign issues.
