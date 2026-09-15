# Controlled adult illustration

Architecture, research and delivery programme for high-control, high-fidelity **adult-only sensual/anime illustration** in Local Asset Studio. Programme: [#403](https://github.com/Chris0Jeky/local-asset-studio/issues/403). Research freeze: 15 September 2026. The foundation source baseline is `b29205cfc95ca4e64d72ae38d53df30c83968997`; the prompt/source-intelligence continuation is based on `d73f67db48257e635def2170b67cefd6a3165098`, and the read-only discovery continuation is based on `88d777bca26ec36e248e2606834789e19cbece08`.

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

Run the standard-library-only offline gates before changing a programme manifest:

```console
python scripts/validate_adult_illustration.py
python scripts/validate_adult_illustration_intelligence.py
python -m unittest discover -s tests -p "test_adult_illustration*.py" -v
```

The foundation validator checks authority, adult/content declarations, route evidence states, control and benchmark references, zero authorized candidate caps, adapter sweep bounds and duplicate IDs. The intelligence validator checks prompt dialect isolation, vocabulary provenance and collisions, technique availability, provider-specific source identity, immutable revisions and hash-pinned file selection. Neither inspects installed models, calls a provider, downloads bytes or submits generation.

Development agents should also read [`agent-skills/adult-illustration/SKILL.md`](../../agent-skills/adult-illustration/SKILL.md).

## Read by task

| Need | Start here |
| --- | --- |
| Product and component boundaries | [Architecture](ARCHITECTURE.md) |
| Independent creative controls | [Control ontology](CONTROL-ONTOLOGY.md) |
| Model, adapter, geometry, training and finishing landscape | [Model and technique landscape](MODEL-AND-TECHNIQUE-LANDSCAPE.md) |
| Prompt dialects, vocabulary and analyzers | [Prompt and tag intelligence](PROMPT-AND-TAG-INTELLIGENCE.md) |
| Hugging Face/Civitai provenance and acquisition handoff | [Source intake](SOURCE-INTAKE.md) |
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
5. **A4 — genre portfolio:** transparent packs for editorial, fashion, swim, hot-spring, lounge, fantasy, sci-fi, street, comedy, action, manga, sheets and repair.
6. **A5 — training and finishing:** one justified isolated LoRA experiment and one accepted repair/upscale/export chain.
7. **A6 — shared operation:** revisioned UI/CLI/SDK/MCP parity with explicit approval and durable evidence.

These are evidence gates, not dates.

## Adult/content boundary

Every programme intent must declare unambiguous adult subject status through reviewed user/canon metadata. A vision model or visual appearance cannot establish age or consent. Ambiguous or youthful identity is refused instead of “fixed” through negative prompting. Multi-adult intimate test cases additionally require an explicit consent-context declaration. Public fixtures are synthetic and non-explicit; broader content classes remain route-specific reviewed declarations.

## Next useful slices

1. Merge/review the stacked foundation, validator, intent-projection and offline CLI PRs in order.
2. Use the #435 read-only catalogs and zero-authority comparison plans to choose exact follow-up evidence work; do not treat a plan as authorization.
3. Build a fake-transport provider snapshot adapter under #433; do not download anything.
4. Pin one taxonomy source and implement one route profile at a time under #432.
5. Begin runtime work only through a finite comparison of existing routes plus the small Anima/SDXL/Qwen shortlist under #405/#409, using the existing coordinator and exact evidence rules.
