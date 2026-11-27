# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: publishing
updated: 2026-11-27T00:56Z
tests: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --tests-only --output .runtime/pro/P36-B-20261126-2/owner-continuation-tests-1
evidence: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/owner-continuation-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
hashes: prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256

## Items
- [x] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel. (commit 6fa8f3a)
- [x] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission. (commit c465277)
- [x] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence. (commit a5e2e9f)
- [x] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update. (commit a5e2e9f)
- [x] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff. (commit 7d2848c)

- [x] 6. Correct actual Studio indexing provenance and prove it through the real indexer. (commit 87783e2)
- [x] 7. Implement durable dispatch coordination with crash/restart/concurrency evidence. (commit ccf9ced)
- [x] 8. Implement independent consumer integrity and current-authority verification. (commit 9ad9db5)
- [ ] 9. Publish expanded evidence, adoption and reviewed continuation closeout.

## Next
Both expanded proofs pass: 303 tests (0 skips with pinned Lumenfold validator, 2 optional skips standalone), all eleven deterministic hashes identical. The full repository suite passes 7,321 tests/62 skips/605.399 s; validate-repo.py passes 4,992 tracked paths, 98 graphs, 194 pins. All 4,930 fixed-base blobs match; local inventory has 62 text files and no broken relative Markdown links. Publish VERIFICATION.md and CONTINUATION_REPORT.md, then add the report-only Drive copy and a continuation adoption comment to existing Lumenfold issue #3175. Read the resulting GitHub tree and compare every changed path/blob with the local allowed-directory inventory, verify README targets, update PR body with issue disposition and limits, commit phase done with final headers, then mark PR #2049 ready. No main/other-branch push or merge; real generation/native qualification remains planned.

## Not pushed yet
- prototypes/pro/P36/P36-B-20261126-2/VERIFICATION.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/CONTINUATION_REPORT.md
