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
