# Saved Make look ownership — 5 November 2026

Issue [#1867](https://github.com/Chris0Jeky/local-asset-studio/issues/1867) records a
save completion clearing another look's newly typed name, unclear seed-lock retention,
unstable picker order and a missing preview. This slice preserves the existing look
schema and save command. It changes presentation ownership and explains which settings
start at their defaults.

The worktree base is local `5f3f43ee8bdad8547e954a4b369fff4b4e1cdeed`, tree
`8ec1a12bdf31fc03106eaa53a1fcb34f75db0916`.
After the slice commit, main `107a5bc69a67246d101ff1754dfe15f67d81e6e9`
(local mirror `e41c97dcbdf985629cec3da0006471b90aaa450d`) was merged without
conflicts. The guide retains both the new saved-tune guidance and the merged
picture-first comparison instructions.

## Reproduction and correction

The source-level regression exercises the shipped Make save functions with held replies.
Before the production fix, the expanded suite had **7 passing and 10 failing tests**;
the retained session log is `make-save-red.log`. A held completion could clear and hide
the replacement form or announce the old save under the current goal.

The UI now captures the original form, fields, look and goal before awaiting the command.
It also checks the privacy epoch and a presentation generation, so a privacy round trip,
Cancel/reopen, or returning to the same look with new nodes cannot revive old feedback.
The existing command still runs once. Acknowledged regular saves can enter the list after
a card switch, while stale successes and refusals leave the current form alone. If the
same form's name or notes change during the request, the completed save is named in the
form and the newer text remains available.

A final review reproduced an adjacent same-form race using the shipped `generate`,
`saveTunedLook`, `saveLookUi` and `say` functions: one fixture job reached **Started**,
then the held save replaced that newer run status. The causal regression failed before
correction; `make-save-status-red.log` retains that result. Save feedback now uses only
its existing local live region, moved just outside the inner form so success remains
visible after the fields clear and hide. The Generate status owner is unchanged. The
success wording identifies the saved name and captured goal and says **Saving a look
does not generate a picture.**

Tunes are sorted by name with an ID tie-breaker within each base look; the goal's base
look order stays intact. The save hint and active guide explain that shape and option
selections restart at defaults. A locked seed number remains a starting value, while
**Different pictures each time** must be turned off again to lock it.

`displayPreviewOf` is used only by `renderLooks` for the gallery and chosen-look strip.
An own preview wins; otherwise an existing, nontrashed base look may supply its picture
with **Base look preview; tuned settings may look different.** The shared `thumbOf`
function, reference-image choices, reference fetches, anchors and lineage are unchanged.
The fallback does not claim a rendered result from the new tuning.

## Executed local checks

- Before-fix source regression: **7 passed, 10 failed**, as described above.
- `node --test tests/make_save_tuned_look.cjs`: **18 passed** after the fix, including
  stale success/refusal, privacy A–B–A, cancel/reopen, replaced nodes, pending edits,
  duplicate press, stable order, empty negative wording, seed zero, scaled and disabled
  LoRAs, display-only preview selection and preservation of a newer Generate status.
  That last case doubles preparation and external effects but retains all four shipped
  status/save/Generate functions; it observes one look POST and one in-memory fixture job.
- On the combined tree, `node --test --test-concurrency=1 tests/make_*.cjs` passed
  **106 tests**, including the 18 saved-look checks. Earlier checks in this same slice
  passed **27 backend look tests** and **30 frontend handoff tests**.
- `python -m unittest discover -s tests -p test_browser_fixture_callbacks.py`:
  **3 passed**.
- `node --check app/static/make.js`, Python compilation of the browser driver, and
  `git diff --check`: passed.
- `python scripts/validate-repo.py`: passed, **98 preset graphs/bindings** and
  **194 pinned assets**, with **4,889 tracked paths** on the combined tree.

## Browser proof and its boundary

The existing cross-platform `tests/make_privacy_transitions_browser.py` driver now has
**11 cases**, including four new saved-look journeys. It uses the actual Make/privacy
scripts, DOM controls and ordinary keyboard/input events. The save POST is captured and
held through `page.route`; its success or refusal is explicitly **fixture-crafted** with
`route.fulfill` after a replacement form or pending edits have been entered. GETs continue
to the existing local HTTP fixture. This is browser ownership proof, not proof that a
real look was persisted. Backend persistence has its separate 27-test coverage above.

The new cases check stale success and refusal after a card switch, edits to the same
pending form, and a normal save whose local success remains visible after the fields
close without changing the global status. The held-reply helper waits for the original
save button's finalization check, including when the button is detached: a one-shot
observer returns the native `isConnected` value and then removes itself. This observes
the actual handler's completion without a timing delay or a production test hook.
Gallery selection then uses the saved tune. Gallery and chosen-card
captures at **1440px and 390px** include the visible base-preview qualifier, loaded image
bytes, viewport bounds and independent hit-testing. The saved tune remains absent from
the functional style-reference picker. The driver records each crafted reply and the
actual command it answered, and refuses any preparation, source staging or generation
request in these journeys.

Screenshots, geometry JSON and the source-hashed receipt are written under
`.runtime/make-privacy-transitions` and uploaded by the existing Private creation
boundaries workflow on Windows and Linux. No local Chromium is available here; this
note does **not** claim that the new browser cases have run. Exact published-head CI and
visual inspection must supply that evidence. No model run or owner art acceptance is
claimed, and the existing paused-artwork and owner-review decisions are unchanged.
