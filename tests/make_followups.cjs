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

function restoreHarness(failure){
  const requests=[],queue=[],saved=[],state={runs:[]};let response=failure;
  const context={state,savedRuns:[{id:'saved',look:'My look',scene:'a room',tune:{seed:0}}],restoredRuns:false,
    presets:()=>[{}],loadCharacters:async()=>{},render(){},renderRuns(){},refreshPickers(){},seedRuns:async()=>{throw Error('Must retain saved history');},
    remember:()=>saved.push(JSON.stringify(state.runs)),FINAL:['completed','failed'],
    setTimeout:(fn,delay)=>{const timer={fn,delay};queue.push(timer);return timer;},clearTimeout:timer=>{const i=queue.indexOf(timer);if(i>=0)queue.splice(i,1);},
    fetch:async(url,options={})=>{requests.push({url,options});if(url==='/api/looks')return{ok:true,json:async()=>({looks:[]})};
      if(response==='network')throw TypeError('Network unavailable');return{ok:response===200,status:response,json:async()=>response===200?{id:'saved',status:'completed',outputs:[]}:({error:'Unavailable'})};}};
  const api=vm.runInNewContext(between('  const json=','  // Curated,')+between('  const timers=new Map();','  // A finished run')+between('  async function load(){','  // The gallery folds away')+';({load,pending:()=>timers.size})',context);
  return{...api,state,requests,saved,queue,respond:status=>{response=status;},tick:async()=>{const timer=queue.shift();assert.ok(timer);await timer.fn();}};
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
