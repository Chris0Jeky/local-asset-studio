'use strict';
// #1496 Compare one setting: Make's sweep plan and prepared() run with synthetic catalog and API replies; never submit a job.
const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
const between=(start,end)=>{const s=make.indexOf(start);assert.ok(s>=0,'missing '+start);const e=make.indexOf(end,s);assert.ok(e>s,'missing '+end);return make.slice(s,e);};

const model=file=>({loader:'UNETLoader',encoders:['qwen'],file});
const bindings={positive:['1','text'],seed:['2','seed'],steps:['2','steps'],sampler:['2','sampler_name'],lora:['3','strength'],lora_name:['3','lora_name'],lora2:['4','strength'],lora2_name:['4','lora_name']};
const BASE={id:'anima-a',family:'Anima',model:model('a.safetensors'),...bindings,choices:{sampler:['euler','dpmpp_2m']},defaults:{steps:25}};
const OTHER={id:'anima-b',family:'Pearly',model:model('b.safetensors'),...bindings,choices:{sampler:['euler']}};
const NOSTEPS={id:'anima-c',family:'Plain',model:model('c.safetensors'),positive:['1','text'],seed:['2','seed']};
const LOOK={id:'look-p',revision:0,name:'Petiflow',body:{preset_id:'anima-a',controls:{steps:25,seed:7,sampler:'euler',lora:1,lora_name:'petiflow.safetensors',lora2:0}}};
const KB={loras:{'petiflow.safetensors':{label:'Petiflow',family:'Anima'},'keta.safetensors':{label:'Ke-ta',family:'Anima',default:0.35}}};

function harness({presets=[BASE,OTHER],missing={},look=LOOK}={}){
  const requests=[],state={tune:{},sweeps:{},looks:[look],look:look.id};
  const context={state,structuredClone,Uint32Array,crypto:{getRandomValues:a=>{a[0]=4242;return a;}},catalog:{presets},knowledge:KB,missingByPreset:missing,
    q:s=>({value:s==='#makeScene'?'a knight by a fire':s==='#makeShape'?'design':'4'}),view:{querySelectorAll:()=>[]},
    json:async(url,body)=>{requests.push({url,body});return{controls:{positive:'pearlypetif, a knight by a fire',...look.body.controls}};}};
  const api=vm.runInNewContext(between('  const presets=()=>','  view.innerHTML=')+between('  function shapeSize(','  const shapeDefault=')+between('  const SCENE_FIRST=','  let estimateEpoch=')
    +';({sweepPlan,sweepOf,sweepAxes,sweepDefaults,tuneOf,lookWhy,prepared,whyPreset,sweepHint})',context);
  const open=(axis,values)=>{const s=api.sweepOf(look);s.open=true;s.axis=axis;s.values=values;return api.sweepPlan(look);};
  return{...api,look,state,requests,open};
}
const plain=v=>JSON.parse(JSON.stringify(v));
// Everything a run sends, minus the one setting the press varies: must be identical across runs.
const without=(controls,keys)=>Object.fromEntries(Object.entries(controls).filter(([k])=>!keys.includes(k)));

test('folded shut, Compare one setting changes nothing',()=>{
  const h=harness();assert.equal(h.sweepPlan(h.look),null);assert.equal(h.lookWhy(h.look),'');
});

test('steps: two or three values, each run differs only in steps',()=>{
  const h=harness(),plan=h.open('steps',['25','13','']);
  assert.equal(plan.why,'');assert.deepEqual(plain(plan.runs.map(r=>r.label)),['25 steps','13 steps']);
  assert.deepEqual(plain(plan.runs.map(r=>r.tune.steps)),[25,13]);
  assert.deepEqual(plain(without(plan.runs[0].tune,['steps'])),plain(without(plan.runs[1].tune,['steps'])));
  assert.deepEqual(plain(h.sweepDefaults(h.look,{id:'steps'})),['25','13'],'defaults: as made, then the draft count');
});

test('adapter strength includes off, and the label is what is sent',()=>{
  const h=harness(),plan=h.open('adapter:lora',['1','0','0.35']);
  assert.equal(plan.why,'');assert.deepEqual(plain(plan.runs.map(r=>r.label)),['Petiflow 1.00','Petiflow off','Petiflow 0.35']);
  assert.deepEqual(plain(plan.runs.map(r=>[r.tune.rows[0].on,r.tune.rows[0].strength])),[[true,1],[false,1],[true,0.35]]);
  h.tuneOf(h.look).scale=50;const scaled=h.sweepPlan(h.look);
  assert.equal(scaled.runs[2].label,'Petiflow 0.35 → 0.18','Style strength still multiplies, and the card says so');
});

