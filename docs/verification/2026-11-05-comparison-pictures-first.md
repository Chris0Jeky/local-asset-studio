# Finished comparison pictures and review actions — #2009

## Scope and source evidence

This is the bounded follow-up to the navigation and review wording pass. The
local starting commit was `b007af1407bc008943a31784018c9eb0cd205eca`, with tree
`3880299d9455183fb659090bda5b04d0cdbfc746` matching published navigation head
`8a2750ff06139e12b4a7c1366e4d12eb7e33aa06`. The parent navigation test repair
`22e095d48b2bd81ea3f56a49d90eb5ec89dbed3a` was merged before this slice was
committed; it changes only the inherited smoke expectation and navigation note.

Issue #2009 identifies completed comparison ordering and overlapping review
actions as remaining problems. Hosted UX run `41947844271`, artifact
`13379357395` (`ux-use-case-evidence`), provides the before evidence:
`review-and-keep-winner/02.png` puts the candidate pictures near the bottom of
the 1536 × 1060 screenshot, below state prose, branch controls, stages, budget
and Library-mark explanations. Its case record reports that the candidate-open
and note controls required scrolling. This evidence predates this follow-up;
it is not an after screenshot or a visual pass for the new code.

## Changes and boundaries

- An awaiting or reviewed image comparison leads with a concise current outcome,
  one project-specific **Pick a winner** / **Open review desk** link, the blind
  toggle and its candidate pictures. The selected plan no longer duplicates
  that link in the list. Other awaiting plans keep their contextual list links.
- Secondary state prose, stages, time and generation accounting, Branch and
  Full plan move into **Plan & execution details** below the candidates. The
  disclosure retains its open state and keyboard focus through a same-plan
  refresh. Typed comparison notes retain their existing draft behavior.
- Runtime, time-accounting and tracking warnings stay visible. Only the two
  known routine completion messages can move into the fold; contact-sheet
  failures and any unfamiliar completion message remain escaped and visible.
- Planned, running, failed, uncertain and reconciliation states retain the
  execution controls and guidance before their saved pictures. Native, voice
  and scene decision/execution owners are unchanged.
- **Choose here** replaces Quick pick. Its button names the specific winner
  action. **Mark in Library** identifies the independent asset mark controls,
  and **Comparison notes** names the existing comparison note field. Endpoints,
  IDs, payloads, privacy rules and the Review desk ownership boundary stay the
  same. Preparing a desk review remains an explicit operation on that page.
- On the layout that stacks the plan list above its detail (1000px and below),
  explicitly selecting a finished image comparison focuses and scrolls to its
  heading. Polling and other rerenders do not repeat that handoff.
- The four active user guides now use the current navigation names and explain
  the picture-first layout and two distinct review actions. Historical QA
  evidence is unchanged.

Independent source review found a hidden contact-sheet-error path and an initial
850px/1000px breakpoint mismatch. Both were corrected and re-reviewed. The new
regression fixtures exercise the actual backend failure message and unfamiliar
escaped text; the viewport checks now include the intervening tablet width.

The coordinator's review also identified that a poll closed an open **Choose
here** disclosure and dropped summary focus before a winner was recorded. The
real-render Node harness reproduced that failure. Disclosure state and summary
focus now follow the asset within the same rendered plan, including if candidates
reorder. A plan switch or Review desk ownership removes that state naturally.
The focused winner button remains inside its open disclosure through refresh;
no choice or request is replayed. Node regressions cover each boundary, and the
browser helper checks summary/button focus and open/closed state at 390 × 500.

## Executed local verification

Passed for the implementation, with the later hosted-qualification follow-up recorded below:

- `node tests/review_frontend.cjs` — 41 tests. Covers the single contextual
  entry, picture/control ordering, visible exceptional messages, execution
  states, unchanged winner payload, refusal handling and separate Library owner.
- `node tests/production_typed_draft_frontend.cjs` — existing note, caret,
  refresh, filter and time-extension checks plus disclosure open/focus retention.
- `node tests/production_clock_frontend.cjs` and
  `node tests/production_terminal_frontend.cjs` — unchanged explicit action and
  reconciliation eligibility.
- `node tests/production_review_checks_frontend.cjs` — candidate check ownership.
- `node tests/production_native_open_frontend.cjs` and
  `node tests/production_put_away_frontend.cjs` — shared renderer and settled-plan
  action regression checks.
- `node tests/production_clarity_frontend.cjs` — existing planner clarity checks.
- `python -m unittest discover -s tests -p test_use_case_matrix.py` — 79 tests,
  one existing skip.
- `node --check app/static/production.js`, Python compilation of
  `tests/studio_use_cases.py`, and `git diff --check`.
- `python scripts/validate-repo.py` — 98 preset graphs/bindings, 194 pinned assets
  and 4881 tracked paths passed before adding this note.

## Hosted browser gate

The existing `review-and-keep-winner` driver reuses its image fixture and now
checks 1440 × 900, 900 × 700, 390 × 844 and 390 × 500. It requires the contextual
review link fully inside the viewport, useful visible image area (both pictures
on desktop/tablet, the first on phone), loaded image bytes, no horizontal
overflow, one project-specific review entry, and the selection focus handoff.
It captures `pictures-<width>x<height>.png` beside the existing case evidence.
The same helper opens/closes the secondary controls by keyboard, checks focus,
scroll and unsent-note retention through rerender, and refuses any production or
job write during those read-only interactions.

These browser assertions have not run locally: this environment has no usable
Chromium binary. Exact-head hosted browser results and their screenshots remain
the visual validation gate. The coordinator owns the full-suite and publishing
steps; this note makes no full-suite or visual-success claim.

### Hosted qualification and focused-heading correction

Published comparison head `3988095eddaf61937e23ce072ec4cee57daa6311` passed UX run
`41951702592`, job `126996913209`: 31/31 use cases, zero page errors, and the later
295 pose-handoff assertions. The artifact `13381890411` identifies that exact
head; its downloaded ZIP matches SHA-256
`f5d2eb54cee2bd4e28001fadf505d77a9452798b30ee41437507e25ff152ccb7`.

All four `pictures-<width>x<height>.png` captures were inspected. Desktop and
tablet show the review entry with both candidates. The 390 × 844 view shows the
first picture and its controls; the 390 × 500 view retains the entry and useful
first-picture area. Both phone captures also show a defect the geometry test had
missed: the focused plan heading starts underneath the wrapped, two-row global
bar. Those captures remain before evidence, not visual acceptance of this fix.

Explicit narrow-screen selection now measures the actual global-bar bottom and
leaves an 8px gap above the focused heading. The ready outcome is shorter because
the adjacent **Pick a winner** button already states the next action. Every
viewport now asserts that the full heading is inside the visible area below the
bar, alongside the existing review-link and picture thresholds. Polling still
does not scroll, and no request or decision handler changes. Final-head hosted
screenshots remain required to qualify this correction.

## Remaining acceptance

Refs #2009. This slice addresses completed-image ordering, the duplicated
selected-plan review link and the distinction between a comparison winner and a
Library mark. It does not unify the inline comparison decision with Review desk's
decision model, merge Workflow builder/guide, redesign the sidebar, or address
the issue's other Make, Voice, Models, label and compact-layout findings. The
broader issue and owner UX tour remain open; no creative choice or owner action
is closed by this implementation.
