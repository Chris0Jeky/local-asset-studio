# Coroutine lifetime qualification: fix and handoff

Refs #1270. This fixes an independently reproduced false-success condition in the lifetime guard. It does not establish the cause or resolution of the historical interpreter signal-11 crash, and #1270 must remain open.

## Reproduced defect and behavior

A real suite can pass, emit `RuntimeWarning: coroutine ... was never awaited` during a test or interpreter finalization, exit zero, and be accepted by the previous parent. Its existing `ResourceWarning` check does not cover this warning class.

The parent now recognizes actual unawaited-coroutine warning headers only after the worker exits. It checks stdout and stderr separately so a partial stdout line cannot obscure a stderr header. Ordinary mentions of the phrase and unrelated runtime warnings do not fail qualification.

The child command enables fatal-error dumps and explicitly enables RuntimeWarning reporting despite ambient PYTHONWARNINGS suppression. The dedicated worker enables bounded, eight-frame coroutine origins before discovery in its main thread. This attributes import-time and test-time creation while frames still exist; it does not promise origin capture in every child thread, recover an old missing crash trace, or override filters deliberately installed by individual tests.

Default 600-second budget, explicit hosted 900-second override, sharding, nonzero exit handling, ResourceWarning failure and actual process-exit waiting are unchanged. No synthetic scanner, resource-forcing cleanup, GC-policy change, dependency addition, alternate test command or new publisher workflow is introduced.

## Current Windows qualification — 11 October 2026

The coordinator refreshed this branch onto main `1525089e`, preserving its original commits. Against the unchanged old guard at `82f1e6b2`, all seven real-subprocess regressions ran on Windows Python 3.14: five expected failures and two passing controls in 2.907 seconds. These cover the missing warning rejection, warning suppression and diagnostic enablement; no historical Linux run is substituted for this baseline.

At integrated source `b6334056`, all seven regressions pass in 3.057 seconds. The existing guard (two), lifetime (13), shard (four) and atexit (four) tests also pass: 30 focused tests total, followed by repository validation (92 graphs/bindings, 176 pins, 3,810 tracked paths). Source and the shared helper stayed frozen during execution. The coordinator observed exclusive admission above 4 GiB free, terminal exit 0 and lease release.

Independent Sol Medium and distinct Muse source reviews found no confirmed merge blocker. A non-blocking outer fixture-timeout descendant-cleanup concern is tracked in #1322; this focused run neither demonstrates that failure nor changes any lifetime budget. Current published-head full Linux/Windows qualification remains pending. Refs #1270 stays open: no cause or resolution of its historical signal-11 crash is established.

The archive identities and older measurements below remain historical provenance, not current qualification claims. No installed runtime, generation, licensing or owner art acceptance was inferred.

## Source identity

Local execution uses the supplied archive identified by ZIP comment `81c7f8479c77937e44a0d721249c498d866d484f`, not a full current-main clone. The two modified existing preimages were verified against immutable main `accc8604311d2fd2f7a9e0278d3b05c0e2e96ba1` and match that archive:

- Parent preimage: `73e9058da5b70ac5894595de84d0977968fbee63`.
- Worker preimage: `a73ca402a04097a438cc6658e5bc3f396dc83e2e`.

The executable outputs stored through the GitHub connector match the locally tested blob identities:

- Parent: `d5c2931cab0d43dab9e34ea119e0b141ec209be2`.
- Worker: `2b179f07a655ec0c36f6d6e949ad08106f8abb40`.
- New subprocess regressions: `e2981aca4b006bba311526684dcb2c6c576e7677`.

## Measured local evidence at publication

Python 3.13.5 on Linux, Node 22.16.0. Hosted Python 3.12 and Windows remain distinct environments.

- Initial six real-process contracts: four fail, two pass before the implementation.
- Same six pass after implementation; the added partial-stdout regression makes seven passing tests in the final focused run, exit 0 (26.225 seconds).
- Tests cover warnings during passing tests and atexit, creation origin before discovery, fatal-dump enablement, ambient warning suppression, awaited and explicitly closed controls, benign mentions, unrelated warnings, and partial stdout.
- Python compilation and `git diff --check` pass.
- Repository validation passes 92 preset graphs/bindings, 176 pinned assets, 158 LoRA names and the archive's local-only media checks.

Existing lifetime fixtures and the unchanged canonical full-suite command are separate qualification steps. No full-suite pass is claimed by the focused results. An earlier baseline attempt was deliberately invalidated because source files changed while nested fixtures were running; it is neither a pass nor a product failure. The subsequent full-suite candidate runs from a frozen worktree. Final results belong in the PR discussion and any later evidence update.

## Repeatable checks

```sh
python -m unittest discover -s tests -p test_full_suite_coroutine_lifetime.py -v
PYTHONPATH=tests python -m unittest test_full_suite_lifetime_guard test_full_suite_lifetime test_full_suite_atexit_lifetime -v
python -m py_compile tests/check_full_suite_lifetime.py tests/full_suite_lifetime_worker.py tests/test_full_suite_coroutine_lifetime.py
FULL_SUITE_LIFETIME_BUDGET_SECONDS=900 PYTHONASYNCIODEBUG=1 python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The existing Full suite lifetime workflow already matches the changed test paths; the canonical CI entry point and deadlines remain intact. Require actual final-source checks and clean process exit before merge. No independent reviewer or owner runtime/artwork acceptance is implied.

## Recovery PR boundaries

#1286 is already merged, with its earlier qualification correction recorded on the PR. #1285 and #1289 retain unreconciled full-suite evidence; #1285 also has a prepared-draft browser failure. #1288's refreshed five-workflow summary reports success, but its fetched Check studio log still names a wrapper blob different from the immutable published wrapper. A green summary is not a reconciliation of that discrepancy.

Both retained #1289 Linux/Windows native-browser ZIPs were rechecked in this retry against their advertised SHA-256 digests. Each report contains six completed scenarios, no JavaScript errors and no generation. Those reports do not replace current-head full-suite qualification. This patch changes none of those product branches and does not merge or certify them.
