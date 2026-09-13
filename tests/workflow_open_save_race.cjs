'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function main() {
  const stateModule = {exports: {}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-project-state.js'), 'utf8'),
    {module: stateModule, globalThis: {}});
  const P = stateModule.exports;
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
  const listeners = {};
  const toolbar = new Element('div'), builder = new Element('div');
  const document = {body: new Element('body'), activeElement: null,
    createElement: tag => new Element(tag), createTextNode: text => ({text}),
    querySelector: selector => selector === '#builder .wf-toolbar' ? toolbar : selector === '#builder .wf-builder' ? builder : ids.get(selector.slice(1)),
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
    dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); }};
  const diagnostics = new Element('div'); diagnostics.id = 'workflowDiagnostics';
  const copy = value => JSON.parse(JSON.stringify(value));
  const bDraft = {format: 'studio.workflow/v1', name: 'B draft', revision: 0, backend_id: 'x', schema_sha256: '0'.repeat(64), nodes: {}, outputs: [], disabled: [], bypass: {}, positions: {}};
  const aDoc = {...copy(bDraft), name: 'A current', revision: 1};
  let doc = copy(bDraft), epoch = 1;
  const W = {snapshot: () => copy(doc), validate() {}, epoch: () => epoch, schema: () => null,
    load(next) { document.dispatchEvent({type: 'workflow:replace'}); doc = copy(next); epoch++; },
    change(next) { doc = copy(next); epoch++; document.dispatchEvent({type: 'workflow:render'}); },
    field() {}, inspect() {}};
  const storageValues = new Map();
  const storage = {getItem: k => storageValues.get(k) || null, setItem: (k,v) => storageValues.set(k,v), removeItem: k => storageValues.delete(k)};
  let openResolve, saveResolve, sequence = 0;
  const calls = [];
  const response = body => ({ok: true, status: 200, json: async () => body});
  const context = {window: {WorkflowStudio: W, WorkflowProjectState: P}, document,
    crypto: {randomUUID: () => 'request-' + (++sequence)}, sessionStorage: storage, confirm: () => true,
    Event: class {constructor(type) {this.type = type;}},
    fetch: async (route, options = {}) => {
      const body = options.body ? JSON.parse(options.body) : null; calls.push([route, body]);
      if (route === P.PREFIX && body) return response({id: 'B', revision: 1, head_revision: 1, document: {...copy(bDraft), revision: 1}});
      if (route === P.PREFIX + '/A') return new Promise(resolve => { openResolve = value => resolve(response(value)); });
      if (route === P.PREFIX + '/B/commands' && calls.filter(x => x[0] === route).length === 1)
        return new Promise(resolve => { saveResolve = value => resolve(response(value)); });
      if (route === P.PREFIX + '/B/commands') return response({id: 'B', revision: 3, head_revision: 3, document: {...copy(body.commands[0].document), revision: 3}});
      throw Error('Unexpected request ' + route);
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-projects.js'), 'utf8'), context);
  await ids.get('saveSharedWorkflow').onclick();
  ids.get('sharedWorkflowChoice').value = 'A';
  const opening = ids.get('openSharedWorkflow').onclick();
  const saving = ids.get('saveSharedWorkflow').onclick();
  openResolve({id: 'A', revision: 1, head_revision: 1, document: aDoc});
  await opening;
  assert.equal(W.snapshot().name, 'B draft', 'An opening response must not replace a draft with a save in flight');
  assert.match(ids.get('sharedWorkflowStatus').textContent, /save.*opening/i);
  saveResolve({id: 'B', revision: 2, head_revision: 2, document: {...copy(bDraft), revision: 2}});
  await saving;
  assert.match(ids.get('sharedWorkflowState').textContent, /Workspace r2.*saved/);
  await ids.get('saveSharedWorkflow').onclick();
  const final = calls.at(-1);
  assert.equal(final[0], P.PREFIX + '/B/commands');
  assert.equal(final[1].commands[0].document.name, 'B draft', 'A later ordinary save must still target its own document');
  const laterOpen = ids.get('openSharedWorkflow').onclick();
  openResolve({id: 'A', revision: 1, head_revision: 1, document: aDoc});
  await laterOpen;
  assert.equal(W.snapshot().name, 'A current', 'Explicit open works after the prior save settles');
  assert.match(ids.get('sharedWorkflowState').textContent, /Workspace r1.*saved/);
  console.log('Open/save interleaving preserves document identity');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
