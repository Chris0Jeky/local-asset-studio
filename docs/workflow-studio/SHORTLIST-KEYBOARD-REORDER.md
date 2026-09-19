# Ordered-source keyboard reorder contract

The recipe shortlist replaces every source row when an image moves. Replacing the
focused move button during its native activation is timing-sensitive: a browser or
embedding can perform a later focus adjustment after the click handler has already
focused the new row. The visible reorder may succeed while keyboard focus lands on
an unrelated control.

## Required behavior

For **Move earlier** and **Move later**:

- Enter and Space move the source exactly once.
- A queued activation from the detached old button cannot replay the move.
- The role stays attached to the image rather than to its old slot.
- Any prior shortlist result is invalidated immediately.
- Focus moves to the role selector in the image's new slot.
- A stale focus callback from an older render cannot override a newer reorder.
- Pointer activation keeps the same focus destination.

No request, attachment, setup application, generation, or persisted source change
is introduced by this interaction.

## Implementation boundary

`app/static/recipe-shortlist.js` handles Enter and Space during `keydown`, prevents
the deferred native click, and calls the same move function used by pointer clicks.
Each rendered move control is single-use, so a queued event on its detached DOM node
is harmless. After rows are rebuilt the chooser focuses the new role selector
synchronously and once more on the next animation frame. A monotonically increasing
render epoch makes the second focus attempt a no-op when another render has already
superseded it.

The next-frame attempt is deliberately bounded to one frame. It is not a retry
loop, timer poll, or claim that the old DOM node remains valid.

## Regression proof

`tests/recipe_shortlist_keyboard_browser.py` mounts the production module in a
minimal real Chromium document. It mirrors the formerly flaky driver sequence of
focusing a move button and then pressing a key. The fixture also schedules a
post-activation focus adjustment to make the old race deterministic.

Run the focused proof with:

```sh
python tests/recipe_shortlist_keyboard_browser.py \
  --out .runtime/shortlist-keyboard-browser
```

The test writes `result.json` and covers Enter, Space, a queued detached-button
activation, pointer activation, stale result invalidation, and two rapid renders.
The recipe-shortlist workflow runs it before the larger native Studio-shell browser
proof, so a timing-contract failure is reported separately from backend, storage,
proposal, and setup-application coverage.
