// #1438: run Make's preparation, restore and retry code with synthetic API replies; never submit a job.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {test}=require('node:test');
const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
const between=(start,end)=>{assert.ok(make.includes(start)&&make.includes(end));return make.slice(make.indexOf(start),make.indexOf(end,make.indexOf(start)));};
const privacy=between('  const creationPrivacy=','  const json=')+between('  const classified=','  // Curated,');

test('an accepted work refusal updates Make Generate without replacing its composer or draft',()=>{
  const nodes=new Map(),look={id:'look',body:{preset_id:'primary-recipe'}},preset={id:'primary-recipe'},reason='The saved selection differs. Switch explicitly in Models & setup.';
  const q=id=>{if(!nodes.has(id))nodes.set(id,{disabled:false,textContent:'',innerHTML:'',dataset:{},attributes:{},setAttribute(k,v){this.attributes[k]=v;},removeAttribute(k){delete this.attributes[k];}});return nodes.get(id);};
  const state={busy:false,status:'',compare:false},context={window:{},q,state,GOALS:[],goal:()=>({}),current:()=>look,tunedPreset:()=>preset,
    placeStatus(){},statusEl:q('#makeStatus'),blockerMarkup:(_look,text)=>text,whyPreset:()=>preset,escape:String,
    backendSwitching:false,backendWorkBlocker:'',online:true,workerAlive:true,schemaAvailable:true,
    render(){throw Error('A readiness change must not rebuild the composer');}};
  context.lookWhy=()=>context.blocker(look);vm.createContext(context);
  vm.runInContext(between('  function runtimeBlocker()','  const blockerMarkup=')+between('  function syncOperation(){','  const say=')+make.match(/  window\.StudioMake=.*\n/)[0],context);
  context.syncOperation();assert.equal(q('#makeGenerate').disabled,false);
  q('#makeScene').value='Keep this draft';const composer=q('#makeComposer'),draft=q('#makeScene');
  context.backendWorkBlocker=reason;
  assert.equal(context.runtimeBlocker(),reason);
  assert.equal(typeof context.window.StudioMake.refreshReadiness,'function');context.window.StudioMake.refreshReadiness();
  assert.equal(q('#makeGenerate').disabled,true);assert.equal(q('#makeWhy').innerHTML,reason);assert.equal(q('#makeGenerate').attributes['aria-describedby'],'makeWhy');
  assert.equal(q('#makeScene'),draft);assert.equal(draft.value,'Keep this draft');assert.equal(q('#makeComposer'),composer);
  context.backendSwitching=true;context.window.StudioMake.refreshReadiness();assert.equal(q('#makeWhy').innerHTML,reason,'Specific work refusal takes priority over a generic switching message');
  context.backendSwitching=false;context.backendWorkBlocker='';context.window.StudioMake.refreshReadiness();
  assert.equal(q('#makeGenerate').disabled,false);assert.equal(q('#makeWhy').innerHTML,'');assert.equal(q('#makeGenerate').attributes['aria-describedby'],undefined);
});

test('Tune seeds follow the target recipe, including extra bindings and locked zero',async()=>{
  for(const originalSeed of [false,true])for(const targetSeed of [false,true,'extra'])for(const reseed of [false,true]){
    const original={id:'original',...(originalSeed?{seed:['1','seed']}:{})},target={id:'target',...(targetSeed==='extra'?{bindings_extra:{seed:['2','seed']}}:targetSeed?{seed:['2','seed']}:{})};
    const look={id:'look',revision:0,body:{controls:{}}},tune={preset:target.id,reseed,seed:0,rows:[],cleared:[]},requests=[];
    const context={structuredClone,Uint32Array,crypto:{getRandomValues:a=>{a[0]=123;return a;}},
      presets:()=>[original,target],presetFor:()=>original,tuneOf:()=>tune,tuneSummary:()=>'',shapeSize:()=>[512,512],SLOTS:[],
      q:s=>({value:s==='#makeScene'?'a room':s==='#makeShape'?'square':'1'}),view:{querySelectorAll:()=>[]},
      json:async(url,body)=>{requests.push({url,body});return{controls:{positive:'a room'},look:{id:'look',name:'Night Shift',revision:0,options:{quiet_wall:true}}};}};
    const prepared=vm.runInNewContext(make.match(/  const NAMED=.*\n/)[0]+between('  function applyTune(','  function renderTune(')+between('  async function prepared(','  let estimateEpoch=')+';prepared',context);
    const result=await prepared(look);
    assert.equal(result.look.id,'look');assert.equal(result.look.options.quiet_wall,true);assert.equal(result.preset_id,'target');assert.equal(result.controls.seed,targetSeed?(reseed?123:0):undefined,JSON.stringify({originalSeed,targetSeed,reseed}));
    assert.deepEqual(requests.map(r=>r.url),['/api/looks/prepare']);
  }
});

