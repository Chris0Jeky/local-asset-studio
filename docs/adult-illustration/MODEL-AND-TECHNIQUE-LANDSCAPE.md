# Model and technique landscape

Research freeze: 15 September 2026. These are candidates and hypotheses, not installed or promoted routes. Exact files, hashes, graphs, resources and terms must be captured through #9/#144 before execution.

## Portfolio lanes

### Fast drafting

**Anima Turbo** is a source-reviewed candidate for composition search. Its card describes a distilled 2B anime model, native ComfyUI support, CFG 1 and 8–12 steps. The same card warns that distillation increases stability/default style while reducing diversity. It therefore belongs in a separate fast-preview lane, not as proof of final quality or compatibility with SDXL adapters.

Existing fast/accelerated repository routes remain baselines. Any Turbo, Lightning or acceleration adapter is a distinct route with its exact schedule.

### High-quality anime generation

Source-reviewed first-wave baselines:

- **Anima Aesthetic** — hybrid tags and prose; quality tags differ from Base/Turbo conventions.
- **Animagine XL 4.0 Opt** — SDXL, ordered tag-oriented prompting and documented generation settings.
- **Illustrious XL v2 Stable** — SDXL-family anime baseline with a broad derivative ecosystem.
- **NoobAI XL 1.1 EPS** — tag-oriented SDXL-family baseline; EPS and v-pred must remain separate profiles.
- **one representative Pony route** — compatibility/ecosystem baseline, selected from an exact version already useful locally rather than many near-duplicate merges.

Start with official/base cards and currently installed baselines. Community merges are later hypotheses only when they solve a measured gap.

### Multi-image instruction editing

**Qwen Image Edit 2511** is the primary first-wave candidate because it documents multiple image inputs, improved character/multi-person consistency, geometric reasoning and LoRA integration. The official weights are 20B BF16; a 16 GB workstation therefore needs a separately pinned quantised/offloaded route and real memory evidence. Full/native and accelerated local configurations are not equivalent.

**FLUX.1 Kontext dev** is an experimental edit comparator with character/style/object references and iterative consistency claims. Its model weights use a non-commercial licence; output permissions and model-service/product use remain separate facts.

Existing repository Qwen/Klein/AniEdit work remains the executable baseline and is reconciled through #21/#357 rather than copied into a new shelf.

### Experimental anime architectures

- **NewBie Image** — candidate natural-language/tag/XML structured prompting and multi-character binding research; exact official revision and runtime path must be pinned before it enters the library.
- **Anima 2.9B preview** — recent community extension of Anima, useful as a watchlist candidate; preview status, inherited terms and resource cost prevent early promotion.
- Later releases enter discovery only through explicit source intake and comparison against promoted routes.

## Prompt dialects

The source intent is independent. Exact profiles compile it differently:

- Anima: lowercase tags with spaces plus optional natural language; Aesthetic should not inherit Base/Turbo score-token assumptions.
- Animagine: ordered tags and its documented quality/settings convention.
- Illustrious/NoobAI/Pony derivatives: exact card/route grammar only; no family-wide boilerplate.
- Qwen/Kontext-style editors: concise natural-language instruction with explicit image-role ownership and invariants.
- Positive-only/distilled routes: exclusions remain unresolved or are rewritten deliberately; a graph textbox called `negative` is not proof of effective conditioning.

A tagger proposes vocabulary. It does not reconstruct the source prompt or prove another model learned the same token.

## Geometry and regional techniques

- **DWPose/OpenPose** — body/face/hand/foot keypoint proposal; inspect and edit before use.
- **depth/normals** — torso/limb orientation and spatial structure, especially under foreshortening.
- **line/sketch/edge** — contour and garment construction.
- **silhouette/segmentation** — outer contour and regional ownership.
- **Blender mannequin/camera** — authored geometry when estimation is unreliable.
- **SAM 2 or a qualified segmenter** — editable mask proposal, never automatic write authority.
- **regional conditioning** — subject/background/contact ownership; separate from final pixel masks.

ControlNet Aux and custom preprocessors require exact installed-schema and dependency review. Do not install them merely because a research card names them.

## Appearance techniques

- **character/canon reference and identity LoRA** — recurring identity;
- **outfit reference/LoRA** — garment construction separate from identity;
- **IP-Adapter-style conditioning** — appearance/style/composition influence with exact base compatibility and crop behavior;
- **native multi-image editing** — semantic role composition;
- **style/material/expression adapters** — low-strength, qualified after structure and identity;
- **body/proportion sliders** — only after monotonicity and collateral-effect evidence.

Averaging all references into one embedding is a baseline, not a universal fusion strategy.

## Repair and finishing

Use the smallest meaningful intervention:

1. inspect the visible defect;
2. select instance/contact and context;
3. author or review geometry if structure is wrong;
4. define write and protection masks;
5. generate a bounded candidate;
6. composite and compare;
7. retain failure and change hypothesis rather than rerolling indefinitely.

High resolution is a separate derivative stage: simple resampling, illustration super-resolution and low-denoise refinement are compared independently. Diffusion refinement is reconstruction, not exact recovery.

## Training

Training begins only after reference/native routes show a repeatable gap. Candidate trainers such as OneTrainer or sd-scripts run in isolated environments. Record exact trainer commit, base hash, trained modules, dataset/captions/masks, split, precision, rank/alpha, learning rates, optimiser/scheduler, buckets, checkpoints, resources and failures.

For Anima, the official card recommends Base for LoRAs, not training its LLM adapter, using a low learning rate and starting around rank 32 / `2e-5`. These are source recommendations to test, not universal settings.

## AMD/runtime

AMD’s current Windows support matrix lists the RX 9070 XT for PyTorch on ROCm 7.2.1/Windows 11 while warning that the full ROCm stack is not available on Windows. This makes a current Windows comparison viable but does not certify every Comfy custom node, captioner, trainer or quantised loader.

Measure per exact route:

- cold process and first generation;
- warm generation;
- model switch;
- VRAM and host RAM/Windows commit;
- load/encode/sample/decode/export where source events prove them;
- spill/offload;
- unload/cleanup;
- OOM, driver reset, crash and uncertain outcome.

Linux is a separate comparison only when pinned and isolated; it is not assumed faster without evidence.

## Promotion rule

A candidate is promoted only when it adds a useful role or improves accepted-output yield/control enough to justify its latency, memory, cleanup and terms. Popularity, showcase images, source-review and successful loading are insufficient.
