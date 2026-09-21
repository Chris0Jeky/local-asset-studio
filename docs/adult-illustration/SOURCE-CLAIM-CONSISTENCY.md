# Provider claim consistency

Follow-up to #433 and #438, layered over #579. This is metadata validation, not a download or execution path.

## Pinned identity is not moving-revision resolution

An explicit 40-hex Hugging Face revision must equal the returned commit, case-insensitively. A moving revision such as `main` or `refs/pr/7` may still resolve to a returned immutable commit. A caller who selected one exact commit must never receive a proposal for another.

When a Hugging Face sibling supplies both top-level and LFS byte-count or SHA-256 claims, both claims are independently validated and must agree. A valid top-level value cannot hide an invalid LFS value. Missing metadata remains unknown, empty files remain valid, and Xet identity is not treated as an interchangeable SHA-256. Sizes must fit the existing saved-snapshot integer bound.

Civitai returned version and nested model IDs must be positive integers, not booleans or numerically equal floats. Saved response status must likewise be an actual integer.

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
