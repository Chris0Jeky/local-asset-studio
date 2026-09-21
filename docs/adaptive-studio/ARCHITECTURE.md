# Adaptive presentation architecture

**Status: proposed. No production bridge, service or migration is installed by this document.**

## 1. Separate the three planes

```text
Existing domain owners                         Presentation plane
Catalog / graph schema ---------------------> capability snapshot
Workspace / draft / reference ownership ----> contextual snapshot ---> pure projection
Jobs / Production / recovery ---------------> execution evidence          |
Existing guide and shortlist rules ---------> contextual advice           v
                                                               task workspace / guide
UI user command -> existing guarded adapter -> existing domain owner      |
                                                                         v
Appearance preferences + media observations ------------> ambience policy -> renderer
```

Domain state answers what the user has requested and what actually happened. Presentation state answers what to show. Ambience state answers what optional decorative content may be rendered. None may fabricate the others' evidence. No new job queue, workflow compiler, model registry, prompt database or asset Workspace is required.

## 2. Ownership and migration boundaries

| Concern | Existing owner to preserve | Proposed seam |
| --- | --- | --- |
| Create values and restoration | `studio-workbench.js`, `StudioSetupDraft` | Immutable capture plus a versioned context stamp |
| Catalog and bound controls | `app.js`, preset catalog/compiler | Readonly exact-route capability summary |
| Reference semantics | `references.py`, workbench reference records | Ordered display model that keeps IDs and staging state |
| Guide progression | `studio-guide-state.js`, `studio-guide.js` | Reuse evaluation and targets; consolidate duplicate guide presentation |
| Shortlist/proposals | `recipe-shortlist.js`, `setup-proposal.js` | Read result with source identity and context stamp |
| Apply/Undo/recovery | `setup-apply.js`, `studio_workflow/setup_drafts.py` | Existing guarded commands, never a second local approximation |
| Jobs/readiness | Current service and UI owners | Observed status and reasons, no derived execution permission |
| Appearance | Workshop preference mechanism if #540/#541 land | Versioned independent preference migration |
| Decorative media | New bounded presentation-only module | Approved asset IDs, manifests, availability observations and playback policy |

Do not mount a framework above a subtree whose children existing code reparents or rewrites. One DOM subtree has one renderer. During an island trial, only the new island root is framework-owned; original input and run controls remain outside it. A future takeover replaces the old renderer atomically behind a feature flag after exact behavioral parity, rather than synchronizing two editable forms.

## 3. Proposed context contract

The following is an interface sketch for the future adapter, not an implemented public API:

```ts
type Observed<T> =
  | { state: 'unknown'; reason: string }
  | { state: 'known'; value: T; observedAt: number; contextStamp: string };

type StudioContext = {
  version: 1;
  contextStamp: string; // workspace + recipe revision + source revision + backend/schema identity
  taskId: string;
  capability: Observed<{
    recipeId: string; backendId: string;
    controls: readonly string[];
    referenceSlots: readonly { id: string; role: string; required: boolean }[];
    supportsMask: boolean;
  }>;
  execution: Observed<{
    state: 'idle' | 'submitting' | 'running' | 'completed' | 'failed' | 'uncertain';
    operationId: string | null;
    blockers: readonly { code: string; message: string; target: string | null }[];
  }>;
  draft: {
    dirty: boolean; conflict: boolean; pendingFiles: number;
    references: readonly { id: string; role: string; stage: 'selected' | 'checked' | 'staged' }[];
  };
};
```

A checked image is not necessarily staged into ComfyUI, and a role label is not a graph binding. Exact required slot IDs come from the route. Observe IDs and primitive projections, not image bytes or arbitrary filesystem paths, in general guidance state. A future implementation must validate runtime JSON as well as compile-time types.

`project(context, preferences)` returns a display model: stable panel order, visible sections, reason codes and a bounded list of suggested semantic actions. It returns **no executable graph and no submit authorization**. The Generate button continues to use its existing owner, which checks readiness at the command boundary.

