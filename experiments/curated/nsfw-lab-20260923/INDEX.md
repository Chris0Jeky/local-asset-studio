# NSFW franchise lab — session index (23–24 September 2026)

Prose record: `FINDINGS.md` (inspection log), `TECHNIQUES.md` (garment/layer
standings), `ORCHESTRATOR.md` (plan), `README.md` (media policy). Pictures are
not in Git. Generated is not accepted art and not licence clearance. Catalog
`verified` stays false. q-29 and q-31 stay open.

## Where the pictures are

- Full PNGs (gitignored, this PC only), relative to
  `C:/AI/ComfyUI_windows_portable/ComfyUI/output/`:
  p4–p93 use the retained archive views below; the five page poses and p2/p3
  use `Studio/nsfw/` and `Studio/nsfw/NSFW2/` (see the inventory below).
  The old closeout's 819 files in `Studio/` was a historical directory census,
  not a count of all judged cells or a current source-location guarantee.
- Organised views (NTFS hardlinks, zero extra bytes):
  `C:/AI/ComfyUI_windows_portable/ComfyUI/output/Studio-lab-20260923/` —
  `by-wave/p4..p93/<cell>.png` (90 wave directories) and
  `by-character/<name>/<cell>.png` (~110 characters; `_settings` holds the six
  p10 cfg/steps ablations, which are not character cells).
- Contact JPEGs (gitignored, served by the Studio gallery):
  `examples/nsfw-lab/<cell>.jpg`, 552 p4–p93 cells, the earlier 118 A–I cells,
  and 15 page-pose/p2/p3 cells.
- Tracked record: `examples/nsfw-lab/MANIFEST.json` (685 entries: id, file,
  sha256, bytes, size, job id, prompt id, cell, source PNG, note).
- Clickable overview: `examples/nsfw-lab/index.html` (gitignored, rebuild with
  `python scripts/lab-media.py index --folder nsfw-lab`).

## Working with the pictures

```bash
python scripts/lab-media.py verify --folder nsfw-lab    # checks all 685 manifest entries on this PC
python scripts/lab-media.py restore --folder nsfw-lab   # rebuild from the Studio PNGs
python scripts/lab-media.py index --folder nsfw-lab     # rewrite index.html
```

## Lab state at closeout (24 September 2026, night)

- The original archive covered exactly 552 judged cells in p4–p93 plus 118
  A–I cells from the 21 September lab: 670 entries. The #988 backfill adds the
  five page poses (`p-`, not a wave named `p1`), six p2 cells and four p3 cells:
  685 entries total. Each of these 15 added cells has a local contact JPEG and
  a hash-verified, unique, restorable source path in the manifest.
- Completeness applies only to A–I, the five page poses, and p2–p93. The
  completed J, K/k2, L, M, M2 and M3 cells also described in FINDINGS are
  outside this manifest coverage; they are not part of the earlier 118.
  Failed, uncertain and never-submitted jobs are not counted as judged cells.
- G24 (miko) CLOSED at p93: crawl (bend variant), portrait, seated rear, eyes,
  bent-over, seiza, sheer-off x2 and Anima/JANIMA ports all hold; C1
  `from below` measured on the miko pair.
- Receipts 404 at p93 judgment (job store cleared): p93 cells have no prompt
  ids or spill lines; judged from files in queue order. Same for the p86 seiza
  (prompt id unrecovered).
- Standing constraints: adult-in-canon only; SFW-pool casts never queued for
  sexual cells; fast presets 832x1216 20 steps; dead prompt ids
  `4dc53889…`, `6ab21b16…`, `c3b53ce6…` stay dead; no prompt-id reuse.

## Page-pose, p2 and p3 source inventory (#988)

All 15 retained PNGs were found on 25 October 2026; none is unavailable.
No matching contact JPEG existed in this fresh worktree before backfill.
The inventory checked the ComfyUI output tree, excluding `DO NOT OPEN`, for
the recorded PNG basenames and cell-named PNG/JPEG contacts. Matching a
basename alone is unsafe: several original `Studio/` paths now hold later,
unrelated renders. The retained PNGs below have embedded graphs matching the
recorded character, family and see-through recipe; the five page-pose seeds
also match FINDINGS. The observed seeds below identify the retained graphs,
not recovered job receipts. Each source's SHA-256 is recorded as
`source_sha256`; the contact's SHA-256, byte count and dimensions were measured
after encoding with the manifest's JPEG settings. Each contact is named
`examples/nsfw-lab/<cell>.jpg` and stays gitignored.

