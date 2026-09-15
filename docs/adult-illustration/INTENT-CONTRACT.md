# Adult illustration intent and CreativeIntent projection

Issue: #404. This is a pure, non-persistent contract. It gives the controlled adult-illustration programme a strict source intent without replacing Prompt Lab's existing `CreativeIntent`.

## Boundary

`studio_prompt.adult_illustration` validates a reviewed adult-only illustration intent and projects the semantics that the existing Prompt Lab understands. It performs no file reads, model discovery, route selection, graph binding, inference, persistence or generation.

The projection deliberately keeps several records separate:

- the complete adult-illustration source intent;
- an existing `CreativeIntent` when all reference roles can be represented;
- a route-neutral control plan;
- source-to-CreativeIntent reference mappings;
- blocking errors and unresolved binding requirements;
- content hashes for stale-record detection.

`execution_authorized` and `generation_submitted` are always false.

## Public API

```python
from studio_prompt.adult_illustration import (
    new_intent,
    validate_intent,
    project,
    validate_projection,
)
```

- `new_intent(brief, subjects, ..., consent_context, coverage)` creates a minimal reviewed source intent.
- `validate_intent(value)` applies strict fields, bounds and adult/content requirements and returns a detached copy.
- `project(value)` emits a deterministic projection without mutating the source.
- `validate_projection(value)` recomputes the projection so changed or stale derived records fail closed.

A multi-subject intent is invalid unless the caller explicitly supplies `consent_context="reviewed_consensual"`. Adult status comes from reviewed owner/canon metadata; the module never infers it from an image.

## Mapping onto CreativeIntent

| Adult illustration record | Existing CreativeIntent destination |
| --- | --- |
| subject descriptions, body, wardrobe, expression | `facets.subject` |
| pose/action | `facets.action` |
| setting, composition, camera, lighting, palette, mood | corresponding facet |
| style and material | `facets.style` |
| tags and avoid terms | unchanged lists |
| adult/content/coverage/consent declarations | hard `verify` constraints |
| user constraints | unchanged constraints after reserved-ID checks |
| identity/body-design reference | `identity` role |
| outfit reference | `costume` role |
| pose reference | `pose` role |
| camera/composition/environment/prop reference | `composition` role |
| style/palette/material reference | `style` role |
| protection reference | `mask` role |

An `edit_source` cannot be represented honestly as an ordinary CreativeIntent reference. It therefore blocks projection until a route-specific edit binding exists. A reference with several roles expands into several CreativeIntent references while preserving one source ID and hash in `reference_map`. Equivalent source roles such as identity and body design share one CreativeIntent role.

## Controls

Controls are typed by target and mechanism. Semantic text and attributed review decisions are already represented in the reviewed intent. Geometry artifacts, appearance adapters, reference bindings, masks, bounded numbers and deterministic operations remain `requires_route_binding`; the projection never turns them into extra prompt prose.

Subject- or region-scoped references likewise retain their ownership in `reference_map` and require a compatible route binding.

## States

- `review_required`: all current semantics are representable and no route-specific binding remains.
- `requires_binding`: a CreativeIntent exists, but geometry/adapters/reference scope or another typed control still needs an exact compatible route.
- `blocked`: the current projection would lose a source role, exceed CreativeIntent reference limits or otherwise misrepresent the source intent.

None of these states means generated, accepted, rights-cleared or promoted.

## Example

`examples/adult-illustration/hot-spring-study.json` is a synthetic, non-executing example with three role-separated source declarations. The placeholder source paths and hashes prove the contract only; no image bytes are included or treated as present. Projection returns `requires_binding` and zero generation.

## Offline CLI

The stacked CLI slice exposes the pure operations without importing model, graph or runtime services:

```console
python scripts/studio_adult_illustration.py validate-intent examples/adult-illustration/hot-spring-study.json
python scripts/studio_adult_illustration.py project examples/adult-illustration/hot-spring-study.json --out experiments/runs/hot-spring-projection.json
python scripts/studio_adult_illustration.py validate-projection experiments/runs/hot-spring-projection.json
```

`--out` uses exclusive creation and never overwrites evidence. Validation errors are JSON on stderr with `execution_authorized: false` and `generation_submitted: false`. A structurally valid `blocked` projection exits successfully because it is an inspectable planning result, not a generation failure.

## Next integration

Map the projection onto existing revisioned Prompt/Setup commands, then bind exact route capabilities. Route binding belongs to #405/#407/#408 and execution remains under #10/#22/#122.