test('a swapped sampler or scheduler reaches Make as one plain notice (owner, 16 Oct 2026)',async()=>{
  for(const [notices,expected] of [[['Sampler a swapped.','Scheduler b swapped.'],'Sampler a swapped. Scheduler b swapped.'],[undefined,'']]){
    const p={id:'p'},look={id:'look',revision:0,body:{controls:{}}},tune={preset:p.id,reseed:false,seed:null,rows:[],cleared:[]};
    const context={structuredClone,Uint32Array,crypto:{},presets:()=>[p],presetFor:()=>p,tuneOf:()=>tune,tuneSummary:()=>'',shapeSize:()=>[512,512],SLOTS:[],
      q:s=>({value:s==='#makeScene'?'a room':s==='#makeShape'?'square':'1'}),view:{querySelectorAll:()=>[]},json:async()=>({controls:{positive:'a room',sampler:'euler'},...(notices?{notices}:{})})};
    const prepared=vm.runInNewContext(make.match(/  const NAMED=.*\n/)[0]+between('  function applyTune(','  function renderTune(')+between('  async function prepared(','  let estimateEpoch=')+';prepared',context);
    const result=await prepared(look);
    assert.equal(result.notice,expected);assert.equal(result.controls.sampler,'euler');
  }
  assert.match(make,/const \{scene,tune,tuned,notice,\.\.\.submit\}=request;/,'the notice is never sent on to /api/jobs');
});

test('a tuned recipe replaces inherited sampler and scheduler with its offered defaults',async()=>{
  for(const sampler of ['inherited','offered','tuned'])for(const scheduler of ['inherited','offered']){
    const original={id:'original'},target={id:'target',name:'Other recipe',sampler:['1','sampler_name'],choices:{sampler:['target-sampler','custom'],scheduler:['target-scheduler']},defaults:{sampler:'target-sampler',scheduler:'target-scheduler'}};
    const look={id:'look',revision:0,body:{controls:{}}},tune={preset:target.id,reseed:false,rows:[],cleared:[],sampler:sampler==='tuned'?'custom':''};
    const controls={sampler:sampler==='offered'?'target-sampler':'old-sampler',scheduler:scheduler==='offered'?'target-scheduler':'old-scheduler'};
    const context={structuredClone,presets:()=>[original,target],presetFor:()=>original,tuneOf:()=>tune,tuneSummary:()=>'',shapeSize:()=>[512,512],SLOTS:[],
      q:s=>({value:s==='#makeScene'?'a room':s==='#makeShape'?'square':'1'}),view:{querySelectorAll:()=>[]},json:async()=>({controls,notices:['Original recipe notice.']})};
    const prepared=vm.runInNewContext(make.match(/  const NAMED=.*\n/)[0]+between('  function applyTune(','  function renderTune(')+between('  async function prepared(','  let estimateEpoch=')+';prepared',context);
    const result=await prepared(look),notices=['Original recipe notice.'];
    assert.equal(result.preset_id,target.id);assert.equal(result.controls.sampler,sampler==='tuned'?'custom':'target-sampler');assert.equal(result.controls.scheduler,'target-scheduler');
    if(sampler==='inherited')notices.push("This look's sampler old-sampler is not offered by Other recipe; using its default target-sampler.");
    if(scheduler==='inherited')notices.push("This look's scheduler old-scheduler is not offered by Other recipe; using its default target-scheduler.");
    assert.equal(result.notice,notices.join(' '));
    assert.ok(!('notes' in result),'per-variant notes never ride into the /api/jobs body');
    // A compare reports a variant's swap only when that variant is sent, never for the unsent base run.
    context.sweepPlan=()=>({axis:{label:'Model'},runs:[{label:'Other recipe',tune}]});
    const swept=await prepared(look,true);assert.equal(swept.notice,'Original recipe notice.');assert.equal(JSON.stringify(swept.variants[0].notes),JSON.stringify(notices.slice(1)));delete context.sweepPlan;
  }
});

