# Role-based portfolio, exact configurations and prompt knowledge

This is a decision matrix derived from report pp. 1-15 and 18-25, reconciled with the inspected repository. It is **not another model registry**. Actual files, source revisions, hashes and terms remain in `models/library.json`; graphs and controls remain in the catalog/API twins; compiler knowledge remains in the current Prompt Lab/KB owners. All execution claims below refer to retained repository records, not a run performed during this integration.

## Portfolio disposition

| Route/configuration | Report's proposed role | Adapted position and next evidence |
| --- | --- | --- |
| Anima Aesthetic 1.1 | Anime-first T2I | Keep a strong existing starting route, not a universal winner. Separate the local schedule from family-card guidance and compare exact task outputs after review. |
| Anima Base 1.0 | Training/flexibility baseline | Already present with actual atelier execution, not merely a not-yet-installed training candidate. Keep Base identity separate from the early Aesthetic-substituted stack probes. No LoRA training campaign is launched here. |
| Anima Turbo 1.1 | Fast audition | Unresolved exact-version profile. Do not substitute the existing **Base 1.0 + turbo LoRA v0.2** recipe as proof of standalone Turbo 1.1. |
| Animagine XL 4.0 Opt | Auditable anime baseline and SDXL controls | Installed-byte manifest identity matches the paper. Useful controlled challenger, especially for exact prompt grammar and repair. Installed or architecture-compatible is not owner-accepted. |
| SDXL IP-Adapter + DWPose/OpenPose | Separate appearance and target geometry | Retain as a structured comparator. A style board can mix identity/outfit/palette; corrected pose is a distinct artifact. Match base, encoder, adapter and ControlNet variants. |
| Qwen Image Edit 2511 Q4_K_M + Lightning 4-step | Identity/outfit/style/native editing | High-priority exact runtime qualification under #77. Include quantizer, accelerator, multimodal encoder, VAE, Comfy nodes, sources and cleanup in the identity. Do not label an unidentified Qwen load failure as evidence for this exact route. |
| Qwen Image Edit 2511 native BF16 | Native model baseline | A separate, currently unqualified local configuration; source settings cannot be copied into the quantized Lightning graph. Not a required download. |
| Current Klein 4B/9B Combine, depth, Copy Pose and replace-character | Not adequately represented in the report portfolio | Preserve current measured baselines. Test pose transfer and identity restoration both individually and as a two-pass journey. Include waiting, intermediate drift and correction effort, not just the final attractive image. |
| Current WAI masked/detail repair | Measured repair baseline | Retain failures and preservation evidence. Compare Animagine in the existing compositor only after a concrete gap, not because the report recommends a cleaner source lineage. |
| OmniGen2 with CPU offload | Native multi-reference comparator | Conditional fallback when current routes leave a measured gap or Qwen runtime fails its bounded trial. The upstream CUDA memory claim is not Radeon evidence; offload may shift pressure into host memory. |
| FLUX.1 Kontext dev | Scoped editing comparator | Optional, purpose-sensitive terms and access review. Not the same architecture/configuration as shipped FLUX.2 Klein. No new default backend. |
| Illustrious XL v2 Stable | Ecosystem bridge | Exact source-profile gap retained. The Civitai build/hash prefix does not authenticate official Hugging Face bytes. Do not silently reuse a newer Illustrious guide. |
| NoobAI XL 1.1 EPS | Private/hobby baseline, not general commercial route | Retain for the owner's private experimentation. Its terms constraints and exact EPS identity remain recorded; neither art quality nor owner preference overwrites them. |
| NoobAI v-pred | Separate community comparator | Keep separate prediction/schedule/adapters; source pins incomplete. No new acquisition in the first wave. |
| Pony V6 | Controlled ecosystem baseline | Retain exact historical results, including poor task output. One portrait is not evidence for a global rejection, and Animagine's grammar is not Pony's grammar. |

Ordinary UI should begin with a task such as **Create anime**, **Combine references**, **Control a pose** or **Repair one area**, then explain a small eligible set. The paper's final three-model picker is a useful simplification hypothesis, not a mandate to remove shipped Klein routes or their owner feedback.

## Exact identities already reconciled

The five complete paper checkpoint SHA-256 values match the corresponding **manifest declarations** at integration checkpoint `6cdf6ab`. This is a comparison of repository data, not hashing files on the workstation:

