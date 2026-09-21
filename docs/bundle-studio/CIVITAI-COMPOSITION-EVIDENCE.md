# Civitai composition evidence

21 September 2026 · first offline source-evidence slice of #754.
Initial main: `1dbd3d53503cd7323f4f7cd2ff7cba7eb589b00d`.

## Purpose

The setup selector needs better evidence than filenames and marketing family names.
Civitai model-version metadata can describe one exact model/version/file, while
retained image metadata can show that several exact model-version IDs were reported
together with weights and scalar generation settings.

That evidence is useful, but it is not authority:

- a provider label is not a locally verified architecture;
- a gallery image is not a controlled compatibility test;
- reactions do not prove quality;
- visible results do not prove complete provider coverage;
- source permission fields are claims, not a legal decision;
- a response does not prove that the referenced local bytes were installed.

`studio_workflow/civitai_composition.py` therefore normalizes already-retained JSON
offline. It does not crawl, contact Civitai, download models or images, install a
node, modify a setup, prepare a graph or submit generation.

## Relationship to the decision engine

This PR and #755 intentionally remain separate.

```text
explicit bounded provider capture (#433 follow-up)
                         |
                         v
retained Civitai/Civitai.red JSON + request receipts
                         |
         civitai_composition.py (this slice)
                         |
 studio.source-composition-evidence/v1
                         |
 provider-neutral fact/evidence adapter
                         |
 setup compatibility evaluator (#755 / #753)
```

The normalizer records observations. The evaluator decides whether a candidate is
incompatible, needs review, possible or recommended. Gallery evidence can affect
ranking only after hard role, modality, architecture, loader, format, runtime and
companion checks have passed.

## Input contract

The CLI accepts `studio.civitai-composition-input/v1` with:

- one exact model-version snapshot;
- zero to 32 retained image pages;
- at most 1,000 total image records;
- an immutable request/response receipt for every snapshot.

Every receipt contains the exact source host, route, sorted query, retrieval time,
response SHA-256, cache validators, outcome and broad authentication context. It
must not contain credentials or secret query parameters.

Supported hosts are exactly:

- `civitai.com`;
- `civitai.red`.

The hosts are never aliases. Their observations remain in different source scopes.
The image query and browsing/filter parameters are also part of the scope, so a
safe-only query is not silently combined with a broader query.

A model-version snapshot must:

- have outcome `ok`;
- use `/api/v1/model-versions/<positive-version-id>`;
- contain the same exact version ID in the payload.

Every image page must:

- use `/api/v1/images`;
- target that exact `modelVersionId`;
- explicitly request `withMeta=true`;
- carry a bounded, credential-free query.

A `filtered` or `blocked` page remains a retained receipt with a diagnostic. It is
not interpreted as an empty authoritative result.

The response SHA-256 is a retained transport receipt. This offline parser cannot
recreate a raw byte hash from a parsed JSON object. The eventual capture command
must compute and validate the receipt before writing the input file, using the
reviewed bounded transport rather than duplicating provider access here.

## Exact model/version/file facts

The normalizer retains bounded fields needed for later review:

- model ID and version ID;
- AIR when syntactically usable, otherwise `civitai-version:<id>`;
- provider model/version names and type;
- `baseModel` and `baseModelType` claims;
- trained words;
- creation, update and publication strings;
- provider permission claims;
- exact provider file ID, name, byte count, primary flag and file type;
- format, precision and size-class metadata;
- provider hashes and scan-result claims.

A valid SHA-256 becomes the file identity. Without one, the fallback identity is
`civitai-file:<version-id>/<provider-file-id>`.

Filename is not identity. Two files with the same name and different provider file
IDs are retained independently. Duplicate provider file IDs refuse the snapshot.
This avoids silently collapsing records when provider/API filename presentation is
inconsistent.

Descriptions, prompts, model/image download URLs and arbitrary provider markup are
not copied into the output. They are untrusted presentation text and are not needed
for compatibility or composition evidence.

## Gallery observations

For every valid image record the normalizer can retain:

- image ID and optional post ID;
- optional uploader and created string;
- top-level exact `modelVersionIds`;
- typed `meta.civitaiResources` rows;
- exact resource version ID and reported weight;
- steps, CFG, clip skip, sampler, scheduler and dimensions;
- aggregate reaction and comment counts;
- whether metadata was present, absent or malformed.

