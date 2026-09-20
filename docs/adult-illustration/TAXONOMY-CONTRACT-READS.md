# Bounded taxonomy contract reads

Follow-up to #432, #437 and #561, stacked on #562 independently from #690's namespace/graph correction.

The source and review manifests are read by taxonomy construction, prompt compilation and membership inspection. Their one-MiB cap must prevent allocation, not merely reject a large buffer after an unbounded `read_bytes()`.

The shared loader now checks size before opening, binds the opened descriptor to the preflight file identity, and reads at most the limit plus one byte. It rejects a changed size or descriptor metadata before JSON decoding and hashing. An exact-limit file remains valid, and the manifest hash still covers the original bytes, including whitespace.

Both JSON nesting recursion errors and lone-surrogate taxonomy text now fail through controlled ValueError validation rather than escaping later through parser recursion or UTF-8 hashing. Valid non-ASCII display text remains supported. There is no replacement-character repair or normalization of retained source bytes.

## Tests

Six regressions cover pre-open oversize refusal, real growth during read, a same-size edit with a changed modification timestamp, exact-limit/raw-hash acceptance, deeply nested JSON and invalid Unicode scalar text. Handles must close on both success and failure.

The unchanged parent produces six assertion failures and one parser RecursionError. With the correction, 143 adult-illustration tests complete successfully with one existing retained-source test skipped. Exact-head hosted/full-suite results are recorded in the PR rather than inferred from these focused checks.

```sh
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

## Boundaries

The descriptor checks detect observed replacement/modification; they are not a signature, a lock, a multi-file transaction or a complete hostile-filesystem sandbox. They do not guarantee a wall-clock deadline or detect every change hidden by filesystem metadata granularity. The existing repository path/symlink policy remains in force.

Taxonomy CSV reconstruction, compiler source binding, vocabulary approval, content identities and zero execution authority remain unchanged. No provider access, download, generated index, model byte, installation, generation, training or promotion is introduced. HUMAN_TODO q-29 remains open.
