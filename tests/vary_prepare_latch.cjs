'use strict';
// Vary prepare must not stick the busy latch, must keep Generate disabled while it runs,
// and must check the recipe before a new-seed round uses the current graph.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');
function between(start, end) {
  const first = source.indexOf(start);
  assert.notEqual(first, -1, 'missing ' + start);
  const last = source.indexOf(end, first + start.length);
  assert.notEqual(last, -1, 'missing ' + end);
  return source.slice(first, last);
}
const readinessSource = between('  function readinessItems(){', '\n  function syncReady(){');
const combineSource = between('  function combineBusy(){', '\n  // Each engine');
const prepareSource = between('  async function prepareVary(button){', "\n  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-vary]')");
const U = require('../app/static/studio-core.js');

function context(extra) {
  const sandbox = {
    U, selected: {id: 'plain', name: 'Plain'}, online: true, schemaAvailable: true, workerAlive: true,
    missingByPreset: {}, continuationState: null, pendingInputs: [], uploaded: null, lastUploaded: null,
    secondPicture: null, sharedAdoptionError: null, varyUnapplied: null, sourceReadError: '',
    submitting: false, handoffBusy: false, pickerBusy: false, restoring: false, pairActionBusy: false, poseBusy: false,
    referencePending: 0, varyBusy: false, catalog: {presets: [{id: 'plain', name: 'Plain'}]},
    draftDirty: false, recipeTemplateHash: null, selectedPositive: 'kept words',
    calls: [], notices: [],
    q: () => ({files: [], value: '1', textContent: '', open: false, close() {}}),
    referencesReady: () => true, posePositionDirty: () => false, poseHeldArtifact: () => null, poseSizeHold: () => null,
    i2vModeBlocker: () => null, continuationBlockerItems: () => [],
    announce(message, error) { sandbox.notices.push({message, error}); },
    assetDetailsDirty: () => false, warnUnsavedAsset() {}, syncGalleryVary() {}, syncReady() {},
    getControl: () => ({value: ''}), updateReady() {}, scheduleTimeEstimate() {}, recipeChanged() {},
    showView() {}, saveDraft() {}, syncCreate() {}, beginContinuation() {},
    selectPreset() {}, applySaved() {},
    crypto: {getRandomValues: (array) => { array[0] = 9; return array; }},
    async api(url) { sandbox.calls.push(url); return {preset_id: 'plain', controls: {positive: 'kept words', seed: 4}}; },
    async post(url) { sandbox.calls.push(url); return {template_sha256: 'checked-graph'}; },
    varyPlanFor: () => ({kind: 'reseed', route: {id: 'plain', name: 'Plain'}, round: {count: 2}}),
    workbenchStamp: () => 'stamp',
    StudioContinuation: {varyStatus: () => 'prepared', unfilled: () => []},
  };
  Object.assign(sandbox, extra || {});
  vm.createContext(sandbox);
  vm.runInContext(readinessSource + '\n' + combineSource + '\n' + prepareSource + '\nthis.readinessItems=readinessItems;this.combineBusy=combineBusy;this.prepareVary=prepareVary;', sandbox);
  return sandbox;
}

test('a throw while Vary is arming does not leave varyBusy stuck', async () => {
  const box = context({workbenchStamp() { throw Error('stamp failed'); }});
  let threw = false;
  try { await box.prepareVary({dataset: {uxVary: 'reseed', asset: 'asset-1', preset: 'plain', job: 'job-1'}}); }
  catch (error) { threw = true; }
  assert.equal(box.varyBusy, false);
  assert.equal(threw, false, 'the failure is announced and the latch clears');
});

test('Generate readiness stays busy while Vary is preparing', () => {
  const box = context({varyBusy: true});
  const items = box.readinessItems().items;
  assert.ok(items.some(item => item.code === 'busy'), items);
  assert.equal(box.combineBusy(), true, 'Combine stays locked while Vary is preparing');
});

test('prepare new seed checks the recipe against the current graph', async () => {
  const box = context();
  await box.prepareVary({dataset: {uxVary: 'reseed', asset: 'asset-1', preset: 'plain', job: 'job-1'}});
  assert.ok(box.calls.includes('/api/recipe-check'), box.calls);
  assert.equal(box.recipeTemplateHash, 'checked-graph');
});
