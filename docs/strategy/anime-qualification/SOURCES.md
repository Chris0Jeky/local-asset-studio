# Source ledger, reconciliation and maintenance

## Supplied research artifact

- Title: *Anime generation and multi-reference editing qualification for local-asset-studio*.
- Freeze: **15 September 2026**; **26 pages**.
- Source repository checkpoint: `b29205cfc95ca4e64d72ae38d53df30c83968997`.
- Supplied PDF SHA-256: `f38d620c21c2f5582e394b784fb0847ede85b399231641935506a16c384e0f6b`.
- Intake: the complete parsed text and rendered page tables were available; the runtime recommendation was checked against the rendered page 16. No OCR was needed.

The original attachment is not copied into this public repository. Page-addressed paraphrases, artifact identity, original public source leads and the adaptation are retained instead. The artifact hash binds this intake to the supplied report; it is not authentication of every claim in that report.

## Inspected repository and source transfer

Reconciliation checkpoint: `6cdf6ab09683b37f55e1b55af582e4e28eac8100`, tree `8c44aae3fdbafa643ed1ba94d1736be9f85c7a28`.

The failed earlier attempt left issue #552 and an integration branch at `537fa` (abbreviated checkpoint), with no implementation commits. The resumed branch was fast-forwarded to the inspected checkpoint, not force-rebased over unknown work.

The complete tracked source was obtained through a temporary read-only GitHub Actions archive on a separate branch: run `35325214997`, artifact `10538868542`, archive ZIP SHA-256 `2e0b96c9c1b331ed50b76742258ad2aea77f66c855f9d5d5cb514e03bbc26f84`. It checked out the exact checkpoint without persistent credentials, exported tracked files only and retained no owner runtime or secrets. The reconstructed local index matched the source tree after accounting for archive line-ending conversion and preserving the tracked CRLF JavaScript fixture. This is an isolated test checkout, not the owner's installed Studio.

The temporary workflow was removed after transfer (cleanup commit `2145025db8f06283118805a10a1d1e658b4b7f33`); its branch has no net source change. Transfer workflow changes are not part of the product PR's ancestry. Test results and the final published head belong in the PR evidence, not inferred from the source-export job's success.

## Current repository divergences from the paper

| Paper claim or omission | Inspected evidence | Adaptation |
| --- | --- | --- |
| Base 1.0 not proven in the report's runtime matrix | `models/library.json`; `experiments/curated/anime-fantasy-atelier/README.md`; Base Studio jobs `8a593206`, `8eb5bc19`, `6ae066d8` are recorded separately from earlier Aesthetic substitution probes. | Treat as a review coverage gap, not missing execution. Preserve exact settings and outcomes; do not extrapolate a model-wide success rate. |
| Stale “no Anima LoRA installed” narrative | `docs/SETTINGS-KNOWLEDGE.md` conflicts with current Anima library assets and the artist-stack recipe. | Correct the narrative and point to the canonical records. Do not duplicate the inventory. |
| Qwen prioritized without complete newer Combine comparison | Current state and `experiments/curated/style-pose-matrix/` retain Klein depth, skeleton, Copy Pose and character replacement evidence; fantasy pack has pose-then-face continuations. | Keep these as matched baselines, including face loss, heel leakage, waiting and two-pass cost. Owner quality decisions remain open. |
| Implicit new campaign needed | Merged #542 provides a strict 48-cell offline pose plan; #446 still needs real route/source/runtime and visual evidence. | Reuse its own contract. Do not inject the paper's seeds/permutations/retries into the same campaign identity. |
| New broad image analysis suggested | Existing Reference Intelligence, saved-brief and setup owners already exist; adjacent #550 vocabulary intake/#555 taxonomy work is not WD image inference. | Extend the established owners; do not declare tagger weights or GPU inference qualified from metadata-only work. |
| Private versus commercial portfolio framing | HUMAN_TODO q-26 and the Klein private-use answer already record private experimentation; q-29 leaves the adult programme undecided. | Preserve those decisions. Do not impose a new commercial launch gate on private art experiments or merge the parked programme by implication. |
| Three-model ordinary UI proposal | Current workbench/Combine tools and adjacent adaptive UX work are more developed than the report snapshot. | Keep task-first UX and measured baselines. A new frontend stack is not decided by model research. |
| Report profile examples presented together | Current Prompt Lab still has generic profile-to-recipe associations; the KB also has exact resource guidance with separate source records. | Extend these owners; do not import the report JSON as a parallel registry or claim the exact-version compiler already exists. |

