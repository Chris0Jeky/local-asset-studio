# Live proofs through the real Studio page — 27 September 2026 (19:37-21:47 local)

Each feature was driven in headless Chromium (Playwright) against the running Studio: main `c22479e8`, and from 20:56 (the Studio restart) main
`cb686915` with #1224 and #1227. ComfyUI 0.35.0 on primary. Every generation was started by the page's own button. The scripts
in `receipts/` are as-run copies with local paths. Prompts are SFW and the subjects are clothed adults. The pictures are
**generated and agent-pre-reviewed only**; the owner's answers are quoted where they exist.

Workspace note, the same for every flow: agent-labelled runs are hidden by the Asset library's default source filter
("Mine"), so each script sets `#assetSource` to All before searching.

## (a) Vary subtle / Vary strong (#1202)

Route: Asset library → the picture → **Vary subtle** or **Vary strong** → Create is prepared (status line, round size,
denoise) → **Generate**. Each round sent exactly one `POST /api/jobs`, preceded by one `POST /api/assets/reference` that
copies the parent in. The job records `parent_assets` = the parent, and the parent's own words were carried.

**Round 1, starting values** (`vary-sdxl-sheet.jpg`, `vary-krea-sheet.jpg`)

| Recipe | Parent | Strength | Job | Denoise in the graph | Pictures (the page's choice) | Time | Agent pre-review |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| SDXL → gentle-variation | job `48120939` (cottage, made for this proof) | subtle | `38198ce3` | 0.3 | 2 ("No timing on this PC yet") | 245.5 s | too close |
| | | strong | `c18e4386` | 0.55 | 2 ("about 2 min per picture here") | 241.5 s | right |
| Krea 2 GGUF → krea-refine | asset `2c48e689` (Night Shift loft) | subtle | `944745a6` | 0.25 | 2 ("about 6.2 min per picture here · 8 runs") | 934.5 s | too close |
| | | strong | `fd7a79b8` | 0.5, 6 steps | 2 | 1247.7 s | right |

**Owner answer (27 Sep 2026, in chat): "Nudge both up".** SDXL moves to 0.5 / 0.7 and Krea to 0.45 / 0.65 (6 steps). The
running Studio reads the main checkout's catalog, so round 2 pressed Vary on the page and then typed the new value into the
page's denoise field before Generate. The submitted graphs carry the new values.

**Round 2, owner values** (`vary-sdxl-sheet-v2.jpg`, `vary-krea-sheet-v2.jpg`)

| Recipe | Strength | Job | Denoise (steps) | Time | Agent pre-review |
| --- | --- | --- | --- | ---: | --- |
| gentle-variation | subtle | `bc31e7fe` | 0.5 | 83.8 s | right: same scene, redrawn details, one seed shifts the cottage |
| | strong | `bc904e63` | 0.7 | 26.7 s | right, further: same subject, new layout and cottage shape |
| krea-refine | subtle | `b4bfb680` | 0.45 (4) | 900.1 s | right: composition held, window and desk redrawn |
| | strong | `213848b0` | 0.65 (6) | 1322.2 s | right, further: composition held; no sign of 6 steps fighting 0.65 |

The catalog now carries these values with status `owner-approved` and the answer in each basis note. `HUMAN_TODO`
`vary-strengths-1202` stays open for its WAI question.

Host commit reached 88.9 % during the last Krea round (sampled every 5 s), with ComfyUI holding about 25 GB. That is close
to the danger zone on this 32 GB box.

## (b) Several recipes on one Combine pair (#1163)

The pair: image 1 = fantasy-pack portrait (asset `021731c0`, `Studio/Anima-v1-Baseline_00004_.png`); image 2 = its
full-body picture as the pose (asset `025678ca`). Route: Asset library → Continue with this → Combine → Prepare → Pull from
library → fills → *Run several recipes on this pair* → tick Klein 9B Copy Pose, Klein 9B depth and Klein 4B → seed
2026092795 → **Prepare plan** → **Start plan**.

- **Attempt 1 (`receipts/plan-live-attempt1.json`): refused.** Led with Klein 4B, whose wording has only two fields (who,
  pose). Prepare plan answered: "…Copy Pose: fill in the wording, replace "[image 1's clothes and colours…]"". The page ticked
  recipes whose extra fill it never showed. Nothing was created. This is a defect candidate, reported to the coordinator and
  handed to a builder; it is not fixed here.
- **Attempt 2 (`receipts/plan-live.json`)** led with Copy Pose, so all three fields showed.
  - Prepare plan (50.3 s): "Prepared 3 pictures: expected about 3.8 min (up to about 5.5 min), medium confidence".
    The server estimate was 225.8 s, with an upper bound of 327 s.
  - Start plan created project `cd3c5812`.
  - Actual: 303.5 s from Start to the last job done, inside the upper bound. Per job: Klein 4B `c13dbf5c` 66.0 s, 9B depth
    `6e66575c` 127.4 s, 9B Copy Pose `227a9fe3` 102.6 s.
  - One `/prompt` per stage: ComfyUI's `got prompt` count rose 4 → 7 across the plan, and the queue was empty afterwards.
  - Host commit peaked at 84.8 % (sampled every 10 s).
- **Runs for these pictures** lists the three runs as "Klein 4B / Klein 9B · depth / Klein 9B · Copy Pose … from a plan".
- All three follow the pose picture (`plan-sheet.jpg`).
- The Copy Pose recipe's placeholder example reads "Ellen Joe, a girl with short black hair…". **The owner said keep it
  (27 Sep 2026)**; do not "fix" it.

## (c) Quick review checks (#1203)

On the plan's three result tiles I tapped: pose = yes on Klein 4B, pose = no on 9B depth, face = yes on 9B Copy Pose.

| Step | What showed |
| --- | --- |
| After the taps | Per-run (per-engine) tallies "pose 1/1", "pose 0/1" and "face 1/1" |
| Fresh browser session | The same chips and tallies. Server tags: `check:pose=yes`, `check:pose=no`, `check:face=yes`. They persist |
| After cycling every chip back to "not checked" | Checks are the owner's answers, so the agent's taps were removed |
| Another fresh session | Empty tallies, and server tags `[]` on all three |

`receipts/review-live.json` records this. The first attempt crashed while rebuilding the pair after an in-context reload,
after the taps and tallies had been read. The persistence proof above uses a fresh session instead.

## (d) Make seamless (#1220)

Route: Asset library → the flat 1024² texture → **Make seamless** (the button said "Flat textures only…") → Create
prepared the tile recipe with the texture's own wording → **Generate**. The Studio then finished each tile without a button
press, writing a "Seamless tile" asset and a 1536² 3×3 preview (`tiles-3x3-sheet.jpg`).

| Texture | Job / prompt | Time | Finish job | Seam (own gradient) | Pre-review | Owner (27 Sep 2026) |
| --- | --- | ---: | --- | --- | --- | --- |
| wall (`Studio/Z-Image-Fast_00021_.png`) | `632fc46a` / `0a213ed5` | 141.8 s | `a44c9cb2` | 4.34 → 0.84 (0.96) | keep | **"Wall ok"** |
| floor, flat planks (`Studio/Z-Image-Fast_00022_.png`) | `93bc7e69` / `ad393351` | 128.8 s | `b4bbc6fb` | 13.53 → 1.93 (1.17) | fixable: a repeating row of plank ends | needs the wider band ("add band choice") |

`python scripts/validate-live.py` on primary passes `zimage-seam-repair` (85 of 90; the 5 failures are the
hidream and qwen21 presets, which only validate on their own backends). The recipe is now `verified: true`, with an
execution_note naming these jobs. The floor is re-run with the wide band once the band choice lands.

## (e) Look templates (#1221 / #1224)

Route: Create → **Use a saved look** (the folded block rendered) → Night Shift (retro anime) → scene "a rain-soaked arcade
entrance on a narrow street at night; at the right edge a glowing vending machine beside the entrance" → **Prepare with
this look** → Variations 2 → **Generate**.

- Prepare switched the recipe to `zimage-fast`, seed 2026092752, 1344×768, with the scene inside the template.
- Job `2acea59b`, prompts `6da84a3a` and `4ba02828`, 147.4 s. One POST.
- Pre-review (`look-sheet.jpg`): the look carries (graphite, rain, a quiet left and centre, a lit vending machine at the
  right with a cyan floor glow). But the "arcade entrance" reads as a closed shutter: the template's plain-wall sentence
  dominates the scene.
- **Owner answer (27 Sep 2026): "Loosen it".** A builder loosens the look; the scene is re-rendered after.

## Not verified

- One agent judge; two pictures per round.
- The Vary buttons' new values are proven by the catalog tests. The page re-press, to confirm the buttons show 0.5 / 0.7 and
  0.45 / 0.65 without the "starting value" label, follows after this PR merges.
- The plan-form defect is not fixed here.
- The tiles are not tested in a game engine.
- No art acceptance, apart from the owner answers quoted above.
