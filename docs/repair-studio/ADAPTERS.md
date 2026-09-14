# Candidate adapters and qualification

Design for #248 with #245 geometry and existing #9/#21/#65/#71/#119/#144/#178. This is an adapter contract, not a list of installed or quality-approved models. Research source IDs refer to [RESEARCH.md](RESEARCH.md).

## 1. Candidate families

**Matched-style local candidate.** Use an existing registered anime checkpoint and its proper encoder/VAE. Distinguish ordinary masked img2img from a dedicated inpaint model or compatible inpaint patch. An SDXL patch does not attach to Qwen, FLUX or SD1.5 weights. A PNG created by one family can still be repaired using another: evaluate style/identity drift instead of calling the bitmap incompatible.

**Instruction/reference candidate.** Extend the current Qwen context-plus-identity bridge before adding a new interface. Preserve real native slot order and semantics. The current bridge does not send a grayscale write mask into Qwen; exact scope is enforced in final composition. Whole-crop edits may shift framing and therefore require registration checks. FLUX.2 Klein is a separately qualified candidate, not a silent fallback.

**Geometry-guided candidate.** Use an authored or reviewed pose/depth/sketch through a compatible native spatial-conditioning route. Store whether the guide was inferred from defective imagery. HandRefiner research is a useful design precedent, not a universal or directly portable node. An optional Blender hand/body proxy can make intended joints explicit; it is still a design hypothesis until reviewed.

**Non-generative/native route.** Preserve, crop, composite, paint or perform deterministic layout. `native` in the offline proposal means manual/native work without implicit AI inference. An AI-enabled editor must submit any image-producing work through the same Studio owner or an explicitly reconciled adapter; it cannot bypass campaign accounting.

**Finishing route.** Conservative learned restoration and optional diffusion remaster are distinct from anatomical repair. Both create derivatives and retain their own model/filter/colour/scale provenance. A pure upscaler does not need a diffusion seed; it still consumes resources and produces an output that needs visual inspection.

## 2. Proposed adapter protocol

These method names describe the future shared interface, not new callable APIs in this PR:

```
describe() -> capability descriptor
preflight(repair_revision, runtime_observation) -> ready | unsupported | blocked | unknown
prepare(repair_revision, pinned_dependencies) -> exact candidate input bundle
request(prepared_bundle, registered_campaign, command_id) -> existing Production project/stage
observe(project_id) -> existing authoritative execution projection
collect(stage_id) -> immutable candidate + actual execution receipt
```

Use the current `character_edit_bridge_plan.py` for pure preparation and `character_edit_bridge_io.py` for client IO. The Production service remains the only execution owner. Do not call a private adapter's `/prompt` directly from UI or an agent. Unknown writes retain the original request/project identity.

## 3. Capability descriptor

A descriptor identifies the adapter implementation/version and references existing catalog/model-library records rather than duplicating them. It reports:

- candidate family; supported preservation modes; reference count, native slot roles/order and spatial controls;
- required checkpoint/prediction/encoder/VAE/patch/LoRA family; schedule/negative-conditioning semantics; supported quantization and acceleration variant;
- source alpha/profile/mode policy; canvas/latent alignment; actual internal reference normalization; mask conversion; known crop/resize operations;
- target-size limits and measured load/encode/sample/decode resource envelope; runtime platform and evidence freshness;
- independent installation/schema/execution/visual-task/terms statuses, with unknown distinct from unsupported;
- permitted user controls, exact graph bindings and which changes invalidate cached evidence.

A capability advertised upstream is not a positive local observation. A valid graph schema cannot establish memory fit. Per-task quality evidence expires or is requalified when an effective model, graph, preprocessing or policy dependency changes.

## 4. Qualification ladder

**Q0 source reviewed:** provenance, dependency family, native conventions and terms recorded. No installation claim.

**Q1 contract tested:** descriptor and graph/slot/mask transforms pass synthetic conformance. No inference or memory-fit claim.

**Q2 executes locally:** one exact bounded run completes on the actual runtime, with prompt ID, output and stage memory/time observations. A failed decode remains failure even if sampling completed.

**Q3 useful for a named task:** source/candidate/composite reviewed for intended change, identity/costume/contact, seams and retained pixels. One useful example is not a general rate estimate.

**Q4 qualified policy route:** held-out class-specific evidence under #257/#66/#72 supports the displayed recommendation and budget. Promote that exact task/configuration, not the model shelf.

The ladder is an evidence projection; it does not merge art acceptance or rights into execution readiness. Users can explicitly audition an experimental route within a finite campaign. No proof is invented to make the UI green.

## 5. Conformance fixtures

Create original synthetic images with labelled colour squares, thin lines, alpha-key pixels, odd dimensions, asymmetric padding and clear non-target areas. Verify what the native node receives, its actual resize/crop and the candidate returned. Include a deliberate full-crop overwrite candidate to demonstrate that final source protection is independent of model compliance.

Test native mask polarity, zero/edit-full masks, off-grid output, unexpected profile/alpha, missing slot, swapped reference, stale template, incompatible patch, changed backend root and response loss. Add source/context registration checks: equal width/height alone must not validate shifted framing.

Use complete real Stage/Start/Collect/Compose fixtures with only the neural boundary substituted for deterministic tests. Real neural qualification then requires explicit approval and a registered campaign. Adapter-level retries cannot create extra candidates hidden from the coordinator.

## 6. Prompt and reference behavior

Build a scoped instruction from the source provenance, defect intent and accepted references. Preserve relevant original character/costume/style information; remove irrelevant multi-panel counts and expression-strip instructions for a single crop. Show the instruction before submission. Do not append model-specific score tags from unrelated families.

A useful example for a reviewed hand region is: repair the hand-to-wrist connection while preserving the intended gesture, sleeve and lighting. This is intent, not a mechanical guarantee. The effective mask and compositor enforce the write boundary. Retain the exact actual prompt, including compiler suffixes and slot labels, in the recipe.

Reference roles must survive UI-to-template projection. Three slots cannot silently accept four distinct required references; ask for a reviewed reduction or use a qualified alternative. A costume reference is not relabelled pose to fit a backend. A contact repair requires adequate references from all affected actors or an explicit limitation.

## 7. Runtime and supply-chain boundary

No node auto-install, runtime pip upgrade, arbitrary workflow code, unreviewed model download or automatic cloud fallback. Use existing pinned library/intake mechanisms and #178 resource preflight. Record hash/size/source/revision and evaluate model-specific terms without assuming that local execution grants unrestricted usage rights.

Current user hardware must be observed before execution. Historical 32 GiB records and later reported 64 GiB RAM are not interchangeable; physical memory, available commit and VRAM are separate measurements. CUDA examples and advertised NVIDIA memory figures are not Windows ROCm evidence. Successful sampling without successful decode is not a completed asset.
