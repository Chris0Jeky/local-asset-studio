# Provider claim consistency

Follow-up to #433 and #438, layered over #579. This is metadata validation, not a download or execution path.

## Pinned identity is not moving-revision resolution

An explicit 40-hex Hugging Face revision must equal the returned commit, case-insensitively. A moving revision such as `main` or `refs/pr/7` may still resolve to a returned immutable commit. A caller who selected one exact commit must never receive a proposal for another.

An abbreviated 7-39-hex Hugging Face commit is bound as an immutable prefix, not a moving ref: the returned validated 40-hex commit must start with the stripped request, case-insensitively, and a mismatch fails before any snapshot or claim is returned. Stored re-entry enforces the same prefix check. A matching prefix is not the same evidence as a full commit identity: it only confirms the resolved commit falls in the requested prefix family and carries weaker uniqueness and collision-resistance than an exact 40-hex pin. Prefer full commits for retained evidence.

When a Hugging Face sibling supplies both top-level and LFS byte-count or SHA-256 claims, both claims are independently validated and must agree. A valid top-level value cannot hide an invalid LFS value. Missing metadata remains unknown, empty files remain valid, and Xet identity is not treated as an interchangeable SHA-256. Sizes must fit the existing saved-snapshot integer bound.

Civitai returned version and nested model IDs must be positive integers, not booleans or numerically equal floats. Saved response status must likewise be an actual integer.

## Hex-named branches require an explicit namespaced ref (#1017)

A caller that means a moving branch whose name happens to be hexadecimal must
request it as `refs/heads/<hex-name>` (for example `refs/heads/deadbeef`). The
namespaced form is treated as a moving ref: it may resolve to any unrelated
full 40-hex commit, the resolved commit is retained as `immutable_revision`,
and the original `refs/heads/<hex-name>` binding is retained as
`requested_revision` through stored re-entry.

An unqualified 7-39-hex revision keeps the #804 commit-prefix meaning in
source intake: the returned commit must start with it case-insensitively,
and an unrelated SHA fails before any snapshot or claim is returned. A full
40-hex revision remains an exact pin. Stored re-entry enforces the same rule,
so rewriting a stored `requested_revision` from `refs/heads/deadbeef` to
`deadbeef` fails even when the stored request and response URLs are re-pointed
to the unqualified route. Requests percent-encode the slash
(`refs/heads/deadbeef` to `refs%2Fheads%2Fdeadbeef`).

Official endpoint evidence (25 Sep 2026, read-only GET, no mutation):
`revision/main?blobs=true` and `revision/refs%2Fheads%2Fmain?blobs=true` on
`google-bert/bert-base-uncased` both returned HTTP 200 and the same full SHA
`86b5e0934494bd15c9632b12f734a8a67f723594`. This verifies the namespaced
branch route exists on the official API; it does not prove any specific hex
branch exists publicly.

- [revision/main?blobs=true](https://huggingface.co/api/models/google-bert/bert-base-uncased/revision/main?blobs=true)
- [revision/refs%2Fheads%2Fmain?blobs=true](https://huggingface.co/api/models/google-bert/bert-base-uncased/revision/refs%2Fheads%2Fmain?blobs=true)

`HexNamedBranchTests` in `tests/test_adult_illustration_source_revision_prefix.py`
covers this synthetically with no provider calls or model bytes: a namespaced
hex branch resolving to an unrelated SHA succeeds and round-trips through
stored validation with its binding intact, the unqualified same hex revision
against the same SHA fails, and stored tampering from the namespaced ref to
the unqualified hex fails. The success path asserts the encoded
`refs%2Fheads%2Fdeadbeef` request URL, a single metadata GET, and retained
`download_authorized` falsehoods.

## Generation and re-entry share the same checks

Both snapshot constructors now validate their finished proposals through the existing saved-snapshot validator before returning. The explicit fetch wrapper therefore cannot finalize a contradictory proposal into its cache. These semantic failures are not retried as transport errors.

Stored request URLs are derived from the provider record. Every recorded response route must belong to that exact source, and the final URL must equal the last recorded redirect, or the request when there was no redirect. Supported canonical routes are the requested Hugging Face revision and its resolved commit, or the exact Civitai version on `civitai.com`/`www.civitai.com`. Other spellings, mirrors, versions and repositories are not silently repaired.

This validates the consistency of recorded facts; it does not authenticate a self-consistent replacement of all evidence. A snapshot's payload hash without the raw payload cannot establish that every retained claim was actually in that payload. Historical raw-payload retention remains #694, and provider claims still do not establish local byte verification, rights approval or exact graph executability.

## Verification

`tests/test_adult_illustration_source_identity.py` contains 12 offline regressions and positive controls. The unchanged #579 parent produces 19 assertion failures; the corrected source stack passes all 147 tests. Tests use synthetic provider metadata and temporary caches, with no provider calls or model bytes.

```sh
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Provider terminology: [Hugging Face HfApi / RepoSibling](https://huggingface.co/docs/huggingface_hub/v1.6.0/en/package_reference/hf_api). File size, Git blob identity and LFS metadata are separate facts; this change does not substitute one for another.

No installation, generation, training, inventory mutation or promotion authority is added. HUMAN_TODO q-29 is not resolved by this patch.
