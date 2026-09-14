# Collection editor review — 14 September 2026

## Refresh ownership, not another queue

The first automatic review of PR #292 at `500665338287b803461f355586dc2d3450afa70e`
raised a possible dropped post-write refresh (thread `4001670177`). Calling the raw
Workspace refresh while its boolean guard is set does drop that call. An isolated
script experiment reproduced this, but omitted the complete application's read owner.

`configureReadPolling()` in `app.js` replaces `refreshAssets` with the existing
`ReadPoller.refresh('assets', ...)` wrapper. That wrapper retains one `lane.queued`
follow-up while its current task runs. Collection callbacks resolve the wrapped
function when they execute. No additional product queue or polling mechanism is
needed for this configured application path.

The investigation initially proposed a queue based on the isolated handler. The
complete-shell experiment disproved that diagnosis. Its three failing raw-handler
assertions are retained as an insufficient fixture, not as three application defects.
Production files are unchanged by this review response.

## Added regression evidence

The browser driver now waits for the actual `window.StudioReadPoller`, pauses only its
periodic timers, and keeps explicit reads and their ownership intact. The previous
lowercase optional test reference did not pause those timers; it was corrected.

- **COL-27:** capture and hold a pre-write Workspace snapshot, confirm Rename, assert
  the existing assets lane has a queued read, release the old snapshot and verify the
  current name after the read owner becomes idle.
- **COL-28:** repeat with removal of the active collection and verify both the current
  collection list and the rendered All assets view. Original assets remain governed
  by the preceding removal assertions.

Both pass on the unchanged production implementation. The expanded local full-shell
run passes **28/28**, with no JavaScript or execution errors. Its mode is explicitly
inert storage/transport with production collection HTTP and temporary SQLite. The
initial matched 26-scenario baseline remains in `COLLECTION-EDITOR-RESULTS.json`;
the two added cases are review coverage, not new before/after bug fixes.

The original 26 native checks passed on the first head. Native results for this
expanded driver must be read from its new-head CI artifact and PR checkpoint, not
inferred from either earlier native or local component evidence. Failed bootstrap,
closed-tab durability, collection CAS/receipts and owner-PC acceptance remain outside
this slice. Broader recovery remains #282.
