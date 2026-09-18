# Taxonomy membership inspection

Implementation guide for [#561](https://github.com/Chris0Jeky/local-asset-studio/issues/561). This optional evidence pass combines a retained `studio.adult-illustration.prompt-projection/v2` artifact with an operator-provided taxonomy index so unresolved compiler inputs can be distinguished from source-known but unreviewed vocabulary.

The report is deliberately separate from prompt compilation. It does not alter a prompt, accept a term, select a route, bind a tokenizer, stage an image or submit generation.

## Why this is separate

The taxonomy-aware compiler reads only the small checked-in source/review contracts. That keeps normal compilation bounded and avoids vendoring the 308,468-byte source CSV or generated 4.6 MB index. Without full membership evidence, an unmatched term can only be reported as unknown.

Membership inspection is an opt-in evidence operation for users or agents that already retained a validated index. It preserves the compiler result and adds source-membership context around each original positive or negative input.

## Prerequisites

1. A reviewed source projection.
2. A retained prompt projection compiled from that source.
3. A taxonomy index built from the exact retained CSV and current review contracts:

```console
python scripts/studio_adult_illustration_taxonomy.py build \
  /reviewed/source/selected_tags.csv \
  --out .runtime/adult-illustration/taxonomy-index.json
```

For the strongest reconstruction evidence, validate the index against the exact source bytes before inspection:

```console
python scripts/studio_adult_illustration_taxonomy.py validate \
  /reviewed/source/selected_tags.csv \
  .runtime/adult-illustration/taxonomy-index.json
```

## Inspect membership

```console
python scripts/studio_adult_illustration_prompt.py inspect-membership \
  experiments/runs/hot-spring-prompt.json \
  --source experiments/runs/hot-spring-projection.json \
  --taxonomy-index .runtime/adult-illustration/taxonomy-index.json \
  --out experiments/runs/hot-spring-membership.json
```

The command:

1. deterministically recompiles and validates the prompt artifact;
2. validates the saved index content identity and strict structure;
3. requires exact source SHA-256, immutable revision and source/review manifest hashes to match the compiled prompt;
4. builds canonical and reviewed-alias lookup maps once;
5. inspects each original compiler input in order;
6. writes a separate content-addressed report using exclusive creation.

Prompt/source documents remain bounded to 1 MiB. The explicitly supplied index has a separate 64 MiB read cap, above the taxonomy contract's 16 MiB rendered-index limit but still finite before JSON parsing.

## Classifications

| Classification | Meaning |
| --- | --- |
| `source_known_reviewed_accepted` | The exact source contains the term and the Studio review currently accepts it for at least one declared compilation context. |
| `source_known_reviewed_ineligible` | The source contains the term and it is reviewed, but the review does not accept it for compilation. |
| `source_known_unreviewed` | The pinned source contains the normalized canonical term, but no Studio review semantics or compilation authority exist. |
| `not_in_pinned_source` | The validated index has no canonical or reviewed-alias match for the input. |

Each inspection retains the compiler's source, status, match kind, entry IDs, emitted forms and semantic facets beside index evidence such as canonical source name, tag ID, category and descriptive frequency.

Known upstream never means recommended, safe, adult, consented, tokenizer-compatible or artistically useful. An unreviewed term remains ineligible even when membership is proven.

## Evidence identity

Reports use `studio.adult-illustration.prompt-membership-report/v1` and bind:

- prompt profile ID and compiled content hash;
- source projection hash;
- prompt catalog manifest hash;
- taxonomy index ID;
- source SHA-256 and immutable revision;
- source/review manifest hashes;
- source and reviewed-entry counts;
- a deterministic `report_sha256`.

The saved index's content identity is validated, but inspection does not receive source bytes. It therefore records:

```json
{
  "index_identity_validated": true,
  "source_revalidated": false
}
```

`source_revalidated: false` is not a failure. It prevents a persisted index from being mistaken for a fresh reconstruction. Use the taxonomy `validate` command when exact source-byte reconstruction is required.

## Authority and privacy boundary

Every report keeps download, install, execution, generation and training authority false. The command:

- opens no provider connection;
- starts no model runner or ComfyUI process;
- reads no reference image bytes;
- downloads or installs nothing;
- writes no prompt/source/index changes;
- submits no neural work;
- creates no allowance or promotion state.

The source CSV, generated index, prompt artifacts and membership reports remain runtime/operator evidence and are not committed by this slice.

## Verification

```console
python -m py_compile \
  studio_prompt/adult_illustration_prompt_membership.py \
  scripts/studio_adult_illustration_prompt.py

python -m unittest tests.test_adult_illustration_prompt_membership -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
```

Passing tests establish deterministic evidence classification, strict identity binding, bounded parsing, tamper rejection and zero-authority behavior. They do not establish source licence clearance, exact tokenizer behavior, prompt quality, route compatibility or accepted artwork.
