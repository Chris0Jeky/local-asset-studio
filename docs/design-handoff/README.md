# Design handoff for Claude Design

A self-contained package that lets **Claude Design** (the AI design tool that produces UI designs and prototypes from
a written brief and references) redesign the Local Asset Studio frontend. Written 27 September 2026 against `main`
`8a41edaa`. It describes the shipped UI from the code, not from older docs; proposals are labelled **Proposal**.
Refs #278 (owner UX verdict), #772 (UX QA tracker), #907 (Vue island, owner option B).

## Contents

| File | Use it for |
| --- | --- |
| [01-PRODUCT-BRIEF.md](01-PRODUCT-BRIEF.md) | What the Studio is, who uses it, jobs to be done, principles, targets, non-goals |
| [02-INFORMATION-ARCHITECTURE.md](02-INFORMATION-ARCHITECTURE.md) | Current sitemap and label drift, object model, proposed five-place IA and vocabulary |
| [03-SCREEN-INVENTORY.md](03-SCREEN-INVENTORY.md) | Every current screen with regions, states, screenshot and observed problems |
| [04-USER-JOURNEYS.md](04-USER-JOURNEYS.md) | 14 journeys (+4 secondary): current steps, desired steps, success criteria |
| [05-COMPONENTS-AND-STATES.md](05-COMPONENTS-AND-STATES.md) | Job/plan/environment states, disabled-with-reason catalogue, 45 components, disclosure, keyboard |
| [06-VISUAL-DIRECTION.md](06-VISUAL-DIRECTION.md) | Tone, the six skins, tokens to define, accessibility |
| [07-CONSTRAINTS.md](07-CONSTRAINTS.md) | Technical and truthfulness constraints (K1-K22) a design must respect |
| [08-DESIGN-REQUESTS.md](08-DESIGN-REQUESTS.md) | 17 prioritised deliverables (D0-D16) with acceptance criteria |
| [09-PROMPTS.md](09-PROMPTS.md) | Project context block + one paste-ready prompt per deliverable, with the screenshots to attach |
| [10-OPEN-QUESTIONS.md](10-OPEN-QUESTIONS.md) | 15 owner decisions, each with a default the design can assume |
| [screenshots/](screenshots/) | 42 JPEGs of the current UI (39 fixture, 3 live read-only with images hidden) |

## How to run it in Claude Design

1. **Create one Claude Design project** for the Studio. Paste the *Project context* block from `09-PROMPTS.md`, and
   attach `01-PRODUCT-BRIEF.md`, `06-VISUAL-DIRECTION.md` and `07-CONSTRAINTS.md` as reference files. Attach
   `05-COMPONENTS-AND-STATES.md` from D2 onwards.
2. **Ask for D0 (design system) first**, then **D1 (shell)**. Review both before anything else: every later screen
   inherits them. Check the contrast table and the disabled-with-reason pattern specifically.
3. **Then the P0 screens in order: D2 Make, D3 Library + Review mode, D4 Runs.** One prompt per session; attach the
   screenshots listed under each prompt so the tool sees what exists today.
4. **Iterate with the acceptance criteria** in `08-DESIGN-REQUESTS.md`. For each output ask: are all listed states
   drawn? Is every disabled control explained? Does 1440×900 show what the criterion says without scrolling? Is the
   390×844 frame present? Is anything auto-running, or an uncertain job offered a Retry? Send the failures back as
   a numbered list in the same session.
5. **P1 (D5-D9)** after P0 is accepted, **P2/P3** as time allows. D14 (skins) comes last because it depends on
   every screen existing.
6. **Export** each accepted design as HTML/CSS (static, no CDN or web fonts) plus a component/state list. Save
   exports under `docs/design-handoff/outputs/<Dnn>/` in a PR so an implementation session can build from them.

Suggested first message after the context block: *"Start with D0. Before designing, list any conflicts you see
between the brief, the constraints and the visual direction."*

## Iteration plan

| Round | Ask for | Owner checks | Exit |
| --- | --- | --- | --- |
| 1 | D0, D1 | Feel, palette, readability, shell | Owner picks direction (maybe 2-3 variants of D0) |
| 2 | D2, D3, D4 | The daily loop: brief → result → review → runs | Owner can "walk" J1, J3, J7, J10 in the prototype |
| 3 | D5-D9 | Compare, recipe choice, Combine, handoffs, error states | J4, J8, J9 walkable |
| 4 | D10-D16 | Secondary pages, skins | Consistency pass |
| 5 | Implementation | Vue island per #907: first island D6 (recipe discovery) unless Q15 says otherwise | Measured against `tests/studio_use_cases.py` and the owner's first-hand pass (HUMAN_TODO q-7) |

## Evidence and limits

- Inventory sources: `app/static/*` and `app/server.py` on `main` 8a41edaa (three read-only code sweeps, spot-checked),
  the fixture harness `tests/studio_use_cases.py`, the live Studio (navigation only; no clicks that submit, switch,
  delete or edit), `docs/UX-AUDIT-2026-09-14.md`, `docs/UX-USE-CASE-MATRIX.md`, `docs/ux-qa/`,
  `docs/adaptive-studio/`, `docs/workshop/`, issues #278 #772 #539 #16 #907 #940 #422, `HUMAN_TODO.md`.
- Fixture screenshots use synthetic data and repository example pictures; running/uncertain job cards were injected
  into fixture data. They show layout and states, not real timings.
- Not captured: the open Review desk (needs a write), the Combine workbench and pose editor, bundle explorer, live
  Library/Runs (card text contains agent-lab prompts), the NSFW lab page (excluded).
- Nothing here is owner acceptance of a design. The owner's verdict on any redesign is recorded separately
  (HUMAN_TODO q-7).

To re-capture after a redesign, drive the same fixture: `build_handler()` in `tests/studio_use_cases.py` serves the
real frontend with synthetic data and blocks every mutation.
