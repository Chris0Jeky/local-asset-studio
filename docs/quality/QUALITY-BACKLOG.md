# Quality backlog: every open picture-quality question (23 September 2026)

This page lists every open question about picture quality that the overnight sweep found, and its status. A picture-quality
question asks whether a render is good, whether a defect is there, which configuration looks better, or whether a
correction worked.

The sweep covered 52 questions, from four places: `CURRENT_STATE.md`, the curated READMEs, the open GitHub issues and
`HUMAN_TODO.md`. The folders `nsfw-lab-*` and `civitai-intake-*` were skipped unopened.

Each question has one status:

| Status | What it means |
| --- | --- |
| **answered** | existing outputs answer it, and an agent judged them |
| **partly** | part is answered, and the rest needs renders or the owner |
| **needs renders** | no existing output can answer it |
| **needs the owner** | a taste or policy choice; an agent pre-review exists where it helps |
| **not judged** | its only evidence is excluded under the overnight adult-only rule |

Every answer below is agent-judged, not accepted. The judgements use the [rubric](JUDGING-RUBRIC.md), and the
[calibration](CALIBRATION-2026-09-23.md) says how far to trust them: well for finding defects, poorly for ranking looks.

Records with SHA-256 and crop coordinates:

- this page's own checks: [QUALITY-BACKLOG.judgements.jsonl](QUALITY-BACKLOG.judgements.jsonl);
- the pre-reviews: [pre-reviews/](pre-reviews/).

## Answered by agent judgement

| Question | Source | Answer |
| --- | --- | --- |
| Did `anime-detail-fix` fix the six-finger NoobAI hand (job `14caa4fb`)? | CURRENT_STATE, atelier doc, STATUS G3 | **No.** At full resolution the hand still has six digits: two tall fingers, a thumb across the palm and three fingers on the right, the same structure as the original. The pass redrew the hand (mean change about 9 grey levels in its box) without fixing the count. The Gentle 0.3 trial (`e4e49006`) also kept it, as recorded. Correction notes now sit beside the three claims. |
| Does `anime-detail-fix` repair hands reliably? | CURRENT_STATE | **Not on the evidence: 0 of 3 recorded passes fixed their target.** On the NoobAI hand, `14caa4fb` and `e4e49006` both left six digits. On the fantasy portrait, `009eddad` changed the eyes, removed both earrings and left the hands ([q-30](pre-reviews/q-30.md)). A masked hand inpaint is the next thing to try. |
| Did `krea-refine` fix the fox faces on the fox shrine (`21e4a629`)? | CURRENT_STATE, atelier doc | **Partly.** The faces now have eyes and snouts. But three or four small foxes became two large ones, and white snow specks cover the frame. The run's prompt was the preset's example ("two red foxes ... on a snowy hill under a starry night sky"), not the shrine's. Refine with the source's own prompt. |
| Does the lantern grip in fantasy-pack portrait 1 need correcting? | q-30, CURRENT_STATE | **No.** Both hands have five digits and a readable pinch. The real flaw is the lantern cut by the bottom edge ([q-30](pre-reviews/q-30.md)). |
| Is the stocking on the throne witch's raised leg a defect (`Nova_00004_`, job `bb8efa52`)? | style-pose-matrix nova README | **Yes.** It ends in a toe-less, bandage-wrapped tip (crop 20,780-230,930), and every Klein restyle of the picture inherited it ([q-27](pre-reviews/q-27.md)). The owner ruled the witch an adult original on 23 September. |
| Do the two Krea 2 VRAM-spill benchmark renders look right, and do they match? | CURRENT_STATE (22–23 Sep), `vram-spill-20260923/` | **Yes.** Same picture and quality, not bit-identical (mean difference 7 of 255). Clean faces and hands; the neon signs carry pseudo-glyphs. The spill did not degrade the image at this seed. |
| Do the Qwen-Image 2.1 launch flags change the picture? | #739, `qwen21-bench.json` | **No.** Per seed, the four flag sets differ by a mean of 0.21 grey levels. The flags change speed, not the image. (Quality: see *partly* below.) |
| How bad are the hand and leg defects in the CSTati, YumeFlux and JANIMA station baselines? | CURRENT_STATE, goal-baselines README | **Mild.** CSTati and YumeFlux have simple but readable hands, and a catwalk stride that hides one boot (composition 3). JANIMA hides its hands in the coat but plants both feet (all 4s). |
| How often do Anima artist-tag runs leave a corner signature mark? | CURRENT_STATE | **2 of 4 checked.** The mark is clear on the artist-tag run (`anima-artist-stack_00002_`) and faint on the 1328×1776 reference (`_00003_`), and absent on the six-adapter and Failleaf runs. It is invisible at thumbnail size; a 40 px crop removes it. |
| Is the 4-step Krea target stack on par with 15 steps? | CURRENT_STATE | **Yes, a tie.** Both blind calibration judges gave both about 4.2 (the 4-step run 4.2 and 4.2, the 15-step 4.2 and 4.0), and the owner called both "very good". |
| Does the compass read at 128 px, and how much cleanup does A need? | compass-first-batch README | **It reads, but it is not yet an icon.** Both exports keep an off-white background, a grey drop shadow and about 4,300 anti-aliased colours. A needs about 10–15 minutes of cleanup: background to alpha, a 16–32 colour palette. B also needs its garbled W and S redrawn. |
| Is the NoobAI Masterpiece colour fringe real? | lora-smoke README | **Yes.** A red/cyan fringe on the edges at both strengths, confirmed at full resolution. It ties the control, so there is no gain to set against it ([q-32](pre-reviews/q-32.md)). |
| Is the `wai-skeleton` dark background acceptable at 0.8, and is the Studio proof clean? | CURRENT_STATE, sdxl-skeleton README | **Yes to both.** The proof (`6a342bbf`) is clean on white. On seed 03 at 0.8 the leak reads as a mid-grey backdrop (fixable). The bent-skeleton renders were not judged: that skeleton was estimated from an excluded fan picture. |

