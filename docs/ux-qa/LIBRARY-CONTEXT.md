# Asset library: visible context and deliberate selection

## Checkpoint and scope

This pass starts at main `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`.
#199, #202, #211 and #216 are merged. No open PR was returned by the initial
repository check. The changes extend the existing library in `workspace.js`;
they do not introduce another journal, guide, persistence boundary or executor.

Refs #16. #177 remains the owner of real pagination, thumbnails and scale
measurements; rendering 205 synthetic rows here does not satisfy it. #204's
wider recovery/lifecycle work remains separate.

## Practical journey and confirmed failures

Select two illustrations, search for one, then organize or export the selection.
The original library preserved both selected IDs but showed only a total.
Favorite, pack export and native/scene handoffs could act on hidden selected
items without acknowledging that the displayed results were narrower. “Select
visible” silently truncated to 200 while manual selection could exceed that
limit. A populated Trash with a nonmatching query said it was empty. Scope-empty
Favorites and collections suggested generating rather than explaining the
actual view. Another real-HTTP test held a bulk request, changed the selection,
then confirmed that its late success erased the newer selection.

The baseline also revealed a layered UI detail: the workbench adds **Awaiting
review** through a wrapper. Its scope must be applied before computing totals
and empty-state reasons, not only to the final card list. It is now handled in
the shared scope projection; the existing wrapper remains compatible.

## Implemented interaction contract

| User action or state | Expected behavior |
| --- | --- |
| Search or change media type | Keep selection; show matching count within this scope, plus visible/hidden selected counts. |
| Review selected assets | List up to 200 selected titles, including outside-view, Trash and unavailable status. Render user text escaped. |
| Activate a bulk action with hidden items | Explain the hidden count and ask before continuing with the entire selection. Cancel sends no action. |
| Activate with unavailable/oversized/foreign-Workspace selections | Refuse locally and explain how to review or reduce the selection. Do not silently drop IDs. |
| Keep only visible | Intersect checkbox selection with the current view, without rewriting an earlier pending command; focus Search. |
| Clear filters | Reset search and media type only. Keep sort, scope, selection, editor draft and pending command. Focus Search. |
| Browse all assets from an empty scope | Reset filters and move to All assets using the existing scope transition. |
| Select visible above 200 results | Label “Select first 200 of N” before activation, select in current sort order and explain the remaining matches afterwards. |
| Try a 201st checkbox | Refuse that check and retain the existing 200. |
| Late confirmed bulk response | Clear an unchanged selection as before; retain a selection whose IDs/order changed while waiting. |
| Saved review `selected` | Display “Keeper” / “Keepers” in the library, not an ambiguous checkbox-selection label. The stored enum is unchanged. |
| Empty scope or filter miss | Distinguish no matches, empty Favorites/Keepers/Awaiting review/Needs work, empty or unavailable collection, empty Trash and all originals being in Trash. |

Desktop search/type/sort share a compact row. On narrow screens the selection
panel is in normal document flow instead of covering the gallery as a sticky
panel. Both the match count and selection explanation have polite status
semantics. This is not a claim of full screen-reader conformance.

## Architecture and trade-offs

`assetScopeAssets()` owns scope membership; `visibleAssets()` applies the search,
media filter and sort to that projection. `assetSelectionInfo()` resolves the
independent ID set against the loaded Workspace with a map. Counts, the selected
list and action checks use this same projection. No server-side metadata meaning,
asset lineage, reference role or generation readiness changes.

The alternative of silently clearing hidden selections was rejected: it would
lose intentional multi-filter organization work. Automatically acting only on
matching results would also change the meaning of an existing selection. The
chosen approach preserves IDs, makes them inspectable and requires a decision
only when the ordinary action includes hidden items.

The capture-phase click guard covers the existing bulk buttons, native-export
button and scene link, including keyboard activation. Existing scene eligibility
and downstream native/export/execution checks still apply. This is a UX guard,
not an authorization boundary: context-menu link opening and programmatic/direct
API use are not certified by the click test. Metadata remains revision- and
Workspace-checked by the existing command service. A loaded snapshot is not a
freshness guarantee; another client's metadata changes can still produce a
normal conflict. No action retries itself.

