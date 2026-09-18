# Workshop Context-Guidance Integration Design

**Date:** 18 September 2026  
**Status:** approved continuation of the Immersive Studio and read-only presentation-boundary direction  
**Parent stack:** #574 → #581

## Goal

Replace the Immersive Studio guidance rail's local conditional copy with the read-only `StudioPresentationContext` projection from #581, while preserving the exact existing prompt, file inputs, recipe state, readiness owner, gallery and Generate handler.

## Boundaries

This is a presentation integration, not another workflow engine or state store. It may:

- read bounded primitive observations from existing owners;
- project one primary semantic intent and secondary observations;
- reveal or focus an existing local surface through a closed action map;
- expose the current frozen projection for tests and inspection.

It may not:

- submit or retry generation;
- select a recipe;
- rewrite a prompt;
- stage or remove a source;
- invent backend health, source readiness or operation state;
- add a timer, polling loop, remote request or framework dependency;
- send prompt text, file paths, image bytes or arbitrary selectors through the context boundary.

## Script loading

`studio-shell.js` loads `/static/presentation-context.js` first. Its successful `onload` creates `/static/workshop.js`. If the boundary cannot load, the progressive workshop enhancement does not mount; the underlying Create interface and its domain handlers remain usable.

The offline workshop prototype loads the same boundary before `workshop.js`, and the exporter inlines both scripts in source order.

## Context capture

The workshop reuses its existing event listeners and `MutationObserver`. The observer schedules one `sync()` pass; there is no second observer or poller.

Each pass creates a bounded context with:

- `workspaceId: "create"`;
- a local context stamp based on a monotonic presentation revision and non-sensitive primitive identities;
- task `generate`;
- recipe/backend identity and exact reference-slot IDs when known;
- source records expressed only as local IDs, slot IDs, human-readable roles and `selected` / `checked` / `staged` stages;
- pending local-file count;
- execution evidence derived from the existing Generate disabled state, first existing blocker and existing result-card count;
- no draft-conflict claim unless an existing owner explicitly exposes one.

A selected local file is `selected`, not staged. An uploaded/current reference already accepted by the existing owner is `staged`. Missing and extra slots remain separate.

## Context revision

The workshop increments a local revision whenever an observed input, recipe, readiness, gallery, draft-status or visibility event schedules a new projection. The prompt text is not captured. The revision makes an intent stale after the draft changes without leaking the draft itself.

Changing only layout, skin or ambience does not grant new authority. The next projection carries those preferences as presentation metadata.

## Guidance rendering

The guidance rail renders the projected `primaryAction`:

- title;
- short description;
- button label;
- "Why this?" reason;
- optional text-only secondary observations.

The button stores the semantic action ID as `data-intent` for diagnostics and tests. It does not store a selector or executable command.

## Closed local action map

`createActionAdapter()` maps only these known IDs:

- `review-readiness` → reveal the existing readiness disclosure;
- `review-sources` → reveal and focus the existing reference board or file input;
- `inspect-operation` → reveal existing problem/result evidence;
- `resolve-draft-conflict` → reveal the existing draft options when available;
- `focus-generate` → focus and scroll the existing Generate button;
- `open-results` → open and focus the existing Recent runs disclosure.

The adapter checks workspace and current context stamp before invoking a handler. A stale intent returns `stale-context`. There is no submit action.

## Progressive compatibility

The underlying workbench DOM nodes are not cloned or replaced. Existing Focus, Studio and Immersive layouts continue to use one editor. If required DOM or the context module is absent, the enhancement leaves the older interface intact rather than approximating domain state.

## Test contract

The integration must prove:

- shell and prototype script ordering;
- `Context.project()` and `createActionAdapter()` are the only guidance decision/dispatch path;
- blocked, ready, source-attention and output states map to semantic IDs;
- a changed prompt invalidates an older intent without exposing prompt text;
- guidance actions only reveal/focus existing nodes and submit zero jobs;
- presentation combinations preserve prompt and file-input identity;
- the offline exported prototype contains the boundary and makes no network request;
- native application/browser checks still reach the original Generate handler exactly once only after an explicit click.

## Claim limits

Passing tests prove frontend integration against repository fixtures and the existing synthetic API. They do not prove live backend readiness, GPU execution, model compatibility, artistic acceptance or every assistive-technology configuration. Real-machine acceptance remains under #539.