| Paper entry | Current canonical asset ID |
| --- | --- |
| Anima Aesthetic v1.1 | `anima-aesthetic` |
| Animagine XL 4.0 Opt | `sdxl-animagine-40-opt` |
| NoobAI XL 1.1 EPS | `sdxl-noobai-v11` |
| Pony Diffusion V6 | `sdxl-pony-v6` |
| Qwen Image Edit 2511 Q4_K_M | `qwen-image-edit-2511-q4-gguf` |

Other relevant existing IDs include `anima-base-v1-0`, `anima-turbo-lora-v0-2`, `qwen-edit-2511-lightning-4step`, `qwen25-vl-7b-fp8-encoder`, `vae-qwen-image` and `qwen-edit-2511-multiple-angles`. Read their current records rather than copying hashes into a second operational registry. Some entries have a hash without an upstream commit revision; record that gap rather than treating a filename, `main`, model size or registry family label as source authentication.

A route identity is the **effective component set plus graph/configuration**, not just a checkpoint ID. Q4 weights, FP8 encoder, Lightning adapter and VAE precision are different dimensions. `configuration_kind` may require multiple attributes because a quantized model can also use a distilled adapter; a single exclusive `native|quantised|distilled` enum from the report is too lossy for this combination.

## Prompt profiles: preserve source scope

These are requirements for #34/#144, not executable settings newly adopted by this document. `null` means the source did not establish the value or the native pipeline owns it. Do not convert it into zero or a guessed default. Public author recommendations, local authored settings and local execution observations need separate provenance.

| Exact target | Grammar and positive/negative treatment | Sampling knowledge and its boundary |
| --- | --- | --- |
| Anima Base 1.0 | Mixed prose/lowercase tags; the paper's Base/general prefix includes `masterpiece, best quality, score_7, safe`; family negative includes low-quality and low-score terms. | Family card: 30-50 steps, CFG 4-5, er_sde and documented alternatives. Paper's 40/4.5 choice is a midpoint proposal; its `normal` scheduler is not established merely by the sampler recommendation. Existing local Base stacks have separate settings/receipts. |
| Anima Aesthetic 1.1 | Prose plus selected tags; do not apply Base score_* tokens to positive **or negative** text. Do not silently strip owner-authored tags: show the conflict and require reviewed rewriting. | Existing local route: Euler/simple, 30, CFG 4, 768x1152. Family-card Aesthetic advice is not a completed v1.1 parameter reconciliation. |
| Anima Turbo 1.1 | Mixed prose/tags, not automatic Base/Aesthetic inheritance. | Report proposes 10 within 8-12, CFG 1, Euler, scheduler unspecified; exact-version source gap remains. |
| Animagine 4.0 Opt | Subject count, known character, series, rating, description, then `masterpiece, high score, great score, absurdres`. Original characters leave franchise fields empty. Negative terms stay model-specific. | Author card supports Euler A, approximately 25-28 steps with 28 recommended, CFG around 5 and listed aspect buckets. `normal` and alternative sweep schedulers need local/profile attribution rather than a blanket “all values source-native” label. |
| NoobAI 1.1 EPS | Quality/year/rating prefix such as `masterpiece, best quality, newest, absurdres, highres, safe`, then reviewed subject tags. | Report/source: Euler A, 25-30, CFG 5-6, SDXL-scale buckets. Current broader local sweep values must not all be relabelled source recommendations. |
| Pony V6 | Pony score/source/rating prefix and clip skip 2; its negative stays separate. | Repository baseline Euler A/normal, 30, CFG 6, 1024 square. The report did not independently freeze the upstream profile. |
| Qwen 2511 native BF16 | Explicit ordinal/role edit language; source example uses a single blank-space negative. Empty string, whitespace and absent channel are not assumed interchangeable in compiler tests. | Source example: 40, `true_cfg_scale=4`, `guidance_scale=1`. Sampler/scheduler pipeline-owned unless a pinned workflow establishes them. |
| Qwen 2511 Q4 + Lightning | Same reviewed task semantics do not imply equivalent conditioning or sampling behaviour. Preserve actual three-slot graph contract and effective source order. | Existing Comfy route 4, CFG 1, Euler/simple; not evidence for native BF16 scheduling. |
| OmniGen2 | Detailed natural language with first/second-image roles; preserve reference transforms. | Report: 50 steps/Euler; edit image guidance 1.2-2.0 differs from in-context 2.5-3.0. Native Radeon performance unknown. |
| Kontext dev | Concise edit instruction; source image remains a native input. | Report/source example guidance 2.5; leave unpinned steps/scheduler unspecified. |
| Illustrious v2 Stable | Exact first-party frozen compiler profile unresolved. | Keep blocked for source-derived compiler promotion, not globally forbidden for explicitly bounded experimentation. |

