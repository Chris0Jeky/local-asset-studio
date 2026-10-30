'use strict';
// #1857 Repair a marked region: the handoff's box parsing, the drag mapping from the scaled picture to source pixels, and the
// attach after Prepare, run on the sliced studio-workbench.js region. Nothing here submits a job.
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
function section(start,end){const a=code.indexOf(start),b=code.indexOf(end,a+start.length);assert.ok(a>=0&&b>a,start);return code.slice(a,b);}
// Values made inside the vm context carry its own prototypes: compare them as JSON.
const same=(actual,expected,message)=>assert.equal(JSON.stringify(actual),JSON.stringify(expected),message);
const region=section('  // #1857 Repair a marked region',"\n  q('#uxPrepareHandoff').onclick=");

function box(extra={}){
  const nodes=new Map(),listeners={},posts=[],calls=[];
  const node=()=>({value:'',textContent:'',open:true,addEventListener(){},querySelector:()=>node(),querySelectorAll:()=>[],getAttribute:()=>null,setAttribute(){},append(){}});
  const b={posts,calls,listeners,handoffBusy:false,submitting:false,sourceContext:{width:800,height:400,sha256:'s'.repeat(64)},handoffAsset:{url:'/media/a.png'},
    repairBoxes:[],repairDrag:null,uploaded:null,handoffBaseline:'stamp',workbenchStamp:()=>'stamp',handoff:{open:true},
    catalog:{presets:[{id:'anime-masked-repair',requires_rgba_mask:true,positive:['2','text'],negative:['3','text']},{id:'plain'}]},
    destinationDetails:()=>calls.push(['details']),selectPreset:(...args)=>calls.push(['selectPreset',...args]),setHandoffParent:(...args)=>calls.push(['parent',...args]),
    updateReady:()=>calls.push(['ready']),element:()=>({style:{}}),escape:String,
    post:async(url,body)=>{posts.push([url,body]);return b.reply(body);},
    document:{addEventListener:(type,fn)=>{(listeners[type]=listeners[type]||[]).push(fn);}},
    q:s=>{if(!nodes.has(s))nodes.set(s,node());return nodes.get(s);},...extra};
  b.q('#uxDestination').value='anime-masked-repair';
  vm.createContext(b);vm.runInContext(region+'\nthis.api={repairParse,repairReason,repairPoint,prepareRepair,beginRepair};',b);return b;
}
const pick={getBoundingClientRect:()=>({left:100,top:50,width:200,height:100}),setPointerCapture(){}};
const at=(x,y)=>({clientX:x,clientY:y,button:0,pointerId:1,preventDefault(){},target:{closest:s=>s==='.ux-repair-pick'?pick:null}});

test('typed boxes parse as whole pixels and every refusal names its reason',()=>{
  const {repairParse,repairReason}=box().api,source={width:800,height:400};
  same(repairParse(' 8,8,40,40; 0 0 16 16 '),[[8,8,40,40],[0,0,16,16]]);
  for(const text of ['','8,8,40','8,8,40.5,40','a,b,c,d','8,8,40,40,1'])assert.equal(repairParse(text),null,text);
  assert.match(repairReason([],null),/Reading the picture/);
  assert.match(repairReason([[0,0,8,8]],{width:804,height:400}),/divisible by 8/);
  assert.match(repairReason([],source),/Mark the region to repair/);
  assert.match(repairReason(Array(17).fill([0,0,8,8]),source),/at most 16/);
  assert.match(repairReason([[0,0,801,20]],source),/not inside the 800 × 400 picture/);
  assert.match(repairReason([[0,0,7,20]],source),/too small/);
  assert.equal(repairReason([[0,0,8,8],[100,50,300,250]],source),null);
});

test('a drag on the scaled picture maps to source pixels, clamped, and adds one box',()=>{
  const b=box(),{repairPoint}=b.api;
  same(repairPoint(pick,at(150,75),{width:800,height:400}),[200,100],'the picture is shown at a quarter of its size');
  same(repairPoint(pick,at(400,0),{width:800,height:400}),[800,0],'a point off the picture clamps to its edge');
  b.listeners.pointerdown[0](at(160,140));b.listeners.pointerup[0](at(110,60));
  same(b.repairBoxes,[[40,40,240,360]],'dragging up-left still gives x0<x1 and y0<y1');
  b.listeners.pointerdown[0](at(110,60));b.listeners.pointerup[0](at(111,61));
  assert.equal(b.repairBoxes.length,1,'a click is not a box');assert.match(b.q('#uxHandoffStatus').textContent,/at least 8 px/);
  b.handoffBusy=true;b.listeners.pointerdown[0](at(110,60));assert.equal(b.repairDrag,null,'no marking while Prepare runs');
});

