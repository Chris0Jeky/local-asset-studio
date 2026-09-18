# Pose editor undo and redo history

The Combine pose editor keeps a local, bounded timeline for authored geometry. It does not reserve a Studio
attempt, call ComfyUI or submit generation. Rendering the orange-line guide remains a separate explicit action.

## State owned by one history entry

Each entry snapshots both arrays used by the editor:

- the current COCO-18 joint coordinates, including `null` for an unknown joint;
- the remembered home coordinates used when an unknown joint is restored.

The snapshot is copied on entry and exit. A later drag or toggle cannot mutate a saved state through a shared
object reference.

## Timeline rules

- A geometry edit records the current state before applying the edit.
- Undo moves the current state to the future stack and restores the newest past state.
- Redo moves the current state back to the past stack and restores the newest future state.
- A new authored edit after Undo discards the abandoned future branch.
- Joint selection and other non-geometry UI changes do not create or invalidate history.
- Both stacks are rescaled when the pose canvas dimensions change, so neither direction restores coordinates
  from an obsolete canvas.
- The timeline retains at most 60 past or future snapshots and exposes safe no-op edges when a direction is
  unavailable.

The Undo and Redo buttons derive their disabled state and help text from the same timeline owner. Keyboard
focus on either action must not leak arrow-key movement into the canvas.

## Issue scope

This delivers the remaining redo slice of #444. It does not claim that #444 is complete: detector-overlay
inspection, residual visualisation and the proposed joint-swap heuristic remain separate work. Those features
should consume the same explicit COCO-18 geometry rather than creating a second editor state owner.
