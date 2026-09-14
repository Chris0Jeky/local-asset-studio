# Keep your place while the library updates

## What changes

A refresh should update the information you are looking at without throwing away
the controls you are using. This slice keeps an asset card and its unchanged
preview in place when the library is refreshed, another asset changes, or sorting
moves the card. Checkbox selection, Favorite, Open and the saved review labels
still use the existing handlers and Workspace records.

The practical journey is: browse with the keyboard → select an asset → receive a
refresh or another client's metadata change → continue from the same control.
When that asset leaves the current view, focus moves to the same kind of control
on the next surviving card in the previous reading order, then the previous one.
If no card remains, focus returns to Search. Refreshing beneath an open review
dialog does not move focus out of the notes you are editing.

No setting, selection, review, source or command is changed by this renderer.
Filtering continues to hide cards without clearing the separately owned selection.
A card that leaves the view is removed, not retained in an invisible cache.

The 14 September integration with the review queue also retains grouped sections.
Changing groups, reordering several cards in one group, and moving a card to another
group preserve the card and unchanged preview. A saved review uses the same projection
without fetching the Workspace again, so cached nodes and the Review next count stay
consistent. Labels and counts update as text; unchanged grouped refreshes make no grid
DOM mutations. The browser fixture uses its own ephemeral loopback port and a strict
test-local Host check, leaving a running Studio on 8191 untouched.

The combined native HTTP/Chromium regression passed all 39 checks on Windows, with no
page exceptions or mutation/generation requests. Before the group reconciliation,
its first three unchanged-refresh controls passed and its combined grouping/count
check failed. The older 31-check records below remain historical evidence for their
original scope. One intermediate native probe logged a server-side Windows socket
abort during preview replacement; the final probe passed without that diagnostic,
which does not establish warning-free behavior or resolve #227.

## Why the old behavior failed

At baseline `2f91421ecbe0e014cceef1074f4d79e4c57051df`, `renderAssets()` assigned the
entire grid's `innerHTML` on every render. The outer Workspace signature already
avoided some unchanged polling work; this is **not** a claim that no guard existed.
A forced refresh, any changed Workspace snapshot, sorting and selection renders
still replaced every card. The same-image elements and focused checkbox were
lost, even when only another asset's metadata changed. Removing a video did not
explicitly pause it or release its source.

The final matching browser baseline records 31 expectations: 13 passed, 18 failed.
The patched driver passes all 31 locally in explicitly inert mode. These are
expectations, not 18 independent defects or a whole-product quality score. The
JSON checkpoint records each matching ID. Native hosted proof is recorded in the
PR when its actual current-head run is inspected, not assumed from local success.

## Implementation and boundaries

`app/static/asset-grid.js` is a small DOM projection, loaded before `workspace.js`.
The existing card markup was extracted into `assetCardHTML()` without changing
its escaping, labels or delegated selectors. The renderer receives that function,
the already-filtered/sorted asset list, current selection, Workspace ID and the
existing empty-state markup. It neither reads nor writes the network or storage.

A WeakMap keyed by grid element retains only the current visible rows. Each row
holds its DOM node and two compact signatures. It is not a metadata store:

| Identity or state | Purpose |
| --- | --- |
| Workspace ID + asset ID | Determines whether a card may be reused. A different Workspace clears the old projection even for coincident IDs. |
| Media type + URL + retained SHA-256 | Determines whether to retain the preview element. A changed source replaces only the preview, not the card's controls. This is comparison of supplied identities, not new byte verification. |
| Displayed metadata + selection | Determines whether labels, tags and review display need updating. Notes, revisions and undisplayed tags alone do not invalidate the card. |
| Actual checkbox/class state | Reconciled even when the previous render signature matches, because checkbox events update DOM directly between renders. |

Existing rows are moved rather than rebuilt. In browsers that provide
`moveBefore`, the renderer uses the state-preserving move. The standard
`insertBefore` fallback keeps the same node and restores its focused control with
`preventScroll`. Both branches are tested. **The fallback does not promise
uninterrupted media playback or preserved decoder state during a move.**

Focus is captured synchronously when the grid is rendered, not when a request is
started. Only focus previously inside this grid is restored. A dialog, Search or
another control remains its owner; the renderer does not steal focus from it.
Unchanged empty-state markup is also reused so its recovery button stays focused.

