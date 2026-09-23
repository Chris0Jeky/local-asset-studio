# Calibration: agent judges against the owner's own verdicts (23 September 2026)

The question: how far can the owner trust an agent's picture judgement? To answer it, two agent judges scored,
blind, every picture the owner has judged in their own words, and the two were compared.

**Short answer.** Agent judges are reliable at finding a named defect: both found the six fingers and the broken foxes,
and both rejected the Restyle the owner rejected. They are not reliable at ranking quality or choosing a look. Their
ranking agrees with the owner's only weakly (Spearman 0.29 and 0.50), and both picked the starting look the owner did
*not* pick. The rubric scores faults, not appeal. Use agent pre-reviews to find and name problems; keep the choice
between two clean pictures with the owner.

## Method

- **Pictures.** Every SFW picture with an owner verdict in their own words: the twelve atelier renders of q-2, the two
  "keep only as an experiment" baselines, the two Anima starting looks (the owner chose B), the two compass icons (the
  owner chose A) and the owner's first Restyle run (q-27). That makes 19 pictures. The owner's words were taken from
  `HUMAN_TODO.md` ("Recorded owner decisions", q-2, q-27), `docs/STUDIO-REVIEW-2026-09-12.md`, the Workspace
  shortlist notes and the restyle README.
- **Not opened, and why.** Two sets were left out.
  - The Qwen edit behind the UX audit (job `dba024ae…`): its submitted prompt asks for an explicit portrait.
  - The owner's Combine pair and every render made from it (q-27 f, q-28): it uses a student-canon character with
    fanservice framing.
  - Both exclusions follow the overnight rule that only SFW pictures of adults are judged.
- **Blind.** The pictures were copied with their metadata stripped, under shuffled labels C01–C19. Each label came
  with its brief only (the prompt, or the Restyle task and its two input pictures).
  - Two fresh subagents judged them. Both report the model ID `claude-opus-5-5`. They were told not to read anything
    outside the folder, and both confirmed they had not.
  - Judge 1 went C01 → C19; judge 2 went C19 → C01. Each cropped every face and hand (judge 2 reports 104 crops).
  - The review agent that wrote this page had read the owner's verdicts, so it did not judge. It built the pack,
    wrote the owner tiers and the agreement rules down *before* any judge started, then unblinded.
- **Owner tiers, as pre-registered.**
  - T5: "genuinely great" / "very good".
  - T4: "good".
  - T3: "okay-ish", "potential but …", "keep only as an experiment", "nice from afar but …".
  - T1: "a complete mess", "not good".
  - The owner's own caveat: almost every picture carries an imperfection they want corrected, and the two favourites
    sit in *Promising — needs correction*. So T5 means "the best so far", not "flawless".

Records, both judges, unblinded, with each picture's path, SHA-256 and the owner's words:
[CALIBRATION-2026-09-23.judgements.jsonl](CALIBRATION-2026-09-23.judgements.jsonl).

## Results

| Measure | Judge 1 | Judge 2 | What it says |
| --- | --- | --- | --- |
| Verdict matches the owner's tier (15 tiered pictures) | 11 / 15 | 12 / 15 | **not informative on its own**: a judge that always said "fixable" would score 13 / 15, because most owner verdicts are mid-range |
| Rank correlation with the owner's tiers (Spearman) | 0.50 | 0.29 | weak; this is the honest headline |
| Picture pairs ordered like the owner (of 78 with different tiers) | 50 right, 16 wrong, 12 tied | 42 right, 23 wrong, 13 tied | better than chance, far from reliable |
| Rejects what the owner called bad (Restyle, Pony) | 1 of 2 (Pony "fixable") | 2 of 2 | good |
| Starting look: picks the owner's B over A | no (picked A) | no (picked A) | **0 of 2** |
| Compass: picks the owner's A over B | no (picked B) | yes | 1 of 2 (both *score* A higher) |
| Owner-named defects also named by the judge | see below | see below | good for bodies and hands, poor for faces of animals and eyes |
| Judge 1 against judge 2 | 14 / 19 same verdict; scores differ by 0.27 on average, 93 of 94 within one point | | the two agents agree with each other far more than with the owner |

