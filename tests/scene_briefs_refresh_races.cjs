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
  const handlers = {}, calls = [], documentHandlers = {}, store = new Map(), h = {calls, delayFirstPage: 0, delayNextPage: 0, gate: null};
  const root = {innerHTML: '', querySelector: () => null, addEventListener: (type, fn) => {handlers[type] = fn;}};
  const sandbox = {StudioBriefCore: core, URL, URLSearchParams, Blob, setTimeout, confirm: () => true};
  let current = hash;
  sandbox.location = {get hash() {return current;}, set hash(value) {current = value; setTimeout(() => sandbox.window.StudioBriefs.refresh(), 0);}};
  sandbox.sessionStorage = {get length() {return store.size;}, key: i => [...store.keys()][i] ?? null, getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, String(value)), removeItem: key => store.delete(key)};
  sandbox.document = {querySelector: selector => selector === '#briefsView' ? root : null, addEventListener: (type, fn) => {documentHandlers[type] = fn;}};
  h.privacy = {scope: () => h.scope, creation: () => 'regular', fetch: (target, options) => sandbox.fetch(target, options)};
  h.scope = 'regular';
  sandbox.StudioPrivacy = h.privacy;
  sandbox.window = {addEventListener() {}, StudioPrivacy: h.privacy};
  const json = body => ({ok: true, json: async () => body});
  sandbox.fetch = async (target, options = {}) => {
    const url = new URL(target, 'http://studio.test'), key = (options.method || 'GET') + ' ' + url.pathname;
    calls.push(key + (url.searchParams.get('cursor') ? '?cursor=' + url.searchParams.get('cursor') : ''));
    if (key === 'GET /api/briefs') return json({workspace_id: workspace, briefs: [{id: 'brief-one', name: 'Lantern', available: true}]});
    if (key === 'GET /api/collections') return json({collections: [], next_cursor: null});
    if (key === 'GET /api/looks') return json({looks: []});
    if (key === 'GET /api/briefs/brief-one') return json({card: {...core.newCard(workspace, 'brief-one'), name: 'Lantern', revision: 0}, candidates: {}, collection_available: true});
    if (key === 'GET /api/assets/page') {
      if (url.searchParams.get('cursor')) {if (h.delayNextPage) await wait(h.delayNextPage); return json(page('two-', null));}
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

test('Going back to the first page while the next page is still loading reloads the first page', async () => {
  const first = '#briefs?id=brief-one&slot=background&picker=1';
  const h = harness(first);
  await wait(50);
  assert.equal(h.candidates('one-'), 12);
  h.delayNextPage = 150;
  h.click('next');
  await wait(20);
  h.setHash(first);
  await wait(400);
  assert.equal(h.candidates('one-'), 12);
  assert.equal(h.candidates('two-'), 0);
});

// A pending working-pack export that is discarded must not leave "Preparing working pack…" behind.
async function pendingPack(h) {
  await wait(50);
  let release;
  h.onOther = key => key === 'POST /api/briefs/export' ? new Promise(resolve => {release = () => resolve({ok: true, json: async () => ({url: '/api/exports/pack', filename: 'pack.zip'})});}) : Promise.reject(Error('Unexpected request ' + key));
  h.click('workingPack');
  await wait(20);
  assert.ok(release, 'export request reached the delayed boundary');
  return release;
}
const settled = h => assert.ok(!h.root.innerHTML.includes('Preparing working pack') && !h.calls.includes('GET /api/exports/pack'));

test('Picker candidates recover after navigating back during a pending working pack', async () => {
  const first = '#briefs?id=brief-one&slot=background&picker=1';
  const h = harness(first);
  await wait(50);
  assert.equal(h.candidates('one-'), 12);
  h.delayNextPage = 200;
  h.click('next');
  const release = await pendingPack(h);
  assert.ok(h.calls.includes('GET /api/assets/page?cursor=c2'));
  h.setHash(first);
  await wait(20);
  release();
  await wait(300);
  assert.equal(h.candidates('one-'), 12);
  assert.equal(h.candidates('two-'), 0);
  settled(h);
});

test('Leaving the brief while a working pack is pending clears its progress text and downloads nothing', async () => {
  const h = harness('#briefs?id=brief-one&slot=background');
  const release = await pendingPack(h);
  h.setHash('#assets');
  release();
  await wait(50);
  h.setHash('#briefs?id=brief-one&slot=background');
  await wait(50);
  assert.ok(h.root.innerHTML.includes('data-action="workingPack"'));
  settled(h);
});

test('Switching privacy while a working pack is pending clears its progress text and downloads nothing', async () => {
  const h = harness('#briefs?id=brief-one&slot=background');
  const release = await pendingPack(h);
  h.scope = 'private'; h.documentHandlers['studio:privacy-change']();
  await wait(20);
  h.scope = 'regular'; h.documentHandlers['studio:privacy-change']();
  release();
  await wait(50);
  assert.ok(h.root.innerHTML.includes('data-action="workingPack"'));
  settled(h);
});