Before removing/replacing a preview, the renderer pauses audio/video, removes
`src` from media and child source elements, and calls `load()` to reset resource
selection. Image `src` is removed before disposal. The explicit asset-detail
preview is a different owner and is not touched.

### Alternatives considered

Rebuilding all cards and refocusing a matching selector would fix part of keyboard
navigation but would still replace the media elements. A full virtual-DOM layer or
new framework would duplicate substantial existing state machinery. Keeping every
filtered card hidden would retain media and grow the cache. This targeted renderer
retains only visible rows and leaves discovery, filters, commands and recovery with
their existing owners.

### A regression caught during implementation

A signature-only shortcut incorrectly retained a checked box after this sequence:
render unselected → check via the existing delegated handler → Clear selection.
The handler had changed DOM without updating the renderer's earlier signature.
`GRID-27` reproduced the stale visual state before correction. The renderer now
reconciles live checkbox and selected-class state before its metadata shortcut.
The final baseline already passes this case; it is an implementation regression,
not relabelled as a defect on main.

## Verification and repeatable QA

```sh
python -m unittest discover -s tests -p 'test_asset_grid_frontend.py' -v
node tests/asset_grid_contracts.cjs
python -m unittest discover -s tests
python scripts/validate-repo.py
# Disposable development/CI environment only, not managed ComfyUI Python:
python -m pip install playwright==1.57.0 -r research/game-assets/requirements-media.txt -r tests/requirements-runtime.txt
python -m playwright install chromium
python tests/asset_grid_browser.py --out .runtime/asset-grid-proof
```

The driver owns a temporary SQLite Workspace and loopback fixture on port 8191.
It refuses an occupied port; do not point it at a real running Studio. Production
Workspace reads are used; writes simulating another client occur in the temporary
fixture only. Page POSTs are recorded by the existing inert API fixture and must be
limited to estimate/reference checks. No generation or owner media is involved.

`--baseline` retains failed expectations but never accepts JavaScript exceptions,
incomplete runs or execution errors. `--inert` is available only as an explicitly
labelled component mode when native navigation is policy-blocked: storage and
fetch are substituted while actual HTML/JS/CSS and Python HTTP are used. Local
native navigation failed with `ERR_BLOCKED_BY_ADMINISTRATOR`; that failed attempt
is retained. Native session/origin behavior is not inferred from the local pass.

Nine Node scenarios cover identity and focus ordering in the actual module. They
count as one unittest wrapper. The existing fake-DOM detail/library contract
harness substitutes **only** rendering with a markup projection: it still tests
existing selection/recovery policies and does not pretend to test DOM identity.
The new full-shell driver tests the real renderer and delegated controls.

The full browser scenarios cover unchanged and changed snapshots, title/tag/alt
updates as text, new rows, reorder, removal, empty views, source/Workspace change,
video release, focused unsaved notes, actual checkbox delegation, immediate Clear
selection, zero DOM mutations on unchanged grid, the move fallback, source-hash
invalidation, and 1440px/390px layout. Two earlier fixture errors (quoted URL test
text and returning an unbound native function from evaluation) are kept in raw logs
and excluded from the matched completed comparison.

## Remaining work under #177 / #16

This is not pagination or a complete resource budget. Workspace payloads and the
number of visible cards remain unbounded; each render still walks the visible
records. There are no measured heap, transfer, GPU or decoding improvements here.
The video fixture deliberately tests DOM cleanup with a synthetic non-decodable
source, not real video playback. Full media lifecycle/decoder measurements,
1,000/10,000-item datasets, proxies/thumbnails, off-page selection resolution,
actual zoom and screen-reader acceptance remain separate.

Sidebar collections, collection destination options and other independently
rendered panels are not converted to keyed rendering in this slice. Their focus
behavior is not certified by the grid checks. Broader task guidance and the
owner's creative/licensing decisions remain open. No HUMAN_TODO item is changed.

Rollback is the ordinary revert of this PR's renderer, script inclusion and call
site. No database migration, file format, stored metadata or command protocol is
changed.

## Primary interaction references

Reviewed 14 September 2026: [DOM Standard, moveBefore](https://dom.spec.whatwg.org/#dom-parentnode-movebefore)
for state-preserving moves; [HTML media resource location](https://html.spec.whatwg.org/multipage/media.html#location-of-the-media-resource)
for the distinction between removing `src` and invoking the load algorithm;
[W3C keyboard interface guidance](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
for persistent, predictable focus. These inform implementation choices and are
not a claim of accessibility conformance or measured performance.