test('Prepare posts the boxes to the repair route and attaches the returned upload to the reference slot',async()=>{
  const b=box({repairBoxes:[[40,40,240,360]]});
  b.reply=body=>({generation_submitted:false,file:'f'.repeat(32)+'_repair-mask.png',sha256:'m'.repeat(64),width:800,height:400,preset_id:'anime-masked-repair',
    plan:{source_asset_id:'asset',source_sha256:'s'.repeat(64),mask_file:'f'.repeat(32)+'_repair-mask.png',boxes:body.boxes},
    context:{title:'Hand',prompt_origin:'submitted-output',prompt_role:'description',positive:'1girl, raised hand',negative:'bad hands'}});
  assert.equal(await b.api.prepareRepair('asset','anime-masked-repair',b.sourceContext,()=>true),true);
  same(b.posts,[['/api/repair/prepare',{asset_id:'asset',preset_id:'anime-masked-repair',boxes:[[40,40,240,360]]}]],'one prepare call and never /api/jobs');
  assert.equal(b.uploaded,'f'.repeat(32)+'_repair-mask.png');
  same(b.calls.filter(c=>c[0]!=='ready'),[['selectPreset','anime-masked-repair',true,true,true],['parent','reference','asset']]);
  assert.equal(b.q('#positive').value,'1girl, raised hand');assert.equal(b.q('#negative').value,'bad hands');assert.equal(b.q('#reference').value,'');
  assert.match(b.q('#referenceHint').textContent,/1 marked box\./);
});

test('without verified source wording the prompt stays blank instead of the recipe example',async()=>{
  for(const context of [{title:'Imported'},{prompt_origin:'unavailable',prompt_role:'unknown',positive:null},{prompt_origin:'submitted-output',prompt_role:'instruction',positive:'Make it night'}]){
    const b=box({repairBoxes:[[40,40,240,360]]});b.q('#positive').value='';b.q('#negative').value='';
    b.reply=body=>({generation_submitted:false,file:'x.png',width:800,height:400,preset_id:'anime-masked-repair',plan:{source_asset_id:'asset',source_sha256:'s'.repeat(64),mask_file:'x.png',boxes:body.boxes},context});
    assert.equal(await b.api.prepareRepair('asset','anime-masked-repair',b.sourceContext,()=>true),true);
    same(b.calls.find(c=>c[0]==='selectPreset'),['selectPreset','anime-masked-repair',true,true,true],'selected with a blank prompt');
    assert.equal(b.q('#positive').value,'',JSON.stringify(context));assert.equal(b.q('#negative').value,'');
  }
});

test('Continue never offers the seamless-tile repaint, which only Make seamless prepares',()=>{
  const C=require('../app/static/continuation-core.js'),cap={consumes_source:true,operation:'masked-repair',requires_mask:true};
  const presets=[{id:'zimage-seam-repair',name:'Seam',tile_route:true,continuation_capability:cap},{id:'anime-masked-repair',name:'Mask',requires_rgba_mask:true,continuation_capability:cap}];
  assert.deepEqual(C.destinations('repair',presets,null).map(p=>p.id),['anime-masked-repair']);
});

test('a drag over a picture that has not loaded adds no box, and a cancelled pointer ends the drag',()=>{
  const b=box(),blank={getBoundingClientRect:()=>({left:0,top:0,width:0,height:0}),setPointerCapture(){}};
  const on=(x,y)=>({...at(x,y),target:{closest:s=>s==='.ux-repair-pick'?blank:null}});
  b.listeners.pointerdown[0](on(0,0));b.listeners.pointerup[0](on(60,60));
  same(b.repairBoxes,[]);assert.match(b.q('#uxHandoffStatus').textContent,/not loaded yet/);
  b.listeners.pointerdown[0](at(110,60));assert.ok(b.repairDrag);b.listeners.pointercancel[0]();assert.equal(b.repairDrag,null);
});

test('an unverifiable or overtaken Prepare attaches nothing',async()=>{
  const ok=body=>({generation_submitted:false,file:'x.png',plan:{source_asset_id:'asset',source_sha256:'s'.repeat(64),mask_file:'x.png',boxes:body.boxes},context:{}});
  for(const [name,reply] of [['submitted',body=>({...ok(body),generation_submitted:true})],['other source',body=>({...ok(body),plan:{...ok(body).plan,source_asset_id:'other'}})],
    ['other boxes',body=>({...ok(body),plan:{...ok(body).plan,boxes:[[0,0,8,8]]}})]]){
    const b=box({repairBoxes:[[40,40,240,360]],reply});
    await assert.rejects(b.api.prepareRepair('asset','anime-masked-repair',b.sourceContext,()=>true),/could not be verified/,name);
    assert.equal(b.uploaded,null,name);
  }
  const b=box({repairBoxes:[[40,40,240,360]]});b.reply=body=>{b.repairBoxes=[];return ok(body);};
  await assert.rejects(b.api.prepareRepair('asset','anime-masked-repair',b.sourceContext,()=>true),/marked boxes changed/);
  assert.equal(b.uploaded,null);
  const late=box({repairBoxes:[[40,40,240,360]],reply:ok});
  assert.equal(await late.api.prepareRepair('asset','anime-masked-repair',late.sourceContext,()=>false),false);assert.equal(late.uploaded,null,'a superseded handoff applies nothing');
});