test('model: As made against a compatible model, with an unoffered tuned sampler put back to the recipe default',()=>{
  const h=harness();h.tuneOf(h.look).sampler='dpmpp_2m';
  assert.deepEqual(plain(h.sweepDefaults(h.look,{id:'model'})),['anima-a','anima-b']);
  const plan=h.open('model',['anima-a','anima-b']);
  assert.equal(plan.why,'');assert.deepEqual(plain(plan.runs.map(r=>r.label)),['As made · Anima','Pearly']);
  assert.deepEqual(plain(plan.runs.map(r=>[r.tune.preset,r.tune.sampler])),[['anima-a','dpmpp_2m'],['anima-b','']]);
});

test('every refusal says why, and only a valid plan is sendable',()=>{
  const cases=[['',['1','2'],'choose the setting to vary'],['steps',['25','25'],'give different values'],['steps',['25'],'give two or three values'],
    ['steps',['25','0'],'whole numbers from 1 to 150'],['steps',['25','12.5'],'whole numbers from 1 to 150'],['adapter:lora',['1','2.5'],'from 0 (off) to 2'],
    ['adapter:lora',['0.35','0.36'],'send the same strength'],['model',['anima-a','anima-z'],'not offered for this look']];
  for(const [axis,values,why] of cases){const h=harness(),plan=h.open(axis,values);assert.match(plan.why,new RegExp('^Compare one setting: .*'+why.replace(/[()]/g,'\\$&')),axis+' '+values);assert.equal(h.lookWhy(h.look),plan.why);}
  const h=harness({missing:{'anima-b':['b.safetensors']}}),plan=h.open('model',['anima-a','anima-b']);
  assert.match(plan.why,/^Compare one setting: Pearly: Needs 1 model file first/);
});

test('an axis the look cannot vary is offered disabled with its reason',()=>{
  const bare={...LOOK,id:'look-bare',body:{preset_id:'anima-c',controls:{seed:7}}},h=harness({presets:[NOSTEPS],look:bare});
  const axes=plain(h.sweepAxes(bare));
  assert.deepEqual(axes.map(a=>a.id),['steps','adapter','model']);assert.ok(axes.every(a=>a.why),JSON.stringify(axes));
  assert.match(h.open('steps',['10','20']).why,/takes no step count/);
});

test('one press: one prepare, one seed, and runs that differ only in the chosen setting',async()=>{
  for(const [axis,values,keys] of [['steps',['25','13'],['steps']],['adapter:lora',['1','0'],['lora']],['model',['anima-a','anima-b'],['sampler']]]){
    const h=harness();h.tuneOf(h.look).sampler='dpmpp_2m';h.open(axis,values);
    const request=await h.prepared(h.look,true);
    assert.deepEqual(h.requests.map(r=>r.url),['/api/looks/prepare'],'one prepare, no job: sending is the caller\'s');
    const runs=request.variants;assert.equal(runs.length,2);
    assert.equal(runs[0].controls.seed,4242);assert.equal(runs[1].controls.seed,4242);
    assert.deepEqual(plain(without(runs[0].controls,keys)),plain(without(runs[1].controls,keys)),axis);
    assert.notDeepEqual(plain(runs[0].controls),plain(runs[1].controls),axis+' changes something');
    if(axis==='model')assert.deepEqual(plain(runs.map(r=>r.preset_id)),['anima-a','anima-b']);else assert.ok(runs.every(r=>r.preset_id==='anima-a'));
    assert.ok(runs.every(r=>r.tune.reseed===false&&r.tune.seed===4242),'each run keeps its seed locked');
  }
  const h=harness(),t=h.tuneOf(h.look);t.reseed=false;t.seed=99;h.open('steps',['25','13']);
  const request=await h.prepared(h.look,true);assert.deepEqual(plain(request.variants.map(r=>r.controls.seed)),[99,99],'a locked seed is the one every run uses');
});

test('an invalid plan refuses before anything is asked of the Studio',async()=>{
  const h=harness();h.open('steps',['25','25']);
  await assert.rejects(h.prepared(h.look,true),/give different values/);assert.equal(h.requests.length,0);
});

test('Generate routes a valid plan to the grouped sender, with the same stop-on-leave watch as Compare looks',()=>{
  assert.match(make,/const why=lookWhy\(look\);if\(why\)\{say\(why\);return;\}if\(sweepPlan\(look\)\)return generateSweep\(look\);/);
  const sweep=between('  async function generateSweep(','  async function generateCompare(');
  assert.match(sweep,/watch=leaveWatch\(\)/);assert.match(sweep,/if\(watch\.stopped\(\)\)break;/);assert.match(sweep,/batch_count:1,label:'Make · Compare · '\+look\.name/);
  assert.match(between('  async function generateCompare(','  // Your pictures lives'),/watch=leaveWatch\(\)/);
});

