# #671 registry writer: draft test and implementation handoff

**This PR is a regression checkpoint, not a shipped writer. Do not merge it.**

Parent: #676 at `2e798f50d3b067445e0be67467465f1f67281969`.
The branch retains the domain and filesystem tests; the complete locally tested
implementation is supplied in the conversation's `las-671-711-evidence.zip`.
GitHub's tool accepted the branch and test objects but repeatedly rejected upload
of `scripts/voice_profile_registry_io.py` with an indeterminate safety-status
message. The rejected module was not republished through another access method.

## Implemented and tested locally

- Version-2, catalogue-bound registry retaining complete commands and derived
  receipts in one atomic file; ordered transition validation reconstructs current
  profiles without a second mutable projection.
- Exact current-registry and current-profile CAS, increasing revisions, preserved
  predecessor chain, durable historical replay and changed request-ID refusal.
- OS-held cross-process lock, bounded no-link reads, flushed same-directory
  publication, pre-/post-replacement checks and explicit unconfirmed outcomes.
- Read-only inspect/receipt/resolution, legacy overlay compatibility without
  automatic migration, unchanged producer/acceptance admission.
- Explicit `inspect`, `update`, `receipt` CLI; no synthesis or model access.

Forty new test methods plus nine existing profile contracts pass on a sparse
exact-parent reconstruction (49 total). Actual spawned writers have one winner;
crash fixtures stop after flush or replacement and verify the retained boundary.
Red evidence includes absent implementation, wrong legacy diagnostic, late
acknowledgement drift and linked-registry resolver re-entry. Source compilation
also passes. These are local Linux checks, not Windows/full-repository evidence.

## Delivery state

The branch contains `tests/test_voice_profile_registry.py` and
`tests/test_voice_profile_registry_io.py`, not their implementation. Its new tests
are intentionally red until the remaining patch is applied. No all-green hosted
or independent-review claim is made; #671 stays open.

The bundle contains `671-complete.patch` against the parent and
`671-remaining-implementation.patch` for this checkpoint. Both have exact file
hash manifests. The latter adds the three writer/IO/CLI modules, the resolver
integration, CLI tests and `docs/spoken-briefs/REGISTRY-CAS.md`.

Before applying a handoff, recheck the branch and parent heads for concurrent
changes. Apply on this draft branch, then run the existing cross-platform Spoken
Brief workflow and full `Check studio` suite; inspect exact-head results before
making a readiness claim. Use the retained tests rather than reimplementing them.

The separate JSON integer error fix is PR #711. It is not required for this
checkpoint's tests and does not implement #671. #705 already owns #703 ordinary
resume persistence; the resource, discovery/export, recovery and figure stacks
were not duplicated.
