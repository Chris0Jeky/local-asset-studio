# Creative Bundle Explorer

13 September 2026 · first implementation slice · baseline `8f471d6`.

In **Create**, open **Explore creative bundles** above recipe search. Search by
look, family or a resource name; inspect the recipe and its historical example;
expand ingredients, adapter explanations and source guidance; adapt a setting;
review the differences and explicitly apply to Create. Generate remains a
separate existing action.

## Delivered

The explorer projects `presets/recipes.json`, the live catalog's defaults and
bindings, `presets/settings-kb.json`, and the existing inspection endpoint. It
adds neither a new recipe database nor a model manager or executor. The existing
workbench remains the editing/submission authority.

The two initial preview links are already-recorded local Krea trials. Cards with
no documented preview say so. A changed prompt, dimension, seed or strength does
not turn an old image into a preview of the new configuration. Source-listed
ranges and recorded hashes are labelled as stored evidence, not measurements of
the currently installed files.

Text-to-image recipes can be applied. Reference and non-image routes remain
inspect-only in this slice. Editable controls cover supported prompt fields,
seed, steps, CFG, dimensions and authored numeric adapter strengths. Sampler,
scheduler and file substitution remain available through the existing
workbench; this slice does not certify arbitrary combinations. Apply resets the
full selected preset before overlaying the resolved recipe, clears references
with explicit consent and sets batch count to one, even for authored sweep
recipes. The normal draft mechanism is retained, not replaced.

**Guided tuning:** Try a related same-preset setup, choose whether to preserve
your wording, seed and canvas, then review and stage its complete sampling and
adapter changes. Draft edits have undo/redo; final Apply remains separate. Edited
configurations do not inherit the source recipe's execution receipt. This is
transient browser state, not a new shared-document store.

**Reusable workflows:** Prepare a named Steps document from the tuned draft,
review it, then explicitly save a new copy through the existing Workspace
workflow service or download its JSON. Reopen it in Workflow builder for shared
revision-checked editing. Saving never generates; interrupted saves retain the
same request identity for explicit recovery.

**Preview delivery:** the canonical JSON index has a generated checked-in JS
module so it can load through Studio's existing static-file policy. Normal
startup requires no build. See the delivery correction below.

**Contextual guidance:** “Why these settings?” checks the actual draft against
resource-scoped records in the existing settings library. It distinguishes
upstream advice, authored starting points and historical observations, shows
prerequisites and conflicts, and updates after edits without applying changes.
Matching catalog pins is not fresh verification of installed model bytes.

## Read next

- [Setup compatibility and recommendation intelligence](SETUP-COMPATIBILITY.md)
- [Retained source evidence to setup compatibility](SETUP-SOURCE-EVIDENCE.md)
- [Atomic, dependency-aware setup substitutions](ATOMIC-SUBSTITUTIONS.md)
- [Resource-scoped settings explanations](SCOPED-GUIDANCE.md)
- [Reusable Steps workflows and retained-save contract](REUSABLE-WORKFLOWS.md)
- [Guided tuning, reconciliation and tests](GUIDED-TUNING.md)
- [Showcase HTTP delivery correction](DELIVERY-FIX.md)
- [Architecture and next interaction model](ARCHITECTURE.md)
- [Representative-example protocol](REPRESENTATIVE-EXAMPLES.md)
- [Validation and remaining acceptance](VALIDATION.md)

Follow-ups: [#143](https://github.com/Chris0Jeky/local-asset-studio/issues/143)
representative portfolios; [#144](https://github.com/Chris0Jeky/local-asset-studio/issues/144)
version-scoped recommendations and atomic module changes. These extend #9, #10,
#14, #16, #36 and #118–#120; they do not close those broader workstreams.

## Source scope is not resource identity

Read-only guidance now distinguishes the advice source from the resource hashes it targets. An optional
`source.scope` in the existing settings-KB claim accepts `family`, `exact_version`, `local_workflow` or
`unrecorded`. Legacy records remain unrecorded; matching model pins never fills that gap automatically.
Specific scopes require a commit/content pin or an explicit `civitai-version:<id>` source identity, not
`main`, a version label or a retrieval date. These are checked declarations, not source authentication.

HTTP, CLI and the current panel receive normalized `source_scope` and the same explanation through
existing `reasons`. Resource applicability, conflict handling, review-due flags and all no-write/no-generation
boundaries remain unchanged. No old source was silently reclassified. The
[research adaptation](../strategy/anime-qualification/ARCHITECTURE.md) explains the distinction and the
remaining exact-version compiler migration.
