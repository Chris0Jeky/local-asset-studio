# Artistic-control preferences and honest model/tool labels

The machine-readable source is `research/character-consistency/edit-routes.json`. Run `python scripts/character_edit.py policies` to see the default local-only selection report. This is source-reviewed metadata as of 12 September 2026, not a live graph inspection.

## Do not collapse these questions

| Dimension | Meaning |
|---|---|
| Local versus hosted | Where inference runs and whether pixels leave the machine. Local execution alone says nothing about learned behaviour. |
| Input/output filtering | A wrapper, node or service classifies and rejects prompts/images or substitutes output. |
| Learned restrictions | Training/fine-tuning may suppress concepts or produce refusals; removing a wrapper does not establish their absence. |
| Agent restrictions | The local planning/critique assistant can have separate behaviour from the image generator. |
| Licence/terms | Permissions for weights, outputs, derivatives or deployment. These are not an inference filter or a quality score. |
| Operational protection | Prevent overwrites, stale edits, runaway compute, unsafe paths and duplicate submissions. Keep these protections independently of artistic preferences. |

## What is known now

| Route | Evidence-backed label | What remains unknown |
|---|---|---|
| New deterministic crop/mask/composite commands | **No content filter in this adapter; no learned model.** Source inspection and tests cover these commands. | They do not synthesize or approve anatomy. This label does not describe arbitrary third-party wrappers. |
| Qwen Edit through the existing Studio | **Local candidate; runtime filters and learned restrictions unverified.** | Inspect the exact graph, custom nodes, weights and prompt path before claiming no filter. Its card's quality claims are not a filtering audit. |
| FLUX.2 Klein 4B | **Open weights with documented safety fine-tuning; upstream filtering code exists.** | Whether this Studio graph enables any supplied filter, and the effect on the user's legitimate artistic briefs. |
| Existing SDXL/anime repair route | **Local candidate; exact derivative/wrapper behaviour unverified.** | Model-card silence or community "uncensored" descriptions are not measurements. |
| Krita AI Diffusion with local backend | **Editor bridge; behaviour depends on the selected backend/model.** | Plugin version, nodes, active filters, reference behaviour and job ownership need native inspection. Its cloud offering is a separate route. |
| Local VLM planner/critic | **Local candidate; assistant behaviour independent of image model.** | Refusal, suppression, instruction-following and critique accuracy need their own test. |
| Hosted GPT Image | **Hosted content filtering documented.** | Endpoint-specific current access/settings. `moderation=low` is not an off switch. Excluded from local-only routing. |

BFL's author card describes checkpoint safety fine-tuning and filters shipped with its inference code. It distinguishes the Apache-licensed 4B model from separate 9B licence requirements. An available filter is not proof that a given Comfy graph invokes it. Documented safety training is also **not a measurement of how often lawful artistic changes will be refused**. [P1]

OpenAI's image API guide documents filtering for inputs/outputs and the supported moderation setting; the less restrictive setting does not disable filtering. No hosted call, API subscription or fallback is enabled here. [P2]

Qwen's edit model card supports its use as a reference-edit candidate, including multi-person consistency claims, but does not certify our local runtime as unfiltered. [P3]

## User preferences implemented

The example defaults to:

```json
{
  "local_only": true,
  "exclude_known_filters": true,
  "exclude_documented_weight_restrictions": true,
  "unknown_policy": "allow_with_warning"
}
```

These are independent selections. The learned-restrictions preference is deliberately separate because a user may prefer to retain a useful local model despite documented training constraints. Unknown candidates remain visible with warnings; they are not promoted to "unrestricted." Choosing `unknown_policy: "exclude"` may leave **no eligible generative route** until an audit supplies better evidence. `python scripts/character_edit.py policies --strict-unknown` demonstrates that distinction.

The report has no automatic winner, inferred quality ranking or authorization token. It does not modify a model, remove a hosted filter, rewrite the user's request, or retry through another provider to conceal a refusal. The adapter contains no artistic keyword blocklist. A legitimate brief can be passed through unchanged; native model-specific syntax changes must remain visible in the existing Prompt Lab trace.

The earlier #64 pilot is a separate experiment. Its Klein baseline is not silently removed or its budget rewritten by these new edit preferences. A study that deliberately compares that model must record the chosen preference and reason explicitly.

## Promote evidence, not slogans

A future exact-bundle audit should record graph hash, reachable node implementations, model/encoder/adapter hashes, application version, actual enabled classifier/filter settings, prompt rewriting, network endpoints and the local agent model independently. Pin this evidence to the execution bundle, not just the family name. Re-audit after an effective graph, node, model or wrapper update.

Useful labels are **no filter in audited adapter**, **filter enabled**, **upstream filter available**, **learned restrictions documented**, **unknown**, and **observed interference on tested art briefs**. Preserve source, date and test denominator. A handful of outputs without a refusal cannot prove that an arbitrary model has no restrictions. Also distinguish a true content refusal from an unsupported control, poor prompt following, failed decode, empty inpaint mask or missing model.

The practical aim is reliable artistic control with no unnecessary content-screening layer added by the Studio. It is not a misleading guarantee that every possible external model will produce every request.

## Primary sources

[P1] https://huggingface.co/black-forest-labs/FLUX.2-klein-4B

[P2] https://developers.openai.com/api/docs/guides/image-generation

[P3] https://huggingface.co/Qwen/Qwen-Image-Edit-2511

[P4] https://github.com/Acly/krita-ai-diffusion

Policy observations are not legal advice or an assertion of output/character rights. Use the existing model library for exact terms; do not duplicate or silently override its records.
