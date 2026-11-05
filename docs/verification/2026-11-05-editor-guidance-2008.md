# Full editor guidance and Saved setups — #2008

Date: 5 November 2026. Local base: `8c37c1c` (tree reconciled with live main by the parent review).

## Changes

- Saved setups metadata is excluded from both delegated editor event handlers and the recipe-discard comparison. Naming a setup or choosing a rejected import preserves picture recovery and does not reschedule draft autosave. Applying a valid setup still uses its existing application owner.
- The original reference-recipe button sits beneath the active recipe name, outside Settings. Its wording confirmation remains owned by the workbench; an accepted switch focuses the actual picture input.
- The original `uxReadinessActionStatus` live region moves beside Generate. It remains a single polite status node, including in a short viewport while the dock's information panel is hidden. Empty status adds no layout space. Source recovery now reports its pending, successful, refused, failed and superseded outcomes there, without repeating those results through the adjacent run-status region or global notice.
- The editor's links and plan messages use the navigation lane's canonical **Comparisons** label.
- The obsolete workbench overwrite of the Comparisons heading is removed. The page HTML remains the heading owner, so the navigation lane's clear title survives normal app startup; that lane owns the rendered-heading browser assertion.
- The historical #1920 step-strip section in the UX use-case matrix now records its removal by #2006. Historical measurements are preserved; #1938 was superseded, not verified as a privacy fix, and #1920 still needs owner validation.

## Reproduction and local verification

The first seven new #2008 Node regressions were also run against the original `HEAD` workbench and workshop source via a temporary read-only source substitution. Five failed: Saved setup name events, import events, preservation of an existing real-edit debounce, the discard comparison, and focus after accepting the picture-recipe switch. The original-source run exited 1; no tracked source was replaced for this reproduction.

Final targeted command:

```sh
node --test tests/workbench_handoff_guards.cjs tests/workshop_contracts.cjs tests/frontend_health.cjs
```

Result: **69 passed, 0 failed, 0 skipped.** This includes sixteen new #2008 behavioral cases executing the real event handlers, discard comparison, link handler, source-recovery function and environment-switch repair. Existing health coverage retains the distinctions between pending, offline, unavailable and ready without submitting a job.

Independent review caught a duplicate source-repair announcement through the existing `announce()` → run-status path. Success and failure assertions reproduced that duplication (two targeted failures), then passed after the source-repair writer was restricted to its dedicated live region. The global announcement owners are unchanged; the full targeted 63-case command passed again.

Review also caught a retained hidden board input taking precedence over the new single-picture recipe's input. A new regression failed for that transition, then passed when focus selection followed the current recipe's `reference_slots` contract. Both single-picture and board targets are covered; the targeted total is now 65 passing cases. The existing browser driver additionally covers board → text-only → single-picture with the old board still mounted.

The same one-owner feedback check was applied to environment switching: its local repair writer now updates only the action-status region, while retaining the existing explicit Switch control and completion watcher. Success/refusal tests both failed on duplicated progress before that change and pass afterward. All other action-status writers were inspected; target navigation and connection checks already write only their dedicated region. Final targeted total: 67 passing cases.

Delayed source-repair success and failure tests reproduced a superseded operation overwriting a newer repair's identical progress text after a privacy change. Stale cancellation feedback now checks the existing picker owner as well as its text, without changing source attachment or busy-state ownership. Both delayed-operation cases pass, and a cancelled repair with no newer owner still reports its cancellation. Final targeted total: 69 passing cases.

Also passed:

```sh
node --check app/static/studio-workbench.js
node --check app/static/workshop.js
python -m py_compile tests/workshop_recipe_wording.py tests/create_readiness_browser.py
git diff --check
```

## Hosted browser verification

Browser evidence is **pending hosted CI**. Chromium is unavailable in this workspace; no local browser pass is claimed.

Existing CI-executed drivers were extended:

- `tests/workshop_recipe_wording.py` (Workshop UI): real Saved setups typing and rejected-file import preserve storage, avoid a discard confirmation, and retain a working Go back to the picture. The reference link remains visible with Settings closed at 1440px and 390px, and focuses the resulting picture input.
- `tests/create_readiness_browser.py` (Guided journey browser): successful and unavailable-target repair results stay visible with Settings closed, keep one polite live region, and retain timeout feedback in the 390 × 500 compact typing dock. The compact check also asserts the feedback rectangle is entirely within the viewport.

The parent review owns the full test suite, repository validation, PR publication and merge. #2008 is implemented locally; final disposition depends on that review and hosted browser results.
