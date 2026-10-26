# Recovery import and keyboard qualification — 26 October 2026

Refs #392 and #393. This work extends the existing shelf and its native browser
fixture. It adds no recovery store, server metadata writer, retry mechanism,
generation, runtime installation or owner acceptance decision.

## Reconciled source

The starting source is authoritative main
`7a89410d34c2580c3b9d47ffd806193e006d4069`, tree
`03910d64c2dd16db1cb45ff92b6330f927e6e083`. The local baseline is a reconstruction
whose complete tracked blobs and modes match that tree; its commit identity is
different. The coordinator owns publishing, current-main reconciliation, hosted
CI and actual merged-tree verification.

The final local native run used these exact SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `app/static/asset-recovery-shelf-ui.js` | `2313d3b6cb74d1a4cdee339807707b0f520e4344a7a939eba9f3b3cba27e25f2` |
| `tests/asset_recovery_shelf_browser.py` | `67ed5210564556ec28e15f3c06a0e1e9e3a78ff8c9ad19307f0f770aded7d04b` |

## Three reproduced UI defects

1. **Keyboard focus after import.** The successful confirmation hides its own
   button. The new native journey failed `SHELF-KEYBOARD-01` after fourteen checks
   had passed: focus did not continue into the imported records. The correction
   moves focus to the first imported record, or the file input for an empty
   import, only when the confirmation still owns focus. It preserves navigation
   performed while the local import is pending.
2. **Cancelled inspection crossing a dialog opening.** A file read was held,
   the shelf closed and reopened, then the old read released. The receipt showed
   `imported: true` and a visible preview in the new dialog even though the
   inspection had been cancelled. The queued close event can find the dialog
   reopened and return before retiring the old import epoch. Each new opening
   now establishes new import ownership and clears its inspection state. Old
   successful reads and old decoding errors cannot populate that context.
3. **Late import rejection crossing a dialog opening.** Independent review found
   that import confirmation guarded its success but not its error. A held store
   rejection reproduced the stale status in a reopened dialog. The same
   epoch, inspected-object and open-dialog checks now guard that rejection.
   Controls prove that a current rejection remains visible, a stale one does not
   replace newer status or focus, and a store write followed by rejection still
   leaves its actual committed local record available for later inspection.

The confirmation completion also checks its original epoch, inspected object
and open dialog before updating presentation. Closing a dialog does not undo an
explicit local import already started; the ownership check concerns which UI
may receive its completion.

## Executed native evidence

The final local command was:

```console
python tests/asset_recovery_shelf_browser.py --out .runtime/recovery-native-review-final
```

It passed **50/50 checks**, with **zero JavaScript exceptions**. It uses the
shipped UI, real loopback HTTP handlers, disposable real SQLite, native
localStorage/sessionStorage, WebCrypto and Web Locks. Local runtime:
Playwright 1.56.0 and bundled Chromium 1194 / 141. The dedicated hosted workflow
pins Playwright 1.57.0 and still requires its own candidate-specific qualification
on Ubuntu and Windows.

| Journey | Observed result |
| --- | --- |
| Exported pending request | A command committed while its response was lost. Export retained its exact body and newer local typing separately. |
| Cleared storage and fresh tab | Both browser stores were cleared, the original page closed, and a new page started with no journal, shelf or persistence opt-in. |
| Inspect, import, restore, status | Inspection sent no receipt query or mutation; confirmation stored locally; restoration preserved the wire body; one explicit GET recovered the historical result without another POST or replacement of newer typing. |
| Unknown status and retry | Status alone did not retry. Keyboard activation of explicit retry sent the byte-identical body and committed once. |
| Occupied session viewpoint | A different draft survived a real reload; attempting to restore the imported record refused while preserving both journal and shelf bytes. |
| Native file refusal matrix | Malformed JSON, corrupt digest, oversized file, future bundle version, duplicate record identity, duplicate pending request, duplicate JSON key and excess depth all refused without changing storage, sending a receipt query or metadata POST, or moving focus from the file input. |
| Foreign/unknown import | Explicit local import permitted inspection/export/discard, with restoration and scoped observation disabled and no foreign receipt/current-state reads. Literal markup remained text. |
| Async focus and cancellation | Newer focus survived a held import. Cancelled valid and malformed reads did not replace the reopened dialog's preview, status or focus. Active, stale and committed-then-rejected imports retained truthful storage outcomes and owned only their current dialog presentation. |
| Unresolved capacity | Twenty distinct unresolved records refused a dependent save without eviction or a POST; explicit local discard preserved the other nineteen records and the exact pending command. |
| Existing protocol | Closed-tab draft recovery, two-tab expected-digest CAS, bounded lock acquisition, quota refusal and original-media preservation remained green. |

