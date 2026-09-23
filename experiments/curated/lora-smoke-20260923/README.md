# LoRA smoke tests: WAI v17, NoobAI-XL 1.1, Pony V6 (23 September 2026)

Issues #757 (Illustrious LoRAs on WAI v17), #758 (NoobAI LoRAs, hobby/non-commercial) and #759 (Pony V6 LoRAs).
The LoRAs came from the scavenger shortlists in `docs/research/CIVITAI-SCAVENGE-2026-09-21.md`.

**Three states, kept apart.** *Generated*: every run below completed on this PC. *Inspected*: an agent opened
every PNG, and the notes are that agent's own words. That is not art acceptance, which stays with the owner.
*Licensed*: nothing here is cleared. The civitai flags are recorded next to each pin in `models/library.json`,
and a flag is not a licence. **NoobAI results are hobby/non-commercial only** under the checkpoint author's terms,
whatever a LoRA's own flags say.

## Method

- Backend: primary ComfyUI on 127.0.0.1:8188 (version 0.35.0), called directly with `POST /prompt` and polled on
  `/history`. This was not a Studio job. The GPU was leased to this worker through `.runtime/gpu-lease.json` from
  01:41 to 01:56 BST and released afterwards. One job ran at a time.
- Graph: each checkpoint's shipped preset graph (`workflows/api/wai-api.json`, `noob-api.json`, `pony-api.json`).
  LoRA slot 8 took one LoRA at one strength on both model and clip, and slot 9 stayed at 0. The exact submitted
  graphs are in `graphs/`, and the script is `research-scripts/lora_smoke.py`.
