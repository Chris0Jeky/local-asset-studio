'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const C=require('../app/static/continuation-core.js');global.StudioContinuation=C;
const U=require('../app/static/studio-core.js');
const source={version:1,asset_id:'source-asset',sha256:'a'.repeat(64),positive:'An adult traveller at the station.',negative:'blur',prompt_origin:'submitted-output',prompt_role:'description',preset_id:'anima-portrait'};
const file='a'.repeat(32)+'_source.png';
const cap={version:1,consumes_source:true,operation:'image-to-image',prompt_role:'description',reference_count:1,template_sha256:'b'.repeat(64)};
const p={id:'refine',name:'Refine',positive:['4','text'],reference:['6','image'],continuation_capability:cap};
const claim=C.initial(source,p,'repair',file).claim;
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
test('source description is copied literally, not mixed with destination example',()=>{
  const out=C.initial(source,{...p,defaults:{positive:'Example witch',negative:'example tags'}},'repair',file);
  assert.equal(out.positive,source.positive);assert.equal(out.negative,source.negative);
});
test('instructions and motion never receive a misleading image caption',()=>{
  for(const [role,operation,intent]of [['instruction','instruction-edit','edit'],['motion','image-to-video','animate'],['none','upscale','repair']]){
    const out=C.initial(source,{...p,continuation_capability:{...cap,prompt_role:role,operation}},intent,file);assert.equal(out.positive,'');assert.equal(out.negative,'');
  }
});
test('old edit instructions and missing descriptions are not treated as captions',()=>{
  for(const item of [{...source,prompt_role:'instruction'},{...source,prompt_origin:'unavailable',positive:null}])assert.equal(C.initial(item,p,'repair',file).positive,'');
});
test('source-free routes, unknown capabilities, wrong intents and unprepared masks are rejected',()=>{
  for(const dest of [{...p,continuation_capability:null},{...p,continuation_capability:{...cap,consumes_source:false}},{...p,continuation_capability:{...cap,requires_mask:true}}])assert.throws(()=>C.initial(source,dest,'repair',file));
  assert.throws(()=>C.initial(source,p,'mesh',file));assert.throws(()=>C.initial(source,p,'repair','../source.png'));
});
test('bounded versioned envelope rejects unknown fields and malformed hashes',()=>{
  assert.deepEqual(C.normalize(claim),claim);
  for(const fields of [{version:true},{version:2},{command:'run now'},{source_sha256:'unknown'},{template_sha256:'b'.repeat(63)},{source_asset_id:42},{intent:'invent'}])assert.equal(C.normalize({...claim,...fields}),null);
});
const full=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/catalog.json'))).presets.find(p=>p.id==='krea-refine');
const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'..',full.graph)));
full.defaults=Object.fromEntries(Object.entries(full).filter(([,value])=>Array.isArray(value)&&value.length===2&&graph[value[0]]&&typeof value[1]==='string').map(([key,value])=>[key,graph[value[0]].inputs[value[1]]]));
test('full8 then light touch restores current authored distill and schedule atomically',()=>{
  const before={...full.defaults,positive:source.positive,reference:file,seed:'9223372036854775800'};
  const eight=C.settings(full,full.variants[2].controls,before);assert.equal(eight.lora3,0);assert.equal(eight.steps,8);assert.equal(eight.denoise,.4);
  const light=C.settings(full,full.variants[0].controls,eight);assert.equal(light.lora3,.85);assert.equal(light.steps,4);assert.equal(light.denoise,.25);
  assert.equal(light.positive,source.positive);assert.equal(light.reference,file);assert.equal(light.seed,before.seed);assert.equal(before.steps,4);
});
test('same-preset examples cannot overwrite source or user-edited prompts',()=>{
  const out=C.settings(full,{positive:'Example witch',negative:'example',reference:'bad.png',denoise:.5},{positive:'My revised station portrait',negative:'Keep mine',reference:file});
  assert.equal(out.positive,'My revised station portrait');assert.equal(out.negative,'Keep mine');assert.equal(out.reference,file);
});
test('variant explanations show effective schedule not an implied full redraw',()=>{
  assert.match(C.variantHelp(full,full.variants[2]),/Denoise 0.4/);assert.match(C.variantHelp(full,full.variants[2]),/8 sampling/);assert.match(C.variantHelp(full,full.variants[2]),/Switches off adapter 3/);
  assert.doesNotMatch(C.variantHelp(full,full.variants[2]),/full-noise/);
});
test('actionable blockers distinguish missing source from missing wording',()=>{
  assert.deepEqual(C.blockers(claim,p,{positive:source.positive,reference:file},['source-asset']),[]);
  assert.match(C.blockers(claim,p,{positive:'',reference:file},['source-asset']).join(),/Describe/);
  assert.match(C.blockers(claim,p,{positive:'yes',reference:'other.png'},['source-asset']).join(),/Reference no longer holds the picture you chose/);
  assert.deepEqual(C.blockerItems(claim,p,{positive:'',reference:'other.png'},['source-asset']).map(i=>i.code),['source','wording']);
});
test('multi-input continuation cannot retain an authored last frame',()=>{
  const multi={...p,last_reference:['7','image'],last_reference_label:'Last frame',continuation_capability:{...cap,reference_count:2}};
  assert.match(C.blockers(claim,multi,{positive:source.positive,reference:file},['source-asset']).join(),/Last frame is empty/);
  assert.deepEqual(C.blockers(claim,multi,{positive:source.positive,reference:file,last_reference:'b'.repeat(32)+'_last.png'},['source-asset']),[]);
});
const boardCap={...cap,operation:'restyle',reference_count:4,source_input:'last_reference',board_min:1};
const board={id:'style-pose-nova',name:'Style + Pose (Nova)',family:'Nova',positive:['2','text'],reference_slots:[{role:'style',binding:['10','image']},{role:'style',binding:['30','image']},{role:'style',binding:['31','image']}],reference_board:{min:1},last_reference:['11','image'],last_reference_label:'Pose picture',continuation_capability:boardCap};
const styleFile='c'.repeat(32)+'_style.png';
test('restyle puts the source on the pose picture and needs one board picture',()=>{
  const prepared=C.initial(source,board,'restyle',file);assert.equal(prepared.claim.intent,'restyle');assert.equal(prepared.positive,source.positive);
  assert.equal(C.sourceInput(boardCap),'last_reference');assert.equal(C.sourceLabel(board),'Pose picture');
  const empty=[{role:'style',file:null},{role:'style',file:null},{role:'style',file:null}];
  assert.deepEqual(C.blockerItems(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],empty).map(i=>i.code),['board']);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],empty).join(),/Picture 1/);
  const one=[{role:'style',file:styleFile},{role:'style',file:null},{role:'style',file:null}];
  assert.deepEqual(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],one),[]);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:'other.png'},['source-asset'],one).join(),/Pose picture no longer holds/);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],[{role:'style',file:styleFile,missing:true},{role:'style',file:null},{role:'style',file:null}]).join(),/board picture is missing/);
  assert.throws(()=>C.initial(source,board,'edit',file));assert.throws(()=>C.initial(source,p,'restyle',file));
  assert.deepEqual(C.destinations('restyle',[p,board,{...board,id:'other',name:'Other'}],source).map(x=>x.id),['style-pose-nova','other']);
  assert.match(C.guidance(board,source).join(' '),/pose picture/i);assert.doesNotMatch(C.guidance(board,source).join(' '),/Picture 1 only/);
});
test('family matching never resurrects a text-only graph as a refinement',()=>{
  const same={...p,id:'same',family:'Anima'},different={...p,id:'different',family:'Krea'};
  const presets=[{id:'anima-portrait',name:'Source',family:'Anima'},{id:'new',name:'New',family:'Anima',continuation_capability:{...cap,consumes_source:false}},different,same];
  assert.deepEqual(C.destinations('repair',presets,source).map(item=>item.id),['same','different']);
});
test('draft roundtrip keeps the guard rather than downgrading to a normal recipe',()=>{
  const draft={version:1,updatedAt:123,recipe:{preset:p.id,controls:{positive:source.positive,reference:file},batch:1,parent_assets:['source-asset'],continuation:claim}};
  const normalized=U.normalizeDraft(draft);assert.deepEqual(normalized.recipe.continuation,claim);
  assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,continuation:{...claim,version:2}}}),null);
  assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,preset:'new'}}),null);
});
test('dead worker cannot be masked by enhanced run presentation',()=>{
  assert.equal(U.readiness({preset:p,online:true,schemaAvailable:true,workerAlive:false}).ready,false);
});
console.log(count+' continuation client policy checks passed.');
