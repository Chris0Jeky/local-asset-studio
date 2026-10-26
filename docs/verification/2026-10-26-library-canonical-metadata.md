# Library canonical metadata — 26 October 2026

Refs [#1627](https://github.com/Chris0Jeky/local-asset-studio/issues/1627). This is the
ordered child of [#1650](https://github.com/Chris0Jeky/local-asset-studio/pull/1650),
based on local `ab4998cacd5fd26eec98806fde7501692f05ce40` from published parent
head `67ad50e3b4c4999b0fa31b2426d6600a4b5f2fe7`. All five preexisting files
changed by this slice were independently fetched from parent merge
`554ca3d58c838648fa1fdf16ff104bd26aefd639` and matched their local baseline blob
IDs. The parent's successful hosted qualification does not qualify this later code change.

## Corrected behavior

An asset explicitly resolved while off page could retain a separate metadata copy
after returning to the page. Saving updated that copy, while the grid and its
favorite action still used the older page row. A resolved missing asset could also
fall through to its old page row when constructing a new command.

The two existing representations now reconcile accepted full observations. The
grid, scope counts and favorite intent use canonical records for the existing page
IDs; an off-page resolved asset is never added to the page. Explicit missing
observations remain unavailable. The receipt helper applies only the confirmed
fields to records at the command's expected revision and Workspace, without
overwriting a newer observation or changing the exact pending command.

Detail, bulk/group and ordinary Library receipts share that helper. Every accepted
owned receipt advances the held-read barrier, including idempotent or already-newer
records. Selected-ID observations repaint affected loaded cards immediately.
Separate observation epochs prevent an older page from clearing a newer selected-ID
read, or an older selected-ID reply, including missing, from overriding a newer page.
Observation-only page retries preserve the requested cursor/history and use the
existing maximum-five-read loop. A genuinely later missing observation still applies.

The change preserves page ID order and checkbox selection during reconciliation.
It does not change the existing bulk-command refresh policy or add another cache,
API, unbounded fetch, background observer or recovery store.

## Causal evidence

Code/test commits are `3b1eff1362565b8666f6bbe5aef756a5bd5b8b4f` and
`8a678624af579a5782bd0d53adee3c0d08743db5` in the isolated author checkout.
Final `app/static/workspace.js` SHA-256:
`82efcd2e83a6897abd96a484cf776683cdd6602dda0e943ef56b439044c5cdde`.

Ignored evidence is retained in `.runtime/canonical-metadata/`:

- `red-node.log`: the initial ten shipped-script contracts all failed before
  implementation, including stale title/favorite, both bulk paths, missing/Trash
  state and held-read behavior.
- `red-final-contracts.log`: the first twelve contracts run against the unchanged
  parent script through a read-only source loader produced eleven failures and one
  passing idempotence compatibility case. The working implementation was not replaced.
- `red-browser/receipt.json`: native Chromium and actual metadata HTTP/SQLite passed
  26 earlier assertions, then failed META-29 because the returned-page card retained
  its old title after a confirmed save. There were no page exceptions.
- `red-read-race.log`: independent review's held-page/newer-ID case failed on the
  first implementation: revision 2 regressed to revision 1. The other twelve
  contracts passed.
- `red-read-direction-and-repaint.log`: mixed-selection resolution left the visible
  star stale, and an older missing reply was accepted after a newer page. Those two
  cases failed while the preceding thirteen passed.
- `green-node.log`: all fifteen final cache contracts passed.
- `final-browser/receipt.json`: all 32 native HTTP/SQLite assertions passed with no
  page exceptions or generation/backend mutations. META-29 through META-32 cover
  the returned-page save, displayed favorite, next opposite favorite command at the
  confirmed revision, and unchanged page membership/selection.

## Focused verification

These commands ran against the isolated candidate. Python used the session's
Python 3.12 environment; wrappers used `NODE_OPTIONS=--test-isolation=none` with
Node 24. Native browser checks used installed Playwright Chromium on Linux and a
disposable loopback fixture, never an installed Studio or ComfyUI runtime.

| Command or contract | Result |
| --- | --- |
| `node tests/asset_metadata_cache.cjs` | 15 passed |
| `python -m unittest discover -s tests -p test_asset_metadata_frontend.py` | 4 wrappers passed: cache, 33 metadata, 14 reload-recovery and 7 quick-check interaction groups |
| `node tests/asset_detail_contracts.cjs` | 28 passed |
| `node tests/workspace_pagination.cjs` | 14 passed |
| `node tests/asset_recovery_session.cjs` | 19 passed |
| `node tests/asset_recovery_refusal.cjs` | 20 passed |
| `node tests/asset_conflict_envelope.cjs` | 34 passed |
| `node tests/asset_source_filter_frontend.cjs` | 4 passed |
| `node tests/asset_grid_contracts.cjs` | 11 passed |
| `python -m unittest discover -s tests -p test_frontend_handoffs.py` | 21 passed |
| `python tests/asset_metadata_browser.py --out .runtime/canonical-metadata/final-browser` | 32 passed; no page exceptions or generation/backend mutation |
| `node --check app/static/workspace.js` | Passed |
| `python scripts/validate-repo.py` | 93 graphs/bindings and 187 pinned assets passed |

Independent review identified the stale-read and mixed-selection repaint cases,
then reviewed the corrections and matching production hash with no blocking
findings. Published child-head CI, Windows qualification and the actual merge tree
remain the coordinator's integration gates; no new full-suite result is claimed here.

## Remaining acceptance

`receipt.current` is a bounded metadata observation, not a complete asset snapshot.
A recovered historical receipt can still require explicit current-state review:
this patch does not infer missing IDs from omitted receipt rows or promote that
partial observation into complete current media, source or collection metadata.

#1627 remains open for other page-only consumers, broader cache freshness, bulk
refresh page preservation, separate page/collection transactions and the other
recorded follow-ups. #177's browser heap/decode budgets, broader proxy/media work,
job history and inventory costs are not established by these correctness fixtures.
`HUMAN_TODO.md` is untouched; artwork, licensing, Kromoss/MOSS, parallax and runtime
owner decisions remain open. No installed package change, model download or
generation was performed.

## CI follow-up — 26 October 2026

The first published [#1651](https://github.com/Chris0Jeky/local-asset-studio/pull/1651)
head, `c4424c13843e510947aa960dd3b4fd400f8145a2`, failed two browser gates. The
following corrections supersede the earlier candidate hash and local qualification
above; those earlier results and the failed CI runs remain retained evidence.

### Preserve same-catalogue selected-ID reads

The [Recipe shortlist gate](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40253878128/job/121351439790)
timed out at `recipe_shortlist_browser.py:278`. The unchanged fixture deliberately
holds a three-ID observation, changes the Library filter to show another asset,
then releases the same selected-ID read. The implementation advanced `assetPageEpoch`
on every page response, so a harmless filter change wrongly cancelled that handoff.
The [independent Codex review](https://github.com/Chris0Jeky/local-asset-studio/pull/1651#discussion_r4373281171)
reported the same regression when an unchanged refresh interrupted an off-page open.

Local native reproduction passed 46 assertions and then hit the identical 30-second
timeout. A read-only comparison of the actual scripts confirmed that the parent
accepted this same-catalogue handoff while the first published child rejected it.
The original shortlist fixture, its held-read assertion and its deadlines are unchanged.

Commit `b366d3a170bedbaa6f351c2f2382f9efb2c00e88` advances the page observation epoch
only when the Workspace/catalogue changes. The equality exception requires a known
32-hex epoch and nonnegative safe-integer revision; absent or malformed stamps do not
qualify. Equal valid stamps across filters, pages or polls preserve the explicit ID
read. Different or unknown stamps still retire it, including a stale missing reply.
Receipt, Workspace and caller selection-ownership checks remain unchanged.

The final production SHA-256 is
`5ce11fc99100a95795371624fc4f6a30e12e16f43d3912efbba7a6e0ddbe72a6`.
The new handoff and off-page-open regressions both failed against the published
script; the equal-invalid-stamp case separately failed against the initially
proposed condition before known-stamp validation was added. All **18 cache
contracts** now pass, including the existing opposite read ordering and later
explicit missing observation. The metadata wrappers (4), pagination (14), ownership
(19), source filtering (4) and syntax checks passed. Independent review reran 18
cache, 14 pagination and 7 interaction groups and found no blocker.

The unchanged native Recipe shortlist fixture then passed **82/82 assertions**, with
no page exceptions or generation/install/switch/asset writes. Its expected server
BrokenPipe traces from deliberately aborted requests remain in the logs. Evidence
under `.runtime/canonical-metadata/` includes `shortlist-red.log`,
`shortlist-published-red.log`, `shortlist-unknown-stamp-red.log`,
`shortlist-final-contract.log` and `shortlist-final/result.json`.

### Supply the Workshop fixture's extracted-function dependencies

The [Workshop gate](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40253878170/job/121351440057)
failed because its extracted `refreshAssets` function did not receive the new epoch
globals. A causal probe showed that missing `assetObservationEpoch` returned false
before any read was requested, leaving `pending[0]` undefined. Supplying only that
global reached both reads but then failed on missing `assetPageEpoch`; supplying both
restored the existing success/failure/busy contract.

The fixture correction, originally `5f94652f1577b6fd3170c23be8f1ff468500ab73` and
integrated as `943e597175959f17ec9067b463b070f300af4e99`, adds only those two globals.
It changes no production code, assertion or deadline. The author's existing 53-test
native fixture passed in 13.575 seconds; the combined correction above passed all
**53 tests in 14.300 seconds**. The original red log and dependency probe are retained
in the author's `.runtime/workshop-fixture/`; the combined run is
`.runtime/canonical-metadata/workshop-combined.log`.

Repository validation passed 93 graphs/bindings, 187 pinned assets and 4,455 tracked
paths. The corrected published head needs its own CI and merge-tree qualification;
the first head's incomplete/failed gates are not reused as a green verdict. The
remaining #1627 scope and owner-acceptance limits stated above are unchanged.
