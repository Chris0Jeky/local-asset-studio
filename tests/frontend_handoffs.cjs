// Exercise the real gallery, reference and save/submit handlers without a GPU or browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const presets = ['plain', 'gentle-variation', 'qwen-1ref', 'qwen-3ref', 'wan22-i2v', 'trellis-auto-cutout', 'anime-detail-fix', 'krea-refine'].map(id => ({
  id, name: id, modality: id === 'wan22-i2v' ? 'video' : id === 'trellis-auto-cutout' ? '3d' : 'image',
  reference: id === 'plain' ? undefined : ['4', 'image'],
  reference_slots: id.startsWith('qwen') ? Array.from({length: id === 'qwen-1ref' ? 1 : 3}, () => ({role: 'identity', contribution: 'Keep the character', avoid: 'Background'})) : undefined,
}));

// One page sandbox over the real scripts. `attached` answers /api/assets/reference, which carries the
// parent_asset lineage claim; `local` answers /api/upload, which never does. That asymmetry is what the
// swap contracts below turn on, so the two responses must stay distinguishable.
function sandbox(attached, local) {
  const elements = new Map(), requests = [];
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', files: [], textContent: '', classList: {toggle() {}},
      addEventListener() {}, scrollIntoView() {}, close() {}, showModal() {},
    });
    return elements.get(selector);
  };
  const context = vm.createContext({
    document: {querySelector: element, querySelectorAll: () => [], addEventListener() {}},
    URL, Blob, location: {hash: ''}, setInterval() {},
    fetch: async (url, options = {}) => {
      if (url === '/api/catalog') return new Promise(() => {}); // Hold page startup.
      if (options.method === 'POST') requests.push({url, data: options.headers?.['Content-Type'] === 'application/json' ? JSON.parse(options.body) : null});
      const data = url === '/api/assets/reference' ? attached : url === '/api/upload' ? local
        : url === '/api/jobs' ? {id: 'child-job', message: 'Queued'}
        : url.startsWith('/api/inspect/') ? {requirements: [], nodes: [], graph: {}}
        : {};
      return {ok: true, json: async () => data, blob: async () => new Blob(['image'], {type: 'image/png'})};
    },
  });
  for (const name of ['app.js', 'references.js', 'workspace.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static', name), 'utf8'), context);
  }
  const run = source => vm.runInContext(source, context);
  run(`catalog=${JSON.stringify({presets})}; online=schemaAvailable=true;
    jobs=[{id:'source-job',outputs:[{asset_id:'source-asset'}]}];
    refresh=async()=>{}; loadSetups=async()=>{};`);
  return {element, requests, context, run, parents: () => JSON.parse(run('JSON.stringify(parentAssets)'))};
}

const localFile = (name = 'unrelated.png') => ({name, size: 2048, type: 'image/png'});

