# Intermediate reference configurations

Read this before mixing image adapters or changing model filenames. The source inventory and supported control mechanisms were researched on 11 September 2026; local compatibility must be checked against the installed runtime.

## 1. Give each reference a job

A reference slot consists of file hash, media kind, role, things to copy and things not to copy. Store masks/crops and their coordinate transforms when relevant. The initial brief schema supports up to twelve reference records, but a particular graph may accept fewer. **The included native Qwen graphs support one to three images. The planner does not silently compress twelve references into that limit.**

| Role | Copy | Avoid accidental transfer |
|---|---|---|
| Identity | Face, proportions, distinctive design features | Pose, lighting, unrelated costume unless requested |
| Costume | Silhouette, components, emblem placement, material | Body identity or composition |
| Pose | Joint arrangement, hand/prop contact, viewing angle where explicit | Person's face, outfit and rendering style |
| Style | Line weight, shading, palette relationships, medium | Subject identity or copyrighted logos |
| Composition | Framing, scale relationships, negative space | Unrequested objects or literal background |
| Geometry | Measured shape, axes, units, topology or approved base mesh | Treating invented rear views as measurements |
| Motion | Timing, action phases, trajectory, contacts | Camera motion or body proportions unless intended |
| Mask | Explicit editable/protected region | Guessing whether white means preserve or edit |

Prompt example:

> Use Image 1 for the character's face, hair, proportions and approved costume. Use only the pose and hand placement from Image 2. Use the linework and restrained watercolor shading of Image 3, not its subject. Create a waist-up portrait with the character holding a compass in the left hand. Preserve the brass clasp, teal coat and left-side satchel. Keep the background simple; do not add lettering.

Role wording helps an instruction-following model but is not a mathematical disentanglement guarantee. For pose-critical anatomy, test a structure-conditioned graph. For exact protected pixels, composite the approved source outside the edit mask rather than trusting a “change only” sentence.

## 2. The three delivered Qwen API graphs

Files are in `research/game-assets/workflows/`:

| File | Reference configuration |
|---|---|
| `qwen-1ref-api.json` | Image 1: identity/costume, plus user instruction |
| `qwen-2ref-api.json` | Image 1: identity/costume; Image 2: pose |
| `qwen-3ref-api.json` | Image 1: identity/costume; Image 2: pose; Image 3: rendering style |

These are actual API graph JSON files derived from the repository's existing `workflows/api/qwen-api.json` at commit `6bd4e5ba36c3df22011727772754b6e9b3d13c70`, not text-only blueprints. `provenance.json` records the original Git blob and canonical JSON hash. The factory verifies the expected baseline node identities and rejects collisions or an already multi-reference baseline. It deep-copies the source rather than mutating it.

