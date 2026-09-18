# Controlled adult illustration

Architecture, research and delivery programme for high-control, high-fidelity **adult-only sensual/anime illustration** in Local Asset Studio. Programme: [#403](https://github.com/Chris0Jeky/local-asset-studio/issues/403). Research freeze: 15 September 2026. The source baseline is `b29205cfc95ca4e64d72ae38d53df30c83968997`.

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
python -m unittest discover -s tests -p "test_adult_illustration.py" -v
python -m unittest discover -s tests -p "test_adult_illustration_intent.py" -v
python -m unittest discover -s tests -p "test_adult_illustration_cli.py" -v
```

The manifest validator checks authority, adult/content declarations, route evidence states, control and benchmark references, zero authorized candidate caps, synthetic adapter non-promotion, finite adapter sweeps, pinned issue ownership and duplicate IDs. The intent and CLI suites additionally cover total bounded projection, exclusive-create evidence, duplicate-key rejection, tamper detection, structured zero-authority errors, and round-tripping projections above the source intent's 64 KiB budget. None inspects installed models, calls the network, binds a route or submits generation.

Development agents should also read [`agent-skills/adult-illustration/SKILL.md`](../../agent-skills/adult-illustration/SKILL.md).

## Read by task

| Need | Start here |
| --- | --- |
| Product and component boundaries | [Architecture](ARCHITECTURE.md) |
| Independent creative controls | [Control ontology](CONTROL-ONTOLOGY.md) |
| Reviewed source intent and Prompt Lab projection | [Intent contract](INTENT-CONTRACT.md) |
| Offline validate/project commands | [Intent contract: Offline CLI](INTENT-CONTRACT.md#offline-cli) |
| Model, adapter, geometry, training and finishing landscape | [Model and technique landscape](MODEL-AND-TECHNIQUE-LANDSCAPE.md) |
| Finite qualification and acceptance | [Evaluation](EVALUATION.md) |
| Human/agent command and authority contract | [Agent contract](AGENT-CONTRACT.md) |
| Delivery order and issue ownership | [Implementation plan](IMPLEMENTATION-PLAN.md) |
| Primary-source ledger | [Sources](SOURCES.md) |
| Machine-readable navigation | [`research/adult-illustration/programme.json`](../../research/adult-illustration/programme.json) |
| Control vocabulary | [`control-ontology.json`](../../research/adult-illustration/control-ontology.json) |
| Route research candidates | [`route-candidates.json`](../../research/adult-illustration/route-candidates.json) |
| Held-out task declarations | [`benchmark-corpus.json`](../../research/adult-illustration/benchmark-corpus.json) |
| Composable genre starts | [`genre-packs.json`](../../research/adult-illustration/genre-packs.json) |
| Adapter qualification template | [`lora-qualification-example.json`](../../research/adult-illustration/lora-qualification-example.json) |

## Programme gates

1. **A0 — contracts:** intent/control ontology, source-evidence candidates, 21-case finite corpus, validator and agent runbook.
2. **A1 — controlled vertical slice:** one approved adult original character; authored pose and silhouette; role-separated appearance; fast-preview versus quality comparison.
3. **A2 — modular controls:** qualified identity, outfit, body/proportion, expression, style/material and acceleration adapters plus authored geometry.
4. **A3 — multi-reference and multi-subject:** explicit slot ownership, regional plans and one accepted two-adult contact/prop scene.
5. **A4 — genre portfolio:** transparent packs for editorial, fashion, swim, hot-spring, lounge, fantasy, sci-fi, street, comedy, action, manga, sheets and repair.
6. **A5 — training and finishing:** one justified isolated LoRA experiment and one accepted repair/upscale/export chain.
7. **A6 — shared operation:** revisioned UI/CLI/SDK/MCP parity with explicit approval and durable evidence.

These are evidence gates, not dates.

## Adult/content boundary

Every programme intent must declare unambiguous adult subject status through reviewed user/canon metadata. A vision model or visual appearance cannot establish age or consent. Ambiguous or youthful identity is refused instead of “fixed” through negative prompting. Multi-adult intimate test cases additionally require an explicit consent-context declaration. Public fixtures are synthetic and non-explicit; broader content classes remain route-specific reviewed declarations.

## Next useful slice

Map retained intent projections onto existing revisioned Prompt/Setup commands, then bind exact route capabilities under #405/#407/#408. Use the existing coordinator and exact evidence rules; validation and projection artifacts do not authorize downloads or execution.
