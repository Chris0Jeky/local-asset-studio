# Page-addressed knowledge extraction and disposition

The page references below refer to the **supplied report**, not to current upstream documentation. “Adopt” means adopt the engineering principle or qualification question; it never means the model has passed. Current corrections and verification are isolated in [SOURCES.md](SOURCES.md). Paths name existing owners or the integration documents, not newly created services.

## Portfolio and evidence foundation: pages 1-5

| ID / pages | Knowledge preserved from the report | Adaptation and owner |
| --- | --- | --- |
| K01 / 1 | RX 9070 XT, 16 GB VRAM, 32 GB RAM; checkpoint b29205c; substantial Studio infrastructure already exists. | Historical target, not a fresh machine probe. Extend current owners; no parallel registry, queue, executor or store. #552/#313 |
| K02 / 1-2 | No defensible universal best anime model; choose routes by creative role, compatibility, evidence and hardware. | Adopt role-based routing. “Promote” in the report is qualification priority, not acceptance. [PORTFOLIO.md](PORTFOLIO.md), #14/#118 |
| K03 / 1-2 | Aesthetic T2I, Animagine controls, Qwen references/editing, Base training, Turbo audition; comparators and repair/sheets have distinct roles. | Keep these hypotheses alongside current Klein/Combine and WAI baselines, rather than replacing defaults. #14/#65/#248 |
| K04 / 2-3 | Library file SHA-256, source revision, size, family and terms already exist; hashes identify bytes, not creators or legal rights. | Key future projections to canonical library IDs. No duplicated install state in these documents. #9/#144 |
| K05 / 2-3 | Anima v1.1 files coexist with model-card prose largely describing v1.0; local Aesthetic is independently pinned. | Introduce source specificity, retain the discrepancy, and separate family guidance from local workflow settings. #34/#144 |
| K06 / 3-4 | Some sources are exact-version reviewed; Pony upstream, Illustrious settings and WD weights have gaps. | Preserve unresolved status. Never fill a missing field from a neighbouring model card or gallery. #144/#9 |
| K07 / 4 | IP-Adapter has architecture-specific variants; report identifies upstream maintenance-only status. | Treat maintenance status as a historical source claim. Pin dependency/weights and recheck compatibility before updates; do not run an update from intake. #9/#445 |
| K08 / 4-5 | WD v3 tagging, Qwen3-VL analysis and OCR are different observations; exact OCR backend was unresolved. | Existing Reference Intelligence owns them. Current WD vocabulary intake is not inference-weight qualification. No silently selected OCR package. #35/#232 |
| K09 / 5 | Recovered metadata, visual observations and reviewed intent are separate; original prompt/seed/model/artist cannot be uniquely recovered visually. | Retain confidence and provenance; no observation becomes a hidden executable instruction or authoritative identity. #21/#232 |

## Architecture-specific models, settings and profiles: pages 5-11

| ID / pages | Knowledge preserved | Adaptation and owner |
| --- | --- | --- |
| K10 / 5 | SDXL-family architectural compatibility does not establish exact-base visual usefulness. | Record prediction type, base ecosystem and adapter identity independently. Pony versus Illustrious remains a qualification boundary. #144/#445 |
| K11 / 5-6 | Anima is Cosmos-derived with Qwen text/VAE components, not SDXL; native LoRAs are separate. | Reject SDXL adapter/ControlNet substitution without native support. A detected pose remains a useful artifact, not an invented Anima control. #34/#445 |
| K12 / 5, 7 | Qwen, OmniGen2 and Kontext have native multimodal contracts rather than SDXL image-conditioning adapters. | Use native image slots, per-route preprocessing and graph bindings. #21/#361/#445 |
| K13 / 6, 9 | Base 1.0: mixed prose/tags; family 30-50 steps, CFG 4-5; er_sde recommendation and alternatives. | Store as family-source advice, separately from local executed Base stacks. Do not overwrite authored defaults automatically. #34 |
| K14 / 6, 8-10 | Aesthetic 1.1 local Euler/simple, 30 steps, CFG 4, 768x1152; avoid score_* tokens. | Local schedule and family-derived Aesthetic syntax are two sources. Diagnose both positive and negative score tokens; do not silently rewrite saved text. #34/#144 |
| K15 / 6, 10 | Turbo 1.1: 8-12 steps, CFG 1 with version reconciliation outstanding. | Do not confuse standalone Turbo with Base + turbo LoRA v0.2. Conditional accelerated settings must not leak into an unaccelerated family grid. #34/#37 |
| K16 / 6-7, 10-11 | Illustrious v2 exact settings unresolved; Noob EPS and v-pred are separate prediction configurations. | Keep the unresolved compiler state; no EPS profile reused for v-pred, no community hash treated as official bytes. #144 |
| K17 / 7-10 | Animagine ordered subject/character/series/rating/content/quality tail, Euler A, 28 steps, CFG 5, documented aspect buckets. | Exact profile migration belongs in Prompt Lab/KB. Its grammar must not become a universal Pony/Noob/WAI profile. Scheduler source scope needs separate attribution. #34 |
| K18 / 7-10 | Noob uses quality/year/rating prefix; Pony score/source/rating grammar and clip skip 2 differ. | Preserve model-specific syntax and private baseline status. Current local profile evidence is not a fresh upstream source freeze. #34/#144 |
| K19 / 7, 11 | Qwen native BF16: 40 steps, true_cfg_scale 4, guidance_scale 1, blank-space negative; local Q4+Lightning: 4 steps/CFG 1/Euler/simple. | Keep checkpoint, precision, accelerator and parameter semantics separate. A Comfy CFG field is not blindly assigned a Diffusers true-CFG value. #34/#77/#302 |
| K20 / 7, 11 | OmniGen2: 50 steps/Euler, separate edit and in-context guidance; Kontext guidance 2.5, unspecified scheduler/steps. | Null means unestablished or native-pipeline-owned, not a missing number to invent. Experimental graph twins only after source/runtime qualification. #14/#144 |
| K21 / 8-9 | Five installed checkpoint hashes and revisions are copied from the repository, not inferred from file size. | Reconciled against current library IDs in PORTFOLIO; canonical bytes remain there. No new registry or automatic install. #9 |
| K22 / 9-11 | Proposed executable prompt-profile JSON is a design, not a delivered compiler. | Adapt to `research/prompt-studio/profiles.json` plus existing KB instead of adopting a second profile registry/schema verbatim. Version saved artifacts deliberately. #34/#38 |

