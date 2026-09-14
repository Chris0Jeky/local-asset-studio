# Chronological continuation: backend schema evidence

The 22:12 UTC GitHub/source snapshot at
`28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3` showed no open PRs and 49 open issues.
The earliest workstreams remain #2, #3, #9 and #10. Existing switching, model
intake, readiness, shared coordination and recovery were inspected instead of
reimplemented. #198 and #224 are merged, and their scoped recovery issues are
closed. Higher-step HiDream acceptance (#2), controlled creative/native outcomes
(#3), full source/bundle/runtime evidence (#9) and accepted multistage exports
(#10) still need their own evidence.

This PR advances #9 through #97. The original schema false-rejection and default
coverage defects already have #156's implementation. The owner's later primary
installed-schema check passed 59/60 graphs; absent AniFox and six unobserved
HiDream/H3 graphs keep #97 open. This session has no access to those installed
schemas and does not fabricate a corpus or mark them passed.

The existing validator now has an explicit, non-executing capture/replay path:
select every graph for one declared backend, make one bounded schema GET, retain
exact response bytes plus catalog/graph identities and every failure, then
rerun the same checker offline. Exclusive publication preserves existing and
concurrently created evidence. Stale or inconsistent capture bindings are not
reported as current passes. See [the complete runbook](../GRAPH-SCHEMA-CAPTURES.md).

The change is confined to the validator, synthetic capture tests, its existing
Linux/Windows CI lane and these guides. It adds no backend manager, queue,
application endpoint, installed dependency or second graph validator. The
parallel #10 ownership fix is independent and uses a separate PR.

Initial feature proof: 11 expected failing methods in the 17-case pre-change
suite. After implementation and adversarial extensions, all 22 new cases and
all 15 existing CLI cases pass. The original full repository baseline ran 1,674
tests (16 skipped) successfully. Final tree-specific results are in the PR;
optional/native skipped tests are not execution evidence.

No model download, workstation switch/restart, GPU job, schema upload or human
choice was performed. Keep captures outside Git. Existing q-1 through q-4
choices are answered; finished-art acceptance and the remaining installed
backend checks are not supplied by this software pass.
