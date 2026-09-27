'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const C = require('../app/static/presentation-context.js');

const knownExecution = (state, patch = {}) => ({
  state:'known', observedAt:100, contextStamp:'ctx-1',
  value:{state, operationId:null, blockers:[], outputs:0, ...patch}
});
const baseInput = () => ({
  workspaceId:'create', contextStamp:'ctx-1', taskId:'generate',
  capability:{state:'known', value:{recipeId:'image', backendId:'primary', referenceSlots:[]}},
  execution:knownExecution('ready'),
  draft:{dirty:false, conflict:false, pendingFiles:0, references:[]}
});

test('captureContext is immutable, allow-listed and strips private fields', () => {
  const input = {...baseInput(), prompt:'private prompt', filePath:'C:/private/source.png'};
  const before = structuredClone(input);
  const context = C.captureContext(input);
  assert.deepEqual(input, before);
  assert.equal(Object.isFrozen(context), true);
  assert.equal(context.version, 1);
  assert.doesNotMatch(JSON.stringify(context), /private prompt|source\.png/);
  assert.equal(context.workspaceId, 'create');
});

test('unknown execution remains unknown instead of becoming a blocker or readiness claim', () => {
  const input = baseInput();
  input.execution = {state:'unknown', reason:'No fresh backend observation.'};
  const view = C.project(C.captureContext(input), {skin:'retro-anime', task:'pose'});
  assert.equal(view.evidenceState, 'unknown');
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_READINESS);
  assert.match(view.primaryAction.description, /No fresh backend observation/);
  assert.equal(view.authorizesSubmission, false);
});

test('task and skin changes only affect presentation and never create commands', () => {
  const context = C.captureContext(baseInput());
  const before = structuredClone(context);
  const a = C.project(context, {task:'pose', skin:'retro-anime'});
  const b = C.project(context, {task:'compare', skin:'atelier'});
  assert.deepEqual(context, before);
  assert.equal(a.authorizesSubmission, false);
  assert.equal(b.authorizesSubmission, false);
  assert.deepEqual(a.commands, []);
  assert.deepEqual(b.commands, []);
  assert.equal(typeof a.primaryAction.execute, 'undefined');
});

test('required source slot identity, pending staging and overflow remain distinct', () => {
  const input = baseInput();
  input.taskId = 'pose';
  input.capability.value.referenceSlots = [
    {id:'identity', role:'Identity', required:true},
    {id:'pose', role:'Pose', required:true}
  ];
  input.draft.references = [
    {id:'identity-source', slotId:'identity', role:'Identity', stage:'staged'},
    {id:'pose-source', slotId:'pose', role:'Pose', stage:'selected'},
    {id:'style-source', slotId:'style', role:'Style', stage:'staged'}
  ];
  const view = C.project(C.captureContext(input), {});
  assert.deepEqual(view.sourceSummary.missing.map(x => x.id), ['pose']);
  assert.deepEqual(view.sourceSummary.pending.map(x => x.id), ['pose-source']);
  assert.deepEqual(view.sourceSummary.extra.map(x => x.id), ['style-source']);
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_SOURCES);
});

test('an uncertain operation stays primary while draft conflict and source issues remain visible', () => {
  const input = baseInput();
  input.execution = knownExecution('uncertain', {operationId:'op-7'});
  input.draft.conflict = true;
  input.capability.value.referenceSlots = [{id:'identity', role:'Identity', required:true}];
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.primaryAction.id, C.ACTIONS.INSPECT_OPERATION);
  assert.ok(view.secondaryActions.some(x => x.id === C.ACTIONS.RESOLVE_DRAFT_CONFLICT));
  assert.ok(view.secondaryActions.some(x => x.id === C.ACTIONS.REVIEW_SOURCES));
});

test('blocked, ready and completed-output observations map to bounded semantic intents', () => {
  const blocked = baseInput();
  blocked.execution = knownExecution('blocked', {blockers:[{code:'model-missing', message:'Install the selected model.', target:'models'}]});
  assert.equal(C.project(C.captureContext(blocked), {}).primaryAction.id, C.ACTIONS.REVIEW_READINESS);
  const ready = baseInput();
  assert.equal(C.project(C.captureContext(ready), {}).primaryAction.id, C.ACTIONS.FOCUS_GENERATE);
  const outputs = baseInput();
  outputs.execution = knownExecution('completed', {outputs:2});
  assert.equal(C.project(C.captureContext(outputs), {}).primaryAction.id, C.ACTIONS.OPEN_RESULTS);
});

