// Steps view keeps uncommitted text through workflow:render (#1062, inspector pattern #976).
// Real studio + steps wiring in Node's VM with a tiny DOM. No browser, no ComfyUI, no queue.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ids = new Map();
class Element {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase(); this.children = []; this.attributes = {};
    this.style = {}; this.dataset = {}; this.parent = null; this._value = '';
    this.textContent = ''; this.selectionStart = 0; this.selectionEnd = 0;
    this.selectionDirection = 'none'; this.validity = {badInput: false};
    this.classList = {add() {}, remove() {}, toggle() {}}; this.hidden = false;
  }
  get value() { return this._value; }
  set value(v) {
    this._value = String(v);
    this.selectionStart = this.selectionEnd = ['number', 'range'].includes(this.type) ? null : this._value.length;
  }
  get valueAsNumber() { return this._value === '' ? NaN : Number(this._value); }
  get isConnected() { let node = this; while (node.parent) node = node.parent; return node.root === true; }
  set id(v) { this._id = String(v); ids.set(this._id, this); }
  get id() { return this._id; }
  append(...nodes) { for (const n of nodes) if (n && typeof n === 'object') { n.parent = this; this.children.push(n); } }
  // Inserted siblings join the live tree, so focus inside the Steps panel survives other panels' re-renders as in a browser.
  before(...nodes) { if (this.parent) this.parent.append(...nodes); }
  replaceChildren(...nodes) {
    for (const c of this.children) c.parent = null; this.children = [];
    if (document.activeElement && !document.activeElement.isConnected) document.activeElement = null;
    this.append(...nodes);
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'id') this.id = String(v);
    if (k === 'type') this.type = String(v);
    if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = String(v);
  }
  getAttribute(k) { return this.attributes[k] ?? null; }
  get descendants() { return this.children.flatMap(c => [c, ...c.descendants]); }
  matches(selector) {
    const m = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(selector);
    if (m) return m[2] === undefined ? m[1] in this.attributes : this.getAttribute(m[1]) === m[2];
    return this.tagName === String(selector).toUpperCase();
  }
  querySelector(selector) { return this.descendants.find(n => n.matches(selector)) || null; }
  querySelectorAll(selector) { return this.descendants.filter(n => n.matches(selector)); }
  contains(node) { return node === this || this.descendants.includes(node); }
  focus() { document.activeElement = this; }
  setSelectionRange(start, end, direction = 'none') {
    if (this.type === 'number' || this.type === 'range') throw Error('InvalidStateError');
    this.selectionStart = start; this.selectionEnd = end; this.selectionDirection = direction;
  }
  checkValidity() { return true; }
  addEventListener() {} setPointerCapture() {} scrollIntoView() {} showModal() {} close() {}
  getBoundingClientRect() { return {width: 900, height: 560, left: 0, top: 0}; }
}

const body = new Element('body'); body.root = true;
const toolbarStub = new Element('div'), builderStub = new Element('div');
body.append(toolbarStub, builderStub);
const listeners = {};
const document = {
  body, activeElement: null,
  createElement: tag => new Element(tag),
  createElementNS: (_, tag) => new Element(tag),
  createTextNode: text => { const n = new Element('#text'); n.textContent = text; return n; },
  querySelector(selector) {
    if (selector === '#builder .wf-toolbar') return toolbarStub;
    if (selector === '#builder .wf-builder') return builderStub;
    if (selector.startsWith('#')) {
      const key = selector.slice(1);
      if (!ids.has(key)) { const node = new Element('div'); node.id = key; body.append(node); }
      return ids.get(key);
    }
    return null;
  },
  addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
  dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); },
};
const schema = {backend_id: 'primary', schema_sha256: 'a'.repeat(64), nodes: {Sampler: {class_type: 'Sampler', name: 'Sampler', category: 'sampling', description: '', outputs: [], output_node: true, inputs: [
  {name: 'steps', type: 'INT', widget: 'number', required: true, hidden: false, options: {min: 1, max: 100, default: 20}},
  {name: 'text', type: 'STRING', widget: 'text', required: true, hidden: false, options: {}}]}}};
const fetch = async url => {
  const reply = value => ({ok: true, json: async () => JSON.parse(JSON.stringify(value))});
  if (String(url).endsWith('/nodes') || String(url).endsWith('/nodes/refresh')) return reply(schema);
  if (String(url).endsWith('/guides')) return reply({guides: []});
  if (String(url) === '/api/catalog') return reply({presets: []});
  throw Error('Unexpected fetch ' + url);
};
const storage = () => ({getItem: () => null, setItem() {}, removeItem() {}});
const context = vm.createContext({document, fetch, localStorage: storage(), sessionStorage: storage(),
  confirm: () => true, prompt: () => null, matchMedia: () => ({matches: false}), requestAnimationFrame() {},
  innerHeight: 900, URL, Blob: class {}, Event: class { constructor(type) { this.type = type; } },
  setTimeout, console, crypto: {randomUUID: () => 'request'}});
context.window = context;
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-studio.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-project-state.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/workflow-projects.js'), 'utf8'), context);
const W = context.WorkflowStudio;
const draft = title => ({format: 'studio.workflow/v1', name: title, revision: 0, backend_id: 'primary', schema_sha256: 'a'.repeat(64),
  nodes: {'1': {class_type: 'Sampler', inputs: {steps: 20, text: 'hello'}}}, outputs: ['1'], disabled: [], bypass: {}, positions: {},
  steps: [{id: 's1', name: 'First', description: 'Does things', nodes: ['1'],
    controls: [{node: '1', input: 'text', name: 'Prompt'}, {node: '1', input: 'steps', name: 'Count'}]}]});
const settle = () => new Promise(r => setTimeout(r, 0));

(async () => {
  await document.querySelector('#loadNodes').onclick(); await settle();
  W.load(draft('Doc'));
  await ids.get('showWorkflowSteps').onclick();
  const stepsPanel = ids.get('workflowSteps');
  assert.ok(stepsPanel && !stepsPanel.hidden, 'Steps view is shown');
  assert.ok(stepsPanel.querySelector('[aria-label="steps"]'), 'One step exposes an INT control');
  let text = stepsPanel.querySelector('[aria-label="text"]');
  assert.ok(text, 'One step exposes a STRING control');
  text.focus(); text.value = 'hello typed'; text.setSelectionRange(2, 5);
  const before = text;
  document.dispatchEvent(new context.Event('workflow:render'));
  text = stepsPanel.querySelector('[aria-label="text"]');
  assert.notEqual(text, before, 'The steps view really was rebuilt');
  assert.equal(text.value, 'hello typed', 'A background render must not replace half-typed steps text');
  assert.equal(document.activeElement, text, 'Focus returns to the steps field being typed in');
  assert.deepEqual([text.selectionStart, text.selectionEnd], [2, 5], 'The caret returns too');
  text.onchange();
  assert.equal(W.snapshot().nodes['1'].inputs.text, 'hello typed', 'Committing still records the steps value');
  document.dispatchEvent(new context.Event('workflow:render'));
  text = stepsPanel.querySelector('[aria-label="text"]');
  assert.equal(text.value, 'hello typed', 'A committed field shows the document value');
  text.focus(); text.value = 'unsent draft'; text.setSelectionRange(0, 3);
  W.load(draft('Fresh'));
  text = stepsPanel.querySelector('[aria-label="text"]');
  assert.equal(text.value, 'hello', 'A replaced document never inherits a draft');
  assert.notEqual(document.activeElement, text, 'No focus is restored after a replace');
  console.log('Steps view keeps typed text');
})().catch(error => { console.error(error); process.exitCode = 1; });
