# Second judge: SDXL VAE decode, plain against tiled (23 September 2026)

An independent second judgement of the lab's overnight experiment `sdxl-vae-decode`. The experiment rendered seven
subjects at one seed each, then decoded each latent three ways: plain, tiled 512 and tiled 1024. That makes 21 files in
ComfyUI `output/Research/overnight-20260923/sdxl-vae-decode/`.

- **Judge.** The review agent (Claude Opus 5.5), using the [rubric](../JUDGING-RUBRIC.md) with corrections R1–R6.
- **Independence.** The records were written before any lab record, key or README was read. The comparison with the
  lab's judgements came afterwards.
- **Content.** The subjects include named game and anime characters, three in non-nude fanservice framings (a skirt flare,
  a kimono off the shoulder, a swimsuit pin-up). All are canonically adult. None was skipped.

No image is committed: the pictures show named characters, and the repository is public. Every file is named by path, and
its sha256 is in [sdxl-vae-decode.judgements.jsonl](sdxl-vae-decode.judgements.jsonl).

## Method

1. **Numbers first.** For each subject, each tiled decode was measured against the plain decode:
   - the mean absolute difference, the maximum, and the share of pixels differing by more than 8;
   - for a seam test, the mean difference in every 8-pixel row and column band.
2. **Blind look at the worst places.** For each subject, the two 96×96 blocks where the three decodes differ most were
   cut out. The three versions went side by side under shuffled labels X, Y and Z, at 3× nearest-neighbour. The key
   stayed sealed until the look was written.
3. **Content.** Each subject's plain render was judged at full resolution, with crops of the faces and hands. Because the
   three decodes are indistinguishable, the same content scores apply to all three.

## Results

**The decodes are the same picture.** Measured against plain, 0–255 scale:

| Subject | tiled 512: mean / max / % > 8 | tiled 1024: mean / max / % > 8 |
| --- | --- | --- |
| action | 1.03 / 61 / 0.42 | 0.53 / 44 / 0.07 |
| duo | 1.23 / 77 / 0.57 | 0.61 / 33 / 0.07 |
| environment | 1.45 / 66 / 1.11 | 0.86 / 55 / 0.29 |
| glamour | 1.25 / 75 / 0.85 | 0.69 / 46 / 0.12 |
| hands | 1.04 / 63 / 0.44 | 0.55 / 35 / 0.07 |
| pinup-swim | 0.91 / 46 / 0.23 | 0.52 / 29 / 0.02 |
| portrait | 1.12 / 41 / 0.09 | 0.60 / 25 / 0.01 |

- **Tiled 1024 is about twice as close to plain as tiled 512** on every subject.
- **No seams.** The highest-difference 8-pixel bands fall on the *same* rows for both tile sizes: environment rows
  1129–1137, glamour 1000–1008, hands 1009–1017. A tile boundary would move with the tile size, so these bands are
  high-detail content edges. There, any decode difference shows first.
- **Blind look.** In all 14 of the worst-difference blocks, X, Y and Z could not be told apart at 3×. There was no grid,
  no banding and no colour shift.

**Content, the same for every decode.** Scores are adherence, anatomy, style, technical and composition:

| Subject | Scores | Verdict | Worst defect |
| --- | --- | --- | --- |
| action | 5 4 5 4 4 | keep | simplified gloved fingers on the hilt |
| duo | 5 4 5 4 4 | keep | a busy knot of hands and flower stems, still readable; no costume leak between the two characters |
| environment | 4 4 5 4 5 | keep | no crowds in the market |
| glamour | 5 4 5 4 4 | keep | hard outline halos, very saturated purples |
| hands | 5 5 5 4 5 | keep | pseudo-glyph text in the book; the cleanest hands in the set |
| pinup-swim | 5 4 5 4 4 | keep | the hand at the thigh tucks its fingers away |
| portrait | 5 5 5 4 4 | keep | slightly plastic jacket highlights |

## Agreement with the lab's judge

Compared after both sets of records existed:

| Measure | Result |
| --- | --- |
| Decode verdict (the three decodes indistinguishable, no seam) | **agree** on all 7 subjects |
| Picture verdict (21 files) | 15 of 21 agree (5 of 7 subjects) |
| Criterion scores (105) | 78 exactly equal; mean difference 0.29; 102 of 105 within one point |
| … adherence | 9 of 21 equal: the weakest criterion |
| … anatomy | 12 of 21 |
| … style, composition | 18 of 21 each |
| … technical | 21 of 21 |

**Where the two judges disagree, and who is right.**

- **pinup-swim, anatomy:** the lab scored 3 and "fixable"; I scored 4 and "keep". We saw the same thing: the hand at the
  thigh shows little more than a thumb and one nail. I named it, then scored it 4. That is exactly bias 1 from the
  calibration ("naming a defect but scoring it 4"), and rule R1 says it should be 3. **The lab is right.**
- **glamour, adherence:** the lab scored 3 and "fixable" (the weapon is a katana, not the naginata the brief asks for); I
  scored 5, reading it as a polearm. The weapon has a short curved blade with a guard at one end, a long dark shaft through
  both hands, and a round fitting at the far end. Both readings are defensible, and the owner or a closer look settles
  it. **Unresolved.**
- **portrait, adherence:** the lab took one point off because the ringed eyes render orange-amber, not the canon's yellow.
  I missed it. **The lab is right.**
- **action and duo, adherence:** the lab took one point off each. For action: the second hand is hidden, and a skirt
  flare suits a non-fanservice brief poorly. For duo: the prose brief gives the flowers to the other character, and I saw
  only the tag prompt. Both are fair points on brief details I did not have or did not weigh.

**What the disagreements say.** Two agent judges using the same rubric agree on everything *measurable*: decode
equivalence, technical faults, style. They drift on *adherence*: this judge scored it a point higher on four of seven
subjects, because the lab read the brief (canon eye colour, which character holds what) more closely. On picture
verdicts, 5 of 7 subjects agree. That matches the calibration's finding that a second agent judge adds a little, mostly
on details the first skimmed. It does not add a different eye.

## Answer to the experiment's question

**Tiled VAE decode at 512 or 1024 is safe to use on SDXL at 832×1216.** No visible difference, no seams, at any of the
seven subjects. Tiled 1024 stays closer to the plain decode. This judge did not measure speed or memory; those are the
lab's numbers.

Not verified: other resolutions, other seeds, or non-SDXL VAEs.