test('semantic adapter rejects unsupported, cross-workspace and stale intents before dispatch', () => {
  let calls = 0, stamp = 'ctx-1';
  const adapter = C.createActionAdapter({
    workspaceId:'create', getContextStamp:() => stamp,
    actions:{[C.ACTIONS.REVIEW_READINESS]:() => { calls++; }}
  });
  assert.deepEqual(adapter.dispatch({id:'submit-generation', workspaceId:'create', contextStamp:'ctx-1'}), {ok:false, reason:'unsupported-action'});
  assert.deepEqual(adapter.dispatch({id:C.ACTIONS.REVIEW_READINESS, workspaceId:'assets', contextStamp:'ctx-1'}), {ok:false, reason:'cross-workspace'});
  stamp = 'ctx-2';
  assert.deepEqual(adapter.dispatch({id:C.ACTIONS.REVIEW_READINESS, workspaceId:'create', contextStamp:'ctx-1'}), {ok:false, reason:'stale-context'});
  assert.equal(calls, 0);
  assert.deepEqual(adapter.dispatch({id:C.ACTIONS.REVIEW_READINESS, workspaceId:'create', contextStamp:'ctx-2'}), {ok:true, id:C.ACTIONS.REVIEW_READINESS});
  assert.equal(calls, 1);
});

test('A-B-A observation gate rejects the first A result after context returns to A', () => {
  const gate = C.createObservationGate();
  const a1 = gate.begin('create', 'ctx-a');
  gate.begin('create', 'ctx-b');
  const a2 = gate.begin('create', 'ctx-a');
  assert.equal(gate.accept(a1, 'create', 'ctx-a'), false);
  assert.equal(gate.accept(a2, 'create', 'ctx-a'), true);
  assert.equal(gate.accept(a2, 'other', 'ctx-a'), false);
});

test('context stamps are deterministic hashes and do not expose source material', () => {
  const source = {recipe:'image', prompt:'private wording', path:'C:/secret.png'};
  const a = C.makeContextStamp(source), b = C.makeContextStamp({...source});
  assert.equal(a, b);
  assert.match(a, /^ctx-[0-9a-f]{8}$/);
  assert.doesNotMatch(a, /private|secret/);
});

test('unknown capability prevents a ready-looking execution observation from becoming a Generate intent', () => {
  const input = baseInput();
  input.capability = {state:'unknown', reason:'Recipe bindings are still loading.'};
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.evidenceState, 'unknown');
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_READINESS);
  assert.match(view.primaryAction.description, /Recipe bindings are still loading/);
});

test('execution evidence from an older context stamp is treated as stale unknown evidence', () => {
  const input = baseInput();
  input.contextStamp = 'ctx-current';
  input.execution = {...knownExecution('ready'), contextStamp:'ctx-old'};
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.evidenceState, 'unknown');
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_READINESS);
  assert.match(view.primaryAction.description, /older context/i);
});

test('pending file work remains source attention even before a slot record exists', () => {
  const input = baseInput();
  input.draft.pendingFiles = 1;
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.sourceSummary.pendingFiles, 1);
  assert.equal(view.sourceSummary.state, 'attention');
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_SOURCES);
  assert.match(view.primaryAction.description, /pending/i);
});

test('context stamps safely normalize cyclic arrays without leaking source material', () => {
  const cyclic = [];
  cyclic.push('private', cyclic);
  const stamp = C.makeContextStamp({cyclic});
  assert.match(stamp, /^ctx-[0-9a-f]{8}$/);
  assert.doesNotMatch(stamp, /private/);
});

test('unknown capability does not erase a known uncertain operation identity', () => {
  const input = baseInput();
  input.capability = {state:'unknown', reason:'Recipe bindings are refreshing.'};
  input.execution = knownExecution('uncertain', {operationId:'op-still-running'});
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.evidenceState, 'active');
  assert.equal(view.primaryAction.id, C.ACTIONS.INSPECT_OPERATION);
  assert.match(view.primaryAction.description, /op-still-running/);
});

test('draft conflict keeps a simultaneous blocked readiness action visible', () => {
  const input = baseInput();
  input.draft.conflict = true;
  input.execution = knownExecution('blocked', {
    blockers:[{code:'model-missing', message:'Install the selected model.', target:'models'}]
  });
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.primaryAction.id, C.ACTIONS.RESOLVE_DRAFT_CONFLICT);
  const readiness = view.secondaryActions.find(action => action.id === C.ACTIONS.REVIEW_READINESS);
  assert.ok(readiness);
  assert.match(readiness.description, /Install the selected model/);
});

test('source attention keeps simultaneous unknown readiness visible', () => {
  const input = baseInput();
  input.draft.pendingFiles = 1;
  input.execution = {state:'unknown', reason:'No fresh backend observation.'};
  const view = C.project(C.captureContext(input), {});
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_SOURCES);
  const readiness = view.secondaryActions.find(action => action.id === C.ACTIONS.REVIEW_READINESS);
  assert.ok(readiness);
  assert.match(readiness.description, /No fresh backend observation/);
});

test('the adapter isolates a missing handler and a throwing handler', () => {
  const stamp = 'ctx-1';
  const adapter = C.createActionAdapter({workspaceId:'create', getContextStamp:() => stamp,
    actions:{[C.ACTIONS.OPEN_RESULTS]:() => { throw new Error('private handler detail'); }}});
  const intent = id => ({id, workspaceId:'create', contextStamp:stamp});
  assert.deepEqual(adapter.dispatch(intent(C.ACTIONS.FOCUS_GENERATE)), {ok:false, reason:'unavailable-action'});
  assert.deepEqual(adapter.dispatch(intent(C.ACTIONS.OPEN_RESULTS)), {ok:false, reason:'handler-failed'});
});

