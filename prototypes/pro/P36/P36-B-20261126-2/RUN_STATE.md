# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: building
updated: 2026-11-26T23:23Z

## Items
- [x] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel. (commit 6fa8f3a)
- [ ] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission.
- [ ] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence.
- [ ] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update.
- [ ] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff.

## Next
Workspace authority (30 tests) and durable attempt admission (22 tests) now include independent-review corrections. Semantic vetoes (26 tests) and guarded export (12 tests) are implemented; retained prior kernel contributes 84 tests. Integrate admission.py and its real-Workspace staging tests next; the worker must retain the new p36_attempt nonce/source/intent marker before submission, and native queue wiring remains planned. Full repository unittest discovery passed 7,321 tests in 615.292 seconds, with 62 skips; app and catalog remain unchanged. Current prototype checkpoint suite is running under .runtime/pro/P36-B-20261126-2/prototype-checkpoint.log. Then author prove.py, deterministic evidence, report and ADOPTION.md, update Lumenfold issue #3175, and verify the entire published inventory.

## Not pushed yet
- prototypes/pro/P36/P36-B-20261126-2/first_character.plan.json
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/FIRST_CHARACTER.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/SOURCES.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_CONTRACT.md
- docs/programmes/systems/research/pro/P36/P36-B-20261126-2/LUMENFOLD_SOURCES.json
