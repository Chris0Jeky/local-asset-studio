'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const C = require('../app/static/presentation-context.js');

const input = () => ({
  workspaceId:'create', contextStamp:'ctx-copy', taskId:'generate',
  capability:{state:'known', value:{
    recipeId:'copy-fixture', backendId:'primary',
    referenceSlots:[{id:'pose', role:'Pose picture', required:true}]
  }},
  execution:{state:'known', observedAt:100, contextStamp:'ctx-copy', value:{
    state:'ready', operationId:null, blockers:[], outputs:0
  }},
  draft:{dirty:false, conflict:false, pendingFiles:1, references:[
    {id:'pose-source', slotId:'pose', role:'Pose picture', stage:'selected'}
  ]}
});

test('selected required source copy asks for staging rather than another attachment', () => {
  const view = C.project(C.captureContext(input()), {});
  assert.equal(view.primaryAction.id, C.ACTIONS.REVIEW_SOURCES);
  assert.deepEqual(view.sourceSummary.pending.map(item => item.id), ['pose-source']);
  assert.deepEqual(view.sourceSummary.missing.map(item => item.id), ['pose']);
  assert.match(view.primaryAction.description, /selected|staging|checking/i);
  assert.doesNotMatch(view.primaryAction.description, /attach or stage every required source role/i);
});

test('pending source copy also names a genuinely absent required role', () => {
  const value = input();
  value.capability.value.referenceSlots.push({id:'identity', role:'Identity picture', required:true});
  const view = C.project(C.captureContext(value), {});
  assert.deepEqual(view.sourceSummary.pending.map(item => item.id), ['pose-source']);
  assert.deepEqual(view.sourceSummary.missing.map(item => item.id), ['pose', 'identity']);
  assert.match(view.primaryAction.description, /stage|checking/i);
  assert.match(view.primaryAction.description, /attach|missing|remaining/i);
});
