# Read-only research input consumption

Follow-up to #435 and #433. The research facade remains a catalog and planning API, not an executor.

## Enforce limits while consuming input

Selection parameters accept iterables. Converting an entire iterable to a list before checking its size defeats the existing case, route, dialect and technique caps. The facade now consumes at most the configured maximum plus one item, then refuses oversized input before loading catalogs. Minimum counts, ID syntax, duplicate checks and catalog membership remain the existing planner's responsibility.

Finite list and generator inputs still produce identical content-addressed plans. The proposed count is not an authorized allowance: the authorized candidate cap remains zero and every execution/download/install/generation/training flag remains false.

Manifest size is checked before opening as before, but the actual read now requests at most the one-MiB cap plus one byte. This also bounds allocation when a file grows between the size check and the read. Oversized content is refused before JSON parsing; a changed byte count remains an error. JSON parser recursion errors become ordinary validation errors handled by the existing CLI error boundary.

## Limits of this guarantee

This is a consumption bound, not a sandbox for arbitrary Python iterators. A caller's individual `next()` operation can still block or perform side effects. The change does not add a wall-clock deadline, authenticate same-size concurrent file replacement, or eliminate every filesystem check/open race. It also does not create a provider fetch, subprocess, runtime dispatch or background worker.

## Offline evidence

`tests/test_adult_illustration_research_bounds.py` uses guarded iterators that fail if consumed past the first excess item, real file growth at the stat/open boundary, deeply nested JSON and valid fixture plans. It verifies pre-catalog rejection, bounded read size, exact finite-generator plan identity, and zero authority.

```sh
python -m unittest tests.test_adult_illustration_research_bounds -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py' -v
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

No provider or model access is required. These changes do not resolve programme promotion or HUMAN_TODO q-29.