// PR #1518 review round.
test('Steps reads the authored count from the served catalog defaults, and is unavailable with its reason when unknown (Codex 4299976349)',()=>{
  const zimage={id:'zimage-fast',family:'Z-Image',model:model('z.safetensors'),positive:['1','text'],seed:['2','seed'],steps:['8','steps']};
  const night={...LOOK,id:'look-night',body:{preset_id:'zimage-fast',controls:{seed:7,width:1344,height:768}}};
  const served=harness({presets:[{...zimage,defaults:{steps:8}}],look:night});
  assert.deepEqual(plain(served.sweepDefaults(night,{id:'steps'})),['8','4']);assert.equal(served.open('steps',['8','4']).why,'');
  const bare=harness({presets:[zimage],look:night}),steps=plain(bare.sweepAxes(night))[0];
  assert.equal(steps.id,'steps');assert.match(steps.why,/step count is not known/);
  const one=harness({presets:[{...zimage,defaults:{steps:1}}],look:night});assert.deepEqual(plain(one.sweepDefaults(night,{id:'steps'})),['1','2'],'never two equal defaults');
});

test('adapter values are told apart by the strength sent, not the label (Codex 4299976354)',()=>{
  const h=harness();h.tuneOf(h.look).scale=0;
  assert.match(h.open('adapter:lora',['1','0']).why,/send the same strength.*All adapters is at 0%/);
  const r=harness(),plan=r.open('adapter:lora',['0.01','0']);
  assert.match(plan.why,/send the same strength/,'0.01 rounds to 0: off, the same as 0');
  const ok=r.open('adapter:lora',['0.01','0.35']);assert.equal(ok.why,'');assert.equal(ok.runs[0].tune.rows[0].on,false);assert.match(ok.runs[0].label,/ off$/);
});

test('a blocked model value names that model for the Models & setup link (Codex 4299976362)',()=>{
  const h=harness({missing:{'anima-b':['b.safetensors']}}),plan=h.open('model',['anima-a','anima-b']);
  assert.equal(plan.preset,'anima-b');assert.equal(h.whyPreset(h.look),'anima-b');
  assert.equal(harness().whyPreset(LOOK),'anima-a','otherwise the tuned recipe');
});

test('the hint says an added adapter brings its trigger word only where it is on',()=>{
  const h=harness(),t=h.tuneOf(h.look);
  assert.match(h.sweepHint(h.look,{id:'steps'}),/^The same look, words and seed for every picture/);
  t.rows.push({slot:'lora2',name:'keta.safetensors',strength:0.35,on:true,added:true});
  KB.loras['keta.safetensors'].trigger='keta style';
  try{assert.match(h.sweepHint(h.look,{id:'adapter:lora2',slot:'lora2'}),/trigger word “keta style” is added only to the pictures where it is on/);
    assert.match(h.sweepHint(h.look,{id:'adapter:lora',slot:'lora'}),/^The same look, words and seed/);}
  finally{delete KB.loras['keta.safetensors'].trigger;}
});

for(const status of [undefined,400])test('a failed sweep preserves sent swaps: '+(status||'no HTTP answer'),async()=>{
  for(const at of [1,2,3]){
    const state={goal:'character',runs:[]},said=[],sent=[],polled=[];
    const context={state,SCENE_FIRST:'Describe the picture.',say:s=>said.push(s),sayMissing:s=>said.push(s),leaveWatch:()=>({stopped:()=>false,stop(){}}),
      prepared:async()=>({axis:'Model',scene:'a room',variants:[1,2,3].map(i=>({preset_id:'p'+i,controls:{},notes:['Swap '+i+'.']}))}),
      json:async(url,body)=>{sent.push(body);if(sent.length===at){const e=Error('Request refused');if(status!==undefined)e.status=status;throw e;}return{id:'job-'+sent.length};},
      remember(){},renderRuns(){},poll:id=>polled.push(id),showRun(){},syncOperation(){}};
    const generate=vm.runInNewContext(between('  async function generateSweep(','  async function generateCompare(')+';generateSweep',context);
    await generate(LOOK);const message=said.at(-1);assert.equal(sent.length,at);assert.equal(state.runs.length,at-1);assert.equal(polled.length,at-1);assert.equal(state.busy,false);
    if(status===undefined){assert.match(message,/the last one may have started and is not shown here; check the library and Problems before trying again/);assert.doesNotMatch(message,/were not sent|send.*again/);}
    else if(at>1)assert.match(message,new RegExp('Started '+(at-1)+' of 3; the rest were not sent'));
    for(let i=1;i<at;i++)assert.ok(message.includes('Swap '+i+'.'),'keeps every sent variant swap');
    assert.ok(!message.includes('Swap '+at+'.'),'no swap for the refused or uncertain variant');
  }
});
