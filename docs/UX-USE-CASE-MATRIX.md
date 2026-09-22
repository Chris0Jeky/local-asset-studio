# UX use-case matrix

## Reference analysis review and Apply — 18 September 2026

`reference-analysis-review-and-apply` now registers the Prompt Lab reference-review pipeline as an
owner-shaped journey. In fixture mode it loads deterministic exported analysis, supplies the same
original image bytes under renamed files, edits an approved style facet, prepares the real before/after
diff through the production reference-review HTTP extension, applies explicitly, and verifies that the
applied references and diff remain visible. The journey records every step and the global use-case
harness still rejects any generation-capable request.

This is interface and data-contract evidence, not evidence that a vision model described a real owner
image well. `tests/reference_review_browser.py` remains the deeper two-viewport proof for undo,
stale-response handling, receipt export, exact-original refusal and text-zoom layout. The focused CI
lane runs both that proof and this measured matrix case.

## Draw the pose — 16 September 2026

The Combine screen now draws its own pose skeleton (#444, #475, #480). A **Draw the pose** panel appears for any
Combine continuation: the 18 COCO-18 joints drag with a mouse or a finger, the joint list picks one for
the arrow keys (1 % of the canvas, 5 % with Shift), a joint can be marked unknown so it and its limbs
leave the drawing, *Start from* loads a standing figure, the bent-forward research figure or a mirror,
and Undo steps back one change. On the skeleton recipe **Use this pose** renders the guide through
`POST /api/pose/render` and attaches it to Picture 1. On a picture-based Combine (depth, Copy Pose, pose-first)
the same control reads **Replace pose picture with drawing**: it still renders through that endpoint, then
replaces Picture 1 and selects the skeleton recipe. The character, seed, canvas and who/clothes answers stay;
the pose answer is cleared so Generate waits for wording that matches the drawing (#492). Ordinary engine
buttons still refuse picture/skeleton reinterpretation — getting back to depth or Copy Pose needs a pose
picture re-pulled from the library. Drawing and rendering submit nothing; Generate stays a separate press.

`python tests/studio_use_cases.py` passed **14/14** journeys in 65.3 s on Windows/Python 3.14, with
**zero generation submissions and zero page errors**. The new `draw-a-pose-for-combine` journey takes
8 clicks: four to reach a prepared Combine on the drawn-skeleton recipe, then a starting figure, a
picked joint, an unknown joint and **Use this pose**; the keyboard nudge is measured by comparing the
canvas bitmap before and after three arrow presses. The guide route is named in `DRAWING_ROUTES` so it
is not miscounted as engine work — `tests/test_pose_guide.py` proves it reaches no model and creates no
job. **This is interface evidence only:** no picture was generated from a guide drawn in this panel,
and the renderer (`studio.coco18-lines/v1`) draws thinner strokes than the hand-drawn figure the
research proved. See [Draw the pose](STYLE-AND-POSE.md#draw-the-pose-16-september-2026).

## Combine experiment loop — 16 September 2026

The same source pair now has a result strip with seed tiles, Workspace keeper/needs-work decisions,
and explicit **Prepare same seed** / **Prepare new seed** actions. Both actions load a checked saved
recipe; Generate still requires a separate click. Failed and uncertain history sits under **Problems**;
its observation and recovery controls remain available when expanded.

The compatible Combine recipes switch on the same screen in **one click**, retaining the character,
pose picture and named answers. Image numbers and graph identity follow the destination recipe.
Edited wording stays with its original recipe and returns when switching back. Skeleton and RGB
picture routes are not interchangeable; excess board pictures and missing references block a switch.
Each choice shows its last completed local timing when available, or says there is no timing yet.

`python tests/studio_use_cases.py --out .runtime/combine-all-use-cases.json` passed **13/13** journeys
in 69.2 s on Windows/Python 3.14, with **zero generation submissions and zero page errors**. The new
`combine-same-pair-second-engine` journey checks source/graph identity, cross-recipe results, preserved
hand edits, two independent review decisions and both seed preparations. It takes 11 clicks in total:
five to prepare the pair, two recipe switches, two reviews and two seed preparations. These are
synthetic browser fixtures, not model-quality or owner-acceptance evidence. Geometry editing and
native guide routing remain separate work under #444/#445; broader #422 stays open.

Ten owner-shaped journeys through the Studio, driven by an agent in a real Chromium and measured
step by step. The intents live in `research/ux/use-cases.json` (selector-free, in the owner's words);
the selectors live in `tests/studio_use_cases.py`, one driver per case. Refs #278.

**Measured 14 Sep 2026 on DESKTOP-IHKOOJS**, Python 3.14, Playwright + Chromium, viewport 1536×1060,
fixture mode, 38.5 s for the whole run. Command: `python tests/studio_use_cases.py`.
Raw record: `research/ux/use-case-matrix.json`; per-step screenshots under `.runtime/ux-use-cases/<case>/NN.png`
(gitignored evidence). **Zero generation requests were sent and zero page exceptions were raised.**

## What "fixture mode" is and is not

The run serves the real frontend files with synthetic API data from `tests/studio_browser_smoke.py`
(imported, not copied), plus the extra read routes these deeper journeys touch — guided paths, the
node catalog, and one additional finished comparison so that reviewing a study is reachable at all.
**No ComfyUI is contacted and no model runs.** So the matrix measures *the interface*: which controls
exist, whether they can be seen and pressed, what the screen says when they cannot, and how many
steps the pipeline costs. It does not measure render quality, timing, or whether a recipe actually
produces a good picture — those need a real run and the owner's eye.

Two consequences worth stating plainly:

- **"Prepare" steps are honest; "start" steps are out of scope by design.** Preparing a comparison
  or a native export is measured end to end. Starting one, and everything downstream of a real job,
  is not exercised anywhere in this suite.
- **The review case runs against a synthetic finished comparison.** The decision path (reveal the
  settings, open a candidate, write a note, keep a winner) is real and measured; the pictures behind
  it are fixture assets, so nothing here is creative acceptance.

## The matrix

**This table is the first measurement, taken before the fixes.** The five friction points it ranks
were fixed in `ux/matrix-friction-fixes` and the suite re-run; the before/after numbers are in
[Re-measured after fixes](#re-measured-after-fixes) below, and every note in this section describes
the interface as it was on 14 Sep 2026.

`int` = steps intended, `took` = steps taken, `clk` = clicks actually performed, `sw` = page/view
switches, `dead` = dead ends, `unexp` = controls disabled with no adjacent reason, `words` =
instruction words encountered (each panel charged once, when it first comes up), `peak` = the most
words on screen at any one step.

| Case | int | took | clk | sw | dead | unexp | words | peak | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first-image-from-brief` | 7 | 7 | 2 | 1 | 1 | 0 | 451 | 378 | PASS |
| `reference-edit-one-source` (wrong turn) | 8 | 8 | 3 | 2 | 2 | 0 | 380 | 467 | PASS |
| `three-reference-identity-pose-style` | 10 | 10 | 7 | 6 | 0 | 0 | 501 | 483 | PASS |
| `compare-settings-from-recipe` | 8 | 8 | 4 | 2 | 0 | 0 | 429 | 362 | PASS |
| `review-and-keep-winner` | 7 | 7 | 4 | 2 | 0 | 0 | 110 | 105 | PASS |
| `reuse-keeper-as-reference` | 8 | 8 | 4 | 2 | 0 | 0 | 85 | 566 | PASS |
| `prompt-lab-to-create` | 8 | 8 | 4 | 1 | 0 | 0 | 521 | 378 | PASS |
| `guided-edit-or-preserve-character` | 9 | 9 | 6 | 1 | 0 | 0 | 1002 | 589 | PASS |
| `build-and-prepare-node-workflow` | 9 | 9 | 3 | 0 | 1 | 1 | 589 | 604 | PASS |
| `frames-to-native-export` | 9 | 9 | 6 | 2 | 0 | 0 | 99 | 64 | PASS |

Every case reached its success condition, and every case took exactly the number of steps it intended.
PASS means the journey completed in the interface — not that the result would be worth keeping.

### Per-case notes against the success condition

- **`first-image-from-brief`** — recipe chosen, brief typed, run control enabled, nothing submitted.
  One dead end: the "what to avoid" field could not be typed into (below).
- **`reference-edit-one-source`** — the deliberate wrong turn happened first: a text-only recipe was
  chosen, and the attempt to bring in a source found nothing to press. Recovery worked: search,
  choose a one-reference recipe, pull a picture from the library, describe the change, ready.
- **`three-reference-identity-pose-style`** — all three slots filled with distinct roles (identity,
  pose, style) and the run control enabled. Highest click and switch count in the suite.
- **`compare-settings-from-recipe`** — a study was prepared on guidance with explicit candidate
  values and an allowance sized to them, and a *new* study appeared in Runs & review as `planned`.
  Not started. The allowance has to be raised by hand to match the planner's own proposal (below).
- **`review-and-keep-winner`** — settings revealed, a candidate opened, a note written, winner kept,
  the study recorded as `reviewed`. Among the lowest reading loads of the suite (110 words).
- **`reuse-keeper-as-reference`** — a library picture was prepared as the source of a one-reference
  recipe with its lineage (`parentAssets[0] == asset-1`) intact.
- **`prompt-lab-to-create`** — compiled wording reached the recipe's brief field only after an
  explicit review and an explicit apply.
- **`guided-edit-or-preserve-character`** — all six stages reached in order (`mechanism → sources →
  wording → readiness → output → review`), each landing on a real control, no generation submitted.
- **`build-and-prepare-node-workflow`** — the catalog loaded, a graph was imported and checked, and
  the export became available. The prepare-a-run control was reached but is disabled with no reason
  given (below). A real run from a saved revision is **not** exercised and cannot be in fixture mode.
- **`frames-to-native-export`** — two frames selected, atlas chosen, frame timing set, export prepared
  and listed. Starting the export is out of scope.

## Top friction points

Ranked by dead ends, then clicks.

1. **The wrong turn says nothing at all.** `reference-edit-one-source`, step 2, Create.
   On a text-only recipe the whole "02 · Bring in your sources" section — heading, explanation and
   the *Pull from library* button — is `display: none`. A person who wants to edit a picture sees no
   reference affordance and no sentence telling them why. Measured as two dead ends in a row
   (the control, then the explanation that is not there).
   *Fix:* keep the section visible on text-only recipes with the controls disabled and one line —
   "This recipe writes from words only. Choose a Qwen Atelier or reference-edit recipe to bring a
   picture in" — plus a link that runs the recipe search for reference-capable recipes.

   **Fixed 14 Sep 2026.** The section stays on screen for every recipe. On a text-only one it opens no
   picker and carries the line "This recipe takes no reference image. Choose a reference recipe (Qwen
   Atelier 1–3 references, Krea refine) to keep a source." — which is also `#uxPullAsset`'s
   `aria-describedby` reason, so anything that reads the control finds it — plus a *Show reference
   recipes* button that runs the existing `edit` intent filter (which selects the first reference recipe and
   resets the prompt, so a typed brief is asked about first). Pressing *Pull from library* on such a
   recipe answers with that same line rather than doing nothing; it is deliberately not `disabled`,
   because a disabled button dispatches no click and so can never explain itself to the person pressing
   it. Dead ends 2 → 0, clicks 3 → 4: the wrong-turn click now lands.

2. **"Prepare saved revision" is disabled with no reason.** `build-and-prepare-node-workflow`,
   step 8, Workflow Studio builder. The only `unexplained-disabled` in the suite: the button is
   present, greyed, and nothing adjacent (title, `aria-describedby`, sibling, or status line) says
   what is missing — a saved revision, a registered recipe, or a runtime.
   *Fix:* give the button an `aria-describedby` status line that names the specific precondition that
   is unmet, in the same sentence shape the readiness panel already uses in Create.

   **Fixed 14 Sep 2026.** `#prepareSavedRun` gained an `aria-describedby` status line
   (`#prepareSavedRunState`) fed from the same `WorkflowProject.snapshot()` its disabled logic reads.
   It names exactly one unmet precondition — no saved document, unresolved save, conflicting revision,
   unsaved edits, no chosen recipe, or a request already in flight — and when the control is live it
   says what pressing it will do. `unexplained-disabled` 1 → 0.

3. **"What to avoid" is behind a closed disclosure.** `first-image-from-brief`, step 6, Create.
   The recipe does bind a negative prompt; the field simply lives inside a collapsed
   `<details>` labelled "Negative prompt · What to avoid", so it cannot be typed into and is easy to
   miss. The owner's brief explicitly asks for what the picture must avoid.
   *Fix:* open the disclosure by default when the recipe binds a negative prompt, or promote it to a
   second always-visible field under "01 · Describe the result".

   **Fixed 14 Sep 2026.** `#negativeWrap` opens whenever the recipe binds a negative prompt. It stays a
   `<details>`, and a manual collapse is remembered in `sessionStorage` for that tab only (wrapped in
   try/catch, so a browser that refuses storage simply gets the default). The step still recorded no
   dead end on current `main` — the probe's own `shown` heuristic gives a closed `<details>`' textarea
   a layout box — but the `fill` timed out before and succeeds now.

4. **Attaching three references costs three modal round trips.** `three-reference-identity-pose-style`,
   Create — 7 clicks and 6 view switches, the most of any case, because *Pull from library* opens a
   modal picker that must be reopened once per slot, each time re-choosing the target slot.
   *Fix:* let the picker stay open and fill the next empty slot after each pick (or allow multi-select
   mapped to slots in order), so three references cost one trip instead of three.

   **Fixed 14 Sep 2026.** The picker advances to the next unfilled slot and stays open after each pick,
   closing itself only when every required slot holds an image. The explicit close button is unchanged,
   and changing the recipe closes it, because its slots no longer apply. Clicks 7 → 5, view switches
   6 → 2.

5. **Create carries the heaviest reading load in the product.** Peak 483 words on screen in the
   three-reference case and 604 in the Workflow Studio builder, versus 64–105 in the Asset library
   and Runs & review. The wordiest single panel is the builder's standing explanation.
   *Fix:* move the standing explanations behind "Why?" disclosures next to the control they explain,
   keeping only the one line a person needs to act on visible by default. Runs & review is the model
   to copy — it is the lightest screen in the suite and the one with no dead ends.

   **Not fixed.** This one was left alone, and the four fixes above made it slightly worse: see the
   word column below.

## Re-measured after fixes

**Measured 14 Sep 2026 on DESKTOP-IHKOOJS** against `main` at `c3df645`, same machine, same command,
same fixture, Python 3.14, Playwright 1.62 + Chromium 1234, viewport 1536×1060. `before` is that
`main` re-measured on this machine minutes earlier, not the 14 Sep table above — `main` has taken
PRs #288 and #291 since, which moved the word counts. Both runs: **10/10 PASS, zero generation
requests, zero page exceptions** (38.0 s before, 41.6 s after).

| Case | clk | sw | dead | unexp | words | peak |
| --- | --- | --- | --- | --- | --- | --- |
| `first-image-from-brief` | 2 | 1 | 0 | 0 | 451 → 472 | 378 → 399 |
| `reference-edit-one-source` | 3 → 4 | 2 | **2 → 0** | 0 | 380 → 401 | 533 → 554 |
| `three-reference-identity-pose-style` | **7 → 5** | **6 → 2** | 0 | 0 | 577 | 559 |
| `compare-settings-from-recipe` | 4 | 2 | 0 | 0 | 498 → 529 | 362 → 383 |
| `review-and-keep-winner` | 4 | 2 | 0 | 0 | 154 | 154 |
| `reuse-keeper-as-reference` | 4 | 2 | 0 | 0 | 80 | 632 |
| `prompt-lab-to-create` | 4 | 1 | 0 | 0 | 694 → 715 | 378 → 399 |
| `guided-edit-or-preserve-character` | 6 | 1 | 0 | 0 | 1001 → 1038 | 608 → 624 |
| `build-and-prepare-node-workflow` | 3 | 0 | **1 → 0** | **1 → 0** | 608 → 624 | 626 → 642 |
| `frames-to-native-export` | 6 | 2 | 0 | 0 | 99 | 86 |

**Suite totals: dead ends 3 → 0, clicks 43 → 42, view switches 19 → 15.** No case regressed on dead
ends or switches, and no case lost its success condition.

Three numbers moved in a direction that needs saying out loud:

- **`reference-edit-one-source` clicks 3 → 4.** The wrong-turn press of *Pull from library* used to hit
  a `display:none` control and was never performed. It is performed now and produces a sentence, so it
  is counted. Two dead ends became one answered click.
- **`three-reference-identity-pose-style` clicks 7 → 5 for a reason worth knowing.** The driver still
  presses *Pull from library* once per slot. The second and third presses now fail — the picker is
  already open and modal, so nothing outside it can be clicked — and the driver's own fallback picks
  the next slot inside the open picker. That is the saving being measured: the button a person would
  have had to press again is unreachable because it is no longer needed. The case still ends with 3/3
  slots attached and the run control enabled.
- **Instruction words rose by 21 on every Create case and 16 on the two Workflow Studio ones.** That is
  exactly the new explanatory text: 21 words for the no-source-slot line that is now always present in
  Create, 16 for the prepare precondition line, 10 for the allowance total in the comparison planner.
  Friction point 5 — Create's reading load — was not in scope, and these fixes push against it: four
  dead ends were traded for 47 words. Fixing 5 properly (standing explanations behind "Why?"
  disclosures next to the control) would pay all of it back and more.

The allowance fix is not visible in this table, because the driver still performs the step that sets
the total by hand: the planner opens at its default of 4, choosing three values keeps 4 (the sizing only
ever raises), and the driver then types 3, which the planner accepts because 3 candidates fit.
`tests/production_clarity_frontend.cjs` proves it directly: choosing an axis sizes the allowance to the
proposal, never lowers a total the operator raised, and leaves a branch that shares its parent's budget
alone; the note states the required total before any refusal.

## The eleventh journey: restyle a recent output — 14 Sep 2026 (later)

The owner's own report the same afternoon: a liked output, a second picture with the look they wanted, and no
idea which recipe does that. *Continue with this → Refine → SDXL • stronger variation* was the closest offer;
attaching the style picture into its single slot produced two blockers whose button only scrolled back up.
`restyle-recent-output-with-a-look` (`research/ux/use-cases.json`, driver in `tests/studio_use_cases.py`) is
that journey after the fix: the fifth Continue route, **Restyle**, plus the one-slot question panel.

| Case | int | took | clk | sw | dead | unexp | words | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `restyle-recent-output-with-a-look` | 8 | 8 | 3 | 1 | 0 | 0 | 863 | PASS |

Fixture mode, `python tests/studio_use_cases.py --case restyle-recent-output-with-a-look`, zero generation
requests, zero page errors. The source lands on the pose picture, the readiness list carries exactly one
condition (*Add at least 1 picture whose look you want to the style board (Picture 1)* with *Show the empty
slot*), the picker opens on Picture 1 and closes itself when the board minimum is met, and the run control
enables. The five clicks are Continue, Restyle, Prepare, Pull from library, the picture. The word count is the
Create view's standing load (friction point 5 above), not new text: the route added one sentence to the
handoff and removed the two unactionable blockers. The same journey on the live Studio produced two real
runs, recorded in `docs/STYLE-AND-POSE.md` and `experiments/curated/style-pose-matrix/2026-09-14-restyle/`.

Re-run the same evening after *Restyle a picture (WAI v17 + light-novel look)* became the route's first destination:
8/8, same five clicks, zero dead ends, zero generation requests; words 1147 (the new recipe's guidance and stages are
longer; trimming is listed in #351).

Re-run later the same night after *Restyle a picture (FLUX.2 Klein 4B, keeps everything)* became the first destination:
8/8, **three clicks** (Continue, Restyle, Prepare), one view switch, zero dead ends, zero generation requests; words 863.
The board steps are gone because the recipe has no style board: the handoff shows the prepared wording (finish, keep
clause, the source's submitted description, 77 words) before preparing, the source panel reports nothing missing, and
the run control enables at once. The case definition and driver were rewritten for that flow (`research/ux/use-cases.json`,
`tests/studio_use_cases.py`); a board recipe chosen as the destination still walks the old Pull-from-library steps.

## Live mode, and what it refuses

`--base-url http://127.0.0.1:8191` drives a running Studio instead of the fixture. It is read-only
by default: **navigation and typing only**, and every click is checked against an explicit deny list
first. Denied by id (Generate, Plan comparison, Prepare comparison/export/articulated, Switch backend,
Save to Workspace, Prepare saved revision, Export graph, imports, downloads, Move to Trash, …), by
label (`generate`, `start comparison`, `render`, `save to workspace`, `move to trash`, `switch backend`,
`download`, `install`, `delete`, `prepare`, `submit`, `run`, `resume`, `stop`, `choose <letter>`),
by attribute (`data-project-action`, `data-choose-candidate`, `data-bulk`, `download`) and for any
button that would submit a form. Reading a control is never blocked — only doing is. Fixture mode never contacts ComfyUI; live mode
reaches only the loopback Studio (whose own health probe reads ComfyUI system stats), and the base URL
must be loopback. Generation submissions are counted from the POSTs the browser itself sent, in both
modes, against every route that can start or resume engine work.

Proven 14 Sep 2026 by pointing live mode at a standalone copy of the fixture server:
**43 actions were refused, 3 of the 10 cases still completed on navigation and typing alone, and zero
generation requests were sent.** The deny list is deliberately over-broad — one guided-path link was
refused because its card text contains "Run a recipe without a browser" — which is the correct way
for a safety list to fail.

### What live mode reaches, and how it ends (#486)

Until #486 ten live journeys died at a `missing-control` dead end before any click, because their
drivers named fixture ids (`asset-1`, the fixture study `cccc…`) or waited for a dialog the guard had
refused to open. Now a live journey ends in one of four named results:

| Result | Meaning |
| --- | --- |
| **PASS** | The success condition was reached on navigation, typing and read-only checks alone. |
| **STOP** | The journey got to a control that would write server state — shown, enabled, with no control missing on the way — and it was measured, refused and never pressed. The reason names the control. A refused control that was hidden or disabled is not a STOP: the journey carries on and reports its dead end. |
| **SKIP** | The live Studio holds nothing the journey needs — no image in the Asset library, no finished comparison awaiting review, no Recent-runs output whose picture is still in the Workspace, a recipe it does not carry. The reason names what is missing. |
| **FAIL** | A real dead end or a broken step on real data. |

Where a driver used a fixture id, live mode takes the fixture id if the page lists it, else the first
matching item in the page's own order (newest first: the Asset library's default sort, the Recent-runs
gallery, the Runs & review list): an image asset for Continue with this and the export selection, a
finished comparison with candidate pictures for review, the first saved image in the picker for a
reference slot. Fixture mode keeps its own ids and never skips — a skip there is a failure.

Two guard changes make those steps reachable without widening what may be written. A button with no
form owner is no longer read as a form submit (a `<button>` without a `type` reports `submit` even
outside any form, which refused every card and gallery button). And `LOCAL_CONTROLS` in
`tests/studio_use_cases.py` lists, with a reason each, the controls whose press only changes the page,
reads, or validates without storing anything — the recipe picker and recipe cards, Continue with
this, its route and destination choices, the saved-picture picker, asset details and selection
checkboxes, a study's details and candidates, and the Workflow builder's recipe import and
connection check. A listed control skips the label heuristic (a recipe card's description says "one
run of this recipe"); the id and attribute deny lists still bind first, and `data-ux-pull` (attaching
a saved picture) joined the attribute list.

Live run, 22 Sep 2026 ~23:30 against the Studio on main 12307176 (452 Workspace images, 381 jobs, six
comparisons awaiting review): **15 cases, 5 PASS, 10 STOP, 0 SKIP, 0 FAIL — all 15 reached; 0 generation
submissions of 34 browser POSTs (`/api/estimate`, `/api/prompt/compile`, `/api/workflow-studio/compile`,
none of which stores anything), 0 page errors.** The same driver before #486: 5 PASS, 10 FAIL.

| Journey | Live result | Where it ends |
| --- | --- | --- |
| first-image-from-brief, reference-analysis-review-and-apply, prompt-lab-to-create, guided-edit-or-preserve-character | PASS | success condition |
| build-and-prepare-node-workflow | PASS | the checked graph is exportable; Export, Save and Prepare are read, never pressed |
| reference-edit-one-source, three-reference-identity-pose-style | STOP | attaching a saved picture to a slot (`data-ux-pull`) |
| compare-settings-from-recipe | STOP | Plan comparison (`planComparison`) |
| review-and-keep-winner | STOP | recording the winner (`data-choose-candidate`) |
| reuse-keeper-as-reference, restyle-recent-output-with-a-look, the two Combine cases, draw-a-pose-for-combine | STOP | Prepare in Create (`uxPrepareHandoff`: it attaches a copy) |
| frames-to-native-export | STOP | Native export (`nativeExport`) |

reference-edit-one-source used to PASS live without ever loading its recipe (the recipe clicks were
refused and the default recipe's readiness was scored); it now loads the recipe and stops honestly at
the attachment.

## Re-running this

```bash
python -m unittest discover -s tests -p "test_use_case_matrix.py"   # offline gate, no browser, ~0.1 s
python tests/studio_use_cases.py                                     # full fixture run, ~40 s
python tests/studio_use_cases.py --case reference-edit-one-source    # one case
python tests/studio_use_cases.py --base-url http://127.0.0.1:8191    # live, read-only
```

The runner exits non-zero when any journey missed its success condition, the page raised an error, a
generation was submitted, or nothing ran at all (an unknown `--case` id is refused rather than filtered
away). **Live mode is the carve-out**: with `--base-url` most journeys stop short because the deny list
refuses their deciding click by design — each such row reads STOP or SKIP with its reason (see above) — so live journey results
are advisory and only a submitted generation, a page exception or an empty run turn a live run red. The
report is written either way, so a red run still leaves its evidence; `verdict()` holds the whole rule and
`tests/test_use_case_matrix.py` pins it without a browser. Until #611 the runner returned 0 whatever it
measured, and each lane carried its own hand-copied gate step to compensate.

Needs Playwright and Chromium (`python -m pip install playwright && python -m playwright install chromium`);
the normal unittest suite needs neither. `.github/workflows/ux-use-cases.yml` runs the offline gate and
the fixture measurement on every PR that touches `app/static/**`, `presets/catalog.json`,
`studio_workflow/guides.py`, the case file or the runner. The matrix JSON and the per-step screenshots
are uploaded as a CI artifact.

Two lessons from this suite's own first hosted-CI runs, worth keeping if you add a case:

- **Wait for the interface, never sleep.** Preparing a study posts, switches view and refreshes, which
  took longer than the 700 ms the runner first slept for. Use `wait_for_new_study()` / `wait_for_studies()`
  rather than `wait_for_timeout`.
- **Assert on something new, not on something present.** The first version of the comparison case
  checked that Runs & review listed *any* study, and passed locally on plans earlier cases had left
  behind, while the prepare it was supposed to measure was being refused. It now requires a study id
  that was not listed before the prepare. CI caught this; the local run did not.

Adding a case: add its intents to `research/ux/use-cases.json` and register a driver of the same id in
`tests/studio_use_cases.py`. The driver must take exactly one recorded action per intent —
`tests/test_use_case_matrix.py` checks that every case has a driver, and a mismatch shows up in the
matrix as `steps taken ≠ steps intended`.

## Combine two pictures — the owner's second report, 14 September 2026 (late night)

The owner took a Klein restyle output, opened *Continue with this → Restyle* again and typed "have the pose of the
second image, the face and expression of the third image" into the keep sentence (jobs `3ad01f31…`, `35b548fd…`, same
seed). That recipe carries one picture and its wording says to keep everything, so the renders were the input again,
read as "the prompt makes no difference". `combine-character-with-another-pose` (`research/ux/use-cases.json`, driver in
`tests/studio_use_cases.py`) is that journey after the fix: a sixth Continue route, **Combine**. Since 15 September the route leads with a FLUX.2
Klein 9B recipe that keeps the board picture as image 1 (Picture 1) and swaps the source in as image 2, and refuses to run
until its three bracketed fills (who is in image 2; image 1's pose; the clothes and colours) are replaced: first the depth-map
variant (`combine-klein-9b-depth`, later that day), then the Copy Pose LoRA recipe (`combine-klein-9b-copypose`, 16 September: character
as image 1, pose picture as image 2), then the pose-first one, then the replace-character recipe
(`combine-klein-9b-replace`, 16 September: the picture to keep as image 1, the character whose face goes in as image 2, and no pose
change), then the 4B recipe (source on image 1, two fills). The
row below was measured with the pose-first 9B recipe leading; the depth variant has the same slots and fills, and the driver
matches the fills by their wording, so the journey is the same length (not re-measured by hand; the `ux-use-cases` lane re-runs it).

| Case | int | took | clk | sw | dead | unexp | words | peak | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `combine-character-with-another-pose` | 9 | 10 | 5 | 3 | 0 | 0 | 997 | 824 | PASS |
| `combine-character-with-another-pose` (15 Sep, slice A of #422) | 9 | 13 | 5 | 3 | 0 | 0 | 955 | 782 | PASS |

**Slice A of #422 (15 September 2026, second row):** the Combine workbench now shows the two pictures side by side above the
recipe card, in the order the model reads them and with the recipe's own labels (an empty tile offers *Pull it from the
library* / *Choose your picture*); the three bracketed fills are three short named fields (*Who is in image 2*, *Image 1's
pose in a few words*, *Image 2's clothes and colours*) that write the prepared wording, which stays visible and editable
underneath (a hand edit stops the fields from rewriting it until *Rebuild it from the fields*); the disabled *Role for
Picture 1* select is gone from fixed boards; and a long recipe description shows its first sentence and *You fill in: …*,
the measurements and licence paragraph behind *More about this recipe*. Same five clicks. The three extra steps are the three
short fields typed in place of one 630-character paragraph edit, and one read of the side-by-side pictures; the wording on screen
fell from 997 to 955 words. Measured in fixture mode (12/12 cases pass) before and after the change in the same session.

Fixture mode, `python tests/studio_use_cases.py` (12/12 cases), zero generation requests, zero page errors. The five
clicks are Continue, Combine, Prepare, Pull from library, the picture; the tenth step is the typed wording. The readiness
list after preparing carries exactly two conditions, both actionable: *Add the picture whose pose you want to Picture 1 (image 1)*
(with *Show the empty slot*) and *Fill in the wording: replace "[who is in image 2 …]", "[image 1's pose …]" and "[image 2's clothes …]"
in the prompt* (with *Write the description*); filling the two brackets clears the second, the pull clears the first,
and the run control reads *Combine pictures →*. The same journey on the live Studio produced the proving run recorded in
`CURRENT_STATE.md` (job `fb0eb95d…`, 37.6 s). In the same change the Edit route now leads with the 20-second Klein edit
instead of the 11-minute Qwen recipe, and its prepared wording carries one bracketed fill; the `reference-edit-one-source`
case still passes with its wrong turn.
