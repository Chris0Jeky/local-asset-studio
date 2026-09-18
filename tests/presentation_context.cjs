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
