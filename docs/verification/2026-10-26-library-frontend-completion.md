# Library frontend completion evidence

Refs #1627. This slice builds on the bounded backend contract in
[Library read completion](2026-10-26-library-read-completion.md). The initial
frontend commit is `c5330ee`; integrated native runs used backend commit
`4914533f` and the native browser observation fixture from `d0c5ec7`.
Hosted qualification and merge status belong to the final PR head.
The final local native Library rerun also passed all 15 checks after backend
correction `8f998268`, on integrated local head `5d11d29`; its separate receipt is
`.runtime/library-page-final-head/receipt.json`. Publishing preserves the tested
file blobs while reconciling the AV and recovery predecessors.

## Observable behavior

- Library pages request their collection bundle in the same observation. Complete
  editor records and unavailable detail rows remain separate. Counts explicitly
  say which page or loaded result they describe; there is no catalogue-wide count.
- An accepted own write marks the retained page boundary for explicit server
  reanchoring. The page does not jump to the newest hundred assets. Historical
  Previous anchors may reanchor after that write; Next stays strict. A refusal
  leaves the confirmed receipt, current page and complete selection intact.
- A post-write page resolves retained unknown selection IDs in one bounded read.
  A missing Recent output is not queried again until the catalogue changes.
  Unavailable rows on the page do not trigger an automatic detail retry.
  A refused supplemental off-page observation cannot hide complete rows from an
  already accepted page; the unresolved details remain explicitly unavailable.
- Combine tiles distinguish unloaded saved reviews from unreviewed assets. Load
  saved checks is a selected-ID observation. Engine/run counts use the canonical
  known records and explicitly identify the loaded scope, including Trash at
  timestamp zero. Setup, Workspace and Workspace epoch changes retire held work.
- Family references resolve the requested off-page image before using the
  existing source picker. Figure receipts resolve their exact child IDs without
  adding them to the Library page. A foreign Workspace or A-to-B-to-A transition
  blocks late child observation while the original split remains confirmed.
- Same run offers explicit reads of at most 20 active outputs for one exact job,
  with Previous/Next and no page drain. Canonical observations supply complete
  metadata while the Library page keeps its own IDs and order. The existing
  detail draft guard owns navigation to a sibling.
- Source-picker unavailable rows retain escaped IDs/reasons and an observed
  denominator. All-unavailable pages do not claim that no saved images exist;
  mixed pages offer only complete records. Explicit continuation retains the
  observed evidence, and a new search replaces it.
- Review queue transitions have their own identity. An older unsuccessful open
  cannot move the position after a newer open succeeds.

## Causal contracts and independent review

The tests execute shipped production functions with controlled asynchronous
responses. The initial 17 off-page consumer contracts all failed before their
implementation. The initial 20 paging contracts likewise failed before their
implementation. Five additional paging race tests reproduced held-cursor,
Workspace, collection-continuation and unavailable-row problems before their
guards were added. Further tests reproduced figure Workspace ABA, reverse-order
queue completion, three source-picker unavailable-page cases, and an accepted
page hidden by a subsequent selected-ID refusal.

Current results:

| Execution | Result |
| --- | --- |
| `node tests/library_offpage_frontend.cjs` | 22 passed |
| `node tests/library_page_frontend.cjs` | 26 passed |
| Existing Workspace pagination contracts | 14 passed |
| Existing canonical metadata-cache contracts | 18 passed |
| Existing detail contracts | 28 passed |
| Family adapter, handoff, Make, source, recovery and off-page consumer contracts | 96 passed |
| Gallery handoff harness, including 30 delayed parallax schedules | passed |
| Python wrappers for the two new contracts and metadata frontend contracts | 6 passed |

Independent review reproduced the queue race by resolving the second of two
off-page moves first, then independently confirmed that the transition owner
keeps the successful editor and position together. It also reproduced the
source-picker false empty state and independently confirmed the unavailable
projection, escaping and continuation correction.

Existing controlled fixtures were updated to return one complete atomic bundle,
not two synthetic reads. A malformed catalogue page now refuses before replacing
accepted records; the metadata-cache test checks that refusal and its positive
control. One local Node 24 test-runner wrapper reported the file as one test when
process isolation was enabled. Running that same consumer file with
`--test-isolation=none` executes all five tests successfully. Hosted workflow Node
22 remains the authority for its normal runner mode; no global Node options were
changed.

## Native Chromium evidence

Local Python 3.12.14, Playwright 1.56 / Chromium 141, synthetic media and disposable
SQLite Workspaces; no model execution or installed runtime changes:

