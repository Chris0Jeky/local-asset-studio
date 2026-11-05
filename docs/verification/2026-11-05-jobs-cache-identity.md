# Jobs cache identity — 5 November 2026

Issue #1808 identified five cache and invalidation concerns. The implementation
base `6b6ee2cfee6991bdb540a3193dca9abe7990d86e` already contains the stale
revision guard, save completion invalidation and Studio fake compatibility.
This change repairs the remaining collection replacement collision and adds
concurrent HTTP coverage of both replacement and revision changes.

## Replacement failure and correction

`JobsView` instances loaded through their constructor can each start at revision
zero. Cached bytes keyed only by `(revision, privacy scope)` therefore survived
replacement of `studio.jobs`, even when the new collection was empty. A delayed
builder from the former collection could also finish after the new builder and
overwrite its answer at the same revision.

The cache token and entry now retain the actual collection. Lookup requires the
entry's collection to be the current one. Store checks collection identity and
revision together under `studio.lock`, then prunes entries from other
collections or revisions. Retaining the reference makes the check independent
of recycled `id()` values or attributes carried across a copied `JobsView`.
Cache keys remain `(revision, scope)` and successful stores retain at most the
three supported privacy scopes. A superseded collection can be retained by the
old entries until the next successful store; that store removes those entries.

Two regressions were run against the unchanged implementation before the fix:

- `test_replacing_jobs_at_the_same_revision_invalidates_every_scope` failed
  independently for Regular, Private and All: each returned stale `304` instead
  of `200` with an empty list.
- `test_a_delayed_http_builder_cannot_replace_a_newer_cached_answer` blocks an
  HTTP builder after projection with events, publishes and caches a new answer,
  then releases the old builder. The replacement case failed because the old
  ETag replaced the new one. Its revision-change case already passed. Both cases
  now retain the new cached bytes without another projection or serialization.

## Reconciliation of the other issue findings

| Finding | Existing implementation and evidence |
| --- | --- |
| An old revision builder evicts a newer entry | `jobs_view_store` already rejects the old revision while holding `studio.lock`, before pruning anything. `test_a_slow_builder_at_an_old_revision_never_evicts_a_newer_entry` covers the finishing order directly; the new HTTP barrier regression covers a real concurrent read. |
| A save needs invalidation after writes, including failure | `Studio._save` already bumps before its `try` and in `finally`. `test_save_bumps_again_after_the_write_and_when_it_fails` observes a revision after the last real write and verifies both bumps when the writer raises. |
| In-place edits need an explicit invalidation contract | `JobsView` documents `_save` or `bump_jobs_view` for edits inside a row. `test_every_mutation_kind_invalidates` exercises save, insert, pop, deletion, put-away, abandonment, stop-tracking and explicit bump through conditional HTTP reads. `test_post_answers_bump_for_mutations_no_method_announces` covers the POST response fallback, and the migration test exercises direct privacy migration without relying on a POST answer. |
| GET assumes cache helpers on Studio fakes | The GET route already uses cache helpers only for an actual `Studio`, matching the POST guard. `test_get_tolerates_a_studio_like_object_without_the_cache_methods` runs the shipped handler against a fake with just jobs, lock and public projection. |

`parallax.Finisher._save_marker` adds `recording_error` after catching a failed
save. Its runtime calls keep the whole transition under the Studio lock:
`submit` owns `self.changed`, whose condition uses `studio.lock`; worker status
changes and shutdown also own that condition; final pair publication owns
`studio.lock`; and `finish_after_run` catches and records failures under that
lock. Constructor recovery runs before the Studio is published or workers are
started. A GET lookup therefore cannot warm a cache between the save's final
bump and this exception cleanup. The parallax worker regressions cover failed
link and failed status saves, retaining visible `recording_error` information.

The mutation contract remains explicit. Code that changes a settled row must
save it or announce its final in-memory edit with `bump_jobs_view`; a multi-step
transition protected by `studio.lock` must include exception cleanup inside the
same lock. Active jobs, queued work, a busy worker and open cancel requests
bypass the cache. `test_unbumped_edits_heal_when_the_entry_expires` documents the
30-second fallback for a caller that violates the contract. This patch does not
introduce recursive mutable wrappers or a repository-wide AST policy: neither
is needed for the reproduced collision, and a static scan would not establish
the runtime lock and nested mutation boundaries above.

## Verification

On this patch:

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_jobs_*.py'` | 24 passed, including the two new regressions and frontend ETag behavior |
| `python -m unittest discover -s tests -p test_server.py` | 177 passed |
| `python -m unittest discover -s tests -p test_parallax_finish_worker.py` | 16 passed |
| `python scripts/validate-repo.py` | Passed: 98 preset graphs/bindings, 194 pinned assets, 167 LoRA names |
| `git diff --check` | Passed |

The full suite and configured workstation qualification were not run in this
environment. The environment cannot reliably inspect its own process through
psutil, so unmocked backend/process qualification requires hosted CI or the
configured workstation. No owner application or generation was launched.
Art direction #1923, parallax usability and the island default decision remain
owner items in `HUMAN_TODO.md`; these checks do not answer them.
