# Goal baseline recipes — 13 September 2026

This small curation records three completed Studio baseline jobs from the configured experiments root. [`provenance.json`](provenance.json) contains the source run IDs, exact recipe controls, model filenames, prompt IDs and output hashes. Each baseline subdirectory retains the exact submitted workflow and recipe. The five distinct required model files were hashed in full against the pinned library after the runs; the runtime versions and full model hashes are recorded here.

The coordinator inspected all three existing output images. They establish completed generation evidence for the requested station brief, while hand detail and leg/foot overlap remain unresolved. They remain experiment-only: no output was selected or human-accepted, and no model-rights or production-use decision is implied.

Only metadata is curated here. The PNGs, raw job receipts, full machine snapshots and private character sources remain outside Git. No generation or network transfer was performed during this curation.

[`wan-tiled-control-failure.json`](wan-tiled-control-failure.json) records a separate full Wan control: sampling and tiled decode completed, but frame 1 already broke up and the 41-frame contact sheet failed visual inspection. The video and extracted frames remain local failure evidence. This does not enable a new production preset or establish usable video.
