# Multi-asset brief verification

28 October 2026. This record covers the standalone prototype at
`docs/prototypes/multi-asset-brief`, based on main `3392d27`.
It does not qualify a production integration or an accepted asset set.

## Executed

| Check | Observed result |
| --- | --- |
| `node docs/prototypes/multi-asset-brief/check.mjs` | 14 passing checks: media kinds, replacement/undo, wrong-kind refusal, persistence, malformed drafts, blocked routes, look and scene request shapes, explicit returns, stale wording/requirements/source refusal, empty searches and inert transport boundary |
| `py -3 docs/prototypes/multi-asset-brief/check_contracts.py` | Actual production collection/asset reader validators accept the fictional pages and refuse foreign Workspace identity. Catalogue look/preset IDs and media kinds match. No transport is opened |
| `node --check .../app.mjs` and `.../browser-check.js` | Pass |
| `py -3 scripts/validate-repo.py` | Pass: 94 graph bindings, 189 pinned assets. Final tracked-payload check is repeated after staging the prototype |
| `browser-check.js` in local Chromium | 25 checks pass at 1280 × 900: replacement, back/forward with search context, undo, edit persistence, image/scene handoffs and explicit returns, five blocked/unsupported routes, empty/failed Library recovery, audio replacement, six filled slots retaining six review gaps, cross-slot route refusal, escaped markup, no API/external resource requests, no horizontal overflow |
| Actual browser reload | Edited title, brief, icon wording, background/audio choices and synthetic return references retained. Preparation authority is dropped |
| Native keyboard input | Enter follows the asset-picker link and chooses a candidate; return focuses main. Enter opens reset with focus on Keep; Escape closes it and returns focus to Reset |
| 390 × 844 mobile emulation | No horizontal overflow; all six slots and return path remain present. Reduced-motion preference matches and the notice animation computes to `none` |
| Storage fault injection | Quota refusal retains the editable in-memory draft with a visible warning. Malformed saved bytes are preserved while a sample draft is edited. A dispatched cross-tab storage event stops writes and explains reload/download recovery |
| Browser console and network | No errors/warnings. Only same-origin static GETs for HTML, CSS and three ES modules; no API/XHR/fetch/beacon traffic or POSTs |

The browser assertions drive real rendered controls and history in Chromium.
Storage failures use browser-side fault injection. The cross-tab check injects
the native event; it is not a two-browser concurrency trial. Fixture validators
and inert browser checks do not prove real Studio source intake or execution.

## Resource and process evidence

The existing shared heavy-job helper admitted the static preview at 23:50 UTC
with **9.94 GiB free**. One browser tab and one static Python server were used,
with no test workers, GPU job or model process. The preview served only this
prototype directory on `127.0.0.1:8471`. The owned Python server PID 6080 was
identified by its full command before stopping it. Its port was then free and
the helper released its lock. The browser tab was closed. Stopping the indefinite
server reports helper exit `-1`; that is teardown, not a failing test result.

Selected captures and raw journey/network/console evidence are retained locally
in the task's `multi-asset-brief/evidence` artifact folder. The screenshots show
the initial desktop brief and a narrow returned-candidate view. They contain
fictional content only. They are deliberately outside the public repository.

The design detector reported undersized metadata labels. The final CSS raises
8–10px labels to 11px and lets the top bar wrap. Wide/narrow confirmation of that
mechanical correction is pending the next resource window; the first captures
precede it. Its generic 11px-text advisory is retained as a compact metadata
tradeoff, not a WCAG conformance claim. Wide tracking applies only to the short
uppercase preview label. No second detector or broader design audit is planned.

## Limits

No full Studio suite, hosted CI result, production integration, live backend or
model readiness, inference, native export, real media-byte validity, licensing,
screen reader, physical phone or owner art acceptance is established here.
No production app/catalog file is changed. A later production implementation
must run the declared full unittest and repository gates plus its real boundary
checks. The prototype does not waive them.

The storage key is prototype-only. Download is a JSON copy, not an import format;
browser-managed download placement has not been tested. Text and references stay
local, with no cloud sync or cross-device recovery. There is one fixed fixture
page; real collection paging remains owned by the existing reader.

`HUMAN_TODO.md` remains unchanged. Existing UX, art/look, licensing, asset intake
and parallax decisions stay with the owner. Refs #313 and #772 retain all of their
real asset and production-journey acceptance work.
