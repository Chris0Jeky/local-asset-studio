# Research and findings: consistent character production

Research snapshot: 12 September 2026. Source identifiers refer to [SOURCES.md](SOURCES.md). The original longer report, prompts, exhibits and bibliography remain byte-preserved in the pinned 71-file delivery; use the importer rather than treating generated crops as new art.

## Recommendation and its uncertainty

Use an accepted character reference bank; generate each needed panel against those accepted references; control pose/camera with compatible structural inputs where available; assess identity, costume, pose and rendering separately; repair only rejected regions; and assemble the card with ordinary graphics code. For substantial motion, retain an authored 2D puppet or 3D rig rather than repeatedly rediscovering the character through independent image generation.

This is an engineering hypothesis, not a measured claim that any local model matches GPT Images 2.5. The first two-route pilot measures feasibility of existing configurations. A separate experiment is needed to establish whether panel-by-panel production beats a one-shot sheet on accepted output per total effort.

## What the supplied sheets actually establish

All three originals are 1448 by 1086 RGBA PNGs; every alpha value is 255. They contain no transparent pixels. Standard and ornate each show four views, two portraits and seven action illustrations. Summer contains four large figure presentations and three portraits; its central presentations are expressive poses, not a strict side-view turnaround. The 33 rectangular crops are review regions, with original backgrounds/shadows and occasional adjacent artwork retained.

The images communicate coherent identity, attractive rendering, costume themes and readable silhouettes. They do not establish a consistent hidden garment construction, complete animation cycle, fixed pivot, timing, clean alpha, rig, or target-engine behaviour. Intentional outfit changes and chibi proportions are variants, not errors. A run drawing is a key-pose proposal, not a runnable animation.

Production targets differ:

| Target | Acceptance requirement |
|---|---|
| Concept card | Communicates design and mood convincingly. |
| Model sheet | Front/profile/back describe compatible construction and proportions. |
| Portrait library | Identity, costume, crop and lighting remain stable as expression changes. |
| Sprite clip | Shared canvas/pivot, timing, contacts, loop and final-size readability work together. |
| Rigged character | Layers/mesh, joints, occluded regions, deformation and native import behave correctly. |

The original sheets divide finite pixels among 13 illustrations. Enlarging small action crops cannot recover fine details that were never represented. Design simplified miniature costumes intentionally; do not let an evaluator demand portrait-level jewellery in tiny sprites.

## Why proprietary editing can look so coherent

OpenAI's September 8 Images 2.5 system card reports improved editing consistency and retention of layout/details. Public API/prompting documentation describes reference editing while retaining consistency limitations. These sources do not reveal enough of the internals to attribute the result to a particular attention mechanism, hidden 3D reconstruction or artistic self-correction loop. [S01-S03]

Qwen's technical report offers a public mechanism: reference images provide semantic visual-language conditioning and reconstructive VAE information, with reconstruction/editing training tasks. A strong reference editor therefore receives more information than a short caption can preserve. This is documented for Qwen, not a claim about OpenAI's architecture. [S04]

A shared canvas may help coordinate the repeated visual vocabulary within one generation; this is an interpretation of the examples, not proof of geometric consistency. Familiar-character priors are another possible confound. An output cannot prove training membership. Test an original identity with a distinctive asymmetric feature before generalizing from Aqua-like fan-art studies.

Reverse prompting should produce a constraint specification: observed identity, costume topology, rendering, what may change and what remains unknown. It cannot uniquely recover a hidden original prompt, checkpoint or seed from pixels.

## Task-oriented model shortlist

| Candidate | Useful role | Boundary |
|---|---|---|
| Qwen-Image-Edit-2511 | First reference preservation baseline. | Studio uses Q4 plus a matching four-step Lightning path; this is not the author's full reference configuration. [S05] |
| FLUX.2 Klein 4B | Compact reference-edit comparison. | Published NVIDIA resource claims are not a Radeon performance guarantee. Use exact installed bundle and terms. [S06-S07] |
| HiDream O1 full | Later quality candidate and subject-preserving layout/skeleton study. | Full and distilled variants have different roles; inspect the isolated installed bundle. [S08] |
| Animagine/WAI | Anime appearance baseline plus matching SDXL conditioning experiments. | IP-Adapter/ControlNet must match architecture, checkpoint and node contracts. [S11-S12] |
| Anima | Anime design/rendering baseline. | Different architecture from SDXL; do not transplant SDXL adapters. [S10] |
| Krea 2 | Art direction and selected expensive refinement. | Stylistic quality is not proof of identity preservation. Train/apply adapters only through documented family-specific paths. [S09] |
| MV-Adapter | Joint multi-view generation experiment. | Better viewpoint priors do not certify unseen geometry or a usable rig. [S13-S14] |

Compare resolved model/encoder/VAE/quantization/adapter/schedule/runtime bundles, not brand names. Equal steps or equal integer seeds across families do not equalize computation or align noise. Reproducibility depends on the surrounding runtime and hardware as well as random state. [S16]

The repository already has Qwen one/two/three-reference recipes and a FLUX reference-edit preset. In Qwen Atelier the first reference establishes aspect ratio, and labels such as identity/pose/style are semantic guidance, not a ControlNet. A square face as primary reference can be inappropriate for a full-body output. Preserve ordering and inspect actual preprocessing. The catalog, not a copied example, is the binding authority.

