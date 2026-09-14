# Continue with this → Restyle, first two runs — 14 September 2026

The Restyle route sends a finished picture to a Style + Pose board as its **pose picture**. Both runs below were
driven through the Studio page exactly as the owner would: *Continue with this →* on the throne witch
(Nova output `Nova_00004_.png`, asset `9f2fca4d91ab59bba39f6e3606d10917`, sha256 `36d5a3661e552197…`),
*Restyle*, *Prepare in Create*, one imported picture pulled from the library onto Picture 1
(`140800824_p0_master1200.jpg`, asset `f44ac333401c5a3d8c831bf58e0644a5`, sha256 `0633c6e8b84bf28e…`),
then *Restyle source →*. Nova Anime XL IL v19, primary backend, no LoRA, seed 2026091407, pose strength 0.9,
832×1216, the source's own submitted prompt copied unchanged. Empty board slots 2 and 3 were pruned from the
submitted graph (`workflow.json` of each run has nodes 10 and 11 only, `IPAdapterCombineEmbeds` with `embed1`).

| Run | Studio job | ComfyUI prompt | Style weight | Time | Output | sha256 |
|---|---|---|---|---|---|---|
| Default | `2f34fdc8-743e-4d3b-807f-6ffb2a7a3966` | `486c1c75-0224-4410-b242-6c459a01f585` | 0.7 | 64 s | `Nova_00005_.png` (asset `441d90ca49575c33998ce26402a26d9d`) | `2dfe58c679a0cbc6…` |
| *Style stronger* variant | `f69c524c-eb0d-4ac0-b8f2-6b51ed2f2ac2` | `6b38f2fe-d79f-4718-83a8-e5b59478ae47` | 0.9 | 28 s | `Nova_00006_.png` (asset `2f3ed7ad995b5c8987a3342e48502c97`) | `1cc8eb9b3f4e9f9a…` |

Sheet: [`examples/style-pose/restyle-continue-nova.jpg`](../../../../examples/style-pose/restyle-continue-nova.jpg)
(source, style picture, 0.7, 0.9). Job records: `experiments/runs/<job>/` outside Git.

## What the pictures show (agent reading, not acceptance)

- **Pose held in both**: seated on the throne, one knee raised, one eye closed, hand at the face, from below.
- **The look moved, but not to the style picture's.** Both outputs are a flat, heavier-lined cel rendering with a
  blue-and-gold palette; 0.9 is more saturated with a glowing throne. The style picture is a soft, lightly shaded
  modern illustration with a red throne, and neither output reads as that rendering. One picture on the board at
  linear weighting is a weaker style signal than the owner's verified three-picture boards
  (`../2026-09-14-nova/`); the route works mechanically, the creative question is HUMAN_TODO q-27.
- Not verified: WAI or the other three boards through this route; a three-picture board through this route; any
  LoRA; a warm-versus-cold timing; art acceptance or licence clearance (the style picture is the owner's import).
