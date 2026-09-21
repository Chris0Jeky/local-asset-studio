# Controlled adult illustration

Architecture, research and delivery programme for high-control, high-fidelity **adult-only sensual/anime illustration** in Local Asset Studio. Programme: [#403](https://github.com/Chris0Jeky/local-asset-studio/issues/403). Research freeze: 15 September 2026. The foundation source baseline is `b29205cfc95ca4e64d72ae38d53df30c83968997`; the prompt/source-intelligence continuation is based on `d73f67db48257e635def2170b67cefd6a3165098`, the read-only discovery continuation is based on `88d777bca26ec36e248e2606834789e19cbece08`, and the immutable taxonomy intake is based on `e2d6970a5852c923738892714c1b75567a018b44`.

The objective is not a single “best” checkpoint or style LoRA. The Studio should turn a short brief and optional references into an inspectable plan that separates:

- **semantics** — subjects, wardrobe, expression, action, scene and relationships;
- **geometry** — pose, silhouette, camera, depth, line, regions and contacts;
- **appearance** — identity, outfit, body design, palette, material and rendering style;
- **pixel authority** — masks, protected regions, compositing and reversible native edits;
- **evidence** — exact route, resources, failures, review, acceptance and rights state.

Text describes. Geometry constrains. References and adapters preserve or modify appearance. Masks determine where an edit may write. No one mechanism should impersonate all four.

## Current boundary

This foundation is non-executing:

- no model, LoRA, custom node or package is downloaded;
- no ComfyUI graph is submitted;
- no generation or training allowance is created;
- no private reference or artwork is committed;
- no route is called installed, 16 GB compatible, unrestricted or promoted;
- no planning, taxonomy or prompt-projection record grants runtime authority.

It extends the existing anime atelier (#14), Prompt Lab, Reference Intelligence, Workflow Studio, Production, character consistency and Repair Studio. It does not add another model registry, workflow store, queue, executor, review database or painting canvas.

## Validate the foundation

Run the standard-library-only offline gates before changing a programme manifest, deterministic prompt profile or taxonomy review:

```console
python scripts/validate_adult_illustration.py
python scripts/validate_adult_illustration_intelligence.py
python scripts/studio_adult_illustration_research.py programme-status
python scripts/studio_adult_illustration_prompt.py profiles
python scripts/studio_adult_illustration_taxonomy.py source
python -m unittest discover -s tests -p "test_adult_illustration*.py" -v
```

The foundation validator checks authority, adult/content declarations, route evidence states, control and benchmark references, zero authorized candidate caps, adapter sweep bounds and duplicate IDs. The intelligence validator checks prompt dialect isolation, vocabulary provenance and collisions, technique availability, provider-specific source identity, immutable revisions and hash-pinned file selection. The prompt compiler adds deterministic route-specific text while keeping non-prompt controls unresolved. The taxonomy intake separates the exact upstream CSV identity from a finite Studio review and grants no blanket compilation authority. None inspects installed models, calls a provider, downloads bytes or submits generation.

Development agents should also read [`agent-skills/adult-illustration/SKILL.md`](../../agent-skills/adult-illustration/SKILL.md).

## Read by task

| Need | Start here |
| --- | --- |
| Product and component boundaries | [Architecture](ARCHITECTURE.md) |
| Independent creative controls | [Control ontology](CONTROL-ONTOLOGY.md) |
| Practical art direction, route stages, LoRA arsenal and genres | [Controlled art direction](CONTROLLED-ART-DIRECTION.md) |
| Model, adapter, geometry, training and finishing landscape | [Model and technique landscape](MODEL-AND-TECHNIQUE-LANDSCAPE.md) |
| Prompt dialects, vocabulary and analyzers | [Prompt and tag intelligence](PROMPT-AND-TAG-INTELLIGENCE.md) |
| Deterministic Animagine/Anima/Qwen profile compiler | [Prompt profiles](PROMPT-PROFILES.md) |
| Immutable anime taxonomy source and finite review | [Taxonomy intake](TAXONOMY-INTAKE.md) |
| Inspect compiled terms against retained source membership | [Taxonomy membership inspection](TAXONOMY-MEMBERSHIP-INSPECTION.md) |
| Hugging Face/Civitai provenance and acquisition handoff | [Source intake](SOURCE-INTAKE.md) |
| Bounded provider-response snapshot adapters | [Source snapshots](SOURCE-SNAPSHOTS.md) |
| Operational candidates and research watchlist | [Technique portfolio](TECHNIQUE-PORTFOLIO.md) |
| Intelligence delivery sequence | [Intelligence implementation plan](INTELLIGENCE-IMPLEMENTATION-PLAN.md) |
| Finite qualification and acceptance | [Evaluation](EVALUATION.md) |
| Adult intent and Prompt Lab projection | [Intent contract](INTENT-CONTRACT.md) |
| Human/agent command and authority contract | [Agent contract](AGENT-CONTRACT.md) |
| Read-only catalogs and comparison plans | [Research discovery](RESEARCH-DISCOVERY.md) |
| Delivery order and issue ownership | [Implementation plan](IMPLEMENTATION-PLAN.md) |
| Primary-source ledger | [Sources](SOURCES.md) |
| Machine-readable navigation | [`research/adult-illustration/programme.json`](../../research/adult-illustration/programme.json) |
| Control vocabulary | [`control-ontology.json`](../../research/adult-illustration/control-ontology.json) |
| Route research candidates | [`route-candidates.json`](../../research/adult-illustration/route-candidates.json) |
| Prompt dialect candidates | [`prompt-dialects.json`](../../research/adult-illustration/prompt-dialects.json) |
| Pinned first prompt profiles and proof vocabulary | [`prompt-profile-vocabulary.json`](../../research/adult-illustration/prompt-profile-vocabulary.json) |
| Immutable taxonomy source contract | [`taxonomy-source.json`](../../research/adult-illustration/taxonomy-source.json) |
| Finite Studio taxonomy review | [`taxonomy-review.json`](../../research/adult-illustration/taxonomy-review.json) |
| Tag-vocabulary contract | [`tag-vocabulary-example.json`](../../research/adult-illustration/tag-vocabulary-example.json) |
| Technique candidates/watchlist | [`technique-candidates.json`](../../research/adult-illustration/technique-candidates.json) |
| Source-intake contract examples | [`source-intake-example.json`](../../research/adult-illustration/source-intake-example.json) |
| Held-out task declarations | [`benchmark-corpus.json`](../../research/adult-illustration/benchmark-corpus.json) |
| Composable genre starts | [`genre-packs.json`](../../research/adult-illustration/genre-packs.json) |
| Adapter qualification template | [`lora-qualification-example.json`](../../research/adult-illustration/lora-qualification-example.json) |

## Programme gates

1. **A0 — contracts:** intent/control ontology, source-reviewed candidates, provider/source provenance, prompt dialect/vocabulary contracts, finite corpus, validators and agent runbook.
2. **A1 — controlled vertical slice:** one approved adult original character; authored pose and silhouette; role-separated appearance; fast-preview versus quality comparison.
3. **A2 — modular controls:** qualified identity, outfit, body/proportion, expression, style/material and acceleration adapters plus authored geometry.
4. **A3 — multi-reference and multi-subject:** explicit slot ownership, regional plans and one accepted two-adult contact/prop scene.
5. **A4 — genre portfolio:** transparent packs for editorial, fashion, swim, hot-spring, lounge, athletic/stretch, fantasy, sci-fi, street, comedy, action, manga, sheets and repair.
6. **A5 — training and finishing:** one justified isolated LoRA experiment and one accepted repair/upscale/export chain.
7. **A6 — shared operation:** revisioned UI/CLI/SDK/MCP parity with explicit approval and durable evidence.

These are evidence gates, not dates.

## Adult/content boundary

Every programme intent must declare unambiguous adult subject status through reviewed user/canon metadata. A vision model or visual appearance cannot establish age or consent. Ambiguous or youthful identity is refused instead of “fixed” through negative prompting. Multi-adult intimate test cases additionally require an explicit consent-context declaration. Public fixtures are synthetic and non-explicit; broader content classes remain route-specific reviewed declarations.

## Next useful slices

1. Review/merge the stacked foundation, validator, intent-projection, offline CLI, intelligence, discovery and source-snapshot PRs in order.
2. Review the #437 immutable taxonomy, taxonomy-aware compiler and optional membership-inspection slices in stack order. Pin exact installed tokenizers before exact token-count claims.
3. Qualify unchanged/manual/taxonomy-assisted prompts under #37/#409; software tests alone do not prove artistic benefit.
4. Use the #435 read-only catalogs and zero-authority comparison plans to choose exact evidence work; do not treat a plan as authorization.
5. Reconcile installed routes and execute the finite Anima/SDXL/Qwen campaign only through #405/#439 and the existing coordinator.
6. Qualify LoRA/slider intervals and interference under #406/#440 before exposing continuous Studio controls.
7. Build the first transparent Guided genre journey under #410 from promoted modules rather than an opaque mega-prompt.
