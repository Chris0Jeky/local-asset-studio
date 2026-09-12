# Character production architecture

## Ownership and invariants

This is an offline specialization of `scripts/game_asset_pipeline.py`, not a second executor. Runtime jobs remain owned by `app/server.py`/`app/production.py`; content-addressed source and derivatives belong to Workspace; actual reference upload/binding belongs to `app/references.py`; review belongs to Review Desk; prompt compilation belongs to Prompt Lab. Native Krita/Blender/Godot adapters retain source and engine evidence.

```
source bytes + provenance
  -> draft character canon (identity / costume / representation / style)
  -> explicit selected or human-approved revision
  -> immutable study request -> deterministic cases and total budget
  -> canon/reference preflight -> existing brief + native preset handoff
  -> [future #65] shared coordinator: reserve / submit / reconcile / inspect
  -> chronological attempt evidence + separate review decisions
  -> accepted panel revisions -> deterministic composition / protected repair
  -> editable source + authored motion -> actual engine acceptance
```

Every stage declares what it changes. Identity edits invalidate dependent portraits/views; costume edits invalidate costume-bearing outputs; layout edits reuse accepted pixels. A final layout change must never cause diffusion. Preserve rejected candidates and parentage rather than overwriting the only evidence of a failed route.

## Implemented contracts

`character_canon` v1 separates four immutable design facets, ordered typed references with hashes, named hard checks and an approval attestation. Drafts contain no reviewer identity. Agent selection is not owner approval. Approval hashes bind the entire design/reference/check specification, so editing it invalidates approval. These hashes are integrity records, not digital signatures or reviewer authentication.

`character_study_request` v1 declares existing preset IDs, tasks, reference IDs, required checks, seeds, hypotheses and one global budget. The product of routes/tasks/seeds must fit that budget. Repairs are additionally capped per case, never given a fresh global allowance. Seeds are limited to JavaScript-safe integers for future UI interoperability.

`character_study_plan` embeds exact canon/request and deterministic expanded cases. Validation rebuilds the plan and compares it, rather than accepting a modified derived case merely because somebody recomputed the outer hash. All plans initially say `not_run` and `submits_generation: false`.

`brief` projects one case into the existing game-assets v1 reference-image contract. Its copied budget identifies the original study and **must not** be treated as a new independent allowance. The future coordinator must bind every case to that study owner; the offline CLI cannot enforce actions performed elsewhere.

`handoff` reads the real current catalog, validates native positive/seed and reference bindings, records the raw graph-file SHA-256, catalog-entry hash, ordered upload requirements and reference policy. It changes no template, sampler, encoder, VAE or adapter. It returns no armed submission payload. Live bundle/node checks, batch size, uploads, actual preprocessing and shared budget reservation remain unresolved.

Attempt records are chronological snapshots: ID, study/case, primary/repair/warmup, parent, execution state, actual prompt ID, hashed output/evidence, measured times and a separate review. Failed, cancelled, warmup and uncertain work count. Uncertainty blocks further work on that case until a separately retained reconciled assessment replaces the unknown state. Never regenerate merely to avoid resolving a lost response.

A selected/accepted output must pass every required check; fail/not_visible/uncertain cannot be averaged away. Review must name the exact output hash. Agent selections and human acceptances are separately counted. To change a selection, create a new assessment snapshot retaining the prior one; this offline file format is not an append-only authenticated review service.

## Source and media discipline

The 71-member archive lock pins original delivery and each extracted member. Intake rejects mutation, unexpected names, traversal, Windows-unsafe names, case collisions, special/symlink entries, unsupported compression and size overflows. Extraction is staged in a new directory; archived Python/HTML is copied as data, never executed. One trusted writer is assumed, matching this repository. This is not a hostile multi-user filesystem sandbox or a signed supply-chain verifier.

Media intake reads actual alpha, not just mode. Rectangular extraction preserves decoded source crop pixels without resampling. The demonstration compositor supports the exact 4-view/2-portrait/7-action layout; it is an opaque review card, not the future 4-view/4-portrait production template or an animation atlas. Its font is Pillow's bundled default; no host font file is shipped. Byte-repeatability is scoped to the recorded Pillow/runtime, not promised across upgrades.

Protected repair uses an explicit grayscale PNG mask: 0 preserves original decoded RGBA, 255 takes the candidate, intermediate values blend. It rejects empty masks, masks with no exactly protected pixels, dimension mismatches and differing embedded ICC profiles. It preserves source ICC bytes but does not claim full colour management, linear-light blending, original PNG metadata or successful interior repair. Native Comfy alpha inversion requires an explicit adapter, not guesswork; #62 already owns that runtime guard.

## Trusted execution still to implement (#65)

Use transactional reservation in the existing Production database before every expensive attempt. The state transition must persist intent before network submission, immediately save a known prompt ID, retain uncertain outcomes after response loss and reconcile without duplicates. Per-case counters alone are insufficient: all branches and repairs share the study budget. Initially require batch size one.

UI, CLI and agent commands use existing revisioned services, not separate databases. Stale revisions invalidate proposals. Default operations inspect/plan/propose; model execution remains explicit. Preserve queued manual work and installed environments. Local helper residency must be coordinated with the image worker; a workspace-only lock is not a global GPU reservation.

Cache full effective inputs: canon revision, reference bytes/crops/order, prompt/profile, raw graph, model/encoder/VAE/adapters, quantization, sampler settings, output settings and relevant runtime versions. Analysis caches and generation caches are separate. A source change creates a branch; no silent reuse based solely on matching prose.

## Failure policy

Return the best accepted intermediate plus defect/cost evidence when budget is exhausted. An uncertain critical detail asks for review; a missing model produces a precise preflight blocker; a broken atlas runs a deterministic repair. Do not install models automatically, spend on hosted services, replace Comfy packages, clear unrelated queues or manufacture art/rights/engine approval to make a milestone green.

Testing layers: pure contracts and synthetic negative cases; exact preset/brief compatibility in CI; real normal-Studio transport with injected faults; bounded workstation inference; owner review; actual native and engine playback. Passing one layer does not imply the later layers passed.