Paths below are relative to the ComfyUI output folder.

| Cell | Retained source PNG | Embedded seed |
| --- | --- | --- |
| p-changli-bentover | `Studio/nsfw/NSFW2/WAI-Illustration_00043_.png` | 2026092401 |
| p-shalltear-seiza | `Studio/nsfw/YumeFlux-ILv1-Baseline_00014_.png` | 2026092402 |
| p-makima-squat | `Studio/nsfw/CSTati-v3-Baseline_00018_.png` | 2026092403 |
| p-zhuyuan-skirt | `Studio/nsfw/AniFox-v2-Baseline_00012_.png` | 2026092404 |
| p-blackswan-portrait | `Studio/nsfw/NSFW2/WAI-Illustration_00044_.png` | 2026092405 |
| p2-albedo-bentover | `Studio/nsfw/NSFW2/WAI-Illustration_00045_.png` | 2026092411 |
| p2-frieren-bentover | `Studio/nsfw/YumeFlux-ILv1-Baseline_00015_.png` | 2026092412 |
| p2-yinlin-squat | `Studio/nsfw/CSTati-v3-Baseline_00019_.png` | 2026092413 |
| p2-scathach-squat | `Studio/nsfw/AniFox-v2-Baseline_00013_.png` | 2026092414 |
| p2-wiz-seiza | `Studio/nsfw/NSFW2/WAI-Illustration_00046_.png` | 2026092415 |
| p2-artoria-sit | `Studio/nsfw/YumeFlux-ILv1-Baseline_00016_.png` | 2026092416 |
| p3-albedo-squat | `Studio/nsfw/NSFW2/WAI-Illustration_00047_.png` | 2026092421 |
| p3-luna-bentover | `Studio/nsfw/YumeFlux-ILv1-Baseline_00017_.png` | 2026092422 |
| p3-serie-bentover | `Studio/nsfw/CSTati-v3-Baseline_00020_.png` | 2026092423 |
| p3-priscilla-squat | `Studio/nsfw/AniFox-v2-Baseline_00014_.png` | 2026092424 |

Job IDs and the five full page-pose prompt IDs are transcribed from FINDINGS.
The ten p2/p3 prompt IDs remain the recorded eight-character prefixes; no
full receipt was recovered or inferred. No job was submitted or regenerated.
Generated, historical lab judgment, art acceptance and licensing stay separate;
this backfill adds no new art judgment or owner decision.

### Backfill proof (25 October 2026)

- `py -3 -m unittest discover -s tests -p test_lab_media.py`: 20 tests pass.
  Before the manifest fix, the new coverage test failed for all 15 omitted
  cells (20 tests run, 15 subtest failures).
- `py -3 scripts/lab-media.py verify --folder nsfw-lab`: 685 entries,
  685 ok, 0 missing, 0 corrupt.
- Restore with `--repo-root` pointing to a disposable tree containing only
  the 15 added manifest entries and `--comfy-output` pointing to the retained
  ComfyUI output folder: 15 restored, 0 failed; subsequent `verify`: 15 ok.
  Source SHA-256, restored contact bytes and byte counts all matched; the
  disposable tree was removed.
- `py -3 scripts/validate-repo.py`: PASS (743 local-media entries,
  102 references, 93 preset bindings, 187 pinned assets). Image binaries
  remain ignored; no runtime or generation was started.

Local verification preparation exposed an existing A–I limitation: the
unchanged 118 entries still name pre-move source paths. The initial full
restore recovered the 552 p4–p93 contacts but rejected or could not find those
118 sources. For local verification only, the 118 contacts were recovered
from relocated PNGs under `Studio/nsfw/` (or its `NSFW2/` subfolder), accepting
only encodings matching the existing manifest hashes. Their recorded paths
are outside #988's page-pose/p2/p3 backfill and remain unchanged; full-folder
restore on another fresh worktree can still encounter that historical gap.

## To resume

1. Read this file, then the tail of `FINDINGS.md` and `TECHNIQUES.md`.
2. Open `examples/nsfw-lab/index.html` for the visual state.
3. Pick the next lever from the open end of `TECHNIQUES.md`; queue 6–10 cells.
4. Judge, append bullets to `FINDINGS.md`, add JPEGs with the build script
   pattern (`/tmp` scratch is gone — re-encode q85/optimize, append to the
   manifest, run `verify`), hardlink new PNGs into the archive views.
