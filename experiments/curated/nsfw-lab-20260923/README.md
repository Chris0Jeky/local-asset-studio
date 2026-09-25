# NSFW lab continuation — 23 September 2026

`FINDINGS.md` is the inspection record. Pictures are not in Git. Generated is not
accepted art and not licence clearance. Catalog `verified` stays false. q-29 and q-31
stay open. These cells are not Creative Bundle entries.

Restore and gallery behaviour for the 21 September contact sheets is unchanged and
documented in `experiments/curated/nsfw-lab-20260921/README.md`. This folder adds
prose only: recipe text, Studio job ids, ComfyUI prompt ids, timings, and judgements.
Local PNG paths are text. Contact JPEGs for this lab live under `examples/nsfw-lab/` (see below); nothing else is added under `examples/`.

Media organisation (closeout, 24 September 2026): all 552 judged cells have
contact JPEGs at `examples/nsfw-lab/<cell>.jpg` (gitignored, Studio-served)
with tracked records in `examples/nsfw-lab/MANIFEST.json` (670 entries with the
earlier 118; `python scripts/lab-media.py verify --folder nsfw-lab` is green)
and a clickable `examples/nsfw-lab/index.html` (gitignored). Full PNGs are
hardlink-sorted on this PC under `ComfyUI/output/Studio-lab-20260923/`
(`by-wave/`, `by-character/`). `INDEX.md` is the resume map.