## 4. Command boundary and stale-response handling

Presentation can request `reveal-control`, `open-recipe-discovery`, `open-source-picker`, `open-model-setup`, `inspect-operation` and `preview-setup-change`. Existing domain adapters decide whether an explicit apply/write is valid. A skin file or model-generated explanation cannot invent a command ID or pass executable code.

For each observation, capture the context stamp and an incrementing request epoch. Abort obsolete transport when possible; always reject replies whose epoch or workspace/recipe/source/backend identity differs. A to B to A still changes the epoch. An abort is not proof that a mutation did not commit. Read requests can be rechecked explicitly; commands retain the existing request ID and recovery semantics.

Adaptation listens to the existing owner notifications. Coalesce duplicate presentation updates. Do not add separate interval timers per component. Unsubscribe and abort owned reads on unmount. Leaving a view must not dispose a domain-owned in-flight job. An ambience renderer subscribes to job state but never controls it.

## 5. Guidance priority and evidence

Order guidance deterministically:

1. Uncertain operation or conflicting draft needing recovery.
2. Unavailable/stale authoritative information.
3. A missing required input or incompatible requested operation.
4. An explicit task step not yet complete.
5. Optional creative suggestions, only when requested or intentionally enabled.

Each item carries `ruleId`, `contextStamp`, `reason`, `target`, and source/freshness where applicable. Display at most one primary next action and two secondary observations. A dismissed suggestion stays dismissed for that rule and context until a relevant change; dismissal never hides blocking execution evidence.

An optional local/remote language model can later propose wording or classify an explicitly submitted brief. Its response is untrusted advice. Validate against a closed action vocabulary, display the rationale, and preview edits. No LLM is needed for missing-input, offline, disclosure, compatibility or recovery rules. No prompt leaves the device through an ambience, telemetry or media-provider request.

## 6. Persistence and extensibility

Keep drafts in their current workspace-scoped owner. Persist only appearance choices, named task-lens preference and optional dismissed-help identifiers in presentation storage. Avoid storing prompts, File bytes or complete service payloads there. Migration is versioned and allow-listed; malformed data resets presentation only. Storage failure is a usable tab-only mode, not a fatal modal.

A future extension descriptor is data only: ID, localized title, entry capability predicate, registered panel/action IDs, help and asset slot IDs. Unknown fields/capabilities are unavailable, not silently enabled. Start with checked-in descriptors. Do not accept arbitrary plugin JavaScript, remote HTML or CSS in a skin archive.

## 7. Lifecycle and interaction invariants

- Layout/skin/guide-level changes produce zero backend commands and retain prompt/file/control identity.
- Only explicit domain actions can alter selected recipes, source order, staged copies or saved revisions.
- Every modal has one focus owner; success returns to the applied destination, cancel returns to the launcher. Nested close events cannot steal destination focus.
- Blockers retain plain-language text even when an advanced panel is collapsed; invoking a remedy reveals the original control.
- Pending jobs and their receipts survive framework unmount and presentation failure.
- No private draft or API response enters a service-worker media cache. A service worker is not needed for the first island or local-file ambience pilot.
- DOM observers remain transition adapters, not the permanent general-purpose state bus. Each migration removes the observer it supersedes.

## 8. Testing surfaces

Use existing real-frontend synthetic-API fixtures for the production adapter, plus pure projection tests. Cases must include unknown/stale evidence, unsupported extra sources, recipe switching, lost responses, cross-tab conflicts, storage denial, hidden views, IME typing and nested dialogs. Browser tests assert current values and absence of unexpected commands, not just a screenshot.

The separate behavior lab is an executable specification over synthetic state. Passing its tests does not prove production adapter compatibility, real GPU execution, media performance or owner UX acceptance. Carry that distinction in any future PR body and evaluation receipt.