| Native flow | Result | Local evidence |
| --- | --- | --- |
| 205-asset Library, one oversized row, page-two star/bulk edit, cross-page selection, strict Next and historical Previous | 15 checks passed, including the same-run and narrow-screen checks below | `.runtime/library-page-verified/receipt.json` |
| 25 same-run outputs browsed as 20 then 5, exact sibling open and draft consent | passed in the Library flow | `.runtime/library-page-verified/same-run-390.png` |
| Unavailable detail disclosure at 390 px | passed, document width 390 px | `.runtime/library-page-verified/unavailable-page-390.png` |
| Figure editor success, exact retry, lost response, off-page children, foreign Workspace and ABA | 12 scenarios passed | `.runtime/library-figures-final/receipt.json` |
| Family navigation, recall, draft guard and off-page existing source picker | passed at 1440 and 390 px, zero generation, unchanged Workspace | `.runtime/library-family-verified/report.json` |
| Source picker unavailable/mixed rows, escaping, paging, search and existing ownership | 4 native tests passed | `workshop_daily_journeys.DailyJourneys` targeted methods |
| Existing Combine second-engine journey | passed, zero generation requests and no page exceptions | `.runtime/library-combine/matrix.json` |
| Original Studio browser smoke | exit 0; no browser exceptions or generation/setup mutations | `.runtime/library-smoke/` screenshots and tool log |

The first native Library passes found fixture interaction mistakes: a collapsed
details element needs `text_content` for its hidden ID, Resolve is inside the
selected-assets disclosure, and a hidden selection needs its existing explicit
confirmation. Correcting those interactions kept the production guards intact.
The subsequent native failure was a real layout defect: the global navigation
flex row laid the unavailable disclosure beside the page buttons and expanded
the Library to 522 px at a 390 px viewport. Scoped wrapping and ID word breaks
corrected it. The failing geometry and screenshot remain in
`.runtime/library-page-layout-details/`; the passing evidence is separate.

The existing Asset detail workflow now runs the two new causal harnesses and
`library_page_browser.py` on its zero-delay matrix, and uploads the native
receipt/screenshots with the other workflow evidence.

## First hosted qualification and retained failures

The first published candidate, PR #1660 head
`12ff76929dea86b847a17382632368d87a051f3f`, exposed two browser-fixture defects:

- [Workshop job 121692466588](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357121717/job/121692466588)
  failed because its extracted `refreshAssets` fixture omitted the new Workspace
  epoch and still supplied two independent asset/collection responses. The exact
  `ReferenceError` was reproduced locally. The fixture now extracts the real
  Workspace-identity observer, supplies its state, and asserts one combined
  details/collections observation. Busy rejection, failed-read preservation and
  successful Workspace adoption remain checked. The entire 54-test native daily
  journey suite passed in 18.409 seconds, with no page exceptions.
- [Model-readiness job 121692468637](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357121688/job/121692468637)
  measured a card after a concurrent inventory/model-use response replaced it.
  A controlled real refresh reproduced the detached handle's zero width and
  empty computed whitespace. The fixture now looks up and measures the current
  card in one browser operation. Both overflow assertions and the exact
  `pre-wrap` assertion remain, with positive-width checks added. Its native
  1440/390/320-pixel runs passed with recovery widths 331/318/248, literal hostile
  path and cleanup text preserved, no mutations and no page exceptions.

Independent review found no blocker in either fixture correction. These changes
do not modify production CSS, raise timeouts, or relax the failed assertions.
Original hosted logs and local causal/green runs were kept separately under
`.runtime/model-recovery-review/` and the session's Workshop verification logs.
Fresh hosted qualification of the corrected candidate is still required.

The same candidate also exposed a real two-tab shelf lost update in
[Ubuntu job 121692469089](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40357121775/job/121692469089).
Both writers returned success while only one viewpoint survived. Artifact
`12667150927` retains their outcomes, generations and digests. That product
correction is owned by parent PR #1659 and reopened issue #825; the earlier
passing shelf runs do not supersede this failure. Library merge qualification
includes the corrected parent and its native evidence.

## Limits

These flows establish bounded per-request reads, truthful loaded/page counts and
ownership under the tested schedules. They do not establish a browser memory or
query-time budget for every catalogue, nor artistic, licensing or engine
acceptance. Explicit picker continuation still accumulates the pages the operator
chooses to load. Broader resource budgeting remains in #177, and owner decisions
in `HUMAN_TODO.md` remain open.
