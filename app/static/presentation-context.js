/* Pure presentation context. It observes and projects; it never authorizes domain commands. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StudioPresentationContext = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const VERSION = 1;
  const ACTIONS = Object.freeze({
    REVIEW_READINESS:'review-readiness',
    REVIEW_SOURCES:'review-sources',
    INSPECT_OPERATION:'inspect-operation',
    RESOLVE_DRAFT_CONFLICT:'resolve-draft-conflict',
    FOCUS_GENERATE:'focus-generate',
    OPEN_RESULTS:'open-results'
  });
  const ACTION_IDS = new Set(Object.values(ACTIONS));
  const EXECUTION_STATES = new Set([
    'blocked','ready','uncertain','submitting','running','waiting','queued',
    'completed','failed','cancelled'
  ]);
  const ACTIVE_STATES = new Set(['uncertain','submitting','running','waiting','queued']);
  const REFERENCE_STAGES = new Set(['selected','checked','staged']);
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);

  function cleanText(value, fallback = '', max = 400) {
    if (typeof value !== 'string') return fallback;
    const text = value.trim();
    return text ? text.slice(0, max) : fallback;
  }

  function token(value, fallback = null, max = 128) {
    const text = cleanText(value, '', max);
    return text && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(text) ? text : fallback;
  }

  function count(value, fallback = 0, max = 10000) {
    const number = Number(value);
    return Number.isSafeInteger(number) && number >= 0 ? Math.min(number, max) : fallback;
  }

  function deepFreeze(value) {
    if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
    for (const item of Object.values(value)) deepFreeze(item);
    return Object.freeze(value);
  }

  function stableValue(value, seen = new Set()) {
    if (value === null || ['string','number','boolean'].includes(typeof value)) return value;
    if (Array.isArray(value)) return value.map(item => stableValue(item, seen));
    if (!object(value) || seen.has(value)) return null;
    seen.add(value);
    const result = {};
    for (const key of Object.keys(value).sort()) {
      const item = value[key];
      if (typeof item === 'undefined' || typeof item === 'function' || typeof item === 'symbol') continue;
      result[key] = stableValue(item, seen);
    }
    seen.delete(value);
    return result;
  }

  function makeContextStamp(value) {
    const source = JSON.stringify(stableValue(value));
    let hash = 0x811c9dc5;
    for (let index = 0; index < source.length; index++) {
      hash ^= source.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return 'ctx-' + hash.toString(16).padStart(8, '0');
  }

  function unknown(reason, fallback) {
    return {state:'unknown', reason:cleanText(reason, fallback), value:null};
  }

  function normalizeCapability(input) {
    if (!object(input) || input.state === 'unknown')
      return unknown(input?.reason, 'Recipe capability has not been observed.');
    const value = input.state === 'known' ? input.value : input;
    if (!object(value)) return unknown(null, 'Recipe capability is malformed.');
    const recipeId = token(value.recipeId);
    const backendId = token(value.backendId);
    if (!recipeId || !backendId) return unknown(null, 'Recipe or backend identity is unavailable.');
    const slots = [], ids = new Set();
    if (value.referenceSlots !== undefined && !Array.isArray(value.referenceSlots))
      return unknown(null, 'Reference-slot capability is malformed.');
    for (const [index, raw] of (value.referenceSlots || []).slice(0, 32).entries()) {
      if (!object(raw)) return unknown(null, 'Reference-slot capability is malformed.');
      const id = token(raw.id);
      if (!id || ids.has(id)) return unknown(null, 'Reference-slot identities are missing or duplicated.');
      ids.add(id);
      slots.push({id, role:cleanText(raw.role, 'Reference ' + (index + 1), 120), required:raw.required !== false});
    }
    return {state:'known', reason:null, value:{recipeId, backendId, referenceSlots:slots}};
  }

  function normalizeExecution(input) {
    if (!object(input) || input.state === 'unknown') {
      const value = unknown(input?.reason, 'Execution readiness has not been observed.');
      return {...value, observedAt:null, contextStamp:null};
    }
    const raw = input.state === 'known' ? input.value : input;
    if (!object(raw) || !EXECUTION_STATES.has(raw.state)) {
      const value = unknown(null, 'Execution evidence is malformed or unsupported.');
      return {...value, observedAt:null, contextStamp:null};
    }
    const blockers = [];
    if (raw.blockers !== undefined && !Array.isArray(raw.blockers)) {
      const value = unknown(null, 'Execution blockers are malformed.');
      return {...value, observedAt:null, contextStamp:null};
    }
    for (const [index, blocker] of (raw.blockers || []).slice(0, 32).entries()) {
      if (!object(blocker)) continue;
      blockers.push({
        code:token(blocker.code, 'blocker-' + (index + 1)),
        message:cleanText(blocker.message, 'Readiness needs attention.'),
        target:token(blocker.target)
      });
    }
    const observedAt = Number(input.observedAt);
    return {
      state:'known', reason:null,
      observedAt:Number.isFinite(observedAt) && observedAt >= 0 ? observedAt : null,
      contextStamp:token(input.contextStamp),
      value:{
        state:raw.state,
        operationId:token(raw.operationId),
        blockers,
        outputs:count(raw.outputs)
      }
    };
  }

  function normalizeDraft(input) {
    const source = object(input) ? input : {};
    const references = [];
    for (const [index, raw] of (Array.isArray(source.references) ? source.references : []).slice(0, 64).entries()) {
      if (!object(raw)) continue;
      references.push({
        id:token(raw.id, 'reference-' + (index + 1)),
        slotId:token(raw.slotId),
        role:cleanText(raw.role, 'Reference ' + (index + 1), 120),
        stage:REFERENCE_STAGES.has(raw.stage) ? raw.stage : 'selected'
      });
    }
    return {
      dirty:source.dirty === true,
      conflict:source.conflict === true,
      pendingFiles:count(source.pendingFiles, 0, 128),
      references
    };
  }

  function captureContext(input = {}) {
    const source = object(input) ? input : {};
    const capability = normalizeCapability(source.capability);
    const execution = normalizeExecution(source.execution);
    const draft = normalizeDraft(source.draft);
    const workspaceId = token(source.workspaceId, 'workspace');
    const taskId = token(source.taskId, 'generate');
    const stampSource = {workspaceId, taskId, capability, execution, draft};
    const contextStamp = token(source.contextStamp, makeContextStamp(stampSource));
    return deepFreeze({version:VERSION, workspaceId, contextStamp, taskId, capability, execution, draft});
  }

  function summarizeSources(context) {
    if (context.capability.state !== 'known') {
      return deepFreeze({state:'unknown', required:[], provided:[], missing:[], pending:[], extra:[]});
    }
    const slots = context.capability.value.referenceSlots;
    const slotMap = new Map(slots.map(slot => [slot.id, slot]));
    const assigned = new Map(), extra = [];
    for (const reference of context.draft.references) {
      if (!reference.slotId || !slotMap.has(reference.slotId) || assigned.has(reference.slotId)) {
        extra.push(reference);
        continue;
      }
      assigned.set(reference.slotId, reference);
    }
    const required = slots.filter(slot => slot.required), missing = [], pending = [], provided = [];
    for (const slot of slots) {
      const reference = assigned.get(slot.id);
      if (!reference) {
        if (slot.required) missing.push(slot);
        continue;
      }
      if (reference.stage === 'staged') provided.push(reference);
      else {
        pending.push(reference);
        if (slot.required) missing.push(slot);
      }
    }
    const state = missing.length || pending.length || extra.length ? 'attention'
      : slots.length ? 'satisfied' : 'not-required';
    return deepFreeze({state, required, provided, missing, pending, extra});
  }

  function intent(context, id, title, label, description, reason) {
    return deepFreeze({
      id, title, label,
      description:cleanText(description, 'Review the current Studio evidence.'),
      reason:cleanText(reason, 'Derived from the current read-only context.'),
      workspaceId:context.workspaceId,
      contextStamp:context.contextStamp
    });
  }

  function project(contextInput, preferences = {}) {
    const context = captureContext(contextInput);
    const sources = summarizeSources(context);
    const secondary = [];
    let execution = context.execution;
    if (context.capability.state === 'unknown') {
      execution = {...unknown(context.capability.reason, 'Recipe capability has not been observed.'), observedAt:null, contextStamp:null};
    } else if (execution.state === 'known' && execution.contextStamp && execution.contextStamp !== context.contextStamp) {
      execution = {...unknown('Execution evidence belongs to an older context. Recheck the current workspace.', 'Execution evidence is stale.'), observedAt:null, contextStamp:null};
    }
    const state = execution.state === 'known' ? execution.value.state : 'unknown';
    const sourceIntent = () => intent(
      context, ACTIONS.REVIEW_SOURCES, 'Review the source roles', 'Review sources',
      sources.missing.length ? 'Attach or stage every required source role before continuing.'
        : sources.pending.length ? 'Some selected sources are not staged yet.'
          : 'One or more sources do not match an available recipe slot.',
      'Exact slot identities, pending staging and extra assignments are kept separate.'
    );
    const conflictIntent = () => intent(
      context, ACTIONS.RESOLVE_DRAFT_CONFLICT, 'Resolve the draft conflict', 'Review draft conflict',
      'A competing draft revision is still present. Review it before another domain action.',
      'The context reports a draft conflict; presentation does not choose a winner.'
    );
    const inspectIntent = () => intent(
      context, ACTIONS.INSPECT_OPERATION, 'Inspect the original operation', 'Inspect operation',
      execution.value?.operationId ? 'Operation ' + execution.value.operationId + ' is ' + state + '. Keep its identity and inspect it before another attempt.'
        : 'The current operation is ' + state + '. Inspect its existing evidence before another attempt.',
      'Active and uncertain operations take precedence over replacement or retry suggestions.'
    );

    let primary;
    if (execution.state === 'known' && ACTIVE_STATES.has(state)) {
      primary = inspectIntent();
      if (context.draft.conflict) secondary.push(conflictIntent());
      if (sources.state === 'attention') secondary.push(sourceIntent());
    } else if (context.draft.conflict) {
      primary = conflictIntent();
      if (sources.state === 'attention') secondary.push(sourceIntent());
    } else if (sources.state === 'attention') {
      primary = sourceIntent();
    } else if (execution.state === 'unknown') {
      primary = intent(
        context, ACTIONS.REVIEW_READINESS, 'Readiness is not known', 'Review readiness',
        execution.reason, 'Missing evidence is not converted into a backend failure or a ready state.'
      );
    } else if (state === 'blocked') {
      const blocker = execution.value.blockers[0]?.message;
      primary = intent(
        context, ACTIONS.REVIEW_READINESS, 'Resolve the next blocker', 'Review readiness',
        blocker || 'Open the existing readiness details to see what the current recipe still needs.',
        'This uses the current readiness owner and does not invent a new prerequisite.'
      );
    } else if (execution.value.outputs > 0) {
      primary = intent(
        context, ACTIONS.OPEN_RESULTS, 'Review the latest result', 'Open recent runs',
        execution.value.outputs + ' output' + (execution.value.outputs === 1 ? ' is' : 's are') + ' recorded in the current context.',
        'The intent opens the existing result surface and does not select or approve an output.'
      );
    } else if (state === 'ready') {
      primary = intent(
        context, ACTIONS.FOCUS_GENERATE, 'Ready when you are', 'Focus Generate',
        'The existing Generate control is reported ready. Focusing it does not submit a job.',
        'Known ready state permits a focus intent, never submission authority.'
      );
    } else {
      primary = inspectIntent();
    }

    const seen = new Set([primary.id]);
    const secondaryActions = secondary.filter(item => !seen.has(item.id) && seen.add(item.id));
    const evidenceState = execution.state === 'unknown' ? 'unknown'
      : ACTIVE_STATES.has(state) ? 'active'
        : context.draft.conflict || sources.state === 'attention' || state === 'blocked' ? 'attention'
          : execution.value.outputs > 0 ? 'outputs'
            : state === 'ready' ? 'ready' : 'observed';
    const presentation = {
      task:token(preferences.task, context.taskId),
      assistance:token(preferences.assistance, 'studio'),
      layout:token(preferences.layout),
      skin:token(preferences.skin),
      ambience:token(preferences.ambience)
    };
    return deepFreeze({
      version:VERSION,
      workspaceId:context.workspaceId,
      contextStamp:context.contextStamp,
      taskId:context.taskId,
      presentation,
      evidenceState,
      sourceSummary:sources,
      primaryAction:primary,
      secondaryActions,
      authorizesSubmission:false,
      commands:[]
    });
  }

  function createActionAdapter(options = {}) {
    const workspaceId = token(options.workspaceId, 'workspace');
    const currentStamp = typeof options.getContextStamp === 'function' ? options.getContextStamp : () => null;
    const handlers = new Map();
    if (object(options.actions)) {
      for (const [id, handler] of Object.entries(options.actions))
        if (ACTION_IDS.has(id) && typeof handler === 'function') handlers.set(id, handler);
    }
    return Object.freeze({
      dispatch(intentValue) {
        const value = object(intentValue) ? intentValue : {};
        if (!ACTION_IDS.has(value.id)) return {ok:false, reason:'unsupported-action'};
        if (value.workspaceId !== workspaceId) return {ok:false, reason:'cross-workspace'};
        if (value.contextStamp !== token(currentStamp())) return {ok:false, reason:'stale-context'};
        const handler = handlers.get(value.id);
        if (!handler) return {ok:false, reason:'unavailable-action'};
        try { handler(); return {ok:true, id:value.id}; }
        catch (_) { return {ok:false, reason:'handler-failed'}; }
      }
    });
  }

  function createObservationGate() {
    let epoch = 0, latest = null;
    return Object.freeze({
      begin(workspaceId, contextStamp) {
        latest = deepFreeze({workspaceId:token(workspaceId, 'workspace'), contextStamp:token(contextStamp, 'ctx-unknown'), epoch:++epoch});
        return latest;
      },
      accept(candidate, workspaceId, contextStamp) {
        return !!candidate && !!latest && candidate.epoch === latest.epoch
          && candidate.workspaceId === latest.workspaceId && candidate.contextStamp === latest.contextStamp
          && latest.workspaceId === token(workspaceId, 'workspace')
          && latest.contextStamp === token(contextStamp, 'ctx-unknown');
      }
    });
  }

  return Object.freeze({
    VERSION, ACTIONS, captureContext, project, summarizeSources,
    createActionAdapter, createObservationGate, makeContextStamp
  });
});
