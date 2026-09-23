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
| `anatomy` | Hands, fingers, limbs, joints, face, eyes, symmetry (animals too) | fused or extra fingers, broken limbs, melted face |
| `style` | Does it match the named look: the preset's intent, the LoRA, the style picture? | wrong medium; semi-real where anime was asked |
| `technical` | Artefacts: noise, banding, seams, garbled text, over-saturation, burn, tiling, blur, stray signature marks | an artefact visible at thumbnail size |
| `composition` | Would it work as a game asset or illustration: silhouette, framing, clean background when asked, crop? | subject cut off, cluttered, unreadable |
| `control` | Only when a control input exists (a pose, depth map, reference or identity picture): was it followed? | the control is ignored |

Write `null` for a criterion that does not apply: `control` without a control input, `anatomy` for a pure object.

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

How far agent judging agrees with the owner, and the corrections that follow from it, are in
[CALIBRATION-2026-09-23.md](CALIBRATION-2026-09-23.md). The short version is kept here once it is measured.
