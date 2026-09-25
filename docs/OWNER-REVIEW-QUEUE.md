# Owner review queue: things to glance at, not blockers

Agents record the choices they made for you here: defaults, copy and wording, layout moves, small behaviours. Nothing
in this file blocks work. Real decisions and approvals stay in [HUMAN_TODO.md](../HUMAN_TODO.md).

How to answer, when convenient:
- **Fine** — put `ok` in the *Your call* column, or just say "queue: ok 1–6" in a session.
- **Change it** — write what you want instead. An agent turns it into an issue or a fix.

Agents add a row when they make a choice like this, and never fill in *Your call* themselves. Agents never tick HUMAN_TODO either; items an agent completed say so and wait for your tick.

| # | Date | Area | What an agent chose | Where to look | Why | Status | Your call |
|---|------|------|---------------------|---------------|-----|--------|-----------|
| 1 | 25 Sep 2026 | Studio | Restarted the Studio on 8191 to load merged Python (#945, #950, #959) after you said it was idle. No job was running. | Any page | Your go-ahead: "do whatever you want with the studio except queueing jobs" | done | |
| 2 | 25 Sep 2026 | Large-job preparation (#306) | The gate changes. Work in flight blocks every action. Uncertain or interrupted records block only the ComfyUI restart, which would wipe the history that Resume observation needs. Planned or awaiting-review plans never block. | Runs & review; `docs/verification/2026-09-19-large-job-preparation.md` | As merged, the gate refused even a dry run on your PC because of five old uncertain jobs | PR open | |
| 3 | 25 Sep 2026 | Asset library | Grid cards show cached thumbnails (about 384 px) instead of the full original. The review dialog still opens the original. | Asset library | Each card loaded a ~1.2 MB PNG; the full library is about 1.4 GB per scroll-through | PR open | |
| 4 | 25 Sep 2026 | Asset library | Shift-click selects a range, Ctrl+A selects what is visible (up to 200) and Escape clears. The library remembers scope, sort, grouping and media type across reloads. | Asset library | Selecting many assets needed one click each; filters reset on every reload | PR open | |
| 5 | 25 Sep 2026 | Asset library | New actions: *Mark as agent run* (default label "Agent lab") and *Mark as mine*, for a selection or a whole group | Asset library → select → action bar | Your old lab outputs carry no marker, so the Mine / Agent runs filter could not hide them | PR open | |
| 6 | 25 Sep 2026 | Create | Ctrl+Enter presses Generate, only when the button itself is enabled. It never submits on its own. | Create | There was no keyboard way to generate | PR open | |
| 7 | 25 Sep 2026 | Create | Pasting a picture (Ctrl+V) fills the first empty reference slot | Create → references | Screenshots had to be saved to disk first | PR open | |
| 8 | 25 Sep 2026 | Create | Layout, Ambience and Skin move into a closed *Appearance* control, so the recipe, prompt and Generate come first | Create | The three cosmetic pickers took the top of the page | PR open | |
| 9 | 25 Sep 2026 | Prompt Lab | Your unfinished brief is kept in this browser and comes back after a refresh | Prompt Lab | A refresh lost everything typed | in progress | |
| 10 | 25 Sep 2026 | Guided workflows | Reopening a guide resumes at the step you left, with a *Start over* control | Guided workflows | Resume always restarted at step 1 | in progress | |
