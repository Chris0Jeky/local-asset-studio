# Bounded taxonomy contract reads

Follow-up to #432, #437 and #561, stacked on #562 independently from #690's namespace/graph correction.

The source and review manifests are read by taxonomy construction, prompt compilation and membership inspection. Their one-MiB cap must prevent allocation, not merely reject a large buffer after an unbounded `read_bytes()`.

The shared loader now checks size before opening, binds the opened descriptor to the preflight file identity, and reads at most the limit plus one byte. It rejects a changed size or descriptor metadata before JSON decoding and hashing. An exact-limit file remains valid, and the manifest hash still covers the original bytes, including whitespace.

Both JSON nesting recursion errors and lone-surrogate taxonomy text now fail through controlled ValueError validation rather than escaping later through parser recursion or UTF-8 hashing. Valid non-ASCII display text remains supported. There is no replacement-character repair or normalization of retained source bytes.

## Native Windows correction

The first hosted Windows run rejected some valid freshly rewritten files as concurrent changes. A regression recorded the compared tuples: device, file ID, size and modification time matched, while `st_ctime_ns` differed between path `stat()` and descriptor `fstat()`.

The corrected loader compares the first four identity dimensions across those APIs, then compares all five dimensions, including change time, between the two observations of the same descriptor. It does not round timestamps, add retries or skip Windows tests. The native closed-write regression remains in ordinary discovery, alongside a deterministic guard test proving file-ID changes and descriptor change-time changes are still rejected.

## Tests

Eight new methods cover pre-open oversize refusal, real growth during read, a same-size edit with a changed modification timestamp, exact-limit/raw-hash acceptance, deeply nested JSON, invalid Unicode scalar text, repeated closed writes and descriptor drift. Handles must close on both success and failure.

The first six tests produce six assertion failures and one parser RecursionError against the unchanged parent. Native Windows then reproduced the additional cross-API change-time failure before its correction. The final local focused suite runs 145 adult-illustration tests successfully, with one existing retained-source test skipped. Exact-head hosted/full-suite results are recorded in the PR rather than inferred from these focused checks.

```sh
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

## Boundaries

The descriptor checks detect observed replacement/modification; they are not a signature, a lock, a multi-file transaction or a complete hostile-filesystem sandbox. They do not guarantee a wall-clock deadline or detect every change hidden by filesystem metadata granularity. The existing repository path/symlink policy remains in force.

Taxonomy CSV reconstruction, compiler source binding, vocabulary approval, content identities and zero execution authority remain unchanged. No provider access, download, generated index, model byte, installation, generation, training or promotion is introduced. HUMAN_TODO q-29 remains open.
