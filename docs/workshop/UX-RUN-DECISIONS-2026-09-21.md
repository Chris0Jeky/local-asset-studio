# Reachable run decisions — 21 September 2026

Child of the entry-point pass (#790), from tracker #772.

## Changes and issue boundaries

- **#778 / #779:** The existing Plan comparison and New seed buttons move into the
  persistent run dock. Their identities and handlers are retained. Planning does
  not submit a job; choosing a seed does not replace the prompt. A recipe without
  a bound seed control hides the otherwise dead New seed action.
- **#775:** There was already one fixed Generate dock with readiness and ETA.
  This pass retains that owner and adds regression coverage at 1440×900,
  1280×720, 640×360, 390×844 and 320×568, with long errors and blockers. It does
  not add another dock or infer readiness from appearance.
- **#770:** The top-level recipe picker stays unique. The authored variations
  selector is labelled Recipe variants, not a second undifferentiated Recipes
  picker. It remains under Fine-tune because it changes the authored control set.
- **Additional mobile defect:** The two appearance selectors had 145px minimums
  that forced a 300px grid into a narrower content box. The corrective entrypoint
  now uses shrinkable tracks and controls at compact widths.

The desktop dock puts secondary tools inline rather than adding vertical bulk.
Compact layouts use a separate wrapping secondary row. Existing reserved space,
Generate disabling, status ownership and readiness resolution are unchanged.

## Evidence

`python tests/workshop_run_decisions.py` reproduces hidden seed/comparison actions
before implementation, then passes all 8 methods (including the inherited
entry-point regressions). Tests cover all three presentations and five viewport
sizes, original node/event-handler retention, unchanged wording, disabled Generate,
visible ETA, no job submission, and the no-seed case. Native renderer fixtures are
synthetic, not owner/runtime acceptance.

The existing `workshop_browser.py` component/geometry matrix also passes. Its
1700px desktop height budget is unchanged: the dock is compacted rather than
weakening the regression. The new driver runs in Workshop UI next to the existing
real HTTP/storage application suite; exact-head hosted results belong in the PR.

#539 and all HUMAN_TODO acceptance decisions remain open. No models, environments,
provider requests, actual generation, user data, or execution policy are changed.
