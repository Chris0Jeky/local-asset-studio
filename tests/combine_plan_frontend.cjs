'use strict';
// #1163 live defect (27 Sep 2026) and #1198: the "Run several recipes on this pair" form, run from the shipped
// studio-workbench.js section in a small stub page. Klein 4B asks who and pose; a ticked Copy Pose also reads the clothes,
// so the form shows that field and Prepare sends it. The form belongs to one pair, the seeds field can be emptied, the stale
// notice clears when the page matches the prepared plan again, and a failed refresh after Start keeps Start withdrawn.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const C=require('../app/static/continuation-core.js');
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/catalog.json'),'utf8'));
// The server derives each recipe's capability from its graph (Studio.catalog); this is the part the plan form reads.
for(const preset of catalog.presets)if(preset.continuation_operation==='combine')preset.continuation_capability={version:1,consumes_source:true,operation:'combine',source_input:'last_reference'};
const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
const start=code.indexOf('  // #1163: the same pair on several recipes'),end=code.indexOf("  // #1203: this PC's owner answers");
assert.ok(start>=0&&end>start,'the plan section is where this contract expects it');
const FOUR='combine-klein',COPY='combine-klein-9b-copypose',DEPTH='combine-klein-9b-depth';

function page({saved={},refresh=async()=>{}}={}){
  const elements={},storage=new Map([['studio-fills:source-asset',JSON.stringify(saved)]]),posts=[],announced=[];
  const q=selector=>elements[selector]||(elements[selector]={value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,files:null});
  const seed={value:'7'},preset=id=>catalog.presets.find(p=>p.id===id);
  const context={q,StudioContinuation:C,catalog,combineWording:new Map(),jobs:[],parentAssets:['source-asset'],recipeTemplateHash:null,
    enginePanel:{hidden:false,innerHTML:''},selected:preset(FOUR),lastUploaded:'keep.png',
    continuationSource:{asset_id:'source-asset',preset_id:'create',sha256:'a'.repeat(64)},
    continuationState:{version:1,intent:'combine',preset_id:FOUR,source_asset_id:'source-asset',source_sha256:'a'.repeat(64),reference_file:'keep.png'},
    referenceRecords:[{role:'pose',file:'pose.png',sha256:'b'.repeat(64)}],
    escape:value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
    combineBusy:()=>false,engineEstimate:()=>null,durationLabel:s=>s+' s',getControl:key=>key==='seed'?seed:null,
    continuationBlockers:()=>[],announce:(text,error)=>announced.push({text,error}),refresh,
    localStorage:{getItem:key=>storage.has(key)?storage.get(key):null,setItem:(key,value)=>storage.set(key,String(value))},
    post:async(url,body)=>{posts.push({url,body});
      if(url==='/api/production')return{id:'plan-1',stages:body.combine_plan.engines.flatMap(e=>body.combine_plan.seeds.map(s=>({engine:e,seed:s}))),combine:{estimate:{total_seconds:60,confidence:'medium'}}};
      return{state:{message:'Running'}};},
  };
  vm.createContext(context);
  // The helpers this section calls live earlier in the workbench; these stand-ins read the same state the same way.
  vm.runInContext(`
    function values(){return{positive:'Klein 4B wording',seed:getControl('seed').value,last_reference:lastUploaded};}
    function attachedReferencePayload(){return referenceRecords.map(r=>({...r}));}
    function pairKey(){return JSON.stringify([continuationState.source_sha256,referenceRecords.filter(r=>r.file).map(r=>r.sha256||r.file)]);}
    function fillsKey(){return continuationState?'studio-fills:'+continuationState.source_asset_id:null;}
    function rememberedFills(){try{return JSON.parse(localStorage.getItem(fillsKey())||'{}');}catch(e){return{};}}
    function combineAnswers(){const saved=rememberedFills(),answers=Object.fromEntries(['who','pose','clothes','outfit'].map(k=>[k,saved['@'+k]||'']));return Object.assign(answers,{who:'the witch',pose:'leaning forward'});}
  `+code.slice(start,end),context);
  const run=text=>vm.runInContext(text,context);
  const tick=(id,checked=true)=>q('#uxPlanEngines').onchange({target:{closest:()=>({checked,dataset:{uxPlanEngine:id}})}});
  const type=(meaning,value)=>q('#uxPlanFills').oninput({target:{dataset:{uxPlanFill:meaning},value}});
  const seeds=value=>{q('#uxPlanSeeds').value=value;q('#uxPlanSeeds').oninput();};
  run('syncCombinePlan()');
  return{q,run,tick,type,seeds,posts,announced,storage,context,preset};
}

