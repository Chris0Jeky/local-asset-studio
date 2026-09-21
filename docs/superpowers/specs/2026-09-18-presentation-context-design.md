# Read-only Presentation Context Boundary

**Date:** 18 September 2026  
**Status:** approved continuation of the Adaptive Studio and Immersive Studio direction  
**Parent implementation:** PR #574, `codex/immersive-studio-presentation`

## Goal

Add a small, deterministic boundary that converts existing domain observations into immutable presentation context and bounded semantic intents. It must help presentation code explain the next useful action without gaining authority to generate, retry, change recipes, stage files or mutate drafts.

## Scope

This slice adds a pure JavaScript module and regression contracts. It does not change a production default, install a framework, add network activity or replace an existing editor, guide, readiness owner or command handler.

The module has four responsibilities:

1. Normalize an allow-listed context snapshot.
2. Project that snapshot into one primary presentation intent and optional secondary observations.
3. Dispatch only closed semantic actions after workspace and context-stamp checks.
4. Reject obsolete asynchronous observations, including A-B-A context changes.

## Context contract

`captureContext(input)` returns a frozen object with this shape:

```js
{
  version: 1,
  workspaceId: 'create',
  contextStamp: 'ctx-…',
  taskId: 'generate',
  capability: {
    state: 'known' | 'unknown',
    reason: String | null,
    value: {
      recipeId: String,
      backendId: String,
      referenceSlots: [{id, role, required}]
    } | null
  },
  execution: {
    state: 'known' | 'unknown',
    reason: String | null,
    observedAt: Number | null,
    contextStamp: String | null,
    value: {
      state: 'blocked' | 'ready' | 'uncertain' | 'submitting' | 'running' |
             'waiting' | 'queued' | 'completed' | 'failed' | 'cancelled',
      operationId: String | null,
      blockers: [{code, message, target}],
      outputs: Number
    } | null
  },
  draft: {
    dirty: Boolean,
    conflict: Boolean,
    pendingFiles: Number,
    references: [{id, slotId, role, stage: 'selected' | 'checked' | 'staged'}]
  }
}
```

Unknown evidence remains unknown. The boundary never converts a missing observation into a backend failure or a readiness claim. Input fields outside the contract, including prompt text, filesystem paths, credentials and image bytes, are discarded.

## Source projection

`project(context, preferences)` compares exact reference-slot identities with draft references. It reports missing required slots, selected or checked references that are not staged, and extra or duplicate source assignments separately.

A task or appearance preference may change presentation wording, but cannot alter capability, execution or draft evidence. Projection is pure and returns `authorizesSubmission: false`, an empty `commands` array and data-only action intents.

## Intent precedence

The primary intent uses this precedence:

1. An uncertain or active operation remains primary and points to inspection of the original operation.
2. A draft conflict is primary when no operation needs inspection.
3. Missing, pending or extra sources point to the existing source-review surface.
4. Unknown or blocked readiness points to existing readiness details without claiming the backend is down.
5. Existing outputs point to the existing Recent runs surface.
6. Known ready state may focus the existing Generate control, but never activate it.

Lower-priority conditions remain available as secondary observations. A simultaneous uncertain operation and draft conflict must retain both facts.

## Semantic action adapter

`createActionAdapter({workspaceId, getContextStamp, actions})` accepts only the module's fixed action IDs. Dispatch rejects:

- unsupported action IDs;
- intents from another workspace;
- intents created for an older context stamp;
- allow-listed actions without a registered local handler.

Handlers receive no untrusted selector, URL, prompt or arbitrary payload. There is deliberately no submission, retry, recipe-selection or file-staging action ID.

## Observation freshness

`createObservationGate()` issues a monotonically increasing token for each observation attempt. A result is accepted only when its token is still the latest and its workspace/context stamp still matches. Returning from context A to B and then to A does not make the first A result current again.

## Context stamps

`makeContextStamp(value)` creates a deterministic local hash. It is an identity aid, not security, storage or provenance evidence. The hash does not expose its source text and must not be treated as authorization.

## Qualification

Required evidence for this slice:

- Node contracts covering immutability, allow-listing, unknown evidence, source identity and overflow, intent precedence, semantic dispatch, cross-workspace rejection, stale-context rejection and A-B-A freshness.
- Normal Python unittest discovery invokes the Node contracts when Node is available.
- Repository validation and relevant hosted checks remain green on the published head.
- The PR remains stacked on #574 and makes no claim of live GPU, frontend integration or owner usability acceptance.

## Follow-on integration

A later stacked slice may load this module before `workshop.js` and replace the current inline guidance projection with `captureContext()` and `project()`. That integration must reuse the workshop's existing mutation observer rather than adding another polling loop, map semantic action IDs to existing reveal/focus functions, and preserve the exact prompt, file-input and Generate nodes.
