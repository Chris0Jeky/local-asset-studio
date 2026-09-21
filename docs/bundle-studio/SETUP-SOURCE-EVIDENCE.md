# Retained source evidence to setup compatibility

21 September 2026 · offline bridge for #753 and #754.

## Purpose

`studio_workflow/source_compatibility.py` converts one retained
`studio.source-composition-evidence/v1` report plus one reviewed exact-resource
mapping into a provider-neutral setup candidate and evidence records accepted by
`studio_workflow/setup_compatibility.py`.

The bridge exists to keep three kinds of information separate:

1. **retained provider facts** — exact source receipts, model/version/file IDs,
   file metadata and bounded gallery observations;
2. **reviewed compatibility facts** — role, modality, architecture, lineage,
   loader, runtime, format and required capabilities;
3. **setup decisions** — Recommended, Possible, Needs review or Incompatible for
   one exact target slot.

Provider labels never become hard compatibility facts merely because they were
returned by an API. A reviewed mapping owns those facts and is pinned to one
retained report context, one exact provider resource and one exact file.

```text
retained Civitai/Civitai.red snapshots
                 |
                 v
 studio.source-composition-evidence/v1   reviewed exact mapping
                 |                               |
                 +---------------+---------------+
                                 v
             studio_workflow.source_compatibility
                                 |
             studio.setup-source-candidate/v1
                      | candidate + evidence
                      v
             studio_workflow.setup_compatibility
                                 |
             read-only compatibility report
```

No step in this bridge contacts a provider, hashes a file, downloads a model,
changes a setup, installs a dependency, switches a backend or submits generation.

## Required pins

The request uses `studio.setup-source-adapter/v1` and contains exactly:

- `report` — a normalized retained source report;
- `mapping` — the reviewed interpretation of one exact resource/file;
- `format` — the adapter schema version.

The mapping must pin:

- the expected retained report `context_sha256`;
- the exact provider resource identity, for example a canonical AIR or
  `civitai-version:<id>`;
- the exact selected file identity, preferably `sha256:<64 lowercase hex>`;
- a content-addressed review revision;
- the review date;
- the candidate role, modality, architecture, lineage, loader inputs, format,
  runtime and required capabilities.

The report context, resource identity and file identity must all match before a
candidate is emitted. A file must occur exactly once in the retained resource.
When its identity is SHA-256, any retained provider SHA-256 claim must agree.

The retained model-version receipt identity is also required to be a lowercase
SHA-256. Its host remains either `civitai.com` or `civitai.red`; the bridge does
not silently rewrite or merge those source identities.

## Authority and trust hierarchy

Hard setup facts come from the reviewed mapping. The retained provider report is
untrusted evidence and remains separately inspectable.

| Input | What it may establish | What it may not establish |
| --- | --- | --- |
| Reviewed mapping | candidate role, architecture, lineage, loaders, runtime, file format and companions | installation, current inventory presence, generation quality or legal clearance |
| Exact provider metadata | source identity and an inspectable compatibility claim | artistic quality, local runtime success or architecture truth without review |
| Gallery co-use | that exact version IDs were reported together in retained records | compatibility proof, quality proof, successful reproduction or licence clearance |
| Reactions/comments | popularity metadata retained for inspection | evidence count, independence, rank or recommendation |

Provider `baseModel`, model type and file format are compared with the reviewed
mapping. A differing base/model-type label becomes a diagnostic rather than an
automatic rewrite. A known provider file-format contradiction refuses the
mapping; a missing provider format remains an explicit diagnostic.

The original normalizer diagnostics are returned as `source_diagnostics`.
Bridge-specific mapping and interpretation findings are returned separately as
`diagnostics`. This prevents source limitations from disappearing inside a later
adapter step.

## Evidence emitted

### Exact provider metadata

One deterministic candidate-scoped `provider_metadata` record is emitted for the
selected file. It is:

- exact-resource scoped;
- compatibility-only;
- tied to the retained model-version response SHA-256;
- non-prescriptive for quality, speed, memory or style strength.

