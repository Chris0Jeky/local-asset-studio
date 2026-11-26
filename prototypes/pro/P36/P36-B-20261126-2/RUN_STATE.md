# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: building
updated: 2026-11-26T23:07Z

## Items
- [ ] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel.
- [ ] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission.
- [ ] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence.
- [ ] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update.
- [ ] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff.

## Next
Read DESIGN.md and UPSTREAM.json. Previous P36 PR #2046 is open/unmerged; the retained kernel here is byte-identical to head 80b274e. Implement studio_authority.py against the pinned app/workspace.py schema, plus attempt_ledger.py. Integrate the semantic scorer and guarded exporter from isolated subagent workspaces. Keep all new code in this run directory. Prior regression tests are prepared locally and will be pushed in the next batch. Linux full-suite discovery is running; inspect .runtime/pro/P36-B-20261126-2/full-suite.log before claiming any result.

## Not pushed yet
- prototypes/pro/P36/P36-B-20261126-2/test_pipeline.py
- prototypes/pro/P36/P36-B-20261126-2/test_consistency.py
- prototypes/pro/P36/P36-B-20261126-2/test_export.py
- prototypes/pro/P36/P36-B-20261126-2/test_review_regressions.py

