'use strict';
// Runs the shipped scene-briefs.js against a tiny fake DOM and a delayed fake API: no browser, no Studio server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const core = require('../app/static/scene-brief-core.js');
const code = fs.readFileSync(path.join(__dirname, '../app/static/scene-briefs.js'), 'utf8');
const workspace = 'a'.repeat(32), wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const page = (prefix, next) => ({assets: Array.from({length: 12}, (_, i) => ({id: prefix + i, title: prefix + i, filename: prefix + i + '.png', media_type: 'image', metadata_revision: 1})), next_cursor: next});

function harness(hash) {
  const handlers = {}, calls = [], documentHandlers = {}, store = new Map(), h = {calls, delayFirstPage: 0, gate: null};
  const root = {innerHTML: '', querySelector: () => null, addEventListener: (type, fn) => {handlers[type] = fn;}};
  const sandbox = {StudioBriefCore: core, URL, URLSearchParams, Blob, setTimeout, confirm: () => true};
  let current = hash;
  sandbox.location = {get hash() {return current;}, set hash(value) {current = value; setTimeout(() => sandbox.window.StudioBriefs.refresh(), 0);}};
  sandbox.sessionStorage = {get length() {return store.size;}, key: i => [...store.keys()][i] ?? null, getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, String(value)), removeItem: key => store.delete(key)};
  sandbox.document = {querySelector: selector => selector === '#briefsView' ? root : null, addEventListener: (type, fn) => {documentHandlers[type] = fn;}};
  sandbox.window = {addEventListener() {}};
  const json = body => ({ok: true, json: async () => body});
  sandbox.fetch = async (target, options = {}) => {
    const url = new URL(target, 'http://studio.test'), key = (options.method || 'GET') + ' ' + url.pathname;
    calls.push(key + (url.searchParams.get('cursor') ? '?cursor=' + url.searchParams.get('cursor') : ''));
    if (key === 'GET /api/briefs') return json({workspace_id: workspace, briefs: [{id: 'brief-one', name: 'Lantern', available: true}]});
    if (key === 'GET /api/collections') return json({collections: [], next_cursor: null});
    if (key === 'GET /api/looks') return json({looks: []});
    if (key === 'GET /api/briefs/brief-one') return json({card: {...core.newCard(workspace, 'brief-one'), name: 'Lantern', revision: 0}, candidates: {}, collection_available: true});
    if (key === 'GET /api/assets/page') {
      if (url.searchParams.get('cursor')) return json(page('two-', null));
      if (h.delayFirstPage) await wait(h.delayFirstPage);
      return json(page('one-', 'c2'));
    }
    if (h.onOther) return h.onOther(key, options);
    throw Error('Unexpected request ' + key);
  };
  vm.runInContext(code, vm.createContext(sandbox));
  const click = action => handlers.click({target: {closest: () => ({dataset: {action}, disabled: false})}});
  return Object.assign(h, {root, click, documentHandlers, sandbox, refresh: () => sandbox.window.StudioBriefs.refresh(), setHash: value => {sandbox.location.hash = value;}, candidates: prefix => (root.innerHTML.match(new RegExp('data-candidate="' + prefix, 'g')) || []).length});
}

test('First page keeps its candidates when navigation and the hash refresh overlap a delayed response', async () => {
  const h = harness('#briefs?id=brief-one&slot=background&picker=1&cursor=c2');
  await wait(50);
  assert.equal(h.candidates('two-'), 12);
  h.delayFirstPage = 150;
  h.click('first');
  await wait(400);
  assert.equal(h.candidates('one-'), 12);
  assert.ok(!h.root.innerHTML.includes('No active candidates match'));
});
