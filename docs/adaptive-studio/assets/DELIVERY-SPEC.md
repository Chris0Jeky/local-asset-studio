# Asset delivery and acceptance contract

## Logical requests versus physical outputs

A catalogue row describes a requested asset family. One row can yield a master, several crops, encoded renditions and a receipt. The inventory therefore must not be treated as a count of generations, files or billable calls. `profiles.json` holds **target** dimensions and budgets. A future provider may not support those dimensions natively; record actual output size and use a reviewed crop/resize/export stage. Do not silently claim a native 4K generation from an upscaled file.

`generate` commissions an original still. `edit` uses the approved anchor for a specific change or layer extraction. `derive` crops, composites or encodes accepted input. `animate` commissions a loop from a still. `source` searches an actual library/provider. `vector` and `code` produce editable functional design. `capture` records actual software behavior. `audio` is optional sound acquisition. All are future work; this pass only writes their specifications.

## Local package layout

Use the owner's configured art-working directory outside Git, for example a selected `theme-assets/<pack>/<asset-id>/` location. This is a proposed relative layout, not an existing path:

```text
<asset-id>/
  master/                 original or reviewed editable source
  renditions/             explicitly named encoded sizes
  review/                 crop, alpha, seam and visual-inspection notes
  receipt.json            actual producer/source/output information
pack-manifest.json        accepted IDs, roles, hashes and local relative paths
```

Name a rendition `<asset-id>--<width>x<height>--<variant>.<ext>`. Never overwrite an accepted master without an explicit new version and receipt. Keep incoming candidates separate from accepted runtime media. Do not store private reference images, downloaded originals, large clips or archives in ordinary source commits. A small approved public demo asset may follow the repo's existing rules, but it requires deliberate publication selection.

## Required receipt fields

Use `receipt-template.json` as an unfilled shape. Record requested ID, actual provider/tool/model as reported, input anchor IDs and hashes, prompt/brief version, output IDs, local relative paths, actual dimensions/duration/codec/byte size/checksum, edits, and inspection results. Record unknown values as null with a reason, never a plausible-looking invented hash or URL.

For sourced work retain provider photo/video ID, original item page, creator credit, download date, exact terms page or retained terms evidence, and any relevant reuse restrictions. A search filter labelled “free” is not a universal warranty about depicted trademarks, people or downstream distribution. The next acquisition session should verify the actual source rather than repeat a general legal promise. Maintain source review, art acceptance and runtime qualification as separate fields.

For generated work record the tool's actual reported model/version. The user's phrase “image 2.5” is a requested creative route label, not a verified API identifier. Native-chat tools may not expose a seed or exact model build; leave it unknown. An output ID or checksum identifies bytes but does not alone prove authorship, compatibility or legal clearance.

## Renditions and visual checks

| Asset type | Required inspection |
| --- | --- |
| Scene/hero/wall | View in actual slot at 390x844, 1440x900 and 1920x1080; preserve text-safe regions, focal point and readable controls |
| Transparent helper/layer | Confirm a real alpha channel; no checkerboard baked in; inspect edges on light and dark surfaces; eliminate matte halos |
| Parallax set | Same dimensions/camera/origin; composite matches anchor; no exposed holes at maximum offsets; include occluded-region repair |
| Loop | Inspect first/last seam, stationary camera, no subject morphing/new objects/flashes; remove audio; attach matching still before use |
| Icons/components | Editable vector/code; consistent grid and line weight; native semantics and forced-colors/keyboard support |
| Tutorial | Exact app commit and public fixture; real operation and actual result; transcript/captions; no private input or fake progress |
| Sample set | Canon and role order documented; illustrative status distinct from actual execution evidence |
| Audio | Inspect peaks, abrupt attack, loop seam and mute behavior; no essential information exclusively in sound |

Semantic text is never inferred from generated decorative art. Workflow diagrams, comparison labels, keyboard hints and badges are real vector/HTML content. Decorative images have no meaningful alt text; illustrative images receive a concise context-specific caption. Do not invent descriptions of source preservation merely because an example looks similar.

## Motion and loading qualification

The renderer must follow [AMBIENCE.md](../AMBIENCE.md): local poster first, remote opt-in, bounded loading, stale-load rejection, reduced-motion/static fallback, user pause, one playing decorative video, no loop during active/uncertain runtime work. Internet, local API and backend availability are separate observations. Disconnected internet with healthy local ComfyUI is not an error state.

Treat byte budgets as proposed acceptance thresholds, not measured performance: poster <=300 KiB, visible first-screen decorative transfer <=350 KiB, optional loop <=4 MiB, bounded local theme cache <=128 MiB. Use visible-container-sized renditions. Test decoded memory and compositing while the real Radeon inference workload runs; a small compressed file can still be expensive to decode. A performance failure means simplify/downsample/keep still, not silently increase budgets.

No remote media or font CDN is a startup dependency. Do not cache draft/API responses as theme content. Do not autoplay sound. Local loops can work offline, but their display still follows job/resource/accessibility policy. A missing or failed media item resolves to a local poster, then CSS tokens, without a blocking modal or an execution-state change.

## Import safety

A theme pack is data, not executable code. Reject path traversal, symlink escape, mismatched type/extension, oversized or corrupt payloads, and an unapproved remote address. Imported SVG needs sanitization or rasterization; scripts, external references and foreignObject are not accepted as theme payload. Never render provider descriptions as raw HTML. Provider credentials and acquisition operations stay outside the render loop.

Keep downloaded metadata and source review tied to the exact chosen file. Content hashes guard accidental mismatch; they do not certify the provider's ownership claim. No automatic model/LoRA installation, command execution, reference staging or generation is part of importing a decorative pack.

## Acceptance stages

`planned` -> `candidate-produced` -> `source-reviewed` and `art-reviewed` (independent) -> `renditions-verified` -> `runtime-qualified` -> `selected-for-release`.

A stage is evidence, not a decorative badge. A candidate can be artistically accepted while source questions remain unresolved; it can be source-reviewed but too distracting or too heavy. The release selection records the actual choices and unresolved limits. No field is advanced merely because a model returned an image or the file decoded successfully.
