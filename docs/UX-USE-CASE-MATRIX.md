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

`int` = steps intended, `took` = steps taken, `clk` = clicks actually performed, `sw` = page/view
switches, `dead` = dead ends, `unexp` = controls disabled with no adjacent reason, `words` =
instruction words encountered (each panel charged once, when it first comes up), `peak` = the most
words on screen at any one step.

| Case | int | took | clk | sw | dead | unexp | words | peak | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `first-image-from-brief` | 7 | 7 | 2 | 1 | 1 | 0 | 451 | 378 | PASS |
| `reference-edit-one-source` (wrong turn) | 8 | 8 | 3 | 2 | 2 | 0 | 833 | 467 | PASS |
| `three-reference-identity-pose-style` | 10 | 10 | 7 | 6 | 0 | 0 | 1956 | 483 | PASS |
| `compare-settings-from-recipe` | 8 | 8 | 4 | 2 | 0 | 0 | 489 | 362 | PASS |
| `review-and-keep-winner` | 7 | 7 | 4 | 2 | 0 | 0 | 215 | 105 | PASS |
| `reuse-keeper-as-reference` | 8 | 8 | 4 | 2 | 0 | 0 | 651 | 566 | PASS |
| `prompt-lab-to-create` | 8 | 8 | 4 | 1 | 0 | 0 | 521 | 378 | PASS |
| `guided-edit-or-preserve-character` | 9 | 9 | 6 | 1 | 0 | 0 | 1002 | 589 | PASS |
| `build-and-prepare-node-workflow` | 9 | 9 | 3 | 0 | 1 | 1 | 589 | 604 | PASS |
| `frames-to-native-export` | 9 | 9 | 6 | 2 | 0 | 0 | 136 | 64 | PASS |

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
  values and an allowance, and it appeared in Runs & review as `planned`. Not started.
- **`review-and-keep-winner`** — settings revealed, a candidate opened, a note written, winner kept,
  the study recorded as `reviewed`. Lowest reading load of the suite (215 words).
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

2. **"Prepare saved revision" is disabled with no reason.** `build-and-prepare-node-workflow`,
   step 8, Workflow Studio builder. The only `unexplained-disabled` in the suite: the button is
   present, greyed, and nothing adjacent (title, `aria-describedby`, sibling, or status line) says
   what is missing — a saved revision, a registered recipe, or a runtime.
   *Fix:* give the button an `aria-describedby` status line that names the specific precondition that
   is unmet, in the same sentence shape the readiness panel already uses in Create.

3. **"What to avoid" is behind a closed disclosure.** `first-image-from-brief`, step 6, Create.
   The recipe does bind a negative prompt; the field simply lives inside a collapsed
   `<details>` labelled "Negative prompt · What to avoid", so it cannot be typed into and is easy to
   miss. The owner's brief explicitly asks for what the picture must avoid.
   *Fix:* open the disclosure by default when the recipe binds a negative prompt, or promote it to a
   second always-visible field under "01 · Describe the result".

4. **Attaching three references costs three modal round trips.** `three-reference-identity-pose-style`,
   Create — 7 clicks and 6 view switches, the most of any case, because *Pull from library* opens a
   modal picker that must be reopened once per slot, each time re-choosing the target slot.
   *Fix:* let the picker stay open and fill the next empty slot after each pick (or allow multi-select
   mapped to slots in order), so three references cost one trip instead of three.

5. **Create carries the heaviest reading load in the product.** Peak 483 words on screen in the
   three-reference case and 604 in the Workflow Studio builder, versus 64–105 in the Asset library
   and Runs & review. The wordiest single panel is the builder's standing explanation.
   *Fix:* move the standing explanations behind "Why?" disclosures next to the control they explain,
   keeping only the one line a person needs to act on visible by default. Runs & review is the model
   to copy — it is the lightest screen in the suite and the one with no dead ends.

## Live mode, and what it refuses

`--base-url http://127.0.0.1:8191` drives a running Studio instead of the fixture. It is read-only
by default: **navigation and typing only**, and every click is checked against an explicit deny list
first. Denied by id (Generate, Plan comparison, Prepare comparison/export/articulated, Switch backend,
Save to Workspace, Prepare saved revision, Export graph, imports, downloads, Move to Trash, …), by
label (`generate`, `start comparison`, `render`, `save to workspace`, `move to trash`, `switch backend`,
`download`, `install`, `delete`, `prepare`, `submit`, `run`, `resume`, `stop`, `choose <letter>`),
by attribute (`data-project-action`, `data-choose-candidate`, `data-bulk`, `download`) and for any
button that would submit a form. Reading a control is never blocked — only doing is. ComfyUI is never
contacted in either mode, and the base URL must be loopback.

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

Adding a case: add its intents to `research/ux/use-cases.json` and register a driver of the same id in
`tests/studio_use_cases.py`. The driver must take exactly one recorded action per intent —
`tests/test_use_case_matrix.py` checks that every case has a driver, and a mismatch shows up in the
matrix as `steps taken ≠ steps intended`.