Malformed optional metadata does not erase valid top-level version IDs. Invalid
individual resource rows are skipped with diagnostics rather than promoting their
claims. Prompt text is never retained.

Identical duplicate image records within one source scope are deduplicated. If the
same source scope and image ID produce conflicting semantic records, all versions
of that image are excluded from evidence; the parser does not pick a first or last
winner.

## Combination aggregation

An unordered exact-version combination is emitted only when at least two version
IDs were reported together. Aggregation is scoped by host, route, query and auth
context.

Breadth is deliberately conservative:

- several images from one post count as one observation;
- distinct posts and distinct uploaders are reported separately;
- repeated work from one uploader does not become independent creator evidence;
- observed resource types and weights remain visible;
- distinct scalar-setting combinations retain occurrence counts;
- engagement is reported separately from evidence breadth.

Every combination explicitly says:

```json
{
  "reported_co_use": true,
  "compatibility_proven": false,
  "quality_proven": false
}
```

The #755 policy may admit exact gallery co-use as recommendation support only after
hard compatibility passes and only with sufficient independent breadth. This file
does not itself label an image successful or a combination optimal.

## Coverage and missing data

`coverage_complete` is false when:

- no image page was retained;
- a page was filtered or blocked;
- a retained page reports an unfetched `nextCursor`.

It does not claim that `true` proves universal Civitai coverage. It means only that
the supplied bounded receipt set did not itself expose one of those incompleteness
conditions. Provider moderation, deletion, authentication, region, indexing and API
behaviour may still limit visibility.

`.com` and `.red` can expose different visible subsets. Those differences are data
to inspect, not records to merge away. A later research report can compare source
scopes explicitly using their receipt hashes and query identities.

## Output and authority

The output format is `studio.source-composition-evidence/v1`. It contains a stable
SHA-256 over the exact input and these explicit authority flags:

```json
{
  "network_performed": false,
  "model_downloaded": false,
  "image_downloaded": false,
  "installation_authorized": false,
  "generation_submitted": false
}
```

The context hash identifies what was normalized. It is not a freshness guarantee,
an approval receipt or proof that the provider response is truthful.

## CLI

```sh
python -m studio_workflow.civitai_composition retained-civitai-input.json
```

Exit 0 prints the normalized report. Invalid input exits 2 with a bounded structured
`invalid_snapshot` error. The command has no network client.

## Verification

The test-only commit `eff448a` preceded the implementation and intentionally failed
because the module did not exist. Focused coverage is:

```sh
python -m unittest discover -s tests -p 'test_civitai_composition.py' -v
python -m studio_workflow.civitai_composition --help
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Fixtures cover exact version/file facts, AIR/SHA identity, same-name files, typed
resource weights, scalar settings, post-level deduplication, uploader breadth,
`.com`/`.red` separation, browsing-level separation, blocked/filtered pages,
incomplete cursors, absent/malformed metadata, invalid resource rows, conflicting
duplicate images, hostile text omission, query/host/route refusal, immutable input,
bounds and CLI zero-authority output.

## Follow-up integration

1. Land or promote the shared provider transport work under #433.
2. Add an explicit operator CLI that captures exact model-version and bounded image
   pages through that transport and writes these receipts. No background crawler.
3. Add reviewed architecture/lineage mappings and local backend/schema observations;
   provider strings alone must not become hard compatibility truth.
4. Adapt normalized exact resource facts and bounded co-use observations into the
   provider-neutral #755 input.
5. Render explanation-first recommendations in Bundle/Create, then apply one atomic
   revision-checked setup diff. Browsing never installs or generates.

## Primary research references

- `https://developer.civitai.com/site/reference/model-versions`
- `https://developer.civitai.com/site/reference/images`
- `https://github.com/civitai/cli`
- `https://github.com/civitai/civitai/blob/main/src/server/utils/server-domain.ts`
- `https://github.com/orgs/civitai/discussions/2198`

No HUMAN_TODO entry is changed by this slice. Adult-illustration q-29 remains an
owner review/acceptance decision.
