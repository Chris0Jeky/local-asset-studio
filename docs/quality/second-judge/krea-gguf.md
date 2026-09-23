# Second judge: Krea 2 Turbo GGUF Q5_K_M against fp8 (23 September 2026)

This is an independent second judgement of the lab's overnight experiment `krea-gguf` (see #873). The experiment asks
whether the GGUF Q5_K_M build of Krea 2 Turbo, optionally with the text encoder on the CPU, draws as well as the fp8
build. The 16 renders are in ComfyUI `output/Research/overnight-20260923/krea-gguf/`:

- a four-way portrait group at one seed: fp8, fp8 with the CPU text encoder, GGUF, and GGUF with the CPU text encoder;
- a fifth GGUF portrait at another seed, with a cached encoder;
- a second portrait seed (probe): fp8 against GGUF;
- action and hands: fp8 against GGUF with the CPU encoder;
- five showcase cases on GGUF alone: duo, environment, glamour, pin-up swim, and a retro-anime LoRA case.

How this was judged:

- **Judge.** The review agent (Claude Opus 5.5) used the [rubric](../JUDGING-RUBRIC.md) with corrections R1–R6. The labels
  were its own shuffle within each subject, and the metadata was stripped.
- **Independence.** The records were written before any lab record, key or README was read. The comparison came
  afterwards.
- **Content.** The subjects are named characters, including non-nude fanservice framings of canonically adult characters
  (2B, Raiden Shogun, Yor Forger), plus an adult original character. Nothing was skipped.
- **What is committed.** No image, because the repository is public. The records, with sha256, labels, configurations
  and seeds, are in [krea-gguf.judgements.jsonl](krea-gguf.judgements.jsonl).

## Is the GGUF visibly softer?

**No.** Sharpness was measured as the mean absolute Laplacian, in grey levels:

| Group | fp8 | GGUF |
| --- | --- | --- |
| Portrait | 6.94 (GPU encoder), 7.32 (CPU encoder) | 6.97 (GPU encoder), 6.99 (CPU encoder) |
| Portrait, second seed | 8.51 | 8.43 |
| Action | 11.88 | 11.66 |
| Hands | 9.48 | 9.29 |
| LoRA case, against the earlier fp8 render of the same prompt and seed | 10.13 | 10.46 |

At 1.4–2.5× crops, the hair strands at the ear, the eyelashes, the book text and the fabric folds look equally crisp in
every pair.

**The one visible difference is not systematic.** In the four-way portrait, both fp8 renders drew Makima's irises as
crisp double rings, and both GGUF renders drew a single ring round a dot. That is less canonical, so adherence was scored
4 on those two. On the second portrait seed the pattern reversed: GGUF drew the double rings and fp8 the single one.

**The text encoder barely matters.** GPU against CPU encoder differs by 1.9 grey levels on GGUF (near-identical) and 6.8
on fp8. fp8 against GGUF differs by about 10.5. So the weights, not the encoder, decide which small details a seed lands
on. Neither build is better at those details.

**Recognisability and LoRA fidelity hold.** Every named character is recognisable on the GGUF build: Makima, 2B, Tifa and
Aerith (costumes kept, no leakage), the Raiden Shogun, and Yor Forger. The Yor hairband is cream with a gold rose, not
gold. The retro-anime LoRA look arrives in full: the same face and composition as the fp8 render of that prompt and seed
(mean difference 12.0).

**Verdicts.** All 16 renders are "keep". The lab's "blind tie" holds.

## Agreement with the lab's judge

The comparison covers 15 pictures. The GGUF cached-encoder portrait is in this set only.

| Measure | Result |
| --- | --- |
| Verdicts | 15 of 15 agree (all keep) |
| Criterion scores (75) | 60 exactly equal; mean difference 0.20; all 75 within one point |
| … style, technical | 15 of 15 each |
| … adherence, anatomy | 12 of 15 each |
| … composition | 6 of 15: the lab gave 5 where this judge gave 4 on the portraits and hands |

**The same worst defect, named independently.** On every portrait, both judges picked the same worst defect: a hard,
plastic-looking white highlight on the shirt front.

**Where the two judges differ, all within one point:**

- This judge took an adherence point off the two single-ring GGUF portraits, and the Yor hairband.
- The lab took points for framing: the skirt flare in the action case, and a blade cropped by the frame in glamour.
- The lab is more generous on composition.

This is the second of tonight's lab-against-review comparisons. On sdxl-vae-decode, picture verdicts agreed on 5 of 7
subjects and adherence was again the least-agreed criterion. The pattern holds: the two agent judges agree on faults and
verdicts, and drift by one point on the softer criteria.

## Not verified

- Speed and memory, which are the lab's numbers.
- Any seed beyond the three used.
- The GGUF build with other LoRAs.
- Whether the owner sees a difference.