test('choosing a character uses a live preferred Restyle look or the default and shows its look note',()=>{
  const fallback={id:'default'},preferred={id:'preferred'},note="Its preferred look is put away; Make uses the goal's default look.";
  for(const [available,look_note,expected] of [[[fallback,preferred],null,'preferred'],[[fallback],note,'default'],[[fallback,preferred],note,'default'],[[fallback],"Its preferred look's recipe is no longer usable; Make uses the goal's default look.",'default'],[[],note,null],[[fallback,{id:'previous'}],note,'previous']]){
    const c={id:'mira',canon_asset_id:'canon',body:{who:'Mira',clothes:'green cloak',look_id:'preferred'},look_note},state={form:{},styleLook:'previous',styleWords:true};
    let said='';const context={state,window:{},usableCharacters:()=>[c],lookPictures:()=>available,goal:()=>({intent:'restyle'}),choosePicture:id=>{state.pick={id};},renderPictures(){},say:text=>{said=text;},q:()=>null};
    const choose=vm.runInNewContext(privacy+between('  function chooseCharacter(','  const chosenCharacter=')+';chooseCharacter',context);context.chooseCharacter=choose;
    const click=vm.runInNewContext('(function(e){'+between("    const character=e.target.closest('[data-make-character]');","    const saveChar=e.target.closest(")+'})',context);
    click({target:{closest:()=>({dataset:{makeCharacter:'mira'}})}});
    assert.equal(state.character,'mira');assert.equal(state.pick.id,'canon');assert.equal(state.form.who,'Mira');assert.equal(state.form.clothes,'green cloak');
    assert.equal(state.styleLook,expected);assert.equal(state.styleWords,!available.length);assert.ok(said.includes(look_note||'Your character is chosen'));
    context.goal=()=>({intent:'edit'});said='';click({target:{closest:()=>({dataset:{makeCharacter:'mira'}})}});assert.ok(!said.includes('preferred'),'the look note is for Restyle only');context.goal=()=>({intent:'restyle'});
    delete c.body.look_id;state.styleLook='own choice';choose('mira');assert.equal(state.styleLook,'own choice','no preferred look leaves the current choice alone');
  }
});

function restoreHarness(failure,status='completed'){
  const requests=[],queue=[],saved=[],state={runs:[]};let response=failure;
  const context={state,window:{},view:{dataset:{}},sessionStorage:{getItem:()=>null,removeItem(){}},readDraft:()=>null,restoreDraft:async()=>{},savedRuns:[{id:'saved',look:'My look',scene:'a room',tune:{seed:0}}],restoredRuns:false,
    presets:()=>[{}],loadCharacters:async()=>{},render(){},renderRuns(){},refreshPickers(){},seedRuns:async()=>{throw Error('Must retain saved history');},
    remember:()=>saved.push(JSON.stringify(state.runs)),FINAL:['completed','failed','uncertain'],
    setTimeout:(fn,delay)=>{const timer={fn,delay};queue.push(timer);return timer;},clearTimeout:timer=>{const i=queue.indexOf(timer);if(i>=0)queue.splice(i,1);},
    fetch:async(url,options={})=>{requests.push({url,options});if(url==='/api/looks')return{ok:true,json:async()=>({looks:[]})};
      if(response==='network')throw TypeError('Network unavailable');return{ok:response===200,status:response,json:async()=>response===200?{id:'saved',status,outputs:[]}:({error:'Unavailable'})};}};
  const api=vm.runInNewContext((make.match(/  const observing=.*\n/)?.[0]||'')+between('  const creationPrivacy=','  // Curated,')+between('  const timers=new Map();','  // A finished run')+between('  let pendingNavigation=null;','  window.StudioMake=')+between('  async function load(){','  // The gallery folds away')+';({load,pending:()=>timers.size})',context);
  return{...api,state,requests,saved,queue,respond:code=>{response=code;},jobStatus:next=>{status=next;},tick:async()=>{const timer=queue.shift();assert.ok(timer);await timer.fn();}};
}

