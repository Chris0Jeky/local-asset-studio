# Read-only presentation context

`app/static/presentation-context.js` is the pure, immutable observation and intent boundary used by the production Create workshop. `studio-shell.js` loads it before `workshop.js`; the offline workshop prototype and exporter keep the same order.

The boundary does not own editable state or execution. Existing recipe, reference, draft, readiness, job and result owners publish bounded primitive observations. The boundary normalizes those observations, projects one primary intent plus optional secondary observations, and rejects stale or cross-workspace dispatch.

## What it never does

It does not:

- read the network or poll the page;
- persist prompts, paths, file objects, model settings or credentials;
- select a recipe or rewrite a prompt;
- stage, remove or relabel a source;
- submit, retry, cancel or approve a job;
- accept arbitrary selectors, URLs, callback payloads or model-generated commands.

Every projection returns `authorizesSubmission: false` and an empty `commands` array.

## Production capture

The workshop captures one snapshot during its existing scheduled `sync()` pass. It adds no second observer or timer. The snapshot contains:

- workspace and task identity;
- selected recipe and backend identity when known;
- exact source-slot IDs, human-readable roles and required flags from `reference-model.js`;
- source records expressed only as bounded IDs, slot IDs, roles and `selected` / `checked` / `staged` stages;
- pending-file count from the shared reference projection;
- current Generate readiness, the first existing blocker and current result count;
- `conflict: false` until an existing draft owner explicitly publishes a conflict observation.

Prompt text, file paths and image bytes never enter the context stamp or frozen projection. A monotonically increasing local revision makes an older intent stale after relevant UI evidence changes.

## Source projection

`reference-model.js` is the single owner of reference readiness semantics. The presentation bridge consumes its slots, references, pending count and `hasSources` result. It does not re-derive `reference_slots`, `last_reference`, board cardinality or staging.

The projected source summary keeps these cases distinct:

- required role with no selected source;
- selected source still checking or staging;
- staged source;
- source that does not match an available slot;
- optional source role with no source.

## Intent precedence

The pure module supports a wider vocabulary for consumers that can publish the corresponding evidence:

1. active or uncertain operation inspection;
2. draft-conflict review;
3. missing, pending or extra source review;
4. unknown or blocked readiness review;
5. existing output review;
6. known-ready Generate focus.

Unknown evidence remains unknown. The projection does not convert absence of evidence into backend failure or readiness.

## Production-reachable actions

The current production workshop captures only `blocked`, `ready` or `completed` execution and does not claim a draft conflict. Its closed action adapter therefore registers only four actions that the current capture can emit:

- `review-readiness` reveals the existing readiness disclosure;
- `review-sources` focuses the exact outstanding existing file input or source board;
- `focus-generate` focuses and scrolls the existing Generate button without activating it;
- `open-results` opens and focuses the existing Recent runs disclosure.

The pure boundary still defines `inspect-operation` and `resolve-draft-conflict` for tests and future consumers. Production does not register those handlers until the existing job or draft owner exposes matching observations. Keeping an action in the pure vocabulary is not a claim that the current Create capture can emit it.

## Safe local dispatch

```js
const adapter = Context.createActionAdapter({
  workspaceId: 'create',
  getContextStamp: () => currentView.contextStamp,
  actions: {
    [Context.ACTIONS.REVIEW_READINESS]: () => reveal(existingReadinessDetails),
    [Context.ACTIONS.REVIEW_SOURCES]: () => focusOutstandingExistingSource(),
    [Context.ACTIONS.FOCUS_GENERATE]: () => existingGenerateButton.focus(),
    [Context.ACTIONS.OPEN_RESULTS]: () => openExistingRecentRuns()
  }
});

const result = adapter.dispatch(currentView.primaryAction);
```

The adapter rejects unsupported action IDs, another workspace, stale context and missing handlers before invoking anything. Handlers receive no arbitrary payload. There is no submission action.

## Context stamps and late observations

`makeContextStamp(value)` produces a deterministic local FNV-1a identity over bounded primitive identity data. It is not encryption, provenance or authorization.

`createObservationGate()` supplies monotonically increasing tokens so a delayed A result is rejected after an A → B → A sequence. Matching text alone does not make an old observation current.

## Qualification boundary

Node contracts prove normalization, immutability, precedence, guarded dispatch and freshness. Browser and native-application tests prove script ordering, original-node identity, source focus, stale-intent rejection and zero implicit submissions against repository fixtures. They do not prove live backend readiness, GPU execution, model compatibility, artistic acceptance or every assistive-technology configuration. Real-machine acceptance remains under #539.
