Arcade and Sakura source-art delivery / 2026-10-02

Twelve logical IDs selected by the lead assistant after visual review: six per world.
Each world has a sources ZIP and a renditions-review ZIP. Both are below 10 MiB.
Extract the two ZIPs for a world into the same directory to reconstruct its full pack.
Metadata is intentionally duplicated so each ZIP carries source identity and caveats.
Each archive has a SHA-256 manifest for its own entries; ARCHIVE-INVENTORY.json records archive hashes.

Originals are untouched. Hero, poster and card derive directly from the exact selected master.
All 22 WebP variants meet their individual profile budgets. All 26 transformations independently reproduce.
Native sources are 1672x941 scenes and 1536x1024 walls. No upscale or size fiction.
The 1920x800 hero and larger requested masters remain absent; native hero is 1668x695 plus 960x400 WebP.

Arcade quiet is a same-room daylight alternative with strong window shadows crossing the heading wall.
Its raw screen-edge landmark outlier is retained, alongside larger-patch diagnostics. Sakura has small local shifts.
Neither alternative is pixel-identical or crossfade-qualified. Narrow heading zones and overscan shortfalls remain.
Source-art choice, source/license review, rendition verification, runtime qualification and release are distinct.
This delivery changes no planning inventory, app runtime, pilot skin, layers, loops, promo or audio.

The Python scripts are audit/replay helpers for the working layout, not app code or theme-executable content.
To replay in a new working directory: place the scripts at its root, restore the six originals under originals,
place generation-prompts-original.json there as prompts.json, and fetch the pinned planning references under reference.
Run check_registration.py, build_pack.py, then verify_and_package.py with Pillow, NumPy and SciPy available.
Do not interpret file preparation timestamps as provider generation timestamps; provider timestamp/model/seed fields remain null.
