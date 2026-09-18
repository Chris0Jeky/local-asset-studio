'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const htmlPath = path.join(__dirname, 'index.html');
assert.ok(fs.existsSync(htmlPath), 'The isolated adaptive behavior specification is not implemented');
const html = fs.readFileSync(htmlPath, 'utf8');
const policy = html.match(/<script id="policy">([\s\S]*?)<\/script>/);
assert.ok(policy, 'The same pure policy used by the browser must be testable');
const sandbox = {module: {exports: {}}};
vm.runInNewContext(policy[1], sandbox, {timeout: 1000});
const A = sandbox.module.exports;
const base = () => A.initial();

test('appearance and task projection never mutate context or grant execution', () => {
  const state = base(); const before = JSON.stringify(state);
  for (const task of Object.keys(A.TASKS)) {
    const view = A.project({...state, task});
    assert.equal(view.submissionAuthorized, false);
    assert.ok(view.secondary.length <= 2);
  }
  assert.equal(JSON.stringify(state), before);
});
test('an uncertain operation overrides creative guidance', () => {
  const view = A.project({...base(), task:'pose', job:'uncertain', refs:0});
  assert.equal(view.action, 'inspect');
  assert.match(view.title, /original request/i);
});
test('uncertain recovery retains a blocking draft conflict in Expert', () => {
  const view = A.project({...base(), job:'uncertain', conflict:true, assistance:'expert'});
  assert.equal(view.action, 'inspect');
  assert.equal(view.blockingSecondary, true);
  assert.ok(view.secondary.some(text => /draft conflict/i.test(text)));
  assert.ok(view.secondary.length <= 2);
});
test('a conflicting draft remains visible in expert mode', () => {
  const view = A.project({...base(), conflict:true, assistance:'expert'});
  assert.equal(view.action, 'conflict');
});
test('internet loss alone does not block local workflow review', () => {
  const state = {...base(), internet:false};
  assert.equal(A.project(state).action, 'review');
  assert.equal(A.ambience({...state, motion:'subtle', media:'local-loop'}).mode, 'local-loop');
});
test('healthy internet cannot make an unavailable backend ready', () => {
  assert.equal(A.project({...base(), backend:'unavailable'}).action, 'backend');
});
test('task selection suggests a route without choosing it', () => {
  const state = {...base(), task:'pose'};
  assert.equal(A.project(state).action, 'recipe');
  assert.equal(state.route, 'words');
});
test('required references and overflow are distinct and never truncated', () => {
  assert.equal(A.project({...base(), task:'pose', route:'pose', refs:1}).action, 'sources');
  const state = {...base(), task:'pose', route:'pose', refs:4};
  assert.equal(A.project(state).action, 'overflow');
  assert.equal(state.refs, 4);
});
test('unknown and stale execution observations cannot appear ready', () => {
  assert.equal(A.project({...base(), api:'unknown'}).action, 'api');
  assert.equal(A.project({...base(), job:'unknown'}).action, 'inspect');
  assert.equal(A.project({...base(), freshness:'stale'}).action, 'refresh');
});
test('running jobs keep the original operation visible', () => {
  assert.equal(A.project({...base(), job:'running'}).action, 'inspect');
  assert.equal(A.ambience({...base(), job:'running', motion:'cinematic', media:'local-loop'}).mode, 'still');
});
test('motion controls override otherwise available local media', () => {
  for (const patch of [{reduced:true},{forcedColors:true},{economy:true},{paused:true},{visible:false},{api:'unknown'},{freshness:'stale'}]) {
    const result=A.ambience({...base(), motion:'cinematic', media:'local-loop', ...patch});
    assert.notEqual(result.mode, 'local-loop');
    assert.equal(result.parallax, false);
  }
});
test('remote media requires permission and a local poster', () => {
  const state={...base(), motion:'subtle', media:'remote-available'};
  assert.equal(A.ambience(state).mode, 'still');
  assert.equal(A.ambience({...state, remoteAllowed:true}).mode, 'remote-loop');
  assert.equal(A.ambience({...state, remoteAllowed:true, poster:false}).mode, 'tokens');
});
test('media failure does not change operation guidance', () => {
  const state={...base(), media:'failed', motion:'cinematic'};
  assert.equal(A.ambience(state).mode, 'still');
  assert.equal(A.project(state).action, 'review');
});
test('obsolete load replies cannot be accepted after A-B-A', () => {
  assert.equal(A.accepts({epoch:3,skin:'atelier'}, {epoch:1,skin:'atelier'}), false);
  assert.equal(A.accepts({epoch:3,skin:'atelier'}, {epoch:3,skin:'sakura'}), false);
  assert.equal(A.accepts({epoch:3,skin:'atelier'}, {epoch:3,skin:'atelier'}), true);
});
test('file is standalone and contains no image/media/network integration', () => {
  assert.doesNotMatch(html, /<(?:img|video|audio|iframe)\b/i);
  assert.doesNotMatch(html, /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(/);
  assert.doesNotMatch(html, /(?:src|href)=["']https?:/);
  assert.match(html, /connect-src 'none'/);
});
