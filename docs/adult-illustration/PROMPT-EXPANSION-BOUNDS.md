# Admit resolution bytes while expanding vocabulary

Follow-up to #432/#437 and #741. Profile implication traversal is iterative, but
one bounded graph can be expanded repeatedly by many input terms. Previously the
128 KiB output check ran only after every resolution had been materialized.

The tag/hybrid compiler now counts the exact canonical UTF-8 JSON bytes of the
resolution array as each trace is produced, including brackets and separators.
Positive and negative inputs share one call-local budget. The first trace that
cannot fit is refused before storing its candidates or expanding the next input.
No input or dependency is silently truncated. The complete-artifact check still
applies because channels, diagnostics, bindings and provenance also consume bytes.

This early test is a lower bound on the complete artifact: its resolution array
is a literal subtree. It cannot reject an otherwise valid artifact. Existing
serialized results, identities, ordering, acceptance rules, and instruction-mode
behavior are unchanged. A failure does not leave a budget shared with later calls.

## Evidence and limits

Five regression methods exercise production compilation with synthetic catalogues:
32 overlapping chains stop after five traces rather than 32; mixed channels share
the budget; multibyte terms count bytes, not characters; the final guard accepts
its exact limit and rejects one byte less; a fresh compilation still succeeds
with unchanged identity after an oversized request fails.

The spy records real expansion calls; it does not invent resolver outputs. Both
the whole output and the count of work performed are asserted. No timer or machine
speed threshold is used. Parent failures and corrected results are retained.

This bounds cumulative trace serialization, not process RSS, elapsed time, or all
compiler allocations. One candidate closure is still materialized under the
existing catalogue entry/fan-out bounds before its trace is admitted. The complete
manifest and graph validators retain their separate responsibilities.

```sh
python -m unittest tests.test_adult_illustration_prompt_expansion_budget -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

No provider call, model bytes, reference image reads, generation, installation or
training is introduced. Authority remains unchanged and HUMAN_TODO q-29 remains
an owner decision. This is a software bound, not artistic or route qualification.
