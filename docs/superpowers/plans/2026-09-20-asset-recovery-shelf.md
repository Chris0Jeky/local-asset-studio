# Asset recovery shelf implementation plan

**Goal:** Extend the existing reload journal with explicit crash/closed-tab recovery.
**Architecture:** A bounded, typed codec plus lock-serialized local shelf; a narrow
journal checkpoint hook gates only existing metadata dispatches. Server ownership
and generation remain unchanged.
**Spec:** `docs/superpowers/specs/2026-09-20-asset-recovery-shelf-design.md`
**Execution:** Inline, regression-first, publishing draft PRs as requested.

## Tasks

- [x] Codec and shelf: add `app/static/asset-recovery-shelf.js` and Node contracts.
  Reject ambiguous JSON/schema/digests, enforce byte/count/depth/key budgets,
  compare expected record digests under the origin lock, verify readback, refuse
  duplicate request IDs and never evict. Prove failure first, then green.
- [x] Session integration: add explicit journal checkpoint hooks to
  `asset-recovery.js`; gate detail/library POSTs in `workspace.js` without gating
  GET-only receipt inspection. Test held persistence, failure, newer typing and
  navigation/Workspace races before dispatch. Existing disabled behavior stays.
- [x] UI: add a separate shelf controller and stylesheet, wire the production
  index, expose inspect-first import/export/restore/discard and per-tab opt-in.
  Reject session conflicts and foreign Workspace restoration without mutations.
- [ ] Native protocol proof: add a temporary SQLite browser driver and read-only
  CI. Exercise real localStorage/Web Locks, closed tab/reload, dropped reply,
  exact retry, two-tab CAS, storage denial and keyboard/narrow flows. Distinguish
  any inert local proof from native browser acceptance.
- [ ] Reconcile main and publish exact tested blobs/tree as a draft PR; record
  actual test results, self-review findings, limitations and remaining issues.

## Review focus

Preserve old command bytes when newer typing arrives. Refuse stale async dispatch
following navigation or Workspace replacement. Preserve evidence when quota fills.
Handle non-ASCII byte limits and duplicate escaped JSON keys. Treat a historical
receipt as a past result rather than proof of current asset lifecycle.

## Execution ledger

- The codec began with 11 failing contracts; all passed after implementation.
- The dispatch bridge began with eight failing contracts; all passed after the
  two existing POST owners gained the narrow optional checkpoint hook.
- The session bridge began with seven failing contracts; all passed.
- Review added three causal regressions: imported library operation extra fields,
  bounded lock acquisition and explicit cleanup after exhausted capacity. All
  failed before correction and pass afterward (29 Node contracts total).
- The first UI driver failed because the shelf had not been installed. Its
  completed inert HTTP/SQLite journey passes 18 checks. Native loopback Chromium
  reports ERR_BLOCKED_BY_ADMINISTRATOR locally; native CI must establish that
  separate guarantee. CSS 200% layout is labelled as CSS zoom, not browser zoom.
- An immutable clean-baseline worktree passed 3,289 tests with 20 skips and clean
  lifetime shutdown. An earlier concurrently modified baseline run was invalid
  as baseline evidence and is not used.
- The ZIP matches live main after reconciling archive CRLF policy: the original
  CRLF frontend fixture is preserved; baseline tree is exactly
  a0bfcfe0dd3b1ee276fc8422472b788edb6f8fe8.
- No independent reviewer is available in this environment; review is self-review.
