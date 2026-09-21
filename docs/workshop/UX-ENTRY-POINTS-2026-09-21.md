# Create entry points — 21 September 2026

## Scope and provenance

This implements the first bounded slice of QA tracker #772, using the issue reports
rather than the owner's unmounted workstation screenshots. Source baseline is
`f22b56bbeee0ecd907aa71b22e4071cc0dde4dde`, tree
`2096e26aa02e9054eb1e1d3379fe27c44033937e`. The uploaded GitHub archive was
reconciled to that tree, including its Windows-script export line endings and the
intentionally retained CRLF test file. No runtime or user configuration was read.

## User stories and disposition

- **#771 / #776:** A creator sees `Choose recipe` when none is selected and
  `Change: <active recipe>` otherwise. The accessible name preserves the full name.
- **#767:** The existing native modal still owns focus containment and Escape.
  Its closed inner drawer now explicitly advertises `inert` / `aria-hidden=true`,
  and its trigger starts with `aria-expanded=false`. A deferred old close event
  cannot make a newly reopened picker inert.
- **#768:** Mobile users can enter Create directly beside Menu. Menu focuses its
  active route (or first route), Escape returns to Menu, and closed off-canvas
  navigation is inert. Resizing restores desktop navigation. The same code serves
  standalone tools, whose CSS breakpoint differs from the main Studio.
- **#769:** The skip link already existed on this baseline. Native keyboard tests
  verify that it is first and moves focus to the main landmark in both shells;
  this PR does not invent another skip link or claim the old one was missing.

All changes are presentation/navigation only. Existing recipe selection, draft
confirmation, source binding and Generate handlers retain ownership.

## Reproduction and validation

`python tests/workshop_entry_points.py` initially failed eight subcases across
five test methods: empty/active labels, initial disclosure state and mobile Create
entry. Existing native Escape/cancellation and skip-link tests passed before the
fix. All five methods now pass, with Focus/Studio/Immersive and both shell variants
covered by subtests. The driver uses exact production scripts and native Chromium
focus behavior over an explicitly synthetic DOM; it never submits a job.

Also run locally:

```console
python tests/workshop_browser.py --output .runtime/ux-daily-loop/component
python -m unittest discover -s tests -p test_workshop_frontend.py
python scripts/validate-repo.py
```

The existing Workshop UI workflow now includes the new keyboard driver alongside
its full-application HTTP/storage tests. Hosted results must be checked against
the current PR head; a component fixture is not a substitute for those results.

## Boundaries

Local Chromium refused loopback navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`.
That restriction was not bypassed. Local renderer-only results do not establish
HTTP, persisted-origin storage, model readiness, GPU execution, art quality or
owner acceptance. #539 stays open. HUMAN_TODO decisions remain unchanged.
