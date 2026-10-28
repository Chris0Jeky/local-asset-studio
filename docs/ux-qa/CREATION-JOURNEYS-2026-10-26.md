# Creation journeys and Make draft recovery — 26 October 2026

## Result and boundary

Make already provides a goal-first creation flow: choose a pictured look, describe the scene, and press Generate. Picture edits, Restyle, Combine, model/LoRA tuning, comparisons, and result follow-ups also exist. This pass keeps those paths and fixes a measured interruption cost: an unsent picture draft lost its selected sources and wording on reload.

The baseline was the exact main tree at `f30875b6`. In native Chromium, Change a picture, Character in a new pose, and Restyle lost their drafts at both 1440 × 900 and 390 × 844. Reconstructing the same fixture state required 3, 6, and 4 input calls respectively. Text-to-image scene wording already survived reload. The new draft regression was run against unchanged production code first: **9 of 16 checks failed**, including all six picture-reload checks and private namespace/resume checks.

The new behavior restores the picture goal, its source/pose identities, wording, pose route, style selection, and fix selection from this tab's session storage. Restoration observes the selected asset identities; it does not stage media or submit work. Unavailable sources and a different Workspace preserve the wording and block Generate until the source is chosen again. Malformed stored drafts are ignored. The focused native recovery check now passes **20 of 20** assertions, with zero jobs and no page or request-thread errors.