Do not add more models until this small pilot provides actionable evidence. No new model download or environment alteration is necessary to run the existing-route feasibility comparison once preflight is complete.

## Workflow structure and prompt design

Separate identity, costume, representation and rendering style. Establish neutral full-body and face anchors plus an explicitly reviewed back design. Long hair can hide fastenings; a model must propose those details and a reviewer must decide, rather than pretending they were visible. Establish a separate accepted chibi interpretation before miniature actions.

Every derivative returns to accepted canon, optionally supplemented by a reviewed relevant view. Avoid chains where each unreviewed derivative becomes the only reference for the next. New anchors enter canon through a versioned approval. Generate one panel at useful resolution, keeping labels and layout outside diffusion.

An editing brief should name the allowed change: one neutral profile, preserve face/hair/standard costume, pose reference only for orientation, full figure visible, no lettering or extra figures, unknown hidden construction remains a proposal. Compile that intent into each model's native dialect; do not paste a universal incantation into every checkpoint.

Appearance conditioning and structural control solve different problems. A pose skeleton can constrain joints while failing sleeves and hand/prop contact; a reference editor can preserve an outfit while placing the hand incorrectly. Matching appearance, geometry and localized acceptance tests must work together. [S11-S12]

A wrong sleeve should trigger a sleeve correction, not a new face. Exact outside-mask preservation requires deterministic compositing; prompt wording alone is not a pixel lock. The supplied utility uses explicit L-mask 0=source and 255=candidate, which is different from Comfy's inverse-alpha convention. Seams and the interior correction still need visual review.

## Personalization and advanced routes

Train a character LoRA only after reference-only editing is insufficient at useful volume. A proposed initial dataset is roughly 20-40 individually reviewed, diverse images with held-out views/poses, not three complete presentation sheets containing labels, multiple scales and outfits. Caption variable costume details and avoid flips that invert meaningful asymmetry. Keep identity and costume controllable; training can amplify a consistently wrong design.

Use exact family guidance: Klein Base is the documented fine-tuning target; Krea's RAW-to-Turbo adapter guidance is family-specific, not a universal transfer rule. [S07,S09]

MV-Adapter supplies jointly conditioned views, including anime derivative examples. The fal Qwen angle adapter offers 96 camera combinations, not 96 animation poses or guaranteed 3D reconstruction. InstantCharacter is a tuning-free personalization candidate with its own dependencies and resources. Qwen Image Layered produces editable RGBA decompositions, not automatic rigs or correct newly exposed surfaces. Sprite Sheet Diffusion addresses animation directly but reports limitations with details/accessories; it is research, not a guaranteed arbitrary-art-to-game pipeline. [S13-S15,S17-S19]

Qwen's 2026 RL report describes preservation-oriented rewards, including face identity in editing. That is a public example of explicit consistency optimization, not proof OpenAI uses the same recipe. [S21]

For repeated motion, compare an authored layered puppet or rigged 3D scene with deterministic fixed-camera rendering. A generative beautification pass can reintroduce drift; retain the untouched render as the baseline. Preserve logical canvases, anchors and timing through atlas packing. Actual Godot playback, not only a metadata file, completes acceptance. [S22]

## Evaluation, resources and rights

Use separate identity/costume/camera/contact/style checks with pass/fail/not_visible/uncertain and local explanations. Do not let a global aesthetic or embedding score conceal a wrong face, extra ornament or broken contact. Critical unknowns block promotion; an occluded optional detail should not become a false negative.

A local Qwen3-VL-4B helper is a candidate for specification extraction and rubric critique, not a proven quality oracle. Calibrate on genuine good/bad pairs, legitimate occlusion and representation changes, with held-out identities. Measure false acceptance and false rejection, abstention, latency and cleanup. Model changes invalidate the critic's calibration. [S20]

The current pilot is 2 routes x 3 tasks x 2 seeds, twelve total attempts including expensive warmups/failures/retries. It has zero extra repair allowance. Record elapsed and cleanup time, actual peak memory where available and rejected outputs; missing measurements remain null. A subsequent proposed comparison is 3 routes x 5 tasks x 3 seeds plus 3 globally budgeted repairs (48 maximum), but it requires a new approved plan and is not an automatic continuation. Same-seed comparisons within a route are useful; between-family seed equality is not a fair-compute claim.

Record source, code, checkpoint, adapter and output rights separately. Hashes do not establish creator authenticity. A permissive checkpoint does not grant rights to an established character. Anima's exact terms distinguish generated-output use from commercial hosting/embedding; do not infer rights from a badge or apply one model's restrictions to unrelated releases. Read current exact terms before use. [S10,S23]

Background removal must preserve white cloth, highlights and translucent fabric. Inspect matting over light and dark backgrounds; keep effects and ground shadows separate where appropriate. A shaded concept is not automatically a PBR material or mechanically correct prop. Choose the output representation before choosing the model.

## What the Studio still needs to prove

The existing architecture already has reference roles, Workspace lineage, Review Desk, repair handoffs, Prompt Lab, native exports and offline game-asset plans. #22 owns the missing end-to-end proof: original accepted design, portraits, authored idle, editable source, anchored atlas and real engine playback. #64 narrows the next experiment; #65 connects the offline contracts to the existing coordinator; #66 calibrates review and repair. These tasks are not completed by this research document.
