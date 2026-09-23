# q-32 retest: four LoRA candidates against their no-LoRA controls — 23 September 2026 (overnight lab)

**Question** (the review judge's request, PR #862). The #846 smokes ran one seed each. Do the four q-32 candidates beat their
own base checkpoint without the LoRA, on three seeds, under the rubric with R1-R7?

**Method.** `q32_loras.py render`, 04:36-04:43 local, straight to the primary ComfyUI (PID 56556). Three showcase cases from
`../suite.py`, each with its fixed seed: `portrait` (Makima), `action` (2B) and `hands` (the original alchemist).

| candidate | base | strength | trigger (appended at the end) |
| --- | --- | --- | --- |
| Aesthetic Masterpiece v3 (`illustrious_masterpieces_v3`) | WAI v17 | 0.4 | masterpiece, best quality, very aesthetic |
| Add Micro Details v7 (`AddMicroDetails_Illustrious_v7`) | WAI v17 | 0.5 | addmicrodetails |
| Flat Color v2 (`illustrious_flat_color_v2`), hobby only | NoobAI XL 1.1 | 0.85 | flat color, no lineart |
| Gothic Neon (`g0th1cPXL`) | Pony V6 | 0.85 | g0thicPXL, glowing, neon |

- **Graphs.** Each base's control is the shipped graph with no LoRA and no trigger. The shipped graphs are `wai`, `noob` and
  `pony` (with its clip skip). Every case carries the SDXL adult-only negative. Pony's prompts add mature female, tall, adult
  proportions and adult face.
- **Decode.** `VAEDecodeTiled` 512/64 (`../sdxl-vae-decode/`: pixel-equivalent to the shipped decoder).
- **Blind judging.** 21 renders; `seal` shuffled each (base, case) group under letters. Every judgement was written before the key
  was read (`judgements.jsonl`). One caveat: the WAI control is recognisable from the sdxl-vae-decode renders (same graph, seed
  and prompt), so the WAI groups were blind only between the two LoRAs.

Images of famous characters stay local: ComfyUI `output/Research/overnight-20260923/q32-loras/index.html`. The Git sheet
`examples/overnight-20260923/q32-loras-sheet.jpg` shows only the original-character `hands` case.

## Results (unblinded)

| configuration | portrait | action | hands | mean | verdicts |
| --- | --- | --- | --- | --- | --- |
| WAI control | 4.6 | 4.2 | 4.6 | **4.47** | keep, keep, keep |
| WAI + Masterpiece 0.4 | 4.6 | 4.2 | 4.6 | **4.47** | keep, keep, keep |
| WAI + Micro Details 0.5 | 4.6 | 4.2 | 4.6 | **4.47** | keep, keep, keep |
| NoobAI control | 4.6 | 4.0 | 3.8 | **4.13** | keep, fixable, fixable |
| NoobAI + Flat Color 0.85 | 4.4 | 3.6 | 3.8 | **3.93** | keep, fixable, fixable |
| Pony control | 4.4 | 3.8 | 3.8 | **4.00** | keep, fixable, fixable |
| Pony + Gothic Neon 0.85 | 4.4 | 3.6 | 3.8 | **3.93** | fixable, fixable, **reject** |

**Every candidate ties its control** (within 0.3 on the mean). None measurably improves on its base under this rubric.

- **WAI Masterpiece 0.4 and Micro Details 0.5.** All nine WAI pictures are clean and score the same.
  - The differences between them are looks only: Micro Details darkened the alchemist's hair, Masterpiece gave her a turtleneck,
    and one gave 2B a less dynamic arms-up stance.
  - Under R6 this is not a recommendation; the owner judges the look in the gallery.
- **NoobAI Flat Color 0.85.**
  - The flat-colour look arrives as intended.
  - Its action picture fused both gloved hands on the hilt into one mass. The control's action picture had a bow-shaped blade
    instead.
  - Both hands pictures swapped props (a beaker and a pen; a second flask) instead of the hand resting on the book, with and
    without the LoRA.
- **Pony Gothic Neon 0.85.**
  - The neon-gothic look is strong.
  - On the hands case it **replaced the subject**: a white-haired woman in black leather with a bottle before a rose window, with
    no apron, coat or book. That is the one `reject` in the set.
  - It also recoloured Makima's white shirt dark.
  - With the strong adult cues, no Pony face read as youthful; nothing was discarded.
  - Neither Pony action picture drew the ruined city.

## Verdict

None of the four candidates earns a default. The q-32 decision stays the owner's: whether a LoRA's look is worth adding is a
taste call (R6), and on defects and brief adherence they tie their controls. If Gothic Neon is kept as an option, expect it to
override the subject and palette at 0.85; its 0.6 setting is untested here.

## Not verified

- Three cases per base. Lower strengths and other checkpoints were not tried.
- The WAI groups were only partly blind (see the method).
- None of this is art acceptance or licence clearance. NoobAI stays hobby-only; Gothic Neon's civitai flags allow RentCivit only.
