# Immutable anime taxonomy intake

Implementation slice for [#437](https://github.com/Chris0Jeky/local-asset-studio/issues/437). It turns one exact, operator-retained anime tag vocabulary into a bounded, deterministic, zero-authority index while keeping upstream source facts separate from Local Asset Studio review decisions.

This is a vocabulary and evidence layer. It does **not** download at runtime, install a model, infer adulthood, classify consent, choose a route, compile a prompt, submit a graph, or prove artistic quality.

## Pinned source

| Field | Value |
| --- | --- |
| Provider repository | `SmilingWolf/wd-eva02-large-tagger-v3` |
| Immutable revision | `fa2b83fd2d68b3d994e22fed5859d7cc99e1cdb0` |
| Selected file | `selected_tags.csv` |
| Bytes | `308468` |
| SHA-256 | `298633d94d0031d2081c0893f29c82eab7f0df00b08483ba8f29d1e979441217` |
| Data records | `10861` |
| Columns | `tag_id,name,category,count` |
| Source categories | `0` general, `4` character, `9` rating |

The exact CSV is retained outside Git. The checked-in source contract records its immutable identity, strict bounds, source-field meanings, provider licence claim, and zero runtime authority. A successful build requires both the exact byte count and SHA-256 before any row is parsed.

The provider licence label is evidence for rights review. It is not automatic approval to redistribute the CSV, bundle model assets, expose a hosted service, or reuse generated work.

## Two distinct contracts

`research/adult-illustration/taxonomy-source.json` records what the pinned source publishes:

- canonical tag name;
- numeric tag ID;
- source category;
- source frequency.

The source does not publish aliases, semantic facets, implications, deprecations, profile compatibility, subject age, content class, or compilation acceptance. Those fields must not be presented as upstream facts.

`research/adult-illustration/taxonomy-review.json` is a finite Studio-owned overlay. The initial review accepts 39 reusable terms for the two tag-oriented profiles and records 10 genuinely distinct aliases. Natural-space forms of underscore canonicals resolve through normalization and are not duplicated as aliases.

Every other source row remains present and searchable in the generated index, but has:

```json
{
  "reviewed": false,
  "accepted_for_compilation": false
}
```

Known upstream therefore never means approved for prompt compilation.

## Offline commands

Inspect checked-in source and review identities without reading or fetching the CSV:

```console
python scripts/studio_adult_illustration_taxonomy.py source
```

Build an index from an operator-retained exact copy:

```console
python scripts/studio_adult_illustration_taxonomy.py build \
  /reviewed/source/selected_tags.csv \
  --out .runtime/adult-illustration/taxonomy-index.json
```

Rebuild and exactly validate a saved index:

```console
python scripts/studio_adult_illustration_taxonomy.py validate \
  /reviewed/source/selected_tags.csv \
  .runtime/adult-illustration/taxonomy-index.json
```

Resolve a canonical or reviewed alias:

```console
python scripts/studio_adult_illustration_taxonomy.py lookup \
  .runtime/adult-illustration/taxonomy-index.json \
  "hot spring"
```

`lookup` verifies the saved index content identity but cannot revalidate source bytes because it receives no source file. Its result therefore declares `source_revalidated: false`. Use `validate` before treating a persisted index as reconstructed evidence.

All output writes use exclusive creation. Existing files are never overwritten. Errors are machine-readable and retain download, install, execution, generation, and training authority as false.

## Parser and review invariants

The intake rejects:

- source byte-count or SHA-256 drift;
- oversized source, review, relationship, or output structures;
- malformed UTF-8 or CSV shape;
- changed headers or record count;
- non-integer, negative, duplicate, or unknown source fields;
- duplicate canonical or normalized names;
- review entries absent from the exact source;
- aliases colliding with any source canonical or another alias;
- unknown semantic facets or prompt profiles;
- implication polarity/profile incompatibility;
- implication or deprecation cycles and excessive relationship depth;
- executable or non-zero authority declarations;
- saved-index content or reconstruction drift.

The generated index sorts by canonical source name and has a deterministic `index_id`. It preserves all source rows for diagnostics while making review and compilation eligibility explicit per row.

## Adult/content boundary

The taxonomy must never establish that a subject is an adult, that a scene is consensual, or that a content envelope is permitted. Those facts come only from reviewed user/canon intent and the existing adult-illustration projection contract. Character/rating rows and model/tagger outputs are not substitutes for that declaration.

The first review intentionally accepts no character or rating row. Common profile-owned quality terms that are absent from this pinned taxonomy remain profile configuration rather than being falsely attributed to the source.

## Qualification result

Against the exact retained source, the current slice produces:

- 10,861 source entries;
- 39 reviewed and compilation-eligible entries;
- 10 reviewed aliases;
- a deterministic rendered index below the 16 MiB bound;
- `hot spring` resolving to source canonical `onsen`;
- unreviewed source rows remaining searchable but ineligible.

These results establish software and provenance contracts only. They do not establish improved prompts, exact installed tokenizer counts, route compatibility, generated-content behavior, or accepted artwork.

## Remaining #437 gates

1. Integrate only reviewed eligible entries into prompt-profile diagnostics without silently promoting the full source.
2. Distinguish known-but-unreviewed, unknown, deprecated, and profile-incompatible terms in compiler output.
3. Pin exact installed tokenizer identities before reporting exact token counts; use bounded estimates otherwise.
4. Expand the review overlay only through evidence-backed diffs, never model-authored bulk acceptance.
5. Compare unchanged/manual/taxonomy-assisted prompts under #37/#409 with exact routes, settings, outputs, failures, and human acceptance.