- Fixed for the whole set: seed `2026092301`, 832x1216, the preset's own steps/CFG/sampler (WAI 30 / 5.0, NoobAI
  28 / 5.5, Pony 30 / 6.0 with clip skip 2; all `euler_ancestral` / `normal`). One SFW subject went in each
  checkpoint's own prompt convention: an adult elf mage, fully clothed, in a candlelit library, holding a
  glowing orb with both hands. WAI got the quality tail and no score tags. NoobAI got the quality/`safe` prefix.
  Pony got the `score_9…score_4_up, source_anime, rating_safe` prefix, with `rating_explicit, rating_questionable`
  added to its negative. All three negatives carried `nsfw`. Five LoRAs got a trigger appended, as recorded per run
  in `results.json` (`trigger`):
  - Micro Details: `addmicrodetails`;
  - Velvet Colorful Lines: `C0lorL1nes`;
  - Flat Color: `flat color, no lineart`;
  - Gothic Neon: `g0thicPXL`, the first word of its card trigger only;
  - Dramatic Lighting: `s1_dram`.

  *Correction, 23 September 2026 (#857):* the two Masterpiece LoRAs' civitai versions do list a trigger (`masterpiece, best
  quality, very aesthetic`), and it was **not** appended. The earlier sentence "a trigger was appended only where the civitai
  version lists one" was wrong. WAI's own tail and NoobAI's prefix already carry `masterpiece, best quality`, but not
  `very aesthetic`. The `presets/settings-kb.json` advice to put that trigger at the end of the prompt is therefore
  untested by this smoke.
- Per checkpoint: one control with no LoRA, then two strengths per LoRA inside the shortlist's range.
- **Two failures, two retries.** The first NoobAI control (`0a7c2416…`) and the first Pony control (`df9f943f…`)
  both failed in node 1, `CheckpointLoaderSimple`, before sampling. The error was `IndexError: list index out of
  range` in `comfy/model_management.py free_memory`. This is the known first-checkpoint-swap race recorded on
  14 September. Each was retried once, deliberately, and the retry succeeded. Both prompt IDs are in `results.json`.
- Timings are wall seconds from submit to history, 20-56 s per image. They include the 4-second history poll,
  the LoRA patch and any host paging. Nobody investigated the slow ones: NoobAI Masterpiece at 56 s and 44 s, and
  Hands Pony 0.6 at 48 s, whose 0.85 run took 24 s.

Sheets: `examples/lora-smoke/wai-illustrious-loras.jpg`, `noob-hobby-loras.jpg` and `pony-v6-loras.jpg`
(control first, then each LoRA at its two strengths). Full records, including every prompt ID, LoRA SHA-256,
output SHA-256, start and finish time and inspection note: `results.json`.

## #757 WAI v17 (Illustrious): 5 LoRAs, 11 renders, 01:42:56-01:47:27

| Run | Prompt ID | s | What the render shows |
|---|---|---:|---|
| control | `4c84f6ec` | 41.6 | Glossy semi-real WAI anime; orb floats above one open hand (not "both hands"); hands plausible |
| Stabilizer illus01 0.5 | `c5f7e402` | 29.1 | Painterly, less gloss, deeper library; orb cupped in both hands; clean |
| Stabilizer illus01 0.7 | `76142942` | 20.1 | Stronger: 2.5D semi-real, dense ornament; clean, but furthest from the WAI look |
| Hands Illu 0.6 | `6e055542` | 24.1 | Almost the control's frame; raised hand slightly cleaner; style unchanged |
| Hands Illu 0.85 | `144670da` | 24.1 | Same frame; hands clean; orb contents drifted to a green leaf crystal |
| Masterpiece v3 0.4 | `703b8be2` | 24.1 | Softer, more illustrative, warm light; orb above two open palms; clean |
| Masterpiece v3 0.6 | `3492b32d` | 20.1 | Moodier and heavier; one palm slightly awkward |
| Micro Details v7 0.35 | `02084a40` | 24.1 | Crisp, high-contrast cel line; small grey mark near one eyebrow |
| Micro Details v7 0.5 | `ffcd0ea9` | 20.1 | Same, a little more detail; the mark is gone; clean |
| Velvet Colorful Lines 0.6 | `3ebfe3fe` | 24.1 | Real style shift: glowing teal/green line accents, bolder colour; clean |
| Velvet Colorful Lines 0.85 | `e76b1034` | 20.1 | Heavier outlines, velvet sheen; palette moves from navy/gold to teal/brass |

**Winners:** Masterpiece v3 at 0.4 (a gentle aesthetic lift and the best "both hands" read); Stabilizer at 0.5
(better hand-orb interaction, still recognisably WAI); Velvet Colorful Lines at 0.6 (the one real style option).
**Keep as utilities:** Micro Details at 0.5 (0.35 left a small mark). Hands Illu at 0.6-0.85 changed nothing
measurable, because the control's hands were already fine at this seed. This smoke cannot prove a hand fix.
**Losers (drop these strengths):** Stabilizer 0.7, Masterpiece 0.6 and Velvet 0.85, which overshoot the brief.
No LoRA collapsed and none showed wrong-base symptoms. The issue's 0.6-0.85 band suits Hands and Velvet. The
utilities' own card ranges sit lower (Masterpiece 0.3-0.6, Micro Details 0.3-0.5), and they were tested there.

## #758 NoobAI-XL 1.1 (eps): 3 LoRAs, 7 renders, 01:48:52-01:52:42. Hobby/non-commercial only

The installed checkpoint is the **epsilon-prediction** release (`Laxhar/noobai-XL-1.1`). The NoobAI builds of
Flat Color (`1132089`) and MeMaXL (`269772`) are **all v-pred**, so neither was downloaded for NoobAI. The
Illustrious Flat Color build stood in for them, because Illustrious v0.1 is NoobAI eps's parent. The Stabilizer
(`nbep11` = NoobAI eps 1.1) and Masterpiece (`noobai-e-pred-1`) builds match the installed prediction type.

| Run | Prompt ID | s | What the render shows |
|---|---|---:|---|
| control (failed) | `0a7c2416` | 56.0 | `CheckpointLoaderSimple` IndexError before sampling; retried once |
| control | `9cee0f82` | 32.1 | Soft, flat NoobAI anime, over-the-shoulder, both hands raised under the orb |
| Stabilizer nbep11 0.6 | `66a21520` | 29.2 | Flips to a semi-real 3D render; orb turned amber; clean |
| Stabilizer nbep11 1.0 | `e40fee56` | 24.1 | Author's strength: anime face on a rendered body; orb pushed off-frame, hands empty |
| Masterpiece eps 0.4 | `2a8701b8` | 56.2 | Keeps the NoobAI look, warmer and painterly; faint red/cyan fringe on outlines |
| Masterpiece eps 0.6 | `801410cb` | 44.1 | Near-identical to 0.4, smoother shading; the fringe is still faint |
| Flat Color (IL) 0.6 | `d90820c3` | 24.1 | Clean flat-colour, no-lineart cel look; no wrong-base symptoms |
| Flat Color (IL) 0.85 | `164ff66c` | 20.1 | Flatter, softer palette, orb cupped in two hands; the most coherent of the set |

**Survive for hobby-only presets:** Flat Color (Illustrious build) at 0.85, and Masterpiece eps at 0.4.
**Drop for these prompts:** the Stabilizer. Its card says it has no default style and must be steered with style
words. With none in this prompt, it replaced NoobAI's anime look with a semi-real render, and at the recommended
1.0 it lost the orb. Retest it only with style tags in the prompt.
**Licence banner:** the `noob` preset's `commercial_note` in `presets/catalog.json` reads "Author terms prohibit
commercialization including generated products". Whether the page shows it prominently enough before a share is
not verified here.

## #759 Pony V6: 3 LoRAs, 7 renders, 01:53:33-01:56:42

| Run | Prompt ID | s | What the render shows |
|---|---|---:|---|
| control (failed) | `df9f943f` | 24.0 | `CheckpointLoaderSimple` IndexError before sampling; retried once |
| control | `6f6f93c5` | 28.1 | Washed painterly Pony; **youthful-looking face despite "adult woman"**; a candle flame in the open palm |
| Gothic Neon 0.6 | `0c8655e1` | 20.3 | Moody painterly, rose window, adult face; holds a book (drift); no neon |
| Gothic Neon 0.85 | `06f0b24e` | 20.1 | Symmetric gothic portrait, orb in both hands, adult face; ears over-saturated; still no neon |
| Dramatic Lighting 0.6 | `5f795533` | 20.1 | Warm backlight and rim light, cleaner colour; book drift; youthful face |
| Dramatic Lighting 0.85 | `ecda2f29` | 28.1 | Hard chiaroscuro; hair became a bob; teal smoke smudge by the orb; youthful face |
| Hands Pony 0.6 | `c311be06` | 48.1 | Control's frame; the candle-in-palm confusion is gone, clean open hand |
| Hands Pony 0.85 | `5e36b6ac` | 24.1 | Same, slightly longer fingers, a little more ornament |

**Keep:** Gothic Neon at 0.85 (the best prompt adherence and the only adult-reading face in the Pony set);
Hands Pony at 0.6 (a pure utility; at this seed it removed the control's candle-in-palm confusion without any
style change); Dramatic Lighting at 0.6 (a clean lighting lift). **Drop:** Dramatic Lighting at 0.85 (bob,
smudge, youthful face).

**Prompt conventions that mattered:**
- The Pony score prefix plus `rating_safe`, with `rating_explicit, rating_questionable` in the negative, kept every
  Pony render clothed.
- Pony V6 drew a youthful face for "adult woman" in the control, and Dramatic Lighting did not correct it. Pony
  prompts should carry stronger adult cues; which cues work is untested.
- Gothic Neon's card trigger is `g0thicPXL, glowing, neon`. This smoke appended only `g0thicPXL`, and no neon
  appeared at either strength. The full trigger is untested.
- Score tags were used on Pony only, never on WAI or NoobAI, as the shortlist says.

## Not verified

- One seed and one subject. A winner here is a smoke pass, not a measured optimum. Hands LoRAs are unproven where
  the base already drew good hands.
- LoRA stacking (for example Stabilizer + Masterpiece, or Hands + a style) was not tested; every run used one LoRA.
- No Studio job ran. The pins install through `ModelLibrary`, but the Studio's LoRA dropdowns and settings guidance
  were not opened in a browser.
- The owner has not judged any render, and no licence was cleared.
