# Immersive Studio Presentation Design

**Date:** 18 September 2026  
**Status:** approved for implementation by the repository owner  
**Basis:** the existing Focus/Studio workshop, the adaptive-studio strategy stack, and the owner-supplied frontend mockups.

## Goal

Add an optional production presentation that approaches the supplied mockups without replacing the current editor, executor, draft store, reference owners, recipe catalogue, or recovery flows.

## Product boundary

The change adds three independent presentation choices:

- **Layout:** add `Immersive Studio` alongside Focus and Studio.
- **Skin:** add `Retro Anime` alongside Atelier, Arcade and Sakura.
- **Ambience:** add `None`, `Night Shift` and `Quiet Morning` as local static environments.

Presentation changes must preserve the same editable DOM nodes, file inputs, recipe selection, parameters, prompt value, output history and Generate handler. They must not select a model, stage a source, submit a job, enable remote media, download assets, or infer readiness.

## Information architecture

At wide desktop widths, Immersive Studio uses three columns:

1. **Run setup rail:** active recipe, recipe change, concise tuning summary and the existing readiness review action.
2. **Prompt workspace:** the original prompt, references, tuning and inspection disclosures, plus current results below.
3. **Context rail:** one derived next action based only on existing readiness and output state.

The shell keeps the existing sidebar and global navigation. At narrower widths the rails become ordinary stacked panels in a deterministic order. Focus and Studio remain available and retain their existing intent.

## Visual language

Retro Anime uses deep navy surfaces, restrained rose/cyan/lavender accents, soft edge illumination and local geometric environment art. It must remain readable without the art and under forced colours. System fonts only.

Night Shift and Quiet Morning are paired local SVGs with the same camera and architecture. They are decorative, carry no status or instructions, use empty semantics, and never block the workspace. Ambience `None` hides the environment region without leaving a layout gap.

## Preference model

Introduce `studio.workshop.presentation.v2` with the allow-listed shape:

```json
{"layout":"focus","skin":"atelier","ambience":"none"}
```

Read the previous `studio.workshop.presentation.v1` value when v2 is absent, retaining its valid layout and skin and defaulting ambience to `none`. Never persist prompts, file paths, model identities, seeds or generation settings. Storage denial remains harmless.

## Contextual guidance

The right rail is deliberately narrow:

- When Generate is blocked, direct the user to the existing readiness disclosure and display the first existing blocker text.
- When Generate is available and no outputs exist, offer to focus the existing Generate button.
- When outputs exist, offer to open the existing Recent runs disclosure.

The guidance button only focuses or reveals existing UI. It never invokes Generate or another domain command. The explanation states that it is derived from current UI observations and does not submit work.

## Accessibility and resource policy

- Keep native select controls for Layout, Skin and Ambience; the visual skin cards mirror the Skin select and expose pressed state.
- Preserve keyboard focus, native recipe-dialog cancellation and 200% zoom usability.
- No horizontal page overflow at 390 px.
- Respect reduced motion and forced colours.
- No network, video, audio, remote fonts, autoplay or service worker.
- Local SVG failure leaves tokens and text fully usable.

## Qualification

Required evidence:

- Pure contracts for allow-listing, v1-to-v2 migration and persistence scope.
- Browser fixture checks for the new controls, visual skin picker, local ambience, guidance behaviour and all layout/skin/ambience combinations preserving prompt and file input identity with zero submissions.
- Existing workshop browser, application, prototype and repository checks remain green.
- Production artwork remains explicitly local and documented in `docs/workshop/ASSETS.md`.

## Out of scope

Vue adoption, remote decorative media, animated ambience, parallax, audio, model/resource telemetry, new recipe semantics, a second prompt model, and a frontend rewrite are not part of this slice.