test('restored transport and HTTP failures retain history and reuse bounded back-off until recovery',async()=>{
  for(const failure of ['network',503,429]){
    const h=restoreHarness(failure);await h.load();
    assert.equal(h.state.runs.length,1);assert.equal(h.state.runs[0].lost,true);assert.equal(h.state.runs[0].scene,'a room');assert.equal(h.state.runs[0].tune.seed,0);
    assert.equal(JSON.parse(h.saved.at(-1))[0].job.id,'saved');
    for(const delay of [5000,10000,20000,30000,30000]){assert.equal(h.queue[0].delay,delay);await h.tick();}
    h.respond(200);await h.tick();assert.equal(h.state.runs[0].lost,false);assert.equal(h.state.runs[0].job.status,'completed');assert.equal(h.pending(),0);assert.equal(h.queue.length,0);
    assert.ok(h.requests.every(r=>!r.options.method),'recovery only reads; it never resubmits');
  }
});

test('restore drops only a confirmed 404 and does not poll the missing run',async()=>{
  const h=restoreHarness(404);await h.load();assert.equal(h.state.runs.length,0);assert.equal(h.pending(),0);assert.equal(h.queue.length,0);assert.equal(h.saved.at(-1),'[]');
  assert.deepEqual(h.requests.map(r=>r.url),['/api/looks','/api/jobs/saved']);
});

