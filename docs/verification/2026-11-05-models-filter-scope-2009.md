# Models status-filter scope — 5 November 2026

Refs #2009. This is a bounded follow-up to the Models summary slice in #2018.
Its base is local `8994688`, tree `b5701bfd65c3c47138cbf437c0e00f744e899f75`,
equivalent to published head `8c034c77fe2a06a17fb4408be1b667482da6a568`.
The earlier slice's successful native receipt and its retained failed-before
captures stay unchanged.

## Observed ambiguity and change

The earlier native artifact `13385283345` showed **Show Installed** beside a
required-file view containing missing and unchecked cards. That behavior was
already present in main: a `need` route deliberately keeps required cards
visible, while the status menu continues to filter the **Files on disk** list.

The menu now reads **Files on disk below** in a required-file view. Its visible
text also supplies the select's accessible name. The normal catalog retains
**Show**, and the select remains available. This changes only presentation:
the status value, saved choice, search, hash/page query, required-card selection,
inventory filtering and request handlers keep their existing behavior.

Browser Back returns to the normal label with the current status choice.
The existing **Show everything** action separately clears the top search and
selects Everything; it does not clear the lower inventory search.

## Regression and qualification

The added frontend contract failed on the base with actual **Show** versus
expected **Files on disk below**. After the change,
`node tests/frontend_handoffs.cjs` passed. The contract exercises both hash and page-query
need routes, ordinary Installed filtering, missing/unchecked required cards,
inventory status, saved choice, unchanged route values and zero additional API reads/writes
from rendering the scope. JavaScript syntax and Python driver compilation passed.
All 30 `test_frontend_handoffs.py` wrappers passed. The repository validator
passed: 98 preset graphs/bindings, 194 pinned assets, 4,893 tracked paths,
167 LoRA names, and 743 local-media entries with 102 references checked.

The existing `preset_model_browser.py` journey now goes from Installed through
native View files activation and actual browser Back. It checks the accessible
name, visible label and select geometry on required-file and return views,
preserves the Installed value and saved choice on Back, and keeps the separate
Show everything reset checks. The longer label is checked against the actual
header at 1440 and 390 pixels; existing target, search-label, placeholder,
runtime-error and no-model-mutation assertions remain. New return captures use
native Tab focus before any helper scrolling.

Fresh native screenshots and the full repository gate remain pending hosted CI
for this follow-up; no new browser pass is claimed locally. The original editor
dependency captures retain their content/control scope, including their narrow
run-dock visibility limitation. This slice does not complete #2009 or settle
owner workstation, artwork, licensing or broader Models acceptance.
