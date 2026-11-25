# Run state
run: P36-B-20261125-1
lane: P36
part: B
base: 0270760a
phase: done
updated: 2026-11-25T02:37Z
tests: py -3 prototypes/pro/P36/P36-B-20261125-1/prove.py --tests-only
evidence: py -3 prototypes/pro/P36/P36-B-20261125-1/prove.py --output .runtime/pro/P36-B-20261125-1/reproduce --check-evidence prototypes/pro/P36/P36-B-20261125-1/EVIDENCE.json --repetitions 100 --lumenfold-root ../lumenfold
hashes: prototypes/pro/P36/P36-B-20261125-1/OUTPUT_HASHES.sha256

## Items
- [x] 1. Inspect Studio asset-family and Lumenfold pack contracts; define identity kill gates. (commit 2cfd0ce)
- [x] 2. Implement linked family receipts, conservative sheet scoring and gated export. (commit 3a05f88)
- [x] 3. Reproduce adversarial evidence and validate pack compatibility. (commit 1271fc4)
- [x] 4. Publish first-character plan, cross-repo adoption and Lumenfold import issue. (commit fad3f12)
- [x] 5. Verify branch payload and publish final evidence for ready-for-review. (commit fad3f12)

## Next
The offline P36 run is complete. Finish the ready-for-review transition on Studio PR #2046 after this checkpoint; do not merge. Studio agents run the evidence command with a fresh output directory and their existing Lumenfold path, then follow ADOPTION.md to move P36's exact Sable A2 source/acceptance mappings from 0 to 1. Resolve current Workspace authority and uncertain jobs before live admission. lf-characters-3d and lf-anime-look adopt or decline Lumenfold issue #3175 and separately prove native import/playback after the accepted handoff; eight prototype receipts are not playable acceptance. All 20 run/report files and README links were verified on branch, both hosted source checks passed, and final local proof passed 84 tests with exact output hashes. Later publication CI is a separate check. The report copy is verified in Drive Lumenfold/pro/P36-B-20261125-1/.

## Not pushed yet
- (none)
