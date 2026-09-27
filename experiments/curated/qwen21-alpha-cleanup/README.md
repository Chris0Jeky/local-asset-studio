# Qwen-Image 2.1 alpha cleanup — 26 September 2026

Deterministic finishing for issue #878, run with `python scripts/game_asset_media.py cleanup`
from branch `muse/878-alpha-cleanup`. Inputs are the 23 September Studio proofs on the
isolated qwen21 backend (read-only); derivatives stay under the gitignored
`.runtime/qwen21-alpha-cleanup/`. Only this README and the three evidence JSONs are tracked.

## Transparent sprite (`qwen21-rgba_00001_.png`, job `b377572d`)

`--mode rgba-cleanup` (alpha below 8 to 0, 224 and above to 255, edge band kept):

- before: bbox the full 1024x1024 canvas, 54,233 dust pixels (alpha 1-7), 277,006 body
  pixels (alpha 224-254), matte in 13,968 components;
- after: bbox `[210, 50, 815, 972]`, dust 0, body 0, edge band unchanged (4,108 px),
  matte in 1 component (356,522 px).
- `atlas` on the dusty original warns "visible pixels touch logical frame edge";
  on the cleaned file it packs with no warnings and `pixel_roundtrip: passed`.

Evidence: `rgba-evidence.json` (input SHA-256 `7c37000a…6912c1b`, output `d46477c7…e7de47d`).

## Text-to-image and edit proofs

`--mode to-rgb` drops the spurious alpha (t2i had 9.4 % of pixels at alpha 224-254,
edit 19.6 %); RGB bytes pass through unchanged. Evidence: `t2i-evidence.json`,
`edit-evidence.json`.

Not verified: visual inspection of the cleaned sprite as art (pixel measurements only);
automatic application to Studio jobs (the recipes still emit RGBA; cleanup is an
explicit step). Not art acceptance and not licence clearance.

## Three new sprites and the despeckle mode — 27 September 2026 (07:14-07:22 local)

Three `qwen21-rgba` jobs ran once each through `POST /api/jobs` on the isolated qwen21 backend (Studio switch at
07:10), one seed each; receipts in `2026-09-27/runs.json` and `recipe-rgba-*.json`:

| Subject | Job / prompt | Size | Wall | Host commit before → peak |
| --- | --- | --- | --- | --- |
| adult knight, full figure | `7179db99` / `f0fb24bb` | 832x1248 | 72.6 s | 50.0 → 76.4 % |
| longsword icon | `0b6b83b7` / `1f902a83` | 1024² | 55.7 s | 51.9 → 77.1 % |
| crystal with sparkles | `254d368d` / `b3e4f7fe` | 1024² | 63.4 s | 51.7 → 77.4 % |

Between jobs the Studio's 32 GiB commit-headroom gate refused the next submission (27.0 GiB) until the qwen21
model cache was released with `POST /free` on 8196; the release is asynchronous (the process fell from 21.4 to
5.0 GB private bytes within about 15 s).

All three raw outputs had the #878 defect: alpha bbox = the whole canvas, 50-99k dust pixels, 15-20k matte
components. `rgba-cleanup` fixed the knight and the sword (one component each; knight bbox `[64, 81, 663, 1182]`;
the sword really runs corner to corner, bbox `[4, 10, 1011, 1015]`). The crystal kept **21 components**: its 5
real pieces (the body, the requested sparkles, 97-2,975 px, peak alpha 207-255) plus **16 specks of 1-12 px whose
brightest pixel is exactly 8**, left at the dust threshold around the soft glow.

New `--mode rgba-despeckle` = `rgba-cleanup`, then clear every detached 4-connected alpha region whose brightest
pixel is below 32 (the dust band the 23 September judge measured, alpha 1-31). A faint glow that touches the
subject stays with its region; a detached sparkle with a bright core stays whatever its size. Results
(`despeckle-*.json`):

| Output | Regions cleared | After: components, bbox |
| --- | --- | --- |
| 23 Sep proof `qwen21-rgba_00001_` | 0 | 1, `[210, 50, 815, 972]` (identical to `rgba-cleanup`) |
| knight `_00006_` | 0 | 1, `[64, 81, 663, 1182]` |
| sword `_00007_` | 0 | 1, `[4, 10, 1011, 1015]` |
| crystal `_00008_` | 16 (36 px) | 5, `[180, 106, 804, 873]` |

`atlas` on each raw output warns "visible pixels touch logical frame edge"; on each despeckled output it packs with
no warnings and `pixel_roundtrip: passed`. The contact sheets (`sheet-*.jpg`: raw on magenta, alpha>0 mask before
and after with the bbox in red, cleaned result on grey; made by `sheet.py`) were opened; the crystal's sparkles are
still present after despeckle. Full-size PNGs stay local in ComfyUI `output/Research/lab2-20260927/rgba/`.

Not verified: the sprites as art (they were viewed at contact-sheet scale only, not judged with the rubric);
automatic application in the Studio (cleanup stays an explicit step). Not art acceptance and not licence
clearance (Qwen Research License: non-commercial).
