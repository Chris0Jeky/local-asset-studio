# Deterministic adult illustration prompt profiles

Implementation guide for the prompt-dialect and reviewed-taxonomy slices under [#437](https://github.com/Chris0Jeky/local-asset-studio/issues/437). It consumes the reviewed, non-executing `studio.adult-illustration.projection/v1` record produced by the existing adult illustration intent layer, resolves only finite reviewed vocabulary, and emits model-profile text only.

This compiler is not a workflow, model selection, route binding, resource reservation or generation approval. It does not read the retained taxonomy CSV or generated index during compilation.

## Delivered profiles

| Profile | Mode | Route candidate | Behaviour |
| --- | --- | --- | --- |
| `animagine-xl4-ordered-v1` | ordered tags | `animagine-xl-4-opt-source-review` | Verified vocabulary only; route-specific ordered positive tags and separate negative channel. |
| `anima-aesthetic-hybrid-v1` | hybrid | `anima-aesthetic-source-review` | Lowercase space-form tags plus reviewed concise prose; deliberately excludes inherited Pony and Anima Base/Turbo score conventions. |
| `qwen-edit-2511-instruction-v1` | instruction | `qwen-image-edit-2511-source-review` | Explicit `Image N` ownership, take/ignore rules, semantic goal and preservation constraints for the repository's proposed three-reference route. |

Each profile pins an immutable documentation revision. The profile does **not** claim that its model files, graph, encoders, VAE or runtime are installed. Those remain exact route evidence under #405/#439.

## Files

- `research/adult-illustration/prompt-profile-vocabulary.json` — profiles and the small profile-owned proof vocabulary.
- `research/adult-illustration/taxonomy-source.json` — immutable upstream source identity and intake bounds.
- `research/adult-illustration/taxonomy-review.json` — finite Studio-owned compilation review.
- `studio_prompt/adult_illustration_prompt_common.py` — strict constants and JSON validation primitives.
- `studio_prompt/adult_illustration_prompt_catalog.py` — bounded profile catalog, aliases and implication validation.
- `studio_prompt/adult_illustration_taxonomy_prompt.py` — read-only reviewed-taxonomy overlay and deterministic lookup.
- `studio_prompt/adult_illustration_prompt_projection.py` — deterministic compiler and tamper-checking validator.
- `scripts/studio_adult_illustration_prompt.py` — zero-authority CLI.
- `tests/test_adult_illustration_prompt_profiles.py` — catalog and compiler contracts.
- `tests/test_adult_illustration_prompt_cli.py` — agent/CLI contracts.
- `tests/test_adult_illustration_taxonomy_prompt_integration.py` — taxonomy precedence, provenance and fail-closed integration contracts.

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

A compiled record uses `studio.adult-illustration.prompt-projection/v2`. Version 2 adds taxonomy identity and per-term resolution provenance; retained version 1 outputs must be recompiled rather than interpreted under the expanded shape.

A compiled record contains:

- exact profile and route-candidate IDs;
- source and profile-catalog identities;
- exact taxonomy source SHA-256, immutable revision and both contract hashes;
- positive, negative or instruction channels;
- explicit ordered reference bindings;
- one bounded resolution record per positive or negative input;
- vocabulary source, match kind, status, entry IDs, emitted forms and semantic facets;
- unresolved-control diagnostics;
- zero-authority flags;
- deterministic content hash.

`validate_prompt_projection` recompiles the record and refuses changed derived output.

## Vocabulary rules

Compilation has two deliberately separate vocabulary layers.

1. **Reviewed taxonomy.** The finite `taxonomy-review.json` overlay is checked first. A matched term is accepted, rejected, deprecated, polarity-constrained and profile-constrained by that review. The compiler never falls back around a taxonomy decision.
2. **Profile-owned proof vocabulary.** `prompt-profile-vocabulary.json` is consulted only when no reviewed taxonomy entry matches. It retains route-specific or documentation-derived terms that are absent from the pinned taxonomy source.

For tag profiles, reviewed taxonomy entries emit their pinned upstream `source_name`, including underscores. Hybrid profiles emit the reviewed human-readable `display` form. Instruction profiles emit neither; they preserve tags in the resolution trace and compile explicit exclusions as natural-language instructions.

Both loaders reject:

- duplicate JSON keys and unknown fields;
- canonical, display or alias collisions after underscore/space normalization;
- implication or deprecation cycles;
- implications to unknown entries;
- polarity mismatches;
- implication targets that lose profile support;
- excessive relationship depth;
- unknown prompt-profile IDs;
- moving or malformed source revisions;
- any authority flag set to true.

The compiler binds source and review manifest hashes into every output. A valid review edit therefore invalidates an older retained prompt projection on revalidation.

The retained `selected_tags.csv` and generated 4.6 MB index are not required for prompt compilation. This keeps the bridge offline and bounded, but means an unmatched term is reported as unknown rather than source-known-but-unreviewed. That finer distinction requires a separately validated index or compact membership handoff.

A WD/VLM/LLM suggestion is not accepted vocabulary merely because it looks plausible. New entries require pinned source evidence and an explicit Studio review diff.

## Diagnostics

The compiler does not silently repair or drop uncertainty. Representative diagnostics include:

- `UNKNOWN_VOCABULARY` — a positive term was absent from both reviewed taxonomy and profile-owned vocabulary;
- `UNKNOWN_AVOID_TERM` — an exclusion was absent from both reviewed taxonomy and profile-owned vocabulary;
- `TAXONOMY_TERM_NOT_ACCEPTED` — a reviewed entry is explicitly ineligible for compilation;
- `TAXONOMY_DEPRECATED_TERM` — a reviewed term has a replacement and is not emitted;
- `TAXONOMY_POLARITY_MISMATCH` — a taxonomy entry was used in the wrong channel;
- `TAXONOMY_UNSUPPORTED_FOR_PROFILE` — a taxonomy entry is not accepted for this exact profile;
- `TAXONOMY_IMPLICATION_NOT_ACCEPTED` — an implied taxonomy entry is not compilation-eligible;
- `TAXONOMY_UNORDERED_FOR_PROFILE` — a reviewed entry has no compatible ordering facet for the profile;
- `VOCABULARY_POLARITY_MISMATCH` — a profile-owned entry was used in the wrong channel;
- `VOCABULARY_UNSUPPORTED_FOR_PROFILE` — a profile-owned entry was not verified for this exact dialect;
- `CONTROL_REQUIRES_ROUTE_BINDING` — geometry, appearance, mask or another non-prompt mechanism remains unresolved;
- `REFERENCE_REQUIRES_ROUTE_BINDING` — role ownership is retained but no model input was bound;
- `REFERENCE_STAGING_REQUIRED` — instruction ownership is compiled, but native image staging/slot binding still needs an exact route;
- `TAGS_NOT_EMITTED_FOR_INSTRUCTION_PROFILE` — tags remain inspectable but are not dumped into Qwen natural-language instructions.

Warnings remain in the record. Hard profile limits, such as Qwen reference count, fail closed.

## Profile behaviour

### Animagine XL 4

The profile emits only verified tags, ordered by semantic facet, followed by the profile's pinned quality suffix. Reviewed taxonomy terms preserve the pinned upstream underscore form, while profile-owned terms retain their reviewed catalog form. It never mixes Pony score/source tokens or Anima conventions. Natural-language facets remain source intent; they are not guessed into arbitrary tags.

References and geometry remain diagnostics until an exact compatible SDXL graph binds them.

### Anima Aesthetic

The profile emits reviewed display forms, profile-owned lowercase space-form tags and concise reviewed prose. It deliberately omits score tags for this Aesthetic profile and does not inherit settings from Turbo or Base variants. The content tag is a model hint only; it cannot establish adult status or output compliance.

### Qwen Image Edit 2511

The profile emits natural-language instructions with ordered source ownership:

```text
Image 1 defines only identity. Use: face design, hair construction.
Do not copy: source outfit, source pose, source background.
```

It includes the reviewed goal, facets, constraints and exclusions. It does not dump Danbooru tags into the instruction. Positive and negative inputs remain represented in `vocabulary_resolutions`, while explicit avoidance terms become natural-language exclusions. The current profile is deliberately scoped to a repository three-reference graph proposal; it is not a claim about every Qwen interface.

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
  studio_prompt/adult_illustration_taxonomy_prompt.py \
  studio_prompt/adult_illustration_prompt_projection.py \
  scripts/studio_adult_illustration_prompt.py

python -m unittest \
  tests.test_adult_illustration_prompt_profiles \
  tests.test_adult_illustration_prompt_cli \
  tests.test_adult_illustration_taxonomy_prompt_integration -v
```

Passing software tests prove deterministic formatting, review precedence, provenance binding, bounds and fail-closed behaviour. They do not prove local model installation, exact installed-tokenizer counts, prompt quality, content behaviour, hardware fit or accepted artwork. Those remain route-evidence and #37/#409 qualification gates.
