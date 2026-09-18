# Taxonomy Membership Inspection Implementation Plan

**Goal:** Add a deterministic, zero-authority inspection report that combines a validated prompt projection with an operator-provided taxonomy index so unknown compiler inputs can be classified as source-known/unreviewed or absent from the pinned source.

**Architecture:** Keep prompt emission unchanged. Validate the retained prompt by recompilation, validate the saved taxonomy index by its content identity and strict structure, require exact source/review contract identities to agree, then build one bounded membership map and inspect each original compiler resolution. Persist the result as a separately versioned, content-addressed report.

**Stack:** Python 3 standard library, existing adult illustration projection/taxonomy contracts, `unittest`, GitHub Actions.

## Fixed decisions

1. The taxonomy CSV and generated index remain operator-provided and outside Git.
2. Membership inspection never changes prompt channels, vocabulary acceptance or generation authority.
3. A saved index proves its own content identity and contract binding, but not reconstruction from source bytes. Reports therefore retain `source_revalidated: false`.
4. The report is separate from `prompt-projection/v2`; this avoids another prompt artifact version merely to attach optional evidence.
5. Every original positive/negative input receives exactly one inspection result in compiler order.
6. The command fails closed on stale prompt source, stale taxonomy contracts, malformed index data or an existing output path.

## Task 1: Lock the report contract with failing tests

Create `tests/test_adult_illustration_prompt_membership.py` covering:

- reviewed accepted positive and negative terms;
- normalized source-known but unreviewed canonical membership;
- a term absent from the pinned source;
- stale contract hashes;
- rehashed but structurally invalid indexes;
- deterministic report identity and recomputation validation;
- changed source projections;
- CLI round-trip and exclusive-create output.

Run:

```console
python -m unittest tests.test_adult_illustration_prompt_membership -v
```

Expected RED: the membership module and CLI command do not exist.

## Task 2: Expose strict saved-index identity validation

Modify `studio_prompt/adult_illustration_taxonomy.py` to expose a public `validate_taxonomy_index_identity` wrapper around the existing strict structural/content validator. It must return a detached value and must not imply source-byte reconstruction.

## Task 3: Implement the membership report

Create `studio_prompt/adult_illustration_prompt_membership.py`.

The inspector must:

- validate the compiled prompt against its reviewed source projection;
- validate the index content identity and structure once;
- require source SHA-256, revision and both contract hashes to match;
- build canonical and reviewed-alias lookup maps once;
- retain compiler source/status/emission beside index evidence;
- classify inputs as reviewed accepted, reviewed ineligible, source-known unreviewed or absent;
- emit bounded counts, zero-authority flags, limitations and a deterministic report hash;
- provide a recomputing validator for retained reports.

## Task 4: Add the CLI command

Extend `scripts/studio_adult_illustration_prompt.py` with:

```console
inspect-membership COMPILED --source SOURCE --taxonomy-index INDEX [--out REPORT]
```

Raise the read limit only for the taxonomy index, bounded to 64 MiB. Keep source/compiled documents at 1 MiB and preserve duplicate-key/non-finite-number rejection.

## Task 5: Document and verify

Update the prompt/taxonomy guides with:

- when membership inspection is useful;
- why `source_revalidated` remains false;
- how to rebuild with exact source bytes when stronger evidence is needed;
- explicit non-promotion and non-execution boundaries.

Run:

```console
python -m py_compile \
  studio_prompt/adult_illustration_prompt_membership.py \
  studio_prompt/adult_illustration_taxonomy.py \
  scripts/studio_adult_illustration_prompt.py
python -m unittest tests.test_adult_illustration_prompt_membership -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
```

Inspect the final diff to confirm no CSV, generated index, model asset, private reference or temporary workflow is committed. Open a draft PR against `codex/adult-illustration-taxonomy-prompt-integration` and reference #561/#437.
