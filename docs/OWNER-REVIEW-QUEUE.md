# Owner review queue: things to glance at, not blockers

Agents record the choices they made for you here: defaults, copy and wording, layout moves, small behaviours. Nothing
in this file blocks work. Real decisions and approvals stay in [HUMAN_TODO.md](../HUMAN_TODO.md).

How to answer, when convenient:
- **Fine** — put `ok` in the *Your call* column, or just say "queue: ok 1–6" in a session.
- **Change it** — write what you want instead. An agent turns it into an issue or a fix.

Agents add a row when they make a choice like this, and never fill in *Your call* themselves. In HUMAN_TODO, agents tick an item only when they have verified its completion, or you have answered every part of it and its conditions hold, and they record how.

| # | Date | Area | What an agent chose | Where to look | Why | Status | Your call |
|---|------|------|---------------------|---------------|-----|--------|-----------|
| 1 | 25 Sep 2026 | Studio | Restarted the Studio on 8191 to load merged Python (#945, #950, #959) after you said it was idle. No job was running. | Any page | Your go-ahead: "do whatever you want with the studio except queueing jobs" | done | |
| 2 | 25 Sep 2026 | Large-job preparation (#306) | The gate changes. Work in flight blocks every action. Uncertain or interrupted records block only the ComfyUI restart, which would wipe the history that Resume observation needs. Planned or awaiting-review plans never block. | Runs & review; `docs/verification/2026-09-19-large-job-preparation.md` | As merged, the gate refused even a dry run on your PC because of five old uncertain jobs | merged #972; one follow-up (#980) for failed jobs that kept an old observing record | |
| 3 | 25 Sep 2026 | Asset library | Grid cards show cached thumbnails (about 384 px) instead of the full original. The review dialog still opens the original. | Asset library | Each card loaded a ~1.2 MB PNG; the full library is about 1.4 GB per scroll-through | merged #969 (measured live: 22 KB per card) | |
| 4 | 25 Sep 2026 | Asset library | Shift-click selects a range, Ctrl+A selects what is visible (up to 200) and Escape clears. The library remembers scope, sort, grouping and media type across reloads. | Asset library | Selecting many assets needed one click each; filters reset on every reload | merged #975 | |
| 5 | 25 Sep 2026 | Asset library | New actions: *Mark as agent run* (default label "Agent lab") and *Mark as mine*, for a selection or a whole group | Asset library → select → action bar | Your old lab outputs carry no marker, so the Mine / Agent runs filter could not hide them | merged #975; used as you approved: 1,178 unreviewed lab outputs marked, 9 of yours remain under Mine | |
| 6 | 25 Sep 2026 | Create | Ctrl+Enter presses Generate, only when the button itself is enabled. It never submits on its own. | Create | There was no keyboard way to generate | merged #974 (also ignored while any dialog is open) | |
| 7 | 25 Sep 2026 | Create | Pasting a picture (Ctrl+V) fills the first empty reference slot | Create → references | Screenshots had to be saved to disk first | merged #974 (several pictures fill several slots) | |
| 8 | 25 Sep 2026 | Create | Layout, Ambience and Skin move into a closed *Appearance* control, so the recipe, prompt and Generate come first | Create | The three cosmetic pickers took the top of the page | merged #974 | |
| 9 | 25 Sep 2026 | Prompt Lab | Your unfinished brief is kept in this browser and comes back after a refresh | Prompt Lab | A refresh lost everything typed | merged #973; a restored draft now says so, with *Start fresh* | |
| 10 | 25 Sep 2026 | Guided workflows | Reopening a guide resumes at the step you left, with a *Start over* control | Guided workflows | Resume always restarted at step 1 | merged #973 (the guide cards already offered Resume; this covers bare links) | |
| 11 | 25 Sep 2026 | Asset library | Bulk review asks before overwriting reviews you already saved, naming the counts; Refresh shows *Refreshing…*; closing a picture returns focus to its card | Asset library | One click could silently replace earlier decisions | merged #975 | |
| 12 | 25 Sep 2026 | Runs & review, Workflow Studio | Text you are typing survives the 15 s refresh; the number box and slider for a setting stay in step | Runs & review → a plan; Workflow Studio | Background refreshes wiped review notes and names mid-typing | merged #976 | |
| 13 | 25 Sep 2026 | Review desk | Says *Saving… / Loading… / Exporting…* while it is locked, and why *Export review evidence* is unavailable | Runs & review → review desk | The page looked frozen during saves | merged #973 | |
| 14 | 25 Sep 2026 | Errors, import, collections | Server errors name the real cause (ComfyUI vs a local file); character import can be cancelled mid-upload; the collection editor shows live limits; the reference picker resets after a bad choice | Various | Audit findings | PR #978 | |
| 15 | 25 Sep 2026 | Tests | The use-case runner gives each case a fresh browser, so saved drafts cannot leak between cases | `tests/studio_use_cases.py` | A restored Prompt Lab draft broke the next case in CI | merged #973 | |
