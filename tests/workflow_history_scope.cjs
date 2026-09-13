/* Execute the real UI wiring with a minimal DOM and an explicit service fixture. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
async function main() {
  const ids = new Map();
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this._value = ''; }
    set id(value) { this._id = value; ids.set(value, this); }
    get id() { return this._id; }
    setAttribute(key, value) { if (key === 'id') this.id = value; else this[key] = String(value); }
    append(...nodes) { this.children.push(...nodes); }
    before() {}
    replaceChildren(...nodes) { this.children = []; this._value = ''; this.append(...nodes); }
    get value() { return this._value; }
    set value(value) { this._value = String(value); }
    addEventListener() {}
    querySelectorAll() { return []; }
  }
  const toolbar = new Element('div'), builder = new Element('div');
  const document = {body: new Element('body'), activeElement: null, listeners: {},
    createElement: tag => new Element(tag), createTextNode: text => ({text}),
    querySelector: selector => selector === '#builder .wf-toolbar' ? toolbar : selector === '#builder .wf-builder' ? builder : ids.get(selector.slice(1)),
    addEventListener(name, fn) { this.listeners[name] = fn; },
    dispatchEvent(event) { this.listeners[event.type]?.(event); }};
  const diagnostics = new Element('div'); diagnostics.id = 'workflowDiagnostics';
  const calls = []; let pendingHistory;
  // State's public contract: success can rebind without replacing the local draft.
  class State {
    constructor() { this.binding = {id: 'A', revision: 2, conflict: false}; this.pending = null; this.busy = false; }
    dirty() { return false; }
    attach(r) { this.binding = {id: r.id, revision: r.revision, conflict: false}; }
    begin(doc, copy, revision) { this.pending = {path: copy ? '/documents' : '/documents/' + this.binding.id + '/restore', body: {revision}, copy}; }
    success(r) { this.attach(r); this.pending = null; return {replace: false, detached: false}; }
    failure() { this.pending = null; }
    detach() { this.binding = null; }
  }
  const W = {snapshot: () => ({name: 'Draft', nodes: {}}), validate() {}, epoch: () => 1, load() {}};
  const context = {window: {WorkflowStudio: W, WorkflowProjectState: {State, PREFIX: '/documents'}}, document,
    Event: class {constructor(type) {this.type = type;}},
    crypto: {randomUUID: () => 'request'}, sessionStorage: {}, confirm: () => true,
    fetch: async (route, options) => {
      calls.push([route, options]);
      if (route.endsWith('/history') && pendingHistory) return pendingHistory;
      const result = route.endsWith('/history') ? {revisions: [{revision: 1, kind: 'create', created_at: 1}]} : {id: 'B', revision: 1, head_revision: 1, document: {name: 'copy'}};
      return {ok: true, json: async () => result};
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-projects.js'), 'utf8'), context);
  assert.equal(calls.length, 0, 'Loading the UI is inert');
  assert.equal(context.window.WorkflowProject.snapshot().id, 'A');
  const history = ids.get('workflowRevisionChoice'), restore = ids.get('restoreSharedWorkflow');
  await ids.get('loadWorkflowHistory').onclick();
  history.value = '1'; history.onchange(); assert.equal(restore.disabled, false);
  let release;
  pendingHistory = new Promise(resolve => { release = resolve; });
  const late = ids.get('loadWorkflowHistory').onclick();
  await ids.get('copySharedWorkflow').onclick();
  assert.equal(context.window.WorkflowProject.snapshot().id, 'B', 'Bridge reflects a copy attached without editor replacement');
  assert.equal(history.value, '', 'Copy clears the old document history selection');
  assert.equal(history.children.length, 1, 'Only the load-history placeholder remains');
  assert.equal(restore.disabled, true, 'Copy cannot restore a revision from the prior identity');
  release({ok: true, json: async () => ({revisions: [{revision: 77, kind: 'old', created_at: 1}]})});
  await late; pendingHistory = null;
  assert.equal(history.children.length, 1, 'Late history response cannot attach to the copy');
  const before = calls.length;
  history.value = '1'; await restore.onclick();
  assert.equal(calls.length, before, 'The action itself rejects unscoped history, not just the disabled button');
  await ids.get('loadWorkflowHistory').onclick();
  history.value = '1'; history.onchange(); assert.equal(restore.disabled, false);
  await restore.onclick();
  assert.equal(calls.at(-1)[0], '/documents/B/restore', 'Fresh history restores only the current copy');
  console.log('Workflow history identity contracts passed');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
