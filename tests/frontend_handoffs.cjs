// Exercise the real gallery, reference and save/submit handlers without a GPU or browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function check(presetId, targetPreset, slots, workspace = false) {
  const elements = new Map(), requests = [];
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', files: [], textContent: '', classList: {toggle() {}},
      addEventListener() {}, scrollIntoView() {}, close() {}, showModal() {},
    });
    return elements.get(selector);
  };
  const upload = {file: 'retained.png', sha256: 'a'.repeat(64), width: 512, height: 768};
  const context = vm.createContext({
    document: {querySelector: element, querySelectorAll: () => [], addEventListener() {}},
    URL, Blob, location: {hash: ''}, setInterval() {},
    fetch: async (url, options = {}) => {
      if (url === '/api/catalog') return new Promise(() => {}); // Hold page startup.
      if (options.method === 'POST') requests.push({url, data: options.headers?.['Content-Type'] === 'application/json' ? JSON.parse(options.body) : null});
      const data = url === '/api/assets/reference' || url === '/api/upload' ? upload
        : url === '/api/jobs' ? {id: 'child-job', message: 'Queued'}
        : url.startsWith('/api/inspect/') ? {requirements: [], nodes: [], graph: {}}
        : {};
      return {ok: true, json: async () => data, blob: async () => new Blob(['image'], {type: 'image/png'})};
    },
  });
  for (const name of ['app.js', 'references.js', 'workspace.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static', name), 'utf8'), context);
  }
  const presets = ['plain', 'gentle-variation', 'qwen-1ref', 'qwen-3ref', 'wan22-i2v', 'trellis-auto-cutout', 'anime-detail-fix', 'krea-refine'].map(id => ({
    id, name: id, modality: id === 'wan22-i2v' ? 'video' : id === 'trellis-auto-cutout' ? '3d' : 'image',
    reference: id === 'plain' ? undefined : ['4', 'image'],
    reference_slots: id.startsWith('qwen') ? Array.from({length: id === 'qwen-1ref' ? 1 : 3}, () => ({role: 'identity', contribution: 'Keep the character', avoid: 'Background'})) : undefined,
  }));
  vm.runInContext(`catalog=${JSON.stringify({presets})}; online=schemaAvailable=true;
    jobs=[{id:'source-job',outputs:[{asset_id:'source-asset'}]}];
    refresh=async()=>{}; loadSetups=async()=>{};
    selectPreset(${JSON.stringify(presetId)});`, context);
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
  console.log('Gallery handoffs retain lineage and role metadata through save and submission.');
})().catch(error => {console.error(error); process.exitCode = 1;});
