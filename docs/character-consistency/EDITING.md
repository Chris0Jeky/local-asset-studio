# Controlled character editing: repairs, costumes and scenes

Start here for the extension to the [character programme](README.md). This is an additive specialization of the existing Studio, not a replacement editor or a second inference queue. [Run the CPU proof](EDIT-RUNBOOK.md), inspect [tool-policy evidence](TOOL-POLICIES.md), then use the [benchmark protocol](EDIT-BENCHMARK.md). Research checked 12 September 2026; no neural quality result is claimed by this document.

## The outcome

Keep a reusable character identity while changing only the requested aspect: repair a hand, introduce a costume variant, place two characters in an observatory, or correct how their hands meet around a prop. Preserve editable sources and earlier accepted states. The goal is high *accepted-edit yield*, not simply an image-generating call that returns successfully.

Four separate requirements govern each operation:

| Requirement | Enforcement or evidence |
|---|---|
| Exact preservation | Restore decoded source RGBA outside the write mask; check every protected pixel. Implemented. |
| Identity/costume continuity | Compare each actor against its own references and selected costume revision. Requires visual review and measured model performance. |
| Geometry/contact | Pose/depth/layout guides plus joint-region review; a written instruction is not a spatial constraint. |
| Intended change | Verify that the defect was fixed or the new design actually appeared. An unchanged image can satisfy preservation while failing the edit. |

A request for a different camera or global lighting cannot also require every original pixel to remain unchanged. The planner must expose that conflict: keep pixels in the local-repair route, or create a scene branch with semantic identity locks and an explicitly larger write area. Never quietly reinterpret an exact lock as a prompt suggestion.

## Persistent information

Use the accepted canon from `character_study.py` as the identity authority. An edit document stores a hash-bound source snapshot, revision, actor IDs, separate per-actor canon/reference records, conservative current bounds, and scene/relationship descriptions. The edit request declares its changes, context crop, write/protection masks, budget and route preferences.

Keep these dimensions independent:

- **Identity:** face construction, hair, stable distinctive features and the character's chosen proportions.
- **Costume variant:** garment design, materials, ornaments and back construction. A costume change creates a proposed variant, not an unnoticed mutation of identity.
- **Scene instance:** placement, pose, expression, contacts, camera, occlusion and lighting for this appearance.
- **Representation:** illustration, chibi, pixel sprite, layered puppet or mesh. Approved simplification belongs here rather than being misclassified as identity drift.

The current edit document pins the canon file as an artifact. It does **not** parse and approve its semantic design: a runtime adapter must invoke the existing canon validator and approval service before promoting production assets. Synthetic demo canon files are fixtures, not approved characters.

`context_box` is what the model may see; the edit mask is where its result may be applied. The protection mask can protect face, hair or another actor even inside a useful context crop. Mask geometry is reviewed data: a correct hash cannot prove that a selected region really is the sleeve.

## Path A: small anatomical or appearance repair

1. Freeze the source revision and inspect at final size and crop scale. Identify the particular error: digit structure, elbow alignment, hand/prop contact, eye asymmetry or a stray mark.
2. Author or review a write mask. Include the actual defect and a controlled transition edge. Give the model enough context to understand the arm and prop; do not grant it that entire context as editable area.
3. Choose the appropriate operation. A deterministic transform or paint correction may be sufficient. For missing structure, use a matching inpaint/edit route, optionally with an authored pose guide.
4. Generate a bounded candidate for the explicit padded crop. The adapter must preserve the recorded crop transform. A model output of a different size is not silently resized into position.
5. Apply only through the write mask. Check the original/candidate/final together: unchanged protected pixels, successful repair, coherent contact and no visible seam.

If the mask is too narrow to fix an extra digit or a mislocated wrist, propose a new mask revision. If the model returns the same broken hand, preservation success must not turn it into acceptance. Face/hand detection is a localization proposal, not an anatomy oracle.

## Path B: costume replacement

First describe the new costume as a versioned design proposal: front/back structure, permitted silhouette change, accessories, material and details that must be visible. Keep the face/hair/identity references separate from the new costume reference. The original outfit should not dominate the identity slot merely because it occupies most of a full-body image.

The write mask must cover both the **old garment footprint and the new garment footprint**, plus required disocclusion and transition regions. Replacing short sleeves with a cape may expose or hide pixels far outside a naive torso mask. A pose/depth map extracted from the old clothing can preserve the wrong silhouette; replace it with an appropriate body proxy or reviewed guide.

Create the costume on one neutral view, review it, establish hidden construction and only then propagate it to other views. Do not feed every new rendering into a chain that gradually changes the design. Re-anchor to the accepted identity and the newly selected costume revision.

The supplied planner emits a `costume-branch` proposal and facet-specific invalidation keys. It never overwrites a canon or fabricates owner approval. Production should invalidate costume-bearing outputs and their downstream sheets while retaining unaffected face crops, independent characters and original source bytes. The included DAG invalidation helper computes this from declared dependencies; undeclared dependencies remain a modelling error, not something a hash discovers.

