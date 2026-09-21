# Deterministic profile vocabulary graph traversal

Follow-up to #432 and #437, on the #562 compiler stack. This concerns the finite
profile-owned fallback vocabulary, not the separately reviewed source taxonomy.

## Preserve the declared bounds, not the interpreter's stack limit

The profile catalogue admits at most 4,096 entries, 32 implications per entry and
a one-MiB manifest. Its recursive cycle checker could nevertheless crash on a
valid 1,200-entry chain. Reversing catalogue order could make validation succeed
by reusing visited tails, only for prompt expansion to crash independently.

Validation now uses explicit depth-first frames with separate active-path and
finished sets. It detects cycles in every component, including shared-tail and
disconnected graphs, without using Python recursion. Unknown targets, polarity
changes and lost profile support remain errors. The known-ID set is built once,
not once per entry.

Expansion also uses an explicit stack. Children are pushed in reverse order so
emission and per-input traces retain the existing left-to-right depth-first order.
A shared descendant appears once per input's closure. No dependency or vocabulary
entry is silently dropped, and no recursion-limit setting is changed.

The existing manifest, entry, fan-out, diagnostic and output bounds remain in
force. A structurally valid graph can still produce an over-budget prompt and
must then be refused by the existing output guard. This is not a new prompt-size,
tokenizer, artistic-quality or runtime-compatibility claim. The taxonomy's own
relationship-depth contract is unchanged.

## Evidence

`tests/test_adult_illustration_profile_graphs.py` covers forward and reverse
1,200-entry chains through real loading, compilation and deterministic validation;
a long cycle; a shared-tail diamond; a disconnected cycle; and semantic edge
refusals. The fixture creates synthetic manifests in temporary directories. It
changes neither checked-in terms nor acceptance decisions.

```sh
python -m unittest tests.test_adult_illustration_profile_graphs -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

No provider, retained CSV, model, reference-image byte, download, installation,
generation or training is required. HUMAN_TODO q-29 remains an owner decision.