Its stable evidence ID includes the candidate, resource and file identities so
two candidates cannot collide merely because they share a generic label such as
`source-provider`.

### Gallery composition

Each retained combination that includes the reviewed model version may emit one
`gallery_co_use` record. It remains:

- family scoped rather than exact-file scoped;
- compatibility-only;
- based on distinct observations and distinct uploader breadth;
- unable to override a hard role, architecture, lineage, loader, format, runtime
  or companion mismatch.

Distinct uploader breadth must be non-negative and cannot exceed distinct
observations. Zero-uploader observations remain visible in
`source_observations`, but they do not become recommendation evidence.

Evidence IDs include candidate identity, source-scope identity and the exact
version combination. Different combinations in one gallery scope therefore stay
separate, while an exact duplicate combination is refused instead of being
silently counted twice.

`civitai.com` and `civitai.red`, browsing/filter context and exact version sets
remain distinct. Engagement totals stay only inside the retained observation and
never affect evidence breadth or ordering.

## Output contract

A successful `studio.setup-source-candidate/v1` result contains:

- `candidate` — the provider-neutral candidate accepted by the setup evaluator;
- `evidence` — one exact provider claim plus any qualified family-scoped gallery
  observations;
- `source_observations` — retained combination records for inspection;
- `source_diagnostics` — limitations produced by source normalization;
- `diagnostics` — mapping/provider-claim differences produced by this bridge;
- `provider_claims` — selected source labels and permission fields retained as
  claims rather than decisions;
- the source context SHA-256 and pinned review revision;
- a deterministic output `context_sha256`;
- explicit false authority flags for provider access, hashing, download,
  installation, selection mutation and generation.

The output fingerprint identifies the exact bridge inputs and interpretation. It
is not a lock, a terms acceptance, proof of installed bytes or permission to
apply the candidate.

## CLI

Run the adapter against retained local JSON:

```sh
python -m studio_workflow.source_compatibility retained-mapping.json
```

Exit 0 prints the deterministic bridge result. Invalid input exits 2 with a
bounded `invalid_source_mapping` error. The CLI has no network or mutation flag
because provider access and setup application are outside this component.

## Current integration boundary

The bridge is read-only. It does not yet:

- build mappings automatically from `models/library.json` or filenames;
- inspect the currently installed ComfyUI node schema or active backend;
- capture live provider data;
- render compatibility states in Bundle/Create selectors;
- prepare a substitution diff;
- recheck a document revision and apply a setup change.

Live metadata capture must reuse the reviewed bounded source transport under
#433 rather than adding another crawler, credential path, redirect policy or
cache. The transport/acquisition stack in #579/#580 is substantially older than
current `main`; reconcile its owners deliberately before consuming it here.

The safe continuation is:

1. merge the provider-neutral evaluator (#755) and retained source normalizer
   (#765);
2. land this bridge (#766) after rebasing/retargeting onto the merged evaluator;
3. add reviewed mapping records for representative exact Civitai and
   Civitai.red fixtures;
4. project current setup slots, inventory and installed schema observations into
   one evaluator request;
5. render Recommended, Possible and Needs review while omitting or disabling
   Incompatible in the normal selector;
6. prepare one complete reviewable setup diff;
7. at Apply, recheck document revision, inventory and backend/schema, then use
   the existing revisioned document/service path atomically.

Opening, browsing or evaluating recommendations must remain side-effect free.
No missing identity or capability may be silently treated as compatible.

## Regression coverage

The contract suite covers:

- exact context/resource/file selection and stale-source refusal;
- reviewed architecture and lineage winning over provider prose;
- Qwen Image Edit 2511 versus Qwen Image 2.1 separation;
- FLUX.1 versus FLUX.2 Klein separation despite gallery popularity;
- `.com`/`.red` scope separation;
- engagement independence;
- zero-uploader observations remaining non-evidence;
- deterministic results under source reordering;
- candidate- and combination-scoped evidence IDs;
- impossible uploader breadth;
- malformed source receipt identity;
- preservation of source diagnostics;
- zero-authority CLI output and structured refusal.

Refs #9 · #144 · #433 · #753 · #754 · #760 · #764
