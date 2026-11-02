# Character sheet and locked repaint, proofs (1 November 2026)

Two presets on the primary backend, ComfyUI 0.35.0, AMD RX 9070 XT. Recipes are the shipped graphs with the controls below,
so `workflows/api/character-sheet-klein-9b-api.json` and `workflows/api/union-repaint-wai-api.json` are the exact recipes.
Agent inspection only. Nothing here is art acceptance or licence clearance.

## `character-sheet-klein-9b`

| run | route | seed | source | prompt ID | time |
| --- | --- | --- | --- | --- | --- |
| 1 | direct graph | 20261101 | fantasy pack full body | `a3380649-f5d7-46ea-8a16-e72d139dae86` | 104.0 s, first load |
| 2 | direct graph | 20261102 | fantasy pack full body | `e1f56ff7-8c61-431c-9075-1062780eade7` | 62.0 s |
| 3 | direct graph | 20261101 | adapter showcase sheet | `ab5ffe70-9b32-4f6a-a3c0-3258c3d58673` | 84.5 s |
| 4 | direct graph | 20261102 | adapter showcase sheet | `a7cc2c5a-c537-465b-b416-96804b3185b2` | 43.8 s |
| 5 | Studio job `842dcb86-715c-4959-81b3-2aefe8306683` | 20261102 | fantasy pack full body | `3ed470e8-19f2-4641-a258-44c58e4bf25b` | 104.5 s, client wait after a model switch |

8 steps, CFG 1, 1536×1024, LoRA strength 1.0. The card says beta57; these used the repository's Flux2Scheduler.

Agent's words: all five sheets show front, side and back on white with head and feet level. Costume carried, including the
satchel and lantern. Eye colour changed from the source on the showcase picture, and proportions differ between views.

## `union-repaint-wai`

| run | route | denoise | prompt ID | time |
| --- | --- | --- | --- | --- |
| 1 | direct graph on the fantasy pack picture | 0.45 | `e564cfda-1507-44eb-b9ef-3c1cf6770cd1` | not recorded: the client timed out during first load |
| 2 | direct graph on the fantasy pack picture | 0.7 | `b3fc1971-43d5-4e1c-8e5a-ac816b19671b` | 13.7 s warm |
| 3 | Studio job `49c9f6f4-d433-4605-aecf-b586a50e1ea4` on a cafe render | 0.45 | `f0135ee3-081f-4a46-bfaf-92cb12da66cd` | 120.8 s, client wait after a model switch |
| 4 | Studio job `49323960-bd2a-4c7e-b924-6524980260bd` on the pack picture | 0.45 | `8b0d63fa-c270-4166-aacc-f44d8e3b68da` | status `uncertain`, not resubmitted |

Seed 20261101, 30 steps, CFG 5, depth 0.8, line art 0.6, prompt "masterpiece, best quality, 1girl, solo, soft cel shading,
clean lineart, anime game character art" (runs 1 and 2 also named the costume).

Agent's words: at 0.45 and 0.7 pose, costume, props and background stayed in place and the finish changed. Run 3 kept every
shape, and the eyes went from pink to blue. So geometry is locked and colour is not. A prompt asking for a plain background
did nothing at these settings. Strengths were not swept.

## Host limit

Run 4 failed because the host did, not the preset. ComfyUI had loaded Anima, Klein 9B and WAI in turn, held 30 GB, and free RAM
reached zero. The Studio's history reads failed with WinError 10055. The Studio reported 14.1 GB of GPU memory overflow on
run 3. `POST /free` recovered 14 GB, and later runs passed with a free between families, tracked in #1893.

Not verified: identity scores for these presets, a real 3D view as the repaint source, and any owner judgement
(`character-sheet-art-1101`).

## Colour lock

The owner judged the unlocked repaint not usable: "the strong eye drifts and imperfections stand out way too much as is". On one
source picture with violet eyes, nine direct renders (seeds 20261101 to 20261103, about 21 s each):

| prompt | denoise | eyes | face chroma error | with the lock |
| --- | --- | --- | --- | --- |
| no colours named | 0.45 | blue | 6.55 to 8.63 | 1.84 to 1.88 |
| colours named | 0.45 | pink-red | 5.95 to 7.70 | 1.85 to 1.89 |
| colours named | 0.30 | pink-red | 5.02 to 5.85 | 1.84 to 1.85 |

Prompts `b92bc981-c8d4-480e-9a64-1102ef2c02f3` to `d0c76fa0-f08b-4f6b-ab0d-60489883e9b7`. Naming the colour did not hold it, and
"pink" was the agent's word for violet eyes. The lock keeps the repaint's lightness and takes per-pixel colour from the source.

Through the Studio with the lock: job `4dce7a5b-e9cd-4c30-8236-98f24a58334e`, prompt `fed045ef-c71d-4714-95d0-1bf63a2f465a`, 94.8 s
after a model switch with 10.3 GB overflowing into system memory (#1893), face chroma error 1.94. An agent compared the eyes with
the source and they match. One source picture only. The owner has not judged locked output.

Earlier uncertain job `49323960-bd2a-4c7e-b924-6524980260bd`: ComfyUI's history still held prompt `8b0d63fa-c270-4166-aacc-f44d8e3b68da`
as a success, so Resume observation closed it as completed on 1 November 2026. Nothing was resubmitted.
