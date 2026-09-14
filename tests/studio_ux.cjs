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
test('the 20-second Klein edit is preferred for edit, the 11-minute Qwen edit second', () => assert.deepEqual(U.recipesFor('edit',catalog).slice(0,2).map(p=>p.id),['flux-edit','qwen-1ref']));
test('bracketed fills left in the wording block readiness on every route and name the prompt', () => {
  const base={preset:{id:'x'},online:true,schemaAvailable:true};
  assert.deepEqual(U.readinessItems(base),[]);
  const items=U.readinessItems({...base,unfilled:['[who]','[the pose]']});
  assert.deepEqual(items.map(i=>[i.code,i.action]),[['wording','fills']]);assert.match(items[0].message,/replace “\[who\]” and “\[the pose\]” in the prompt/);
  // A recipe that transforms a picture blocks on the missing picture you keep, named by the recipe's own label, before anything else.
  const source=U.readinessItems({...base,preset:{id:'combine-klein',last_reference_label:'Picture to keep (image 1)'},sourceMissing:true,unfilled:['[who]']});
  assert.deepEqual(source.map(i=>[i.code,i.action]),[['source','source'],['wording','fills']]);assert.equal(source[0].message,'Add the picture you keep to Picture to keep (image 1).');
});
test('combine offers only declared combine boards and restyle never offers them', () => {
  const combine=U.recipesFor('combine',catalog);assert.ok(combine.length&&combine.every(p=>p.continuation_operation==='combine'&&p.reference_board&&p.last_reference));
  assert.ok(!U.recipesFor('restyle',catalog).some(p=>p.continuation_operation==='combine'));
});
test('review totals exclude trash and do not infer art approval', () => {
  const s=U.summarize([{review:'selected'},{review:'needs_work'},{},{review:'unreviewed',trashed_at:123}],[],[{status:'completed'}]);
  assert.deepEqual([s.assets,s.keepers,s.needsWork,s.unreviewed],[3,1,1,1]);
});
test('active, attention and planned work stay distinct', () => {
  const s=U.summarize([],['planned','awaiting_review','uncertain','running'].map(status=>({state:{status}})),[{status:'partial'},{status:'running'}]);
  for(const key of ['prepared','reviewPlans','attentionPlans','activePlans','attentionJobs','activeJobs']) assert.equal(s[key].length,1,key);
});
test('submitting jobs remain active on the overview', () => assert.equal(U.summarize([],[],[{status:'submitting'}]).activeJobs.length,1));
test('memory allocation failures explain the cause and next action', () => {
  const failure=U.failureDetails({status:'failed',message:'Generation failed: ComfyUI reported an execution error: KSampler: bad allocation'});
  assert.equal(failure.kind,'memory_allocation');
  assert.match(failure.summary,/memory|GPU|VRAM/i);
  assert.match(failure.action,/resolution|batch|LoRA/i);
  const host=U.failureDetails({status:'failed',message:'Generation failed: ComfyUI reported an execution error: VAEDecode: DefaultCPUAllocator: not enough memory'});
  assert.equal(host.kind,'memory_allocation');
});
test('structured execution failures retain engine context', () => {
  const failure=U.failureDetails({status:'failed',failure:{kind:'memory_allocation',title:'Memory allocation failed',summary:'Allocation summary',action:'Allocation action',node_type:'KSampler',exception_type:'RuntimeError',detail:'bad allocation'}});
  assert.equal(failure.title,'Memory allocation failed');
  assert.equal(failure.node_type,'KSampler');
  assert.equal(failure.exception_type,'RuntimeError');
  assert.equal(failure.detail,'bad allocation');
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
test('draft carries per-input lineage attribution and rejects unbacked claims', () => {
  const d=draft();d.recipe.parent_by_input={reference:'source'};
  assert.deepEqual(U.normalizeDraft(d).recipe.parent_by_input,{reference:'source'});
  assert.equal(U.normalizeDraft(draft()).recipe.parent_by_input,undefined,'A draft without the field stays without it, so the reload fallback still runs');
  const empty=draft();empty.recipe.parent_by_input={};
  assert.equal(U.normalizeDraft(empty).recipe.parent_by_input,undefined,'An empty mapping is not frozen into the draft');
  for(const mapping of [{reference:'not-a-declared-parent'},{unknownInput:'source'},{reference:42},['source'],'source']) {
    const bad=draft();bad.recipe.parent_by_input=mapping;assert.equal(U.normalizeDraft(bad),null);
  }
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
test('transfer names matching recipes without selecting one', () => {
  const out=U.promptTransfer({state:'review_required',profile:{id:'p',recipes:['qwen-1ref','qwen-2ref']},fields:{positive:'A lantern'}});
  assert.deepEqual(out.recipes,['qwen-1ref','qwen-2ref']);
  assert.deepEqual(U.promptTransfer({state:'review_required',profile:{id:'p'},fields:{positive:'A lantern'}}).recipes,[]);
  const replayed=U.promptTransfer({fields:out,profile:{id:out.profile},recipes:out.recipes});
  assert.deepEqual(replayed.recipes,out.recipes,'A stored handoff still names its recipes when Create replays it');
});
test('recipe names are bounded and catalog-shaped', () => {
  const bad=['Qwen 1Ref','../etc','x'.repeat(61),42,null,'ok-one','ok-one','a','b','c','d','e','f','g','h','i'];
  const out=U.promptTransfer({state:'review_required',profile:{id:'p',recipes:bad},fields:{positive:'A lantern'}});
  assert.deepEqual(out.recipes,['ok-one','a','b','c','d','e','f','g']);
  assert.deepEqual(U.promptTransfer({state:'review_required',profile:{id:'p',recipes:'qwen-1ref'},fields:{positive:'A lantern'}}).recipes,[]);
});
test('an unbuilt prompt says so instead of going quiet', () => {
  const [only]=U.promptBlockers(null);
  assert.equal(only.code,'NOT_COMPILED');assert.equal(only.blocking,true);assert.match(only.action,/Build the prompt/);
  assert.deepEqual(U.promptBlockers({state:'review_required',fields:{positive:'A lantern'},errors:[],diagnostics:[]}),[]);
});
test('every compiler error becomes a sentence, an action and a kept code', () => {
  const codes=['REFERENCE_COUNT','REFERENCE_KIND','NEGATIVE_REWRITE_REQUIRED','TAGS_REQUIRED','PROMPT_TOO_LONG','STRUCTURAL_CONTROL_REQUIRED','VERBATIM_UNBOUND','NEGATIVE_UNBOUND','TAGS_UNBOUND','SPEECH_TEXT_REQUIRED','VOICE_LANGUAGE_UNSUPPORTED','LYRICS_CONFLICT','METER_UNSUPPORTED','MOTION_UNSPECIFIED','TAG_COVERAGE_REVIEW','NO_TEXT_CONDITIONING','PARAMETER_HANDOFF','ACCEPTANCE_REQUIRED'];
  for(const code of codes) {
    const [item]=U.promptBlockers({state:'blocked',profile:{name:'Test profile',min_refs:0,max_refs:0},intent:{references:[],avoid:[]},fields:{},errors:[{code,message:'raw compiler text'}],diagnostics:[]});
    assert.equal(item.code,code);assert.equal(item.detail,'raw compiler text',code);
    assert.ok(item.message.length>20&&/[.!]$/.test(item.message),code+' needs a sentence');
    assert.ok(item.action.length>10&&/[.!]$/.test(item.action),code+' needs an action');
    assert.notEqual(item.message,item.action,code);
  }
});
test('an unknown future code still explains itself rather than showing bare text', () => {
  const [item]=U.promptBlockers({state:'blocked',fields:{},errors:[{code:'INVENTED_LATER',message:'raw compiler text'}],diagnostics:[]});
  assert.equal(item.message,'raw compiler text');assert.match(item.action,/compiler detail/);assert.equal(item.blocking,true);
});
test('reference-count wording follows the actual profile and attachment count', () => {
  const blocked=count=>U.promptBlockers({state:'blocked',profile:{name:'SDXL',min_refs:0,max_refs:0},intent:{references:Array(count).fill({}),avoid:[]},fields:{},errors:[{code:'REFERENCE_COUNT',message:'raw'}],diagnostics:[]})[0];
  assert.match(blocked(1).message,/reads no reference images, and 1 reference is attached/);
  assert.match(blocked(2).message,/2 references are attached/);
  assert.equal(blocked(1).fix,'switch-profile');
  const short=U.promptBlockers({state:'blocked',profile:{name:'Qwen',min_refs:1,max_refs:3},intent:{references:[],avoid:[]},fields:{},errors:[{code:'REFERENCE_COUNT',message:'raw'}],diagnostics:[]})[0];
  assert.match(short.message,/needs at least 1 reference image/);assert.equal(short.fix,'','Attaching a file is the fix, not a profile swap');
});
test('avoid terms are quoted back and offered a place to go', () => {
  const [item]=U.promptBlockers({state:'blocked',profile:{name:'FLUX',min_refs:0,max_refs:0},intent:{references:[],avoid:['crowd','watermark']},fields:{},errors:[{code:'NEGATIVE_REWRITE_REQUIRED',message:'raw'}],diagnostics:[]});
  assert.match(item.message,/\(crowd, watermark\)/);assert.equal(item.fix,'avoid-to-note');
});
test('notes are separated from blockers', () => {
  const list=U.promptBlockers({state:'blocked',profile:{name:'Animagine',min_refs:0,max_refs:0},intent:{references:[],avoid:[]},fields:{},errors:[{code:'TAGS_REQUIRED',message:'raw'}],diagnostics:[{code:'TAG_COVERAGE_REVIEW',message:'raw note'}]});
  assert.deepEqual(list.map(x=>x.blocking),[true,false]);
});
test('an unusable transfer says which limit it hit', () => {
  const long=U.promptBlockers({state:'review_required',profile:{name:'SDXL'},fields:{positive:'x'.repeat(8001)},errors:[],diagnostics:[]});
  assert.deepEqual(long.map(x=>x.code),['TRANSFER_TOO_LONG']);
  const none=U.promptBlockers({state:'review_required',profile:{name:'TRELLIS'},fields:{image_reference_id:'ref-a'},errors:[],diagnostics:[]});
  assert.deepEqual(none.map(x=>x.code),['NO_PROMPT_TEXT']);
  assert.ok(none[0].blocking&&long[0].blocking);
});
console.log(count+' Studio UX policy checks passed.');
