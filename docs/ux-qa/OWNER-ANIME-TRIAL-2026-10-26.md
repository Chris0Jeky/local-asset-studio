# Owner trial: a specific, finished adult anime character

**Status: proposed and unrun.** This is a repeatable owner test for the gap between preparing a recipe and getting a picture worth keeping. It has no generation, timing or art-acceptance results yet. The [native creation journeys](CREATION-JOURNEYS-2026-10-26.md) remain separate synthetic evidence.

Use one original character brief across Make, Full editor and follow-ups. Record the effort to reach an accepted result, including rejected attempts. A successful job, a picture the owner accepts, and permission to use its model are separate decisions.

## Fixed brief

This character is a proposed test subject, not an owner-approved design. It follows the clothed fantasy direction in the [existing illustration brief](../FANTASY-CHARACTER-BRIEF.md) without changing that pack's chosen look or the separate character-consistency canon. Replace the subject before the trial if desired; then freeze the replacement for the whole comparison.

Paste this scene exactly for the first two image routes:

> An original adult elven cartographer, age 28, with mature facial proportions, amber eyes and shoulder-length ash-silver hair braided at her left temple. A small brass crescent hair clip sits above her left ear. She wears a tailored navy travelling coat with brass fastenings over an ivory high-neck blouse, a teal scarf and a brown leather belt pouch. She is fully clothed. Show her from mid-thigh upward, turned slightly toward the viewer, with a warm, self-assured expression. Her bare right hand holds a folded parchment map at her waist; her left hand rests on a balcony rail. Both hands are visible. Behind her is a quiet fantasy harbour at blue hour, with soft distant lanterns. Warm light shapes her face against the cool background. Use refined anime linework, soft cinematic shading and a restrained navy, teal and copper palette. Keep the face and hands clear, the clothing coherent and the background subordinate. No lettering, logo, border or additional person.

Keep these seven visible requirements on the review sheet:

| Requirement | Inspect directly |
|---|---|
| Adult character | Clearly adult appearance and proportions; original design |
| Identity | Amber eyes, ash-silver hair, left-temple braid and brass crescent clip |
| Costume | Navy coat, brass fastenings, ivory high neck, teal scarf, brown belt pouch |
| Framing | Mid-thigh portrait; face and both hands inside the frame |
| Action | Right hand holds the map; left hand rests on the rail |
| Scene | Quiet harbour at blue hour; no second person or lettering |
| Finish | Appealing face, readable hands, warm face light, cool background, soft anime shading |

For a pose derivative, change only the action and framing instruction:

> Keep the same adult character, face, hair, clothing and colours. Show her full length on the same balcony, her weight on her right leg, looking back over her left shoulder. Her right hand holds the folded map beside her hip and her left hand rests lightly on the rail. Keep both hands and both feet in frame.

Use the owner's chosen pose picture if the route needs one. Record its asset ID and the intended pose before opening the picker. A result made with a different source is a different attempt.

## Freeze the starting conditions

Run this in a separately authorized configured-machine session. Preparing this document does not extend an existing attempt budget. No installation, model download, backend switch or package change is part of the timed journey.

Before timing, record the Studio commit, browser/version, viewport, active backend, available model and LoRA filenames/hashes, and the Workspace identity. Choose one available anime look as route A. Choose the desired compatible model/LoRA configuration as route B and record it exactly. Model availability and suitability must be checked on that machine; a pictured look is not a promise about this brief's output.

For both routes use **Portrait**, **How many: 1**, and the look's **As made** quality unless a recorded control requires otherwise. Freeze the common seed at `1729` when both routes expose it. Record actual pixel dimensions, steps, sampler, scheduler, guidance and adapter strengths from each recipe. Keep the brief unchanged. Different model families can interpret these settings differently; matching a seed does not make their outputs equivalent experiments.

Route B may change the model and compatible adapter stack together because that is a real user task. Its result is a comparison of complete configurations. To attribute an improvement to one adapter or setting, a separate trial must change only that item.

Prepare up to three deliberate reference assets for the reference tasks: the chosen character candidate, a pose picture and a style picture. Record each asset ID, role and classification. Use sources already available for this session. If a prerequisite is absent, mark the dependent task **blocked** instead of substituting an unrelated image.

Use **Private session** for the personal creation trial. Confirm the status line says the creation is private. The view buttons can be tested independently later. Keep the evidence with the private work; do not commit personal source pictures, prompts or recovery downloads into the repository.

## Measure effort and waiting separately

Start a task clock when the owner sees its instruction. Stop it at the stated endpoint. A screen recording or observer can record the following without coaching the owner through hidden controls:

