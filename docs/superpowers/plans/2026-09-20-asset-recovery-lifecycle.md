# Recovery lifecycle inspection implementation record

**Goal:** Make retained recovery inspectable after asset/collection lifecycle drift.
**Spec:** `docs/superpowers/specs/2026-09-20-asset-recovery-lifecycle-design.md`
**Architecture:** Existing Workspace read transaction + bounded GET extension +
read-only lens inside the existing shelf dialog. No new store or mutation owner.
**Execution:** Inline under the user's explicit request to continue and publish PRs.

## Completed local steps

- [x] Reconcile live main, #684 collection recovery and #698 shelf. The interrupted
  lifecycle branch had no unique commit. Reconstruct only the relevant source.
- [x] Recover SQLite/HTTP projection after ten tests fail for missing implementation.
- [x] Add 200-target, concurrent snapshot, malformed timestamp and actual wire-byte
  tests. Two tests exposed four failures; fix refusal and ASCII-encoded accounting.
- [x] Recover read-only lens after its positive contracts fail without the module.
  Fourteen Node contracts pass with strict identities and epoch-based response guards.
- [x] Add actual-shell browser test; missing installation fails LIFE-01. Wire the
  shipped script, buttons and wrapping CSS. Use the production handler extension
  chain in the fixture, rather than the unextended base Handler.
- [x] Run 19 inert browser checks, 14 SQLite/HTTP tests, 14 lens contracts, 14 existing
  reload contracts, 17 editor contracts and the repository validator successfully.
- [x] Attempt native local Chromium once; navigation is blocked by
  ERR_BLOCKED_BY_ADMINISTRATOR. No policy bypass or native-proof claim is made.
- [x] Add native Ubuntu/Windows exact-head CI and operator/architecture documentation.

## Publication and review gates

- Publish as a draft child of #698 with byte-checked changed-file objects.
- Read exact-head native/full-suite CI before recording its result on the PR.
- Leave #393 open with its broader editor/focus/real-browser-zoom acceptance explicit.

## Review findings and decisions

The recovery resume also reproduced a separate shelf form-key-order defect. Its
five round-trip tests and boundary correction were published on #698 in
`c323f58a293b1fcab8c97f075216f15af6a20979`; do not duplicate it in this child diff.
The shelf correction passed all ten workflows before this child publication.

Ruling: reuse the existing receipt validator rather than invent another receipt
schema or treat asset equality as commit evidence. Retained command bytes remain
untouched. Ruling: don't infer an unobserved Trash/restore history from a revision
number. Ruling: retain current membership as an observation, not a reconstructed
historical membership list. No independent reviewer is available in this session;
reported review is self-review and causal tests, not an independent approval.
