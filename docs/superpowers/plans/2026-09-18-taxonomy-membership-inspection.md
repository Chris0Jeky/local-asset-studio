# Taxonomy Membership Inspection Implementation Plan

**Goal:** Add a deterministic, zero-authority inspection report that combines a validated prompt projection, an operator-provided taxonomy index and the exact retained taxonomy source bytes so unresolved compiler inputs can be classified as source-known/unreviewed or absent from the pinned source without trusting a self-rehashed index.

**Architecture:** Keep prompt emission unchanged. Validate the retained prompt by recompilation, validate the saved index's strict structure and current checked-in source/review identities, then deterministically rebuild that index from the exact supplied source bytes and current finite review. Only after both evidence checks succeed, build bounded membership maps and inspect each original compiler resolution. Persist the result as a separately versioned, content-addressed report.

**Stack:** Python 3 standard library, existing adult illustration projection/taxonomy contracts, `unittest`, GitHub Actions.

## Fixed decisions

1. The taxonomy CSV and generated index remain operator-provided and outside Git.
2. Exact retained taxonomy source bytes are mandatory for membership inspection because unreviewed source rows cannot be authenticated from an index's self-derived content hash alone.
3. Membership inspection never changes prompt channels, vocabulary acceptance, route selection or generation authority.
4. `source_revalidated: true` is emitted only after `validate_taxonomy_index` reconstructs the supplied index from the exact source bytes and current review contract.
5. The report is separate from `prompt-projection/v2`; this avoids another prompt artifact version merely to attach optional evidence.
6. Every original positive/negative input receives exactly one inspection result in compiler order.
7. The command fails closed on stale prompt source, stale source metadata, stale source/review contracts, changed reviewed overlays, malformed index data, wrong source bytes or an existing output path.
8. The membership module first reuses strict saved-index/current-contract validation for precise diagnostics, then reuses exact taxonomy reconstruction. It must not duplicate or weaken either validator.
9. Source bytes are read with the taxonomy contract's finite `max_source_bytes` bound; prompt/source documents remain at 1 MiB and the saved index remains bounded to 64 MiB before JSON parsing.

## Review correction

Codex review identified that a changed unreviewed canonical row could be paired with a recomputed `index_id`, allowing a forged `source_known_unreviewed` or `not_in_pinned_source` classification. The correction adds a RED-before/GREEN-after contract proving that self-rehashing is insufficient and requires exact source reconstruction before classification.

## Task 1: Lock the report contract with failing tests

Create `tests/test_adult_illustration_prompt_membership.py` and `tests/test_adult_illustration_prompt_membership_source_auth.py` covering:

- reviewed accepted positive and negative terms;
- normalized source-known but unreviewed canonical membership;
- a term absent from the pinned source;
- stale source metadata and contract hashes;
- changed reviewed overlays;
- rehashed but structurally invalid indexes;
- a self-rehashed changed unreviewed row;
- wrong taxonomy source bytes;
- exact source bytes authenticating membership;
- deterministic report identity and recomputation validation;
- changed source projections;
- CLI round-trip, bounded reads and exclusive-create output;
- no network, subprocess, model or ComfyUI side effects.

Run:

```console
python -m unittest tests.test_adult_illustration_prompt_membership_source_auth -v
python -m unittest tests.test_adult_illustration_prompt_membership -v
```

Expected RED before the correction: the inspector does not accept source bytes and the forged-index regressions fail at the old function signature.

## Task 2: Authenticate the saved index

For each inspection:

1. validate the saved index's content identity and strict persisted structure;
2. bind all pinned source metadata and both checked-in manifest hashes to current contracts;
3. compare every finite reviewed-overlay field with the current review contract;
4. rebuild the expected index from the exact supplied source bytes and current review;
5. require byte-for-byte canonical equality with the saved index before membership lookup.

This order preserves useful stale-contract and malformed-index diagnostics while preventing self-rehashed unreviewed rows from becoming evidence.

## Task 3: Implement the membership report

Create `studio_prompt/adult_illustration_prompt_membership.py`.

The inspector must:

- validate the compiled prompt against its reviewed source projection;
- authenticate the taxonomy index through the two-stage validation above;
- require the compiled prompt's taxonomy identity to match the authenticated index;
- build canonical, reviewed-display and reviewed-alias lookup maps once;
- retain compiler source/status/emission beside index evidence;
- classify inputs as reviewed accepted, reviewed ineligible, source-known unreviewed or absent;
- emit bounded counts, zero-authority flags, limitations and a deterministic report hash;
- set `source_revalidated: true` only after exact reconstruction;
- provide a recomputing validator for retained reports.

## Task 4: Add the CLI command

Extend `scripts/studio_adult_illustration_prompt.py` with:

```console
inspect-membership COMPILED \
  --source SOURCE \
  --taxonomy-index INDEX \
  --taxonomy-source SELECTED_TAGS_CSV \
  [--out REPORT]
```

Read the taxonomy source with its checked-in contract bound. Keep duplicate-key and non-finite-number rejection for JSON inputs and preserve exclusive creation for reports.

## Task 5: Document and verify

Add a focused guide covering:

- when membership inspection is useful;
- why exact source bytes are required;
- what `source_revalidated: true` proves and does not prove;
- the difference between source membership and reviewed compilation eligibility;
- explicit non-promotion, privacy and non-execution boundaries.

Run:

```console
python -m py_compile \
  studio_prompt/adult_illustration_prompt_membership.py \
  scripts/studio_adult_illustration_prompt.py
python -m unittest \
  tests.test_adult_illustration_prompt_membership_source_auth \
  tests.test_adult_illustration_prompt_membership \
  tests.test_adult_illustration_taxonomy_prompt_integration \
  tests.test_adult_illustration_prompt_cli -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
```

Inspect the final diff to confirm no CSV, generated index, model asset, private reference or temporary workflow is committed. Open a draft PR against `codex/adult-illustration-taxonomy-prompt-integration`, address review findings, remove all temporary patch machinery, and reference #561/#437.
