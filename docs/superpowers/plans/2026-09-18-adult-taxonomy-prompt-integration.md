# Reviewed Taxonomy Prompt Integration Implementation Plan

> **For Chris:** Required sub-skill: use `superpowers:executing-plans` to implement this plan task by task.

**Goal:** Connect the immutable reviewed anime taxonomy from #550 to the deterministic prompt profiles from #450 without requiring the retained source CSV or generated 4.6 MB index at compile time.

**Architecture:** Add a strict, read-only taxonomy overlay loader over the checked-in source and review contracts. Tag and hybrid prompt profiles resolve reviewed taxonomy terms before the smaller profile-owned proof vocabulary. A taxonomy match is authoritative for acceptance, polarity and profile support, so the compiler never falls back around a rejected taxonomy decision. Compiled artifacts retain exact taxonomy identities and a deterministic per-input resolution trace. Instruction profiles keep tags inspectable but never emit them.

**Tech Stack:** Python 3 standard library, existing `studio_prompt` contracts, `unittest`, GitHub Actions.

**Source contracts:**

- `docs/adult-illustration/TAXONOMY-INTAKE.md`
- `docs/adult-illustration/PROMPT-PROFILES.md`
- Issue #437
- PR #550 as the stack base

## Fixed decisions

1. The checked-in taxonomy review is the only new compilation authority. The full upstream CSV remains external and is not loaded by prompt compilation.
2. A reviewed taxonomy match takes precedence over the proof vocabulary. Rejection, polarity mismatch, deprecation or profile incompatibility cannot be bypassed by catalog fallback.
3. `tag` profiles emit the pinned upstream `source_name`; `hybrid` profiles emit the reviewed display form; `instruction` profiles emit neither.
4. Profile-owned terms absent from the taxonomy can still resolve through `prompt-profile-vocabulary.json`.
5. Every compiled artifact binds the taxonomy source SHA-256 and both contract manifest hashes. Changed taxonomy review bytes invalidate retained compiled output.
6. No exact token count is added in this slice. Installed tokenizer identity remains a separate route-evidence gate.
7. No model, node, source file, reference image, ComfyUI process or neural job is touched.

### Task 1: Lock the bridge contract with failing tests

**Files:**

- Create: `tests/test_adult_illustration_taxonomy_prompt_integration.py`

**Step 1: Add taxonomy-first and fallback tests**

Cover:

- `hot spring` resolving through the reviewed taxonomy to upstream `onsen`;
- a taxonomy-only term such as `closed eyes`;
- profile-catalog fallback for `rim light`;
- tag versus hybrid surface forms;
- exact taxonomy source/review identities in compiled output.

**Step 2: Add fail-closed tests**

Cover:

- a taxonomy profile rejection cannot fall back to the proof vocabulary;
- normalized alias collision in the checked-in review refuses;
- changed review manifest invalidates a retained prompt projection;
- Qwen instruction mode records tags as not emitted and never dumps them into instructions.

**Step 3: Run the focused test before implementation**

```console
python -m unittest tests.test_adult_illustration_taxonomy_prompt_integration -v
```

Expected: fail because `studio_prompt.adult_illustration_taxonomy_prompt` does not exist.

**Step 4: Commit the red contract**

```console
git add tests/test_adult_illustration_taxonomy_prompt_integration.py \
  docs/superpowers/plans/2026-09-18-adult-taxonomy-prompt-integration.md
git commit -m "test: define reviewed taxonomy prompt integration"
```

### Task 2: Add the strict reviewed-taxonomy overlay

**Files:**

- Create: `studio_prompt/adult_illustration_taxonomy_prompt.py`
- Test: `tests/test_adult_illustration_taxonomy_prompt_integration.py`

**Step 1: Load existing contracts rather than inventing a store**

Call `load_taxonomy_contracts(root)` and expose only:

- exact source SHA-256 and revision;
- source and review manifest hashes;
- reviewed entries keyed by `source_name`;
- a normalized lookup over source name, display form and reviewed aliases.

**Step 2: Validate the overlay independently**

Reject:

- normalized canonical or alias collisions;
- missing implication/deprecation targets;
- implication polarity or profile-support changes;
- cycles and relationship depth beyond the source contract bound;
- unknown profile IDs against the prompt-profile catalog at integration time.

