# Prompt, technique and source-intelligence implementation plan

Execution plan for #432 and #433. It extends the approved #403 architecture and the existing stacked foundation; it does not authorize model acquisition or generation.

## I0 — Static contracts and validation

Deliver:

- exact route-bound prompt dialect candidates;
- tag-vocabulary contract examples;
- technique watchlist with compatibility blockers;
- Hugging Face/Civitai source-intake examples;
- standard-library validator and adversarial tests;
- documentation and agent routing.

Gate: all checked-in records are non-executing, zero-authority and source/revision uncertainty is visible.

## I1 — Read-only discovery commands

Add deterministic commands over checked-in manifests:

- `programme-status`;
- `controls/routes/packs/benchmarks list|get`;
- `dialects/techniques list|get`;
- `sources inspect`;
- `comparison-plan` with authorized candidate cap zero.

Gate: the same IDs and canonical JSON are returned through CLI and library calls; unknown IDs fail; no command contacts a provider or ComfyUI.

## I2 — Source snapshot adapter

Build bounded provider adapters that accept only supported canonical Hugging Face/Civitai identities and emit snapshot proposals. Preserve raw provider payload hashes or retained local snapshots where permitted.

Gate: fake-server tests cover redirects, pagination, changed versions, missing hashes, duplicate files, oversized payloads, malformed UTF-8/JSON, rate limits, private/gated resources and response loss. The adapter still performs no download.

## I3 — Reviewed acquisition handoff

Compile a reviewed snapshot into the existing #356 acquisition plan and #9 inventory expectation. Show storage total, exact destinations, credentials boundary and hashes.

Gate: preparation creates no bytes; a separately authorized fake/local proof demonstrates resume and post-download SHA-256 verification without overwriting existing files.

## I4 — Verified vocabulary index

Ingest one pinned taxonomy export and route-specific trigger records into a local bounded search index. Preserve source category, aliases, implications, deprecations, frequency and Studio semantic facets.

Gate: deterministic query results, no remote autocomplete at generation time, and no accepted entry without immutable provenance and review.

## I5 — Prompt compiler profiles

Implement one profile at a time:

1. Animagine tag baseline;
2. Anima hybrid baseline;
3. Qwen Image Edit instruction baseline.

Gate: exact fixtures cover order, separator, locked fields, unsupported non-prompt controls, token budget and negative semantics. Profiles remain unbound until their target route evidence is exact.

## I6 — Optional analyzers

Qualify one pinned WD tagger and one already-supported vision/caption helper only if manual vocabulary/reference review remains a measured bottleneck.

Gate: cached immutable observations, resource admission, no auto-retry after uncertain execution, and held-out semantic accuracy versus no-helper/manual review.

## I7 — Accepted-output qualification

Use #37/#409 to compare unchanged brief, concise human clarification, compiler projection and optionally reviewed helper projection on fixed routes and references.

Gate: promote or reject each profile based on accepted distinct tasks, hard constraints, attempts and cleanup. Prompt formatting alone cannot pass.

## PR slicing

1. Contracts/docs/validator.
2. Read-only discovery and zero-authority comparison-plan commands.
3. Provider snapshot adapter with fake transports.
4. Source-to-acquisition plan handoff.
5. Vocabulary index.
6. One deterministic profile at a time.
7. Optional analyzers and runtime qualification.

Each PR names its parent branch, tests and exact non-authority boundary. Do not stack unrelated model/runtime changes onto these contracts.
