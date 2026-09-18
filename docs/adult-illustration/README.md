# Controlled adult illustration

Architecture, research and delivery programme for high-control, high-fidelity **adult-only sensual/anime illustration** in Local Asset Studio. Programme: [#403](https://github.com/Chris0Jeky/local-asset-studio/issues/403). Research freeze: 15 September 2026. The foundation source baseline is `b29205cfc95ca4e64d72ae38d53df30c83968997`; the prompt/source-intelligence research was prepared against `d73f67db48257e635def2170b67cefd6a3165098`, and the read-only discovery continuation is based on `88d777bca26ec36e248e2606834789e19cbece08`.

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
- no planning record grants runtime authority.

It extends the existing anime atelier (#14), Prompt Lab, Reference Intelligence, Workflow Studio, Production, character consistency and Repair Studio. It does not add another model registry, workflow store, queue, executor, review database or painting canvas.

## Validate the foundation

Run the standard-library-only offline gates before changing a programme manifest or intent/projection contract:

```console
python scripts/validate_adult_illustration.py
python scripts/validate_adult_illustration_intelligence.py
python scripts/studio_adult_illustration_research.py programme-status
python scripts/studio_adult_illustration_research.py catalogs
python -m unittest discover -s tests -p "test_adult_illustration*.py" -v
```

The foundation validator checks authority, adult/content declarations, route evidence states, control and benchmark references, zero authorized candidate caps, synthetic adapter non-promotion, finite adapter sweeps, pinned issue ownership and duplicate IDs. The programme owner map pins prompt-dialect work to #432, source-intake work to #433 and read-only discovery to #435 in addition to the core #404–#413 sequence; missing, unknown or reassigned owners fail closed. The intelligence validator additionally checks prompt-dialect isolation, verified immutable vocabulary provenance, provider URL/ID agreement, unique source file paths, technique availability and hash-pinned selection. The intent and CLI suites cover total bounded projection, exclusive-create evidence, duplicate-key rejection, tamper detection and structured zero-authority errors. Research discovery rejects oversized manifests before allocating their contents and retains unresolved immutable technique revisions in comparison plans. None inspects installed models, contacts a provider, downloads bytes, binds a route or submits generation.

Development agents should also read [`agent-skills/adult-illustration/SKILL.md`](../../agent-skills/adult-illustration/SKILL.md).

## Read by task

| Need | Start here |
| --- | --- |
| Product and component boundaries | [Architecture](ARCHITECTURE.md) |
| Independent creative controls | [Control ontology](CONTROL-ONTOLOGY.md) |
| Reviewed source intent and Prompt Lab projection | [Intent contract](INTENT-CONTRACT.md) |
| Offline validate/project commands | [Intent contract: Offline CLI](INTENT-CONTRACT.md#offline-cli) |
| Prompt dialects, vocabulary and analyzers | [Prompt and tag intelligence](PROMPT-AND-TAG-INTELLIGENCE.md) |
| Hugging Face/Civitai provenance and acquisition handoff | [Source intake](SOURCE-INTAKE.md) |
| Operational candidates and research watchlist | [Technique portfolio](TECHNIQUE-PORTFOLIO.md) |
| Intelligence delivery sequence | [Intelligence implementation plan](INTELLIGENCE-IMPLEMENTATION-PLAN.md) |
| Model, adapter, geometry, training and finishing landscape | [Model and technique landscape](MODEL-AND-TECHNIQUE-LANDSCAPE.md) |
| Finite qualification and acceptance | [Evaluation](EVALUATION.md) |
| Human/agent command and authority contract | [Agent contract](AGENT-CONTRACT.md) |
| Read-only catalogs and comparison plans | [Research discovery](RESEARCH-DISCOVERY.md) |
| Delivery order and issue ownership | [Implementation plan](IMPLEMENTATION-PLAN.md) |
| Primary-source ledger | [Sources](SOURCES.md) |
| Machine-readable navigation | [`research/adult-illustration/programme.json`](../../research/adult-illustration/programme.json) |
| Control vocabulary | [`control-ontology.json`](../../research/adult-illustration/control-ontology.json) |
| Route research candidates | [`route-candidates.json`](../../research/adult-illustration/route-candidates.json) |
| Prompt dialect candidates | [`prompt-dialects.json`](../../research/adult-illustration/prompt-dialects.json) |
| Tag-vocabulary contract | [`tag-vocabulary-example.json`](../../research/adult-illustration/tag-vocabulary-example.json) |
| Technique candidates/watchlist | [`technique-candidates.json`](../../research/adult-illustration/technique-candidates.json) |
| Source-intake contract examples | [`source-intake-example.json`](../../research/adult-illustration/source-intake-example.json) |
| Held-out task declarations | [`benchmark-corpus.json`](../../research/adult-illustration/benchmark-corpus.json) |
| Composable genre starts | [`genre-packs.json`](../../research/adult-illustration/genre-packs.json) |
| Adapter qualification template | [`lora-qualification-example.json`](../../research/adult-illustration/lora-qualification-example.json) |

## Programme gates

1. **A0 — contracts:** intent/control ontology, source-evidence candidates, provider/source provenance, prompt-dialect and vocabulary contracts, 21-case finite corpus, validators and agent runbook.
2. **A1 — controlled vertical slice:** one approved adult original character; authored pose and silhouette; role-separated appearance; fast-preview versus quality comparison.
3. **A2 — modular controls:** qualified identity, outfit, body/proportion, expression, style/material and acceleration adapters plus authored geometry.
4. **A3 — multi-reference and multi-subject:** explicit slot ownership, regional plans and one accepted two-adult contact/prop scene.
5. **A4 — genre portfolio:** transparent packs for editorial, fashion, swim, hot-spring, lounge, fantasy, sci-fi, street, comedy, action, manga, sheets and repair.
6. **A5 — training and finishing:** one justified isolated LoRA experiment and one accepted repair/upscale/export chain.
7. **A6 — shared operation:** revisioned UI/CLI/SDK/MCP parity with explicit approval and durable evidence.

These are evidence gates, not dates.

## Adult/content boundary

Every programme intent must declare unambiguous adult subject status through reviewed user/canon metadata. A vision model or visual appearance cannot establish age or consent. Ambiguous or youthful identity is refused instead of “fixed” through negative prompting. Multi-adult intimate test cases additionally require an explicit consent-context declaration. Public fixtures are synthetic and non-explicit; broader content classes remain route-specific reviewed declarations.

## Next useful slices

1. Review the stacked foundation, validator, intent-projection, offline CLI and intelligence PRs in order.
2. Use the #435 read-only catalogs and zero-authority comparison plans to choose exact follow-up evidence work; do not treat a plan as authorization.
3. Build a fake-transport provider snapshot adapter under #433; do not download anything.
4. Pin one taxonomy source and implement one route profile at a time under #432.
5. Begin runtime work only through a finite comparison of existing routes under #405/#409, using the existing coordinator and exact evidence rules.
