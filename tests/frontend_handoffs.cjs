// Exercise the real gallery, reference and save/submit handlers without a GPU or browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const StudioContinuation = require('../app/static/continuation-core.js');
const StudioAssetRecovery = require('../app/static/asset-recovery.js');

const templateSha = 'b'.repeat(64);
const operation = id => id === 'plain' ? 'new-image'
  : id === 'wan22-i2v' || id === 'h3-first-last' ? 'image-to-video'
  : id === 'trellis-auto-cutout' ? 'image-to-3d'
  : id.startsWith('qwen') ? 'instruction-edit'
  : id === 'anime-detail-fix' ? 'localized-detail' : 'image-to-image';

const presets = ['plain', 'gentle-variation', 'qwen-1ref', 'qwen-3ref', 'wan22-i2v', 'trellis-auto-cutout', 'anime-detail-fix', 'krea-refine'].map(id => ({
  id, name: id, modality: id === 'wan22-i2v' ? 'video' : id === 'trellis-auto-cutout' ? '3d' : 'image',
  reference: id === 'plain' ? undefined : ['4', 'image'],
  reference_slots: id.startsWith('qwen') ? Array.from({length: id === 'qwen-1ref' ? 1 : 3}, () => ({role: 'identity', contribution: 'Keep the character', avoid: 'Background'})) : undefined,
  positive: ['1', 'text'], defaults: {},
  continuation_capability: {consumes_source: id !== 'plain', operation: operation(id), prompt_role: id.startsWith('qwen') ? 'instruction' : id === 'wan22-i2v' ? 'motion' : 'description', requires_mask: false, reference_count: id.startsWith('qwen') ? (id === 'qwen-1ref' ? 1 : 3) : 1, template_sha256: templateSha},
})).concat([{id: 'h3-first-last', name: 'h3-first-last', modality: 'video', reference: ['4', 'image'], last_reference: ['5', 'image']}]);

// Two Combine boards with opposite reference orders: the 4B keeps its source as image 1, the 9B puts the board picture first.
for (const [id, boardLabel, keepLabel] of [['combine-4b', 'Pose picture (image 2)', 'Picture to keep (image 1)'], ['combine-9b', 'Pose picture (image 1)', 'Picture to keep (image 2)']]) {
  presets.push({id, name: id, modality: 'image', positive: ['1', 'text'], defaults: {}, last_reference: ['20', 'image'], last_reference_label: keepLabel,
    reference_board: {min: 1}, reference_board_label: boardLabel, reference_slots: [{role: 'pose', contribution: '', avoid: ''}],
    continuation_capability: {consumes_source: true, operation: 'combine', prompt_role: 'description', requires_mask: false, reference_count: 2, template_sha256: templateSha}});
}

presets[presets.length - 3].positive = ['1', 'text'];
presets[presets.length - 3].defaults = {};
presets[presets.length - 3].continuation_capability = {consumes_source: true, operation: 'image-to-video', prompt_role: 'motion', requires_mask: false, reference_count: 2, template_sha256: templateSha};

function sourceAttachment(file, parent = 'source-asset', sha256 = 'a'.repeat(64)) {
  return {file, sha256, width: 512, height: 768, parent_asset: parent, context: {
    version: 1, asset_id: parent, sha256, title: 'Exact selected output', preset_id: 'plain', preset_name: 'Source fixture',
    prompt_id: 'prompt-1', positive: 'The exact retained source description.', negative: 'blur',
    prompt_origin: 'submitted-output', prompt_role: 'description', width: 512, height: 768,
  }};
}

// One page sandbox over the real scripts. `attached` answers /api/assets/reference, which carries the
// parent_asset lineage claim; `local` answers /api/upload, which never does. That asymmetry is what the
// swap contracts below turn on, so the two responses must stay distinguishable. `availability` maps a
// saved reference file to its sha256 for /api/references/check; anything absent reads as unavailable.
function sandbox(attached, local, availability = null, diagnostic = null) {
  const elements = new Map(), requests = [];
  let clickHandler;
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', files: [], textContent: '', classList: {toggle() {}},
      querySelectorAll() {return [];}, addEventListener(name, handler) {(this.listeners ||= {})[name] = handler;}, scrollIntoView() {}, focus() {this.focused=true;}, close() {this.open=false;}, showModal() {this.open=true;},
    });
    return elements.get(selector);
  };
  const context = vm.createContext({
    document: {querySelector: element, querySelectorAll: () => [], addEventListener(name, handler) {if (name === 'click') clickHandler = handler;}},
    URL, Blob, StudioContinuation, StudioAssetRecovery,
    sessionStorage: (store => ({getItem: k => store.has(k) ? store.get(k) : null, setItem(k, v) {store.set(k, String(v));}, removeItem(k) {store.delete(k);}}))(new Map()),
    window: {confirm: () => true}, location: {hash: ''}, setInterval() {},
    fetch: async (url, options = {}) => {
      if (url === '/api/catalog') return new Promise(() => {}); // Hold page startup.
      if (options.method === 'POST') requests.push({url, data: options.headers?.['Content-Type'] === 'application/json' ? JSON.parse(options.body) : null});
      const data = url === '/api/assets/reference' ? attached : url === '/api/upload' ? local
        : url === '/api/references/check' ? JSON.parse(options.body).files.map(file => ({file, available: Boolean(availability?.[file]), sha256: availability?.[file]}))
        : url === '/api/jobs' ? {id: 'child-job', message: 'Queued'}
        : url.includes('/i2v-diagnostic') ? (diagnostic || {})
        : url.startsWith('/api/inspect/') ? {requirements: [], nodes: [], graph: {}}
        : {};
      return {ok: !(url.includes('/i2v-diagnostic') && diagnostic?.error), json: async () => data, blob: async () => new Blob(['image'], {type: 'image/png'})};
    },
  });
  for (const name of ['app.js', 'reference-model.js', 'references.js', 'workspace.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static', name), 'utf8'), context);
  }
  const run = source => vm.runInContext(source, context);
  run(`catalog=${JSON.stringify({presets})}; online=schemaAvailable=true;
    jobs=[{id:'source-job',outputs:[{asset_id:'source-asset'}]}];
    refresh=async()=>{}; loadSetups=async()=>{};`);
  return {element, requests, context, run, click: target => clickHandler({target}), parents: () => JSON.parse(run('JSON.stringify(parentAssets)'))};
}

