# History restore feedback — 5 November 2026

Issue [#1874](https://github.com/Chris0Jeky/local-asset-studio/issues/1874) concerned a
successful restore leaving an older revision labelled current and a message that its
review had been canceled. This slice updates the existing command and history owners;
it adds no mutation, retry, storage or generation authority.

## Reproduction and correction

The mounted regression runs both shipped owners against verified synthetic revision
receipts. Its document dispatches listeners synchronously in registration order, including
all three recipe events emitted by shared-draft adoption. Against the original source at
local mirror `a285827b6865d9ddb5c825ede6d23f77c1b3ae83` (main `2dc4efe4`), the restore
commits and adopts revision 5, but History performs no follow-up read and retains the
revision 3 list. The regression fails with one history read instead of two.

The command owner now returns a compact outcome only after both validated commits and
guarded editor adoption succeed. A marker around that exact synchronous adoption prevents
its own recipe events from canceling the matching History review. The command owner's
existing editor/privacy epoch checks remain in place.

History then makes one GET through its existing reader. The response must include the
confirmed restored revision or a newer head. A separate read lifetime rejects delayed
successes and errors after closure, context changes, selection changes or a newer read.
Failed or canceled refreshes leave the confirmed restore intact and explain which older
list remains. Rows say **latest loaded revision**, rather than claiming a live head.

Saved setup names and unapplied import selections are metadata. Their input/change events
no longer cancel either restore owner. Applying a saved setup still emits recipe events
and invalidates the review, as do real draft edits and privacy/Workspace changes.

## Executed checks

Final targeted qualification includes main `d7392c025027b2df8e4a045f44e54f05529f111f`
(local mirror `5f3f43ee8bdad8547e954a4b369fff4b4e1cdeed`), merged without conflicts.
That includes the editor's Saved setups event handling from #2012.

- Before-fix mounted regression: **failed as expected**, after successful commits/adoption,
  because the automatic history GET was missing.
- `node --test --test-concurrency=1 tests/setup_history_client.cjs tests/setup_history_restore_client.cjs tests/setup_apply_client.cjs tests/setup_proposal_client.cjs`:
  **59 passed**. Coverage includes the exact two-command sequence, all adoption events,
  minimum/newer heads, failed refresh/manual refresh, late successes and errors after seven
  kinds of cancellation, metadata versus actual edits, and busy/failed/unknown/unadopted
  operations that must not trigger a successful refresh. Earlier checkpoint, lost-reply,
  privacy and adoption guards remain covered.
- `python -m unittest discover -s tests -p test_setup_history_frontend.py -v`:
  **2 passed**, including the read-only source contract and Node suite wrapper.
- `python -m unittest discover -s tests -p test_frontend_handoffs.py -v`:
  **30 passed**.
- `python scripts/validate-repo.py`: passed; **98** preset graphs/bindings, **194** pinned
  assets, **4,888** tracked paths and **167** LoRA names checked.
- `node --check` for `setup-apply.js`, `setup-history.js` and `app.js`: passed.
- `python -m py_compile tests/setup_apply_browser.py`: passed.
- `git diff --check`: passed.

## Native browser evidence

The existing `tests/setup_apply_browser.py` journey now checks actual Saved setups naming,
an unreadable import, a native saved-setup button, the one automatic history GET, the new
row and concrete success messages after real SQLite commits. It retains earlier guards
and captures the refreshed result at 1440px and 390px. The recipe-shortlist CI lane runs
this driver against a native HTTP origin.

No local Chromium is available in this session. Native browser results, screenshots and
the full suite must be recorded from the exact published head; source tests are not a
browser pass. Historical browser evidence remains unchanged.

The paused artwork wave, parallax usability and Studio art-direction owner decisions are
unchanged. This fix does not claim creative or owner-workstation acceptance.