## Path C: multi-character scenarios

Start with a scene layout rather than one long prompt. Each actor has its own stable ID and references; identical local reference IDs in different actors are legal because the actor namespace is preserved. The request specifies desired bounds and optional pose references, a back-to-front actor order and explicit contact regions. Unknown actors, duplicated bindings, missing identity references, cyclic global occlusion and impossible declared ordering are rejected.

For a two-character observatory scene, the proposed production sequence is:

```
scene layout and camera/light proposal
  -> reviewed background or authored proxy
  -> actor A appearance using only A's identity/costume references
  -> actor B appearance using only B's identity/costume references
  -> joint contact/occlusion repair where their hands meet the telescope
  -> local shadow/edge integration within declared masks
  -> per-actor identity review and scene-level acceptance
```

Pure alpha cutouts are a useful baseline, but do not themselves solve common lighting, perspective, hidden limbs or physical interaction. Conversely, a final whole-image "harmonize" pass can destroy the identities established in the earlier passes. Prefer controlled contact, shadow and seam passes. Global changes require an explicitly different preservation contract.

Per-actor sequential passes and joint generation are alternatives to compare, not a guaranteed universal ranking. Interactions may require a shared crop and references from all participants. The `interaction` operation therefore permits multiple target actors and demands a contact relationship and region. A global front-to-back order does not represent two interlocking arms; local contact regions must carry that exception through a native layer/mask adapter.

The current planner preserves these typed proposals but does not bind them to a neural graph. Excess references must produce an unsupported-capability result, never truncation, arbitrary montage or reassignment of costume to pose. Studio's three semantic reference slots are not a universal eight-actor controller.

## The local-agent/editor bridge

The working bridge is intentionally small: `describe` -> `plan` -> `prepare` -> externally create candidate -> `apply`. Both preparation and application are deterministic local CLI operations. They expose JSON, exact images and explicit errors, so a local agent can use them without writing ad hoc image code. No LLM, cloud call, content classifier or model installer is hidden in those commands.

For the native extension, reuse Krita for document/layer/selection/painting operations, ComfyUI for model inference, and the existing Production service for ownership and budgets. The agent should propose typed operations such as `inspect_document`, `propose_mask`, `plan_edit`, `prepare_patch`, `request_candidate`, `import_result_layer`, `compare` and `revert`. The user and agent operate on the same revisioned document; neither has an independent hidden state.

Krita AI Diffusion is a strong candidate for the canvas side: its maintained documentation covers selections, edit models, regional references and controls [S1-S4]. It is not automatically a Studio-compatible executor. Avoid running its automatic/live generation path beside Studio without one reconciled job owner. The actual native plugin runs in Krita's application environment [S5]; importing `krita` into the Studio Python interpreter is not the bridge.

A model-generated mask is a proposal. Specialist tools such as Krita Vision Tools can help select objects by point/box [S6]; hair/translucency matting needs separate assessment. Qwen Image Layered is a decomposition candidate [S7], not an automatic puppet rig. A local VLM can propose edit intents or critique results, but its own refusals, hallucinations and calibration are independent of the image model's behaviour [S8].

Keep operational safeguards separate from content preferences. Workspace confinement, no overwrites, revision checks, bounded memory/compute and no duplicate uncertain submissions protect the user's work. They do not add an artistic keyword filter. A prompt hidden in image metadata or a model card is input data, not permission to run a command.

## Implementation boundary and next integration

Implemented: strict actor/edit contracts, source-bound plans, truthful route-policy reporting, symbolic downstream invalidation, context extraction/padding, hash-bound candidate application, pixel-preservation checks and a reproducible synthetic proof.

Not implemented here: local LLM inference, automatic segmentation, neural candidate generation, Krita/MCP connection, shared transactional edit-document storage, live budget enforcement, semantic acceptance or high-yield generation. These attach to #71 (native bridge), #72 (edit-yield benchmark) and the existing #23/#65/#66 rather than becoming a second framework. No model changes or moderation-bypass mechanisms are installed.

The minimal runtime integration must reserve the **shared** budget, retain intent/prompt IDs before and after submission, reconcile lost responses, prevent stale document results from being applied, and import an unapproved result as a new layer/revision. Actual successful edits and measured failure classes are required before unattended promotion.

## Sources

[S1] https://github.com/Acly/krita-ai-diffusion

[S2] https://docs.interstice.cloud/edit-models/

[S3] https://docs.interstice.cloud/regions/ — regional conditioning is not geometric composition control.

[S4] https://docs.interstice.cloud/control-layers/

[S5] https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html

[S6] https://github.com/Acly/krita-vision-tools

[S7] https://huggingface.co/Qwen/Qwen-Image-Layered

[S8] https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct

[S9] https://huggingface.co/Qwen/Qwen-Image-Edit-2511 — author-reported character and multi-person improvements, not this project's benchmark.

These are primary capability sources reviewed for architecture, not evidence that their exact current implementations have been installed or executed on the user's workstation.
