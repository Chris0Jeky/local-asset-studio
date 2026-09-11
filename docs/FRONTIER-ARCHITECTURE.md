# Architecture: turn research into repeatable asset production

**Proposal, not an already implemented runtime.** The delivered code is the offline workbench described in [its README](../research/frontier/README.md). The following contracts guide future local-agent PRs. They complement existing issues #1 (cheap discovery), #2 (isolated backend switching) and #3 (controlled experiments).

## 1. Separate the records that currently get conflated

Use distinct entities, with stable IDs and links:

| Entity | Owns | Must not imply |
|---|---|---|
| Source record | Author URL, provider IDs, retrieved metadata, access state, dates | Author identity authenticated merely by a mirror |
| Artifact | File hash, size, format, immutable revision, local locations | Installed or executable |
| Model bundle | Exact diffusion model, encoder, VAE, adapters, patches and terms | Fits VRAM because the main file fits |
| Workflow | Visual/API graph pair, node contracts, core/custom-node revisions | Quality accepted because schema validation passed |
| Recipe | User controls, staged intent, defaults and input contracts | A universal sampler configuration |
| Execution | Prompt IDs, resolved inputs, runtime fingerprint, outputs, timings, errors | Artist approval or commercial permission |
| Acceptance | Reviewer, brief, selected output, defects, cleanup and export checks | Approval of unrelated versions or future runs |

The new research catalog deliberately cannot assert `local_verified: true`. Real execution evidence belongs in a separate append-only record, not a manually promoted research badge.

### Proposed evidence record

```json
{
  "schema_version": 1,
  "recipe_id": "h3-seed-lab",
  "workflow_sha256": null,
  "bundle_lock_sha256": null,
  "runtime_fingerprint": null,
  "submission": {"state": "not_submitted", "prompt_id": null},
  "timing_seconds": {"load": null, "encode": null, "sample": null, "decode": null},
  "peak_memory_bytes": {"gpu": null, "host": null, "measurement_method": null},
  "outputs": [],
  "acceptance": {"reviewed": false, "accepted": null, "defects": [], "cleanup_minutes": null},
  "commercial_review": {"state": "not_reviewed", "terms_snapshot_sha256": null}
}
```

Null means not measured, not zero. A successfully returned image is execution evidence, not proof of quality. This is a design example, not a file purportedly produced by a real H3 run.

## 2. A model library that answers “where does this go?”

Intake begins with the provider's exact file/version metadata and model card. Propose a component role and destination; verify it against the intended graph's loader inputs. Filename hints should be the weakest evidence, not the decisive classifier. Show the user the complete bundle, required versus optional components, installed matches and missing pieces.

A proposed bundle lock records provider, repository/model ID, immutable revision, file ID/path, expected byte size, SHA-256, role, destination, base lineage, prediction type, variant, quantization, loader class and reviewed terms. For custom nodes, also pin commit and dependency requirements. Record an unverified hash as unknown; never fill it with a made-up value or confuse a repository commit hash with a model-file checksum.

Discovery can be broad; installation should be selective. Deduplicate by trusted content hash and retain multiple logical references to the same bytes. Stage downloads as temporary files, verify size/hash, then atomically promote them. Preserve interrupted downloads where supported. Avoid populating Git with weights or cache shards.

### Resource preflight

Measure current free disk, RAM and queue state. Estimate incremental space for missing components, temporary download copies, extracted environments, decoder intermediates and output frames. Existing weights can be shared between isolated runtimes when loaders support it; do not automatically duplicate them. Reserve system headroom and account for offloaded weights competing with an encoder or another process in 32GB RAM.

Discover GPU vendor/backend explicitly. ROCm may expose Torch's `cuda` namespace; `torch.cuda.is_available()` alone must not be interpreted as NVIDIA. The helper delivered here intentionally does not import Torch. A future local capability probe should inspect `torch.version.hip`, runtime versions and supported operators in the correct interpreter, then save evidence with a timestamp.

Report compatibility as documented, measured, incompatible with this exact path, or unknown. “CUDA path unavailable” does not mean the model is mathematically impossible on AMD; it means that particular implementation needs an alternative or another worker.

## 3. Native graph first, compiler second

Start from a pinned upstream native template, then resolve filenames and validate it against the installed `/object_info` contracts. Cache discovery rather than requesting the full payload every few seconds; this extends existing issue #1. Keep a saved schema fingerprint beside each successful graph.

A compiler can later map a Studio recipe to an API graph, but it must reject absent nodes, incompatible model roles and invalid enum values before submission. Display the fully resolved plan: selected backend, models, resolution, frame count, stages, estimated budget and output contract. A human-readable blueprint such as the supplied `recipes.json` must never be accepted as executable graph JSON merely because it contains a `stages` array.

Model-family contracts own constraints such as frame-count formulas, width/height alignment, latent channels, reference limits and distilled schedules. Read them from the exact model/template revision. Do not apply a rule learned from LTX to H3 or an SDXL sampler to a distilled video graph.

## 4. Staged execution and resumability

Proposed state machine:

