# Run state
run: P36-B-20261126-2
lane: P36
part: B
base: 0270760a
phase: done
updated: 2026-11-26T23:51Z
tests: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --tests-only --output .runtime/pro/P36-B-20261126-2/owner-tests-1
evidence: py -3 prototypes/pro/P36/P36-B-20261126-2/prove.py --output .runtime/pro/P36-B-20261126-2/owner-proof-1 --check-evidence prototypes/pro/P36/P36-B-20261126-2/EVIDENCE.json --check-hashes prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256
hashes: prototypes/pro/P36/P36-B-20261126-2/OUTPUT_HASHES.sha256

## Items
- [x] 1. Audit Studio lifecycle and Lumenfold pack contracts; retain prior owned-source kernel. (commit 6fa8f3a)
- [x] 2. Implement current Workspace authority, semantic identity vetoes and durable attempt admission. (commit c465277)
- [x] 3. Implement conflict-safe Lumenfold export and adversarial reproducible evidence. (commit a5e2e9f)
- [x] 4. Publish first-character route plan, cross-repo adoption, and import-side issue update. (commit a5e2e9f)
- [x] 5. Complete proving checks, hashes, branch inventory, and ready-for-review handoff. (commit 7d2848c)

## Next
The owner or Studio agents should run the evidence command above from this branch in the existing Studio environment, using a new .runtime output path, and compare EVIDENCE.json plus all seven OUTPUT_HASHES.sha256 entries; optional --lumenfold-root accepts only the inspected validator/schema bytes. Then follow ADOPTION.md to move the exact accepted Sable A2 source/acceptance mapping from 0 to 1 without authorizing new generation. Studio agents own the planned worker admission/ledger seam; lf-characters-3d and lf-anime-look own the planned native staged import and appearance gates in Lumenfold issue #3175, with the published addendum at issuecomment-7205798489. VERIFICATION.md records 202 tests with no skips using the pinned consumer, a standalone repeat with only two optional skips and identical seven hashes, the 7,321-test repository suite with 62 skips, final repository validation, source/branch checks and all runtime limits. This run's software is implemented; real-character/native outputs remain planned, direct current-importer consumption is disallowed, and generation budget remains zero.

## Not pushed yet
- (none)
