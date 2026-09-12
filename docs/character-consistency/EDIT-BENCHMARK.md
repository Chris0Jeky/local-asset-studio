# Measure useful edits, not just preserved pixels

Tracked in #72: a **proposed, unexecuted** experiment extending #64/#66. It does not change the existing twelve-case reference-view pilot. Machine-readable design: `research/character-consistency/edit-benchmark.json`.

## Hypotheses

**E1: Scoped repair improves yield.** A model sees an informative crop but its result is applied only through a reviewed write mask. Compare with a whole-image instruction baseline from the same exact model/bundle. Endpoint: requested correction succeeds without identity or collateral defects. Preserved source pixels alone cannot satisfy it.

**E2: A costume proposal improves repeatability.** Separate accepted identity and a new garment design before propagating it into poses/views. Compare with a whole-image outfit-change request using the same source and costume reference. The first trial only measures individual edits, not proof of cross-view propagation; that requires a separately budgeted extension.

**E3: Actor-bound layout reduces cross-character copying.** Compare a joint prompt baseline with actor-bound references, reviewed layout and scoped scene passes. Evaluate each face, hairstyle, costume and contact independently. Paired stage counts and actual compute must be reported; repeated use of one seed across different graphs does not align their noise.

**E4: Specialist tools lower cleanup effort.** Compare reviewed automated selection/pose proposals with manual masks/guides for the same tasks. Include their preparation time, model/tool setup cost and failures. This is a later ablation; the initial edit trial does not answer it.

## First controlled trial: 32 primary attempts, 8 reserved repairs

Use two approved original identities (one can be held out from helper tuning), each with one anatomy defect, one garment change, one scenario and one two-actor interaction: eight task instances. Two strategies and two seed replicates give **32 primary attempts**. Reserve **four repairs per strategy**, eight overall; total **40 image-producing attempts**, not 40 jobs of arbitrary batch size.

For the first trial, the scoped scenario strategy must use one joint regional candidate per primary attempt, retaining typed actor/layout controls. Do **not** claim a multistage per-actor sequence fits one attempt. The planner's multi-actor sequential route is a different experiment whose stage count must be explicitly budgeted. This avoids giving the scoped strategy hidden extra inference.

Any neural warmup, failed decode after inference, cancelled generation, uncertain submission or repeat consumes the same candidate allowance. A separate run may reallocate unspent attempts before submission through a recorded plan revision, never after seeing results. Do not silently skip hard cases. Record failed preparation separately so it cannot disappear from end-to-end success reporting.

Use one exact model/configuration shared by both strategies where possible; pin weights, adapters, prompt/native fields, input order, source bytes, crop transforms, sampler, output dimensions and runtime. Budget differences in actual GPU time remain visible. Only use a documented native regional/control path; unsupported actor binding is a reported blocker, not a prompt-only claim.

Source design and mask creation have real costs. Record those separately and in total effort, even though this candidate allowance begins after approved sources exist. Selecting an original canon, training a LoRA or provisioning a new runtime requires its own explicit experiment, not free pre-processing outside all budgets.

## Proposed targets, not predictions

The scoped strategy target is **at least 12/16 primary attempts** passing edit-success and all applicable critical visual checks, and **at least 7/8 distinct task instances** yielding one accepted result within its **20-attempt total cap** (16 primary + up to 4 repair). These small denominators are feasibility targets, not a universal 75% or 87.5% performance claim.

Require **zero decoded pixel differences outside the declared write mask and within protection regions** whenever the requested contract is exact preservation. The whole-image baseline must still be assessed for collateral change; do not claim identical hard-preservation mechanisms for it. A scenario intentionally changing background pixels uses its declared larger mask rather than misclassifying every background change as a defect.

Report per class and per actor. A pool of easy recolours must not hide failed hands or exchanged faces. Show raw counts, confidence intervals when warranted, abstentions, and the held-out result. With only four primary scoped attempts per class, uncertainty is large. Even 30/30 later success would not prove zero failure probability.

## Review and cost records

For every attempt retain source, candidate, final composite, exact masks/guides, recipe, actual prompt ID, execution outcome and review snapshot. Name the reviewer kind. `pass`, `fail`, `not_visible` and `uncertain` remain distinct. A required identity feature that cannot be seen needs another diagnostic view or abstention; do not guess it was preserved.

Measure whether the requested change happened, identity per actor, costume correctness, anatomy/contact, scene relation, collateral changes and final-size seams. A generated/refused/failed state is separate from semantic acceptance. Classify content refusals separately from unavailable controls, empty masks, unchanged images, out-of-memory, reference mixups and visual failures.

Primary cost metric: **total measured effort per accepted distinct task**, including review, mask preparation, rejected attempts and repair. Also show first-pass yield, time to first usable result, median/p95 only with adequate samples, warm/cold inference timings and measured memory. Missing values remain null; external published timings are not local measurements.

The vision critic must be calibrated through #66 before auto-selection. It cannot grade its own prompt text as proof the pixels are correct. Owner approval and native/engine acceptance remain distinct. Prefer independent masked/blind comparisons without revealing which strategy produced each candidate.

## Stop and expansion rules

Stop a route after a confirmed capability mismatch, persistent incorrect identity assignment, exact-preservation failure or exhausted budget. Preserve the most useful intermediate and the failure evidence. Do not solve a failed test by lowering its requirement after the run.

After the first scoped trial, expand one successful class at a time. Suggested later tests: cross-view costume propagation; sequential versus joint actor rendering with matched total compute; challenging occlusion/hand-held props; local VLM versus manual review; original unseen identity; authored-rig baseline for repeated scenarios. Each receives a new frozen case set and budget. A broad "high success rate" label requires repeated held-out production results, not the deterministic fixture.
