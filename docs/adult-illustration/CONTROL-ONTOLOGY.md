# Control ontology

A prompt textbox is not a control system. This ontology separates user intent from the mechanism that enforces it.

## Control domains

| Domain | Examples | Preferred mechanisms | Common failure when reduced to text |
| --- | --- | --- | --- |
| Subject/identity | face, hair, markings, body canon | canon, character LoRA, identity reference, native edit | identity drift or costume entanglement |
| Body/silhouette | height impression, shoulders, waist/hips, musculature | calibrated slider, silhouette, depth, canon | attractive but wrong or non-monotonic proportions |
| Pose/action/contact | stance, weight support, hand/prop contact | authored pose, depth/normal, sketch, joint region | impossible support, crossed limbs, lost contact |
| Camera/composition | shot, yaw/pitch, lens impression, subject bounds | layout, camera blockout, crop/aspect, composition reference | model chooses a convenient framing |
| Wardrobe/coverage | garment construction, layers, fit, coverage | outfit reference/LoRA, regional edit, mask | identity/outfit leakage and accidental exposure |
| Expression/gaze | eyelids, mouth, blush, gaze target | text/tags, low-strength adapter, scoped face edit | exaggerated expression or identity change |
| Scene/environment | location, props, atmosphere | text, layout, depth/regions, environment reference | background source copies its subjects |
| Lighting/palette/material | rim light, silk, steam, wet/gloss treatment | text, reference, material/style adapter, relighting | style adapter overwrites anatomy or costume |
| Rendering/style | line, colour, medium, era | style reference/adapter, model profile | artist/style dominates identity and composition |
| Pixel authority | writable/protected area | reviewed masks and compositor | global redraw presented as local edit |
| Finishing | upscale, sharpen, colour, typography | deterministic/native tools; qualified refinement | invented detail or style drift called recovery |

## Input types

- `semantic_text`: reviewed natural-language requirement.
- `vocabulary_choice`: verified profile-specific token or named option.
- `bounded_number`: unit, min/max/default and evidence source required.
- `geometry_artifact`: source hash, coordinate basis and transform required.
- `appearance_adapter`: exact adapter/base compatibility and range required.
- `reference_binding`: source, role, take/ignore, subject/region and native slot required.
- `mask_authority`: context, write and protection masks with explicit polarity.
- `deterministic_operation`: parameters and source/output hashes.
- `review_decision`: attributed human/agent observation; acceptance remains human-owned.

## Adult/content envelope

The source intent includes reviewed metadata:

- all represented people are unambiguously adults;
- adult assertion source is owner/canon metadata, never visual inference;
- ambiguity or youth-coded identity refuses;
- multi-adult intimate tasks include an explicit consent-context declaration;
- the content class and required coverage are route inputs, not inferred from one token;
- public fixtures remain non-explicit and synthetic.

A negative prompt is not an age or consent control.

## Independent axes for sensual art direction

Genre is built from independent axes rather than one “ecchi intensity” value:

- adult presentation;
- silhouette emphasis;
- wardrobe coverage and fit;
- fabric opacity/layering;
- pose suggestiveness;
- camera intimacy;
- gaze/expression;
- material treatment;
- narrative setting;
- rendering style;
- content class.

Each axis maps to one or more mechanisms. A body slider may need a silhouette guide. Camera intimacy changes framing/aspect and perhaps geometry. Wardrobe coverage may need a regional garment edit. Style generally enters after composition and identity are stable.

## References

A reference may carry several reviewed roles but never “everything” implicitly:

```json
{
  "source_id": "workspace-asset-id",
  "expected_sha256": "64 lowercase hex characters",
  "roles": ["identity", "outfit"],
  "take": ["face design", "hair shape", "robe construction"],
  "ignore": ["pose", "background", "text"],
  "subject_id": "adult-a",
  "region_id": null,
  "transform_id": "crop-v1",
  "confidence": "reviewed",
  "native_binding": null
}
```

Analysis capacity and generator slot capacity are different. Excess inputs refuse rather than being dropped or montaged.

## Geometry and regions

A geometry plan may include pose, silhouette, depth, normals, line art and segmentation, but each route declares which controls it genuinely binds. Control strength and schedule are route-specific.

For multi-subject work, contacts name participants and a shared region. Local crossings are allowed; one global front-to-back ordering is not enough for interlocking limbs. Regional prompts, geometry regions and pixel masks remain separate.

## LoRA and adapter controls

Classify by effect before exposing:

- identity;
- outfit;
- body/proportion;
- pose/action;
- expression;
- camera/composition;
- style;
- material/effect;
- detail/repair;
- acceleration.

Start qualification with one adapter. Then test the primary identity adapter with important pairs. A complete stack is promoted only after pairwise evidence. Acceleration adapters create separate route variants.

## Diagnostics

The compiler should report:

- unsupported control;
- missing source or stale hash;
- missing adult/content declaration;
- incompatible base/adapter;
- unqualified weight;
- non-monotonic slider;
- excess or ambiguous references;
- role leakage risk;
- geometry transform mismatch;
- mask polarity/scope mismatch;
- route/resource evidence unknown;
- terms/use gate;
- execution authority absent.

It never silently drops or translates an unsupported mechanism into generic prose.
