# Goal-first rework, 19 Oct 2026 (ux-lead, overnight)

Owner ask (19 Oct): a user with an objective, such as a very high-end anime picture with a chosen model and LoRAs and then
tweaks, should get there without confusion. Rework allowed. Earlier rounds (audits v1-v3, 16 Oct) already made Make the
goal-first front door; this pass audits what still feels clunky and fixes it in small slices.

## Method
Preview Studio on 127.0.0.1:8291 from the `ux/*` worktree (own empty workspace, real ComfyUI catalog read-only), driven by
Playwright at 1440x900. Every generation route was intercepted; nothing was submitted. Run cards were seen by restoring a
fake finished run in the browser only (`/api/jobs/<id>` and `/api/image/...` answered by the harness).

## Target information architecture (unchanged shape, sharper surface)
1. **What are you making?** Goal tiles (5 make-new, 6 from-a-picture). Already in place.
2. **Look** chosen by its picture. The look is the default model + LoRAs + wording for the goal.
3. **Recipe in view**: the model, each LoRA with its strength and the step count are readable without opening anything,
   and one press opens them for editing (Tune). Expert controls (sampler, negative, seed, compare one setting) stay folded.
4. **Describe + Generate**: one text box, shape, how many, estimated time, one Generate.
5. **Results with next steps**: Keep / Not this, then the tweaks people ask for by name: Vary, Fix face, Upscale,
   Change one thing (outfit, colour), New pose; the rest under More.

## Findings (19 Oct) and slices
| # | Finding | Slice |
| --- | --- | --- |
| F1 | Model and LoRAs hidden: the shut Tune line read "Model, adapters, steps, seed", naming categories, not choices. | S1: the line reads "As made: Anima · anima-base-v1.0 · pearly_petiflow2 1.00 · 25 steps" (the model file is named when a family has two); tuned runs keep "Tuned: ..." |
| F2 | Before the first picture the composer sat in a 40% column beside an empty "Your pictures" column; Shape, How many and Generate stacked below the text box. | S1: the split opens only once runs exist; before that the composer uses the full width with its controls in the side column. |
| F3 | A look whose example picture is local-only and absent showed a broken image. | S1: missing look pictures fall back to the blank mark. |
| F4 | Run cards: "Change one thing" and "Put in a new pose" (change outfit, change pose) were under More. | S2 |
| F5 | Picture goals: the empty-picker line wraps in a narrow grid cell. | S2 |

Each slice's before/after and proof are in its PR and in `docs/UX-USE-CASE-MATRIX.md` where clicks change.
Judgement calls are logged in `docs/REVIEW-BACKLOG.md` with how to reverse them.

## Pass 2 (ux-lead-2, 19 Oct): a first-time user, the whole app, 1440x900 and 390 px
Method: a preview Studio on 127.0.0.1:8292 from the `ux2/*` worktree, with **no experiments root**, so it showed what a new install
shows. Real catalog, ComfyUI on 8188 read-only. A Playwright walk (`scratchpad`, not committed) loaded the 12 pages at both widths
and aborted every non-GET except `/api/estimate`; nothing was submitted. Runs & review with real history was read as text only from
the live Studio (8191), with non-GETs and images blocked, because pictures there may be adult (agents do not open them).

What the walk measured, a selected subset of the 12 pages (visible controls / words, plus page height at 1440 → 390 where it was recorded; the other five pages and the missing heights were not kept): Make 23 / 318 / 1711 → 2699; Library
20 / 145; Models & setup **431** / 438 / 2279 → 4267; Full editor 59 / 200; Compare & review 8 / 165; Workflow builder 67 / **1187** /
3904 → 6558; Prompt Lab 46 / 417. No page scrolls sideways at 390 px. No page errors.

Onboarding: Make opens first with *Anime character* chosen. From a cold start, a high-end anime picture is **look, words,
Generate**: 2 clicks plus typing, with the model and LoRAs readable on the chosen look. That path is sound. The friction was around it:

| # | Finding | Where | Slice |
| --- | --- | --- | --- |
| P1 | On a new install the estimate said "About 4 min in total, from earlier runs on this PC" beside a card saying ~31 s. Nothing had run: the server's answer was a generic guess (`confidence: none`). | Make | #1574: the look's lab median when nothing comparable ran, else "a rough guess"; Compare looks never claims runs it did not use |
| P2 | Every picture goal on an empty library dead-ended: "import one in the library" meant leaving Make (5 clicks + file). | Make | #1576: *Import a picture…* in the picker and the pose slot; it is chosen (2 clicks + file) |
| P3 | One page said LoRA and adapter for the same thing; Steps said "Finer" where Quality said "Fine". | Make | #1582 |
| P4 | Review words differed in four places (Keep / Not this; Keep / Needs work / Reject; Keeper(s) / Rejected; "Keep for consideration"). Make had no review keys. | All | Decision J: Keep / Needs work / Not this, K / W / X, "Kept". Make part #1579; the rest Brief J (Sol) |
| P5 | Models & setup: 6 of 24 look rows showed broken images; "Needs a check (170)" and "Installed (0)" while all 24 looks were ready. | Models & setup | Brief H (#1580) |
| P6 | Compare & review with no plans said "Choose a plan on the left" over an empty list; the status filter was cut to "In progress o"; the Review desk opened directly was a dead end. | Compare & review | Brief I (Sol) |
| P7 | The Full editor showed three ways into the same checks (Review readiness, Review checks, Readiness & run details). | Full editor | Decision K, Brief K (Sol) |
| P8 | Make cannot help with a recipe that needs another model environment: Generate is disabled with "Switch to X to use this recipe" and a link. MOSS-Image (#1575) is the first Make-worthy case. | Make | Next: environment chip on looks and a one-press switch beside the disabled Generate, after #1575 |
| P9 | Models & setup: the "Model environment" fold sits above the page heading, and look rows are subtitled with recipe names ("Anima v1 · modular illustration baseline"). | Models & setup | Open, low |
| P10 | Library: three import affordances on the empty first screen, and the heading "A library, not a dead end." says little. | Library | Open, low |
| P11 | Phone: the 11 goal tiles fill the first screen before any look; the Full editor's dock takes about 17% of an 844 px screen. | Make, Full editor | Open, low |
| P12 | Workflow builder: 1,187 words on its first screen, 6,558 px tall at 390 px. | Workflow builder | Open: Brief E folded its tools; a second pass would fold the walkthrough text |
