# Workshop implementation plan

**Goal:** Replace the dense Create page with an actual switchable workshop, without changing generation authority.
**Architecture:** One presentation controller moves existing controls into focused surfaces. A small pure preference module defines layout/skin options. The workbench adapter exposes snapshots and target revelation without a second state owner.
**Stack:** Plain JavaScript, CSS, native dialog, Python unittest, Node contracts and Playwright Chromium. No application dependency or build step.
**Spec:** [DESIGN.md](DESIGN.md).

1. Capture the current app, inspect the existing shell/disclosure/shortlist owners, and record a baseline browser screenshot.
2. Write failing pure contracts for preference validation and storage failures; write browser assertions for node identity, modal focus, compact layout, mobile overflow and no implicit generation.
3. Implement Focus: compact header, native recipe modal, tuning/inspection surfaces, existing sources, persistent run dock, real readiness/ETA. Keep all original input/button IDs and event ownership.
4. Exercise edited prompt cancellation, accepted recipe switching, moved readiness targets, uploaded references, saved setup recovery and route changes. Fix only regressions introduced by this composition.
5. Publish PR 1 with exact verification commands and explicit local-GPU limitations.
6. Add Studio as a second selectable layout on PR 1. Add Arcade/Sakura as independent skins, local original assets and a self-contained interactive HTML prototype with clearly synthetic demo state.
7. Test every layout/skin at desktop and mobile; capture images and metric receipts; run repository tests/validator. Publish PR 2 with stack order and owner acceptance guide.

Manual comparison tasks: start a prompt; change recipe and cancel; change recipe and accept; find an adapter; attach a source; resolve an unavailable input; save a setup; inspect a recent run; switch presentation without losing any draft. Report completion and mistakes, not only time-to-click. No behavioural telemetry is collected automatically.