## Partly answered

| Question | Source | What is answered | What remains |
| --- | --- | --- | --- |
| Do the Hands LoRAs fix hands? | lora-smoke README | Hands Pony drew six digit tips at both strengths; Hands Illu changed nothing visible (the blind judge mistook it for the control) | a multi-seed test where the base draws bad hands |
| Which Pony renders read adult, and which cues make Pony draw one? | lora-smoke README | the control, both Hands renders and (per the README) Dramatic Lighting 0.85 read youthful; Gothic Neon and Dramatic Lighting 0.6 read adult | which prompt cues work: needs renders |
| Is Qwen-Image 2.1 good enough, next to the current defaults? | #739 | both seeds are underexposed navy and soft at 8 steps (style 3, technical 3) | more steps and a side-by-side with the defaults |
| Does the replace route keep the portrait's face? | CURRENT_STATE, fantasy-pack README | the fringe, the earrings and the expression carry at full-body scale; the fine features are redrawn ([q-30](pre-reviews/q-30.md)) | portrait-fidelity faces: a face pass, needs renders |
| Are Anima hands acceptable when visible? | CURRENT_STATE | on look B (the fantasy pack) the visible hands were clean in 1, 2 and 3 ([q-30](pre-reviews/q-30.md)) | plain Anima base with hands in view |
| Which installed SDXL checkpoint is the best base (#14)? | #14, CURRENT_STATE | on the evidence so far, WAI and YumeFlux lead and tie, CSTati is close, Animagine is next, and Pony and NoobAI are weakest. Sources: the calibration pack (WAI 4.4, NoobAI 3.4–3.8, Pony 2.8–3.6 on one brief), the smoke controls (WAI 3.6, NoobAI 3.4, Pony 3.0) and the Style + Pose matrix | one fixed brief across all seven, three seeds, blind |
| The Anima two-seed comparison `fbb384c7` | CURRENT_STATE | both seeds are clean and neither draws the sword the brief names; agent-judged here | which look the owner prefers (rubric R6); probably superseded |
| Does the calibrated judge agree with the owner on new pictures? | #66, the calibration | measured on 14 tiered pictures: finds defects, ranks poorly | new owner verdicts |

## Needs the owner (a pre-review exists)

| Question | Pre-review |
| --- | --- |
| q-25: is the Style + Pose direction right for the pack, and should the defaults change? | [q-25](pre-reviews/q-25.md) |
| q-27 (a), (d): Restyle finish, Klein or WAI to lead, Mishima or Momoko | [q-27](pre-reviews/q-27.md) |
| q-27: does the look-from-a-picture recipe earn its place? | not judged; its sources are excluded ([q-27](pre-reviews/q-27.md)) |
| q-28 (a), (e): is the depth Combine the complete pose change; depth or Copy Pose to lead | [q-28](pre-reviews/q-28.md); needs an adult-pair re-prove first |
| q-30: per-picture keeper / needs-work / experiment; the character's face; the expression edit; the full-body keeper | [q-30](pre-reviews/q-30.md) |
| q-32: which LoRA-smoke looks the owner likes | [q-32](pre-reviews/q-32.md) |
| Is the Krea target stack with koukouya close enough to the owner's target image? | none (a taste question) |
| #143: one bundle's base against its adapter stack | none (needs the owner's chosen bundle, then renders) |

## Needs new renders (for the lab)

| Question | Source |
| --- | --- |
| Combine routes on an adult original pair: depth, ankle cut, Copy Pose, skeleton, replace; three seeds each | q-28, #422, #446, #427 |
| Replace route with a costume-leak test (image 2 in different clothes) | CURRENT_STATE |
| Copy Pose as the fantasy pack's full-body route | CURRENT_STATE |
| A third board picture with "take only … from image 3" wording | CURRENT_STATE |
| Qwen-Image-Edit 2511 re-posing on hard poses against its cost | #812 |
| LoRA smoke: untested full triggers, stacking, three seeds for the candidates | lora-smoke README, #857 |
| Pony adult cues | lora-smoke README |
| Style + Pose: other seeds, pose strength 0.7 / 0.9 / 1.0, the pack's own portrait as the board, the unrun Animagine and CSTati boards | q-25, CURRENT_STATE |
| Restyle: other boards, a denoise sweep, a Nova twin, Klein 9B, AniEdit, Z-Image Turbo | #351, #343, #357 |
| Klein restyle with "bare feet" wording and the source's true colours named | [q-27](pre-reviews/q-27.md) |
| Masked hand inpaint on the NoobAI six-finger hand and the pack's depth-Combine lantern hand | this page |
| The repair-yield programme: scoped repair against a whole-image edit | #72, #257, #66 |
| Qwen Atelier reference fidelity on the corrected graphs | #21 |
| IP-Adapter plus / plus-face carrying an original design on WAI | CURRENT_STATE |
| Never-run recipe variants | CURRENT_STATE |
| FLUX LoRA smoke on the Klein and dev stacks | #764 |

## Not judged tonight

| Question | Why |
| --- | --- |
| Depth-cut value; subject isolation; speech-bubble and lettering leaks; Q8 against Q6 | every render uses the excluded student-canon fan pair (the q-28 note) |
| The character-pilot profile marked "requires review" | not reached tonight; the pilot's pictures live in `C:/AI/character-lab/pilot-20260912/` |
| Wan 2.2 video coherence; TRELLIS and Hunyuan3D meshes | video and 3D need frame or turntable review; not reached tonight |

## Found on the way

- The two Style + Pose matrix files that held a clothing-less beach render (`Style-Pose/WAI_00008_.png`, sha256
  `bdf2fc68…`) were found by numeric matching without opening them. The coordinator is moving them to local-only (PR #865).
- An agent judgement recorded in a README can be wrong at full resolution. Three examples tonight:
  - "clean five-digit hand" (NoobAI);
  - "clean open hand" (Hands Pony);
  - "hands plausible" (the WAI smoke control).

  The rubric's crop rule exists for this reason; README notes written from whole frames should be read as provisional.
