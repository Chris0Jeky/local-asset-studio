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

presets[presets.length - 1].positive = ['1', 'text'];
presets[presets.length - 1].defaults = {};
presets[presets.length - 1].continuation_capability = {consumes_source: true, operation: 'image-to-video', prompt_role: 'motion', requires_mask: false, reference_count: 2, template_sha256: templateSha};

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
      addEventListener() {}, scrollIntoView() {}, close() {this.open=false;}, showModal() {this.open=true;},
    });
    return elements.get(selector);
  };
  const context = vm.createContext({
    document: {querySelector: element, querySelectorAll: () => [], addEventListener(name, handler) {if (name === 'click') clickHandler = handler;}},
    URL, Blob, StudioContinuation, StudioAssetRecovery,
    sessionStorage: {getItem(){return null;},setItem(){},removeItem(){}},
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
  for (const name of ['app.js', 'references.js', 'workspace.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static', name), 'utf8'), context);
  }
  const run = source => vm.runInContext(source, context);
  run(`catalog=${JSON.stringify({presets})}; online=schemaAvailable=true;
    jobs=[{id:'source-job',outputs:[{asset_id:'source-asset'}]}];
    refresh=async()=>{}; loadSetups=async()=>{};`);
  return {element, requests, context, run, click: target => clickHandler({target}), parents: () => JSON.parse(run('JSON.stringify(parentAssets)'))};
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


// The recipe picker stays interactive while /api/upload is in flight; a swap in that window must not submit.
async function recipeSwapDuringUploadNeverSubmits() {
  const s = sandbox(sourceAttachment('a'.repeat(32) + '_retained.png'), {file: 'own-upload.png', sha256: 'e'.repeat(64), width: 512, height: 768});
  s.run(`selectPreset('gentle-variation');`);
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

(async () => {
  await recipeSwapDuringUploadNeverSubmits();
  await unstagedLocalFilesCannotBeSaved();
  await explicitLocalAbandonment();
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
  await firstLastFramesAttributeSeparately();
  await savedSetupCarriesPerInputAttribution();
  await legacySetupWithoutAttributionIsUnchanged();
  await importedRecipeKeepsUnattributedParents();
  await pullingIntoASlotReplacesItsSource();
  await i2vDiagnosticEligibilityAndRetry();
  await unresolvedInputLineageCannotBeSaved();
  console.log('Gallery handoff contracts passed: lineage and role metadata survive save and submission, and a swapped reference drops the stale source.');
})().catch(error => {console.error(error); process.exitCode = 1;});
