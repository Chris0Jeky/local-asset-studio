# Inspect compiled prompt taxonomy membership

Issue #561 adds a zero-authority evidence report that joins three retained records:

1. a `studio.adult-illustration.prompt-projection/v2` compiled prompt;
2. the exact reviewed source projection from which that prompt is deterministically recompiled;
3. an operator-provided `studio.adult-illustration-taxonomy-index/v1` file.

The report distinguishes reviewed taxonomy terms, source-known but unreviewed terms, and terms absent from the pinned source. It does not alter prompt emission, promote vocabulary, contact a provider, read reference images, call a model, submit generation or grant execution authority.

## Command

```console
python scripts/studio_adult_illustration_prompt.py inspect-membership \
  experiments/runs/hot-spring-anima-prompt.json \
  --source experiments/runs/hot-spring-projection.json \
  --taxonomy-index .runtime/adult-illustration-taxonomy-index.json \
  --out experiments/runs/hot-spring-taxonomy-membership.json
```

The taxonomy index can be produced with the separate offline intake command documented in [Taxonomy intake](TAXONOMY-INTAKE.md). The generated index and retained source CSV remain outside the repository. Input is bounded to 64 MiB for the index and 1 MiB for each prompt/source JSON document. Output uses exclusive creation and never overwrites an existing file.

## Validation sequence

The inspection fails closed unless all of these checks pass:

1. The compiled prompt exactly matches deterministic recompilation from the supplied source projection and current prompt/profile/review contracts.
2. The taxonomy index has the expected schema, zero-authority declarations, strict entry shape, internally consistent counts, unique canonical names and aliases, valid relationships, and a SHA-256 identity matching its canonical content.
3. The index source metadata exactly matches the current pinned provider, repository, immutable revision, selected file, byte count, source SHA-256 and record count.
4. The index source/review manifest hashes match the current checked-in contracts and the compiled prompt.
5. Every reviewed index entry exactly matches the finite checked-in review overlay; a changed reviewed alias, display form, implication, polarity, profile list or acceptance flag is refused.

The report deliberately sets `source_revalidated: false`. Content-addressing and contract matching cannot prove that every unreviewed entry was reconstructed from the retained CSV. Exact source reconstruction remains:

```console
python scripts/studio_adult_illustration_taxonomy.py validate \
  retained-selected_tags.csv \
  .runtime/adult-illustration-taxonomy-index.json
```

That separate command needs the exact retained source bytes and deterministically rebuilds the complete index.

## Membership rows

The report preserves one ordered row for every original positive and negative compiler input. Each row retains:

- the original channel, input and normalized form;
- compiler source, status and compiler match kind;
- `reviewed`, `source_known_unreviewed` or `absent` membership;
- index match kind (`canonical`, `normalised_space`, `display` or `alias`);
- canonical source name, tag ID, source category, frequency, review flag and compilation-acceptance flag when the validated index supports them.

`source_known_unreviewed` is descriptive evidence only. It does not establish intended meaning, correct polarity, profile compatibility, safety, quality or artistic value. `absent` means absent from the supplied validated index, not impossible language. A reviewed term can still have a compiler status such as deprecated, wrong polarity or unsupported profile; membership never overrides that compiler decision.

## Identity and authority

The output schema is `studio.adult-illustration.prompt-taxonomy-membership/v1`. It binds:

- compiled prompt SHA-256;
- source-projection SHA-256;
- taxonomy index ID;
- pinned taxonomy source SHA-256;
- source and review manifest hashes;
- deterministic report SHA-256.

All authority fields remain false. The command opens no socket, starts no process, downloads nothing, reads no model/reference bytes and submits no job. Passing tests establish deterministic evidence handling, not tokenizer compatibility, local route readiness, prompt quality, content behavior or accepted artwork.

## Verification

```console
python -m py_compile \
  studio_prompt/adult_illustration_taxonomy_membership.py \
  scripts/studio_adult_illustration_prompt.py

python -m unittest \
  tests.test_adult_illustration_taxonomy_membership \
  tests.test_adult_illustration_taxonomy_prompt_integration \
  tests.test_adult_illustration_prompt_cli -v
```

The focused fixture intentionally builds content-addressed index evidence without retaining the external source CSV. It therefore exercises the same `source_revalidated: false` trust boundary as the inspection report.
