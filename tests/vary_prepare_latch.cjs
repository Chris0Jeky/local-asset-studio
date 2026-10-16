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
    calls: [], notices: [], asked: [], answer: true, typed: '', negative: '', staged: false,
    window: {confirm(text) { sandbox.asked.push(text); return sandbox.answer; }}, stagedPicture: () => sandbox.staged,
    q: (selector) => ({files: [], value: selector === '#positive' ? sandbox.typed : selector === '#negative' ? sandbox.negative : '1', textContent: '', open: false, close() {}}),
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

const press = {dataset: {uxVary: 'reseed', asset: 'asset-1', preset: 'plain', job: 'job-1'}};

test('Vary asks before replacing the owner own wording, and declining changes nothing (#1213)', async () => {
  const box = context({typed: 'my own words', answer: false, applySaved() { throw Error('applied'); }});
  await box.prepareVary(press);
  assert.equal(box.asked.length, 1, 'one question');
  assert.deepEqual(box.calls, [], 'nothing was fetched or posted');
  assert.equal(box.varyBusy, false);
  assert.match(box.notices.at(-1).message, /Nothing changed/);
  assert.notEqual(box.notices.at(-1).error, true);
  box.answer = true; box.applySaved = () => {};
  await box.prepareVary(press);
  assert.equal(box.asked.length, 2);
  assert.ok(box.calls.includes('/api/recipe-check'), 'accepting prepares the round');
});

test('Vary asks when a picture is staged, and not for the recipe default wording on an empty setup (#1213)', async () => {
  const staged = context({staged: true});
  await staged.prepareVary(press);
  assert.equal(staged.asked.length, 1);
  assert.match(staged.asked[0], /staged picture/);
  const plain = context({typed: 'recipe default', selected: {id: 'plain', name: 'Plain', defaults: {positive: 'recipe default'}}});
  await plain.prepareVary(press);
  assert.equal(plain.asked.length, 0, 'default wording and no picture is not owner work');
  const negative = context({negative: 'no text, no watermark, my list', selected: {id: 'plain', name: 'Plain', defaults: {negative: 'lowres'}}});
  await negative.prepareVary(press);
  assert.equal(negative.asked.length, 1, 'a custom negative prompt is owner wording too');
  assert.ok(plain.calls.includes('/api/recipe-check'));
});

test('putting the source back keeps a Vary carry-failure block on the same continuation', async () => {
  const reattachSource = between('  async function reattachSource(){', '\n  // One slot, two pictures');
  const claim = {version: 1, intent: 'edit', preset_id: 'plain', reference_file: 'a'.repeat(32) + '_old.png', source_asset_id: 'asset-1', source_sha256: 'b'.repeat(64), template_sha256: 'c'.repeat(64)};
  const box = context({
    continuationState: claim, secondPanel: {hidden: true}, selected: {id: 'plain', name: 'Plain', continuation_capability: {}},
    varyUnapplied: {stamp: JSON.stringify(claim), message: 'Vary could not keep lora_name'},
    async post() { return {file: 'd'.repeat(32) + '_new.png', sha256: claim.source_sha256, parent_asset: 'asset-1', context: {sha256: claim.source_sha256}}; },
    attachContinuationSource() {}, pendingInputs: new Set(), tileBusy: false, parallaxBusy: false, continuationSource: {},
    StudioContinuation: {normalize: value => ({...value}), sourceInput: () => 'reference', sourceLabel: () => 'Reference', unfilled: () => []},
  });
  vm.runInContext(reattachSource + '\nthis.reattachSource=reattachSource;', box);
  assert.ok(box.readinessItems().items.some(item => item.code === 'vary'), 'blocked before');
  await box.reattachSource();
  assert.notEqual(box.continuationState.reference_file, claim.reference_file, 'the claim follows the fresh copy');
  assert.ok(box.readinessItems().items.some(item => item.code === 'vary'), 'Generate stays blocked after Put the source back');
});