This is interface and request-contract evidence. The synthetic fixtures have no ComfyUI or model connection, use repository example media, and cannot establish artistic quality, identity fidelity, attractive results, licensing, or owner acceptance. The configured-machine acceptance gap in [#539](https://github.com/Chris0Jeky/local-asset-studio/issues/539) remains.

## Ten bounded journeys

`tests/creation_workflow_journeys.py` reuses the existing production frontend, intent drivers in `tests/studio_use_cases.py`, and cases in `research/ux/use-cases.json`. Each case starts in a new browser context. The drivers' documented fixture prerequisites and direct setup/state injections are retained; those are not counted as user inputs. These are bounded paths to readiness or an explicit diagnostic boundary, not complete journeys to an accepted artwork.

An **input call** is a performed click, check, selection, fill, or key press. The existing `clicks` metric omits typing and keyboard operations, so it undercounts effort for wording-heavy cases. A fill counts once regardless of text length; its character count is also recorded. Browser auto scrolling is recorded as viewport movement and is not counted as a human gesture.

| Journey | Concrete endpoint | Existing clicks | Input calls | Typed fields / key presses | Baseline automated s | After automated s |
|---|---|---:|---:|---:|---:|---:|
| Adult anime character | Pictured look and plain scene prepared in full editor | 3 | 4 | 1 / 0 | 2.52 | 2.73 |
| Anime look, chosen model and LoRA | Compatible model, added artist adapter, 38 steps, locked seed | 7 | 11 | 3 / 1 | 4.94 | 5.10 |
| Specific LoRA in full editor | Search, choose strength, verify trigger added once | 5 | 7 | 2 / 0 | 3.60 | 3.97 |
| Compare looks | Three looks, one scene, one explicit Generate boundary | 5 | 6 | 1 / 0 | 4.03 | 3.36 |
| Reuse a keeper | Chosen Library picture staged as a reference, lineage retained | 4 | 5 | 1 / 0 | 4.95 | 5.21 |
| Restyle a recent output | Source, pictured style, preserved colours; Generate ready | 4 | 6 | 1 / 1 | 3.34 | 3.01 |
| Character in another pose | Two selected pictures and three plain wording fields | 3 | 6 | 3 / 0 | 3.10 | 3.03 |
| Identity, pose and style references | Three assigned reference slots, recipe ready | 6 | 8 | 2 / 0 | 14.11 | 14.08 |
| Vary a keeper | Exact retained controls or an explained refusal | 5 | 5 | 0 / 0 | 8.42 | 8.32 |
| Guided edit / preserve character | Mechanism, sources, wording, readiness, output and review stages reached | 6 | 6 | 0 / 0 | 3.97 | 3.78 |

All ten passed before and after; their input counts did not change. Vary intentionally tests an invalid recorded control and therefore includes one expected refusal in the existing dead-end metric. The improvement is **zero re-entry inputs to recover after reload**, avoiding the original 3–6 repeated inputs in the interrupted picture paths.

The elapsed columns are automation wall time, not human task time or GPU latency. The after run includes 1.00–2.75 seconds of fixed per-action driver waits and 0.55–1.73 seconds of evidence capture per case, plus additional application/driver waits and assertions. The report records those components without pretending the remainder is human effort or pure app latency. No speed improvement is inferred from the small timing differences. Human search, reading, comparison and decision time require a timed owner walkthrough; model execution time must be recorded separately from submission acknowledgment to terminal result, followed by the owner's keep/reject decision.

## Privacy and interruption behavior

Make uses the shared `StudioPrivacy` contract when available and retains a regular-only fallback for older fixtures. Creation classification and the selected read scope are separate. The following focused checks use an explicitly synthetic implementation of that contract; the composed pass below exercises the real privacy controller and frontend.

- An unsent regular draft converted to Private keeps its current form. It moves to a private per-tab key and removes its regular draft/scene copy. Its exact active tuning snapshot moves out of local storage; a newer tune written by another tab is not removed.
- Returning to Regular restores a regular draft or clears the form. Private wording, negative text, tuning, redo records, and remembered Combine fills remain in private session storage. Scope-only filtering does not move the active creation draft.
- Regular, Private and All read scopes filter result cards independently. A filter change clears old result DOM/caches immediately, and a late read cannot repopulate them. Changing the view does not erase unobserved stored history.
- In All view, reusing a private result or source in a regular creation is refused with a direct instruction to choose Private. Private wording is not copied into regular caches.
- A generation intent captures classification before preparation or uploads. A later scope/creation change cannot reclassify the outgoing job. Delayed private acknowledgments are retained under their original classification and are not rendered in a regular result list. `submitted(captured)` carries the shared revision so an old acknowledgment cannot reset a newer choice.
- A private creation can deliberately use a regular source. Source reads use that source's regular scope; staged copies and the destination job use the captured private creation intent. The source is not reclassified.

The native privacy driver passes **19 of 19** assertions with two inert job acknowledgments. It holds a prepare request and a Combine source-context request while switching privacy, then inspects exact outgoing headers, private/regular storage, and visible DOM. No actual generation occurs.

## Reproduce and inspect

Run from the repository root with the repository's browser-test dependencies available. `CHROMIUM_PATH` can select an installed executable; each fixture binds its own ephemeral loopback port and closes it at the end. The recorded local environment was Python 3.12.14, Playwright 1.56.0, and Chromium 141.0.7390.37. This records what ran; it does not change the repository CI dependency pin.

```sh
python tests/make_draft_browser.py --out .runtime/make-draft-final
python tests/make_privacy_browser.py --out .runtime/make-privacy-final
python tests/private_creation_browser.py --out .runtime/private-creation-browser
python tests/creation_workflow_journeys.py --out .runtime/creation-workflow-final/report.json --screenshots .runtime/creation-workflow-final/screenshots
python tests/make_goals_browser.py --screenshots .runtime/make-goals-regression-verified
python tests/make_tune_browser.py
python -m unittest discover -s tests -p test_frontend_handoffs.py
python -m unittest discover -s tests -p test_make_goal_requests.py
node tests/make_shapes_tune.cjs
node --check app/static/make.js
python scripts/validate-repo.py
```

The new reports retain exact source SHA-256 hashes. The journey report also records the browser/Python/Playwright versions and whether the measured source changed during the run. Reports and screenshots are runtime artifacts; the test drivers and this explanation are versioned.

The composed privacy driver uses the real privacy controller, topbar, Make, Full editor and Library, plus the matching production read contracts over an isolated synthetic SQLite fixture. It does not inject a privacy implementation. `--app-root` can select a separate checkout for read-only local integration testing; the selected checkout supplies both frontend files and the matching fixture. The focused Make drivers explicitly replace the privacy module with their named synthetic contract, keeping that narrower evidence distinct. Browser-cancelled connections are recorded separately from request-handler faults.

Integration with the newer bounded Library API exposed an additional recovery failure: the restored source request lacked required `workspace_id` and `details:true`. Make now sends the saved Workspace identity and asks for the bounded detail record. Old unbound sources preserve wording but require a fresh source choice. The focused draft gate consequently has **20** assertions. The composed run also reproduced private Full editor import wording disappearing after reload. After the shared editor persistence fix, the integrated source at `0af8d6a` passes **36 of 36** native assertions with one inert job, zero page/request-handler errors, and unchanged served source hashes during the run. That includes imported private draft recovery, another tab's exact newer regular bytes surviving conversion, immediate scope clearing, and an independent tab starting Regular. It does not establish real model or filesystem-output behavior; those belong to their separate backend gates.

Local verification:

| Gate | Observed outcome |
|---|---|
| Original symptom, production source unchanged | Six picture-reload failures; new combined draft test 7/16 |
| New draft browser | 20/20, zero jobs/page errors/request-thread errors |
| New privacy browser | 19/19, two inert jobs, zero page/request-thread errors |
| Real composed privacy owner, Make, Full editor and Library | 36/36, one inert job, zero page/request-handler errors, served source unchanged |
| Ten bounded journeys | 10/10, zero generation submissions, 55 observed non-generation POSTs, zero page errors |
| Existing Make goals browser | 34 inert jobs, zero real submissions, zero page errors |
| Existing Make tune browser | One inert job, expected exact tuned payload, zero page errors |
| Frontend handoff unit gate | 21/21 using normal Node test-runner isolation |
| Make request unit gate | 5/5 |
| Make follow-up / compare-setting / shape-and-tune Node gates | 18/18, 15/15, 21/21 |

The existing Make goals test now explicitly chooses picture pose mode before its picture-import case: the earlier figure selection is deliberately recovered after reload. Import assertions were retained. The source-slicing Node fixtures were expanded to include their new privacy dependencies; their assertions were retained. In the restricted command runner, normal Node test subprocess isolation exposed only a wrapper result; the same unmodified gate passed with normal permitted process execution. No assertion count or isolation policy was weakened.

## Privacy controls and available workspace

The composed screenshots exposed a separate layout cost: the privacy bar occupied about 168 pixels on desktop before the creation form. A scoped CSS adjustment reduces gaps, removes inherited disclosure spacing, and lets the status and collapsed explanation share a row. Private session, This creation, and the Regular / Private / All view controls keep their separate labels and functions. The expanded explanation still spans the bar.

A native screenshot pass over the integrated `0af8d6a` source, first unchanged and then with only this CSS adjustment, measured the following bar heights. These are rendered pixels, not task-time estimates.

| Viewport | Make before / after | Full editor before / after |
|---|---:|---:|
| 1440 × 900 | 167.5 / 87.9 px | 169.8 / 90.2 px |
| 390 × 844 | 264.7 / 211.7 px | 267.0 / 214.0 px |

Both views kept every privacy control within the viewport with no horizontal overflow. The expanded explanation remained readable at both widths. Keyboard order stayed Private session → This creation → Regular → Private → All. The pass submitted no jobs and reported no page errors. Before/after screenshots and rendered measurements are retained with the runtime evidence; the composed driver also records privacy-bar height and page overflow for its desktop and mobile states.

## Remaining acceptance and adjacent work

The relevant issues were reviewed before choosing this slice: [#772](https://github.com/Chris0Jeky/local-asset-studio/issues/772), [#343](https://github.com/Chris0Jeky/local-asset-studio/issues/343), [#539](https://github.com/Chris0Jeky/local-asset-studio/issues/539), [#118](https://github.com/Chris0Jeky/local-asset-studio/issues/118), [#278](https://github.com/Chris0Jeky/local-asset-studio/issues/278), and [#410](https://github.com/Chris0Jeky/local-asset-studio/issues/410). Many older navigation complaints already have later Make improvements. Library paging/off-page source behavior belongs to the concurrent #1660 work, not a second implementation here.

The [owner anime trial](OWNER-ANIME-TRIAL-2026-10-26.md) supplies an unrun original adult character brief, ten bounded tasks, separate search/reading/decision and machine timing, a six-output-image cap and an owner scorecard. Its budget counts every image in Make's two- or four-image Vary round; optional generation stops at readiness when the remaining budget is insufficient. It includes interruption/resume, a result-to-variation loop and narrow-screen keyboard use. A delayed request while changing privacy remains a useful additional interruption check. Real output judgments should name the failed constraint—identity, pose, clothing, composition, style, or finish—and link the exact recipe/model/seed. Existing owner tasks `lab-art-acceptance-1019`, `kromoss-trial-1019`, `moss-look-1019`, `asset-wave-1-chatgpt`, and `parallax-layers-1219` remain open.
