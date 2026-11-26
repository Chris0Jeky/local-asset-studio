# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: measuring
updated: 2026-11-26T23:33Z

## Items
- [x] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel. (commit 6fa8f3a)
- [x] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission. (commit f5216e1)
- [ ] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence.
- [ ] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update.
- [ ] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff.

## Next
The independently reviewed admission integration is implemented: 23 focused tests pass, including revocation during final file verification, input-file changes during the last authority capture, and malformed diagnostic strings. Run prove.py against a new .runtime directory; the first combined proof is running at .runtime/pro/P36-B-20261126-2/proof-1. Inspect its tests.log and deterministic evidence, reproduce in a second directory, then commit EVIDENCE.json and OUTPUT_HASHES.sha256. Complete README.md, VERIFICATION.md, ADOPTION.md and REPORT.md, add the import-plan update to existing Lumenfold issue #3175, and publish report copies to the requested Drive folder. The full repository unittest command already passed 7,321 tests with 62 skips. No native generation/import ran.

## Not pushed yet
- prototypes/pro/P36/P36-B-20261126-2/first_character.plan.json
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/FIRST_CHARACTER.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/SOURCES.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_CONTRACT.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_SOURCES.json
