# Reviewed setup proposals implementation plan

**Goal:** Show one complete, source-bound proposed setup beside the captured Create draft, without applying or staging it.

**Architecture:** Extend #258's shared observation service. A stateless proposal binds the caller's full browser-draft declaration, explicit wording/contributions, ordered Workspace sources and exact target graph. UI and read-only agents consume the same report. Reference transform and wording projections share the existing compiler's pure helpers. No new persistence or executor.

**Tech stack:** Existing Python/stdlib HTTP, Pillow reference inspection, plain JavaScript and native browser dialog. Existing official-MCP and browser CI lanes.

**Spec:** `docs/workflow-studio/SETUP-PROPOSALS.md` (usage/contract and residual #232 acceptance).

## Constraints

Keep owner configuration/runtime/media unchanged. Do not stage, apply, approve or generate. A caller's draft hash is not a server revision, authentication or a lease on its source files. Preserve the existing reference compiler and Generate owner. Keep #232 open for staging/apply/recovery/persisted undo.

## Delivery sequence

- [x] Shared service: add failing source/graph/draft/wording/diff tests under `test_recipe_shortlist_proposal.py`; implement strict bounded request validation, exact source recapture, target-scoped existing prerequisite projection, full diff and canonical response identity. Extract pure reference helpers, proving agreement with actual compilation. Reject unsupported slot/role/mask combinations rather than omit them.
- [x] Shared clients: add HTTP/SDK/CLI/read-MCP agreement, malformed/tampered response and bounded-file tests. Keep the existing loopback/framing transport. No response or request JSON is executable code.
- [x] UI: expose a copied normalized draft from its current workbench owner, add a Preview button on source-bound suggestions, and a modal with explicit wording/contributions, settings/source/lineage diff and current-state guards. Every edit invalidates; late or reordered replies never restore evidence. No Apply control until #232's mutation owner is implemented.
- [ ] QA: extend the existing native browser driver, preserve zero mutation assertions, keyboard/mobile/zoom checks, actual selected files and stale-response scenarios. Run the full suite and validator. Publish an exact tested tree against main after #258 integration, obtain automated review, inspect final hosted artifacts and update issues with remaining acceptance.

Initial source: #258 head `c4074ca05eec7898ee36938f5cc8e766647e032d`, tree `cb58a2b89cacfb4bc238464ec84094e48cc2c1fe`. #237 is merged; #258 is retargeted to main but still open at initial inspection. Concurrent runtime/Generate fixes in #262 are not overwritten.

Integrated newer main `ff6c0f494ba3f8f74e7fd4af10cdbfd0fec186d9` after #258 merged, without feature patch conflicts. Hosted evidence and PR closeout are recorded separately when actually run.
