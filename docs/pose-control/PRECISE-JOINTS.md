# Precise joint positions in Combine

Continuation of #466 and #475 under #444. This is a small addition to the existing body editor, not a second pose application, document store or inference route.

## Interaction

Select a known joint and enter **X / Y in pixels**. **Set joint position** or Enter applies the pair as one edit to the existing drawing and Undo history. Both values must be finite decimal numbers inside the current canvas; zero and fractional positions are valid. Empty input is not silently converted to zero. Invalid coordinates leave the drawing unchanged and mark the fields invalid.

Typing alone changes no geometry or attachment. A readiness refresh preserves unfinished input. While the pair of fields differs from the drawing, Generate, Use/Replace pose, engine switching, joint selection, dragging, presets, unknown/restore and Undo are held. The readiness message has a **Review joint coordinates** action; **Reset fields** discards only the unapplied field values. This prevents a visible numeric edit from being ignored by the next guide render.

Unknown joints have disabled position fields; use the existing Restore action first. Arrow keys inside a numeric input edit that input, not the skeleton. Once applied, the guide request contains the edited coordinates. The render-in-progress hold also covers the new fields and Apply/Reset controls.

The drawing's coordinates are continuous pixel-edge positions: X in 0..width, Y in 0..height, measured from the top-left, with Y downward. UI and guide serialization use two decimal places. The server remains the authority for canvas limits and input validation. This does not change the raster renderer or any model conditioning settings.

## Scope and state

The existing editor's drawing and remembered positions remain in-session. Undo uses its existing snapshots; this slice does not implement redo, durable Workspace revisions or saved pose reopening. Explicitly changing the canvas rescales the drawing and refreshes numeric fields to that new geometry. Changing away from a Combine recipe does not impose an irrelevant pose-field blocker on another recipe. Source-image overlays, imported detector confidence, shared headless editing and persistent geometry remain #444.

The first handoff PR preserves character/source roles and rejects stale/malformed guide responses. This child adds precision inputs; it does not infer whether a drawn pose agrees with the retained natural-language pose wording. Review that wording before Generate.

## Verification

```console
node tests/pose_guide_handoff.cjs
node tests/pose_editor_core.cjs
python -m unittest discover -s tests -p 'test_pose_guide*.py' -v
python tests/pose_editor_handoff_browser.py
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Pure tests cover valid zero/boundary/fractional coordinates, missing/nonfinite/boolean/hex/out-of-range values, the actionable readiness hold and reuse of Undo. The native-page fixture checks typing-versus-application, pending-draft holds, refresh without lost typing, Enter, invalid input, reset, unknown/restore, number-input arrows, exact coordinates in the actual guide request, and render-busy holds at desktop and 390px. Existing replacement/recovery scenarios remain in the same driver. APIs are synthetic and Generate is never clicked; hosted reports/screenshots are the browser evidence when local navigation is administrator-blocked.

No GPU generation, model/node/runtime change, native renderer qualification, source-art publication or owner art acceptance occurs. The initial pinned baseline was `186d2b0`; persistent reference brief PRs #418/#421 merged independently while this work was underway and are not rebuilt here. Full current-main integration is recorded on each PR separately from local tests of the pinned source.
