# Repair contracts and coordinate accounting

Normative design for #244/#245/#246/#249. Existing v1/v2 character-edit contracts remain authoritative until a versioned adapter explicitly supports the additions. The shipped `studio.repair-proposal/v0` checker validates a small **design-declaration subset**, not these full runtime contracts.

## C1. Immutable source and normalized canvas

Retain original bytes, MIME/format, bounded metadata and content digest. A normalization receipt names original and derivative identities, encoded dimensions, EXIF transform, oriented dimensions, materialized transparency, colour/profile decision, bit depth, decoder version and pixel limits. Byte hashes and decoded-pixel hashes answer different questions.

The initial repair master is a bounded single-frame RGB/RGBA PNG derivative. Do not silently flatten animation, HDR, palettes or unknown colour profiles. The current pixel bridge rejects EXIF; normalize through a new explicit intake route before calling it. The current neural bridge additionally rejects genuinely transparent/colour-ambiguous context; that guard must remain until an alpha/colour-aware candidate adapter is qualified.

Use one bounded byte capture for source hash and decode facts. Snapshots must not replace an existing concurrent destination; reuse the existing Workspace boundary and pending #234/#235 corrections. Same-capture consistency is not a universal snapshot guarantee against a hostile concurrent writer. Recheck actual source dependencies at apply/dispatch.

## C2. Identity and observations

An instance has a stable ID, parent panel/scene, canon link, costume revision and role-bound references. A prop is an entity without an invented character identity. Repeated panels may share a canon, never an instance ID. Keep reference order because native models can attach meaning to slot number.

An observation carries `source_revision`, `region`, `view_transform`, `observer`, `observer_revision`, `finding`, `visibility` and evidence. Visibility is visible/occluded/out_of_frame/ambiguous. A model confidence is a detector or critic output, not a calibrated probability of correctness unless independently established. Human annotations and accepted canon are separate records; neither is reconstructed from a hash.

A contact declares participants, source-space region, intended relation and applicable local occlusion. Hand-to-prop constraints may involve a protected prop: participating in the edit intent does not automatically make the entire entity writable. Review all contact regions after candidate placement.

## C3. Five different spatial meanings

| Artifact | Meaning | Convention |
|---|---|---|
| Subject selection/matte | Which visible instance pixels belong to the target | Binary selection or separately declared fractional alpha |
| Context image/box | What the model can inspect | Normalized source coordinates with explicit exclusions/padding |
| Sampler edit mask | Where an adapter may add/redraw model content | Adapter-specific, converted from a declared canonical artifact |
| Final write coverage | Where candidate pixels can enter the repair master | Full-source grayscale L, 0 source / 255 candidate |
| Protection | Pixels forbidden to change | Full-source binary L, 255 protected |

Source transparency is not repair permission. Comfy LoadImage inverse-alpha masks need an explicit conversion; an ordinary transparent cutout must not be passed as an implicit edit mask. A bbox detector is not a subject matte, and a subject matte is not necessarily the correct repair footprint.

Compute the final effective support after dilation, feathering, crop mapping and any resampling. Store both the authored mask and effective mask with the producing transform. Reject support/protection overlap rather than silently subtracting it and pretending the requested repair is still feasible. Padding must remain non-writable. A full-frame edit must be explicitly declared, not inferred from an accidental mask.

Mask the old defect footprint, intended corrected footprint and required transition/disocclusion. Deleting an extra limb means recreating the background behind it. A crop can show shoulder, wrist and prop while only the reviewed hand transition is writable. Conversely, protected neighboring imagery may still influence conditioning; handle contamination in context/reference design, not by claiming the protection mask prevents influence.

## C4. Coordinates, scale and padding

All boxes are `[x0, y0, x1, y1]` on the normalized oriented source, with exclusive right/bottom coordinates. Store source crop, intended rational scale, actual rounded resized dimensions, padding L/T/R/B, final work size, native alignment, filters and transform implementation revision. Do not stretch to a square or silently centre-crop.

For the v0 mathematical scaffold, positive dimensions use half-up rounding:

```
resized_width = floor(crop_width * numerator / denominator + 1/2)
sx = resized_width / crop_width
x_work = (x_source - crop_left + 1/2) * sx - 1/2 + pad_left
x_source = (x_work - pad_left + 1/2) / sx + crop_left - 1/2
```

