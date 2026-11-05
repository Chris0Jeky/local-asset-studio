# Models: file summaries and actions — 5 November 2026

Refs #2009, manage-9 only. The broader QA issue remains open. This is a presentation
change; model installation, verification, backend selection and request ownership
retain their existing handlers.

## Reproduction and scope

Started from live main `2ceda747d7f39605c663240d641dd28c0689b80e`, exact local mirror
`254e2605228d41376a94b2e2e189987240b1c1e1` (tree
`faefd4273ed1fbfa63efa4d9862952bc63ddfcd8`).

A focused fixture executed the shipped `app.js` renderer with inert DOM and
transport boundaries. A shared missing file appeared in two look summaries and
one file card; another missing file appeared in one summary and one card. An
unused missing file appeared only in its card. Each file had one install control,
and rendering sent zero POSTs. The repeated detail was the filename list across
the impact summary and the file actions. This was source-level reproduction,
not a native browser observation.

The updated `modelShopCards` expectation failed against the old renderer's
`Needs: base.safetensors, enc.safetensors` output before the production change.
The regression passes with counts and one **View files** link. Existing file
acquisition, eligibility, search and verification assertions remain.

## Result

- Look rows show missing, changed and unchecked counts. Known filenames and
  installation details stay in their file cards.
- Unlisted requirements retain the exact filename and available explanation in
  both the overview and the filtered destination, where the overview is hidden.
  They acquire no install control.
- **View files** includes requirements reported by inspection and look adapters,
  even when the health response supplies no missing-file map. The list renders
  each curated asset once. Needed verification actions are visible on arrival.
- Failed and unfinished checks remain explicit and count toward the total looks;
  they do not count as ready. An all-failed fixture reports **0 of 2**, and an
  elapsed retry cooldown does not create a fresh two-minute promise.
- The header uses plain download/check wording. The storage panel continues to
  show its reported reserve; the fixed duplicate 20 GiB label is removed.

## Verification

The existing `frontend_handoffs.cjs` renderer fixtures cover shared dependencies,
one action per file, known filenames shown once, escaped unlisted filenames and
notes, missing/changed/unknown states, failed and pending inspection totals,
search, filtered links without health data, manual installation eligibility, and
zero writes. `preset_model_readiness.cjs` retains the dependency and installer
eligibility contracts.

`preset_model_browser.py` retains its Full editor dependency checks and adds the
actual Models view at 1440 and 390 pixels. The journey uses native file-detail
links and filter controls, verifies unlisted and unknown detail after navigation,
checks that verification controls are visible, and records native Tab/Enter
navigation, viewport geometry before any helper scrolling on the keyboard path,
screenshots, page errors, zero mutations and source hashes. Its HTTP
fixture was exercised locally: five model assets, five looks, known and unknown
inspection replies, and one intentional 503. No model or installer runs.

Local targeted qualification:

- `python -m unittest discover -s tests -p 'test_frontend_handoffs.py' -v`:
  30 passed, including the shipped renderer and existing Make/History handoffs.
- `python -m unittest discover -s tests -p 'test_preset_model_*.py' -v`:
  39 passed, including HTTP readiness, occupied paths and installer eligibility.
- Direct `frontend_handoffs.cjs` and `preset_model_readiness.cjs` runs passed.
- `node --check app/static/app.js`, Python driver compilation and
  `git diff --check` passed.

Reconciled with merged Make main `4a59dabb0fb8f402317590e115369fe52601e73f`
through exact local mirror `54c23469859a3515f04f321a203c0d544ffb0207`, tree
`045af753398cb85451d391c4dd22eeeebfc156be`. The merge was conflict-free,
including both guide additions. Fresh qualification on merge commit `5ae9039`
again passed all 30 frontend wrappers and 39 model tests. The repository
validator passed: 98 preset graphs/bindings, 194 pinned assets, 4,892 tracked
paths, 167 LoRA names, and 743 local-media entries with 102 references checked.

At this point native Chromium and the full repository gate were pending
hosted CI; no local browser proof was claimed. This change does not establish
owner workstation, artwork, licensing or broader Models redesign acceptance.

## Hosted visual review and bounded corrections

The first hosted browser assertions passed on remote head `d040de2`, but visual
review of artifact `13385490475` rejected qualification. The retained
`models-summary-390.png` and `models-needed-files-390.png` showed part of the
search label behind the privacy row. The placeholder in the look summary grew
to about 123 pixels wide. `models-unknown-file-390.png` also showed
`Cannot read properties of null (reading 'controls')` in the environment status,
despite an empty uncaught `page_errors` list. These captures remain failed visual
evidence; the green assertions did not establish a clean page.

The toolbar now follows `privacy.css`'s existing extra 32-pixel header row at
widths up to 700 pixels. The look text flex rule excludes `.look-thumb`, leaving
the placeholder's existing 44-by-44-pixel rule in control. Installer and focus
owners are unchanged.

The environment error was a production startup race. With no selected recipe,
`application?.preset_id` and the requested recipe ID were both `undefined`;
the equality passed and the Looks reader dereferenced a null application.
The adjacent prepared-payload reader had the same absent-owner comparison.
Both readers now require their corresponding owner object before comparing
recipe IDs. The global preparation hold and matching failed-application blocker
remain intact. No backend request or retry behavior changed.

Before the guard change, the added `looks_frontend.cjs` case threw the exact
null-`controls` error. The added `backend_refresh.cjs` case reproduced the same
caught error in `#backendStatus` through the shipped backend/readiness path,
with the catalog held and no recipe selected. Both now pass, including the
healthy status after the catalog is released and zero writes.

The browser driver now holds the original catalog GET, refreshes through the
existing backend read owner after classic scripts mount, checks healthy startup
status with Generate disabled, and forwards the held GET. Every Models journey capture
records and asserts the actual search-label bounds and hit targets against the
occupied header, including after native keyboard scrolling; summary captures
also assert 44-by-44 placeholders. It checks the expected healthy backend status
and visible error/alert panels as well as uncaught errors. Receipts now hash the
Looks and backend owners too. The original dependency captures retain their
content/control scope; they do not prove full-panel visibility above the run dock.

Fresh local checks after these corrections: 19 direct Look checks, 13 preparation
ownership checks, 48 backend refresh checks (also through their Python wrapper),
all 30 frontend wrappers, and all 39 model-readiness tests passed. JavaScript
syntax, Python driver compilation, `git diff --check`, and the repository
validator passed with the same counts recorded above.
Corrected native captures and the full gate remain pending hosted CI and visual
review. No corrected native-browser pass is claimed locally.