test('terminal observations map to intents, evidence states and singular wording', () => {
  const project = (state, outputs) => {
    const input = baseInput(); input.execution = knownExecution(state, {outputs});
    return C.project(C.captureContext(input), {});
  };
  const one = project('completed', 1);
  assert.equal(one.primaryAction.id, C.ACTIONS.OPEN_RESULTS);
  assert.match(one.primaryAction.description, /^1 output is recorded/);
  assert.equal(one.evidenceState, 'outputs');
  assert.match(project('completed', 3).primaryAction.description, /^3 outputs are recorded/);
  for (const state of ['failed', 'cancelled']) {
    const view = project(state, 0);
    assert.equal(view.primaryAction.id, C.ACTIONS.INSPECT_OPERATION, state);
    assert.equal(view.evidenceState, 'observed', state);
  }
  const done = project('completed', 0);
  assert.equal(done.primaryAction.id, C.ACTIONS.INSPECT_OPERATION);
  assert.equal(done.evidenceState, 'observed');
  assert.equal(project('ready', 0).evidenceState, 'ready');
});

test('malformed capability becomes unknown instead of passing as known', () => {
  const capability = value => {
    const input = baseInput(); input.capability = {state:'known', value};
    return C.captureContext(input).capability;
  };
  for (const value of ['recipe', {recipeId:null, backendId:'primary'}, {recipeId:'image', backendId:''},
                       {recipeId:'image', backendId:'primary', referenceSlots:'a'},
                       {recipeId:'image', backendId:'primary', referenceSlots:[null]},
                       {recipeId:'image', backendId:'primary', referenceSlots:[{id:'a'}, {id:'a'}]},
                       {recipeId:'image', backendId:'primary', referenceSlots:[{role:'no id'}]}]) {
    assert.equal(capability(value).state, 'unknown', JSON.stringify(value));
  }
  assert.deepEqual(capability({recipeId:'image', backendId:'primary', referenceSlots:[{id:'a'}]}).value.referenceSlots,
    [{id:'a', role:'Reference 1', required:true}]);
});

test('malformed execution normalizes safely', () => {
  const execution = (value, extra = {}) => {
    const input = baseInput(); input.execution = {state:'known', ...extra, value};
    return C.captureContext(input).execution;
  };
  assert.equal(execution({state:'dancing'}).state, 'unknown');
  assert.equal(execution({state:'ready', blockers:'x'}).state, 'unknown');
  const normalized = execution({state:'blocked', blockers:[null, {}, {code:'bad code!', message:'  ', target:'models'}], outputs:'many'},
    {observedAt:-5, contextStamp:'not a token!'});
  assert.equal(normalized.state, 'known');
  assert.deepEqual(normalized.value.blockers, [
    {code:'blocker-2', message:'Readiness needs attention.', target:null},
    {code:'blocker-3', message:'Readiness needs attention.', target:'models'}]);
  assert.equal(normalized.observedAt, null);
  assert.equal(normalized.contextStamp, null);
  assert.equal(normalized.value.outputs, 0);
  assert.equal(execution({state:'ready'}, {observedAt:Number.NaN}).observedAt, null);
});

test('stamps are key-order stable and ignore non-data fields', () => {
  assert.equal(C.makeContextStamp({a:1, b:[2, 3]}), C.makeContextStamp({b:[2, 3], a:1}));
  assert.equal(C.makeContextStamp({a:1, f:() => 1, s:Symbol('x'), u:undefined}), C.makeContextStamp({a:1}));
  const cyclic = {a:1}; cyclic.self = cyclic;
  assert.match(C.makeContextStamp(cyclic), /^ctx-[0-9a-f]{8}$/);
  assert.notEqual(C.makeContextStamp({a:1}), C.makeContextStamp({a:2}));
});

test('draft and capture defaults clamp safely', () => {
  const draft = value => { const input = baseInput(); input.draft = value; return C.captureContext(input).draft; };
  assert.equal(draft({pendingFiles:-1}).pendingFiles, 0);
  assert.equal(draft({pendingFiles:9999}).pendingFiles, 128);
  assert.equal(draft({pendingFiles:'x'}).pendingFiles, 0);
  const references = draft({references:[null, {id:'bad id!', stage:'bogus'}, ...Array.from({length:80}, (_, i) => ({id:'r' + i}))]}).references;
  assert.equal(references.length, 63, 'at most 64 raw entries are read; the null one is skipped');
  assert.deepEqual(references[0], {id:'reference-2', slotId:null, role:'Reference 2', stage:'selected'});
  const empty = C.captureContext(null);
  assert.equal(empty.workspaceId, 'workspace'); assert.equal(empty.taskId, 'generate');
  assert.equal(empty.capability.state, 'unknown'); assert.equal(empty.execution.state, 'unknown');
  assert.match(C.captureContext({contextStamp:'bad stamp!'}).contextStamp, /^ctx-[0-9a-f]{8}$/);
});
