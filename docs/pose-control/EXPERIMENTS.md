# Pose-transfer qualification protocol

Design date: 15 September 2026. Refs #407, #409, #439, #440, #446. This is a proposed experiment design, not an executed benchmark or generation allowance.

## Questions and discriminating tests

| Hypothesis | Minimal comparison | Evidence that would change the decision |
| --- | --- | --- |
| Extraction, not the generator, caused the earlier structural failure | Failed detector guide versus manually corrected guide, same SDXL route and appearance | Corrected joints improve intended geometry without unacceptable appearance cost |
| Wrong donor geometry caused heel leakage | Same cached depth map versus reviewed fixed-canvas erasure; identical route/prompt | Foot shape changes while body/camera/identity measures remain acceptable |
| Copy Pose is useful beyond one pair | RGB route on unseen source situations and second character | Accepted distinct tasks, not just repeated success on the development pair |
| Representation is route-specific | Native RGB input versus declared unsupported depth variant in isolated research only | Never promote a generic preprocessor chain without evidence |
| Two stages beat repeated whole-image rerolls | First-pass + bounded scoped repair versus equal total-attempt budget | Lower time/active effort to an accepted asset, no protected-pixel drift |
| Ignored donor attributes leak | Matched target geometry with varied donor costume/background | A pose-only route remains stable on appearance invariants or is honestly narrowed |

A hypothesis test changes one factor within an exact route. Cross-route portfolio comparisons are useful engineering comparisons, not causal isolation of model architecture alone.

## Screening campaign

Eight cases, two fixed noise initializations per route, three frozen routes: **48 first-pass candidate slots**. This is a screening budget, not statistical evidence of a universal success rate. Production authorization remains zero until a separately reviewed campaign allocates it. Repairs, retries and image-producing warmups need their own counted slots; a failed/refused reservation and an actual image attempt must not be conflated.

Cases:

1. Familiar difficult bend: development case only; preserve its historical failures.
2. Unseen crossed-leg configuration: explicit front/back overlap.
3. Seated/support pose: feet and support relationship specified.
4. Overhead reach: body and arm placement independently reviewed.
5. Strong camera foreshortening: camera is a scored requirement, not inferred from body-joint similarity.
6. Hand/prop contact: body-only P0 guide declares the hand/contact gap; additional evidence is required.
7. Second approved character in an unseen pose: challenge identity/costume generalisation.
8. Irrelevant-donor-attribute counterfactual: a fixed pose with a declared baseline/variant donor pair. The two candidate slots are paired with one shared route-specific seed, not mislabeled as two independent seeds; larger seed replication requires an amended cap.

The eight-case arithmetic allocates two slots per case. Case 8 intentionally uses those slots for baseline/variant instead of seed replication. Record this asymmetry in the report. Freeze real sources outside Git; synthetic manifests hold case IDs and required observations only. Split held-out material by identity/source situation, not adjacent crops of the same image.

Routes:

- One installed Klein 9B geometry-reference configuration, with exact input representation frozen for the campaign; do not mix skeleton and depth results into one configuration.
- The recorded Copy Pose RGB-input configuration, with character first, pose donor second and exact LoRA/trigger.
- One corrected-skeleton SDXL ControlNet configuration. Freeze checkpoint, appearance-conditioning method and native renderer. The target guide bypasses pose detection.

## Preflight before any image attempt

Read exact model/encoder/VAE/LoRA hashes, graph hash, node commits, runtime identity and current installed schema. Check both reference roles, canvas/aspect, transforms, guide bytes, renderer options and no example-file residue. Verify resource readiness through the existing coordinator. Preserve unfilled or unsupported controls as blockers, not dropped fields.

Review intended body keypoints before generation. Mark unknown geometry rather than manufacturing certainty. Hands, camera, limb overlap, support and contacts need separate requirements when COCO-18 cannot encode them. Neither detector confidence nor artifact hash is owner approval.

## Execution discipline

Use existing Studio/Production APIs and saved job/prompt identities. No new direct `/prompt` experiment loop. A lost response is observed through the existing receipt/history mechanism, never automatically replayed. Stop on unknown dispatch outcome, repeated binding failure, driver instability or exhausted cap.

Block by resident model to avoid uncontrolled model swaps, retain block order, and reverse/rotate order in a later replication. Distinguish queue, cold load, preparation, sampling and total wall time. Keep fast and observed degraded Comfy process states separate. The historical restart probe is a workaround observation, not a proved allocator/driver diagnosis or permission to restart an active queue.

## Review record

Every candidate keeps case/source/pose/renderer/route/job/output identities and one row per criterion:

- hard constraints and subject count: pass / fail / unreviewed;
- body pose: pass / fail / uncertain, with a named mismatch;
- camera/framing;
- identity;
- outfit/colours/exact markings;
- style/palette;
- hands/contact/support;
- anatomy/legitimate occlusion;
- ignored-facet leakage;
- owner acceptance: true / false / null.

Use reviewed landmarks for optional normalized pixel-error diagnostics, with visibility and denominator retained. Do not let the failing extractor be the sole scorer. No global aesthetic score can override a required-pose failure. A generated, executed, reviewed, accepted and rights-cleared result remains distinct.

Report accepted distinct tasks / attempted distinct tasks, total reservations, actual image attempts, failures by class, active correction time, queue/wait time, cleanup time and time to first accepted result. Include all rejected candidates and incomplete cases. Case 8 is a paired distractor test, not an extra independent success observation.

## Stop, narrow, promote

Stop a route on an invalid binding or uncertain dispatch until reconciled. Two consecutive repeats of the same defect without a changed hypothesis trigger review rather than another blind reroll. This is a proposed experiment policy, not a runtime auto-restart rule.

A route is promoted only for the cases/content/style range actually reviewed. Record failures alongside successes. If body pose improves but appearance collapses, retain it as a geometry draft candidate rather than calling pose transfer solved. If a good candidate needs one local repair, report both attempts and test final protected pixels.

## Follow-on research, in order

1. One complementary structural condition after a corrected-skeleton baseline works. Keep route-local strength/schedule bounds and source-derived defaults.
2. Confidence-aware regions: reliable torso depth, corrected limbs, removed distractors and explicit replacement foot/hand geometry. A black rectangle is not universally neutral conditioning.
3. Neutral 3D proxy for unresolved perspective and contacts, with explicit coordinate/depth conventions.
4. Wider counterfactual distractor tests for donor clothing, backgrounds and silhouette appendages.
5. A specialised pose-transfer model only after exact release/runtime/terms qualification; no assumed AMD compatibility.
6. Targeted adapter training only after retained evidence shows a reference/control gap and the dataset/canon/rights owners approve a separate plan.
