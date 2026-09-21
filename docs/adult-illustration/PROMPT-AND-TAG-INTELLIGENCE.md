# Prompt and tag intelligence

Research and architecture for issue #432. This layer helps people and agents express reviewed intent in the exact dialect of a selected route. It is not a prompt-autocomplete toy, an unbounded LLM rewrite, or a substitute for geometry, references, adapters, masks, execution review, or artistic acceptance.

## Product decision

The source of truth remains the model-independent adult-illustration intent. A prompt is a **compiled projection** for one exact route configuration. Changing a checkpoint, text encoder, prediction type, quantisation, workflow or custom-node implementation may invalidate the projection even when the family name is unchanged.

The Studio should therefore expose three things separately:

1. the reviewed intent and locked constraints;
2. the target route's documented prompt dialect;
3. the generated projection, diagnostics and unresolved concepts.

A person may still edit the native prompt, but that edit becomes an attributed route-specific override rather than silently changing the source intent.

## Why one universal prompt composer fails

Anime models do not share one language:

- ordered tag-oriented SDXL routes use tokens whose order, spacing, quality vocabulary and negative channel are model-specific;
- Anima variants accept tags and natural-language descriptions but Base, Turbo and Aesthetic must not inherit one profile blindly;
- Pony derivatives frequently rely on derivative-specific score, source and rating conventions;
- instruction editors such as Qwen Image Edit use ordered natural-language reference ownership and invariants rather than a large tag dump;
- positive-only or distilled graphs may expose fields whose names do not prove effective negative conditioning.

The compiler must not mix these conventions or invent a generic fallback.

## Four records, not one prompt string

### Reviewed intent

Model-independent subjects, adult declarations, wardrobe, pose, camera, scene, style, references, exclusions and locks. This is already represented by `studio.adult-illustration.intent/v1` and projected into the existing Prompt Lab `CreativeIntent` boundary.

### Dialect profile

An exact route-bound declaration containing:

- route candidate identity;
- immutable source revision before promotion;
- tag, hybrid or instruction mode;
- separator and ordered sections;
- quality/rating/source-token rules;
- natural-language support;
- negative and weighting semantics;
- tokenizer or encoder limits where measured;
- linked verified vocabularies;
- concepts that must remain geometry, reference, adapter, mask, deterministic or review operations;
- unresolved facts and qualification evidence.

`research/adult-illustration/prompt-dialects.json` begins with source-reviewed but intentionally unready profiles. A moving `main` card is enough for research, not promotion.

### Vocabulary record

A vocabulary entry needs more than a string:

```json
{
  "id": "camera-three-quarter-view",
  "canonical": "three quarter view",
  "display": "three-quarter view",
  "aliases": ["three-quarter view"],
  "implications": [],
  "deprecated_by": null,
  "semantic_facets": ["camera"],
  "source": {
    "kind": "danbooru_export",
    "url": "...",
    "revision": "immutable revision"
  },
  "status": "verified",
  "route_profile_ids": ["exact-route-profile"],
  "accepted": true
}
```

The checked-in `tag-vocabulary-example.json` contains **contract examples only**. They are not accepted triggers. A real vocabulary must pin its taxonomy source, preserve aliases/deprecations and separately qualify route support.

Danbooru's broad categories—general, artist, copyright, character and meta—remain source metadata. They do not give the Studio the semantic distinctions it needs between wardrobe, pose, contact, camera, lighting, material and background. The Studio ontology supplies that second layer.

### Observation or proposal

A tagger, captioner or local LLM produces an immutable attributed proposal:

- exact model, file/digest and runner;
- template and thresholds;
- input derivative identity;
- raw tags/scores or caption;
- uncertainty and omitted regions;
- execution duration and failure state.

Review creates a separate selection or override. The observation is never rewritten to look correct after the fact.

## Analyzer portfolio

### WD SwinV2 Tagger v3

The SmilingWolf model publishes ONNX and safetensors variants plus `selected_tags.csv`, with 10,861 classes in the reviewed config. It is a useful anime-vocabulary suggester, not an original-prompt reconstructor or a calibrated judge. Threshold, class imbalance, crop behavior and semantic grouping require local evidence.

Proposed use:

