# Second judge: the Combine routes re-proved on an adult original pair (23 September 2026)

This is an independent second judgement of the lab's `combine-adult` re-proof (#875). The re-proof put the fantasy pack's
traveller portrait, an adult original character, into one spellcasting pose (wide stance, one arm raised, one arm out),
on four Combine routes. Each route ran through the Studio with three seeds:

- **depth**: the depth map, uncut;
- **depth-cut88**: the depth map, cut at 88 %;
- **copypose**: Copy Pose;
- **skeleton**: the drawn skeleton.

**How it was judged.** The review agent (Claude Opus 5.5) judged all twelve outputs under its own shuffled labels (X01–X12),
with metadata stripped, using the [rubric](../JUDGING-RUBRIC.md) and R1–R6. It saw the character picture and the pose
picture, but no key. All records were written before any lab record was read. The drawn skeleton itself was not shown.

**What is committed.** No images. The records hold the sha256 and the Studio job and prompt IDs:
[combine-adult.judgements.jsonl](combine-adult.judgements.jsonl).

## Results

| Route | Seed …41 | Seed …42 | Seed …43 | Keeps |
| --- | --- | --- | --- | --- |
| skeleton | keep | keep | keep | **3 / 3** |
| copypose | keep | keep | fixable (pose mirrored; the forward hand rests at the hip) | 2 / 3 |
| depth | reject (blank face, grey hands) | keep | reject (blank dark face) | 1 / 3 |
| depth-cut88 | reject (blank face, grey hands) | keep | reject (blank dark face) | 1 / 3 |

- **Skeleton is the reliable route on this pair.**
  - All three seeds keep the portrait's fringe, brown eyes, gold earrings, teal scarf and navy coat, with clean
    five-digit hands.
  - The pose follows the picture.
  - The finish is flatter, a clean cel look, not the portrait's painterly shading.
- **Copy Pose keeps the most of the portrait's look.**
  - On seed …42 it even keeps the station-platform background and the semi-painterly finish.
  - On seed …43 it mirrors the pose and loses the forward hand.
  - On seed …41 the hair lightens to brown, and a tiled floor and a faint arc were added.
- **Depth loses the face on 4 of 6 renders.**
  - The failures are blank skin-coloured or dark-brown ovals, twice with grey, glove-like hands.
  - The 88 % cut changes nothing: the same seed gives the same outcome with or without it.
  - This is the fantasy pack's slice-6 failure again ([q-30](../pre-reviews/q-30.md)). On this evidence, a depth
    Combine needs the replace route afterwards to restore the face.

## Agreement with the lab's judge

| Measure | Result |
| --- | --- |
| Verdicts | **12 of 12 agree**, including every reject and the single fixable |
| Criterion scores | 51 of 72 exactly equal; all within one point |

Where the scores differ, the lab scored one point higher on adherence or control for most clean renders, and on
composition for the skeleton route. The pattern matches the night's two earlier comparisons: agreement on faults and
verdicts, with a one-point drift on the softer criteria.

## For q-28

This is the adult-pair evidence that [q-28](../pre-reviews/q-28.md) asked for. The skeleton route leads on reliability
(3/3), and Copy Pose on keeping the look (2/3). The depth route, which currently leads the Combine route in the Studio,
failed the face on 4 of 6 renders.

Not verified:

- **Coverage.** One character, one pose, three seeds.
- **Harder poses.** The deep bend of the original q-28 pair was not tested, because that pair is excluded.
- **The skeleton itself.** The drawn skeleton picture was not inspected.
