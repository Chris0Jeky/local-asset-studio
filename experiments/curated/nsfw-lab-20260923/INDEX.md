# NSFW franchise lab — session index (23–24 September 2026)

Prose record: `FINDINGS.md` (inspection log), `TECHNIQUES.md` (garment/layer
standings), `ORCHESTRATOR.md` (plan), `README.md` (media policy). Pictures are
not in Git. Generated is not accepted art and not licence clearance. Catalog
`verified` stays false. q-29 and q-31 stay open.

## Where the pictures are

- Full PNGs (gitignored, this PC only):
  `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio/` (819 files; the lab
  owns 552, the rest is other Studio work).
- Organised views (NTFS hardlinks, zero extra bytes):
  `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio-lab-20260923/` —
  `by-wave/p10..p93/<cell>.png` (89 waves) and
  `by-character/<name>/<cell>.png` (~110 characters; `_settings` holds the six
  p10 cfg/steps ablations, which are not character cells).
- Contact JPEGs (gitignored, served by the Studio gallery):
  `examples/nsfw-lab/<cell>.jpg`, 552 lab cells plus the earlier 118.
- Tracked record: `examples/nsfw-lab/MANIFEST.json` (670 entries: id, file,
  sha256, bytes, size, job id, prompt id, cell, source PNG, note).
- Clickable overview: `examples/nsfw-lab/index.html` (gitignored, rebuild with
  `python scripts/lab-media.py index --folder nsfw-lab`).

## Working with the pictures

```bash
python scripts/lab-media.py verify --folder nsfw-lab    # all 670 present and hash-matching
python scripts/lab-media.py restore --folder nsfw-lab   # rebuild from the Studio PNGs
python scripts/lab-media.py index --folder nsfw-lab     # rewrite index.html
```

## Lab state at closeout (24 September 2026, night)

- 552 judged cells across waves p10–p93 (plus Wave J/K/L and p1–p9 prequels in
  the same FINDINGS log). Every judged cell has a contact JPEG and a manifest
  entry; `verify` is 670/670 ok.
- G24 (miko) CLOSED at p93: crawl (bend variant), portrait, seated rear, eyes,
  bent-over, seiza, sheer-off x2 and Anima/JANIMA ports all hold; C1
  `from below` measured on the miko pair.
- Receipts 404 at p93 judgment (job store cleared): p93 cells have no prompt
  ids or spill lines; judged from files in queue order. Same for the p86 seiza
  (prompt id unrecovered).
- Standing constraints: adult-in-canon only; SFW-pool casts never queued for
  sexual cells; fast presets 832x1216 20 steps; dead prompt ids
  `4dc53889…`, `6ab21b16…`, `c3b53ce6…` stay dead; no prompt-id reuse.

## To resume

1. Read this file, then the tail of `FINDINGS.md` and `TECHNIQUES.md`.
2. Open `examples/nsfw-lab/index.html` for the visual state.
3. Pick the next lever from the open end of `TECHNIQUES.md`; queue 6–10 cells.
4. Judge, append bullets to `FINDINGS.md`, add JPEGs with the build script
   pattern (`/tmp` scratch is gone — re-encode q85/optimize, append to the
   manifest, run `verify`), hardlink new PNGs into the archive views.