// Use the actual retention/render/persistence code, with only the DOM and timers replaced.
function historyHarness(runs,saved=[]){
  const storage=new Map([['studio.make',JSON.stringify({runs:saved})]]),timers=new Map(runs.map(r=>[r.job.id,r.job.id])),cleared=[],state={goal:'character',runs};
  const policy=make.includes('  const observing=')?between('  const observing=','  const remember='):'';
  const context={state,timers,window:{},rememberDraft(){},runTitle(){},q:()=>({}),clearTimeout:id=>cleared.push(id),localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
  const render=between('  function renderRuns(){','    planPolish(')+'return list;}';
  const api=vm.runInNewContext(privacy+make.match(/  const FINAL=.*\n/)[0]+policy+between('  const remember=','  const presets=')+render+';({remember,renderRuns,savedRuns,restored:()=>{restoredRuns=true;}})',context);
  return{...api,state,timers,cleared,saved:()=>JSON.parse(storage.get('studio.make')).runs};
}
const run=(id,status='completed',group)=>({job:{id,status},look:id,scene:'a room',group});

test('six-card history retains every running card and whole mixed Compare groups, including after reload',()=>{
  const runs=Array.from({length:5},(_,i)=>run('done-'+i)).concat([run('pair-a','completed','pair'),run('pair-b','completed','pair'),run('old-done'),run('queued','queued'),run('painting','running'),run('unknown','uncertain'),run('mixed-done','completed','mixed'),run('mixed-running','observing','mixed')]);
  const expected=runs.filter(r=>r.job.id!=='old-done').map(r=>r.job.id),h=historyHarness(runs);h.restored();h.remember();
  assert.deepEqual(h.saved().map(r=>r.id),expected,'persistence retains complete cards and all ongoing runs');
  assert.equal(h.renderRuns().length,10);assert.deepEqual(h.state.runs.map(r=>r.job.id),expected);assert.deepEqual(h.cleared,['old-done']);
  for(const id of ['queued','painting','unknown','mixed-running'])assert.ok(h.timers.has(id));
  const reload=historyHarness([],h.saved());assert.deepEqual(Array.from(reload.savedRuns,r=>r.id),expected,'restore must not truncate a Compare or ongoing runs');
  reload.remember();assert.deepEqual(reload.saved().map(r=>r.id),expected,'remember before load also keeps the saved history');
});

test('a finished overflow Compare rolls off as a whole, while lost contact stays observed',()=>{
  const runs=Array.from({length:6},(_,i)=>run('done-'+i)).concat([run('a','completed','old'),run('b','failed','old'),{...run('lost','completed'),lost:true},run('stopped','uncertain')]);
  runs.at(-1).job.tracking_disposition={status:'stopped'};
  const h=historyHarness(runs);h.restored();h.renderRuns();h.remember();
  assert.deepEqual(h.state.runs.map(r=>r.job.id),runs.slice(0,6).map(r=>r.job.id).concat('lost'));
  assert.deepEqual(h.saved().map(r=>r.id),h.state.runs.map(r=>r.job.id));assert.deepEqual(h.cleared,['a','b','stopped']);
});

function compareHarness(leaveAt,failure){
  const state={goal:'character',busy:false,runs:[]},view={hidden:false,isConnected:true},requests=[],statuses=[],polled=[];let observer;
  const leave=()=>{view.hidden=true;observer?.callback([{oldValue:null}]);view.hidden=false;observer?.callback([{oldValue:''}]);};
  const context={state,view,window:{},Uint32Array,crypto:{getRandomValues:a=>a},compareList:()=>[1,2,3].map(id=>({id:'look-'+id,name:'Look '+id,body:{}})),compareBlocker:()=>'',q:()=>({value:'a room'}),say:s=>statuses.push(s),
    MutationObserver:class{constructor(callback){this.callback=callback;observer=this;}observe(){}disconnect(){this.disconnected=true;}},
    presetFor:()=>({id:'preset'}),shapeSize:()=>[512,512],bound:()=>false,remember(){},renderRuns(){},poll:id=>polled.push(id),syncOperation(){},
    json:async(url,body)=>{requests.push({url,body});if(url==='/api/looks/prepare'){if(leaveAt==='prepare')leave();return{controls:{},look:{id:body.id,name:body.id,revision:0},notices:['Swap '+body.id+'.']};}
      if(failure&&requests.filter(r=>r.url==='/api/jobs').length===(failure.at||2)){const e=Error('Request refused');if(failure.status!==undefined)e.status=failure.status;throw e;}
      if(leaveAt==='job')leave();return{id:'job-'+requests.filter(r=>r.url==='/api/jobs').length,status:'queued'};}};
  const generate=vm.runInNewContext(privacy+between('  function leaveWatch(){','  // Your pictures lives')+';generateCompare',context);
  return{generate,state,requests,statuses,polled,disconnected:()=>observer?.disconnected};
}

test('Compare navigation during prepare sends zero; navigation during a job keeps only that job and never resumes',async()=>{
  for(const [at,count] of [['prepare',0],['job',1]]){
    const h=compareHarness(at);await h.generate();
    assert.equal(h.requests.filter(r=>r.url==='/api/jobs').length,count,at);assert.equal(h.state.runs.length,count);assert.equal(h.polled.length,count);
    // Codex P2 on #1514: only a look whose job started reports its sampler swap.
    assert.equal(h.statuses.at(-1),'Started '+count+' of 3; the rest were not sent because you left Make.'+(count?' Swap look-1.':''));assert.equal(h.state.busy,false);assert.equal(h.disconnected(),true);
    await Promise.resolve();assert.equal(h.requests.filter(r=>r.url==='/api/jobs').length,count,'returning never sends remaining jobs');
  }
});

test('Compare still sends every look when Make stays visible',async()=>{
  const h=compareHarness();await h.generate();assert.deepEqual(h.requests.filter(r=>r.url==='/api/jobs').map(r=>r.body.look.id),['look-1','look-2','look-3']);assert.equal(h.state.runs.length,3);assert.equal(h.polled.length,3);assert.match(h.statuses.at(-1),/^Started 3 pictures/);assert.equal(h.state.busy,false);
});

test('Compare distinguishes an uncertain last send from an HTTP refusal, without retrying',async()=>{
  for(const at of [1,2])for(const status of [undefined,400]){
    const h=compareHarness(null,{at,status});await h.generate();const said=h.statuses.at(-1);
    assert.equal(h.requests.filter(r=>r.url==='/api/jobs').length,at);assert.equal(h.state.runs.length,at-1);assert.equal(h.state.busy,false);
    if(status===undefined){assert.match(said,/the last one may have started and is not shown here; check the library and Problems before trying again/);assert.doesNotMatch(said,/were not sent|send.*again/);}
    else if(at===2)assert.match(said,/Started 1 of 3; the rest were not sent/);
    if(at===2)assert.match(said,/Swap look-1\./);assert.doesNotMatch(said,/Swap look-2\./);
  }
});

test('uncertain restored runs keep polling reads until the job settles',async()=>{
  const h=restoreHarness(200,'uncertain');await h.load();assert.equal(h.pending(),1);await h.tick();assert.equal(h.pending(),1);
  h.jobStatus('completed');await h.tick();assert.equal(h.pending(),0);assert.ok(h.requests.every(r=>!r.options.method));
});

test('an uncertain run polls at the back-off ceiling, not every 2.5 s (#1514 review)',async()=>{
  const h=restoreHarness(200,'uncertain');await h.load();await h.tick();assert.equal(h.queue[0].delay,30000);
});

test('unfinished cards past the six are capped at 20 (#1514 review)',()=>{
  const runs=Array.from({length:6},(_,i)=>run('done-'+i)).concat(Array.from({length:25},(_,i)=>run('busy-'+i,'running')));
  const h=historyHarness(runs);h.restored();assert.equal(h.renderRuns().length,26);
});

test('uncertain observation can resume and Stop tracking clears its polling timer',async()=>{
  for(const action of ['resume','stop']){
    const state={runs:[run('job','uncertain')]},polled=[],cleared=[],timers=new Map([['job','timer']]);
    const context={window:{},state,timers,CSS:{escape:x=>x},q:()=>({value:'owner stopped'}),json:async()=>({status:'uncertain',tracking_disposition:{status:action==='resume'?'active':'stopped'}}),
      renderRuns(){},remember(){},say(){},poll:id=>polled.push(id),clearTimeout:id=>cleared.push(id)};
    const recover=vm.runInNewContext(privacy+make.match(/  const FINAL=.*\n/)[0]+(make.match(/  const observing=.*\n/)?.[0]||'')+between('  async function recover(','  const marks=')+';recover',context);
    await recover({dataset:action==='resume'?{makeResume:'job'}:{makeStop:'job'}});
    assert.deepEqual(polled,action==='resume'?['job']:[]);assert.deepEqual(cleared,action==='stop'?['timer']:[]);assert.equal(timers.has('job'),action==='resume');
  }
});

test('Make single and comparison pictures show the recorded quiet-left diagnostic',()=>{
  const app=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
  const note=app.slice(app.indexOf('function lookNote('),app.indexOf('var expandedPrompts='));
  for(const group of [false,true])for(const unavailable of [false,true]){
    const output={filename:'scene.png',asset_id:'picture-1',text_safe:unavailable?{error:'unsupported image'}:{left_edge_density:0.02,right_edge_density:0.1,comparison:'left quieter'}};
    const job={id:'job-1',status:'completed',controls:{seed:4},look:{id:'look-night-shift',name:'<Night Shift>',revision:2,options:{quiet_wall:true}},outputs:[output]};
    const runs=[{job,look:'Night Shift',scene:'A room'}],cards=[{group,id:'job-1',runs}];let rendered='';
    const box={children:[],contains:()=>false,querySelectorAll:()=>[]};
    const context={state:{runs},window:{},runCards:()=>cards,q:()=>box,planPolish(){},layout(){},runTitle(){},tick(){},observing:()=>false,
      FINAL:['completed'],words:job=>job.status,picture:()=>true,pictureTitle:String,escape:String,esc:s=>String(s).replaceAll('<','&lt;'),
      recovery:()=>'',marks:()=>'',characterMarkup:()=>'',actions:()=>'',selectedOf:()=>null,draftRun:()=>false,
      document:{activeElement:{},createElement:()=>({children:[],set innerHTML(value){rendered=value;}})}};
    const render=vm.runInNewContext(privacy+note+between('  function renderRuns(){','  // Picture goals stay in Make')+';renderRuns',context);
    render();
    assert.match(rendered,/Prepared with &lt;Night Shift>/);
    assert.match(rendered,/<span data-make-clock="job-1" aria-hidden="true"><\/span>/,'every card carries a silent clock slot');
    if(unavailable)assert.match(rendered,/Quiet-left check unavailable: unsupported image/);
    else{assert.match(rendered,/left 2\.0%, right 10\.0%/);assert.match(rendered,/Detail proxy only/);}
  }
});

test('recorded and new seed result handoffs retain Look provenance without submitting',async()=>{
  const source=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  const handler=source.slice(source.indexOf('  resultPanel.onclick=async e=>{'),source.indexOf('  // Number keys 1-5'));
  const look={id:'look-night-shift',name:'Night Shift',revision:2,options:{quiet_wall:true}};
  for(const mode of ['recorded','new']){
    let saved;const calls=[],recipe={preset_id:'plain',controls:{positive:'scene',seed:4},look,parent_assets:[],references:[]};
    const panel={},context={resultPanel:panel,pairActionBusy:false,setupStamp:()=>'',syncReady(){},q:()=>({}),
      jobs:[{id:'job-1',status:'completed',outputs:[{seed:4}]}],catalog:{presets:[{id:'plain'}]},
      api:async()=>recipe,post:async url=>{calls.push(url);return{template_sha256:'checked'};},
      crypto:{getRandomValues:array=>{array[0]=9;return array;}},StudioContinuation:{combineReferences:()=>[]},
      selectPreset(){},applySaved(value){saved=value;},saveDraft(){},updateReady(){},recipeChanged(){},announce:message=>{throw Error(message);}};
    vm.runInNewContext(handler,context);
    await panel.onclick({target:{closest:()=>({dataset:{uxRerun:mode,job:'job-1',index:'0'}})}});
    assert.equal(JSON.stringify(saved.look),JSON.stringify(look));
    assert.equal(saved.controls.seed,mode==='new'?'9':'4');
    assert.deepEqual(calls,['/api/recipe-check']);
  }
});

// Run clock and tab title: the real helpers with only document, timers and /api/estimate replaced.
function clockHarness(runs){
  const listeners={},requests=[],slows=runs.map(()=>({hidden:true,textContent:''})),els=runs.map((r,i)=>({dataset:{makeClock:r.job.id},textContent:'',closest:()=>({querySelector:()=>slows[i]})})),timers=[];
  const document={title:'Local Asset Studio',hidden:false,addEventListener:(k,fn)=>{listeners[k]=fn;},querySelectorAll:()=>els};
  const context={document,state:{runs},FINAL:['completed','failed'],Date,
    rough:e=>e?.confidence==='none',duration:s=>s<90?Math.round(s)+' s':Math.round(s/60)+' min',
    json:async(url,body,captured)=>{requests.push({url,body,captured});return{estimate_seconds:180,confidence:'medium'};},
    runPrivacy:r=>r.privacy||'regular',requestPrivacy:(scope,privacy)=>({scope,privacy}),
    setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout(){}};
  const api=vm.runInNewContext(between('  const PAINTING=','  function words(job)')+';({runClock,runTitle,tick,slowRun,SLOW})',context);
  return{...api,document,listeners,requests,els,slows,timers,context};
}

test('a painting card shows elapsed time against the usual time on this PC, and nothing once it ends',()=>{
  const {runClock}=clockHarness([]),job={status:'running',started_at:1000},e={estimate_seconds:180,confidence:'medium'};
  assert.equal(runClock(job,e,1080),'1:20 of about 3 min');
  assert.equal(runClock(job,e,1300),'5:00, longer than the usual 3 min');
  assert.equal(runClock(job,{estimate_seconds:180,confidence:'none'},1080),'1:20','a generic guess is not shown as the usual time');
  assert.equal(runClock(job,null,1065),'1:05');
  assert.equal(runClock({...job,status:'completed'},e,1080),'');
  assert.equal(runClock({status:'queued'},e,1080),'','waiting has no painting clock');
});

test('the tab title counts unfinished runs and ticks a finish seen only after the tab returns',()=>{
  const runs=[{job:{id:'a',status:'running'}},{job:{id:'b',status:'queued'}}],h=clockHarness(runs);
  h.runTitle();assert.equal(h.document.title,'(2) Local Asset Studio');
  h.document.hidden=true;runs[0].job.status='completed';runs[1].job.status='failed';h.runTitle();
  assert.equal(h.document.title,'✓ Local Asset Studio');
  h.document.hidden=false;h.listeners.visibilitychange();assert.equal(h.document.title,'Local Asset Studio');
});

test('tick fills each clock, asks /api/estimate once per run and stops when nothing paints',async()=>{
  const now=Date.now()/1000,runs=[{privacy:'private',job:{id:'a',status:'running',started_at:now-20,preset_id:'p',controls:{steps:8},batch_count:2,references:[{}]}}],h=clockHarness(runs);
  h.tick();assert.match(h.els[0].textContent,/^ · 0:2\d$/);assert.equal(h.timers.length,1);
  await new Promise(r=>setImmediate(r));h.tick();
  assert.match(h.els[0].textContent,/^ · 0:2\d of about 3 min$/);
  assert.equal(h.requests.length,1);assert.deepEqual(JSON.parse(JSON.stringify(h.requests[0])),{url:'/api/estimate',body:{preset_id:'p',controls:{steps:8},batch_count:2,reference_count:1},captured:{scope:'private',privacy:'private'}},'the estimate reads the run’s own privacy history');
  runs[0].job.status='completed';const before=h.timers.length;h.tick();assert.equal(h.els[0].textContent,'');assert.equal(h.timers.length,before,'no further tick is scheduled');
});

test('the slow-state hint needs a well-measured usual time and a large overrun, and is advice only',async()=>{
  const {slowRun}=clockHarness([]),job={status:'running',started_at:1000},high={estimate_seconds:60,confidence:'high'};
  assert.equal(slowRun(job,high,1000+170),false,'under usual+120 s');
  assert.equal(slowRun(job,high,1000+181),true,'past both 3x and usual+120 s');
  assert.equal(slowRun(job,{estimate_seconds:600,confidence:'high'},1000+1801),true,'3x governs long runs');
  assert.equal(slowRun(job,{estimate_seconds:600,confidence:'high'},1000+1700),false);
  assert.equal(slowRun(job,{estimate_seconds:60,confidence:'medium'},1000+9999),false,'medium confidence never warns');
  assert.equal(slowRun({...job,status:'completed'},high,1000+9999),false);
  const now=Date.now()/1000,runs=[{job:{id:'a',status:'running',started_at:now-400,preset_id:'p'}}],h=clockHarness(runs);
  h.context.json=async(url,body)=>{h.requests.push({url,body});return{estimate_seconds:60,confidence:'high'};};
  h.tick();assert.equal(h.slows[0].hidden,true,'no hint before the estimate is known');
  await new Promise(r=>setImmediate(r));h.tick();assert.equal(h.slows[0].hidden,false);assert.equal(h.slows[0].textContent,h.SLOW);
  assert.ok(h.requests.every(r=>r.url==='/api/estimate'),'only the estimate is read; nothing is cancelled or sent');
  runs[0].job.status='completed';h.tick();assert.equal(h.slows[0].hidden,true);assert.equal(h.slows[0].textContent,'');
});
