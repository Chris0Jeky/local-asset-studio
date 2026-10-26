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
const combineSource = between('  // sendBusy counts only', '\n  // Each engine');
const prepareSource = between('  async function prepareVary(button){', "\n  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-vary]')");
const U = require('../app/static/studio-core.js');

function context(extra) {
  const sandbox = {
    U, selected: {id: 'plain', name: 'Plain'}, online: true, schemaAvailable: true, workerAlive: true,
    missingByPreset: {}, continuationState: null, pendingInputs: [], uploaded: null, lastUploaded: null,
    secondPicture: null, sharedAdoptionError: null, varyUnapplied: null, sourceReadError: '',
    submitting: false, handoffBusy: false, pickerBusy: false, restoring: false, pairActionBusy: false, poseBusy: false,
    referencePending: 0, varyBusy: false, tileBusy: false, parallaxBusy: false, planBusy: false, polishBusy: new Set(), makeVaryBusy: new Set(), catalog: {presets: [{id: 'plain', name: 'Plain'}]},
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

test('Create new-seed preparation preserves the recorded Look options', async () => {
  const look={id:'look-night-shift',name:'Night Shift',revision:2,options:{quiet_wall:true}};
  let saved;
  const box=context({async api(){return {preset_id:'plain',controls:{positive:'scene',seed:4},look};},applySaved(value){saved=value;}});
  await box.prepareVary({dataset:{uxVary:'reseed',asset:'asset-1',preset:'plain',job:'job-1'}});
  assert.equal(JSON.stringify(saved.look),JSON.stringify(look));
  assert.equal(saved.controls.positive,'scene');
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

// #1497 Vary from Make: StudioWorkbench.vary sends the prepared round as one job and leaves Create alone.
const SC = require('../app/static/continuation-core.js');
// The catalog's own wai-vary route; continuation_capability is computed by the server from the graph, so it is stated here.
const authored = JSON.parse(fs.readFileSync(path.join(__dirname, '../presets/catalog.json'), 'utf8')).presets.find(p => p.id === 'wai-vary');
const catalogPresets = [
  {id: 'wai', name: 'WAI', seed: ['5', 'seed'], defaults: {}, continuation_capability: {operation: 'new-image', prompt_role: 'description'}},
  {id: 'plain', name: 'Plain', seed: ['5', 'seed'], continuation_capability: {operation: 'new-image'}},
  {...authored, continuation_capability: {consumes_source: true, operation: 'image-to-image', prompt_role: 'description', requires_mask: false, template_sha256: 'd'.repeat(64)}},
];
const makeVarySource = between('  function varyPlanFor(', '\n  // Rebuilt only when') + '\n' + between('  const makeVaryBusy=new Set();', '\n  Object.assign(globalThis.StudioWorkbench,{polish,polishPlan,vary});');
const SHA = 'a'.repeat(64), FILE = 'b'.repeat(32) + '_copy.png';
const sourceContext = {version: 1, asset_id: 'asset-1', sha256: SHA, preset_id: 'wai', prompt_role: 'description', prompt_origin: 'submitted-output', positive: 'a knight in a garden', negative: 'lowres', width: 832, height: 1216};
function makeVaryBox(extra) {
  const box = {
    StudioContinuation: SC, catalog: {presets: catalogPresets}, missingByPreset: {}, installedLoras: [],
    assetState: {assets: [{id: 'asset-1', media_type: 'image', trashed_at: null}]},
    jobs: [{id: 'job-1', preset_id: 'wai', status: 'completed', controls: {lora: 0.8, lora_name: 'style.safetensors', lora2: 0, lora2_name: 'none.safetensors', sampler: 'euler', scheduler: 'normal', cfg: 6, steps: 28}}],
    calls: [], sent: [], context: sourceContext, recipePreset: 'wai', combineBusy: () => false, sendBusy: () => false, tileBusy: false, parallaxBusy: false, syncReady() {},
    crypto: {getRandomValues: (array) => { array[0] = 41; return array; }},
    async readSource() { box.calls.push('context'); return box.context; },
    async api(url) { box.calls.push(url); return {preset_id: box.recipePreset, controls: {positive: 'a lantern', seed: 4}}; },
    async post(url, body) {
      box.calls.push(url);
      if (url === '/api/assets/reference') return {file: FILE, sha256: SHA, parent_asset: body.id, context: box.context};
      if (url === '/api/recipe-check') return {template_sha256: 'c'.repeat(64)};
      box.sent.push(body); if (box.postJobs) return box.postJobs(body); return {id: 'job-' + box.sent.length, status: 'queued'};
    },
    // Create must stay untouched: any of these firing fails the test.
    beginContinuation() { throw Error('touched Create'); }, applySaved() { throw Error('touched Create'); }, selectPreset() { throw Error('touched Create'); },
    window: {confirm() { throw Error('asked to overwrite Create'); }},
  };
  Object.assign(box, extra || {});
  vm.createContext(box);
  vm.runInContext(makeVarySource + '\nthis.vary=vary;this.varyPlanFor=varyPlanFor;', box);
  return box;
}

test('Make Vary posts one prepared img2img round with the carried stack and leaves Create alone (#1497)', async () => {
  const box = makeVaryBox();
  const job = await box.vary('asset-1', 'wai', 'job-1', 'strong');
  assert.equal(job.id, 'job-1');
  assert.deepEqual(box.calls, ['context', '/api/assets/reference', '/api/jobs']);
  assert.equal(box.sent.length, 1, 'one press, one job');
  const sent = box.sent[0], route = catalogPresets.find(p => p.id === 'wai-vary');
  assert.equal(sent.preset_id, 'wai-vary');
  assert.equal(sent.label, 'Make · Vary strong');
  assert.equal(sent.batch_count, 2, 'no timing yet: the round Vary prepares is 2');
  assert.equal(JSON.stringify(sent.parent_assets), '["asset-1"]');
  assert.equal(sent.continuation.reference_file, FILE);
  assert.equal(sent.continuation.source_asset_id, 'asset-1');
  assert.equal(sent.continuation.template_sha256, route.continuation_capability.template_sha256);
  assert.equal(sent.controls.reference, FILE);
  assert.equal(sent.controls.denoise, route.vary.strong.controls.denoise);
  assert.equal(sent.controls.lora_name, 'style.safetensors', 'the picture own adapters are kept');
  assert.equal(sent.controls.steps, 28);
  assert.equal(sent.controls.seed, 41);
  assert.match(sent.controls.positive, /a knight in a garden/);
});

test('Make Vary new seeds checks the recipe and sends one round (#1497)', async () => {
  const reseed = catalogPresets.find(p => p.id === 'plain');
  const box = makeVaryBox({jobs: [{id: 'job-1', preset_id: reseed.id, status: 'completed', controls: {}}], recipePreset: reseed.id});
  assert.equal(box.varyPlanFor(reseed.id, 'job-1', 'asset-1').kind, 'reseed');
  await assert.rejects(box.vary('asset-1', reseed.id, 'job-1', 'subtle'), /out of date/);
  assert.equal(box.sent.length, 0, 'a stale button sends nothing');
  await box.vary('asset-1', reseed.id, 'job-1', 'reseed');
  assert.deepEqual(box.calls, ['/api/jobs/job-1/recipe', '/api/recipe-check', '/api/jobs']);
  assert.equal(box.sent.length, 1);
  assert.equal(box.sent[0].preset_id, reseed.id);
  assert.equal(box.sent[0].expected_template_sha256, 'c'.repeat(64));
  assert.equal(box.sent[0].controls.seed, 41);
  assert.equal(box.sent[0].controls.positive, 'a lantern');
  assert.equal(box.sent[0].label, 'Make · Vary');
});

test('Make new-seed Vary forwards Look provenance in its one job request', async () => {
  const look={id:'look-night-shift',name:'Night Shift',revision:2,options:{quiet_wall:true}};
  const box=makeVaryBox({jobs:[{id:'job-1',preset_id:'plain',status:'completed',controls:{}}],
    async api(){return {preset_id:'plain',controls:{positive:'scene',seed:4},look};}});
  await box.vary('asset-1','plain','job-1','reseed');
  assert.equal(box.sent.length,1);
  assert.equal(JSON.stringify(box.sent[0].look),JSON.stringify(look));
  assert.equal(box.sent[0].controls.seed,41);
});

test('a second Make Vary press while the first is sending posts nothing more (#1497)', async () => {
  let release; const box = makeVaryBox({postJobs: () => release ? {id: 'job-y'} : new Promise(r => { release = r; })});
  const first = box.vary('asset-1', 'wai', 'job-1', 'subtle');
  await assert.rejects(box.vary('asset-1', 'wai', 'job-1', 'strong'), /already being sent/);
  for (let i = 0; !release && i < 50; i++) await new Promise(r => setImmediate(r));
  assert.ok(release, "the first press reached /api/jobs");
  release({id: 'job-x'}); await first;
  assert.equal(box.sent.length, 1);
  await box.vary('asset-1', 'wai', 'job-1', 'subtle');
  assert.equal(box.sent.length, 2, 'the latch clears once the first post settles');
});

test('a failed Make Vary post is reported, not sent again (#1497)', async () => {
  const box = makeVaryBox({postJobs: () => { throw Error('connection reset'); }});
  await assert.rejects(box.vary('asset-1', 'wai', 'job-1', 'subtle'), /connection reset/);
  assert.equal(box.sent.length, 1, 'no retry of an uncertain submission');
});

test('a Make Vary post with no HTTP answer is flagged uncertain; an HTTP refusal is not (Codex P1 on #1500)', async () => {
  const lost = makeVaryBox({postJobs: () => { throw TypeError('Failed to fetch'); }});
  await assert.rejects(lost.vary('asset-1', 'wai', 'job-1', 'subtle'), error => error.uncertain === true);
  const refused = makeVaryBox({postJobs: () => { const e = Error('Unsupported sampler'); e.status = 400; throw e; }});
  await assert.rejects(refused.vary('asset-1', 'wai', 'job-1', 'subtle'), error => !error.uncertain);
});

test('Make Vary refuses with its reason before copying anything (#1497)', async () => {
  const binned = makeVaryBox({assetState: {assets: [{id: 'asset-1', media_type: 'image', trashed_at: 1}]}});
  await assert.rejects(binned.vary('asset-1', 'wai', 'job-1', 'subtle'), /in the bin/);
  assert.deepEqual(binned.calls, []);
  const wordless = makeVaryBox({context: {...sourceContext, prompt_origin: 'unknown', positive: ''}});
  await assert.rejects(wordless.vary('asset-1', 'wai', 'job-1', 'subtle'), /No description was kept/);
  assert.deepEqual(wordless.calls, ['context'], 'no copy and no job');
});

const kreaPresets = JSON.parse(fs.readFileSync(path.join(__dirname, '../presets/catalog.json'), 'utf8')).presets;
const kreaRoute = {...kreaPresets.find(p => p.id === 'krea-refine'), continuation_capability: {...catalogPresets[2].continuation_capability}};
const kreaSource = {...kreaPresets.find(p => p.id === 'krea-anime-atelier'), continuation_capability: {operation: 'new-image', prompt_role: 'description'}};
const kreaRecorded = {lora: 0.7, lora_name: 'recorded-style.safetensors', lora2: 0, lora2_name: 'recorded-off.safetensors', lora3: 0, lora3_name: 'recorded-third.safetensors', lora4: 0.4, lora4_name: 'recorded-fourth.safetensors', sampler: 'euler_ancestral', scheduler: 'beta', cfg: 1.5};
const kreaJob = {id: 'job-1', preset_id: kreaSource.id, status: 'completed', controls: {...kreaRecorded, steps: 15, positive: 'a witch in a garden'}};
const kreaContext = {...sourceContext, preset_id: kreaSource.id, positive: kreaJob.controls.positive};
test('Make Krea Vary submits the four-slot recorded stack with the historical four/six step strengths', async () => {
  for (const [strength, denoise, steps] of [['subtle', 0.45, 4], ['strong', 0.65, 6]]) {
    const box = makeVaryBox({catalog: {presets: [kreaSource, kreaRoute]}, jobs: [kreaJob], context: kreaContext});
    await box.vary('asset-1', kreaSource.id, 'job-1', strength);
    assert.equal(box.sent.length, 1);
    const sent = box.sent[0];
    for (const [key, value] of Object.entries(kreaRecorded)) assert.equal(sent.controls[key], value, key);
    assert.equal(sent.controls.denoise, denoise); assert.equal(sent.controls.steps, steps);
    assert.equal(sent.preset_id, 'krea-refine'); assert.equal(sent.controls.positive, kreaJob.controls.positive);
    assert.deepEqual(box.calls, ['context', '/api/assets/reference', '/api/jobs']);
  }
});
test('Create Krea Vary prepares the same four-slot stack and never submits a job', async () => {
  for (const [strength, steps] of [['subtle', 4], ['strong', 6]]) {
    const controls = Object.fromEntries([...Object.keys(kreaRecorded), 'denoise', 'steps', 'seed'].map(key => [key, {value: ''}]));
    const plan = SC.varyPlan({preset_id: kreaSource.id, job_id: 'job-1', media_type: 'image'}, [kreaSource, kreaRoute], [kreaJob], {}, []);
    const box = context({
      StudioContinuation: SC, varyPlanFor: () => plan, getControl: key => controls[key],
      async post(url) { box.calls.push(url); return {file: FILE, sha256: SHA, parent_asset: 'asset-1', context: kreaContext}; },
      beginContinuation() { box.selected = kreaRoute; box.continuationState = {preset_id: kreaRoute.id}; },
    });
    await box.prepareVary({dataset: {uxVary: strength, asset: 'asset-1', preset: kreaSource.id, job: 'job-1'}});
    assert.equal(box.notices.some(notice => notice.error), false, JSON.stringify(box.notices));
    for (const [key, value] of Object.entries(kreaRecorded)) assert.equal(controls[key].value, String(value), key);
    assert.equal(controls.steps.value, steps); assert.equal(controls.denoise.value, strength === 'subtle' ? 0.45 : 0.65);
    assert.deepEqual(box.calls, ['/api/assets/reference']);
  }
});
test('each excluded Krea source uses its checked recorded recipe for a new-seed Make round', async () => {
  for (const id of ['krea-portrait', 'krea-portrait-gguf', 'krea-environment', 'krea-anime-atelier-gguf', 'krea-style-lab']) {
    const source = {...kreaPresets.find(p => p.id === id), continuation_capability: {operation: 'new-image', prompt_role: 'description'}};
    const box = makeVaryBox({catalog: {presets: [source, kreaRoute]}, jobs: [{...kreaJob, preset_id: id}]});
    box.api = async url => { box.calls.push(url); return {preset_id: id, controls: {...kreaRecorded, steps: 15, positive: 'recorded words'}}; };
    await box.vary('asset-1', id, 'job-1', 'reseed');
    assert.deepEqual(box.calls, ['/api/jobs/job-1/recipe', '/api/recipe-check', '/api/jobs']);
    assert.equal(box.sent.length, 1); assert.equal(box.sent[0].preset_id, id);
    assert.equal(box.sent[0].expected_template_sha256, 'c'.repeat(64));
    assert.equal(box.sent[0].controls.steps, 15); assert.equal(box.sent[0].controls.lora_name, kreaRecorded.lora_name);
  }
});

// make.js side: one press calls StudioWorkbench.vary once, adds the run and polls it; a failure only says so.
const makeSource = fs.readFileSync(path.join(__dirname, '../app/static/make.js'), 'utf8');
test('Make keeps disabled Vary visible with its linked reason (#1510)',()=>{
  const markup='<button type="button" disabled aria-describedby="vary-why">Vary</button><small id="vary-why">Needs a source picture.</small>';
  const box={state:{varying:new Set(),varyHeld:new Set(),polish:{},polishing:new Set()},escape:String,POLISH:{},
    window:{StudioWorkbench:{varyMarkup:()=>markup}},document:{createElement:()=>({innerHTML:'',querySelector:()=>({disabled:true}),querySelectorAll:()=>[]})},
    marks:()=>'',characterMarkup:()=>'',polishKinds:()=>[],merged:()=>false};
  const start=makeSource.indexOf('  function actions('),end=makeSource.indexOf('\n  // My character',start);
  const actions=vm.runInNewContext(makeSource.slice(start,end)+';actions',box),html=actions({id:'job'},{asset_id:'asset'});
  assert.ok(html.includes(markup),'disabled Vary and its aria-describedby hint stay on the card');
});

for(const [words,reason] of [['',/No description was kept/],['a knight [place]',/wording filled in/],['a knight',null]])
test('Vary render checks wording '+JSON.stringify(words)+' without reading the source (#1510)',()=>{
    const box=makeVaryBox();box.jobs[0].controls.positive=words;
    box.catalog={presets:catalogPresets.map(p=>p.id==='wai-vary'?{...p,positive:['1','text'],continuation_placeholder:'[place]'}:p)};
    vm.runInContext(between('  function varyMarkup(','  function varyPlanFor(')+'\nthis.markup=plan=>varyMarkup(plan,"","vary-why");',Object.assign(box,{escape:String}));
    const plan=box.varyPlanFor('wai','job-1','asset-1','image',undefined,true),html=box.markup(plan);
    // Create prepares the form and lets you describe the picture, so only Make (one press) pre-checks wording.
    assert.equal(box.varyPlanFor('wai','job-1','asset-1').kind,'img2img','Create Vary is not pre-checked');
    if(reason){assert.equal(plan.kind,'none');assert.match(plan.reason,reason);assert.match(html,/disabled aria-describedby="vary-why"/);assert.ok(html.includes(plan.reason));}
    else{assert.equal(plan.kind,'img2img');assert.doesNotMatch(html,/disabled/);}
    assert.deepEqual(box.calls,[],'render never reads context or posts');
});

test('Vary locally refuses an oversized source or a route needing another picture (#1510)',()=>{
  for(const oversized of [true,false]){
    const box=makeVaryBox();if(oversized)box.assetState.assets[0].bytes=20*1024*1024+1;
    else box.catalog={presets:catalogPresets.map(p=>p.id==='wai-vary'?{...p,continuation_capability:{...p.continuation_capability,source_input:'last_reference'}}:p)};
    const plan=box.varyPlanFor('wai','job-1','asset-1','image',undefined,true);assert.equal(plan.kind,'none');assert.match(plan.reason,oversized?/20 MiB/:/more than this picture/);assert.deepEqual(box.calls,[]);
  }
});

test('an authored Vary placeholder is refused even without locally known source wording (#1510)',()=>{
  const box=makeVaryBox();box.catalog={presets:catalogPresets.map(p=>p.id==='wai-vary'?{...p,continuation_prompt:'Redraw in [place].',continuation_placeholder:'[place]'}:p)};
  const plan=box.varyPlanFor('wai','job-1','asset-1','image',undefined,true);assert.equal(plan.kind,'none');assert.match(plan.reason,/wording filled in/);assert.deepEqual(box.calls,[]);
});

const varyPictureStart = makeSource.indexOf('  async function varyPicture(button){');
const varyPictureSource = makeSource.slice(varyPictureStart, makeSource.indexOf('\n  // shortcut: Comfy outputs have no auxiliary role;', varyPictureStart));
function makeCard(vary) {
  const box = {VARY_HELD: 'held', state: {varying: new Set(), varyHeld: new Set(), runs: [{job: {id: 'run-1', outputs: [{asset_id: 'asset-1'}]}, look: 'Pearly', lookId: 'look-p', goal: 'character'}]}, said: [], polled: [],
    renderRuns() {}, remember() {}, poll(id) { box.polled.push(id); }, say(text) { box.said.push(text); }, window: {StudioWorkbench: {vary}}};
  vm.createContext(box); vm.runInContext(varyPictureSource + '\nthis.varyPicture=varyPicture;', box); return box;
}
test('Make card Vary is wired to one StudioWorkbench.vary call per press (#1497)', async () => {
  assert.notEqual(varyPictureStart, -1, 'make.js has a Make-side Vary');
  assert.doesNotMatch(makeSource, /Prepare variations in the full editor/, 'the card no longer sends the owner to the full editor');
  assert.match(makeSource, /closest\('\[data-make-vary\]'\);if\(varying&&!varying\.disabled\)\{void varyPicture\(varying\)/);
  let calls = 0, release; const box = makeCard((...args) => { calls++; assert.deepEqual(args, ['asset-1', 'wai', 'job-1', 'subtle', undefined]); return new Promise(r => { release = r; }); });
  const button = {dataset: {asset: 'asset-1', preset: 'wai', job: 'job-1', makeVary: 'subtle'}};
  const first = box.varyPicture(button); await box.varyPicture(button);
  assert.equal(calls, 1, 'a double press sends once');
  assert.ok(box.state.varying.has('asset-1'), 'busy while sending');
  release({id: 'vary-1', status: 'queued'}); await first;
  assert.equal(box.state.varying.size, 0);
  assert.equal(box.state.runs[0].job.id, 'vary-1'); assert.equal(box.state.runs[0].look, 'Vary subtle · Pearly');
  assert.deepEqual(box.polled, ['vary-1']);
  const failing = makeCard(async () => { throw Error('Vary uses X. Missing here'); });
  await failing.varyPicture(button);
  assert.equal(failing.state.varying.size, 0); assert.equal(failing.polled.length, 0); assert.match(failing.said.at(-1), /Missing here/);
  assert.equal(failing.state.varyHeld.size, 0, 'a known refusal leaves Vary pressable');
  let lostCalls = 0; const lost = makeCard(async () => { lostCalls++; throw Object.assign(TypeError('Failed to fetch'), {uncertain: true}); });
  await lost.varyPicture(button); await lost.varyPicture(button);
  assert.equal(lostCalls, 1, 'an uncertain Vary is never sent again from this page');
  assert.ok(lost.state.varyHeld.has('asset-1')); assert.equal(lost.said.at(-1), 'held');
});
