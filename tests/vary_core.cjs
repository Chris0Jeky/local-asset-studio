'use strict';
// Vary subtle / Vary strong (#1202): which recipe a kept picture is varied on, how many pictures, and what the page says.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const C=require('../app/static/continuation-core.js');
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const cap=(operation,extra={})=>({version:1,consumes_source:operation!=='new-image',operation,prompt_role:'description',template_sha256:'b'.repeat(64),...extra});
const refine={id:'refine',name:'Refine pass',positive:['4','text'],reference:['6','image'],seed:['7','seed'],denoise:['7','denoise'],continuation_capability:cap('image-to-image'),
  vary:{status:'starting-value',sources:['portrait','refine'],subtle:{controls:{denoise:0.25},basis:'Measured polish default.'},strong:{controls:{denoise:0.5,steps:6},basis:'Starting value.'}}};
const portrait={id:'portrait',name:'Portrait',positive:['1','text'],seed:['3','seed'],continuation_capability:cap('new-image')};
const plain={id:'plain',name:'Plain text recipe',positive:['1','text'],seed:['3','seed'],continuation_capability:cap('new-image')};
const combine={id:'combine',name:'Combine',positive:['1','text'],seed:['3','seed'],continuation_capability:cap('combine')};
const noSeed={id:'upscale',name:'Upscale',continuation_capability:cap('new-image')};
const presets=[refine,portrait,plain,combine,noSeed];
const picture=(preset_id,extra={})=>({preset_id,job_id:'job-1',media_type:'image',trashed_at:null,...extra});
const runs=(id,seconds,n=3)=>Array.from({length:n},(_,i)=>({preset_id:id,status:'completed',elapsed_seconds:seconds*(i+1)/2,batch_count:1}));

