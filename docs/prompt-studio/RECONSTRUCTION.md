# Reverse prompting, examples and iterative discovery

“Reverse engineer the prompt” covers several different tasks. The studio should expose the distinction instead of pretending the pixels reveal the original instructions.

## 1. Recover recorded recipe claims first

A generated PNG can contain a prompt, workflow or parameter text in PNG textual chunks. The supplied inspector reads tEXt, zTXt and iTXt under file/chunk/decompressed-text limits, checks CRCs and preserves duplicate records. It extracts selected scalar text/model/sampler claims from a known Comfy JSON shape. It never imports nodes, runs code or posts the graph.

A checksum-valid metadata record is still an **embedded claim**, not authenticated provenance. It can be edited after generation, refer to missing files or describe an earlier stage. The extractor does not classify conditioning as positive/negative through full graph reachability. For faithful reproduction, reconcile the original graph, source images, masks, model hashes, node/runtime versions and latent initialization; a prompt alone is insufficient.

The CLI accepts bounded PNGs up to16MiB and up to128KiB expanded text per record. The browser intentionally accepts smaller images to fit the1MiB request cap. JPEG/WebP metadata and arbitrary sidecar formats are not implemented. The parser does not decode or validate pixel data; it is not a complete PNG conformance or malicious-media scanner. See the [PNG specification](https://www.w3.org/TR/png-3/).

## 2. Reconstruct visible design intent when no trustworthy recipe exists

Use a vision helper to describe composition, visible subject attributes, palette, lighting and rendering treatment. Optionally ask a tagger for vocabulary. Separate uncertain interpretation from direct observations. Do not infer a specific photographer, artist, real-person identity, seed, checkpoint, lens model or invisible geometry from appearance alone.

Let the user choose what matters. One reference can supply costume, another pose, another medium. Explicitly say what not to transfer. A caption of everything visible is often worse than a short selection of the properties relevant to the requested asset.

The delivered helper preprocesses up to three single-frame images, applies EXIF orientation, composites alpha onto white for analysis, scales within768px and strips metadata. That makes the analysis bounded, not perfectly faithful: fine text, small costume details and translucent edges may need a crop or manual description. The original reference and its hash remain unchanged. Cropped/zoomed multi-pass inspection is a future reviewed operation, not silently fabricated detail.

## 3. Choose the reconstruction mode

**Faithful:** prioritise composition, identity and visible design; use a reference-edit/control path where appropriate. Record unavoidable uncertainty and compare at the target size.

**Extract selected traits:** preserve only the assigned roles, such as ink treatment and palette without copying subject identity. This is the default for a style example.

**Deliberate variant:** retain locked properties and explicitly propose changes elsewhere. “More dramatic” should resolve to concrete alternatives such as lighting contrast, camera angle or stronger silhouette rather than an automatic pile of adjectives.

These modes describe the interaction design. The current IR represents roles/locks/changes; it does not include an automatic mode selector or guarantee identity consistency.

## 4. Examples and preference memory

A later reference library should store accepted output, its exact source recipe, a task/intent summary, reviewer choices and defects. Add rejected comparisons as negative evidence. Retrieve by modality, task and selected traits before multimodal similarity. A visually similar item from a different workflow or incompatible licence is not an automatic template.

Prompt retrieval should bring back **why the example worked and what was held fixed**, not just its long prompt. Keep retrieval scores distinct from confidence and quality. The Qwen multimodal embedding/reranker family is a candidate for this layer; it is not installed by this PR.

## 5. Bounded experiments instead of endless enhancement

Start with the user's brief unchanged. Compare one clarified version and one model-specific variation while keeping the same model/graph/references. Two seeds per version can be a useful first screen, not statistical proof. Inspect failure categories: omitted element, wrong relation, identity drift, pose error, excessive style transfer or bad finishing.

Change one cause at a time. A broken finger touching a prop might require a pose guide or masked repair rather than a rewritten whole-scene prompt. A video with wrong action timing may need a different reference/shot plan. A sprite with moving pivots needs deterministic packaging, not more diffusion steps.

The delivered experiment planner emits bounded proposed runs but never queues them. Automatic candidate generation, preference learning and evolutionary prompt search remain follow-ups requiring actual evaluation and shared resource accounting.
