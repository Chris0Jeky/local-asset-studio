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
| F1 | Model and LoRAs hidden: the shut Tune line read "Model, adapters, steps, seed", naming categories, not choices. | S1: the line reads "As made: Anima · pearly_petiflow2 1.00 · 25 steps"; tuned runs keep "Tuned: ..." |
| F2 | Before the first picture the composer sat in a 40% column beside an empty "Your pictures" column; Shape, How many and Generate stacked below the text box. | S1: the split opens only once runs exist; before that the composer uses the full width with its controls in the side column. |
| F3 | A look whose example picture is local-only and absent showed a broken image. | S1: missing look pictures fall back to the blank mark. |
| F4 | Run cards: "Change one thing" and "Put in a new pose" (change outfit, change pose) were under More. | S2 |
| F5 | Picture goals: the empty-picker line wraps in a narrow grid cell. | S2 |

Each slice's before/after and proof are in its PR and in `docs/UX-USE-CASE-MATRIX.md` where clicks change.
Judgement calls are logged in `docs/REVIEW-BACKLOG.md` with how to reverse them.