An acknowledged bulk response compares its captured ID sequence with the current
selection before clearing. A changed sequence is kept. Deliberately returning to
exactly the same sequence is treated as the same selection; no new interaction
history or persistent selection revision is introduced. Existing unconfirmed
command bodies and journal selection remain independent and immutable.

Only the selected-item disclosure is bounded at 200. The grid and Workspace
payload still scale with the whole library; #177 is not solved here. Native
formats may impose stricter limits than the library's 200-item action ceiling.

## QA and evidence

`LIBRARY-CONTEXT-RESULTS.json` records matching expectation IDs, before/after
results and production source hashes. The same full-shell driver was run against
an isolated checkout of original main and the candidate:

- Baseline: **31 browser expectations, 7 passed / 24 failed**.
- Candidate: **31 passed / 0 failed**, no JavaScript exceptions.
- Actual-script contracts: **14 passed**, counted as **one** ordinary unittest
  case. Their full baseline run fails all 14; the initial 12 and subsequent
  scope/Trash regressions are also retained separately.
- The held-request regression first failed on the old late-clear behavior, then
  passed after the current-selection check.
- One failed fixture attempt toggled an already-open disclosure closed. DOM
  evidence showed the unavailable item existed but the fixture hid it. The
  corrected test opens the disclosure only when closed; that attempt remains
  recorded, not presented as a product defect.

Browser actions exercise the actual shell and production metadata HTTP against
a temporary SQLite Workspace. Exactly two deliberate metadata commands are
expected in the passing run: confirmed Favorite for two IDs and the held Keeper
update for one ID. Canceled actions, filters, selection changes and handoffs send
no metadata/export/generation command. Source registration and initial fixture
metadata are setup, not counted as browser writes. The 205-row selection case
is explicitly in-memory UI data, with library refresh paused for that phase;
it is not a real-media/database-scale benchmark.

**Local limitation:** native navigation returned `ERR_BLOCKED_BY_ADMINISTRATOR`.
Successful local browser receipts therefore identify `--inert`: actual HTML,
JavaScript and CSS plus real HTTP/SQLite metadata, but substituted browser
storage/API transport. Native origin/media loading is unverified locally. The
existing **Asset detail workflow QA** lane now runs the default native driver
and publishes its receipt/screenshots with seven-day retention. Hosted results
must be read from the current-head run, not inferred from this local checkpoint.

Full final offline suite: **1,675 run, 1,659 passed, 16 skipped, no failures**
(118.699 seconds). Validator: **66 graph/binding contracts, 121 pins, 86 LoRA
names, 1,136 tracked paths**. The 14 actual-script scenarios are one unittest
wrapper, not additional suite cases. Existing Pillow deprecation and exit-time
socket warnings remain in the saved logs.

During publication main advanced to `3d3135a17811d2e4846ada05aae35e06f60d92f4`
through #226. Its changed files do not overlap this slice. The local results
remain tied to pinned main plus this patch; hosted PR merge-candidate checks
provide the separate integration observation.

## Reproduce

```sh
node tests/asset_library_contracts.cjs
python -m unittest discover -s tests -p 'test_asset_library_frontend.py' -v
python tests/asset_library_browser.py --out .runtime/asset-library-proof
# Explicit component mode only when native browser navigation is policy-blocked:
python tests/asset_library_browser.py --inert --out .runtime/asset-library-component
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Use the existing development/CI Playwright installation, never the managed
ComfyUI environment. The fixture binds only its own allowed loopback port 8191
and refuses an occupied port; it does not attach to or stop a running Studio.
`--baseline` relaxes expectation failures only, never page exceptions or execution
errors. Compare matching IDs and modes. Runtime logs, screenshots and temporary
fixtures remain outside tracked source.

## Next practical slice

Before adding pagination under #177, retain this selection contract across pages:
explicit counts of selected-but-not-shown assets, stable IDs, a reviewable action
set and no silent pruning on inserts/deletes. Add cursor/summary endpoints and
scale measurements under the existing Workspace boundary, not a second browser
asset store. Larger lifecycle and stale-export behavior need separate tests.

No new human creative decision is required. Existing `HUMAN_TODO.md` decisions
and outstanding artwork/quality acceptance are unchanged; no generated work,
model terms or licence is approved by these software checks.
