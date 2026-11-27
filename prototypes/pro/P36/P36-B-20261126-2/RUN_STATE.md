# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: building
updated: 2026-11-27T00:38Z
tests: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --tests-only --output .runtime/pro/P36-B-20261126-2/owner-tests-1
evidence: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/owner-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
hashes: prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256

## Items
- [x] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel. (commit 6fa8f3a)
- [x] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission. (commit c465277)
- [x] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence. (commit a5e2e9f)
- [x] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update. (commit a5e2e9f)
- [x] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff. (commit 7d2848c)

- [x] 6. Correct actual Studio indexing provenance and prove it through the real indexer. (commit 87783e2)
- [ ] 7. Implement durable dispatch coordination with crash/restart/concurrency evidence.
- [ ] 8. Implement independent consumer integrity and current-authority verification. Complete: 32 focused tests pass; record this checkpoint SHA next.
- [ ] 9. Publish expanded evidence, adoption and reviewed continuation closeout.

## Next
Record this checkpoint SHA for item 8: independent handoff verifier, its 32 passing tests and API are now published, alongside the read-only Production intent factory and its 24 passing tests. Complete root's dispatch coordinator and publication/reconciliation tests. The latest changes freeze caller JSON, recheck authority after marker publication, require the acknowledged prompt, and pin exact observed job/workflow bytes while settling the ledger and journal in one transaction. Independent review reproduced three pre-fix defects and its six regressions pass. Run dispatch-reviewed.log, then publish coordinator sources/tests in a <=10-file checkpoint. Integrate deterministic consumer_evidence.py and production_evidence.py from specialist work, add dispatch evidence to prove.py, preserve historical evidence, and finish aggregate checks/adoption. All callbacks are offline simulations, no generation/native import.

## Not pushed yet
- prototypes/pro/P36/P36-B-20261126-2/attempt_ledger.py
- prototypes/pro/P36/P36-B-20261126-2/dispatch_coordinator.py
- prototypes/pro/P36/P36-B-20261126-2/dispatch_simulation.py
- prototypes/pro/P36/P36-B-20261126-2/dispatch_fixtures.py
- prototypes/pro/P36/P36-B-20261126-2/test_dispatch_coordinator.py
- prototypes/pro/P36/P36-B-20261126-2/test_dispatch_review.py