```text
planned -> preflight_passed -> approved -> submission_intent_saved
        -> submitted(prompt_id) -> running -> completed -> review_pending
        -> accepted OR rejected
```

Failures are explicit branches. A transport timeout after POST becomes `submission_uncertain`; it must trigger reconciliation with existing queue/history, not automatic resubmission. Preserve known prompt IDs. Queue cancellation and worker restart must target an owned job/process and refuse when unrelated work is active.

Do not promise distributed exactly-once execution over a backend that provides no idempotency key. Persist an intent before POST and a returned prompt ID immediately after it; provide a recoverable reconciliation state for the gap between those operations. This preserves the repo's current no-uncertain-repeat principle.

Stage outputs should be immutable artifacts. Before scheduling a downstream stage, verify hashes and acceptance prerequisites. A final-quality shot may require an accepted preview; an export may require reviewed typography and alpha. Rejected artwork should not trigger increasingly expensive upscales in pursuit of a sunk cost.

For one GPU, use one coordinator for Studio-owned GPU work, with separate worker processes/environments for incompatible families. Recheck the real ComfyUI queue before switching. Do not claim a Studio lock prevents manual submissions in the advanced interface. Integrate the isolated HiDream path through existing issue #2 before generalizing the mechanism.

## 5. Exact caching before approximate acceleration

A proposed conditioning cache key includes encoder/model identities, tokenizer and node revisions, prompt bytes, negative prompt where applicable, reference image/video/audio hashes, crop/resize policy, masks, frame anchors, dimensions, dtype and relevant preprocessing parameters. Sampling adds seed, schedule, guidance, model/adapters/strengths and latent initialization. Decoding adds VAE identity and tiling parameters.

Do not key a video cache only by prompt. Do not save a subset of a nested conditioning object while losing keyframes or audio. Mark serialization versions explicitly; a cache hit that changes the conditioning is a correctness defect even when the output looks plausible.

Use an atomic write and a manifest checksum; limit cache size and provide explicit eviction. Never load unknown pickle files from downloaded workflows. Exact cached intermediates, approximate attention and distillation have different quality/compatibility implications and should be separate toggles with separate benchmarks.

Account for retained tensors: caching everything can increase memory pressure. Prefer CPU/disk persistence of appropriate validated intermediates and release stage-local GPU references. Benchmark cold and warm runs separately, including host-memory peaks and crash/restart costs.

## 6. Shot planning and finishing contracts

A shot manifest should define timebase, frame count, source/target resolution, reference anchors, protected prefix intervals, overlap handles, audio sample rate/channels and desired export. Use rational timebases where needed rather than accumulating floating-point frame errors. Preserve original audio and media timestamps through every visual branch.

Continuation, interpolation, upscaling and reshooting are distinct operations. They each need their own acceptance tests. Rebuilding shape-dependent conditioning after a latent resize is not optional where the selected model requires it. Run a short seam probe before extending a long clip.

A 3D asset contract should include units, axis orientation, pivot, polygon budget, texture dimensions, channel color spaces, alpha mode, UV coverage, skeleton requirements and engine target. Run deterministic checks where possible, then visual review from multiple views. A GLB that opens is not automatically a usable game asset.

A sprite contract adds palette, logical pixel grid, anchors, frame durations, alpha policy and atlas padding. Round-trip each atlas crop to the source frame and test the actual playback loop; expand the existing Lanternkeeper checks rather than starting from scratch.

## 7. Studio UX: capability and project context

Keep Studio's home screen organized by intent: create illustration, edit a reference, build a character pack, animate a shot, repair a clip, build a prop or export a campaign. Each recipe offers draft, controlled and finishing variants where those are meaningful. Explain visible controls in the vocabulary of the task, then expose the underlying graph as an advanced view.

The model library should show why a file is missing and where it belongs. The experiment screen should show lineage and comparable crops, with original/refined toggles, seed/schedule changes and retained failures. The shot screen should show anchors and overlap intervals. The asset screen should show deliverable contracts and outstanding checks.

Use native Comfy App Mode/subgraphs where appropriate; use Krita for painting and Blender for deterministic scenes. The studio's distinctive value is coordinating those tools with provenance, compatibility, selection and export—not recreating every editor.

## 8. Research refresh without uncontrolled downloads

Periodically inspect official release notes/model cards, the relevant native-template changes and selected maintainer repositories. Then sample Civitai/Hugging Face by specific family and capability: anime line-art control, reusable identity, fantasy environments, temporal refinement, efficient text encoding, PBR reconstruction or rigging. Record publication date separately from retrieval date.

Capture why each new entry is useful, which existing candidate it competes with, and one bounded test that could falsify its claimed advantage. Retire weak or abandoned paths instead of endlessly expanding the default dropdown. Do not scrape private/gated material or automatically accept new terms. Trending counts can rank discovery candidates; they cannot establish best quality or compatibility.

## Acceptance for the future runtime

Prove restart/resume behavior with injected transport failures; reject malformed/untrusted workflows before importing custom code; verify active queues cannot be silently cleared; demonstrate bounded experiments and stable provenance; preserve output artifacts and audio; and show at least one accepted asset through the complete export path. Only then promote that specific bundle as a default flagship configuration.