This table is an inspection snapshot. Re-read open PRs and their changed paths before taking a slice; concurrent repository work can make a previously missing item delivered.

## Primary-source checks performed during adaptation

Checked **18 September 2026**. These checks distinguish current public text from report-derived claims. Unless an immutable revision is explicitly listed, the URL remains mutable and the check is not a complete source snapshot. No model weights were downloaded or executed.

| Source | What this check supports | Remaining boundary |
| --- | --- | --- |
| [AMD ROCm 10.0.0 release notes](https://rocm.docs.amd.com/en/docs-10.0.0/about/release-notes.html), Operating system support | The **Radeon** Ubuntu 24.04.4 row specifies **HWE 6.17**. GA 6.8 belongs to the Instinct row. RX 9070 XT/gfx1201 and Windows 11 25H2 appear in the release support information. | Correct report p.16; do not claim the full Studio wheel/custom-node tuple is tested. No upgrade performed. |
| [AMD Radeon Linux matrices](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/native_linux/native_linux_compatibility.html) | Separate product/version-specific compatibility reference to consult before building the comparator. | Follow the relevant version, not merely the latest page title; confirm full environment with the operator. |
| [CircleStone Anima](https://huggingface.co/circlestone-labs/Anima) | Family roles and Aesthetic score-token distinction remain documented. | Current prose does not by itself reconcile every v1.1 value or qualify the local Base/Turbo adapter stack. |
| [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0) | Ordered tags, recommended sampler/steps/CFG and aspect buckets. | Attribute local scheduler/sweep choices separately; no new visual ranking. |
| [Qwen Image Edit 2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) | Native multi-image editing and the native BF16 example's parameter names. | Does not attest the Studio's Q4+Lightning runtime or an arbitrary native slot maximum. |
| [NoobAI XL 1.1](https://huggingface.co/Laxhar/noobai-XL-1.1?not-for-all-audiences=true) | EPS settings and author-described restrictions, including generated-product commercialization. | Private-purpose decision and reference/adapter rights remain separate; no use clearance inferred. |
| [Illustrious XL v2.0](https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0) | Exact model source lead. | A satisfactorily frozen v2 Stable compiler/sampling profile remains unresolved; newer linked material is not silently substituted. |
| [OmniGen2](https://github.com/VectorSpaceLab/OmniGen2) | Authors' native memory claim and CPU-offload path. | CUDA-oriented resource claims are not Radeon timings or host-memory guarantees. Paper's commit `18e6f9d5271b517fcb32e999f10df943ae9b8f20` is a retained report pin, not a newly attested checkout here. |
| [DWPose](https://github.com/IDEA-Research/DWPose) | Whole-body pose estimation, ControlNet usage and ONNX routes. | Pin exact detector code/weights and map conventions before qualification. |
| [ComfyUI IP-Adapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) | Primary repository for architecture-specific adapter integration. | The paper's maintenance-only description is retained as its historical observation; no dependency update performed. |
| [Kontext dev license](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev/blob/main/LICENSE.md) | Model use and outputs have distinct conditions. | Preserve the actual terms and intended-use review; this integration is not a legal clearance or hosted-service approval. |

Other source leads remain report-derived, not independently requalified in this pass: the exact Pony upstream profile, full WD v3 model/weight pin, OCR implementation, individual Civitai flags/creator rights, the old ControlNet 1.1 conventions and the precise Comfy headless example. See report pp. 3-5, 12, 14-15 and 25-26. Do not turn a cited URL into a claim of completed source review.

## Claim maintenance and invalidation

For each operational advice claim retain: source kind, scope, locator, immutable revision/content or provider-version identity when available, retrieval/review date, affected component IDs, what was actually observed, unresolved limitations and a review-after date where useful. A hash/revision-shaped string is a declaration until independently verified against the cited source.

Refresh immediately when the model/base/encoder/adapter/control/quantizer, graph, node version, prompt dialect, source transforms, runtime, intended use or owner canon changes. Before spending a qualification allowance, check upstream availability/terms and current source scope again. A calendar review flag is a maintenance prompt, not automatic authority to execute or rewrite settings.

The existing guidance evaluator preserves advice conflicts instead of averaging them, and historical observations do not become recommendations. Missing `source.scope` stays `unrecorded`; family scope never becomes exact simply because targeted resource hashes match. Preserve prior receipts when a claim is superseded. Scope migration and source verification are separate tasks.
