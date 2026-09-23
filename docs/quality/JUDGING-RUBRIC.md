# How agents judge a picture

This page is the one rubric every agent uses when it scores a generated picture. It turns "is this any good?"
into six numbers, one verdict and one named defect, so that two judgements can be compared and checked.
It was first written for the overnight quality lab of 23 September 2026.

An agent's judgement is a pre-review. It never replaces the owner's eye.

## Four states that never merge

| State | Who says so | What it means |
| --- | --- | --- |
| **generated** | the job | the render finished |
| **agent-judged** | an agent, with this rubric | scored, with the worst defect named |
| **human-accepted** | the owner, in their own words | the owner likes it enough to use it |
| **licensed** | the model terms | the use is allowed |

Agents write "agent-judged", never "accepted" or "approved", and never tick a `HUMAN_TODO.md` item.

## The six scores

Score each criterion from 1 to 5. **3** means usable with a fix; **5** means no visible fault at full size.

| Key | What it asks | A 1 looks like |
| --- | --- | --- |
| `adherence` | Does it show what the brief asked for: subject, count, props, outfit, setting? | wrong subject, or a key element missing |
| `anatomy` | Hands, fingers, limbs, joints, face, eyes, symmetry (animals too) | unreadable or fused hands, broken limbs, melted face (one extra finger on an otherwise readable hand is a 3, see R3) |
| `style` | Does it match the named look: the preset's intent, the LoRA, the style picture? | wrong medium; semi-real where anime was asked |
| `technical` | Artefacts: noise, banding, seams, garbled text, over-saturation, burn, tiling, blur, stray signature marks | an artefact visible at thumbnail size |
| `composition` | Would it work as a game asset or illustration: silhouette, framing, clean background when asked, crop? | subject cut off, cluttered, unreadable |
| `control` | Only when a control input exists (a pose, depth map, reference or identity picture): was it followed? | the control is ignored |

Write `null` for a criterion that does not apply: `control` without a control input, `anatomy` for a pure object.

**R9. `control` for a pose, depth or reference input is graded, never a binary 2 or 5.** The coordinator ruled this on
23 September 2026. The ruling is stated in full here; its only other copy is the overnight session's local protocol file
(`.runtime/overnight/PROTOCOL.md`, gitignored). The owner may override it.

| Score | The control input was… |
| --- | --- |
| 1 | ignored |
| 2 | followed only as a trace |
| 3 | kept in stance or silhouette, but a named key part is missing (write that part in `worst_defect`) |
| 4 | followed, with one minor deviation |
| 5 | followed exactly |

Why: on the Style+Pose pack the two judges agreed on all 18 verdicts but on none of the 18 `control` scores. Both saw the
same outcomes: the raised arm was lost at 0.7 and held at 0.9–1.0 on two seeds. One judge scored every picture 2 or 5. The
other scored 1 where the pose was ignored, 3 where only the stance was kept, and 4 where it was followed
([second-judge/stylepose-pack.md](second-judge/stylepose-pack.md)).

## The verdict

- **keep**: every score is at least 4.
- **fixable**: nothing is below 3, and a named fix exists (inpaint the hands, reseed, change a strength, crop).
- **reject**: anything else.

Always give one sentence that names the worst defect and the region you zoomed into, with pixel coordinates.
"Hands look off" is not a judgement; "left hand, crop 610,880-760,1040: six fingers" is.

## How to look

1. Look at the whole picture first, at full size.
2. Crop every hand and every face (people and animals) at full resolution, enlarged 2x when small, and look at
   the crops. Count the fingers. Most defects the owner has named were invisible in the whole frame.
3. Crop any small detail the brief names: the prop in the hand, the eyes, any lettering.
4. Compare with the control input when there is one: the pose picture, the source picture, the style picture.
5. Score, then write the record.

Pillow is enough for crops: `Image.open(p).crop((x0, y0, x1, y1)).resize(...)`.

## The record

One JSON object per picture, appended to `judgements.jsonl` beside the review document. The `sha256` ties the
judgement to the exact bytes; a re-rendered file with the same name is a different picture.