test('a recipe with a declared route varies on it, from the picture, with its recorded strengths',()=>{
  const plan=C.varyPlan(picture('portrait'),presets,[],{});
  assert.equal(plan.kind,'img2img');assert.equal(plan.route.id,'refine');assert.equal(plan.source.id,'portrait');
  assert.deepEqual(plan.strengths.subtle.controls,{denoise:0.25});assert.deepEqual(plan.strengths.strong.controls,{denoise:0.5,steps:6});
  assert.equal(plan.starting,true,'nothing is owner-approved yet');
  assert.equal(C.varyPlan(picture('refine'),presets,[],{}).route.id,'refine','a varied picture varies again');
});
test('a route must really resample the picture: a declaration on the wrong graph is ignored',()=>{
  for(const broken of [{...refine,continuation_capability:cap('instruction-edit')},{...refine,continuation_capability:{...cap('image-to-image'),consumes_source:false}},{...refine,continuation_capability:cap('image-to-image',{prompt_role:'instruction'})},{...refine,vary:{...refine.vary,strong:null}}])
    assert.equal(C.varyRoute('portrait',[broken,portrait]),null);
});
test('round size follows the owner rule: 4 under a minute per picture here, else 2, and 2 with no timing yet',()=>{
  assert.deepEqual(C.varyRound(runs('refine',40),'refine'),{count:4,timing:{count:3,seconds:40}});
  assert.deepEqual(C.varyRound(runs('refine',60),'refine'),{count:2,timing:{count:3,seconds:60}},'a minute is not under a minute');
  assert.deepEqual(C.varyRound([],'refine'),{count:2,timing:null});
  const batch=[{preset_id:'refine',status:'completed',elapsed_seconds:200,batch_count:4}];
  assert.equal(C.varyRound(batch,'refine').count,4,'time is per picture, not per run');
  assert.equal(C.varyPlan(picture('portrait'),presets,runs('refine',30),{}).round.count,4,'the route is timed, not the source recipe');
});
test('with no route, a text recipe falls back to new seeds on the same recipe',()=>{
  const plan=C.varyPlan(picture('plain'),presets,runs('plain',20),{});
  assert.equal(plan.kind,'reseed');assert.equal(plan.route.id,'plain');assert.equal(plan.round.count,4);
});
test('no Vary without a way to vary, each with the reason beside the control',()=>{
  const reason=item=>{const plan=C.varyPlan(item,presets,[],{});assert.equal(plan.kind,'none');assert.ok(plan.reason.length>20,plan.reason);return plan.reason;};
  assert.match(reason(picture('combine')),/Prepare new seed/);
  assert.match(reason(picture('upscale')),/no seed/);
  assert.match(reason(picture('plain',{job_id:null})),/No run is recorded/);
  assert.match(reason(picture('unknown-recipe')),/No Studio recipe/);
  assert.match(reason(picture('portrait',{trashed_at:123})),/bin/);
  assert.match(reason(picture('portrait',{media_type:'video'})),/pictures/);
  assert.match(reason(null),/picture/);
});
test('a route that cannot run here is disabled with its own reason, never swapped for another model',()=>{
  const blocked=C.varyPlan(picture('portrait'),[{...refine,runtime_block:'Switch to Main library to use this recipe.'},portrait],[],{});
  assert.equal(blocked.kind,'none');assert.match(blocked.reason,/Refine pass.*Switch to Main library/);
  const missing=C.varyPlan(picture('portrait'),presets,[],{refine:['krea2_turbo_fp8_scaled.safetensors']});
  assert.equal(missing.kind,'none');assert.match(missing.reason,/krea2_turbo_fp8_scaled/);
  assert.equal(C.varyPlan(picture('portrait'),[{...refine,missing_loras:['niji.safetensors']},portrait],[],{}).kind,'none');
  assert.equal(C.varyPlan(picture('plain'),presets,[],{plain:['model.safetensors']}).kind,'none');
});
test('the status line names the recipe, the strength, the seeds and the time, and says nothing ran',()=>{
  const plan=C.varyPlan(picture('portrait'),presets,runs('refine',300),{});
  const subtle=C.varyStatus(plan,'subtle',1234);
  assert.match(subtle,/Vary subtle/);assert.match(subtle,/Refine pass/);assert.match(subtle,/denoise 0\.25/);assert.match(subtle,/starting value/);
  assert.match(subtle,/2 new seeds from 1234/);assert.match(subtle,/5 min per picture here · 3 runs/);assert.match(subtle,/Nothing was generated/);
  assert.match(C.varyStatus(plan,'strong',7),/denoise 0\.5/);
  assert.match(C.varyStatus(C.varyPlan(picture('portrait'),presets,[],{}),'subtle',1),/No timing on this PC yet/);
  const reseed=C.varyStatus(C.varyPlan(picture('plain'),presets,runs('plain',20),{}),'reseed',9);
  assert.match(reseed,/new seeds, same recipe/);assert.match(reseed,/4 new seeds from 9/);assert.match(reseed,/20 s per picture/);assert.match(reseed,/Nothing was generated/);
  assert.equal(C.varyStatus({...plan,starting:false},'subtle',1).includes('starting value'),false,'an owner-approved strength drops the label');
});
test('the hint beside the buttons names the route, the round and the strengths',()=>{
  assert.equal(C.varyHint(C.varyPlan(picture('portrait'),presets,[],{})),'On Refine pass · 2 pictures · denoise 0.25 / 0.5 (starting values)');
  assert.equal(C.varyHint(C.varyPlan(picture('plain'),presets,[],{})),'Starts afresh from the same words · 2 pictures');
  assert.equal(C.varyHint({kind:'none',reason:'x'}),'x');
});
test('the shipped catalog routes Krea and plain SDXL pictures and nothing else',()=>{
  const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/catalog.json'),'utf8')).presets;
  const routed=Object.fromEntries(catalog.filter(p=>p.vary).map(p=>[p.id,p.vary.sources]));
  assert.deepEqual(Object.keys(routed).sort(),['gentle-variation','krea-refine']);
  // Server-computed capability stands in here: both are image-to-image description routes (tests/test_vary_routes.py proves it from the graphs).
  const live=catalog.map(p=>p.vary?{...p,continuation_capability:cap('image-to-image')}:p);
  assert.equal(C.varyRoute('krea-anime-atelier',live).id,'krea-refine');assert.equal(C.varyRoute('sdxl',live).id,'gentle-variation');
  assert.equal(C.varyRoute('wai',live),null);assert.equal(C.varyRoute('combine-klein-9b-copypose',live),null);
});
console.log(count+' Vary policy contracts passed');
