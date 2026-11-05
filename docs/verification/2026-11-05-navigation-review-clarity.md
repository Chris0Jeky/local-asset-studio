# Navigation and comparison review clarity — #2009

## Scope and source evidence

This is a bounded navigation and wording pass. At baseline `8c37c1c`,
`studio-shell.js` put Full editor and Compare & review inside the collapsed
Advanced group. Review desk had no navigation or finder entry. The finder did
not index `switch`, `history` or `winner`. In `production.js`, a plan's `Review`
link opened `/review.html?project=<id>`, while Library's `Review next` began a
different asset queue. The production purpose and starting points were inside
the closed `productionIntro` disclosure.

## Changes

- Full editor, Comparisons and Review desk are visible in the primary navigation
  without opening Advanced. Their existing URLs are preserved.
- The finder sends `switch` to Models & setup, `history` and `workspace` to
  Library, and `winner`, `pick a winner` and `review` first to Review desk.
- An awaiting comparison's contextual link is named **Pick a winner**. It still
  carries that comparison's exact project ID and remains absent without a saved
  candidate. Completed decisions retain **Open review desk**.
- The comparison page visibly explains its purpose, explicit Start step and
  Review desk handoff. The disclosure contains status definitions only.
- Review desk's empty state explains how to choose a finished comparison. Its
  global navigation entry deliberately carries no arbitrary project ID.
- Visible references in the workflow guide state, character import, bundle
  explorer and Spoken Briefs use Comparisons too. Reserved workshop/workbench
  references are aligned by the companion editor change.

## Routing and side-effect review

The global Review desk entry is `/review.html`; a plan's Pick a winner entry is
`/review.html?project=<existing-id>`. Library stays `/#assets` and retains its
independent Review next action. No route, API request, privacy scope, generation
control, review ownership or stored handoff changes. Quick pick still submits
the existing comparison review command, while candidate Keep/Needs work marks
remain Library metadata. Render tests verify the project ID, single primary
review entry, no request during rendering and unchanged inline-pick payload.

## Local verification

Passed:

- `node tests/studio_ux.cjs` — 62 checks, including actual sidebar rendering and
  finder results for the navigation intents.
- `node tests/review_frontend.cjs` — 35 checks, including contextual routing,
  saved candidates, unchanged inline decisions and refused decisions.
- `node tests/production_clarity_frontend.cjs` — purpose outside the disclosure,
  empty state, planner labels and comparison arithmetic.
- `node tests/frontend_handoffs.cjs` — existing generation and lineage handoffs.
- `node tests/production_review_checks_frontend.cjs` — saved candidate checks.
- `node tests/production_terminal_frontend.cjs` — terminal controls and explicit
  action eligibility.
- `node tests/studio_guide_state.cjs` — 26 guide state and route checks.
- `node tests/character_import_frontend.cjs` — unchanged explicit import and
  duplicate-submission controls.
- `node tests/bundle_guidance_client.cjs` — 9 guidance ownership checks.
- `python -m unittest discover -s tests -p test_spoken_brief_frontend.py` — 2 checks.
- `python -m unittest discover -s tests -p test_ui_place_names.py` — 3 checks.
- `node --check` for the modified JavaScript files, Python compilation of the
  browser driver, and `git diff --check`.

The existing `tests/studio_use_cases.py` drivers now check direct visibility of
the three destinations, finder aliases, Escape focus restoration, the persistent
comparison purpose, visible candidate images and the plan-specific review URL.
They run through the existing desktop/narrow viewport harness. Browser execution
is pending hosted exact-head CI: this environment has no usable Chromium binary.
The Spoken Briefs browser driver expects the updated navigation label too. No
visual pass is claimed.

## Remaining #2009 work

This pass does not merge Workflow builder and Workflow guide, redesign the whole
sidebar, unify Quick pick with Review desk's decision model, or restructure all
production controls around the pictures. Candidate pictures already render
outside a disclosure; the new browser assertion protects that behavior, but
above-the-fold visual ordering still needs browser assessment. Broader #2009
acceptance remains open.
