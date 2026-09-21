# Deterministic adult illustration prompt profiles

Implementation guide for the first prompt-dialect slice under [#437](https://github.com/Chris0Jeky/local-asset-studio/issues/437). It consumes the reviewed, non-executing `studio.adult-illustration.projection/v1` record produced by the existing adult illustration intent layer and emits model-profile text only.

This compiler is not a workflow, model selection, route binding, resource reservation or generation approval.

## Delivered profiles

| Profile | Mode | Route candidate | Behaviour |
| --- | --- | --- | --- |
| `animagine-xl4-ordered-v1` | ordered tags | `animagine-xl-4-opt-source-review` | Verified vocabulary only; route-specific ordered positive tags and separate negative channel. |
| `anima-aesthetic-hybrid-v1` | hybrid | `anima-aesthetic-source-review` | Lowercase space-form tags plus reviewed concise prose; deliberately excludes inherited Pony and Anima Base/Turbo score conventions. |
| `qwen-edit-2511-instruction-v1` | instruction | `qwen-image-edit-2511-source-review` | Explicit `Image N` ownership, take/ignore rules, semantic goal and preservation constraints for the repository's proposed three-reference route. |

Each profile pins an immutable documentation revision. The profile does **not** claim that its model files, graph, encoders, VAE or runtime are installed. Those remain exact route evidence under #405/#439.

## Files

- `research/adult-illustration/prompt-profile-vocabulary.json` — profiles and the small pinned proof vocabulary.
- `studio_prompt/adult_illustration_prompt_common.py` — strict constants and JSON validation primitives.
- `studio_prompt/adult_illustration_prompt_catalog.py` — bounded catalog, aliases and implication validation.
- `studio_prompt/adult_illustration_prompt_projection.py` — deterministic compiler and tamper-checking validator.
- `scripts/studio_adult_illustration_prompt.py` — zero-authority CLI.
- `tests/test_adult_illustration_prompt_profiles.py` — catalog and compiler contracts.
- `tests/test_adult_illustration_prompt_cli.py` — agent/CLI contracts.

## Authority boundary

Every compiled artifact records all of these as false:

```json
{
  "execution_authorized": false,
  "generation_submitted": false,
  "download_authorized": false,
  "install_authorized": false,
  "training_authorized": false
}
```

The compiler:

- opens no socket;
- starts no subprocess;
- contacts no provider;
- reads no reference image bytes;
- downloads or installs nothing;
- calls no model runner or ComfyUI endpoint;
- submits no neural job;
- creates no allowance;
- advances no route evidence state.

## Input contract

The source must be an intact `studio.adult-illustration.projection/v1` value with:

- reviewed adult owner/canon metadata;
- `sensual_non_explicit` content envelope for this initial slice;
- `execution_authorized: false`;
- `generation_submitted: false`;
- a non-blocked existing `CreativeIntent` projection;
- bounded facets, tags, avoidance terms, constraints and references.

Compile from the intent projection, not directly from a loose user string. That preserves the distinction between reviewed intent, route-specific text and non-text controls.

## Commands

List profiles:

```console
python scripts/studio_adult_illustration_prompt.py profiles
```

Compile an existing adult illustration projection:

```console
python scripts/studio_adult_illustration_prompt.py compile \
  experiments/runs/hot-spring-projection.json \
  --profile anima-aesthetic-hybrid-v1 \
  --out experiments/runs/hot-spring-anima-prompt.json
```

Validate a retained compiled artifact by recompiling it from its source:

```console
python scripts/studio_adult_illustration_prompt.py validate \
  experiments/runs/hot-spring-anima-prompt.json \
  --source experiments/runs/hot-spring-projection.json
```

Output files use exclusive creation. A failed compile or validation does not overwrite an existing artifact.

## Output contract

A compiled record contains:

- exact profile and route-candidate IDs;
- source and catalog identities;
- pinned source/documentation revisions;
- positive, negative or instruction channels;
- explicit ordered reference bindings;
- unresolved-control diagnostics;
- zero-authority flags;
- deterministic content hash.

`validate_prompt_projection` recompiles the record and refuses changed derived output.

## Vocabulary rules

The checked-in vocabulary is deliberately small. It is a proof of deterministic profile compilation, not the final anime taxonomy.

A vocabulary entry has:

- a canonical lowercase form;
- aliases;
- implications;
- semantic facet;
- positive or negative polarity;
- exact compatible profile IDs.

The loader rejects:

- duplicate JSON keys;
- unknown fields;
- alias collisions after underscore/space normalization;
- implication cycles;
- implications to unknown entries;
- polarity mismatches;
- implication targets unavailable to a source profile;
- moving or malformed source revisions;
- any authority flag set to true.

A WD/VLM/LLM suggestion is not accepted vocabulary merely because it looks plausible. Future taxonomy intake must pin source URL, immutable revision, selected file, byte count and SHA-256, then map source categories into the Studio semantic facets through review.

## Diagnostics

The compiler does not silently repair or drop uncertainty. Representative diagnostics include:

- `UNKNOWN_VOCABULARY` — a positive term was not present in the pinned profile vocabulary;
- `UNKNOWN_AVOID_TERM` — an exclusion was not verified for the profile;
- `VOCABULARY_POLARITY_MISMATCH` — an entry was used in the wrong channel;
- `VOCABULARY_UNSUPPORTED_FOR_PROFILE` — a valid entry was not verified for this exact dialect;
- `CONTROL_REQUIRES_ROUTE_BINDING` — geometry, appearance, mask or another non-prompt mechanism remains unresolved;
- `REFERENCE_REQUIRES_ROUTE_BINDING` — role ownership is retained but no model input was bound;
- `REFERENCE_STAGING_REQUIRED` — instruction ownership is compiled, but native image staging/slot binding still needs an exact route;
- `TAGS_NOT_EMITTED_FOR_INSTRUCTION_PROFILE` — tags remain inspectable but are not dumped into Qwen natural-language instructions.

Warnings remain in the record. Hard profile limits, such as Qwen reference count, fail closed.

## Profile behaviour

### Animagine XL 4

The profile emits only verified tags, ordered by semantic facet, followed by the profile's pinned quality suffix. It never mixes Pony score/source tokens or Anima conventions. Natural-language facets remain source intent; they are not guessed into arbitrary tags.

References and geometry remain diagnostics until an exact compatible SDXL graph binds them.

### Anima Aesthetic

The profile emits lowercase space-form tags and concise reviewed prose. It deliberately omits score tags for this Aesthetic profile and does not inherit settings from Turbo or Base variants. The content tag is a model hint only; it cannot establish adult status or output compliance.

### Qwen Image Edit 2511

The profile emits natural-language instructions with ordered source ownership:

```text
Image 1 defines only identity. Use: face design, hair construction.
Do not copy: source outfit, source pose, source background.
```

It includes the reviewed goal, facets, constraints and exclusions. It does not dump Danbooru tags into the instruction. The current profile is deliberately scoped to a repository three-reference graph proposal; it is not a claim about every Qwen interface.

## Adding another profile

1. Open or use the exact route/prompt issue; do not add a family-wide generic profile.
2. Pin immutable official documentation and source revisions.
3. Record separator, ordering, quality/rating/source-token rules, negative semantics, natural-language support and native reference limits.
4. Add only verified vocabulary entries compatible with that profile.
5. Write failing tests for ordering, mixed-family rejection, limits, unknown terms and tamper detection.
6. Implement the minimal projection behaviour.
7. Run the focused suite and both adult illustration validators.
8. Compare unchanged brief, concise human clarification and compiled profile under #37/#409 before claiming artistic benefit.
9. Promote only for the exact tasks and route configuration supported by retained evidence.

## Verification

```console
python -m py_compile \
  studio_prompt/adult_illustration_prompt_common.py \
  studio_prompt/adult_illustration_prompt_catalog.py \
  studio_prompt/adult_illustration_prompt_projection.py \
  scripts/studio_adult_illustration_prompt.py

python -m unittest \
  tests.test_adult_illustration_prompt_profiles \
  tests.test_adult_illustration_prompt_cli -v
```

Passing software tests prove deterministic formatting, bounds and fail-closed behaviour. They do not prove local model installation, prompt quality, content behaviour, hardware fit or accepted artwork.
