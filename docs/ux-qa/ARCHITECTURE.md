# An aware Studio: work-session and transition contracts

## Decision

Improve the actual handoffs between existing features. Do not introduce a new universal wizard, app store, queue, editor framework or autonomous assistant. An aware interface needs reliable context before it needs generated advice.

The unit of interaction is a **work session**: an identified asset or document, a user intent, a visible draft, an acknowledged baseline, and explicitly permitted operations. In this slice those are the existing `activeAsset`, native form controls, a transient field snapshot, a dialog epoch and an in-flight marker. Persisted authority remains `AssetWorkspace`. The epoch only rejects stale UI callbacks; it never authenticates a user, certifies source bytes or resolves concurrent server writes.

## State transitions implemented here

| Event | Behavior | Boundary |
|---|---|---|
| Open an existing asset | Populate once and start a new dialog epoch | No upload, generation or automatic diagnostic |
| Edit title/tags/review/notes | Compare draft with acknowledged baseline | Unsaved text stays local; no autosave claim |
| Favorite | Persist only the favorite bit; retain the entire form | Does not accept artwork or save notes |
| Save | Capture fields, serialize one mutation, retain dialog | Inputs stay editable; newer typing is not overwritten |
| Save confirmed | Advance baseline to the accepted snapshot | Do not rerender media or claim newer edits were saved |
| Save rejected/lost/timed out | Retain draft, expose unconfirmed outcome, release controls | Abort the request; never retry it automatically |
| Close/Escape/lineage with edits | Ask before discarding; cancel leaves the form intact | Save remains an explicit alternative |
| Leave while mutation pending | Hold departure and explain why | Avoid closing a different session after a late callback |
| Trash/restore | Obtain discard consent when needed, pause fields during write | Keep original files and recipes recoverable |
| Diagnostic completion | Apply only to the captured asset, epoch and newest request | Read-only failures are not generation failures |

The library's existing refresh owner remains independent. A slow refresh must not keep Save disabled after its write has already completed. Refreshing the library does not repopulate the open detail form. Closing or switching invalidates read callbacks, including a return to the same asset ID. There is no subscription, new interval or cache of reports in this change.

## Next integration: contextual task summary (design, not implemented)

Reuse the existing guide in #118/#169 and source-bound continuation instead of drawing another stepper. Project a small summary from their owned state:

```
Goal: repair the right hand
Source: selected asset + exact attachment/transform evidence
Preserve: identity, costume, composition; source remains unchanged
Change: hand region through the chosen supported control
Ready: required references observed / missing / unknown
Next: stage source → inspect settings → explicitly Generate → compare
Side effects: one proposed candidate; no install or backend switch implied
```

Each fact must include its owner and freshness. A named source is not proof its file is still available. A ready graph is not proof of memory fit or output quality. A successful job is not a reviewed or licensed asset. A missing observation is `unknown`, not `false`, `complete` or zero. Alternatives explain which requirement they cannot preserve instead of silently substituting a recipe.

Use the existing intent/continuation records for goal, source and constraints; Workspace for metadata and lineage; Production for attempts/budgets; graph/bundle owners for capability evidence; the guide for presentation. Read projections can be composed at the UI boundary, but only an owning service changes its state. Do not copy them into an authoritative browser JSON project.

A generic transition proposal can carry `from`, `to`, `source identities`, `preserved fields`, `changed fields`, `invalidated evidence`, `required observations`, `side effects`, and `return target`. These are proposed fields for shared adapters, not a new persisted schema in this PR. Every adapter must bind to real current controls. Unsupported or lossy transitions stay explicit.

## Dependency order and acceptance

1. **Protect information.** Deliver metadata expected-revision checks under #188 and the pending-reference save fix under #117. Add real two-client and lost-response tests before claiming human/agent parity. Browser reload/crash drafts need a separate persistence decision; this patch protects an open session only.
2. **Explain the next action from evidence.** Integrate #169 and #171, then test a known output → specific repair → settings review journey. Prompt assistance remains opt-in and proposed; it cannot invent observations, quietly change locked traits or launch a job.
3. **Join execution and review.** Reuse Production reconciliation and #122's execution boundary. Show observing, stopped, uncertain, failed and completed accurately. A failed retrieval never grants permission to retry generation. Compare source/candidate at final-size detail, preserve failures, and record owner review separately.
4. **Extend modality-specific paths.** An image repair needs source/mask semantics; a shot needs anchors/timebase and decode capacity; voice needs exact words and line identity; scene editing needs timeline revision and stale-preview state. Share transition vocabulary, not misleading universal controls.
5. **Measure the complete journey.** Track preserved user edits, stale-result rejection, unexpected mutation count, recovery steps and time-to-next-action. After separately authorized real runs, measure accepted-output effort including rejects and manual cleanup. Click counts alone are insufficient.

## Known limitations and rejected shortcuts

An epoch cannot stop two clients overwriting persisted notes; use transactional expected revisions. Disabling Save alone does not protect newer edits; preserve the submitted snapshot. Comparing only asset IDs does not handle A→B→A; include a session identity. A toast behind a modal is not adequate recovery feedback. An aborted POST may have committed on the server; say unconfirmed and add request-identity reconciliation under #188. A browser width of 720px is not proof of actual 200% zoom. CSS preview bounds do not establish media-decode, accessibility conformance or memory benefits.

No persistent asset-draft store, multi-tab synchronization, refresh/unload interception, global retry engine or general editor replacement is introduced. Native confirm is a deliberate small-scope choice; a future nonblocking discard dialog must retain equivalent keyboard/focus behavior and cannot become another parallel state machine.

## Primary interaction references

Reviewed 13 September 2026: [W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) supports reporting progress/results without moving focus. [W3C modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) informs keyboard and focus expectations. [Playwright network testing](https://playwright.dev/python/docs/network) distinguishes controlled test responses from service behavior. These inform the design; none is evidence that this implementation meets all accessibility criteria or that a mocked backend is production-tested.