The fixture records four metadata POST attempts deliberately required by its
save/recovery scenarios: two lost replies around real commits, a pre-commit
failure and its explicit exact retry. Import, inspection, restoration, malformed
files, capacity refusal and local discard add no metadata or generation writes.

The existing Node contracts also passed **46/46**:

```console
node --test --test-isolation=none tests/asset_recovery_shelf.cjs tests/asset_recovery_shelf_session.cjs tests/asset_recovery_checkpoint.cjs tests/asset_recovery_shelf_restore.cjs
```

`--test-isolation=none` is a local Node 24 process-mode adjustment for this
container; no assertion is replaced. The repository's normal Python wrapper
and hosted workflow remain the integration owners.

## Browser-owned zoom evidence

A minimal temporary Manifest V3 extension runs only in the disposable Chromium
profile. It calls the browser's `tabs.setZoom` / `tabs.getZoom` APIs in automatic,
per-tab mode. It has no content script and changes no Studio CSS or source.
This follows the primary documentation for
[Playwright extension contexts](https://playwright.dev/python/docs/chrome-extensions)
and [Chrome tab zoom](https://developer.chrome.com/docs/extensions/reference/api/tabs#method-setZoom).

The native receipt records:

| Observation | Before | After |
| --- | ---: | ---: |
| Browser zoom factor | 1 | 2 |
| CSS viewport width | 390 | 195 |
| Device pixel ratio | 1 | 2 |
| Computed CSS zoom | 1 | 1 |

Keyboard navigation reached the shelf actions at native 200% zoom without
horizontal dialog overflow. The screenshot was inspected: text wraps, the
focused Export action is visible, and the remaining controls are vertically
scrollable. The original CSS-zoom case remains separately labelled.

## Retained failure and fixture history

Raw local evidence is under ignored `.runtime/`, including
`recovery-red-focus`, `recovery-cancel-probe`, `recovery-red-import-rejection`,
and `recovery-native-review-final`. The first three preserve the product failures
above; the final directory contains the complete result and both zoom screenshots.

Fixture development also found and corrected distinct setup mistakes: a fresh
tab had not opted back into persistence before exporting a new pending command;
a programmatic editor close correctly discarded an ordinary draft, so the
occupied-session journey now uses reload; keyboard restoration now waits for
the actual queued dialog-close event before the next keyboard activation and
for the resulting editor; and a Playwright wait argument needed its documented
keyword form. The committed-rejection control initially reused the record needed
by the next successful import, correctly provoking the store's duplicate-ID
refusal; it now uses a distinct synthetic draft. The existing test server was also missing its empty `jobs` mapping
for real family reads. Those are fixture corrections, not additional claimed
product defects. No original browser timeout or assertion was relaxed.

## Limits and remaining acceptance

The file picker is driven through Playwright's input-file API; the operating
system chooser is not tested. Browser-owned zoom is executed and read back, but
browser-menu interaction and a screen-reader session are not claimed. The
broader #393 keyboard conflict/rebase/lifecycle matrix and durable last-refusal
annotation remain separate work. Existing Node fault tests retain the
checkpoint/readback boundary coverage; this pass does not claim a new OS crash
or power-loss campaign.

Only synthetic review text and media enter these fixtures. Browser-data clearing
without a usable export, origin changes, private-mode retention and copied
databases sharing a Workspace identity retain their documented limitations.
`HUMAN_TODO.md` is unchanged; its art, model/runtime and publication choices remain
open. Passing software checks do not decide them.
