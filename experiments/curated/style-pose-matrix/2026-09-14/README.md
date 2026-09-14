# Style + Pose checkpoint × LoRA matrix — 14 September 2026

Thirty Studio jobs run serially by `scripts/style-pose-matrix.py` (plan and per-cell job ids, prompt ids, timings
and output hashes in [`manifest.json`](manifest.json); the plan in [`plan.json`](plan.json)). Every cell used the
owner's own pictures from the Asset library: the KonoSuba character sheet (asset `6152a06a…`, 1448×1086) as the
single style picture, and two pose pictures, a seated throne illustration (`f44ac333…`, 849×1200) and a small
back-view beach screenshot (`b43e7da9…`, 253×430). Prompt: an adult original witch character, fully described in
words; seed 2026091410; 832×1216; style weight 0.8; pose strength 0.9; IP-Adapter Plus ViT-H with `linear`
weighting; Xinsir OpenPose ControlNet from an OpenPose skeleton extracted at 1024 px.

Grid: six checkpoints × {no LoRA / cinematic lighting 0.5 / manga-ink-screentone 0.6} × {throne, beach}; the
LoRA cells ran on the throne pose only (cinematic) or both poses (screentone) to keep the run under two hours.
Assessment sheet: [`examples/style-pose/matrix/assessment-sheet.jpg`](../../../../examples/style-pose/matrix/assessment-sheet.jpg);
full-size JPEG copies of six cells sit next to it.

## What was seen (one seed, my reading, not art acceptance)

| Checkpoint | Pose | Style from the sheet | Verdict |
|---|---|---|---|
| WAI v17 | Followed on both pictures: seated with the knee raised and a wink from below; back view with the hat and the hips turned | Warm red / black / gold palette, glossy cel shading, crisp outlines, the diamond trim on the robe | **Best overall**; keep as default |
| YumeFlux ILv1 | Followed on both | Same palette, slightly more saturated and painterly, good costume detail | **Second**; worth keeping |
| Animagine XL 4.0 | Followed on both | Darker, flatter, less glossy; the palette leans brown | Usable, third |
| CSTati v3 | Followed, less precise on the beach picture | Soft, low-contrast, costume detail washed out | Weak with this adapter |
| Pony V6 | Lost | Abstract colour fields, no figure | **Unusable** with IP-Adapter Plus ViT-H at weight 0.8; recipe removed |
| NoobAI XL 1.1 | Lost | Abstract texture, no figure | **Unusable** at these settings; recipe removed (a NoobAI-native adapter would be needed, see `research/style-pose/`) |

LoRA columns: `cinematic lighting` at 0.5 warms and adds rim light without changing the pose or the palette source;
`manga-ink-screentone` at 0.6 barely shows under the board, the sheet's colours win. Neither broke a cell.

## Timing (ComfyUI execution seconds per cell, from `/history` timestamps)

62–372 s, median about 110 s, with no relation to the checkpoint or LoRA: the same WAI graph ran 372 s (throne) and 113 s
(beach) back to back. ComfyUI drops its resident models to paged host RAM between jobs and reloads from the pagefile
when the box is short of RAM (152 leaked MCP node processes were reclaimed mid-run; free RAM stayed at 6–9 GB of 32).
The slow cells are reload cost, not sampling cost.

## Not verified

One seed only; no style-weight or pose-strength sweep; no warm, RAM-quiet timing; Pony/NoobAI were not retried at lower
adapter weight; no licence judgement (the sheet is fan art of a licensed series and the LoRAs' civitai flags are
recorded in `models/library.json`, never inferred); nothing here is art acceptance, that stays with the owner.