The current `research/prompt-studio/profiles.json` still includes generic recipe associations: the descriptive SDXL profile lists `anima-portrait`, and the Animagine tag profile lists WAI/Pony/Noob recipes. These are existing software baselines, **not evidence of model-specific dialect equivalence**. Migration must preserve saved profile revisions and produce explicit diagnostics for unsupported or unused intent.

The current Anima family sweep also offers eight steps with a textual “only with turbo LoRA” condition. The family planner does not by itself attest that accelerator. Move conditional schedules into exact resource-qualified advice or implement a tested conditional projection; do not mistake explanatory prose for enforced prerequisites.

## Controls, reference roles and leakage

SDXL-family LoRAs, IP-Adapters and ControlNets must match the intended architecture and exact base ecosystem. Encoder and adapter variants matter: appearance, face, style and composition are not interchangeable. Anima, Qwen, OmniGen2 and FLUX need their own compatible mechanisms. DWPose, depth, normal, line-art and segmentation extractors can produce reusable artifacts even when a chosen generator has no corresponding conditioning model.

Store identity/outfit/style/pose/composition/background intent separately from the effective generator slots. The current schema already uses **costume**; introducing **outfit** requires a deliberate compatibility mapping, not silently renaming saved records. A style board's averaged embeddings may leak subject, clothing and palette; a pose image may leak a silhouette's heels. Preserve crop/resize/padding, coordinate frame, color/range convention, encoder identity, source hash and per-subject ownership.

Qwen's documented multi-image example proves multiple inputs, not unlimited inputs. The Studio's three-reference recipe contract is a separate implementation fact. Reference Intelligence's four-image analysis limit and CreativeIntent's reference-record budget do not expand that graph. Unsupported roles or excess sources must be shown and resolved, not silently dropped or averaged.

## LoRA knowledge retained without a second inventory

Report pp. 14-15 records the following precise source-version leads. Canonical library entries remain the operational authority for declarations; creator and reference rights remain separate.

| Candidate | Report model/version | Role and qualification boundary |
| --- | --- | --- |
| Mishima Kurone LN style | 1523528 / 1723753 | `mishimakurone`; Illustrious-family visual comparison, not an artist authorization. |
| Glossy Anime Style | 1364837 / 1541970 | `glossy_anime_style`; Illustrious-only first comparison; inspect palette/identity leakage. |
| Detail Enhancer IL v2 | 1450571 / 1983243 | No required trigger reported; detail-only axis, not an identity or anatomy guarantee. |
| Konosuba Fantastic Days style | 1610833 / 1824928 | Optional listing trigger; known-style benchmark, not permission for franchise commercialization. |
| Anima-native artist style | Existing Anima library record; report full hash maps to `anima-koukouya-v2-step2500` | Separate Anima adapter ecosystem, with exact selected strength/base recorded. |
| Noob IP-Adapter Mark 1 | HF-derived, locally unverified in the report | Not a first-wave addition; base terms and exact adapter evidence still required. |
| Noob v-pred | 833294 / 1190596 | Distinct prediction route; reported hash prefix is not a full verified local pin. |
| Illustrious v2 community build | 1489531 / 1684946 | `C2A1A3EA…` is a source-review prefix, not authentication of official HF bytes. |

Do not infer current flags from this historical table. Match full hashes, exact version and trigger sources; keep incompatible or uncertain candidates out of automatic recipe compilation.

## Intended use and terms are a separate axis

Report pp. 18-19 distinguishes **model-weight use, generated outputs, derivatives/training, and hosted/embedded use**. Preserve that decomposition. The author-described output permissions for Anima and Kontext differ from their model-use terms; Noob's source includes generated-product commercialization restrictions; Qwen and OmniGen2 have different model-side licensing profiles. None of those descriptions clears an input image, character, artist-style adapter or redistributable embedding.

The owner recorded private experimentation with no commercial plan in HUMAN_TODO q-26, and separately answered the Klein 9B private-use question. Do not reopen that same decision merely because a paper has a commercial portfolio column. Do retain per-file records and surface a fresh review before selling assets, offering hosted inference, embedding/distributing weights or changing training/redistribution purpose. This is an evidence and intended-use workflow, not an automated legal verdict.