## References, geometry and adapters: pages 11-15

| ID / pages | Knowledge preserved | Adaptation and owner |
| --- | --- | --- |
| K23 / 11-12 | Character+pose: separate IP-Adapter appearance embeddings from DWPose/OpenPose geometry. | Keep this comparator, but evaluate against the newer measured Klein depth/skeleton/Copy Pose routes. #444/#446 |
| K24 / 12 | Depth, normals, line art and segmentation artifacts are separate from their conditioning models. | Record coordinate/range/crop conventions. Segmentation can be a writable/protected mask without a segmentation ControlNet. #245/#445 |
| K25 / 12 | Pose artifact includes source hash, detector revision/weights, instance IDs, body/hands/face/confidence, raster hash, edits and advisory authority. | Extend existing pose artifact/editor contract rather than copy the paper's parallel schema. Unknown joints/occlusion stay unknown. #443/#444 |
| K26 / 12 | Editing a skeleton produces a new hashed derivative; faulty hands are not ground truth. | Preserve detector original and human revision; compare effective geometry, not detector certainty alone. #444/#257 |
| K27 / 13 | SDXL adapter boards are not native slots; averaging can blur identity and leak outfit/palette. | Record combination method, weights and crop occupancy. A style embedding is not an identity lock. #21/#361 |
| K28 / 13-14 | Native image-order grammar matters; Qwen examples do not prove an arbitrary slot maximum; four analyzed references do not imply four generator slots. | Separate analysis capacity, CreativeIntent records and selected graph capacity, with explicit unsupported-source refusal. #232/#361 |
| K29 / 13-14 | Qwen/OmniGen2/Kontext can drift semantically; crops and input occupancy affect results. | Order and crop are deliberate matched experiments, never hidden preprocessing. Keep role IDs while rebinding ordinals. #37/#446 |
| K30 / 14 | Protected inpaint uses source + writable mask; the repaint route may consume references. | Hard preservation is enforced by final composition, not a prompt request. Scope the effective mask including feather/alpha support. #245/#248 |
| K31 / 14-15 | Civitai IDs, version IDs, triggers, hashes and commercial flags were already inventoried. | Keep in canonical library/research; API flags do not override base or source rights. #9/#144 |
| K32 / 14-15 | Mishima, Glossy, Detail IL v2 and Fantastic Days are Illustrious-family candidates with different roles/flags. | Match the exact base; style benchmark is not creator authorization. A detail LoRA is not an identity remedy. PORTFOLIO, #144 |
| K33 / 15 | Anima-native LoRA, Noob IP-Adapter, Noob v-pred and community Illustrious build each have different verification gaps. | No cross-architecture stack; retain unverified prefixes as prefixes. No automatic comparator acquisition. #144 |
| K34 / 15 | Narrative “no Anima LoRA installed” conflicts with the library. | Correct current SETTINGS-KNOWLEDGE prose. Keep historical artifacts intact. #552 |

## Runtime and trusted use: pages 15-20

