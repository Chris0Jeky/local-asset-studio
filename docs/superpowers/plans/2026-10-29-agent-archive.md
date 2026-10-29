# Reviewed agent Archive implementation plan

**Goal:** Agents can preview, deliberately archive/unarchive, and recover the exact
receipt for explicit Library IDs, using the existing Workspace command owner.

**Architecture:** A bounded typed client observes an explicit selection once,
retains its scope and metadata revisions in a hash-bound review document, and
sends only the existing archive/unarchive command. Read/author MCP permissions
separate planning/recovery from writes. There is no second catalogue or journal.

**Tech stack:** Existing Python stdlib loopback transport, SQLite owner and MCP.

## Design and alternatives

Issue #123 needs usable organization tools, not just collection discovery. Direct
unreviewed generic metadata writes would broaden authority unnecessarily; a new
server mutation endpoint would duplicate the transactional owner. Use the existing
`/api/assets/update` and original receipt endpoint, restricted to Archive actions.
The caller must retain the review document before calling apply, and explicitly
approve its canonical SHA-256. Missing/hidden targets refuse the entire preview.
A stale revision refuses atomically. Uncertain replies never refresh revisions,
retry automatically or create a replacement request identity. Recover is one GET
and validates the returned receipt against the same retained plan; unknown never
means safe to resubmit. Historical receipts and bounded current metadata remain
separate. Archive is independent of privacy/Trash and never moves/deletes bytes.

This is the immediate organization slice, not completed-run privacy migration.
Physical migration needs a separately reviewed dependency inventory, verified
publication and durable rollback journal (#1678); it is not implied by this plan.
No UI/prototype redesign, owner runtime, GPU generation or human acceptance.

## Steps and review focus

- [x] Tests first: single observation, exact review/hash, missing/private targets,
  no-op and stale revisions, lost reply recovery/replay, response framing and
  malicious receipt identities; prove no automatic writes or media changes.
- [x] `studio_workflow/asset_archive_client.py`: typed preview/apply/recover and
  bounded CLI; validate prior to transport, retain unknown-outcome context.
- [x] Agent bridge: read-only preview/recover in all modes, author-only apply;
  explicit schemas, retained plan/request/scope and no hidden queue ownership.
- [ ] Actual SDK and stdio protocol tests on Linux/Windows, existing asset and
  workflow regressions, repository validation and exact-head hosted full suite.
- [ ] Usage guide, dated evidence and PR issue disposition; merge only after the
  relevant final-source gates pass. Do not close broader #123/#1678 acceptance.

Review specifically: archived timestamp zero, mixed privacy, off-page IDs, exact
request replay after a newer edit, current metadata limited to ten targets,
truncated/mismatched replies, oversized plans, invalid UTF-8/duplicate JSON keys,
and concurrent modification between preview and apply.

## Causal evidence before publication

The initial 11 client cases failed because the reviewed client was absent; five
bridge cases then failed because the tools were unavailable. After implementation,
15 client and five bridge cases pass. An adversarial receipt test reproduced a
false no-op acknowledgement; matching unchanged IDs to the retained lifecycle
corrected it. The actual composed handler also caught a wrong query-bearing POST
route during development: apply now uses the exact legacy path and explicit
privacy header, with a regression for Regular/Private/All. No server route or
authority was broadened to make tests pass.

The raw transport adds one optional validated privacy header; existing reads keep
the same behavior. Official SDK/stdio tests are committed for the dedicated
required-SDK platform gate; local optional skips must not be counted as passes.

Local broader regressions before publication: 469 workflow tests complete with
17 optional-SDK skips and no failures; all 238 asset tests pass. The validator
passes 94 graphs/bindings, 189 pinned assets and 164 LoRA names. These overlapping
groups are not additive. Final hosted protocol/full-suite qualification remains
pending until its exact-head evidence is recorded in the PR.
