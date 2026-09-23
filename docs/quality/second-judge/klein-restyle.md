# Second judge: the Klein restyle wording fixes (23 September 2026)

This is an independent second judgement of the lab's `klein-restyle` experiment (#883). It tests the two defects that the
[q-27 pre-review](../pre-reviews/q-27.md) found in the Klein 4B restyle of the throne witch:

- the hair and eye colours drift;
- the raised foot comes out as a toe-less, wrapped tip.

Three wordings were each run at three seeds (2026091401, 2026092351, 2026092352), all through the Studio's `restyle-klein`
recipe:

- the shipped wording;
- the wording with "long purple hair, blue eyes" and "bare feet";
- the same colours with "a beige thigh-high stocking on the raised leg".

The source is `Style-Pose/Nova_00004_.png`. The owner ruled on 23 September 2026 that it shows an adult original, so it was
judged in full. It is framed as a pin-up, which is judged on technical grounds only.

**How it was judged.** The review agent (Claude Opus 5.5) judged the nine outputs blind:

- under its own shuffled labels, with metadata stripped;
- with crops of the face and eye and of the raised foot for every picture;
- with the wording read from each file's embedded prompt only after the records were written;
- before any lab record was read.

The records are in [klein-restyle.judgements.jsonl](klein-restyle.judgements.jsonl). No images are committed.

## Results

| Wording | Hair and eye colours kept | Raised foot | This judge's verdicts |
| --- | --- | --- | --- |
| shipped | **1 of 3** | wrapped, toe-less tip on 3 of 3 | 3 fixable |
| + "long purple hair, blue eyes" + "bare feet" | **3 of 3** | bare foot with five toes on 2 of 3; toes under a pale band on seed …52 | 2 keep, 1 fixable |
| + the same colours + "beige thigh-high stocking on the raised leg" | **3 of 3** | a clean stocking foot on 3 of 3 (a faint band on one) | 3 keep |

The shipped wording lost the colours on two seeds:

- seed …01: black hair and a violet-pink eye;
- seed …52: black-grey hair and a grey-violet eye.

Seed …51 kept a dusky mauve with a blue eye. Naming the colours fixed all three. Seeds …52 in both colour-named wordings
came out paler, a silver-lavender, but still purple-tinted.

**Answer to the lab's claim.** Confirmed in substance:

- Naming the colours keeps them on 3 of 3.
- Naming the stocking gives a proper stocking foot on 3 of 3.
- "Bare feet" gives toes on 3 of 3, but one seed wraps a band over them.

This judge counts the shipped wording's toe-less foot on 3 of 3, where the lab counts 2 of 3. The difference is one foot
(seed …52), whose toes show under a band. The lab read it as a sandal band, and this judge as the same wrap.

**Recommendation.** Ship the stocking wording as the default for this source, or better, derive the colour and clothing
words from the source picture rather than from its prompt. The prompt says "long dark hair", but the picture shows purple.

## Agreement with the lab's judge

The lab's records are in its PR #883 (`experiments/curated/overnight-20260923/klein-restyle/judgements.jsonl` there); merge that first so this comparison can be traced in the tree.

| Measure | Result |
| --- | --- |
| Picture verdicts | **8 of 9** agree |
| Criteria exactly equal | 35 of 54 |
| … style, technical | 9 of 9 |
| … composition | 0 of 9: the lab gave 5 throughout, this judge 4 |

The one verdict difference is the "bare feet" seed …52: sandal band (lab, keep) against wrap band (this judge, fixable).

Across the night's five lab-against-review comparisons:

| Experiment | Picture verdicts agreeing |
| --- | --- |
| VAE decode | 5 of 7 subjects |
| Krea GGUF | 15 of 15 |
| Combine | 12 of 12 |
| Hand inpaint | 10 of 18 (records in #882, `second-judge/hand-inpaint.md`) |
| Restyle | 8 of 9 |

Composition is the criterion where the two judges differ most consistently: the lab is one point more generous.

## Not verified

- Other sources.
- Other seeds.
- Whether the owner prefers the stocking or the bare foot. That is a taste question (R6).
