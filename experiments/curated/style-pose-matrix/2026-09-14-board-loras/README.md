# Style board × new LoRA sweep, and the board combine probes — 14 September 2026

Thirteen Studio jobs through `scripts/style-pose-matrix.py` ([`manifest.json`](manifest.json), [`plan.json`](plan.json))
on the three-slot **style board**: the KonoSuba character sheet, the KonoSuba group art (adult cast) and the braided
bodysuit study from the owner's Asset library, all three encoded and, in this sweep, **concatenated** at board weight 0.8.
Pose picture: the seated throne illustration. Prompt, seed (2026091410), canvas (832×1216) and pose strength (0.9) as in
the checkpoint matrix. One new LoRA per cell on WAI v17 (ten cells) and the baseline plus the two best guesses on YumeFlux
(three cells). Sheets: [`board-lora-sweep-wai.jpg`](../../../../examples/style-pose/matrix/board-lora-sweep-wai.jpg),
[`board-lora-sweep-yumeflux.jpg`](../../../../examples/style-pose/matrix/board-lora-sweep-yumeflux.jpg).

Five direct ComfyUI probes ([`probes.json`](probes.json), prompt ids inside) then varied only the board on the WAI +
Mishima 0.8 cell: combine `average` at 0.8, `concat` at 0.5, `average` at 0.6, two pictures averaged at 0.8, and the sheet
alone at 0.8. Sheet: [`board-combine-probes.jpg`](../../../../examples/style-pose/matrix/board-combine-probes.jpg).

## What was seen (one seed; my reading, not art acceptance)

- **Three pictures concatenated at 0.8 over-drive the look**: every WAI cell in the sweep came out harsher and more
  saturated than the single-sheet matrix cell, with heavy outlines and neon skies. The pose held in all thirteen cells.
- **Averaging fixes it.** `average` at 0.8 and especially at 0.6 gave clean lineart, the sheet's warm palette and a calmer
  background; `concat` at 0.5 was acceptable; two pictures averaged drifted pinker (the group art's palette); the sheet
  alone drifted to a softer, more generic WAI look. The recipes now default to `average` at board weight 0.7.
- **LoRAs, on the over-driven concat board** (so read them as relative): Mishima Kurone 0.8 gave the cleanest light-novel
  lineart and the most "official art" faces; Fantastic Days 0.9 added sparkle and rim light; Glossy 1.0 and Shiny 0.8
  pushed skin highlights; Konosuba SD8 0.8 went softer and pinker; Detail enhancer 0.7 shifted the palette green and
  over-sharpened, so it is not a free upgrade; Momoko 0.8 went darker with striped rim light; Mishima 0.7 + Glossy 0.6
  was the best combination, Mishima 0.7 + Detail 0.6 the worst. On YumeFlux the board pulled the palette blue and the
  Mishima cell again read most like the sheet.
- **Timing**: 71–311 s per cell, the same reload spread as the checkpoint matrix; probes 66–204 s.

## Recommendation for the next round

WAI v17 or YumeFlux, board `average` at 0.6–0.7, Mishima Kurone 0.7–0.8 (trigger `mishimakurone`) with Glossy 0.5–0.6 as
the second slot, Fantastic Days 0.9 as the alternative first slot for splash-art sparkle. Not verified: any seed other
than 2026091410, the beach pose on the board, strengths other than the ones above, licence terms (recorded in
`models/library.json`, never inferred).

## Verifying runs on the averaged board (defaults as shipped)

| Recipe | Studio job | Prompt | Seconds | Seen |
|---|---|---|---|---|
| wai | `12be1c70-cd3b-456c-ae47-371e4b58f1ce` | `a0e13d48-d073-4313-9451-e96646e4aec5` | 121 | seated with the knee raised, one eye closed and the hand on the throne arm as in the pose picture; clean light-novel lineart with glossy skin highlights, the sheet's brown-black-gold witch costume with diamond trim, a starry dark-blue sky borrowed from the board's group art; no text, no extra limbs. |
| yumeflux | `1a07713c-a1b6-4c56-ab22-29743658e3de` | `c020c7f5-9124-4cb3-ab1e-18fdd2342574` | 275 | same pose held; the throne is fully drawn in red and gold, the costume is glossier and more saturated, the background a blue energy swirl; face and hands clean. |

Board: the same three pictures, averaged at the authored 0.7; throne pose; Mishima Kurone 0.8 + Glossy 0.6; seed
2026091410. JPEG copies: `examples/style-pose/board-verify-wai.jpg`, `board-verify-yumeflux.jpg`; hashes in
[`verify.json`](verify.json). These two runs are what `verified: true` on the WAI and YumeFlux recipes refers to; the
Animagine and CSTati boards stay unverified.
