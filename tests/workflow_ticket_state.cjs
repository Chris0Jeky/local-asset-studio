'use strict';
const assert = require('node:assert/strict');
const {State, KEY, signature, validateReport} = require('../app/static/workflow-ticket-state.js');
const clone = x => JSON.parse(JSON.stringify(x));
const doc = {format: 'studio.workflow/v1', name: 'Example', revision: 1, nodes: {}};
const request = '11111111-1111-4111-8111-111111111111', job = '22222222-2222-5222-8222-222222222222';
const hash = 'a'.repeat(64), recipe = {preset_id: 'example', controls: {seed: 42}, batch_count: 1};
const report = {format: 'studio.preset-projection/v1', generation_submitted: false, recipe,
  document_sha256: hash, authored_graph_sha256: hash, prepared_graph_sha256: hash, ticket_sha256: hash,
  job_id: job, changed_bindings: {}, ticket: {format: 'studio.run-ticket/v1', request_id: request,
    recipe, pins: {graph_sha256: hash}, generation_submitted: false, notice: 'Registered only'}};
function storage() { return {raw: null, fail: false, getItem() {return this.raw;}, setItem(k, v) {if (this.fail) throw Error('storage failed'); this.raw = v;}, removeItem() {if (this.fail) throw Error('storage failed'); this.raw = null;}}; }
function prepared() {const s = storage(), state = new State(s); state.accept(report, doc, 'example'); return {s, state};}
let count = 0;
function test(name, fn) {fn(); console.log('PASS ' + name); count++;}
test('load is inert and restores the original identity', () => {
  const {s} = prepared(), reloaded = new State(s);
  assert.equal(reloaded.record.phase, 'prepared'); assert.equal(reloaded.record.report.ticket.request_id, request);
});
test('intent must persist before the ticket can be returned', () => {
  const {s, state} = prepared(); const ticket = state.begin(doc, 'example');
  assert.equal(JSON.parse(s.raw).phase, 'attempted'); assert.deepEqual(ticket, report.ticket);
});
test('storage refusal prevents initial dispatch', () => {
  const {s, state} = prepared(); s.fail = true;
  assert.throws(() => state.begin(doc, 'example'), /storage/); assert.equal(state.record.phase, 'prepared');
});
test('initial run refuses a changed source or recipe', () => {
  const {state} = prepared();
  assert.throws(() => state.begin({...doc, name: 'changed'}, 'example'), /changed/);
  assert.throws(() => state.begin(doc, 'other'), /changed/);
});
test('recovery returns the same ticket after later edits and reload', () => {
  const {s, state} = prepared(); state.begin(doc, 'example');
  const second = new State(s); assert.deepEqual(second.begin({...doc, name: 'changed'}, 'other', true), report.ticket);
  assert.throws(() => second.begin(doc, 'example'), /stale/);
});
test('attempted unknown work cannot be cleared or replaced', () => {
  const {state} = prepared(); state.begin(doc, 'example');
  assert.throws(() => state.clear(), /Unresolved/); assert.throws(() => state.accept(report, doc, 'example'), /retained/);
});
test('malformed, wrong-job and null dispatch replies preserve intent', () => {
  const {state} = prepared(); state.begin(doc, 'example');
  for (const result of [null, {}, {job: null}, {job: {id: request, status: 'completed'}}, {job: {id: job, status: 'invented'}}]) {
    assert.throws(() => state.dispatched(result)); assert.equal(state.record.phase, 'attempted'); assert.equal(state.canClear(), false);
  }
});
test('active and uncertain status are never treated as completed', () => {
  const {state} = prepared(); state.begin(doc, 'example');
  for (const status of ['queued', 'waiting', 'running', 'uncertain']) {state.observe({id: job, status}); assert.equal(state.canClear(), false);}
});
test('reconciliation-required preserves the same request', () => {
  const {state} = prepared(); state.begin(doc, 'example');
  state.dispatched({job_id: job, status: 'reconciliation_required'}); assert.equal(state.canClear(), false);
  assert.deepEqual(state.begin(null, '', true), report.ticket);
});
test('terminal observation allows explicit local clearing only', () => {
  for (const status of ['completed', 'failed', 'partial', 'cancelled']) {
    const {s, state} = prepared(); state.begin(doc, 'example'); state.observe({id: job, status});
    assert.equal(state.canClear(), true); state.clear(); assert.equal(s.raw, null); assert.equal(state.record, null);
  }
});
test('failed clearing leaves the in-memory record intact', () => {
  const {s, state} = prepared(); s.fail = true; assert.throws(() => state.clear()); assert.ok(state.record);
});
test('unsafe integers and altered recipe/report are rejected', () => {
  let r = clone(report); r.ticket.recipe.controls.seed = 2**63;
  assert.throws(() => validateReport(r), /exact browser/);
  r = clone(report); r.ticket.recipe.preset_id = 'changed'; assert.throws(() => validateReport(r), /differ/);
  r = clone(report); r.job_id = '../prompt'; assert.throws(() => validateReport(r), /identity/);
  r = clone(report); r.ticket.pins.graph_sha256 = 'b'.repeat(64); assert.throws(() => validateReport(r), /differs/);
});
test('corrupt persisted state fails closed without deletion', () => {
  const s = storage(); s.raw = '{broken'; assert.throws(() => new State(s)); assert.equal(s.raw, '{broken');
  s.raw = JSON.stringify({version: 1, phase: 'prepared', source: '', report, last_status: 'completed'});
  assert.throws(() => new State(s)); assert.ok(s.raw);
});
test('stable signatures tolerate key order but preserve values', () => {
  assert.equal(signature({a: 1, b: 2}), signature({b: 2, a: 1})); assert.notEqual(signature({a: 1}), signature({a: true}));
});
console.log(`${count} ticket-state contracts passed`);
module.exports = {report, doc, storage};