The y mapping is analogous. Integer coordinates denote pixel centres; support boundaries use half-pixel edges. Independent integer rounding can make actual x/y scales differ slightly, so record both rational values. Do not assume a global nominal scalar is the actual mapping. Other adapters may use different conventions, but must declare and test them rather than reusing this identity incorrectly.

Raster resampling is not invertible. Exact inverse **coordinate** accounting does not recover original high-frequency image content. Reinsert a corrected crop into the original using the recorded transform and effective write mask; restore source pixels outside it. Validate landmarks/context registration in addition to shape, particularly for instruction editors that may reframe the scene.

The current no-resample bridge is retained unchanged. New scaling requires fixtures for odd sizes, asymmetric padding, transparent edges, integer/fractional scale, crop-boundary support and model-side auto-resize. Unknown internal resizing is an unsupported adapter state, not a guess.

## C5. Pixel preservation

For normalized source S, registered candidate C and final write coverage W, the compositor creates R through the existing declared blend operation. Require exact decoded RGBA equality `R[p] == S[p]` for every p where W is zero and every protected p. Check source/candidate/result together. RGB hidden under zero alpha participates in a strict RGBA contract; visible similarity alone is not exact preservation.

Encoded-space versus linear-light blending, straight versus premultiplied alpha, ICC handling and precision are explicit. Existing Pillow encoded-space blending is not automatically linear-light colour management. Candidate mode/profile changes fail before apply unless a reviewed conversion adapter creates a new compatible candidate.

Mask boundaries can blend while still producing visible seams. Zero outside-mask changes proves scope, not wrist alignment, correct fingers, retained costume or useful change. A no-op result stays unaccepted unless the operation itself was intentionally no-op.

Global upscale and colour transforms create a **derivative** with a distinct contract. Exact preservation may be evaluated against a separately generated deterministic scaled baseline where appropriate, but never called equality to the original-resolution source. Preserve the repaired master separately.

## C6. Candidate and decision records

A candidate receipt binds source/document/instance/canon/reference/mask/transform identities; exact native template and effective graph; model/encoder/VAE/adapter/runtime versions; campaign/stage/attempt identity; actual prompt ID; output hash, dimensions, mode, profile; and complete execution/collection outcome. Unknown pins remain unknown.

Track independent dimensions: preparation validity, execution state, mechanical validation, intended-change review, identity/costume/contact review, owner acceptance, rights review and target export acceptance. No one `verified` boolean collapses them. An agent may select a candidate for review; it cannot manufacture owner approval by supplying a hash or `approved:true`.

A repair decision records original/candidate/composite crops, each applicable check as pass/fail/not_visible/uncertain, notes, reviewer provenance and source revision. An accepted repair becomes a new revision; undo/revert creates another revision without deleting evidence. A draft can be exported, but stays labelled draft.

## C7. Dependencies and authorization

UI and agent commands include expected document revision, command/request ID and exact operation scope. Source, effective masks and canon are checked again at the final write boundary. An older proposal may remain inspectable but cannot overwrite newer native or Studio work. Bind complete dependency manifests; #225 owns the existing Krita request gap.

Register and reserve through existing Production campaigns. Limits in an offline proposal are only declarations. All actual image-producing stages count; changing seed list, label, revision or plan directory cannot evade the root cap. Auxiliary analysis calls are explicitly bounded too. Unknown submissions retain their identities and reservations until existing reconciliation determines a supported next action.

## C8. Shipped v0 subset

The checker accepts a source hash/revision/size; one preservation mode; crop/scale/pad declarations; bounded instances, targets, references and contacts; four hash-declared masks with explicit convention; intent/visibility/synthesis declaration; finite candidate/analysis caps; and ordered alternative strategy names. Unknown fields, ambiguous versions and malformed/duplicate JSON fail visibly.

It checks algebra and declaration consistency only. Mask files are not opened, hashes are not verified, contact pixels and native controls are not inspected, extended outpaint canvases are not planned, and no campaign is registered. Every successful response has `executable:false`, `authority:none` and `pixel_validation:not_performed`, plus the outstanding runtime/review checks. Do not feed this document directly to Production or treat it as a substitute for current character-edit handoffs.