```json
{"image": "<path>", "sha256": "<of the image file>", "prompt_id": "...", "job_id": "... or null",
 "judge": "lab|review", "judged_at": "<python datetime.now()>", "blind": true,
 "scores": {"adherence": 4, "anatomy": 3, "style": 5, "technical": 4, "composition": 4, "control": null},
 "verdict": "fixable", "worst_defect": "left hand has six fingers (crop 610,880-760,1040)",
 "fix": "reseed or hand inpaint", "notes": "..."}
```

Take `judged_at` from the clock (`python -c "import datetime; print(datetime.datetime.now())"`), never from a guess.
Set `blind` to `false` whenever the judge already knew the configuration or the owner's verdict.

## Blind comparisons

When two or more configurations are compared (a LoRA on or off, two samplers, two strengths):

1. A script renders the pictures and writes a key that maps shuffled labels (A, B, C…) to configurations, for
   example `key.sealed.json`. Do not read the key yet.
2. Judge every picture under its label only, and write all the judgements first.
3. Then read the key and write the analysis: mean scores per configuration, and wins and losses per seed.
4. Call two configurations a tie when their means are within 0.3. Do not rank noise. Prefer three or more seeds
   before claiming a difference.

## Calibration notes

Measured on 23 September 2026 ([CALIBRATION-2026-09-23.md](CALIBRATION-2026-09-23.md)). Two blind agent judges were
compared with the owner's own verdicts on 19 pictures:

- **They found the owner's named defects well**: the six fingers, the fused foxes, the lost throne.
- **They ranked quality poorly**: Spearman 0.29 and 0.50 against the owner's tiers, and their verdicts (11 and 12 of 15)
  matched the owner less often than a judge that always says "fixable" would (13 of 15).
- **Asked to choose, both picked the starting look the owner did not pick.**

Apply these corrections every time:

- **R1. Score after naming.** If the worst defect you named needs a fix before the picture is usable, the criterion it
  belongs to scores at most 3. A 4 means you would ship it without touching that defect. Judges most often erred by
  naming merged fingers or blotchy skin and still scoring 4.
- **R2. Count the props.** A named prop that is missing, duplicated or not held as the brief asks caps `adherence` at 3.
- **R3. One extra finger on an otherwise readable hand is `anatomy` 3**, with a masked hand inpaint as the named fix. Keep 1–2 for
  unreadable hands, several broken hands or a broken face.
- **R4. A small signature glyph in the outer edge**, removable by a crop that does not touch the subject, is
  `technical` 4. Name the crop as the fix.
- **R5. Faces are faces, animals included.** A featureless or melted face on anything the brief names (a cat in a lap,
  a fox at a shrine) is `anatomy` 3 at most, or 2 if it is the main subject. Name crude eyes when you see them.
- **R6. Appeal is not scored.** When the owner must choose between two clean pictures (a look, a direction), describe
  the differences and do not recommend one. Agents disagreed with the owner on exactly that kind of choice.

- **R8. Correction passes** (adopted by the coordinator on 23 September 2026; the owner may override).
  - Scope: a picture that repairs another one, such as a hand inpaint, a face pass or a refine.
  - `adherence` scores whether the named defect was fixed.
  - `control` scores whether everything else was kept: the gesture, the style and the rest of the picture.
  - `anatomy` follows R3 as usual.
  - A pass that leaves the defect is a reject, however clean it looks.

  Why: on the hand-inpaint experiment, two agent judges agreed on every configuration's outcome but on only 10 of 18
  picture verdicts. One scored `adherence` against the picture's prompt, the other against the repair job
  ([second-judge/hand-inpaint.md](second-judge/hand-inpaint.md)).

  Worked example, from a slip the same experiment exposed: the review judge scored the unchanged six-finger hands
  `anatomy 2`. Under R3 that is 3. Under R8 the verdict is still reject, because `adherence` is 2: the hand was not
  fixed.

Trust agent judging to find, locate and name defects, to reject broken outputs, and to check that a control was
followed. Do not trust it to choose between clean looks or to say what is "spectacular". A second agent judge mostly
repeats the first, so it does not replace the owner's eye.