| Measure | Definition |
|---|---|
| Input actions | Each click/tap, toggle, selection, completed text-field entry, file choice or key command. Count a continuous text entry once; separately record fields and characters. Count retries and mistaken actions. |
| Search effort | Number of queries, query changes and result lists inspected; time spent locating a look, model, adapter or source. |
| Reading and decisions | Time reading the interface, understanding a choice or choosing between candidates. Include this in active human effort. |
| Backtracks / dead ends | Returning because the previous route did not support the goal, or reaching a control that gives no useful next action. Record the reason. |
| Request acknowledgment | Generate press to the Studio confirming the job identity. This is not generation completion. |
| Queue and generation | From the acknowledged job through queue/start to a terminal result, using job/backend receipts where available. Record an unavailable start timestamp as unknown. |
| Review and correction | Time examining results and deciding keep, reject or repair; includes opening full-size views and inspecting details. |
| Interruption | Time away from the task, reported separately. Reload recovery work after returning counts as active effort. |

If review or setup overlaps a running job, record the overlap. Do not add overlapping intervals and call the sum wall time. Report **active human time**, **elapsed time to first candidate**, **elapsed time to first accepted result**, and **machine/queue time** separately. If nothing is accepted, report “no accepted result within the budget,” with the actual attempts and time spent.

The targets below are proposed diagnostic thresholds, not measured performance or product promises. They can be changed before the first attempt. Record the actual result when a threshold is exceeded. If the owner cannot find a next action after 90 seconds, log the blocker before an observer gives a hint; count that hint as assistance.

## Ten bounded tasks

The full trial has a proposed cap of **45 minutes of active human effort** and **six generated images**, with one image per submission. Model waiting is reported separately. The two baseline images use the same fixed scene; later jobs each have a named purpose. Unused follow-up slots are not permission for additional random batches. A task that only prepares a recipe ends before Generate.

| Task | Start and instruction | Endpoint and proposed diagnostic target | Image budget |
|---|---|---|---:|
| T1 — First specific picture in Make | Open Make from the normal entry point. Choose **Anime character**, route A's pictured look, the fixed scene and the frozen settings. Find Generate without external instructions. | Ready state reached in 3 minutes of active effort; then submit once and score the result. Record the first-ready time separately from generation and review. | 1 |
| T2 — Chosen model and LoRA | Starting from the same scene, open **Model, LoRAs and settings**. Select route B's exact compatible model, adapter and strength. Check any trigger wording the interface added. | The intended files and values appear in the submitted recipe, with no duplicated trigger. Ready within 3 additional active minutes; submit once and score. | 1 |
| T3 — Inspect the full recipe | Open the selected route in Full editor. Locate the same model, adapters, wording, seed and dimensions without losing the scene. Inspect the draft controls. | Explain which values the route will use and export a draft if desired. Stop before Generate. Record any changed or unrepresentable value; target 2 active minutes. | 0 |
| T4 — Reuse and survive interruption | Choose the better usable baseline as a source in **Change a picture**. Enter “Keep everything else; change only the scarf from teal to muted crimson.” Reload the same tab before submitting. | Same goal, exact source and wording return, with no replacement job. Target: zero re-entry inputs; readiness within 30 seconds after reload, excluding unavailable backend/source checks. | 0 |
| T5 — Restyle without rebuilding | From the chosen source, open **Restyle a picture**, choose a second pictured look and retain the costume colours. | Exact source and intended style are visible at readiness. Stop before Generate; target 2 active minutes. Record whether the style choice required a new search. | 0 |
| T6 — Identity, pose and style references | In a compatible Full editor recipe, assign the three prepared pictures to their intended roles. Read back which image controls identity, pose and style. | Correct asset identity in every slot and a clear readiness state, or an explained unsupported combination. Stop before Generate; target 3 active minutes. | 0 |
| T7 — Same character, new pose | Return to the chosen baseline and use **Character in a new pose** with the pose picture and derivative wording above. Use the picture route; drawn-pose artifacts are outside this private-creation slice. | The original character and requested pose are both represented in the prepared request. Submit once. Score pose and identity separately; target 3 active minutes to readiness. | 1 |
| T8 — Vary a keeper | Choose the strongest usable candidate, use the offered Vary action once, and record its exact mode/seed. Inspect the original beside the result. | Clear source lineage, one acknowledged job, and an owner choice between original and variant. If the UI refuses the recorded recipe, record the reason and stop this task. | 1 |
| T9 — One correction, then enlargement | Name one visible defect before choosing an offered face/hand correction or Refine action. Keep the original. Compare the result, then use **Upscale 2×** only if the owner has chosen a candidate worth enlarging. | The named defect improves without unacceptable identity/style loss. Enlarging preserves the chosen picture at the intended viewing size. Unsupported actions are recorded as blocked; no substitute model or extra retry is assumed. | Up to 2 |
| T10 — Find, retain and resume | In Library, find the chosen result, record its review/notes and place it in a private collection if desired. Switch Regular → Private → All, then return to Make. Repeat the unsent-draft reload portion at 390px width using the keyboard. | Regular hides private results; Private/All find the intended asset; changing the view keeps the creation private. No typed draft is lost. Target: find the named asset in 60 active seconds; record mobile focus/scroll problems separately. | 0 |

