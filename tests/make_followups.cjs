// #1438: run Make's preparation, restore and retry code with synthetic API replies; never submit a job.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {test}=require('node:test');
const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
const between=(start,end)=>{assert.ok(make.includes(start)&&make.includes(end));return make.slice(make.indexOf(start),make.indexOf(end,make.indexOf(start)));};

test('Tune seeds follow the target recipe, including extra bindings and locked zero',async()=>{
  for(const originalSeed of [false,true])for(const targetSeed of [false,true,'extra'])for(const reseed of [false,true]){
    const original={id:'original',...(originalSeed?{seed:['1','seed']}:{})},target={id:'target',...(targetSeed==='extra'?{bindings_extra:{seed:['2','seed']}}:targetSeed?{seed:['2','seed']}:{})};
    const look={id:'look',revision:0,body:{controls:{}}},tune={preset:target.id,reseed,seed:0,rows:[],cleared:[]},requests=[];
    const context={structuredClone,Uint32Array,crypto:{getRandomValues:a=>{a[0]=123;return a;}},
      presets:()=>[original,target],presetFor:()=>original,tuneOf:()=>tune,tuneSummary:()=>'',shapeSize:()=>[512,512],SLOTS:[],
      q:s=>({value:s==='#makeScene'?'a room':s==='#makeShape'?'square':'1'}),view:{querySelectorAll:()=>[]},
      json:async(url,body)=>{requests.push({url,body});return{controls:{positive:'a room'}};}};
    const prepared=vm.runInNewContext(make.match(/  const NAMED=.*\n/)[0]+between('  function applyTune(','  function renderTune(')+between('  async function prepared(','  let estimateEpoch=')+';prepared',context);
    const result=await prepared(look);
    assert.equal(result.preset_id,'target');assert.equal(result.controls.seed,targetSeed?(reseed?123:0):undefined,JSON.stringify({originalSeed,targetSeed,reseed}));
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

function restoreHarness(failure,status='completed'){
  const requests=[],queue=[],saved=[],state={runs:[]};let response=failure;
  const context={state,savedRuns:[{id:'saved',look:'My look',scene:'a room',tune:{seed:0}}],restoredRuns:false,
    presets:()=>[{}],loadCharacters:async()=>{},render(){},renderRuns(){},refreshPickers(){},seedRuns:async()=>{throw Error('Must retain saved history');},
    remember:()=>saved.push(JSON.stringify(state.runs)),FINAL:['completed','failed','uncertain'],
    setTimeout:(fn,delay)=>{const timer={fn,delay};queue.push(timer);return timer;},clearTimeout:timer=>{const i=queue.indexOf(timer);if(i>=0)queue.splice(i,1);},
    fetch:async(url,options={})=>{requests.push({url,options});if(url==='/api/looks')return{ok:true,json:async()=>({looks:[]})};
      if(response==='network')throw TypeError('Network unavailable');return{ok:response===200,status:response,json:async()=>response===200?{id:'saved',status,outputs:[]}:({error:'Unavailable'})};}};
  const api=vm.runInNewContext((make.match(/  const observing=.*\n/)?.[0]||'')+between('  const json=','  // Curated,')+between('  const timers=new Map();','  // A finished run')+between('  async function load(){','  // The gallery folds away')+';({load,pending:()=>timers.size})',context);
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
  const context={state,timers,q:()=>({}),clearTimeout:id=>cleared.push(id),localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
  const render=between('  function renderRuns(){','    planPolish(')+'return list;}';
  const api=vm.runInNewContext(make.match(/  const FINAL=.*\n/)[0]+policy+between('  const remember=','  const presets=')+render+';({remember,renderRuns,savedRuns,restored:()=>{restoredRuns=true;}})',context);
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

function compareHarness(leaveAt){
  const state={goal:'character',busy:false,runs:[]},view={hidden:false,isConnected:true},requests=[],statuses=[],polled=[];let observer;
  const leave=()=>{view.hidden=true;observer?.callback([{oldValue:null}]);view.hidden=false;observer?.callback([{oldValue:''}]);};
  const context={state,view,Uint32Array,crypto:{getRandomValues:a=>a},compareList:()=>[1,2,3].map(id=>({id:'look-'+id,name:'Look '+id,body:{}})),compareBlocker:()=>'',q:()=>({value:'a room'}),say:s=>statuses.push(s),
    MutationObserver:class{constructor(callback){this.callback=callback;observer=this;}observe(){}disconnect(){this.disconnected=true;}},
    presetFor:()=>({id:'preset'}),shapeSize:()=>[512,512],bound:()=>false,remember(){},renderRuns(){},poll:id=>polled.push(id),syncOperation(){},
    json:async(url,body)=>{requests.push({url,body});if(url==='/api/looks/prepare'){if(leaveAt==='prepare')leave();return{controls:{},notices:['Swap '+body.id+'.']};}
      if(leaveAt==='job')leave();return{id:'job-'+requests.filter(r=>r.url==='/api/jobs').length,status:'queued'};}};
  const generate=vm.runInNewContext(between('  async function generateCompare(){','  // Your pictures lives')+';generateCompare',context);
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
  const h=compareHarness();await h.generate();assert.equal(h.state.runs.length,3);assert.equal(h.polled.length,3);assert.match(h.statuses.at(-1),/^Started 3 pictures/);assert.equal(h.state.busy,false);
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
    const context={state,timers,CSS:{escape:x=>x},q:()=>({value:'owner stopped'}),json:async()=>({status:'uncertain',tracking_disposition:{status:action==='resume'?'active':'stopped'}}),
      renderRuns(){},remember(){},say(){},poll:id=>polled.push(id),clearTimeout:id=>cleared.push(id)};
    const recover=vm.runInNewContext(make.match(/  const FINAL=.*\n/)[0]+(make.match(/  const observing=.*\n/)?.[0]||'')+between('  async function recover(','  const marks=')+';recover',context);
    await recover({dataset:action==='resume'?{makeResume:'job'}:{makeStop:'job'}});
    assert.deepEqual(polled,action==='resume'?['job']:[]);assert.deepEqual(cleared,action==='stop'?['timer']:[]);assert.equal(timers.has('job'),action==='resume');
  }
});
