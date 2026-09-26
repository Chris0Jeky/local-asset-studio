# Qwen-Image 2.1 native 2K square — 26 September 2026

One frozen proving run for the #739 leftover "a 2048² text-to-image run".
`prove_2048.py` holds the frozen inputs; `run-2048.json` the outcome;
`recipe-qwen21-t2i-2048.json` the exported recipe. No resubmission on any outcome.

## Preflight and backend switches

- Health before: Studio healthy, primary active, both ComfyUI queues empty, no held
  GPU lease, host commit headroom 73.8 GiB, VRAM 16.6/17.0 GiB free, no spill.
- The first switch to qwen21 was refused by the gate: five `uncertain` restart
  leftovers. Their prompts were all absent from the running ComfyUI history, so
  three were stop-tracked with that recorded reason (`0c0fc66f`, `7a07ce99`,
  `22cedbc9`); the other two (`0cbaae1b`, `a2908800`) were already stopped records
  from the 14 September PR #367 rollout, and the server correctly refused to
  overwrite their reasons. Recipes and prompt IDs retained everywhere; nothing
  resubmitted. This also restores backend switching for the owner.
- Switch primary → qwen21 completed in ~30 s; switch back completed after the run
  (see below). No generation was submitted by either switch.

## The run

- Job `252c3ebe-5376-4817-b810-397dd7b26ada`, prompt
  `3593cd92-133b-4e0d-a350-e37abe327388`, seed 2026092601, 2048x2048, 25 steps,
  default brief. `completed` in 353.0 s wall.
- GPU: the job completed with the spill message — 11.9 GB spilled into shared RAM
  during the run, 1.2 GB still retained after; the Studio unloads ComfyUI models
  before the next job. Native 2K on this 16 GB card is possible but paging-bound;
  1 MP stays the everyday size.
- Output `Studio/qwen21-t2i_00002_.png` (5,474,405 bytes, SHA-256
  `60f0f3228db4b64f76dda28198e2454fe30a72a7e731a6d88a143d330df02a54`): PNG RGBA
  2048x2048, opened and inspected. The briefed scene
  is all there — adult silver-haired sorceress, midnight-blue coat and cape with
  gold clasps, lit brass lantern in hand, stone bridge, rain, blue-hour mountains.
  Clean anime finish; the visible hand holds the lantern handle naturally; no
  anatomical breaks at full view. Agent-inspected only, not art acceptance.
- Same faint-alpha trait as the 1MP proofs: 481,653 px (11.5 %) at alpha 224-254;
  strip or threshold alpha before any alpha-based crop (`cleanup --mode to-rgb`).

## Switch back

After evidence was recorded, the Studio was switched qwen21 → primary; the primary
came back healthy on 8188 with an empty queue. Steady state restored.

Not verified: visual quality at 100 % zoom (single full-view inspection only);
whether a higher `--reserve-vram` on the isolated launcher avoids the spill;
multi-reference, text-heavy and LoRA items under #739. Not art acceptance and not
licence clearance (Qwen Research License, non-commercial).
