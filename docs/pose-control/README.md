# Geometry-first pose transfer

Design date: 15 September 2026. Baseline: `fee134aee70b3432873197e233b6b888d98f1d22` (merged #431).

Status: architecture and implementation programme, not a claim of qualified pose transfer. Parent ownership stays with #407. The owner requested this programme after reviewing the recent Combine trials: preserve a character's identity, outfit and finish while faithfully taking another image's pose, including unusual poses.

Read [EXPERIMENTS.md](EXPERIMENTS.md) for the qualification protocol and [IMPLEMENTATION.md](IMPLEMENTATION.md) for the first test-first slices.

## Product outcome

A person can see the intended geometry, correct a failed extraction directly, keep that correction while changing generation routes, and repair a local defect without discarding an otherwise accepted result. Agents use the same artifact and revision identities. Success is time and active effort to an accepted asset, not the number of available models or successful HTTP jobs.

The immediate useful seam is corrected body keypoints plus a rendered guide. It deliberately precedes a richer camera/contact scene specification: a small tool that produces inspectable files is more useful than another broad non-executing schema with no working path.

## What the existing evidence establishes

The [Combine research record](../../experiments/curated/style-pose-matrix/2026-09-14-combine/README.md) and PRs #367, #372, #381, #424 and #431 separate several failures:

- Some early failures were wrong routes, inherited pose prose or unwanted costume instructions. Do not classify those as model capability limits.
- OpenPose and DWPose produced a scrambled extraction on the difficult reference. The earlier SDXL comparison therefore did not test a correct ControlNet input.
- Depth-first Klein improved the body configuration, but depth retained donor geometry such as heels. Foreground segmentation alone does not remove a shoe inside the subject.
- A manually drawn skeleton influenced the result, including an incorrectly drawn arm. This justifies a correctable geometry input; it does not establish complete-pose reliability.
- Copy Pose worked on the tested RGB pair but not on its depth substitution. Route-specific representations and ordering matter.
- A two-pass edit fixed a recorded foot defect. That visual observation is not a guarantee that a whole-image editor preserves all other pixels.
- Three seeds of one source pair are development evidence, not a held-out success rate. Preserve every per-axis defect and the owner's uncompleted q-28 review.

The shipped [depth graph](../../workflows/api/combine-klein-9b-depth-api.json) feeds estimated depth through VAE encoding and `ReferenceLatent`, not a dedicated depth ControlNet. [BFL's structural-guidance documentation](https://docs.bfl.ai/guides/usecases_editing_controlnets), checked 15 September 2026, describes this semantic reference approach and warns against pixel-perfect expectations. Do not promote the guide to a deterministic body rig.

## Alternatives and decision

1. **Keep searching prompts/checkpoints.** Cheap integration, but leaves bad extracted geometry invisible and confounds failures. Retain only as a baseline.
2. **Inspect/correct geometry and qualify a small route portfolio. Chosen.** Works with the existing Studio, improves diagnosis and permits local interventions. Costs a focused authoring surface and exact binding contracts.
3. **Require a full 3D character rig or train a new adapter immediately.** May help difficult views, but adds substantial setup/training costs before the present baselines have a fair comparison. Keep a neutral Blender proxy as an escalation, and training behind an observed held-out gap.

## Architecture and ownership

```text
Existing Workspace sources + reviewed appearance intent
                    |
Existing detector output / authored keypoints / later Blender proxy
                    |
P0 pose artifact: canvas + body joints + uncertainty + source identity
                    |
Explicit correction -> immutable child artifact -> inspectable guide
                    |
Existing setup preview: exact geometry + appearance roles + route bindings
                    |
Existing prepare / Production / single Studio worker
                    |
Per-axis review -> accept OR bounded scoped repair -> export derivative
```

- `studio_workflow` owns the pure pose artifact and local import/edit/export helpers. It does not acquire a database, server, queue, downloader or model runner.
- AssetWorkspace owns eventual persistence and content-addressed bytes. #120 and #418 own shared document/revision mechanisms; do not create a pose-specific competing store.
- #21/#232 own real source staging and reviewed native slots; #445 qualifies the new geometry bindings.
- #422 owns the Combine source-pair/results/engine-switch loop; #444 adds the focused pose overlay there, not a new general canvas application.
- #10/#72 own registered execution allowances and candidate accounting. #302 supplies resource evidence. #446 supplies the focused screening protocol.
- #243/#245/#248/#249 own scoped repair, pixel masks, model adapters and coupled contacts. A conditioning-erasure mask never acquires pixel-write authority.
- #403's controlled-illustration programme consumes these generic geometry tools. This work does not duplicate its intent ontology, source discovery, adapter lab or benchmark executor.

Active PRs #425/#428 own continuation ordering/canvas limits; #418/#421 own persistent reference briefs; #434/#436/#441 own research/source intelligence; #442 owns the public-facing documentation refresh. This additive programme does not overwrite their paths or claim their unmerged behavior is shipped.

## Decisions

### P-01: Store geometry, not a longer pose caption

A pose artifact describes an explicit body layout. Appearance intent excludes the source's old pose. Camera, overlap and contact remain separate declared requirements when the body-only artifact cannot express them; never quietly compile unsupported geometry to text and call it controlled.

### P-02: Missing is not zero; manual is not detector certainty

The first adapter supports one explicitly selected COCO-18 body with continuous pixel-edge coordinates on a fixed canvas. A joint at x=0 or y=0 is valid. A missing joint is null. Positive detector confidence is retained; manual edits carry manual origin and null detector confidence. Export formats requiring a positive presence flag may use a documented sentinel, never relabel it as detector evidence.

### P-03: Bounded, hash-identified content; no approval by validation

Import retains the SHA-256 of the exact keypoint JSON bytes, source coordinate-space declaration and selected person index. Artifact identity is deterministic canonical JSON over validated content. It is integrity/provenance, not a signature or proof of human correctness. Every artifact remains unreviewed in P0. The CLI can check structure and revise content but cannot approve geometry or art. Image-byte identity, native transforms and human review must be observed separately at staging.

An edit supplies the expected artifact ID and a finite set of unique joint replacements. Validate the complete batch before producing an immutable child; a stale ID refuses. A no-op returns the unchanged artifact. The parent is never overwritten. Unsupported BODY_25, MPI, nonempty face/hand/3D channels and ambiguous frame selection refuse rather than dropping useful information.

### P-04: Rendering is a versioned adapter, not just colored lines

A local COCO-18 PNG preview provides an immediate inspectable artifact for manual experiments. Record renderer version, canvas, threshold, point filtering and output hash. It is not asserted byte-equivalent to an upstream renderer or qualified for SDXL.

For the actual SDXL comparison, use the installed auxiliary renderer with pinned options. [ControlNet Aux](https://github.com/Fannovel16/comfyui_controlnet_aux) exposes keypoint JSON; [OpenPose output documentation](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/02_output.md) describes distinct body layouts and coordinate scales. [Xinsir](https://github.com/xinsir6/ControlNetPlus) documents rendering/preprocess differences and complementary control types. These sources motivate explicit layouts, coordinates and renderer identity; they do not qualify the owner's AMD configuration.

Do not send a pre-rendered skeleton through a pose detector. Route it as a precomputed guide to the actual control node. Preserve aspect ratio and record any crop/resize/pad transform. A skeleton, RGB pose donor and depth map are different input types.

### P-05: Erasure is not cropping

#431's successful intervention painted the lower region of an already computed depth map black. Cropping the original RGB image changes framing and recomputes depth. Implement dimension-preserving post-depth erasure under #427, recording source/output hashes and exact regions. Outside the declared erasure region pixels must remain equal. Black means removed visual evidence for this candidate recipe, not universally neutral depth or a guarantee of no leakage. Feet requiring exact orientation need replacement structure, not automatic deletion.

### P-06: Preserve accepted pixels by construction

A whole-image semantic edit can still drift. Repair candidates must return through #245's effective write region and composite onto the accepted original. Test outside-region pixel equality. Contacts may require a joint region owned by #249. Exact lettering can be a deterministic finishing layer instead of a reason to reroll the whole figure.

### P-07: Escalate geometry only where it helps

A neutral Blender proxy can establish camera and limb/contact arrangement without a finished character model. Record application/version, scene, camera intrinsics/extrinsics, pose, render pass, depth convention and transforms. Derive clean guides; do not treat a crude visible mannequin as a magically disentangled reference. Keep 2D corrections for intentional illustration stylisation. Advanced multi-person/contact/hand support stays under #407/#249 until an explicit adapter exists.

### P-08: Judge routes by bounded outcome and effort

Freeze case/route/source/guide identities before a campaign. Separate body pose, camera, identity, clothes, style, anatomy and contact. Keep all failures and uncertain submissions. No rerolls without allowance, no cross-architecture same-seed equivalence, and no model promotion from software validation. Novel confidence-aware regional conditioning and counterfactual distractor tests are hypotheses to evaluate, not shipped capabilities.

## Ordered delivery

| Slice | Owner | Deliverable / exit evidence |
| --- | --- | --- |
| P0 | #443 | Import, revision-checked correction and PNG/JSON export; synthetic software tests |
| P0d | #427 | Exact post-depth erasure helper and pixel-preservation tests; live effect separately reviewed |
| P1 | #444 / #422 | Focused Combine overlay, existing Workspace revisions, explicit staging; real-browser no-generation proof |
| P2 | #445 | Exact Klein, Copy Pose RGB and corrected-ControlNet candidates; no detector-on-skeleton mistake |
| P3 | #446 / #439 | Bounded held-out screening, accepted-task/effort report, narrow promotion or rejection |
| P4 | #407 / #249 | Neutral proxy and explicit camera/contact guides for unresolved hard cases |
| P5 | #245 / #248 / #257 | Scoped repair and accepted-pixel preservation; complete accepted asset |

No new model acquisition, training, GPU call, owner-runtime change, private-media publication, allowance expansion or HUMAN_TODO decision is authorized by this document. Models and their terms remain exact-route checks. Initial code can run locally without the Studio or ComfyUI; live qualification is a separately recorded step.
