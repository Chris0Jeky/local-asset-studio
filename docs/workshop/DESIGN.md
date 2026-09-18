# Create workshop redesign

Design baseline: main `b8b1409d0f397b7562e67366e51629826ec0ae7d`.
Source brief: owner-supplied **LAS Create UX wishlist, 17 September 2026**, especially sections 3, 5, 7 and 8. The brief's 3397 px height and ~25 controls are its QA observations, not new measurements. This change measures its own browser fixture separately.

## Outcome

Create should open on an idea, not a catalogue. Keep the active recipe, the prompt, required sources and the real Generate action easy to find. Power controls remain available without dominating the first screen.

Two layouts share one editor: **Focus** is a generous single-column writing desk; **Studio** places that same desk alongside the existing result gallery. Layout is independent from skin. **Atelier** is warm graphite and a peach accent; **Arcade** uses a midnight palette and pixel motifs; **Sakura** uses an anime-inspired rose palette and illustrated atmosphere. None changes models, prompt semantics, defaults, permissions, or generation behaviour.

## State and authority

Keep `studio-workbench.js` as the migration adapter and the existing application as the only executor. Move actual DOM nodes, not duplicate inputs or cloned buttons. The existing per-workspace/per-recipe draft system stays the sole prompt-recovery owner. Store only allow-listed layout/skin preferences under a new browser-local key. A storage failure must not prevent editing. No analytics transport, model download, generated example, or job submission runs on load.

A native labelled dialog owns recipe discovery. Tuning and inspection stay in inline disclosures so existing validation, walkthrough and keyboard focus targets remain reachable. Escape closes the recipe dialog and focus returns to its opener; inline disclosures retain native summary behaviour. The recipe readiness action opens the moved picker before the existing handler focuses its search. Preserve source-file input identities and current values while switching presentation.

## Surfaces

| Surface | Treatment |
| --- | --- |
| Active recipe | Compact header with Change action; full metadata remains inspectable |
| Recipe discovery | Searchable modal using the current catalogue and its filters; no second recipe store |
| Prompt | Spacious textarea; existing fill-in wording and continuation tools preserved |
| Negative prompt | First workshop visit collapses the existing disclosure without clearing it; its existing session toggle owner then retains explicit choices |
| Parameters/adapters | Above-the-fold quick summary; existing controls and adapter stack in a grouped inline disclosure |
| Sources | Existing recipe-specific file inputs, reference board and continuation controls |
| Readiness/run | Original checks, status, ETA and original Generate button; always-visible run dock on Create |
| Recent runs | Existing media, provenance and Continue actions; opens after explicit Generate, right rail only in Studio on wide screens |
| Saved setups | Secondary disclosure/surface, using the current store and apply/save handlers |
| Models | Existing dedicated Models route; no inline full catalogue |
| Under the hood | Optional inspection, never promoted over generation |

No new queue, model registry, reference store, or prompt editor. No backend rewrite or dependency change.

## Interaction decisions

Opening a picker does not mutate the editor. Switching the presentation does not reconstruct the editor. Choosing a different recipe must pass a work-loss confirmation when custom wording or attachments would be replaced; cancellation leaves the current recipe and draft untouched. It does not silently carry incompatible image bindings to a new recipe. Existing prepared-setup and continuation review flows retain their own guards.

The native modal scrolls independently; the page must not jump to the top when it closes. Avoid viewport-height clipping of sources and blockers. At small widths the recipe surface fills the available screen, and the run dock wraps without horizontal page overflow. Short viewports may require scrolling the content, but the action remains reachable.

Presentation selectors are allow-listed. Decorative assets are local, optional, non-interactive, and kept out of text fields and status areas. Honour reduced motion and forced colours. Use ordinary system fonts; do not fetch fonts or artwork from a third party.

## Verification and delivery

PR 1: Focus workbench, shared presentation seam, recipe/tuning surfaces, state-preserving navigation, accessibility and browser contracts.
PR 2: Studio variation and optional skins on the same seam, offline interactive prototype, asset source notes, comparison evidence.

At 1440×900, the active recipe, prompt and Generate should appear in the first viewport; default document height target is <1600 px. At 390×844, no horizontal page overflow and no hidden Generate. Measure with fixture state labelled as such, not fabricated local hardware evidence. Exercise the real application through its existing fake-server test fixture where possible. Retain existing suite coverage for drafts, handoffs, references, readiness and saved setups.

Open acceptance: Chris's preference between layouts/skins; a real local ComfyUI click-through with the installed models and owner references. No screenshot or passing frontend test constitutes art acceptance or model licence clearance. Existing HUMAN_TODO choices remain untouched.
