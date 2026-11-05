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

Native Chromium and the full repository gate are pending
hosted CI; no local browser proof is claimed. This change does not establish
owner workstation, artwork, licensing or broader Models redesign acceptance.