// The brief's "what to avoid" is part of the brief, not an advanced setting: the disclosure opens
// whenever the recipe binds a negative prompt, stays collapsible, and remembers a manual collapse
// for this tab only (#278 friction 3). A recipe that binds nothing keeps the field hidden.
async function avoidWordingIsVisibleWhenTheRecipeBindsIt() {
  const {element, context, run} = sandbox(sourceAttachment('a'.repeat(32) + '_retained.png'), {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
  run(`catalog.presets.push({id:'binds-avoid',name:'binds-avoid',modality:'image',positive:['1','text'],negative:['2','text'],defaults:{negative:'blurry'}},
                            {id:'no-avoid',name:'no-avoid',modality:'image',positive:['1','text'],defaults:{}});
       selectPreset('binds-avoid');`);
  assert.equal(element('#negativeWrap').hidden, false, 'A bound negative prompt is shown');
  assert.equal(element('#negativeWrap').open, true, 'A bound negative prompt is open by default');
  assert.equal(element('#negative').value, 'blurry');
  context.sessionStorage.setItem('studio-negative-collapsed', '1');
  run(`selectPreset('binds-avoid');`);
  assert.equal(element('#negativeWrap').open, false, 'A manual collapse is remembered for this tab');
  context.sessionStorage.removeItem('studio-negative-collapsed');
  run(`selectPreset('no-avoid');`);
  assert.equal(element('#negativeWrap').hidden, true, 'A recipe that binds no negative prompt still hides the field');
}

const localFile = (name = 'unrelated.png') => ({name, size: 2048, type: 'image/png'});
const flush = () => new Promise(resolve => setImmediate(resolve)); // Drain a fire-and-forget restore.

async function check(presetId, targetPreset, slots, workspace = false) {
  const upload = sourceAttachment('a'.repeat(32) + '_retained.png');
  const {element, requests, context, run} = sandbox(upload, {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
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
  const canSubmit = !element('#generate').disabled;
  if (slots) {
    assert.equal(state.references[0].file, upload.file);
    assert.equal(state.references[0].sha256, upload.sha256);
    assert.equal(state.references[0].role, 'identity');
    assert.equal(state.ready, slots === 1, 'Unfilled additional slots must still block generation');
    assert.equal(canSubmit, slots === 1 && !selectedRequiresNewPrompt(state.preset), 'Source inputs and task-specific wording both govern readiness');
  }
  element('#saveName').value = 'Retained gallery handoff';
  await element('#save').onclick();
  const saved = requests.find(r => r.url === '/api/setups').data.recipe;
  assert.deepEqual(saved.parent_assets, ['source-asset']);
  assert.deepEqual(saved.references, state.references);
  if (canSubmit) {
    await element('#generate').onclick();
    const submitted = requests.find(r => r.url === '/api/jobs').data;
    assert.deepEqual(submitted.parent_assets, ['source-asset']);
    assert.deepEqual(submitted.references, state.references);
    assert.equal(submitted.controls.reference, upload.file);
  }
}

function selectedRequiresNewPrompt(id) {
  return id.startsWith('qwen') || id === 'wan22-i2v' || id === 'h3-first-last';
}

// A Workspace handoff followed by a different local file must not record the new output as a child of
// the old asset: the workspace lineage column, the run recipe and every export read parent_assets.
async function swapDropsHandoffLineage(handoffPreset) {
  const attached = sourceAttachment('a'.repeat(32) + '_from-source-asset.png');
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
  assert.equal(requests.some(r => r.url === '/api/jobs'), false, 'A source-bound continuation cannot silently submit a replacement file');
  element('#saveName').value = 'Swapped reference';
  await element('#save').onclick();
  assert.equal(requests.some(r => r.url === '/api/setups'), false, 'An unstaged replacement cannot be reported saved');
  assert.match(element('#setupStatus').textContent,/not uploaded/);
  assert.deepEqual(parents(), [], 'The unsaved replacement still drops the old source');
}

// The board summary states the reference order the recipe's own labels declare: the 9B Combine keeps the board
// picture as image 1 and the source follows; the 4B keeps the source as image 1 (the summary used to say the 4B
// order for both, contradicting the 9B recipe's labels on the same screen).
async function boardSummaryFollowsTheRecipeOrder() {
  const {run, element} = sandbox(sourceAttachment('a'.repeat(32) + '_from-asset-a.png'), {file: 'own.png', sha256: 'c'.repeat(64), width: 512, height: 768});
  run(`selectPreset('combine-9b')`);
  assert.match(element('#referenceSummary').textContent, /the pose picture on the board is image 1 \(its structure is kept\), the picture you keep follows it as image 2/);
  run(`selectPreset('combine-4b')`);
  assert.match(element('#referenceSummary').textContent, /image 1 is the picture you keep, a pose picture on the board follows it as image 2 \(and 3\)/);
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
  element('#positive').value = 'Keep the two retained subjects and use the replacement pose.';
  await element('#generate').onclick();
  const submitted = requests.find(r => r.url === '/api/jobs').data;
  assert.deepEqual(submitted.parent_assets, ['asset-a']);
  assert.equal(submitted.references[1].file, local.file);
  assert.equal(submitted.references[1].parent_asset, null, 'A locally uploaded slot claims no source asset');
  element('#referenceCards').onclick({target: {closest: selector => selector === '[data-ref-clear]' ? {dataset: {refClear: '0'}} : null}});
  assert.deepEqual(parents(), [], 'Clearing the last asset-backed slot clears the lineage');
  assert.equal(element('#generate').disabled, true, 'An empty slot still blocks generation');
}

// Two reference inputs are two attachment points: changing the last frame must not disown the source
// attached to the first frame, whose copy is still what the recipe generates from.
async function firstLastFramesAttributeSeparately() {
  const attached = sourceAttachment('a'.repeat(32) + '_from-asset-a.png', 'asset-a');
  const local = {file: 'own-last-frame.png', sha256: 'c'.repeat(64), width: 512, height: 768};
  const {element, requests, run, parents} = sandbox(attached, local);
  run(`selectPreset('plain');
    assetState.assets=[{id:'asset-a',title:'Original',media_type:'image',tags:[],source:{},lineage:[],bytes:1024}];openAsset('asset-a');`);
  await run(`handoffAsset('asset-a','h3-first-last')`);
  assert.deepEqual(parents(), ['asset-a'], 'The handoff attaches the source to the first frame');
  assert.equal(element('#generate').disabled, true, 'An authored last-frame example cannot satisfy a continuation');
  element('#lastReference').files = [localFile('last.png')];
  element('#lastReference').onchange();
  assert.deepEqual(parents(), ['asset-a'], 'Choosing a last frame from disk keeps the first frame lineage');
  element('#positive').value = 'A slow orbit around the subject.';
  run('updateReady()');
  assert.equal(element('#generate').disabled, false, 'An explicit local last frame makes the reviewed continuation runnable');
  await element('#generate').onclick();
  const submitted = requests.find(r => r.url === '/api/jobs').data;
  assert.deepEqual(submitted.parent_assets, ['asset-a']);
  assert.equal(submitted.controls.reference, attached.file, "The source asset's copy is still the first frame");
  assert.equal(submitted.controls.last_reference, local.file);
  element('#reference').files = [localFile('first.png')];
  element('#reference').onchange();
  assert.deepEqual(parents(), [], 'Changing the first frame releases exactly the source it held');
}

// #108: two inputs filled from two different saved assets is exactly the shape the single-parent
// heuristic cannot reconstruct, so the mapping travels with the setup. Saving, reloading in a fresh
// page and swapping the first frame must release that frame's source and keep the other one.
async function savedSetupCarriesPerInputAttribution() {
  const first = {file: 'from-asset-a.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'asset-a'};
  const local = {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768};
  const saving = sandbox(first, local);
  saving.run(`selectPreset('h3-first-last');
    uploaded='from-asset-a.png';claimInputParent('reference','asset-a');
    lastUploaded='from-asset-b.png';claimInputParent('lastReference','asset-b');`);
  assert.deepEqual(saving.parents(), ['asset-a', 'asset-b'], 'Both frames declare their own source');
  saving.element('#saveName').value = 'Two frames, two sources';
  await saving.element('#save').onclick();
  const recipe = saving.requests.find(r => r.url === '/api/setups').data.recipe;
  assert.deepEqual(recipe.parent_by_input, {reference: 'asset-a', lastReference: 'asset-b'}, 'The setup records which input each source is on');

  const {element, requests, run, parents} = sandbox(first, local); // A fresh page: nothing carries over.
  run(`applySaved(${JSON.stringify(recipe)});`); // Exactly what saved() hands applySaved on a reload.
  assert.deepEqual(parents(), ['asset-a', 'asset-b'], 'The reload keeps the declared lineage');
  element('#reference').files = [localFile('replacement-first.png')];
  element('#reference').onchange();
  assert.deepEqual(parents(), ['asset-b'], 'Swapping the first frame after a reload releases only its source');
  element('#positive').value = 'Move slowly from the first frame to the last.';
  await element('#generate').onclick();
  const submitted = requests.find(r => r.url === '/api/jobs').data;
  assert.deepEqual(submitted.parent_assets, ['asset-b']);
  assert.equal(submitted.controls.reference, local.file);
  assert.equal(submitted.controls.last_reference, 'from-asset-b.png');
}

// A setup saved before #108 has no mapping. It must restore exactly as it did then: the unambiguous
// single-parent, single-input case is attributed, and anything ambiguous stays untouched.
async function legacySetupWithoutAttributionIsUnchanged() {
  const first = {file: 'from-asset-a.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'asset-a'};
  const local = {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768};
  const legacy = (controls, parent_assets) => ({preset: 'h3-first-last', controls, batch_count: 1, parent_assets, references: []});

  const ambiguous = sandbox(first, local);
  ambiguous.run(`applySaved(${JSON.stringify(legacy({reference: 'from-asset-a.png', last_reference: 'from-asset-b.png'}, ['asset-a', 'asset-b']))});`);
  assert.deepEqual(JSON.parse(ambiguous.run('JSON.stringify(parentByInput)')), {}, 'A legacy two-source setup stays unattributed');
  ambiguous.element('#reference').files = [localFile('replacement-first.png')];
  ambiguous.element('#reference').onchange();
  assert.deepEqual(ambiguous.parents(), ['asset-a', 'asset-b'], 'An unattributed parent is still never dropped');

  for (const [label, record] of [['no field at all', legacy({reference: 'from-asset-a.png'}, ['asset-a'])],
    // A draft written before #112 normalizes with an empty mapping; that is absence, not "nothing was
    // attributed", so the fallback must still run or the reload regresses a case that works on main.
    ['an empty mapping', {...legacy({reference: 'from-asset-a.png'}, ['asset-a']), parent_by_input: {}}]]) {
    const single = sandbox(first, local);
    single.run(`applySaved(${JSON.stringify(record)});`);
    assert.deepEqual(JSON.parse(single.run('JSON.stringify(parentByInput)')), {reference: 'asset-a'}, 'The unambiguous legacy case is still attributed with ' + label);
    single.element('#reference').files = [localFile('replacement-first.png')];
    single.element('#reference').onchange();
    assert.deepEqual(single.parents(), [], 'and a swap still releases it with ' + label);
  }
}

// A job-exported recipe is rebuilt server-side by compile_references, so its records never carry a
// parent_asset - now or later. An unattributed parent must survive an edit to any slot.
async function importedRecipeKeepsUnattributedParents() {
  const attached = {file: 'from-asset-a.png', sha256: 'a'.repeat(64), width: 512, height: 768, parent_asset: 'asset-a'};
  const local = {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768};
  const available = {'exported-1.png': '1'.repeat(64), 'exported-2.png': '2'.repeat(64), 'exported-3.png': '3'.repeat(64)};
  const {element, requests, run, parents} = sandbox(attached, local, available);
  const references = Object.entries(available).map(([file, sha256], index) => ({role: 'identity', contribution: 'Keep the character', avoid: 'Background', file, sha256, width: 512, height: 768, slot: index + 1}));
  run(`applySaved(${JSON.stringify({preset: 'qwen-3ref', controls: {positive: 'A study'}, batch_count: 1, parent_assets: ['asset-a', 'asset-b'], references})});`);
  await flush();
  assert.deepEqual(parents(), ['asset-a', 'asset-b'], 'An imported recipe keeps the lineage it declares');
  assert.equal(run('referencesReady()'), true, 'The imported references check out as available');
  await run(`uploadRoleFile(2,${JSON.stringify(localFile('replacement.png'))})`);
  assert.deepEqual(parents(), ['asset-a', 'asset-b'], 'Editing a slot with no recorded source disowns nothing');
  element('#referenceCards').onclick({target: {closest: selector => selector === '[data-ref-clear]' ? {dataset: {refClear: '0'}} : null}});
  assert.deepEqual(parents(), ['asset-a', 'asset-b'], 'Clearing a slot with no recorded source disowns nothing');
  assert.equal(element('#generate').disabled, true, 'The cleared slot still blocks generation');
  assert.equal(requests.some(r => r.url === '/api/jobs'), false, 'Importing and editing must never submit generation');
}

// The Pull-from-library picker in studio-workbench.js drives this exact sequence against one slot.
// The workbench module itself needs a DOM this sandbox does not have (window, createElement, node
// insertion, dialogs, localStorage), so the shipped picker is covered by tests/studio_browser_smoke.py;
// what is pinned here is the shared helper it calls, plus the wiring that it still calls it.
async function pullingIntoASlotReplacesItsSource() {
  const attached = {file: 'from-asset-b.png', sha256: 'b'.repeat(64), width: 512, height: 768, parent_asset: 'asset-b'};
  const {run, parents} = sandbox(attached, {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
  run(`selectPreset('qwen-3ref');
    Object.assign(referenceRecords[0],{file:'from-asset-a.png',sha256:'a'.repeat(64),width:512,height:768,parent_asset:'asset-a',missing:false});
    parentAssets=['asset-a'];renderReferenceSlots();`);
  await run(`(async()=>{const result=await post('/api/assets/reference',{id:'asset-b'});const previous=referenceRecords[0].parent_asset;
    Object.assign(referenceRecords[0],result,{missing:false});replaceParentAsset('reference',previous,'asset-b');})()`);
  assert.deepEqual(parents(), ['asset-b'], 'Pulling a new source into a slot replaces the one it held');
  const workbench = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');
  assert.match(workbench, /replaceParentAsset\(/, 'The library picker must attribute through the shared helper');
  assert.match(workbench, /beginContinuation\(/, 'The workbench handoff must enter the shared source-bound transition');
  assert.doesNotMatch(workbench, /parentAssets=\[\.\.\.new Set/, 'The picker must not append lineage without releasing the slot it replaced');
}

async function i2vDiagnosticEligibilityAndRetry() {
  const report={job:{},source:{},requested:{},preprocessing:{},video:{probe:{}},artifacts:{},graph:{}};
  const supported=sandbox(null,null,null,report);
  supported.run(`assetState.assets=[{id:'wan-video',title:'Wan video',media_type:'video',job_id:'wan-job',preset_id:'wan22-i2v',source:{},lineage:[],tags:[],bytes:1024}];openAsset('wan-video');`);
  assert.match(supported.element('#assetDiagnostic').innerHTML,/data-i2v-diagnostic="wan-job"/,'Workspace exposes diagnostics for recorded Wan I2V output');
  await supported.click({closest: selector => selector === '[data-i2v-diagnostic]' ? {dataset:{i2vDiagnostic:'wan-job'},disabled:false} : null});
  assert.match(supported.element('#assetDiagnostic').innerHTML,/Offline I2V diagnostic/,'Successful diagnostics render the report');

  const unsupported=sandbox(null,null);
  for (const preset_id of ['av-preview','generic-video']) {
    unsupported.run(`assetState.assets=[{id:'unsupported',title:'Unsupported video',media_type:'video',job_id:'other-job',preset_id:${JSON.stringify(preset_id)},source:{},lineage:[],tags:[],bytes:1024}];openAsset('unsupported');`);
    assert.equal(unsupported.element('#assetDiagnostic').innerHTML,'','Workspace hides diagnostics for unsupported video jobs');
  }

  const failed=sandbox(null,null,null,{error:'I2V diagnostic unavailable: recorded Wan output is missing'});
  failed.run(`assetState.assets=[{id:'wan-video',title:'Wan video',media_type:'video',job_id:'wan-job',preset_id:'wan22-i2v',source:{},lineage:[],tags:[],bytes:1024}];openAsset('wan-video');`);
  await failed.click({closest: selector => selector === '[data-i2v-diagnostic]' ? {dataset:{i2vDiagnostic:'wan-job'},disabled:false} : null});
  assert.match(failed.element('#assetDiagnostic').innerHTML,/data-i2v-diagnostic="wan-job"/,'Failed diagnostics restore the retry button');
}

async function explicitLocalAbandonment() {
  const {element, requests, run} = sandbox({}, {});
  run(`jobs=[{id:'uncertain-job',preset_name:'Lost response',status:'uncertain',message:'Unknown',outputs:[],prompt_ids:[],can_abandon:true,abandon_requires_acknowledgement:true}];renderJobs();`);
  const html=element('#gallery').innerHTML;
  assert.match(html,/data-abandon-ack/);assert.match(html,/does not cancel remote work/);
  assert.match(html,/maxlength="1000"/);assert.equal(requests.length,0,'Rendering never sends an abandonment or generation');
  const reason={value:''},ack={checked:false};
  const button={dataset:{job:'uncertain-job'},disabled:false,closest:()=>({querySelector:selector=>selector==='[data-abandon-reason]'?reason:ack})};
  const event={target:{closest:selector=>selector==='.abandonJob'?button:null}};
  await element('#gallery').onclick(event);assert.equal(requests.length,0);
  reason.value='Retain the lost receipt';await element('#gallery').onclick(event);assert.equal(requests.length,0);
  ack.checked=true;await element('#gallery').onclick(event);
  assert.deepEqual(requests,[{url:'/api/jobs/uncertain-job/abandon',data:{reason:'Retain the lost receipt',acknowledge_unknown:true}}]);
  assert.equal(button.disabled,false);
  run(`jobs=[{id:'abandoned',preset_name:'Preserved',status:'abandoned',message:'Retained',outputs:[],prompt_ids:[],abandonment:{basis:'outcome_unknown',reason:'<script>not markup</script>'}}];renderJobs();`);
  assert.match(element('#gallery').innerHTML,/&lt;script&gt;/);assert.doesNotMatch(element('#gallery').innerHTML,/class="abandonJob"/);
  assert.match(element('#gallery').innerHTML,/Remote outcome remains unknown/);
}

// #940: Problems shows the newest five open problems; put-away ones stay one toggle away.
async function problemsPanelPutAway() {
  const {element, requests, run} = sandbox({}, {});
  const failed=i=>`{id:'f${i}',preset_name:'Failed ${i}',status:'failed',message:'OOM',outputs:[],prompt_ids:[],created_at:${i},can_put_away:true,put_away:false}`;
  run(`jobs=[${[1,2,3,4,5,6,7].map(failed).join(',')},{id:'away',preset_name:'Put away one',status:'failed',message:'Old',outputs:[],prompt_ids:[],created_at:0,put_away:true,put_away_basis:'owner',put_away_at:100,can_bring_back:true},{id:'tracking',preset_name:'Still tracked',status:'uncertain',message:'Unknown',outputs:[],prompt_ids:['p'],created_at:9,can_stop_tracking:true,can_put_away:false,put_away:false}];renderJobs();`);
  let html=element('#gallery').innerHTML;
  assert.match(html,/Problems · 8 run\(s\) · 1 put away/);
  assert.equal((html.match(/data-put-away="true"/g)||[]).length,4,'Newest five shown; the tracked uncertain job offers no Put away');
  assert.match(html,/Stop tracking before putting this away/);
  assert.match(html,/3 older problem\(s\) not shown/);assert.doesNotMatch(html,/Failed 3/);
  assert.doesNotMatch(html,/Put away one/);assert.match(html,/Show put away \(1\)/);
  assert.equal(requests.length,0,'Rendering sends nothing');
  const toggle=value=>({target:{closest:selector=>selector==='[data-problems-toggle]'?{dataset:{problemsToggle:value}}:null}});
  await element('#gallery').onclick(toggle('away'));html=element('#gallery').innerHTML;
  assert.match(html,/Put away one/);assert.match(html,/data-put-away="false"/);assert.match(html,/Hide put away/);
  await element('#gallery').onclick(toggle('all'));html=element('#gallery').innerHTML;
  assert.match(html,/Failed 1/);assert.match(html,/Show newest 5 only/);
  assert.equal(requests.length,0,'Toggles are local presentation only');
  const button={dataset:{job:'f7',putAway:'true'},disabled:false};
  await element('#gallery').onclick({target:{closest:selector=>selector==='.putAway'?button:null}});
  assert.deepEqual(requests.filter(r=>r.url.endsWith('/put-away')),[{url:'/api/jobs/f7/put-away',data:{put_away:true}}]);
  assert.equal(button.disabled,false);
  const back={dataset:{job:'away',putAway:'false'},disabled:false};
  await element('#gallery').onclick({target:{closest:selector=>selector==='.putAway'?back:null}});
  assert.deepEqual(requests.filter(r=>r.url.endsWith('/put-away')).at(-1),{url:'/api/jobs/away/put-away',data:{put_away:false}});
  assert.ok(requests.every(r=>!/\/(resume|stop-tracking|abandon)$|^\/api\/jobs$/.test(r.url)),'Put away never resumes, stops, abandons or submits');
}

// #117: an unavailable check may keep a source claim in memory but clear the attachment.
// Named setup persistence must not turn that uncertainty into an unattributed durable parent.
async function unresolvedInputLineageCannotBeSaved() {
  for(const missing of ['reference','lastReference']) {
    const s=sandbox(null,null);
    s.run(`selectPreset('h3-first-last');uploaded='first.png';lastUploaded='last.png';
      parentAssets=['asset-a','asset-b'];parentByInput={reference:'asset-a',lastReference:'asset-b'};
      ${missing==='reference'?'uploaded':'lastUploaded'}=null;`);
    s.element('#saveName').value='Recoverable draft';s.element('#positive').value='Keep this wording';
    await s.element('#save').onclick();
    assert.equal(s.requests.filter(r=>r.url==='/api/setups').length,0,'No durable parent for an empty '+missing);
    assert.equal(s.element('#saveName').value,'Recoverable draft');
    assert.equal(s.element('#positive').value,'Keep this wording');
    assert.deepEqual(s.parents(),['asset-a','asset-b'],'Failed availability is not evidence to discard in-memory lineage');
    assert.match(s.element('#status').textContent,/reattach/i,'Recovery instruction names the next action');
    assert.match(s.element('#status').textContent,missing==='reference'?/first frame/i:/last frame/i);
    s.run(`${missing==='reference'?'uploaded':'lastUploaded'}='restored.png';`);
    await s.element('#save').onclick();
    const saved=s.requests.find(r=>r.url==='/api/setups').data.recipe;
    assert.deepEqual(saved.parent_by_input,{reference:'asset-a',lastReference:'asset-b'});
    assert.deepEqual(saved.parent_assets,['asset-a','asset-b']);
    const reload=sandbox(null,null);reload.run(`applySaved(${JSON.stringify(saved)})`);
    reload.element(missing==='reference'?'#reference':'#lastReference').files=[localFile()];
    reload.element(missing==='reference'?'#reference':'#lastReference').onchange();
    assert.deepEqual(reload.parents(),[missing==='reference'?'asset-b':'asset-a'],'Reload and swap releases only the replaced source');
  }
  const legacy=sandbox(null,null);
  legacy.run(`selectPreset('h3-first-last');parentAssets=['historical-parent'];parentByInput={};`);
  legacy.element('#saveName').value='Legacy unbound history';await legacy.element('#save').onclick();
  assert.deepEqual(legacy.requests.find(r=>r.url==='/api/setups').data.recipe.parent_assets,['historical-parent'],'Never invent attribution for historical parents');
}

// Review #202: choosing a replacement from disk is not yet a persisted upload.
async function unstagedLocalFilesCannotBeSaved() {
  for(const input of ['reference','lastReference']) {
    const s=sandbox(null,null);
    s.run(`selectPreset('h3-first-last');uploaded='first.png';lastUploaded='last.png';claimInputParent('reference','asset-a');claimInputParent('lastReference','asset-b');`);
    s.element('#'+input).files=[localFile('replacement.png')];s.element('#'+input).onchange();
    s.element('#saveName').value='Keep pending local selection';
    const parents=s.parents();await s.element('#save').onclick();
    assert.equal(s.requests.length,0,'An unstaged selected '+input+' must neither save nor upload implicitly');
    assert.equal(s.element('#saveName').value,'Keep pending local selection');
    assert.equal(s.element('#'+input).files[0].name,'replacement.png');
    assert.deepEqual(s.parents(),parents,'Save must not recreate the released old source');
    assert.match(s.element('#setupStatus').textContent,/not uploaded.*Asset library.*Pull from library/);
    assert.match(s.element('#setupStatus').textContent,input==='reference'?/first frame/:/Last frame/);
    // Clearing a browser-only selection permits the already supported source-free setup.
    s.element('#'+input).files=[];s.element('#'+input).onchange();
    await s.element('#save').onclick();
    assert.equal(s.requests.filter(r=>r.url==='/api/setups').length,1);
  }
}


// #345: a board recipe has a named continuation source and role slots at the same time.
// Copying that same asset into a role slot must not let clearing the slot erase the source lineage.
async function boardContinuationSourceHasItsOwnLineageClaim() {
  const attached = sourceAttachment('source-copy.png', 'source-asset');
  const local = {file: 'replacement.png', sha256: 'c'.repeat(64), width: 640, height: 640};
  const s = sandbox(attached, local);
  s.run(`selectPreset('combine-9b');
    lastUploaded='continuation-source.png';
    claimInputParent('lastReference','source-asset');
    Object.assign(referenceRecords[0],{file:'source-copy.png',sha256:'a'.repeat(64),width:512,height:768,parent_asset:'source-asset',missing:false});
    parentAssets=['source-asset'];renderReferenceSlots();`);
  assert.deepEqual(JSON.parse(s.run('JSON.stringify(parentByInput)')),
    {lastReference:'source-asset'}, 'The continuation source needs an independent named-input claim on board recipes');
  s.element('#saveName').value = 'Board continuation lineage';
  await s.element('#save').onclick();
  const saved = s.requests.find(request => request.url === '/api/setups').data.recipe;
  assert.deepEqual(saved.parent_by_input, {lastReference:'source-asset'});
  assert.deepEqual(saved.parent_assets, ['source-asset']);
  s.run(`selectPreset('plain');applySaved(${JSON.stringify(saved)});`);
  await flush(); // Settle the saved role availability check before the replacement upload.
  assert.deepEqual(JSON.parse(s.run('JSON.stringify(parentByInput)')),
    {lastReference:'source-asset'}, 'Reloading a board setup must restore the named continuation-source claim');
  assert.equal(s.run('lastUploaded'), 'continuation-source.png');
  await s.run(`uploadRoleFile(0,${JSON.stringify(localFile('replacement.png'))})`);
  assert.deepEqual(s.parents(), ['source-asset'], 'Replacing the matching board slot must retain the reloaded continuation source parent');
  assert.equal(s.run('lastUploaded'), 'continuation-source.png');
}

// The recipe picker stays interactive while /api/upload is in flight; a swap in that window must not submit.
async function recipeSwapDuringUploadNeverSubmits() {
  const s = sandbox(sourceAttachment('a'.repeat(32) + '_retained.png'), {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
  s.run(`selectPreset('gentle-variation');`);
  s.element('#positive').value = 'Keep this subject while refining the lighting.';
  s.element('#reference').files = [localFile()];
  s.element('#reference').onchange();
  const fetch = s.context.fetch;
  s.context.fetch = async (url, options) => { const result = await fetch(url, options); if (url === '/api/upload') s.run(`selectPreset('qwen-1ref');`); return result; };
  await s.element('#generate').onclick();
  assert.equal(s.requests.some(r => r.url === '/api/jobs'), false, 'A recipe swapped during the source upload must not be submitted');
  assert.equal(s.run('selected.id'), 'qwen-1ref');
  assert.equal(s.run('submitting'), false, 'Generate is released after the refused submission');
  assert.equal(s.run('uploaded'), null, 'The refused upload is not left bound to the recipe it was not made for');
  s.context.fetch = fetch;
  s.run(`selectPreset('gentle-variation');`);
  s.element('#positive').value = 'Keep this subject while refining the lighting.';
  s.element('#reference').files = [localFile()];
  s.element('#reference').onchange();
  await s.element('#generate').onclick();
  assert.equal(s.requests.filter(r => r.url === '/api/jobs').length, 1, 'An undisturbed upload still submits exactly once');
  assert.equal(s.requests.find(r => r.url === '/api/jobs').data.controls.reference, 'own-upload.png', 'The upload made for this recipe is what gets submitted');
  // Controls edited while the upload is in flight do not change what was approved: the pressed intent is submitted.
  s.requests.length = 0;
  s.element('#reference').files = [localFile()];
  s.element('#reference').onchange();
  s.element('#batch').value = '1';
  s.context.fetch = async (url, options) => { const result = await fetch(url, options); if (url === '/api/upload') s.element('#batch').value = '4'; return result; };
  await s.element('#generate').onclick();
  const submitted = s.requests.find(r => r.url === '/api/jobs');
  assert.ok(submitted, 'An edit to a control during the upload does not block the approved submission');
  assert.equal(String(submitted.data.batch_count), '1', 'The batch count the operator pressed Generate with is submitted, not the mid-upload edit');
  s.context.fetch = fetch;
}

// #772: Ctrl+Enter is one click on the real Generate button, never a second path around its guards.
async function generateShortcutRoutesThroughTheButton() {
  const s = sandbox({}, {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
  s.run(`selectPreset('plain');`);
  let openDialog = null;
  s.context.document.querySelector = selector => selector === 'dialog[open]' ? openDialog : s.element(selector);
  s.context.document.body = {closest: () => null};
  const jobs = () => s.requests.filter(r => r.url === '/api/jobs').length;
  assert.equal(jobs(), 0, 'Loading Create never submits');
  const button = s.element('#generate'), create = s.element('#createView'), prompt = s.element('#positive'), outside = {closest: () => null};
  prompt.value = 'A lantern-lit workshop.'; prompt.closest = () => null;
  create.hidden = false; create.contains = node => node === prompt;
  button.closest = () => null; button.getClientRects = () => [{}]; button.disabled = false;
  let clicks = 0;
  button.click = () => {clicks++; button.onclick();};
  const press = (extra = {}) => {
    const e = {key: 'Enter', ctrlKey: true, target: prompt, prevented: false, preventDefault() {this.prevented = true;}, ...extra};
    return [s.context.generateShortcut(e), e.prevented];
  };
  assert.deepEqual(press(), ['clicked', true], 'Ctrl+Enter in the prompt clicks the enabled Generate button');
  assert.deepEqual(press(), ['blocked', true], 'A second press while the first run is submitting does not click again');
  assert.equal(clicks, 1);
  assert.match(s.element('#status').textContent, /already being submitted/);
  await flush(); await flush();
  assert.equal(jobs(), 1, 'Two quick presses submit exactly one run');
  assert.deepEqual(press({repeat: true}), ['repeat', true], 'A held key repeat is swallowed');
  assert.equal(clicks, 1, 'A key repeat never clicks');
  assert.deepEqual(press({ctrlKey: false}), ['ignored', false], 'Plain Enter keeps its normal meaning');
  assert.deepEqual(press({shiftKey: true}), ['ignored', false]);
  assert.deepEqual(press({altKey: true}), ['ignored', false], 'Ctrl+Alt+Enter is not the shortcut');
  assert.deepEqual(press({isComposing: true}), ['ignored', false], 'An IME composition keeps its Enter');
  assert.deepEqual(press({defaultPrevented: true}), ['ignored', false], 'A field that already handled Enter keeps it');
  openDialog = {};
  assert.deepEqual(press({target: s.context.document.body}), ['ignored', false], 'An open modal owns the keyboard even when focus fell to body');
  assert.deepEqual(press(), ['ignored', false]);
  openDialog = null;
  assert.equal(clicks, 1, 'None of those clicked');
  assert.deepEqual(press({ctrlKey: false, metaKey: true}), ['clicked', true], 'Cmd+Enter works on a Mac');
  assert.equal(clicks, 2);
  await flush(); await flush();
  assert.equal(jobs(), 2, 'Each deliberate press is one click and at most one run');
  button.disabled = true;
  s.element('#uxBlockers .ux-blocker p').textContent = 'Add a prompt to generate.';
  assert.deepEqual(press(), ['blocked', true]);
  assert.equal(s.element('#status').textContent, 'Add a prompt to generate.', 'A disabled button announces its existing reason');
  button.disabled = false; button.closest = selector => selector === '[hidden]' ? {} : null;
  assert.deepEqual(press(), ['blocked', true], 'A hidden button is never clicked');
  button.closest = () => null;
  assert.deepEqual(press({target: outside}), ['ignored', false], 'Outside Create the shortcut does nothing');
  prompt.closest = selector => selector === 'dialog' ? {} : null;
  assert.deepEqual(press(), ['ignored', false], 'Inside a dialog the shortcut does nothing');
  prompt.closest = () => null; create.hidden = true;
  assert.deepEqual(press(), ['ignored', false], 'On another view the shortcut does nothing');
  assert.equal(clicks, 2);
  assert.equal(jobs(), 2);
}

// #772: a pasted or multi-dropped picture fills empty slots through uploadRoleFile; text pastes stay the browser's.
async function pastedAndDroppedPicturesFillEmptySlots() {
  const s = sandbox({}, {});
  const fetch = s.context.fetch;
  s.context.fetch = async (url, options = {}) => url === '/api/upload'
    ? (s.requests.push({url, name: options.headers['X-Filename']}), {ok: true, json: async () => ({file: 'up-' + options.headers['X-Filename'], sha256: 'e'.repeat(64), width: 512, height: 768})})
    : fetch(url, options);
  let openDialog = null;
  s.context.document.querySelector = selector => selector === 'dialog[open]' ? openDialog : s.element(selector);
  const body = {closest: () => null}, prompt = s.element('#positive'), create = s.element('#createView');
  s.context.document.body = body; create.hidden = false; create.contains = node => node === prompt || node === body;
  prompt.closest = selector => selector.includes('textarea') ? prompt : null;
  const png = (name, size = 2048, type = 'image/png') => ({name, size, type});
  const paste = (files, {target = body, types = ['Files']} = {}) => {
    const e = {target, clipboardData: {files, types}, prevented: false, preventDefault() {this.prevented = true;}};
    return [s.context.pasteReference(e), e.prevented];
  };
  const slots = () => JSON.parse(s.run('JSON.stringify(referenceRecords.map(r=>r.file))'));
  const uploads = () => s.requests.filter(r => r.url === '/api/upload').map(r => r.name);
  s.run(`selectPreset('qwen-3ref');`);
  assert.deepEqual(paste([], {target: prompt, types: ['text/plain']}), ['ignored', false], 'A text paste is left alone');
  assert.deepEqual(paste([png('clip.png')], {target: prompt, types: ['text/plain', 'Files']}), ['ignored', false], 'Text on the clipboard wins in a text field');
  openDialog = {};
  assert.deepEqual(paste([png('a.png')]), ['ignored', false], 'A paste behind an open modal is left alone');
  openDialog = null;
  assert.deepEqual(uploads(), []);
  assert.deepEqual(paste([png('a.png')]), ['pasted', true]);
  await flush(); await flush();
  assert.deepEqual(slots(), ['up-a.png', null, null], 'The picture lands in the first empty slot');
  assert.deepEqual(paste([png('b.png')], {target: prompt, types: ['Files']}), ['pasted', true], 'An image-only paste into the prompt still attaches');
  assert.deepEqual(paste([png('c.png'), png('d.png')]), ['pasted', true]);
  assert.match(s.element('#status').textContent, /1 more picture was ignored/);
  await flush(); await flush();
  assert.deepEqual(slots(), ['up-a.png', 'up-b.png', 'up-c.png']);
  assert.deepEqual(uploads(), ['a.png', 'b.png', 'c.png'], 'Every pasted picture went through the upload path; the extra was not sent');
  assert.deepEqual(paste([png('e.png')]), ['full', true]);
  s.run(`referenceRecords[1].file=null;`);
  assert.deepEqual(paste([png('f.gif', 10, 'image/gif')]), ['refused', true], 'Only PNG, JPG or WebP is accepted');
  assert.deepEqual(paste([png('big.png', 21 * 1024 * 1024)]), ['refused', true], 'The 20 MiB limit applies before upload');
  assert.equal(uploads().length, 3);
  // A drop onto a card keeps its old meaning for the first picture and fills the other empty slots with the rest.
  s.run(`selectPreset('qwen-3ref');`);
  s.element('#referenceCards').ondrop({preventDefault() {}, target: {closest: () => ({dataset: {refDrop: '1'}})}, dataTransfer: {files: [png('x.png'), png('y.png'), png('z.png'), png('w.png')]}});
  assert.match(s.element('#status').textContent, /3 pictures added\. 1 more was ignored/);
  await flush(); await flush();
  assert.deepEqual(slots(), ['up-y.png', 'up-x.png', 'up-z.png']);
  // An unsupported or oversized file never takes a valid picture's slot (Codex review on #974).
  s.run(`selectPreset('qwen-3ref');referenceRecords[0].file='kept.png';referenceRecords[2].file='kept.png';`);
  s.element('#referenceCards').ondrop({preventDefault() {}, target: {closest: () => ({dataset: {refDrop: '0'}})}, dataTransfer: {files: [png('bad.gif', 10, 'image/gif'), png('huge.png', 21 * 1024 * 1024), png('good.png')]}});
  assert.match(s.element('#status').textContent, /1 picture added\. 2 other files were skipped/);
  await flush(); await flush();
  assert.deepEqual(slots(), ['up-good.png', null, 'kept.png'], 'The valid picture takes the dropped-on slot');
  assert.ok(!uploads().includes('bad.gif') && !uploads().includes('huge.png'));
  s.element('#referenceCards').ondrop({preventDefault() {}, target: {closest: () => ({dataset: {refDrop: '1'}})}, dataTransfer: {files: [png('bad.gif', 10, 'image/gif')]}});
  assert.match(s.element('#status').textContent, /Nothing was added/);
  // The slot picker is cleared after each attempt, so choosing the same file again fires a new change event.
  const input = {dataset: {refFile: '0'}, files: [png('again.png')], value: 'C:\\fakepath\\again.png'};
  s.element('#referenceCards').listeners.change({target: input});
  assert.notEqual(input.value, '', 'The picker keeps its File while the upload runs');
  await flush(); await flush();
  assert.equal(input.value, '', 'The slot picker is reset once the upload settles');
  assert.equal(slots()[0], 'up-again.png');
  // A slot-less reference recipe receives the picture in its own file input, as if chosen there.
  s.run(`selectPreset('gentle-variation');`);
  s.context.DataTransfer = class {constructor() {this.files = []; this.items = {add: file => this.files.push(file)};}};
  s.context.Event = class {constructor(type, options = {}) {this.type = type; this.bubbles = !!options.bubbles;}};
  let changes = 0;
  s.element('#reference').files = [];
  s.element('#reference').dispatchEvent = event => {changes++; assert.equal(event.type, 'change'); s.element('#reference').onchange(event);};
  assert.deepEqual(paste([png('source.png')]), ['pasted', true]);
  assert.equal(changes, 1);
  assert.equal(s.element('#reference').files[0].name, 'source.png');
  assert.deepEqual(paste([png('second.png')]), ['full', true], 'A filled slot-less input is not replaced');
  s.run(`selectPreset('plain');`);
  assert.deepEqual(paste([png('nothing.png')]), ['no-reference', true]);
  assert.match(s.element('#status').textContent, /takes no reference picture/);
  create.hidden = true;
  assert.deepEqual(paste([png('elsewhere.png')]), ['ignored', false], 'Pasting on another view is left alone');
}

// #772: a new seed and a replaced comparison pin say what happened instead of changing silently.
async function seedAndPinChangesAreAnnounced() {
  const s = sandbox({}, {});
  s.run(`selectPreset('plain');`);
  s.element('#randomSeed').onclick();
  assert.match(s.element('#status').textContent, /^Seed changed to \d+\. Nothing was generated\.$/);
  assert.equal(s.element('#status').textContent, 'Seed changed to ' + s.element('[data-key="seed"]').value + '. Nothing was generated.');
  const pin = job => ({closest: selector => selector === '.pin' ? {dataset: {job, index: '0'}} : null});
  for (const job of ['a', 'b']) await s.element('#gallery').onclick({target: pin(job)});
  assert.doesNotMatch(s.element('#status').textContent, /oldest pin/);
  await s.element('#gallery').onclick({target: pin('c')});
  assert.match(s.element('#status').textContent, /oldest pin was replaced/);
  assert.deepEqual(JSON.parse(s.run('JSON.stringify(pinned.map(p=>p.job))')), ['b', 'c']);
}

// Models & setup: the status filter next to #modelSearch narrows the installed
// weights (and the curated cards) to what needs action, combines with the text
// search, and restores the stored choice. Without it every row renders always,
// so the action-needed files stay buried among verified ones.
async function modelStatusFilter() {
  const {element, context, run} = sandbox({}, {});
  context.localStorage = (store => ({getItem: k => store.has(k) ? store.get(k) : null, setItem(k, v) {store.set(k, String(v));}, removeItem(k) {store.delete(k);}}))(new Map());
  assert.equal(run('typeof restoreModelStatus'), 'function', 'Models list has a status filter to restore; without it every weight renders with no way to surface what needs action');
  const assets = [
    {id:'a-verified', name:'Verified Model', family:'Test', bytes:8, file:'checkpoints/verified.safetensors', present:true, verified:true, installable:true, download:{status:'installed'}},
    {id:'a-unverified', name:'Unverified Model', family:'Test', bytes:8, file:'checkpoints/unverified.safetensors', present:true, verified:false, installable:true, download:{}},
    {id:'a-missing', name:'Missing Model', family:'Test', bytes:8, file:'checkpoints/missing.safetensors', present:false, verified:false, installable:true, download:{}},
    {id:'a-failed', name:'Failed Model', family:'Test', bytes:8, file:'checkpoints/failed.safetensors', present:false, verified:false, installable:true, download:{status:'failed', message:'boom'}},
    {id:'a-pin', name:'Pin Model', family:'Test', bytes:8, file:'adapters/pin.gguf', present:false, verified:false, installable:false, install_note:'Copy in by hand'},
  ];
  const inventory = [
    {file:'checkpoints/verified.safetensors', bytes:8},
    {file:'checkpoints/unverified.safetensors', bytes:8},
    {file:'loras/extra.safetensors', bytes:8},
  ];
  run(`library=${JSON.stringify({assets, inventory, storage:{}, folders:[], collections:[]})};`);
  run('restoreModelStatus()');
  assert.equal(element('#modelStatus').value, 'all', 'Status filter defaults to Everything');
  run('renderInventory()');
  assert.match(element('#inventory').innerHTML, /\/verified\.safetensors/);
  assert.match(element('#inventory').innerHTML, /unverified\.safetensors/);
  assert.match(element('#inventory').innerHTML, /extra\.safetensors/);
  assert.match(element('#modelCount').textContent, /3 of 3 shown/);

  element('#modelStatus').value = 'action';
  run('renderInventory()');
  assert.match(element('#inventory').innerHTML, /unverified\.safetensors/, 'Needs action keeps the present-but-unverified file buried among verified rows');
  assert.doesNotMatch(element('#inventory').innerHTML, /\/verified\.safetensors/, 'Needs action hides SHA-256 verified files');
  assert.doesNotMatch(element('#inventory').innerHTML, /extra\.safetensors/, 'Needs action hides installed files with no curated action');
  assert.match(element('#modelCount').textContent, /1 of 3 need action/);

  element('#modelSearch').value = 'checkpoints';
  run('renderInventory()');
  assert.match(element('#inventory').innerHTML, /unverified\.safetensors/);
  assert.doesNotMatch(element('#inventory').innerHTML, /\/verified\.safetensors/);
  element('#modelSearch').value = 'extra';
  run('renderInventory()');
  assert.match(element('#inventory').innerHTML, /No matching installed weights/, 'Text search narrows within the status filter instead of replacing it');
  element('#modelSearch').value = '';

  element('#modelStatus').value = 'installed';
  run('renderInventory()');
  assert.match(element('#inventory').innerHTML, /\/verified\.safetensors/);
  assert.match(element('#inventory').innerHTML, /extra\.safetensors/);
  assert.doesNotMatch(element('#inventory').innerHTML, /unverified\.safetensors/);
  assert.match(element('#modelCount').textContent, /2 of 3 installed/);

  const baseFetch = context.fetch;
  const fixture = {storage:{free_bytes:5000000000, total_bytes:200000000000, reserve_bytes:20000000000}, model_root:'C:/models', assets, folders:[], collections:[], inventory};
  context.fetch = async (url, options = {}) => url === '/api/library' ? {ok:true, json: async () => fixture} : baseFetch(url, options);
  element('#modelStatus').value = 'action';
  await run('refreshLibrary()');
  const cards = element('#modelCards').innerHTML;
  for (const name of ['Unverified Model', 'Missing Model', 'Failed Model', 'Pin Model']) assert.match(cards, new RegExp(name), 'Needs action keeps the card for ' + name);
  assert.doesNotMatch(cards, /Verified Model/, 'Needs action hides the verified card');
  assert.match(cards, /1 curated model is hidden by the/, 'A filtered card list says how many cards the filter hides');
  element('#modelStatus').value = 'installed';
  await run('refreshLibrary()');
  for (const name of ['Missing Model', 'Failed Model', 'Pin Model']) assert.doesNotMatch(element('#modelCards').innerHTML, new RegExp(name), 'Installed hides ' + name);
  assert.match(element('#modelCards').innerHTML, /are hidden by the/, 'Installed says the action cards are hidden, not absent');
  element('#modelStatus').value = 'all';
  await run('refreshLibrary()');
  assert.match(element('#modelCards').innerHTML, /Verified Model/, 'Everything restores the full card list');

  assert.equal(typeof element('#modelStatus').onchange, 'function', 'Changing the status filter persists the choice for the next visit');
  element('#modelStatus').value = 'installed';
  await element('#modelStatus').onchange();
  assert.equal(context.localStorage.getItem('studio.models.status'), 'installed', 'The choice is stored under studio.models.status');
  element('#modelStatus').value = 'all';
  run('restoreModelStatus()');
  assert.equal(element('#modelStatus').value, 'installed', 'The stored choice is restored on load');
  context.localStorage.setItem('studio.models.status', 'bogus');
  run('restoreModelStatus()');
  assert.equal(element('#modelStatus').value, 'all', 'An unknown stored choice falls back to Everything');
  { context.fetch = baseFetch; // Teardown scope: restores the shared fetch hook; closed below with the function.
}
}

(async () => {
  await generateShortcutRoutesThroughTheButton();
  await seedAndPinChangesAreAnnounced();
  await pastedAndDroppedPicturesFillEmptySlots();
  await recipeSwapDuringUploadNeverSubmits();
  await unstagedLocalFilesCannotBeSaved();
  await explicitLocalAbandonment();
  await problemsPanelPutAway();
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
  await boardContinuationSourceHasItsOwnLineageClaim();
  await boardSummaryFollowsTheRecipeOrder();
  await firstLastFramesAttributeSeparately();
  await savedSetupCarriesPerInputAttribution();
  await legacySetupWithoutAttributionIsUnchanged();
  await importedRecipeKeepsUnattributedParents();
  await pullingIntoASlotReplacesItsSource();
  await i2vDiagnosticEligibilityAndRetry();
  await unresolvedInputLineageCannotBeSaved();
  await avoidWordingIsVisibleWhenTheRecipeBindsIt();
  await modelStatusFilter();
  console.log('Gallery handoff contracts passed: lineage and role metadata survive save and submission, and a swapped reference drops the stale source.');
})().catch(error => {console.error(error); process.exitCode = 1;});