T1 and T2 do not have to produce an acceptable picture for their interface steps to pass. If neither gives a usable source, stop the source-dependent tasks and report why; do not spend the remaining budget manufacturing a prerequisite. T3–T6 can be exercised with a previously approved source in a separate interface-only run, clearly labeled as such.

For T9, a corrective model can change the face or finish. Score preservation against the chosen original, not just whether the new image looks attractive by itself. Upscaling cannot turn an unaccepted source into an accepted source by default.

An uncertain submission ends further generation until its original job/prompt identity is reconciled. Preserve its recipe and known prompt ID. A timeout is not proof that the backend did nothing, and refreshing does not authorize a replacement submission.

## Owner scorecard

Review every result at the same fit-to-window size, then at 100% for face, hands and clothing. Keep the original visible when judging a derivative. The owner gives the scores; an agent may record the answer but must not infer it from completion, Favorite, a high score or a screenshot.

Use this common scale for each category: **0** absent or unusable; **1** major failure; **2** mixed, needs substantial repair; **3** good with a small visible defect; **4** meets the brief convincingly. A missing view or uninspected detail is **not inspected**, not zero and not a pass.

| Category | Weight | Concrete question |
|---|---:|---|
| Identity and brief fidelity | 25 | Are the specified identity details present? For a derivative, is this recognizably the same adult character? |
| Face and personal appeal | 20 | Does the owner find the face attractive and expressive, with mature proportions and convincing features? |
| Anatomy and hands | 15 | Do visible hands, fingers, limbs and contact with the map/rail make sense? |
| Composition and requested pose | 15 | Is the framing useful, the pose readable and the requested action actually present? |
| Costume and prop construction | 10 | Are the coat, scarf, fastenings, pouch and map coherent, with the intended colours and no fused objects? |
| Light, colour and finish | 15 | Does the soft anime finish have controlled detail, readable lighting and a subordinate background without distracting artifacts? |

Calculate the weighted score as `sum(weight × category_score / 4)`, out of 100. Do not compute a complete score while a category is uninspected.

A **proposed keeper threshold** is at least 85/100, with every category at least 3, and all of these hard requirements met: clearly adult appearance; the specified clothing coverage; one original character; the task's required face/limbs visible; no major anatomical or rendering defect at the intended display size. This is a threshold to agree before the trial, not an acceptance already given by the owner.

The final decision still needs the owner's explicit answer:

> Would I keep and use this picture for the stated purpose without another generation or repair? **Yes / Needs one named correction / No.** Why?

Record the owner's words. A numerical pass with “No” is unaccepted. A deliberate owner exception should name the waived requirement and the intended use. Neither answer establishes model licensing or commercial-use permission.

## Retain one short record per attempt

Copy these empty tables into the session's evidence note. Leave unavailable facts blank or mark them unknown; do not backfill estimates as measurements.

| Attempt | Task / route | Parent asset IDs and roles | Job / prompt ID | Exact recipe and output path | Owner decision and reason |
|---|---|---|---|---|---|
| | | | | | |

| Attempt | Input actions / fields / characters | Search queries / backtracks / assistance | Active setup s | Review s | Ack s | Queue s | Generation s | Elapsed s / overlap note |
|---|---|---|---:|---:|---:|---:|---:|---|
| | | | | | | | | |

| Attempt | Identity /4 | Face /4 | Anatomy /4 | Pose /4 | Costume /4 | Finish /4 | Weighted /100 | Hard requirements | Keep / correction / reject |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| | | | | | | | | | |

Finish with four separate findings: which interface tasks passed or blocked; actual effort and waits to the first usable and first accepted result; the named image defects and the owner's decisions; any licensing question still open. Link each claim to the exact attempt. Keep rejected outputs and failed requests in the account of effort.

The existing owner tasks `lab-art-acceptance-1019`, `kromoss-trial-1019`, `moss-look-1019`, `asset-wave-1-chatgpt` and `parallax-layers-1219` remain open. This trial neither runs their models nor accepts their prior results by proxy.