1. create a bounded analysis derivative;
2. run one pinned model/file with retained thresholds;
3. preserve raw scores;
4. map labels into the verified vocabulary and semantic ontology;
5. let the user accept, reject or reassign them;
6. never select tags automatically merely because their score exceeds a threshold.

### JoyCaption or a general VLM

A caption model can describe relationships, garment construction, camera and ambiguous context that a flat tagger misses. Its prose is still an observation, not proof of identity, age, consent, hidden anatomy, rights, original prompt or exact route triggers.

Use a single already-qualified helper first. Compare semantic omissions and inventions against the no-helper/manual baseline before adding a second model.

### Local language model

The LLM should **retrieve and rank verified entries**, not invent a tag dictionary. A valid request supplies:

- reviewed intent;
- locked fields;
- target dialect profile;
- bounded verified vocabulary;
- examples tied to that profile;
- an output schema containing selected IDs, unresolved concepts and rationale.

Its output is a proposal. Unknown concepts stay unknown. It cannot transform an unsupported pose, mask or reference role into prose merely to make compilation appear complete.

## Compilation sequence

```text
reviewed source intent
  -> split controls by mechanism
  -> retrieve candidate vocabulary for semantic-text controls
  -> apply exact dialect order/separators/special tokens
  -> build negative or affirmative avoidance projection according to the route
  -> count actual target tokens where the tokenizer is pinned
  -> report unsupported, truncated, conflicting and non-prompt controls
  -> emit a reviewable prompt projection and content hash
```

The compiler must preserve the difference between:

- a concept absent from the route vocabulary;
- a concept supported by another mechanism;
- a concept that conflicts with a locked constraint;
- a concept truncated by the tokenizer;
- a route whose negative semantics are unknown;
- a user override that is intentionally native to this route.

## Required diagnostics

At minimum:

- `UNKNOWN_VOCABULARY`;
- `ALIAS_RESOLVED`;
- `DEPRECATED_TAG`;
- `IMPLICATION_ADDED`;
- `DIALECT_MIXED`;
- `NEGATIVE_SEMANTICS_UNRESOLVED`;
- `TOKEN_BUDGET_EXCEEDED`;
- `CONTROL_REQUIRES_GEOMETRY`;
- `CONTROL_REQUIRES_REFERENCE`;
- `CONTROL_REQUIRES_ADAPTER`;
- `CONTROL_REQUIRES_MASK`;
- `LOCK_CONFLICT`;
- `ROUTE_PROFILE_NOT_READY`.

A diagnostic may block, warn or explain. It never silently removes a hard requirement.

## Qualification

For one exact route, keep model, graph, references, geometry, resolution and sampling fixed. Compare:

1. unchanged short brief;
2. concise human clarification;
3. verified-vocabulary compiler projection;
4. optional local-helper proposal accepted field by field.

Measure hard-constraint coverage, identity/outfit/pose/contact results, prompt edits, token use, accepted distinct tasks, attempts and cleanup. Do not promote a profile because its prompt appears sophisticated or because the same helper praises it.

The initial held-out set should include:

- one subject with pose and camera constraints;
- garment construction and material;
- character plus separate pose/style references;
- two adults with distinct ownership and a shared prop/contact;
- a conflicting reference whose background must be ignored;
- a scoped edit where the prompt cannot replace the write mask.

## Agent contract

Read-only agents may list profiles, vocabulary and unresolved concepts. A proposal command may return an exact intent-to-prompt diff and zero-authority diagnostics. Applying a route-specific override requires expected-revision semantics through the existing shared intent owner. Compile, inspect and diff create no jobs.

No agent may:

- invent accepted vocabulary;
- choose artist tags on the user's behalf;
- infer adult status or consent from pixels;
- select a latest model/profile implicitly;
- change geometry, references, masks or adapter weights while claiming to only edit text;
- install a tagger or helper;
- advance a route or vocabulary evidence state without retained proof.

## Delivery order

1. Static profile/vocabulary contracts and validator — this foundation.
2. Read-only list/get/explain commands over the manifests.
3. Pinned taxonomy intake and alias/deprecation index.
4. Deterministic compiler profiles for one tag, one hybrid and one instruction route.
5. Optional analyzer adapters through the existing helper/resource coordinator.
6. Finite accepted-output qualification under #37/#409.
7. Shared UI/CLI/SDK/MCP projection through #413.
