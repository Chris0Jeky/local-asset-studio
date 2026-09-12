# Reverse prompting, examples and iterative discovery

“Reverse engineer the prompt” covers several different tasks. The studio should expose the distinction instead of pretending the pixels reveal the original instructions.

## 1. Recover recorded recipe claims first

The existing inspector now handles bounded PNG textual chunks, JPEG/WebP metadata
and an explicitly supplied schema-v1 JSON sidecar. It retains independent and
conflicting records, source hashes, encoding decisions and unsupported fields.
It never imports nodes, executes a graph or asks a vision model to interpret pixels.

Known Comfy API output nodes are traced to separate sampler stages and their
positive/negative conditioning inputs. Unused text stays separate. Unknown
operators, output ambiguity, dynamic text and cycles remain visible rather than
being resolved by guesswork. Zeroed conditioning is not presented as an effective
negative prompt; filenames are not model pins. A user-selected output node is
not proof that it created the supplied pixels.

A checksum-valid or hash-matched record is still an editable **claim**, not
authenticated provenance. For faithful reproduction, reconcile the original
graph, source images, masks, model hashes, node/runtime versions and latent
initialization. The inspector does not establish that execution contract.

See [Output-aware recipe inspection](RECIPE-INSPECTION.md) for the CLI, HTTP and
sidecar schemas, supported node/format subsets, budgets and synthetic demo. The
CLI accepts media up to 16 MiB; the browser uses a smaller limit within the
existing 1 MiB HTTP request cap. No pixel decode, arbitrary sidecar discovery,
XML interpretation or automatic workflow import is performed.

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