The [native node implementation](https://raw.githubusercontent.com/Comfy-Org/ComfyUI/master/comfy_extras/nodes_qwen.py) exposes `image1`, `image2` and `image3` on `TextEncodeQwenImageEditPlus`. Extra inputs are connected to both conditioning encoders; the existing multi-reference latent method remains in place. File bindings are:

```text
Node 4.image      = asset-identity.png
Node 16.image     = asset-pose.png       [2/3-reference variants]
Node 17.image     = asset-style.png      [3-reference variant]
Node 6.prompt     = user-authored or role-compiled description
Node 11.seed      = explicit experiment seed
Node 13.filename_prefix = controlled output prefix
```

Paths above are Comfy input filenames, not arbitrary user-PC paths. The local agent should upload/copy authorized reference bytes into Comfy's input area, retain the returned safe name and bind that name. Do not send a local path to a hosted service by accident.

The inherited bundle is Qwen-Image-Edit-2511 Q4_K_M, the Qwen2.5-VL encoder, Qwen VAE and the matching four-step Lightning adapter. The factory deliberately retains the original model, encoder, VAE, scheduler and sampling settings: four steps, CFG 1, Euler/simple and shift 3.1. This is preservation of an existing repo recipe, **not a newly optimized recommendation**. Use the separately prepared quality path for a controlled comparison; do not simply increase Lightning steps and label it a full-quality model.

The original primary image still passes through its 768×768 `ImageScale` with cropping disabled. Pre-crop or pad a nonsquare primary reference deliberately, or revise the graph with an aspect-aware path and retest. Do not unknowingly stretch a character and then blame identity conditioning. Extra references follow the native encoder's own preprocessing. Record all crop/scale transforms if pose or mask coordinates must agree.

Validation in this pass covers static topology and regression properties. No saved live `/object_info` snapshot or new inference was available. The supplied checker can inspect a locally saved snapshot, but dynamic custom schemas still need Comfy's native validation. The graphs are not added to the production preset picker and visual-node counterparts remain a follow-up.

## 3. Which mechanism should an agent select?

**A. One reference, a new expression or outfit detail.** Begin with a model-specific reference edit. Preserve hairstyle and costume through a protected-region comparison. If the edit is local, crop/mask and composite rather than regenerate a full turnaround.

**B. Identity plus pose.** Use the two-reference Qwen graph as a convenient semantic test. For strict limbs/contacts, use a matching pose/depth ControlNet and a separate appearance adapter. A photograph of a pose and an extracted skeleton are different inputs; check the graph's contract before connecting them.

**C. Identity plus pose plus style.** Use the three-reference graph, or independently tuned structure and appearance controls in a supported SDXL family. Start from identity-only, add pose, then add style. Diagnose whether a failure begins at a particular conditioning stage. A single “reference strength” slider cannot faithfully represent every model's mechanisms.

**D. Several characters together.** Scope each identity to a region or instance and label references explicitly. A collage does not guarantee spatial binding. Test isolated characters, then the joint composition, and record identity swaps. The shipped three-slot configuration is not a demonstrated multi-character compositor.

**E. Many references for one production identity.** First select a canonical identity sheet and reconcile contradictions. A larger model input allowance is not permission to mix inconsistent ages, proportions, costumes and viewpoints. BFL documents different limits across hosted APIs, playground and local dev; its [dev recommendation is up to six images](https://help.bfl.ai/articles/6546682167-what-is-multi-reference-editing). Use the exact selected model/node's limits, not an advertised universal maximum. [Klein's native documentation](https://docs.comfy.org/tutorials/flux/flux-2-klein) is a distinct family-specific entry point.

**F. A mask must preserve the rest exactly.** Define mask semantics and coordinate system. Save original pixels, generate the candidate region, composite with a reviewed feather where required, then verify protected-region equality on the decoded pixel data. Lossy final export can change pixels again; keep the lossless source proof.

**G. A whole character pack.** Approve the identity first; then run portrait and key-pose branches from the same design. The eight-route planner expresses the dependency structure. A generated sheet may be useful as a proposal, but each final frame needs a correct canvas, anchor, action phase and duration.

## 4. Useful experiment configurations

Recommended initial comparison, explicitly experimental: identity-only versus identity+pose versus identity+pose+style, two seeds each, one fixed brief. Measure costume retention, face consistency, pose/contact fidelity, final-size readability and cleanup effort. Hold the reference bytes and dimensions fixed. Equal integer seeds across different model families are not equivalent noise or equal compute.

For cutout animation, compare manual layer preparation with Qwen-Image-Layered followed by repair. Count holes exposed by rotation and minutes of overlap painting, not merely how many layers were produced. For stroke animation, compare manually drawn inbetweens with LayerInbetween on two accepted keyframes. For 3D-generated sprites, compare the deterministic render to any optional style-transfer pass across adjacent frames rather than one cherry-picked frame.

A candidate becomes a default only when it improves an explicit production outcome. Keep original/refined previews and rejected examples. Generation success, design acceptance and licence status must remain separate fields.