| ID / pages | Knowledge preserved | Adaptation and owner |
| --- | --- | --- |
| K35 / 15-17 | Current Windows baseline, separate current-supported Windows comparator, separate Linux comparator. | Correct the paper's Linux hardware-row error; no environment changes in this intake. Exact matrix/driver/torch/node compatibility still needs operator verification. #303 |
| K36 / 15-17 | Historical timings are route-specific; a poor Pony result and six-finger Noob defect are retained failures, not rankings. | Preserve attempt IDs and task context; include newer Base/Combine evidence without extrapolation. #10/#37 |
| K37 / 16-17 | Qwen-family load failure was CPU allocation/Windows commit pressure, not an established Q4-specific VRAM requirement. | Attach exact route/configuration before attribution; commit, physical RAM, RSS and VRAM are distinct. #77/#302 |
| K38 / 16-17 | OmniGen2 authors report roughly 17 GB native VRAM and offload alternatives, on a CUDA-oriented setup. | Offload-first candidate for 16 GB, but test host memory and Radeon execution rather than converting the claim into a guarantee. #307 |
| K39 / 17-18 | Runtime receipt: graph/model hashes, Comfy/nodes, OS/kernel/driver/ROCm/torch, cold/warm/switch timings, peaks, cleanup/outcomes/failure artifacts. | Extend existing observer; null until measured. Separate wait, execution, cold load, analysis, cleanup and two-pass costs. #302 |
| K40 / 18 | `job_resources.py` and Windows commit gate already exist; observer has no admission/recovery power. | Preserve listener-bound epochs, sample coverage, bounded retention, no rebind and best-effort non-authoritative observation. #302/#178 |
| K41 / 18-19 | Weight use, outputs, derivatives and hosted/embedded use differ by model. | Record these dimensions plus intended use. Preserve private-experiment decisions; reopen commercial review only when that purpose changes. #9/#144 |
| K42 / 19 | Effective suitability intersects checkpoint/adapter/source-reference/application constraints. | Provenance records support a reviewed decision; they are not an automatic legal verdict. Embeddings remain derived source artifacts. #144/#232 |
| K43 / 19-20 | Prompt Lab, Reference Intelligence, Workflow Studio, Experiment Lab and operator boundary have distinct responsibilities. | Adopt the ownership split, reconcile actual schema names, and route through existing coordinator/backend admission. ARCHITECTURE, #123 |
| K44 / 20 | Comfy API graphs support headless operation; MCP should be a thin validated client, not an installer or queue bypass. | Reuse existing SDK/CLI/MCP; no browser automation for generation, arbitrary paths, unreviewed node installation or embedded graph execution. #123 |

## Finite campaign, results and integration: pages 20-26

| ID / pages | Knowledge preserved | Adaptation and owner |
| --- | --- | --- |
| K45 / 20-21 | T01 T2I; T02 known character; T03 original identity; T04 target pose; T05 identity/outfit/style; T06 contact; T07 scoped edit; T08 sheet. | Stage behind the accepted pack. Each subscene, repair case and sheet view needs an explicit cell, not a hidden multiplication. QUALIFICATION, #10/#37/#446 |
| K46 / 21-22 | Fixed seeds, zero-generation preflight, one smoke, three-seed quality, six order permutations, three crop variants. | Preserve the proposed seeds as a separate campaign design. Existing 40/48-attempt plans retain their own seeds/caps; do not merge them arithmetically. #72/#446 |
| K47 / 21-22 | One infrastructure retry, no aesthetic reroll, every output retained; failures consume attempts. | Plan a global retry pool as well as per-cell limits. Uncertain submission is reconciliation-only, not retryable failure. #10/#257 |
| K48 / 22 | Composite candidate patch only within writable region, preserve original RGBA. | Compare decoded pixel bytes and metadata separately; specify transforms and mask support. An unchanged no-op can preserve pixels yet fail the intended edit. #245/#248 |
| K49 / 22-23 | Execution, slots, pixels, subject count, OCR and geometry are hard axes; identity/anatomy/style/composition/contact are visual axes. | Missing is unknown, not a pass. Review by a human or independent critic; proposing generator cannot solely approve itself. #37/#257 |
| K50 / 23 | Accepted/user choice separate from scores; record clarifications, text/reference/mask edits, attempts, operator time and resource cost. | Use failure-inclusive denominators and pack reuse as north star. Do not hide effort in a single aesthetic score. #313/#315 |
| K51 / 23-24 | Small architecture delta: existing library, KB, analysis, paired graphs, curated campaigns and observer. | New intake docs are a traceability layer only. First code extends existing guidance, not another qualification engine. #552 |
| K52 / 24-25 | Ordinary UI should ultimately present a small task-oriented portfolio; comparator shelves remain experimental. | Keep Create/Combine/Repair intent-led; exact model choice remains inspectable. Exposing three named models is a hypothesis, not a replacement of current UX. #118/#539 |
| K53 / 25 | Highest unresolved execution question is Qwen Q4+Lightning reliability on the 32 GB Windows host; otherwise bounded OmniGen2 offload comparison. | Resource-qualified challenger to current measured routes, not a prerequisite for completing the pack with existing tools. #77/#307 |
| K54 / 25-26 | Bibliography uses several mutable URLs; some sources mentioned in text lack independently pinned citations. | Store report hash/checkpoint and page locator; use dated primary-source checks, explicit gaps and change-triggered refresh. SOURCES, #144 |

## Coverage and limits

Every numbered page contributes to the map. The settings and LoRA tables are expanded in PORTFOLIO; the eight tasks, result axes and retry rules are expanded in QUALIFICATION. Proposed JSON shapes are treated as requirements, not imported as parallel stores. The report supplies no completed campaign, approved canonical character, measured Radeon OmniGen2 run or resolved OCR selection. This integration does not supply those missing results by inference.
