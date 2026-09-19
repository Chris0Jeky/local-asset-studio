# Create workshop redesign

Original design baseline: main `b8b1409d0f397b7562e67366e51629826ec0ae7d`.  
Immersive extension approved by the repository owner on 18 September 2026 from the supplied frontend mockups and the adaptive-studio strategy.

## Outcome

Create should open on an idea, not a catalogue. Keep the active recipe, the prompt, required sources and the real Generate action easy to find. Power controls remain available without dominating the first screen.

Three layouts share one editor:

- **Focus** is the default single-column writing desk.
- **Studio** places that same desk beside the existing result gallery.
- **Immersive Studio** creates a wide three-column composition: compact run setup, the same editor, and one contextual next-action rail. At smaller widths it becomes the same deterministic stacked workbench.

Layout is independent from skin and ambience. Atelier, Arcade, Sakura and Retro Anime alter presentation tokens only. None, Night Shift and Quiet Morning alter only optional local decorative art. They do not change models, prompt semantics, recipe defaults, permissions, reference roles or generation behaviour.

## State and authority

Keep `studio-workbench.js` and the existing application as the only editable-state and execution owners. Move actual DOM nodes; do not clone inputs, file controls or Generate. The existing per-workspace/per-recipe draft system remains the sole prompt-recovery owner.

Presentation state is an allow-listed object under `studio.workshop.presentation.v2`:

```json
{"layout":"focus","skin":"atelier","ambience":"none"}
```

A valid v1 layout/skin value is read when v2 is absent; ambience becomes `none`. Prompt text, file names, model identity, seed and generation settings are never written to this key. A storage failure must not prevent editing.

A native labelled dialog owns recipe discovery. Tuning and inspection stay in inline disclosures so existing validation, walkthrough and keyboard-focus targets remain reachable. Escape closes the recipe dialog and returns focus. Preserve source-file input identity and current values through every presentation switch.

## Surfaces

| Surface | Treatment |
| --- | --- |
| Environment | Optional shallow local header; never a status or execution surface |
| Route strip | Navigation/reveal only; no alternate task state or executor |
| Run setup rail | Existing active recipe, Change action, tuning summary and readiness review |
| Recipe discovery | Searchable native modal using the current catalogue and filters |
| Prompt | Existing textarea, unchanged identity and handlers |
| Negative prompt | Existing disclosure and session preference owner |
| Parameters/adapters | Existing controls grouped under progressive disclosure |
| Sources | Existing file inputs, reference board and continuation controls |
| Context rail | One read-only next action based on current blocker, Generate state or output count |
| Readiness/run | Existing checks, status, ETA and original Generate button in the fixed dock |
| Recent runs | Existing media, provenance and Continue actions |
| Saved setups | Existing store and apply/save handlers in secondary disclosure |
| Under the hood | Optional inspection, never promoted over generation |

No new queue, model registry, reference store, prompt editor, readiness owner or backend service is introduced.

## Context guidance contract

The production contextual rail has four reachable actions:

1. **Review readiness** reveals the existing readiness disclosure and its first reported blocker.
2. **Review sources** focuses the exact outstanding existing source input or reveals the current source board.
3. **Focus Generate** moves focus to the existing Generate button without invoking it.
4. **Open recent runs** opens and focuses the existing result disclosure.

The current production capture reports only `blocked`, `ready` or `completed` execution and hard-codes no draft conflict. It therefore does not register `inspect-operation` or `resolve-draft-conflict` handlers. Those IDs remain part of the pure presentation-context vocabulary for a future consumer only after an existing job or draft owner publishes matching evidence.

The rail cannot infer an installed model, fabricate VRAM/timing, change a recipe, mutate a source, submit a job or retry an uncertain operation. Its “Why this?” text states which current UI observation it used. Source, readiness and result actions reveal or focus existing owners; they do not create a second workflow path.

## Visual and media policy

Retro Anime uses deep navy surfaces, restrained rose/lavender accents and cyan highlights with system fonts. Night Shift and Quiet Morning are original same-camera geometric SVG scenes. Source SVGs remain reviewable, while production CSS embeds inert data copies because the application static handler does not serve SVG files directly.

The scenes contain no text, controls, status or remote references. They disappear in forced-colour mode. No video, audio, parallax, autoplay, remote provider or network probe is included. The UI reserves no environment gap when ambience is None.

## Interaction decisions

Opening a picker does not mutate the editor. Switching presentation does not reconstruct the editor. Choosing a different recipe still passes the existing work-loss confirmation when custom wording or attachments would be replaced. Cancellation leaves the current recipe and draft untouched.

The recipe modal scrolls independently and restores focus/scroll. At small widths, native Layout, Skin and Ambience selects remain visible; the richer skin cards are an optional wide Immersive mirror. The run dock stays reachable without horizontal page overflow.

## Verification and delivery

Required automated evidence:

- Node contracts for allow-listing, v1 fallback, v2 persistence scope and option matrices.
- Component browser checks for cancelled/accepted recipe changes, draft/file identity, all 36 layout × skin × ambience combinations, contextual guidance authority and zero implicit submissions.
- Desktop/mobile geometry for every layout × skin pair, with an Immersive ambience representative.
- Actual-application HTTP/storage checks for real source lineage and exactly one explicit original submission request.
- Offline prototype checks with zero network requests/page exceptions.

Production defaults remain Focus + Atelier + None. The review prototype starts in the approved visual pilot only.

Open acceptance: a real local ComfyUI click-through with installed models and owner references, plus owner judgement of the environment art in normal use. No screenshot or passing frontend test constitutes model/GPU qualification, art acceptance or licence clearance.