async function check(presetId, targetPreset, slots, workspace = false) {
  const upload = {file: 'retained.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'source-asset'};
  const {element, requests, context, run} = sandbox(upload, upload);
  run(`selectPreset(${JSON.stringify(presetId)});`);
  const button = {dataset: {job: 'source-job', index: '0', ...(targetPreset ? {preset: targetPreset} : {})}};
  if (workspace) {
    vm.runInContext(`assetState.assets=[{id:'source-asset',title:'Original',media_type:'image',tags:[],source:{},lineage:[],bytes:1024}];openAsset('source-asset');`, context);
    assert.ok(element('#assetHandoffs').innerHTML.includes('data-handoff="'+targetPreset+'"'), 'Workspace exposes the repair action');
    await vm.runInContext(`handoffAsset('source-asset',${JSON.stringify(targetPreset)})`, context);
    assert.equal(context.location.hash, 'create');
    vm.runInContext(`assetState.assets[0].media_type='video';openAsset('source-asset');`, context);
    assert.equal(element('#assetHandoffs').innerHTML, '', 'Image repair actions are absent on video assets');
  } else {
    if (['anime-detail-fix', 'krea-refine'].includes(targetPreset)) {
      const card = vm.runInContext(`mediaCard({id:'source-job',controls:{}},0,{media_type:'image'})`, context);
      assert.ok(card.includes('data-preset="'+targetPreset+'"'), 'Gallery exposes the repair action');
      const video = vm.runInContext(`mediaCard({id:'source-job',controls:{}},0,{media_type:'video'})`, context);
      assert.ok(!video.includes('data-preset="'+targetPreset+'"'), 'Image repair actions are absent on video outputs');
    }
    await element('#gallery').onclick({target: {closest: selector => selector === '.reference-output' ? button : null}});
  }
  assert.equal(requests.some(r => r.url === '/api/jobs'), false, 'Attaching must never submit generation');
  const state = JSON.parse(vm.runInContext('JSON.stringify({preset:selected.id,parents:parentAssets,references:attachedReferencePayload(),ready:referencesReady()})', context));
  assert.deepEqual(state.parents, ['source-asset'], 'Gallery handoff must retain the selected source identity');
  assert.equal(state.preset, targetPreset || (presetId === 'plain' ? 'gentle-variation' : presetId));
  assert.equal(state.references.length, slots);
  if (slots) {
    assert.equal(state.references[0].file, upload.file);
    assert.equal(state.references[0].sha256, upload.sha256);
    assert.equal(state.references[0].role, 'identity');
    assert.equal(state.ready, slots === 1, 'Unfilled additional slots must still block generation');
    assert.equal(element('#generate').disabled, slots !== 1);
  }
  element('#saveName').value = 'Retained gallery handoff';
  await element('#save').onclick();
  const saved = requests.find(r => r.url === '/api/setups').data.recipe;
  assert.deepEqual(saved.parent_assets, ['source-asset']);
  assert.deepEqual(saved.references, state.references);
  if (state.ready) {
    await element('#generate').onclick();
    const submitted = requests.find(r => r.url === '/api/jobs').data;
    assert.deepEqual(submitted.parent_assets, ['source-asset']);
    assert.deepEqual(submitted.references, state.references);
    assert.equal(submitted.controls.reference, upload.file);
  }
}

// A Workspace handoff followed by a different local file must not record the new output as a child of
// the old asset: the workspace lineage column, the run recipe and every export read parent_assets.
async function swapDropsHandoffLineage(handoffPreset) {
  const attached = {file: 'from-source-asset.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'source-asset'};
  const local = {file: 'unrelated-local-file.png', sha256: 'c'.repeat(64), width: 640, height: 640};
  const {element, requests, run, parents} = sandbox(attached, local);
  run(`selectPreset('plain');
    assetState.assets=[{id:'source-asset',title:'Original',media_type:'image',tags:[],source:{},lineage:[],bytes:1024}];openAsset('source-asset');`);
  await run(`handoffAsset('source-asset',${JSON.stringify(handoffPreset)})`);
  assert.deepEqual(parents(), ['source-asset'], 'The handoff records the source asset');
  element('#reference').files = [localFile()];
  element('#reference').onchange();
  assert.deepEqual(parents(), [], 'Choosing a different local file drops the handoff lineage');
  await element('#generate').onclick();
  const submitted = requests.find(r => r.url === '/api/jobs').data;
  assert.deepEqual(submitted.parent_assets, [], 'A swapped reference must never be submitted as a child of the old asset');
  assert.equal(submitted.controls.reference, local.file, 'The unrelated local file is what is actually generated from');
  element('#saveName').value = 'Swapped reference';
  await element('#save').onclick();
  assert.deepEqual(requests.find(r => r.url === '/api/setups').data.recipe.parent_assets, [], 'Saved setups carry the same corrected lineage');
}

// On a role board the lineage is per slot: replacing one image drops only that image's source.
async function slotSwapKeepsTheOtherSlots() {
  const attached = {file: 'from-asset-a.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'asset-a'};
  const local = {file: 'unrelated-local-file.png', sha256: 'c'.repeat(64), width: 640, height: 640};
  const {element, requests, run, parents} = sandbox(attached, local);
  run(`selectPreset('qwen-3ref');
    Object.assign(referenceRecords[0],{file:'from-asset-a.png',sha256:'a'.repeat(64),width:512,height:768,parent_asset:'asset-a',missing:false});
    Object.assign(referenceRecords[1],{file:'from-asset-b.png',sha256:'b'.repeat(64),width:512,height:768,parent_asset:'asset-b',missing:false});
    Object.assign(referenceRecords[2],{file:'own-photo.png',sha256:'d'.repeat(64),width:512,height:768,missing:false});
    parentAssets=['asset-a','asset-b'];renderReferenceSlots();`);
  await run(`uploadRoleFile(1,${JSON.stringify(localFile('replacement.png'))})`);
  assert.deepEqual(parents(), ['asset-a'], 'Only the replaced slot loses its source');
  assert.equal(run('referencesReady()'), true, 'The board is still complete');
  await element('#generate').onclick();
  const submitted = requests.find(r => r.url === '/api/jobs').data;
  assert.deepEqual(submitted.parent_assets, ['asset-a']);
  assert.equal(submitted.references[1].file, local.file);
  assert.equal(submitted.references[1].parent_asset, null, 'A locally uploaded slot claims no source asset');
  element('#referenceCards').onclick({target: {closest: selector => selector === '[data-ref-clear]' ? {dataset: {refClear: '0'}} : null}});
  assert.deepEqual(parents(), [], 'Clearing the last asset-backed slot clears the lineage');
  assert.equal(element('#generate').disabled, true, 'An empty slot still blocks generation');
}

(async () => {
  await check('qwen-1ref', null, 1);
  await check('qwen-3ref', null, 3);
  await check('plain', null, 0);
  await check('plain', 'wan22-i2v', 0);
  await check('plain', 'trellis-auto-cutout', 0);
  for (const target of ['anime-detail-fix', 'krea-refine']) {
    await check('plain', target, 0);
    await check('qwen-3ref', target, 0, true);
  }
  for (const target of ['anime-detail-fix', 'krea-refine']) await swapDropsHandoffLineage(target);
  await slotSwapKeepsTheOtherSlots();
  console.log('Gallery handoff contracts passed: lineage and role metadata survive save and submission, and a swapped reference drops the stale source.');
})().catch(error => {console.error(error); process.exitCode = 1;});
