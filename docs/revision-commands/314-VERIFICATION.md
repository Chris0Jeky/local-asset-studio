# Shared receipt values: local verification

Base: `67f995f245518b36fb0192a61da780d337d53028`.

## Delivered boundary

The two proven stores already use the shared value toolkit. This change preserves that extraction and adds only `StoredBytes` and `exact_stored_value()` for new byte-bound receipt formats. No SQL, domain action, request dispatch, callback repository, schema migration, cleanup worker or file write was added to the toolkit. The collection journal is the next consumer, in the separate #387 slice.

The distinction is intentional:

```python
# Existing receipts retain their canonical-JSON identity contract.
legacy = stored_value(b'{ "a" : 1 }', canonical_value({'a': 1}).sha256)
assert legacy.matches

# New byte-bound receipts report changes in actual retained evidence.
exact = exact_stored_value(b'{ "a" : 1 }', canonical_value({'a': 1}).sha256,
                           max_bytes=16384)
assert not exact.matches
```

Neither helper decides the public error code, repairs evidence or touches storage. The caller validates its typed schema and acts on the facts. `max_bytes` may narrow, never enlarge, the existing 1 MiB JSON ceiling. Storage input must be UTF-8; literal NUL is refused while a JSON-escaped NUL remains valid.

## Executed checks

Environment: Linux, Python 3.13.5. No model, native application, hosted workflow or automated reviewer was used.

* Original `test_revision_consistency_values.py`: **8 passed** before edits.
* New tests first failed because exact byte binding was absent.
* Final local run: `python -m unittest discover -s tests -p 'test_revision_consistency_*.py' -v`: **19 passed**, consisting of the 8 original value tests and 11 new exact-byte tests. Only these two matching test files were present in the selected-source checkout. This is **not** a claim that the repository-wide fault-matrix files were run.
* `python -m compileall -q studio_workflow tests`: passed for the locally materialized files.
* Whitespace validation of the staged change: `git diff --cached --check`.

## Self-review correction

A UTF-8 decode alone does not establish that the subsequent JSON byte parser will use UTF-8. A BOM-less UTF-16/32 ASCII document can decode as UTF-8 containing NULs, then be autodetected as another encoding by `json.loads(bytes)`. The first non-ASCII test input did not exercise that path. The corrected ASCII regression produced **four failing subtests** without the NUL guard (LE/BE, 16/32-bit) and passed with it. The strict decoder still handles duplicate keys, reserved keys, depth, nonfinite numbers and syntax errors.

## Tested file bindings

| File | Git blob SHA |
| --- | --- |
| `studio_workflow/revision_consistency.py` after change | `6a91168510af4b5df2141c1e7051da06118cf6d1` |
| `tests/test_revision_consistency_exact_bytes.py` | `ac535330eea47a819039f5305e0a110b01181823` |
| unchanged `studio_workflow/core.py` | `93f18cb2f136e9dca8b01415d0d660fcb04e4ed4` |
| original `tests/test_revision_consistency_values.py` | `208e613faad65be616ebe8473fa8d6f25324473b` |

The selected source files were retrieved through the GitHub connector and their full Git blob hashes checked before testing. Native Git network access failed in this runtime. The published tree must be based on the full upstream tree, not on the selected-source local Git tree.

## Not established by this slice

The complete offline repository suite, `scripts/validate-repo.py`, the existing SetupDrafts lifecycle matrix and browser acceptance were not run here. Existing store migrations and payload shapes were not changed. Broader #314 reconciliation and #120/#387 product acceptance remain separate from these 19 pure-value tests. Owner decisions in `HUMAN_TODO.md` are unchanged.
