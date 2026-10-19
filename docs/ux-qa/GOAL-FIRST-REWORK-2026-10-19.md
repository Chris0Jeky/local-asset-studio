# Goal-first rework, 19 Oct 2026 (ux-lead, overnight)

Owner ask (19 Oct): a user with an objective, such as a very high-end anime picture with a chosen model and LoRAs and then
tweaks, should get there without confusion. Rework allowed. Earlier rounds (audits v1-v3, 16 Oct) already made Make the
goal-first front door; this pass audits what still feels clunky and fixes it in small slices.

## Method
Preview Studio on 127.0.0.1:8291 from the `ux/*` worktree (own empty workspace, real ComfyUI catalog read-only), driven by
Playwright at 1440x900. Every generation route was intercepted; nothing was submitted. Run cards were seen by restoring a
fake finished run in the browser only (`/api/jobs/<id>` and `/api/image/...` answered by the harness).

## Target information architecture (unchanged shape, sharper surface)
1. **What are you making?** Goal tiles (5 make-new, 6 from-a-picture). Already in place.
2. **Look** chosen by its picture. The look is the default model + LoRAs + wording for the goal.
3. **Recipe in view**: the model, each LoRA with its strength and the step count are readable without opening anything,
   and one press opens them for editing (Tune). Expert controls (sampler, negative, seed, compare one setting) stay folded.
4. **Describe + Generate**: one text box, shape, how many, estimated time, one Generate.
5. **Results with next steps**: Keep / Not this, then the tweaks people ask for by name: Vary, Fix face, Upscale,
   Change one thing (outfit, colour), New pose; the rest under More.

## Findings (19 Oct) and slices
| # | Finding | Slice |
| --- | --- | --- |
| F1 | Model and LoRAs hidden: the shut Tune line read "Model, adapters, steps, seed", naming categories, not choices. | S1: the line reads "As made: Anima · anima-base-v1.0 · pearly_petiflow2 1.00 · 25 steps" (the model file is named when a family has two); tuned runs keep "Tuned: ..." |
| F2 | Before the first picture the composer sat in a 40% column beside an empty "Your pictures" column; Shape, How many and Generate stacked below the text box. | S1: the split opens only once runs exist; before that the composer uses the full width with its controls in the side column. |
| F3 | A look whose example picture is local-only and absent showed a broken image. | S1: missing look pictures fall back to the blank mark. |
| F4 | Run cards: "Change one thing" and "Put in a new pose" (change outfit, change pose) were under More. | S2 #1534: Change one thing, New pose, Restyle in one press |
| F5 | Picture goals: the empty-picker line wraps in a narrow grid cell. | S2 #1534 |
| F6 | LoRAs were a name to guess (type, datalist, Add); a recorded default of 0 added a LoRA at 0. | S3 #1537: a card per fitting LoRA with Add; one search for list and Enter |
| F7 | Double presses could apply twice or undo (Keep, Resume, Save character, Put away); chosen look shown by colour only. | S4 #1540 |
| F8 | Look cards did not say which model they use; sidebar numerals read as counts. | S5 #1543 |
| F9 | Quality was a tick (Draft) plus a hidden Tune option (Finer). | S6 #1546: Quality Draft / As made / Fine beside Generate; no automatic finishing chain (gpu-lab advice) |
| F10 | The fold holding the model and LoRAs was called "Tune this look". | S7 #1548: "Model, LoRAs and settings" |
| F11 | Models & setup listed ready looks with no way to use one. | S8 #1549: Use in Make |
| F12 | "built-in adapter at 1" (audit v3 N13). | #1552 |
| F13 | Other tabs: Library first screen, Compare & review empty state, Prompt Lab storage-first, Library dialog's disabled actions. | Briefs A-D, run by Sol workers |
| F14 | Four pictures on a result card showed eleven buttons each. | #1558: one picture's next steps at a time (62 → 29 visible buttons) |
| F15 | Anima LoRAs said "may not suit" on the Anima merges (One Obsession, Pearly). | #1562: family_aliases |
| F16 | Draft on Anima looks only halved the steps; round 7 found the turbo LoRA at 8 steps a near-tie on one picture. | #1559 |
| F17 | No one-press light refine; detail-fix changed clean faces in round 7. | #1569: Refine 1.5× (anime-refine 0.22) |
| F18 | The pose grid offered the character as its own pose; imported file names doubled. | #1564 |
| F19 | Fix/Upscale stayed refused after a passing failure (recipes loading, failed read). | #1571 |
| F20 | The anime goal led with Petiflow; round 7 favoured the One Obsession and Pearly mixes. | #1572 |
| F21 | Other tabs, second round: Workflow builder first screen, Full editor's doubled blocker, recipe picker prose. | Briefs E-G (Sol) |

## Still open
- Fine: round 7 found no gain from more steps on Anima (one picture), so Anima offers no Fine; other families keep 1.5× steps until measured.
- Only two stick figures for New pose (audit v3 N11).

Each slice's before/after and proof are in its PR and in `docs/UX-USE-CASE-MATRIX.md` where clicks change.
Judgement calls are logged in `docs/REVIEW-BACKLOG.md` with how to reverse them.
