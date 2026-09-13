# Interrupted-session recovery — 13 September 2026

## Recovered work, not a second implementation

The retry inspected the live issue list, recent merges, open PR changed paths,
review discussions and tracked source. The interrupted work was already in
[PR #198](https://github.com/Chris0Jeky/local-asset-studio/pull/198), branch
`codex/chronological-recovery-followups`, at
`b56972e83e81da05ecbcfc5c51f0b7a478918c21`. A missing chat closeout was not proof
that those changes were lost. The quoted intermediate 1,412-test report was
not reused as verification of the current tree.

The retry integrates main `4ff057c84abb26664d066160580677361c857eb4` into the
existing PR and adds preservation tests. No competing worker, queue, recovery
service, issue or replacement PR was created. The temporary source acquisition
branch is not part of the delivery tree.

## Chronological disposition

| Issue | Current evidence and disposition |
| --- | --- |
| #2 | Explicit isolated backend switching, startup ownership interlocks and retained HiDream trials already exist. Higher-step same-seed and native/runtime acceptance remain; keep open. |
| #3 | Controlled quality experiments remain outcome work. Newer Krita mechanical revisions are not neural repair or finished character-pack acceptance; keep open. |
| #9 | Intake publication, unknown-role handling, graph validation and dependency readiness already exist. Exact source/bundle/hardware evidence remains; PR #203 independently covers loader-role guidance. Keep open and avoid overlap. |
| #10 | The existing Production coordinator, clock, reservations and submission records remain the execution owner. PR #186 merged and #93/#94 are closed. PR #198 supplies the scoped #95/#98/#110 fixes, not all accepted-export and multistage evidence. |
| #95 | PR #198 contains failure-handler containment, shared worker admission and exact-ID history handling. Its reviewed save-failure fallback keeps Production uncertain; two causal tests cover known and pending receipts. Ready for issue closure only through the complete PR. |
| #97 | Corrected checker and expanded CLI coverage already exist. Full per-backend installed-schema evidence remains; do not close from reduced fixtures. |
| #98 | PR #198 supplies common framing and MIME-sniffing response headers, real HTTP coverage and native-browser framing checks. Ready for closure with that PR. |
| #110 | PR #198 supplies evidence-only failed/partial reconciliation. This retry strengthens actual-file, Workspace and competing-command preservation coverage. Ready for closure with that PR. |
| #187 | Mixed known-ID/unknown-tail reconciliation remains separate. Its fail-closed guard is retained; no false terminal completion or replay is introduced here. |

The open guidance, setup-lineage, metadata/browser-driver and baseline-recipe
work was inspected for overlap. Their deliverables were not copied into this
recovery patch. Existing `HUMAN_TODO.md` decisions remain unchanged; no new
creative or licence approval is implied.

## Current recovery flow

1. Stop/resume of a known prompt stays in the existing job observation path.
   The exact prompt ID is retained, encoded only for the history URL, and never
   used as permission for another submission.
2. An observed negative terminal result with valid matching receipts enables
   **Reconcile outcome only**. GET/inspection does not mutate Production.
3. The explicit command records one local failed project disposition with
   `new_work_authorized: false`. A stale queued Production pass performs the
   same reconciliation before preflight, clock entry or later-stage creation.
4. The original job files, outputs, clock and reservations are retained.
   Failed/partial results require a separately authorized repair branch;
   unknown tails stay unknown. This action is neither remote cancellation nor
   a declaration that another backend is idle.

## Added regression evidence

Three tests in `tests/test_production_terminal.py` extend the existing fixtures:

- Failed-result reconciliation retains a real PNG, its content-addressed
  Workspace copy, SHA-256, decoded pixels, Workspace rows, retained job output
  identity, plan and reservations through reconciliation and restart.
- The same preservation contract holds for a partial result with an unsent
  tail. The test image is authored fixture data, not an inferred model output.
- Three explicit reconciliation calls compete with one stale queued pass,
  synchronized by a barrier. They obtain the same durable disposition without
  adding a job, queue item, prompt POST, clock charge or continuation consent.

The image fixture uses Studio's real output indexer, rather than an invented
Workspace attribute or an unindexed output record. Network replies and the
model runtime remain synthetic; SQLite, PNG decoding, file snapshots and the
concurrent request threads are real. Existing Studio worker starts are
suppressed in these fixtures, so no consumer or GPU work is accidentally added.

Causal check: the three added tests were copied to a separate checkout of main
`4ff057c` **without** PR #198. All three failed at the existing
`Resume observation of the retained prompt before authorizing later stages`
guard. On the integrated PR, all three pass; the complete terminal module has
13 passing cases. This isolates the already-implemented #110 behavior, not a
new production fix. Initial fixture-construction mistakes were corrected before
running this original-versus-candidate check and are not counted as product bugs.

The recovered production-code review had one P1 finding: an error saving an
uncertain job could cause the outer coordinator fallback to persist a failed
project. Source `b56972e` contains the correction and known/pending regression
cases. The subsequent review reported no major issues. This retry adds tests
and integration evidence; it does not represent a new independent review of
unchanged code.

## Browser evidence recovered

The nine head-specific workflows for `b56972e` passed. The storage workflow's
artifact `10322821398` was downloaded and checked against SHA-256
`ead1028eaa9bc604eb73db0bb836f335a4149bf3d4a83dfa993293c333539b27`.
Its result records zero page errors, keyboard reconciliation, same-origin and
cross-origin frame refusal, and only the explicit reconciliation POST. Both
1440px and 390px screenshots were inspected; the storage-warning message is
visible above the workspace, including the narrow layout.

These are recovered hosted checks of that earlier head, not a claim that a
local browser was run in the retry. Final-head hosted results belong in the PR
verification comment and are rechecked after publication.

## Reproduce

```sh
python -m unittest discover -s tests -p test_production_terminal.py -v
python -m unittest discover -s tests -p test_worker_recovery.py -v
python -m unittest discover -s tests -p test_http_security.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
node tests/production_terminal_frontend.cjs
node tests/frontend_health.cjs
git diff --check
```

The existing Production storage workflow runs the extended terminal module on
Linux and Windows; no extra queue or CI lane was added for these three tests.
GPU generations, downloads, workstation processes/configuration, native-tool
acceptance, model licensing and subjective artwork acceptance were not changed
or established by this retry.

## Local retry verification

| Check | Observed result |
| --- | --- |
| Recovered PR integrated with `4ff057c`, before new tests | 1,532 run, 1,517 passed, 15 skipped; exit 0 |
| Integrated PR plus the three preservation tests | 1,535 run, 1,520 passed, 15 skipped; exit 0 (101.578 seconds reported by unittest) |
| Complete terminal module | 13 passed |
| New tests against original main without #198 | 3 expected errors at the existing Resume guard; no patch applied to production source |
| Repository validator | 66 preset graphs/bindings, 121 pinned assets and 86 LoRA names; exit 0 |
| Shipped JavaScript handlers and syntax; whitespace check | Passed |

The full suite still emits fixture diagnostics and existing Pillow-deprecation
and unclosed-test-socket warnings; exit 0 is not described as warning-free.
Skipped optional/live checks are not treated as workstation evidence.