The loader must not need `selected_tags.csv` or the generated taxonomy index.

**Step 3: Provide deterministic lookup helpers**

Expose bounded helpers that return match provenance and an implication closure. Do not emit text or diagnostics from the loader.

**Step 4: Run loader-focused tests**

```console
python -m unittest \
  tests.test_adult_illustration_taxonomy \
  tests.test_adult_illustration_taxonomy_depth \
  tests.test_adult_illustration_taxonomy_prompt_integration -v
```

Expected: overlay tests pass; compiler assertions still fail until Task 3.

### Task 3: Integrate taxonomy resolution into prompt compilation

**Files:**

- Modify: `studio_prompt/adult_illustration_prompt_projection.py`
- Test: `tests/test_adult_illustration_prompt_profiles.py`
- Test: `tests/test_adult_illustration_taxonomy_prompt_integration.py`

**Step 1: Load and cross-check both vocabularies**

`compile_prompt` loads the existing profile catalog and reviewed taxonomy overlay. Taxonomy profile IDs must exist in the profile catalog.

**Step 2: Resolve taxonomy before proof vocabulary**

For tag and hybrid profiles:

1. normalize the raw input;
2. inspect the reviewed taxonomy;
3. if matched, enforce acceptance, polarity, deprecation and exact profile support;
4. follow only valid accepted implications;
5. render `source_name` for tag mode or `display` for hybrid mode;
6. only when no taxonomy entry matches, try the existing proof vocabulary;
7. otherwise retain the existing unknown-term diagnostic.

**Step 3: Add deterministic provenance**

Add:

- a `taxonomy` identity object;
- `vocabulary_resolutions`, one bounded record per positive/negative input;
- source, match kind, status, entry IDs and emitted forms;
- source-specific diagnostics for taxonomy rejection or incompatibility.

Keep the existing zero-authority flags and final `compiled_sha256` over the complete result.

**Step 4: Preserve instruction semantics**

Qwen instruction compilation keeps tags out of the instruction and marks each term `not_emitted_instruction_profile`. It must not produce taxonomy profile-support warnings for a channel that is intentionally unused.

**Step 5: Run focused compiler tests**

```console
python -m unittest \
  tests.test_adult_illustration_prompt_profiles \
  tests.test_adult_illustration_prompt_cli \
  tests.test_adult_illustration_taxonomy_prompt_integration -v
```

Expected: all pass.

### Task 4: Document and verify the integrated slice

**Files:**

- Modify: `docs/adult-illustration/PROMPT-PROFILES.md`
- Modify: `docs/adult-illustration/TAXONOMY-INTAKE.md`
- Modify: `docs/adult-illustration/README.md` only if the existing reading path needs a cross-link

**Step 1: Document precedence and provenance**

Explain:

- reviewed taxonomy first, proof vocabulary second;
- no fallback around a taxonomy rejection;
- tag versus hybrid surface forms;
- deterministic resolution records and hash invalidation;
- external CSV/index not required at compile time;
- exact tokenizer and artistic qualification remain open.

**Step 2: Run syntax and contract verification**

```console
python -m py_compile \
  studio_prompt/adult_illustration_taxonomy_prompt.py \
  studio_prompt/adult_illustration_prompt_projection.py
python scripts/validate_adult_illustration.py
python scripts/validate_adult_illustration_intelligence.py
python scripts/studio_adult_illustration_taxonomy.py source
python scripts/studio_adult_illustration_prompt.py profiles
```

**Step 3: Run the complete Adult Illustration suite**

```console
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
```

**Step 4: Inspect the final diff**

Confirm:

- no retained CSV, generated index, model asset or temporary workflow is committed;
- no authority flag changes to true;
- no provider/network/runtime dependency is introduced;
- the PR is stacked only on #550;
- exact tokenizer evidence and accepted-output qualification remain explicitly open.

**Step 5: Commit and open a review-ready stacked PR**

```console
git add studio_prompt tests docs
git commit -m "feat: integrate reviewed taxonomy into prompt diagnostics"
```

Open the PR against `codex/adult-illustration-taxonomy-intake`, reference #403/#432/#437, and keep #437 open for tokenizer and accepted-output gates.
