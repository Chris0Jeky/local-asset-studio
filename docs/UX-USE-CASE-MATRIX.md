# UX use-case matrix

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
   recipes* button that runs the existing `edit` intent filter. Pressing *Pull from library* on such a
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

The allowance fix is not visible in this table, because the driver still performs the step that raises
it by hand; that fill is simply a no-op now. `#experimentBudget` holds 3 before the driver types 3.
`tests/production_clarity_frontend.cjs` proves it directly: choosing an axis sizes the allowance to the
proposal, never lowers a total the operator raised, and leaves a branch that shares its parent's budget
alone; the note states the required total before any refusal.

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

## Re-running this

```bash
python -m unittest discover -s tests -p "test_use_case_matrix.py"   # offline gate, no browser, ~0.1 s
python tests/studio_use_cases.py                                     # full fixture run, ~40 s
python tests/studio_use_cases.py --case reference-edit-one-source    # one case
python tests/studio_use_cases.py --base-url http://127.0.0.1:8191    # live, read-only
```

Needs Playwright and Chromium (`python -m pip install playwright && python -m playwright install chromium`);
the normal unittest suite needs neither. `.github/workflows/ux-use-cases.yml` runs the offline gate and
the fixture measurement on every PR that touches `app/static/**`, `presets/catalog.json`,
`studio_workflow/guides.py`, the case file or the runner, and fails when a case misses its success
condition. The matrix JSON and the per-step screenshots are uploaded as a CI artifact.

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
