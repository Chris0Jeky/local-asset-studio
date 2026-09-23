# Second judge: Z-Image fp8 with the text encoder on the CPU (23 September 2026)

This is an independent second judgement of the blind A/B in the lab's `zimage-fp8` experiment (#893). It compares three
builds of the shipped `zimage` graph:

- the fp8 build with the text encoder on the CPU;
- the fp8 build with the encoder on the GPU;
- the bf16 build with the encoder on the CPU.

It ran three showcase cases (portrait, action, hands), each at a fixed seed. The prompts were checked before viewing:
all three show clothed adults. Two of them name famous characters, so no images are committed.

**How it was judged.** The review agent (Claude Opus 5.5) judged the nine pictures blind:

- per case, under its own A/B/C shuffle, with metadata stripped;
- with the face, the sword hands and legs, and the flask and book hands cropped at 2×;
- before reading the key or any lab record.

The records are in [zimage-fp8.judgements.jsonl](zimage-fp8.judgements.jsonl).

## Result: the blind tie holds

| Case | fp8, CPU encoder | fp8, GPU encoder | bf16, CPU encoder |
| --- | --- | --- | --- |
| portrait | keep (4.8) | keep (4.8) | keep (4.8) |
| action | keep (4.4) | keep (4.4) | keep (4.4) |
| hands | keep (4.6) | keep (4.8) | keep (4.6) |
| wall time | 46–77 s | 72–534 s | 71–149 s |

The numbers in brackets are each picture's mean score.

- **All nine are keeps.** The configuration means are 4.6, 4.67 and 4.6, all within 0.3, so they tie.
- **The encoder's device barely changes the picture.** The two fp8 renders of each case are near-identical. The bf16
  build draws a slightly different picture from the same seed.
- **Defects shared by every configuration:**
  - the portrait's irises are plain yellow, without the rings the prompt asks for;
  - the two gloved hands on the sword hilt merge into one black mass.

## Agreement with the lab's judge

| Measure | Result |
| --- | --- |
| Picture verdicts | **9 of 9** agree: all keeps |
| Criteria exactly equal | 24 of 45 |
| … style | 9 of 9 |
| … adherence | 0 of 9 |

On adherence, the lab gave 5 where this judge gave 4 for the missing eye rings or the sword grip. Elsewhere the two
judges differ by one point either way. No difference separates the configurations.

**Answer to the lab's claim.** Confirmed: fp8 with the CPU encoder matches bf16 on quality. On these three cases it takes 46–77 s, against
532–534 s for fp8 with the GPU encoder on the two cases that spilled.

## Not verified

- One seed per case, three cases.
- The proposed `zimage-fast` preset has had no Studio proof (#893).
- Nothing here is art acceptance, and it is not a licence claim for the third-party fp8 file.
