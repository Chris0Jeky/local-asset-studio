# Read-only presentation context

`app/static/presentation-context.js` is a pure context and intent boundary for future Adaptive Studio presentation code. In this PR it is exercised by Node and Python contracts only. The production shell does not load it yet.

## Why it exists

Current domain owners already know the selected recipe, source roles, draft/recovery state, readiness and output evidence. A presentation component should not duplicate those stores or infer authority from attractive UI state. The boundary converts an explicit snapshot into immutable display data and closed semantic intents.

It deliberately does not:

- read the network or poll the page;
- persist prompts, paths, file objects or model settings;
- select a recipe or rewrite a prompt;
- stage a source;
- submit, retry, cancel or approve a job;
- accept arbitrary CSS selectors, URLs or callback payloads.

## Capturing a snapshot

```js
const Context = window.StudioPresentationContext;
const context = Context.captureContext({
  workspaceId: 'create',
  contextStamp: 'ctx-current-revision',
  taskId: 'pose',
  capability: {
    state: 'known',
    value: {
      recipeId: 'pose-transfer',
      backendId: 'primary',
      referenceSlots: [
        {id: 'identity', role: 'Identity', required: true},
        {id: 'pose', role: 'Pose', required: true}
      ]
    }
  },
  execution: {
    state: 'unknown',
    reason: 'The local readiness owner has not published a fresh observation.'
  },
  draft: {
    dirty: true,
    conflict: false,
    pendingFiles: 1,
    references: [
      {id: 'source-1', slotId: 'identity', role: 'Identity', stage: 'staged'},
      {id: 'source-2', slotId: 'pose', role: 'Pose', stage: 'selected'}
    ]
  }
});
```

The returned object is recursively frozen and contains only the documented primitive fields. Unknown capability or execution evidence remains unknown.

## Projecting guidance

```js
const view = Context.project(context, {
  task: 'pose',
  assistance: 'studio',
  layout: 'immersive',
  skin: 'retro-anime',
  ambience: 'night-shift'
});
```

The result contains:

- exact missing, pending and extra source-role collections;
- one `primaryAction` and optional `secondaryActions`;
- a context/workspace stamp on every action;
- `authorizesSubmission: false`;
- an empty `commands` array.

Presentation preferences may alter wording or arrangement, but never mutate the captured evidence.

## Intent precedence

1. An uncertain or active operation stays primary so the original operation can be inspected.
2. A draft conflict remains visible and becomes primary when no operation requires inspection.
3. Missing, pending or extra source assignments point to source review.
4. Unknown or blocked readiness points to the current readiness details without inventing a backend failure.
5. Existing outputs point to Recent runs.
6. Known ready state may focus Generate, but never activate it.

A simultaneous uncertain operation, draft conflict and source problem retains the latter two as secondary observations.

## Safe local action mapping

A later workshop integration can map closed semantic IDs to existing local reveal/focus functions:

```js
let currentContext = context;
const adapter = Context.createActionAdapter({
  workspaceId: 'create',
  getContextStamp: () => currentContext.contextStamp,
  actions: {
    [Context.ACTIONS.REVIEW_READINESS]: () => reveal(existingReadinessDetails),
    [Context.ACTIONS.REVIEW_SOURCES]: () => reveal(existingReferenceBoard),
    [Context.ACTIONS.FOCUS_GENERATE]: () => existingGenerateButton.focus(),
    [Context.ACTIONS.OPEN_RESULTS]: () => openExistingRecentRuns()
  }
});

const result = adapter.dispatch(view.primaryAction);
```

The adapter rejects unsupported action IDs, another workspace, stale context and missing handlers before calling anything. Handlers receive no selector or arbitrary payload. There is no semantic action for submitting generation.

## Rejecting late observations

```js
const gate = Context.createObservationGate();
const token = gate.begin('create', context.contextStamp);

// After asynchronous read-only evidence returns:
if (gate.accept(token, 'create', currentContext.contextStamp)) {
  // Publish the observation to the real owner or next snapshot.
}
```

The monotonically increasing token rejects a late A result after an A → B → A sequence. Matching text alone does not make an old observation current.

## Context stamps

`makeContextStamp(value)` produces a deterministic local FNV-1a identity string such as `ctx-1a2b3c4d`. It does not expose its input, but it is not encryption, provenance or authorization. Callers should hash only bounded primitive identity data rather than image bytes or complete prompts.

## Qualification boundary

The contracts prove pure normalization, projection and local dispatch guards. They do not prove production script ordering, browser integration, actual readiness, model compatibility, GPU execution, artistic acceptance or usability. A follow-on stacked PR must load the module before `workshop.js`, reuse the workshop's existing observer rather than add polling, and preserve the exact prompt, file-input and Generate nodes.
