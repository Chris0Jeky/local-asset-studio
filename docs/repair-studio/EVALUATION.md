# Evaluation and release evidence

Design for #257; reuse #66 critic calibration and #72 scoped edit evaluation. No neural experiment is performed or authorized by this document. Proposed budgets below are ceilings for separately approved studies, not credits, registrations or changes to the exhausted historical pilot.

## 1. Preserve existing studies

Keep #72's frozen 32 primary + 8 repair = 40-attempt design and its ownership intact. Do not substitute new source images, change denominators or silently append this programme's trials. Existing completed/failed/unknown work stays recorded. A new diagnostic campaign requires a new explicit approval and registered receipt under the existing coordinator.

## 2. Measure the right outcomes

Report distinct tasks accepted within budget, total candidates attempted, useful candidates, critical wrong edits, abstentions/not_visible cases, reversions and unfinished tasks. Measure wall time, active selection/masking time, model time, review time and manual cleanup. Cost per accepted asset includes rejected and failed attempts, not just the last attractive image.

Preservation, actual defect correction, identity, costume, contact/pose, seams and final-size readability are separate assessments. An unchanged image can pass preservation and fail repair. A sharper image can fail anatomy. A geometrically plausible hand can fail because it holds the wrong prop or belongs to the wrong actor.

For paired degradation, retain a known clean original and derive downsampling/compression/noise variants through recorded transforms. Pixel or perceptual fidelity comparisons are meaningful within that setup. For natural generated deformities there is no unique correct original; use an authored intent/reference/contact rubric and reviewed outcomes rather than fabricated ground truth. Neither benchmark category substitutes for the other.

## 3. Proposed diagnostic pilot

A small new pilot can use eight task cases, two declared strategies and at most one primary candidate per case/strategy: at most 16 primary attempts. A separately declared rescue pool of at most eight gives a maximum of 24 image-producing attempts for that campaign. Already-good/no-op controls should consume no image attempt when the policy chooses preserve; do not fill unused slots merely to meet the ceiling. Analysis calls/time have a separate finite cap specified before registration. This is a proposed design, not a run request.

| Case | What it reveals |
|---|---|
| Intact panel | Unnecessary redraw and false defect detection |
| Tiny malformed hand/wrist | Working crop resolution and actual structural correction |
| Extra/ambiguous limb | Footprint, disocclusion and topology rather than sharpening |
| Legitimately occluded fingers | False positives and not_visible handling |
| Out-of-frame foot | Reconstruction declaration versus false extraction claim |
| Neighboring character fragment | Target/reference contamination and protected scope |
| Hair/veil over clutter | Selection versus matting, alpha halos and native handoff |
| Two subjects sharing a prop | Joint contact, identity and sequential-versus-coupled cost |

Use manual/current Studio practice as baseline, not an intentionally weak generic prompt. Compare the proposed scoped route using the same source, intent, allowed changes and total work ceiling. A different model's identical seed does not imply paired latent noise or equivalent candidate difficulty. Retain all variant settings.

The pilot discovers failures and determines which route/class combinations deserve wider qualification. It is not a universal reliability estimate and should not be turned into a showcase by discarding inconvenient cases.

## 4. Held-out qualification

Freeze source identities, costume references, defect labels, visibility, allowed scope, budgets, adapter/policy versions and scoring before the held-out run. Split by identity/costume/source sheet; near-identical crops from one sheet do not form independent train/test cases. Include intentional stylization controls and multiple render styles, not only easy frontal portraits.

Use a blinded or at least independently ordered source/candidate/composite review where practical. The generating model's own critique cannot approve its output. Record disagreements and reasons, with exact candidate IDs. The owner decides artistic acceptance; automated mechanical failures cannot be waived by an aesthetic score.

Proposed initial quality targets, to approve before a qualification study: at least 80% of in-scope tasks accepted within a maximum of three image candidates per task, no accepted critical wrong-target/preservation/identity failure, and at least 25% lower median active cleanup effort than the current/manual baseline. These are engineering hypotheses, not measured results or guarantees. Report per class and do not dilute a failing contact route with many easy restoration images. A route that misses its goal remains experimental; do not move the goal after seeing the results.

Collect enough independent cases for the claimed confidence. Zero observed critical failures in a small pilot is not zero risk. For illustration, under independent identical Bernoulli trials, zero failures in n trials gives a one-sided 95% upper failure bound `1 - 0.05**(1/n)`; at least 299 such zero-failure trials are needed for that bound to fall below 1%. Real cases may be correlated, so this calculation is an assumption-bound illustration, not a certification rule.

## 5. Critic calibration

#66 owns calibrated advisory critique. Track detection/localization quality separately from whether a proposed repair is correct. Add explicit abstention and visibility categories; count false acceptance, false rejection and review burden. A face detector's score is not confidence that its redraw retained identity.

Evaluate the critic on withheld candidates, including fluent-looking wrong hands and unchanged defects. A quality score cannot substitute for an exact protection check. When observer methods disagree, display the disagreement or request targeted review; do not average it into unjustified certainty.

## 6. Release gates

R1: deterministic scope/recovery tests plus one genuinely accepted hand/limb repair and a retained unsuccessful/no-op case through the real shared journey. R2: clutter and occlusion demonstrations with scope/matte review. R3: repeated-instance sheet and actual coupled contact evidence. R4: bounded strategy transitions, same UI/agent semantics and real uncertainty recovery. R5: held-out task evidence, total-effort comparison and saved/reopened native/derivative exports.

A green graph check, a successful model load, a completed sample and a user-selected candidate are different milestones. Publish exact evidence level and unresolved classes. Preserve private artwork and full receipts locally; publish synthetic fixtures, aggregate outcomes and redacted provenance only when permitted.