let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
(async()=>{
await test('Klein 4B open and Copy Pose ticked: the form shows the clothes field and Prepare sends it',async()=>{
  const p=page();
  assert.equal(p.q('#uxPlanFills').hidden,true,'Klein 4B alone needs nothing more than its own two fields');
  assert.equal(p.q('#uxPlanSeeds').value,'7','the seeds start from the open recipe seed');
  p.tick(COPY);
  const box=p.q('#uxPlanFills');
  assert.equal(box.hidden,false);assert.match(box.innerHTML,/data-ux-plan-fill="clothes"/);
  assert.match(box.innerHTML,/Clothes and colours/);assert.match(box.innerHTML,/Klein 9B · Copy Pose/);assert.match(box.innerHTML,/value=""/);
  const rendered=box.innerHTML;p.type('clothes','a black and red robe');
  assert.equal(box.innerHTML,rendered,'typing never re-renders the field under the cursor');
  assert.equal(JSON.parse(p.storage.get('studio-fills:source-asset'))['@clothes'],'a black and red robe','the answer is kept for this character');
  p.tick(DEPTH);assert.match(box.innerHTML,/Klein 9B · Copy Pose, Klein 9B · depth/);assert.equal((box.innerHTML.match(/data-ux-plan-fill=/g)||[]).length,1,'one field per meaning');
  assert.match(box.innerHTML,/value="a black and red robe"/);
  await p.q('#uxPlanPrepare').onclick();
  const plan=JSON.parse(JSON.stringify(p.posts.find(r=>r.url==='/api/production').body.combine_plan));
  assert.deepEqual(new Set(plan.engines),new Set([FOUR,COPY,DEPTH]));
  assert.deepEqual(plan.answers,{who:'the witch',pose:'leaning forward',clothes:'a black and red robe'});
  assert.equal(p.q('#uxPlanStart').hidden,false);
  p.type('clothes','a blue robe');assert.equal(p.q('#uxPlanStart').hidden,true,'editing the extra answer withdraws Start');
});
await test('a stored answer for this character fills the extra field; an empty one is left for the server to refuse',async()=>{
  const p=page({saved:{'@clothes':'a stored robe'}});p.tick(COPY);
  assert.match(p.q('#uxPlanFills').innerHTML,/value="a stored robe"/);
  await p.q('#uxPlanPrepare').onclick();assert.equal(p.posts.at(-1).body.combine_plan.answers.clothes,'a stored robe');
  const empty=page();empty.tick(COPY);assert.equal(empty.q('#uxPlanPrepare').disabled,false,'the page does not second-guess the server');
  await empty.q('#uxPlanPrepare').onclick();assert.equal('clothes' in empty.posts.at(-1).body.combine_plan.answers,false,'an empty answer is not sent');
});
await test('no extra field when the open recipe asks it, or the ticked recipe has its own edited wording',async()=>{
  const p=page();p.context.selected=p.preset(COPY);p.context.continuationState.preset_id=COPY;p.run('syncCombinePlan()');p.tick(FOUR);
  assert.equal(p.q('#uxPlanFills').hidden,true,'Copy Pose already asks the clothes');
  const q=page();q.run(`combineWording.set(pairKey()+'|${COPY}','Edited Copy Pose wording')`);q.tick(COPY);
  assert.equal(q.q('#uxPlanFills').hidden,true,'edited wording reads no answers');
});
await test('the form belongs to one pair: an engine switch keeps it, another pair starts from its own recipe and seed (#1198)',async()=>{
  const p=page();p.tick(COPY);p.seeds('11, 12');
  p.context.selected=p.preset(COPY);p.context.continuationState.preset_id=COPY;p.run('syncCombinePlan()');
  assert.deepEqual(JSON.parse(p.run('JSON.stringify([...planChoice].sort())')),[FOUR,COPY].sort(),'switching engines within the pair keeps the ticks');
  assert.equal(p.q('#uxPlanSeeds').value,'11, 12');
  p.context.selected=p.preset(FOUR);p.context.referenceRecords=[{role:'pose',file:'other.png',sha256:'c'.repeat(64)}];p.run('syncCombinePlan()');
  assert.deepEqual(JSON.parse(p.run('JSON.stringify([...planChoice])')),[FOUR],'a new pair starts with its open recipe ticked');
  assert.equal(p.q('#uxPlanSeeds').value,'7','and its own seed');assert.equal(p.q('#uxPlanFills').hidden,true);
});
await test('the seeds field can be emptied; it is filled once per pair (#1198)',async()=>{
  const p=page();p.seeds('');p.run('syncCombinePlan()');assert.equal(p.q('#uxPlanSeeds').value,'');
  assert.match(p.q('#uxPlanSummary').textContent,/Type one to four seeds/);
});
await test('the stale notice clears when the page matches again and returns on the next change (#1198)',async()=>{
  const p=page();await p.q('#uxPlanPrepare').onclick();const prepared=p.q('#uxPlanStatus').textContent;assert.match(prepared,/^Prepared 1 pictures/);
  p.seeds('7, 8');assert.match(p.q('#uxPlanStatus').textContent,/Prepare again/);assert.equal(p.q('#uxPlanStart').hidden,true);
  p.seeds('7');assert.equal(p.q('#uxPlanStatus').textContent,prepared,'the Prepared line comes back with Start');assert.equal(p.q('#uxPlanStart').hidden,false);
  p.seeds('9');assert.match(p.q('#uxPlanStatus').textContent,/Prepare again/,'a later change is announced again');
});
await test('Start stays withdrawn and reads Started when the refresh after it fails (#1198)',async()=>{
  const p=page({refresh:async()=>{throw Error('offline');}});await p.q('#uxPlanPrepare').onclick();
  await p.q('#uxPlanStart').onclick();
  assert.equal(p.q('#uxPlanStart').hidden,true);assert.match(p.q('#uxPlanStatus').textContent,/^Started\./);
  assert.ok(p.announced.some(a=>/started.*offline/i.test(a.text)),JSON.stringify(p.announced));
  assert.equal(p.posts.filter(r=>r.url.endsWith('/start')).length,1);
  await p.q('#uxPlanStart').onclick();assert.equal(p.posts.filter(r=>r.url.endsWith('/start')).length,1,'no second Start');
});
console.log(count+' Combine plan form checks passed.');
})().catch(error=>{console.error(error);process.exit(1);});
