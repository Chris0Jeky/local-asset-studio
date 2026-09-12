/* Pure policy checks: node tests/studio_ux.cjs. No browser or packages required. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const U = require('../app/static/studio-core.js');
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../presets/catalog.json'))).presets;
let count = 0;
function test(name, fn) { fn(); count++; console.log('PASS: ' + name); }
const image = {media_type:'image',filename:'source.png'};
const audio = {media_type:'audio',filename:'voice.wav'};
const draft = () => ({version:1,updatedAt:123,recipe:{preset:'qwen-1ref',controls:{positive:'A study',seed:42},batch:1,parent_assets:['source'],references:[]}});
const ready = overrides => U.readiness({preset:{id:'example'},online:true,schemaAvailable:true,...overrides});
test('invalid routes normalize to overview', () => {
  for (const route of [null,undefined,'#unknown','#../../models']) assert.equal(U.normalizeView(route),'home');
  for (const route of U.VIEWS) assert.equal(U.normalizeView('#'+route),route);
});
test('intent selection never mutates catalog order', () => {
  const before=JSON.stringify(catalog);U.recipesFor('edit',catalog);assert.equal(JSON.stringify(catalog),before);
});
test('each task has current catalog coverage', () => {
  for (const task of U.INTENTS) assert.ok(U.recipesFor(task.id,catalog).length,task.id);
});
test('image handoffs require actual reference bindings', () => {
  for (const task of ['edit','repair','animate','mesh']) assert.ok(U.recipesFor(task,catalog,true).every(p=>p.reference));
  assert.ok(!U.recipesFor('animate',catalog,true).some(p=>p.id==='wan22-t2v'));
});
test('unknown intents do not offer fabricated recipes', () => assert.deepEqual(U.recipesFor('invented',catalog),[]));
test('Qwen one-reference is preferred for edit', () => assert.equal(U.recipesFor('edit',catalog)[0].id,'qwen-1ref'));
test('review totals exclude trash and do not infer art approval', () => {
  const s=U.summarize([{review:'selected'},{review:'needs_work'},{},{review:'unreviewed',trashed_at:123}],[],[{status:'completed'}]);
  assert.deepEqual([s.assets,s.keepers,s.needsWork,s.unreviewed],[3,1,1,1]);
});
test('active, attention and planned work stay distinct', () => {
  const s=U.summarize([],['planned','awaiting_review','uncertain','running'].map(status=>({state:{status}})),[{status:'partial'},{status:'running'}]);
  for(const key of ['prepared','reviewPlans','attentionPlans','activePlans','attentionJobs','activeJobs']) assert.equal(s[key].length,1,key);
});
test('pending or unavailable health is not mislabeled offline',()=>{const r=ready({online:null});assert.equal(r.ready,false);assert.match(r.blockers.join(' '),/not yet confirmed/);assert.doesNotMatch(r.blockers.join(' '),/offline/);});
test('ready recipe has no invented blockers', () => assert.deepEqual(ready(),{ready:true,blockers:[]}));
for (const [name,overrides] of Object.entries({offline:{online:false},unknown_schema:{schemaAvailable:false},no_recipe:{preset:null},missing_files:{missing:['model']},missing_references:{referencesReady:false},backend_mismatch:{backend:'other'},switching:{switching:true},pending_transfer:{busy:true},blocked_runtime:{preset:{runtime_block:'Requires measured setup'}}})) {
  test(name+' prevents a ready presentation',()=>{const r=ready(overrides);assert.equal(r.ready,false);assert.ok(r.blockers.length);});
}
test('scene picker supports only typed PNG MP4 WAV sources', () => {
  assert.ok(U.sceneEligibility([image,audio]).ok);
  assert.ok(U.sceneEligibility([{media_type:'video',filename:'clip.MP4'}]).ok);
  for(const value of [[],[audio],[{...image,filename:'a.jpg'}],[{...image,filename:'a.mp4'}],[{...image,trashed_at:2}]]) assert.equal(U.sceneEligibility(value).ok,false);
});
test('scene source limits match existing editor contracts', () => {
  assert.ok(U.sceneEligibility(Array(16).fill(image).concat(Array(32).fill(audio))).ok);
  assert.equal(U.sceneEligibility(Array(17).fill(image)).ok,false);
  assert.equal(U.sceneEligibility([image,...Array(33).fill(audio)]).ok,false);
});
test('draft normalizes primitives and preserves lineage', () => {
  const normalized=U.normalizeDraft(draft());assert.equal(normalized.recipe.controls.seed,42);assert.deepEqual(normalized.recipe.parent_assets,['source']);assert.equal(normalized.templateHash,null);
});
test('draft rejects unsupported versions, batches and identities', () => {
  for(const mutate of [d=>d.version=2,d=>d.updatedAt='now',d=>d.recipe.preset='',d=>d.recipe.batch=5,d=>d.recipe.batch=1.5,d=>d.recipe.controls=null,d=>d.recipe.parent_assets=[42]]) {const d=draft();mutate(d);assert.equal(U.normalizeDraft(d),null);}
});
test('draft rejects prototype keys and non-primitive control payloads', () => {
  for(const input of ['{"__proto__":"bad"}','{"constructor":"bad"}','{"positive":{"html":"bad"}}','{"positive":[]}']) {const d=draft();d.recipe.controls=JSON.parse(input);assert.equal(U.normalizeDraft(d),null);}
});
test('draft rejects oversized values and nonfinite numbers', () => {
  for(const value of ['x'.repeat(20001),Infinity,NaN]) {const d=draft();d.recipe.controls.positive=value;assert.equal(U.normalizeDraft(d),null);}
  const d=draft();d.unused='x'.repeat(131073);assert.equal(U.normalizeDraft(d),null);
});
test('reference records cannot inject markup into dimensions', () => {
  for(const ref of [{width:'<img onerror=alert(1)>'},{sha256:'bad'},{height:-1},{bytes:1.5},{role:{}},{missing:'false'}]) {const d=draft();d.recipe.references=[ref];assert.equal(U.normalizeDraft(d),null);}
});
test('draft retains role constraints without claiming availability', () => {
  const d=draft();d.recipe.references=[{file:'ref.png',sha256:'a'.repeat(64),width:512,height:768,role:'identity',contribution:'face',avoid:'background',missing:true}];
  assert.deepEqual(U.normalizeDraft(d).recipe.references,d.recipe.references);
});
test('draft preserves file-reattachment requirements', () => {
  const d=draft();d.pendingInputs=['reference','reference','lastReference'];assert.deepEqual(U.normalizeDraft(d).pendingInputs,['reference','lastReference']);d.pendingInputs=['unknown'];assert.equal(U.normalizeDraft(d),null);
});
test('prompt transfer is text only, not executable bindings', () => {
  const out=U.promptTransfer({state:'review_required',profile:{id:'test'},fields:{positive:'A lantern',negative:'blur',seed:42},references:[{file:'a.png'}]});
  assert.equal(out.profile,'test');assert.equal(out.negative,'blur');assert.equal(out.references,undefined);assert.equal(out.seed,undefined);
});
test('blocked and oversized compilations cannot transfer', () => {
  for(const input of [null,{}, {state:'blocked',fields:{positive:'text'}},{fields:{positive:' '}},{fields:{positive:'x'.repeat(8001)}},{fields:{positive:'text',negative:'x'.repeat(8001)}}]) assert.equal(U.promptTransfer(input),null);
});
console.log(count+' Studio UX policy checks passed.');
