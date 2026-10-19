/* Pure policy checks: node tests/studio_ux.cjs. No browser or packages required. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const U = require('../app/static/studio-core.js');
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../presets/catalog.json'))).presets;
const vm = require('node:vm');
let count = 0;
function test(name, fn) { fn(); count++; console.log('PASS: ' + name); }
test('picture goals share the visible subgroup name inside the one radiogroup',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),box={};
  const GOALS=vm.runInNewContext(make.match(/const GOALS=(\[[\s\S]*?\n  \]);/)[1]);
  const render=make.slice(make.indexOf('  function renderGoals(){'),make.indexOf('  // Once a look is chosen'));
  vm.runInNewContext(render+';renderGoals();',{q:()=>box,GOALS,state:{goal:'restyle'},escape:s=>s});
  assert.match(box.innerHTML,/<div[^>]*role="group"[^>]*aria-labelledby="makePictureGoals"[^>]*><span[^>]*id="makePictureGoals"[^>]*>From a picture you have<\/span>/);
  const pictureGroup=box.innerHTML.slice(box.innerHTML.indexOf('role="group"'));
  for(const goal of GOALS.filter(g=>g.intent))assert.ok(pictureGroup.includes('data-make-goal="'+goal.id+'"'));
  assert.equal((box.innerHTML.match(/role="radio"/g)||[]).length,GOALS.length);
  assert.equal((box.innerHTML.match(/tabindex="0"/g)||[]).length,1);
});
test('finder goal names, hints and look membership match Make',()=>{
  const goals=(file,name)=>vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static',file),'utf8').match(new RegExp('const '+name+'=(\\[[\\s\\S]*?\\n  \\]);'))[1]);
  assert.equal(JSON.stringify(goals('studio-shell.js','makeGoals')),JSON.stringify(goals('make.js','GOALS')));
});
test('finder indexes preset model and family metadata and offers Tune without generation',()=>{
  const shell=fs.readFileSync(path.join(__dirname,'../app/static/studio-shell.js'),'utf8');
  const commands=shell.slice(shell.indexOf('  function commands(){'),shell.indexOf('  async function loadLooks()'));
  const input={value:'wai'},results={};
  const context={$:s=>s==='#studioCommandSearch'?input:results,makeGoals:[{id:'character',looks:['look-test']}],synonyms:{},keywords:{},looks:[{id:'look-test',name:'Fantasy portrait',body:{preset_id:'test'}}],presets:[{id:'test',name:'Portrait recipe',family:'WAI',model:{file:'base-model.safetensors'}},{id:'flux',name:'FLUX',family:'FLUX'}],links:[['models','Models & setup','Install models','/#models']],escape:s=>s};
  vm.runInNewContext(commands+';commands();',context);
  assert.match(results.innerHTML,/data-make-look="look-test"/);
  for(const query of ['base-model','portrait recipe']){input.value=query;vm.runInNewContext('commands()',context);assert.match(results.innerHTML,/data-make-look="look-test"/);}
  for(const query of ['lora','adapter','tune']){input.value=query;vm.runInNewContext('commands()',context);assert.match(results.innerHTML,/href="\/#make"/);assert.match(results.innerHTML,/Open Model, LoRAs and settings under the words in Make/);}
  input.value='flux';vm.runInNewContext('commands()',context);assert.match(results.innerHTML,/href="\/#models"/);
});
test('finder reaches installed adapters and model files that no look uses (#23), and no longer offers Overview (#18)',()=>{
  const shell=fs.readFileSync(path.join(__dirname,'../app/static/studio-shell.js'),'utf8');
  const commands=shell.slice(shell.indexOf('  function commands(){'),shell.indexOf('  async function loadLooks()'));
  const input={value:''},results={};
  const context={$:s=>s==='#studioCommandSearch'?input:results,makeGoals:[{id:'character',looks:['look-test']}],synonyms:{},keywords:{},looks:[{id:'look-test',name:'Fantasy portrait',body:{preset_id:'test'}}],
    presets:[{id:'test',name:'Portrait recipe',family:'WAI',model:{file:'wai-base.safetensors'},choices:{lora_name:['xilmo-style.safetensors','pearly-line.safetensors'],sampler:['euler']}},{id:'flux',name:'FLUX',family:'FLUX',model:{file:'flux-checkpoint.safetensors'},choices:{lora2_name:['pearly-line.safetensors']}}],
    links:[['models','Models & setup','Install models','/#models'],['home','Overview','Attention, recent work and next steps','/#home','01','Workspace',true]],escape:s=>s};
  vm.runInNewContext(commands+';commands();',context);
  // The empty finder keeps its shape: no adapter rows until something is typed.
  assert.doesNotMatch(results.innerHTML,/Use xilmo/);
  input.value='xilmo';vm.runInNewContext('commands()',context);
  assert.match(results.innerHTML,/<b>Use xilmo-style\.safetensors in Make<\/b>/);assert.match(results.innerHTML,/LoRA - add it under Model, LoRAs and settings in Make/);
  input.value='pearly';vm.runInNewContext('commands()',context);
  assert.match(results.innerHTML,/<b>Use pearly-line\.safetensors in Make<\/b>/);
  // A checkpoint file with no look reaches Models & setup through that row's own file index, once.
  input.value='flux-checkpoint';vm.runInNewContext('commands()',context);
  assert.match(results.innerHTML,/<b>Models & setup<\/b>/);assert.equal((results.innerHTML.match(/href="\/#models"/g)||[]).length,1);
  // A file a look already uses is found through that look.
  input.value='wai-base';vm.runInNewContext('commands()',context);
  assert.match(results.innerHTML,/data-make-look="look-test"/);
  // Samplers are not adapters.
  input.value='euler';vm.runInNewContext('commands()',context);assert.doesNotMatch(results.innerHTML,/Use euler/);
  input.value='overview';vm.runInNewContext('commands()',context);assert.doesNotMatch(results.innerHTML,/href="\/#home"|Overview/);
});
test('Make orders each goal by lab evidence, files painting styles under Painted illustration and keeps Krea last',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),grab=re=>JSON.parse(JSON.stringify(vm.runInNewContext('('+make.match(re)[1]+')')));
  const goals=grab(/const GOALS=(\[[\s\S]*?\n  \]);/),looks=id=>goals.find(g=>g.id===id).looks,ids=new Set(JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/looks.json'))).looks.map(l=>l.id));
  // Lab rounds 1-2 (docs/looks/LOOK-LAB-2026-10-16.md): measured high scorers first, rejects after them, unmeasured slow Krea last.
  assert.deepEqual(looks('character'),['look-anima-pearly-petiflow','look-oneobsession-anima-v20-showcase','look-anifox-ringeko','look-pearly-anima-mix-v10-showcase','look-wai-fantasy-portrait','look-anima-fantasy-portrait','look-animagine-fantasy-portrait']);
  assert.deepEqual(looks('scene'),['look-night-shift-retro-anime','look-noob-fantasy-scene','look-krea-watercolor-anime']);
  assert.deepEqual(looks('painting').slice(0,2),['look-anima-painterly-artist-tags','look-krea-style-emerald-tarot']);
  assert.ok(['look-krea-atelier-target-stack','look-krea-witch-nijisis'].every(id=>looks('painting').includes(id)&&!looks('character').includes(id)),'oil-paint and Nijisis looks are paintings');
  assert.deepEqual(looks('photo').slice(0,2),['look-preset-zimage-fast','look-preset-realvis']);assert.deepEqual(looks('game'),['look-zimage-game-icon','look-preset-stylized-prop','look-preset-pixel-lora']);
  for(const g of goals.filter(g=>g.looks)){const first=g.looks.findIndex(id=>/krea/.test(id));assert.ok(first<0||g.looks.slice(first).every(id=>/krea/.test(id)),g.id+' keeps Krea last');for(const id of g.looks)assert.ok(ids.has(id),id);}
  const tested=grab(/const TESTED=(\{[^}]*\});/),shapes=grab(/const SHAPE_FOR=(\{[^}]*\});/);
  assert.deepEqual(Object.keys(tested).sort(),['look-anima-painterly-artist-tags','look-anima-pearly-petiflow','look-krea-lenovo-ultrareal','look-krea-oil-fantasy','look-krea-realistic-snapshot','look-krea-style-inkwork-darkbrush','look-krea-watercolor-anime','look-night-shift-retro-anime']);
  assert.ok(!('look-zimage-game-icon' in tested),'game icon kept 3 of 8 (round 5), below the badge rule');assert.match(grab(/const BEST_FOR=(\{[^}]*\});/)['look-zimage-game-icon'],/check shape details/);
  assert.deepEqual(shapes,{character:'portrait',scene:'landscape',game:'square'});
});
test('Make speed and Best for come from the look lab doc',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),grab=re=>JSON.parse(JSON.stringify(vm.runInNewContext('('+make.match(re)[1]+')')));
  const doc=fs.readFileSync(path.join(__dirname,'../docs/looks/LOOK-LAB-2026-10-16.md'),'utf8'),rows={};
  for(const m of doc.matchAll(/^\| (look-[\w-]+) \|[^|]*\|[^|]*\| ([\d.]+) \|/gm))rows[m[1]]=Number(m[2]);
  const lab=grab(/const LAB_SECONDS=(\{[^}]*\});/),best=grab(/const BEST_FOR=(\{[^}]*\});/),ids=new Set(JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/looks.json'))).looks.map(l=>l.id));
  assert.ok(Object.keys(rows).length>=20,'the R1 table parses');assert.deepEqual(lab,rows,'LAB_SECONDS is the doc R1 "Median s/image" column');
  for(const id of Object.keys(best)){assert.ok(ids.has(id)&&(id in rows||id==='look-zimage-game-icon'),id);/* round 4 (PR #1488) look: its evidence is its receipts, not an R1 row */assert.ok(best[id].length<=80,id);}
  assert.ok(lab['look-night-shift-retro-anime']>=45,'Night Shift is not Fast (#1448)');
});
const image = {media_type:'image',filename:'source.png'};
const audio = {media_type:'audio',filename:'voice.wav'};
const draft = () => ({version:1,updatedAt:123,recipe:{preset:'qwen-1ref',controls:{positive:'A study',seed:42},batch:1,parent_assets:['source'],references:[]}});
const ready = overrides => U.readiness({preset:{id:'example'},online:true,schemaAvailable:true,...overrides});
test('invalid routes and the retired Overview route normalize to Make', () => {
  for (const route of [null,undefined,'#unknown','#../../models']) assert.equal(U.normalizeView(route),'make');
  assert.equal(U.normalizeView('#models?need=wai'),'models');
  // #18: #home and #overview left the navigation; both land on Make, the default view.
  for (const route of ['#home','#overview','#home?x=1']) assert.equal(U.normalizeView(route),'make',route);
  for (const route of U.VIEWS.filter(route => route !== 'home')) assert.equal(U.normalizeView('#'+route),route);
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
  assert.deepEqual(source.map(i=>[i.code,i.action]),[['source','source'],['wording','fills']]);assert.equal(source[0].message,'Add your picture to Picture to keep (image 1); the authored example picture is never run.');
  // A pose picture is not kept, so the line names the slot by the recipe's own label rather than promising to keep it.
  assert.equal(U.readinessItems({...base,preset:{id:'style-pose-wai',last_reference_label:'Pose picture'},sourceMissing:true})[0].message,'Add your picture to Pose picture; the authored example picture is never run.');
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
test('put-away jobs leave the desk but stay counted', () => {
  const s=U.summarize([],[],[{status:'failed',put_away:true},{status:'uncertain',put_away:true},{status:'uncertain'},{status:'running',put_away:false}]);
  assert.equal(s.attentionJobs.length,1);assert.equal(s.putAwayJobs.length,2);assert.equal(s.activeJobs.length,1);
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
test('memory headroom refusals are explained in plain words, claiming only what the evidence shows (#308)', () => {
  const low=U.failureDetails({status:'failed',prompt_ids:[],message:'Host commit headroom 20.0 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission. No prompt was submitted for output 1.'});
  assert.equal(low.kind,'host_headroom');
  assert.match(low.title,/^Held/);
  assert.match(low.summary,/20\.0 GiB/);assert.match(low.summary,/32 GiB/);assert.match(low.summary,/commit headroom/);assert.match(low.summary,/RAM plus the page file/);assert.match(low.summary,/Nothing was sent to ComfyUI/);
  assert.doesNotMatch(low.summary+low.action,/GPU/,'the check measures commit, not GPU memory');
  assert.match(low.action,/Generate again/);assert.doesNotMatch(low.action,/retr(y|ied) automatically/i);
  assert.match(low.detail,/Host commit headroom 20\.0 GiB/,'the engine wording stays available');
  const partial=U.failureDetails({status:'partial',prompt_ids:['p1'],message:'Host commit headroom 19.5 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission. No prompt was submitted for output 2.'});
  assert.equal(partial.kind,'host_headroom');assert.match(partial.summary,/Output 2 was not sent/);assert.doesNotMatch(partial.summary,/Nothing was sent/);
  const unknown=U.failureDetails({status:'failed',message:'Host commit headroom is unavailable: performance counters are unavailable. No prompt was submitted for output 1.'});
  assert.equal(unknown.kind,'host_headroom');assert.match(unknown.title,/unknown/);assert.match(unknown.summary,/performance counters are unavailable/);assert.match(unknown.summary,/instead of guessing/);
  // Without the server's no-submission clause, nothing is claimed about what was sent.
  const bare=U.headroomExplanation('Host commit headroom 12.3 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission');
  assert.match(bare,/^Held: .*12\.3 GiB/);assert.doesNotMatch(bare,/sent/);
  const evidence=U.failureDetails({status:'failed',prompt_ids:[],message:'Host commit headroom 12.3 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission'});
  assert.doesNotMatch(evidence.summary,/sent/,'empty prompt_ids alone is not no-submission evidence (submission_evidence.never_submitted)');
  const lone=U.failureDetails({status:'partial',prompt_ids:[],message:'Host commit headroom 12.3 GiB is below the required 32 GiB. No prompt was submitted for output 2.'});
  assert.match(lone.summary,/Output 2 was not sent to ComfyUI\./);assert.doesNotMatch(lone.summary,/had already finished/);
  // After the opt-in release: the card says the cache was already freed and points at other programs.
  const freed=U.failureDetails({status:'failed',prompt_ids:[],message:"Host commit headroom 21.4 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission even after the Studio freed ComfyUI's cached models. No prompt was submitted for output 1."});
  assert.equal(freed.kind,'host_headroom');assert.match(freed.summary,/21\.4 GiB even after it freed ComfyUI's cached models; this job needs 32 GiB/);assert.match(freed.action,/outside ComfyUI/);assert.doesNotMatch(freed.action,/wait until a running job/);
  assert.doesNotMatch(low.summary,/freed/);
  assert.equal(U.headroomExplanation('Seed plus batch count exceeds supported range'),null);
  assert.equal(U.failureDetails({status:'running',message:'Generating output 1 of 1'}),null);
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
test('Make seamless offers the server seam bands, keeps a too-wide band listed with its reason, and sends a number',()=>{
  const status={eligible:true,band_px:112,band_choices:[{name:'narrow',band_px:112,available:true,reason:null},{name:'wide',band_px:160,available:true,reason:null}]};
  const both=U.tileBands(status);
  assert.deepEqual(both.options,[{value:'112',label:'narrow (112 px)',disabled:false,selected:true},{value:'160',label:'wide (160 px)',disabled:false,selected:false}]);
  assert.equal(both.note,'');
  const small=U.tileBands({...status,band_choices:[status.band_choices[0],{name:'wide',band_px:160,available:false,reason:'A 160 px band needs a side of at least 320 px; this texture is 256 px.'}]});
  assert.deepEqual(small.options.map(o=>o.disabled),[false,true]);
  assert.equal(small.note,'Wide: A 160 px band needs a side of at least 320 px; this texture is 256 px.');
  assert.deepEqual(U.tileBands({eligible:false,band_choices:status.band_choices}),{options:[],note:''},'no choice on a picture that cannot tile');
  assert.deepEqual(U.tileBands(null),{options:[],note:''});
  assert.equal(U.tileBandPx('160'),160);assert.equal(U.tileBandPx(''),null);assert.equal(U.tileBandPx(undefined),null);assert.equal(U.tileBandPx('wide'),null);
});
test('pose canvas is exposed as an operable application, not a static image (#1402)', () => {
  const code = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');
  const match = code.match(/<canvas id="uxPoseCanvas"[^>]*>/);
  assert.ok(match, 'pose canvas markup must be present');
  const tag = match[0];
  assert.match(tag, /role="application"/, 'keyboard-operable pose canvas must not expose role=img (WCAG 4.1.2)');
  assert.match(tag, /aria-roledescription="pose editor"/, 'pose canvas must name its roledescription');
  assert.match(tag, /aria-label="[^"]*Pose skeleton[^"]*"/, 'pose canvas keeps its accessible label');
  assert.match(tag, /aria-label="[^"]*joint[^"]*arrow keys[^"]*Shift[^"]*"/, 'pose canvas label must describe joint selection, arrow keys and Shift+arrow');
});
test('Make drops a second write to the same target while the first is in flight (Muse lens, 19 Oct)',async()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),line=make.match(/  const inflight=new Set\(\),once=.*\n/)[0];
  const api=vm.runInNewContext(line+';({once,inflight})',{});let calls=0,release;const slow=()=>new Promise(r=>{calls++;release=r;});
  const first=api.once('character:c1',slow),second=api.once('character:c1',slow),other=api.once('character:c2',async()=>{calls++;});
  await second;await other;assert.equal(calls,2,'the same target runs once; another target still runs');release();await first;
  assert.equal(api.inflight.size,0,'the key is released after the write settles');await api.once('character:c1',async()=>{calls++;});assert.equal(calls,3);
  await assert.rejects(api.once('k',async()=>{throw Error('boom');}));
  // Each character form has its own key (Codex P2 on #1540): a pending save of one form never drops another form's save.
  assert.match(make,/once\('character-save:'\+form\.dataset\.mode\+':'\+form\.dataset\.makeCharacterForm,/);assert.equal(api.inflight.has('k'),false,'a failed write releases its key');
});

test('Petiflow additions use knowledge defaults while retaining every lab note',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),kb=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/settings-kb.json'),'utf8')).loras;
  const look={id:'look-anima-pearly-petiflow'},preset={},t={rows:[],cleared:[]},names=['anima-xilmo-000020.safetensors','anima-ke-ta_style_v1.safetensors','anima-newanimastyle-v1.safetensors','anima-kieed_v9_step6000.safetensors'];
  const context={tunedPreset:()=>preset,presetFor:()=>preset,tuneOf:()=>t,freeSlot:()=> 'lora2',compatible:()=>names,entry:n=>kb[n],clamp:n=>n,tuneChanged(){},q:()=>null,say(){},fits:()=>true,short:n=>n};
  const start=make.indexOf('  const LAB='),end=make.indexOf('  // Style strength',start),add=make.slice(make.indexOf('  function addAdapter('),make.indexOf('  function tuneClick('));
  const api=vm.runInNewContext(make.slice(start,end)+add+';({addAdapter,labOf})',context);
  for(const name of names){t.rows=[];api.addAdapter(look,name);assert.equal(t.rows[0].strength,kb[name].default,name);assert.match(String(api.labOf(look,name)),/Lab with Petiflow:/);}
  assert.match(String(api.labOf(look,names[3])),/flattened the face/);
});

test('Tune lists every fitting LoRA as a card: other families folded, typing narrows, a recorded 0 starts at 1 (19 Oct)',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
  const kb={'a.safetensors':{label:'Alpha style',family:'Anima',role:'style',trigger:'@alpha',default:0.6,strength:[0.3,1]},'b.safetensors':{label:'Beta',family:'Anima',role:'detail',trigger:'@betaword',default:0,strength:[0,1]},'c.safetensors':{label:'Gamma',family:'Other',role:'style',default:1}};
  const t={rows:[{slot:'lora',name:'a.safetensors'}],cleared:[]},files=Object.keys(kb);
  const context={tuneOf:()=>t,freeSlot:()=>'lora2',compatible:()=>files,entry:n=>kb[n],clamp:v=>Math.min(2,Math.max(0,Math.round((Number(v)||0)*20)/20)),fits:(l,f)=>kb[f].family==='Anima',short:n=>kb[n].label,escape:s=>String(s),tuneChanged(){},q:()=>null,say(){},labOf:()=>null};
  const api=vm.runInNewContext(make.slice(make.indexOf('  function adapterMatches('),make.indexOf('  function tuneClick('))+';({loraCards,startOf,adapterMatches,addAdapter})',context);
  const all=api.loraCards({},'');
  assert.doesNotMatch(all,/data-tune-pick="a\.safetensors"/,'an added LoRA is not offered again');
  assert.match(all,/data-tune-pick="b\.safetensors"[\s\S]*<details class="make-lora-more"><summary>1 from other families[\s\S]*data-tune-pick="c\.safetensors"/,'made-for first, other families folded');
  assert.match(all,/starts at 1\.00 \(works 0–1\)/,'a recorded 0 is not a starting strength');
  assert.equal(api.startOf('a.safetensors'),0.6);assert.equal(api.startOf('b.safetensors'),1);
  const narrowed=api.loraCards({},'gam');assert.match(narrowed,/c\.safetensors/);assert.doesNotMatch(narrowed,/b\.safetensors|<details/);
  assert.match(api.loraCards({},'zzz'),/No installed LoRA for this model matches/);
  // Enter and Add use the list's search (Codex P2 on #1537): a trigger word alone finds and adds its LoRA.
  assert.match(api.loraCards({},'@betaword'),/data-tune-pick="b\.safetensors"/);assert.deepEqual(api.adapterMatches({},'@betaword'),['b.safetensors']);
  api.addAdapter({},'b.safetensors');assert.equal(t.rows.at(-1).name,'b.safetensors');assert.equal(t.rows.at(-1).strength,1);
});

test('An Anima-family merge counts as Anima for its LoRAs (family_aliases, 19 Oct)',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),kb=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/settings-kb.json'),'utf8'));
  const lines=make.match(/  const base=p=>.*\n  const fits=.*\n/)[0];
  const mix={family:'One Obsession Anima v2.0'},context={kb:()=>kb,presetFor:()=>mix,tunedPreset:()=>mix,entry:n=>({'a.safetensors':{family:'Anima'},'j.safetensors':{family:'JANIMA v1 (Anima)'}})[n]};
  const api=vm.runInNewContext(lines+';({fits,base})',context);
  assert.equal(api.base(mix),'Anima');assert.equal(api.fits({},'a.safetensors'),true,'an Anima LoRA is made for an Anima merge');assert.equal(api.fits({},'j.safetensors'),false,'another family still may not suit');
});
test('Make offers a character card on every saved picture regardless of review, and preserves canon labels',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
  const context={state:{charSave:null},reviewOf:()=>context.review,usableCharacters:()=>context.characters,escape:s=>s,characterForm:()=>'<form>character</form>',CANON_NOTE:'canon',characters:[]};
  vm.runInNewContext(make.slice(make.indexOf('  function characterMarkup('),make.indexOf('  // Prefilled from the run')),context);
  for(const review of ['unreviewed','selected','rejected','needs_work']){context.review=review;assert.match(context.characterMarkup({status:'completed'},'asset-0'),/data-make-character-save="asset-0"/,review);}
  context.state.charSave='asset-0';assert.equal(context.characterMarkup({},'asset-0'),'<form>character</form>');
  context.characters=[{canon_asset_id:'asset-0',name:'Mira'}];assert.equal(context.characterMarkup({},'asset-0'),'<small class="make-canon">Canon of Mira</small>');
  assert.equal(context.characterMarkup({},null),'');
  context.state.charSave=null;context.characters=[];context.assetState={assets:[{id:'asset-0',trashed_at:1}]};
  assert.match(context.characterMarkup({},'asset-0'),/Put away in the library/,'a put-away picture says why instead of offering a form that can only fail');
  assert.doesNotMatch(context.characterMarkup({},'asset-0'),/data-make-character-save/);
});
test('Make depth is explicit, Copy Pose remains default, missing choices fall back and plain 9B stays hidden',()=>{
  const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
  const ids=['combine-klein-9b-copypose','combine-klein-9b-replace','combine-klein-9b-depth','combine-klein-9b','combine-klein'];
  const context={state:{poseMode:'picture',poseRoute:'copy'},ready:()=>true,presets:()=>context.list,runnable:p=>!!p&&!p.runtime_block,SC:()=>({destinations:()=>context.list,combineKind:()=> 'picture'})};
  context.list=ids.map(id=>({id,continuation_capability:{}}));
  vm.runInNewContext(make.slice(make.indexOf('  function goalRoute('),make.indexOf('  // Character in a new pose from a picture'))+make.slice(make.indexOf('  const POSE_ROUTE='),make.indexOf('  const notReady=')),context);
  const route=()=>context.goalRoute({intent:'combine'})?.id;
  assert.equal(route(),ids[0]);context.state.poseRoute='scene';assert.equal(route(),ids[1]);
  context.state.poseRoute='depth';assert.equal(route(),ids[2]);
  context.list=context.list.filter(p=>p.id!==ids[2]);assert.equal(route(),ids[0],'missing depth uses the existing default');
  context.list=ids.map(id=>({id,continuation_capability:{}}));context.list[2].runtime_block='unavailable';assert.equal(route(),ids[2],'explicit depth surfaces its blocker');
  context.state.poseRoute='copy';context.list[0].runtime_block='unavailable';assert.equal(route(),ids[4],'depth and plain 9B never become automatic fallbacks');
  context.list=context.list.filter(p=>p.id!==ids[0]&&p.id!==ids[1]);assert.equal(route(),ids[4],'missing Copy Pose still uses the existing fallback');
  context.state.poseRoute='scene';assert.equal(route(),ids[4],'missing Replace still uses the existing fallback');
  context.list=context.list.filter(p=>p.id!==ids[4]);assert.equal(route(),undefined,'plain 9B stays hidden');
});
console.log(count+' Studio UX policy checks passed.');