**Defect recall.** For each defect the owner named, did the judges name it too?

| Owner said | Judge 1 | Judge 2 |
| --- | --- | --- |
| NoobAI portrait: six fingers | yes (crop 30,555-160,700) | yes |
| Fox shrine: the foxes lose detail | yes: fused, translucent fox with no legs | yes |
| Fox shrine: the fox faces are morphed | no | no |
| Restyle: throne gone | yes | yes |
| Restyle: garish | yes ("burnt neon") | yes |
| Restyle: flat | partly ("posterised") | partly ("smeared linework") |
| Restyle: eyes crude | no | no |

That is 4 of 7 fully and 1 partly, for each judge. The review agent checked the fox crop afterwards: the foxes'
faces are featureless muzzles with no eyes, a defect that both judges' crops contained and neither named.

Per picture (mean of the scored criteria; verdict):

| Picture | Owner | Judge 1 | Judge 2 |
| --- | --- | --- | --- |
| `Studio/krea-anime-atelier_00001_.png` | T5 "genuinely great" | 4.2 fixable (corner signature glyph) | 4.4 keep |
| `Studio/probes/witch-target-ersde-4step_00001_.png` | T5 "very good" | 4.2 keep | 4.2 keep |
| `…/witch-target-stack_00001_.png` | T5 | 4.2 fixable (glyph, paint blotches) | 4.0 fixable |
| `…/witch-target-stack-4step_00001_.png` | T5 | 4.2 fixable (glyph) | 4.2 fixable (glyph) |
| `…/witch-nijisis-4step_00001_.png` | T5 | 4.4 keep | 4.2 keep |
| `…/witch-target-plus-baroque-oil-4step_00001_.png` | T4 "good" | 4.2 keep | 4.4 keep |
| `…/witch-airy-watercolor-short-4step_00001_.png` | T4 | 4.8 keep | 4.8 keep |
| `Studio/WAI-Illustration_00012_.png` | T3 "okay-ish" | **4.4 keep** | **4.4 keep** |
| `Studio/noob_00004_.png` | T3 "potential, six fingers" | **3.4 reject** | 3.8 fixable |
| `Studio/krea-style-lab_00001_.png` | T3 "foxes morphed" | 4.4 fixable | 4.2 fixable |
| `…/witch-nijisis-baseline_00001_.png` | T3 "potential but imperfect" | **4.2 keep** | **4.2 keep** |
| `Studio/WAI-Illustration_00013_.png` | T3 "experiment" | 4.0 fixable | 4.4 fixable |
| `Studio/anima-artist-stack_00004_.png` | T3 "experiment" | 3.6 fixable | **4.4 keep** |
| `Studio/pony_00002_.png` | T1 "a complete mess" | **3.6 fixable** | 2.8 reject |
| `Style-Pose/Nova_00007_.png` (owner's Restyle) | T1 "not good" | 2.3 reject | 2.2 reject |
| `Studio/Anima-v1-Baseline_00001_.png` (A) | not chosen | 4.8 keep | 4.8 keep |
| `Studio/Anima-v1-Baseline_00002_.png` (B) | **chosen look** | 4.4 keep | 4.6 keep |
| compass seed 2026091103 (A) | preferred | 3.75 fixable | 4.25 keep |
| compass seed 2026091104 (B) | alternate | 3.5 fixable | 3.5 fixable |

Bold marks a disagreement with the owner.

## The biases found

1. **Naming a defect but scoring it 4.** This is the main leniency. Both judges called WAI 00012 and the NIJISIS baseline
   "keep", and the owner called them "okay-ish" and "imperfect". Yet the judges had *named* real flaws in them: merged
   fingers and an over-long thumb behind the magic circle; mottled paint blotches on the shins; boots cut by the frame
   edge. The judges wrote the defect down, then scored its criterion 4 as if it did not need fixing.
2. **No criterion for appeal.** The owner's words are about appeal as much as faults: "not spectacular", "the artistic
   side is not popping", "genuinely great". The rubric has no place for that. Both judges preferred the clean, flat
   Anima base (A, 4.8) over the softer cinematic look the owner chose (B). Their reason: B's sheen and bloom read as
   faults.
3. **Animal faces get less care than human faces.** Both judges excused featureless cat and fox faces as a style
   choice. The owner did not: "their faces are morphed".
4. **Eyes and "flat" are under-named on stylised failures.** Both judges rejected the owner's Restyle. They named the
   throne and the burnt palette, but neither named the crude eyes.
5. **Harshness on a single extra finger.** Judge 1 rejected the NoobAI portrait for its six-fingered hand. The owner
   called it "has potential", and the studio's hand pass fixed that exact hand in 36 s (job `14caa4fb`). The rubric's own
   anchor ("a 1 looks like fused or extra fingers") pushed judge 1 there.
6. **Strict on corner signature glyphs.** Stray glyphs in a corner cost the Krea/Niji favourites a full point in
   `technical`, which dropped two T5 pictures below the T3 WAI render. The owner never mentioned the glyphs.
7. **Leniency when the subject is unreadable but the picture is pretty.** Judge 1 scored the Pony render's adherence
   and composition 4. The brief asked for a cowboy shot; the render is a back view with a featureless face and the lower
   body dissolving into light. The owner's verdict: "a complete mess".

## Corrections, now in the rubric

These notes are added to [JUDGING-RUBRIC.md](JUDGING-RUBRIC.md) under *Calibration notes*:

- **R1. Score after naming.** If the worst defect you named needs a fix before the picture is usable, the criterion it
  belongs to scores at most 3. A 4 means you would ship it without touching that defect.
- **R2. Props are counted.** A named prop missing, duplicated or not held as the brief asks caps `adherence` at 3.
- **R3. One extra finger on an otherwise readable hand is `anatomy` 3, not 1 or 2.** A hand inpaint fixes it. Keep 1–2
  for hands that are unreadable blobs, several broken hands, or a broken face.
- **R4. A small signature glyph in the outer edge that a crop removes without touching the subject is `technical` 4**,
  with the crop named as the fix.
- **R5. Faces are faces, animals included.** A featureless or melted face on a character the brief names (a cat in a lap,
  a fox at a shrine) is `anatomy` 3 at most, and 2 if it is the main subject. The same goes for eyes: name them when they
  are crude.
- **R6. Appeal is not scored.** When the owner must choose between two clean pictures (a look, a direction), the agent
  describes the differences and does **not** recommend one. The agents' picks disagreed with the owner's on the one look
  choice they had to make.

**Post-hoc check, not a validation.** Re-applying R1–R5 to the judges' *own named defects*, without looking again,
changes these results:

| Measure | Judge 1 | Judge 2 |
| --- | --- | --- |
| Verdict agreement | 11 → 15 of 15 | 12 → 15 of 15 |
| Spearman | 0.50 → 0.69 | 0.29 → 0.44 |

The rules were written from these same 15 pictures, so this shows the rules are consistent with the owner's verdicts. It
does not show they generalise. The starting-look choice stays wrong under every rule (R6 exists for that reason). The
next owner verdicts are the real test: record them and re-run this page's analysis
(`python experiments/curated/quality-calibration-20260923/analyse.py`).

## How far to trust agent judging

| Trust it for | Do not trust it for |
| --- | --- |
| finding and locating hand, finger, limb and prop defects (crop coordinates included) | choosing between two clean looks or directions |
| rejecting clearly broken outputs and ignored controls | saying whether a picture is "spectacular" or merely "fine" |
| checking a control input was followed (pose, identity, costume kept) | ranking pictures that are all good |
| making the owner's review faster: a pre-sorted list with named defects | anything unseen at full size: judge crops, not thumbnails |

The two agent judges agree with each other much more than either agrees with the owner. A second agent opinion
therefore does not replace the owner's eye; it mostly repeats the first opinion.

## Not verified

- Only 15 tiered pictures plus two pairwise choices: every number above carries wide uncertainty. One flipped verdict
  moves agreement by about 7 points.
- The owner's verdicts came at different times, often from contact sheets rather than full-size files, and in a few
  words. A tier is our reading of those words, not the owner's own score.
- Both judges and the review agent are the same model family, so shared blind spots do not show up as disagreement.
- The corrections R1–R6 are untested on new pictures.
