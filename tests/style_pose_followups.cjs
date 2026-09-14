'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const B=require('../app/static/bundle-core.js');
const W=require('../app/static/bundle-workflow-core.js');
const G=require('../app/static/bundle-guidance-client.js');
const C=require('../app/static/continuation-core.js');

const clone=value=>JSON.parse(JSON.stringify(value));
const preset=()=>({
  id:'style-pose',name:'Style + Pose',family:'Synthetic',modality:'image',backend_id:'primary',
  style_weight:['14','weight'],pose_strength:['18','strength'],bindings_extra:{},
  defaults:{style_weight:0.75,pose_strength:0.85}
});
const nodes=()=>({
  '14':{class_type:'IPAdapterAdvanced',inputs:{weight:0.75}},
  '18':{class_type:'ControlNetApplyAdvanced',inputs:{strength:0.85}},
  '20':{class_type:'SaveImage',inputs:{images:['18',0],filename_prefix:'Studio/StylePose'}}
});

test('bundle controls cover style and pose with numeric contracts',()=>{
  const p=preset(),recipe={id:'balanced',preset_id:p.id,controls:{}};
  assert.ok(B.KEYS.includes('style_weight'));
  assert.ok(B.KEYS.includes('pose_strength'));
  const resolved=B.resolve(p,recipe,{style_weight:0.55,pose_strength:0.7});
  assert.equal(resolved.style_weight,0.55);
  assert.equal(resolved.pose_strength,0.7);
  assert.equal(B.editable(p,'style_weight'),true);
  assert.equal(B.editable(p,'pose_strength'),true);
  assert.equal(B.controlLabel('style_weight'),'Style weight');
  assert.equal(B.controlLabel('pose_strength'),'Pose strength');
  assert.throws(()=>B.resolve(p,recipe,{style_weight:2.05}),/between 0 and 2/);
});

test('workflow projection binds style and pose without changing native types',()=>{
  const p=preset(),graph=nodes();
  const snapshot={preset:p,recipe:{id:'balanced',preset_id:p.id,name:'Balanced'},graph,controls:{style_weight:0.55,pose_strength:0.7}};
  const base={format:'studio.workflow/v1',name:'Style + Pose',revision:0,backend_id:'primary',schema_sha256:'a'.repeat(64),nodes:clone(graph),outputs:['20'],disabled:[],bypass:{},positions:{},source:{preset_id:p.id,authoring_only:true}};
  const result=W.build(snapshot,base,'Reusable Style + Pose');
  assert.equal(result.document.nodes['14'].inputs.weight,0.55);
  assert.equal(result.document.nodes['18'].inputs.strength,0.7);
  const labels=result.document.steps.flatMap(step=>step.controls.map(control=>control.name));
  assert.ok(labels.includes('Style weight'));
  assert.ok(labels.includes('Pose strength'));
});

test('guidance payload retains style and pose bindings',()=>{
  const p=preset(),graph=nodes();
  const payload=G.payload({preset:p,controls:{style_weight:0.55,pose_strength:0.7},graph});
  assert.deepEqual(payload.expected_bindings.style_weight,[['14','weight']]);
  assert.deepEqual(payload.expected_bindings.pose_strength,[['18','strength']]);
});

test('variant help names every numeric knob authored by the variant',()=>{
  const p={defaults:{denoise:1,steps:30,cfg:4,style_weight:0.75,pose_strength:0.85,lora:1,lora_name:'style.safetensors'}};
  const help=C.variantHelp(p,{controls:{cfg:3.5,style_weight:0.55,pose_strength:0.7,lora:0.6}});
  assert.match(help,/Guidance \(CFG\) 3\.5/);
  assert.match(help,/Style weight 0\.55/);
  assert.match(help,/Pose strength 0\.7/);
  assert.match(help,/Adapter 1 strength 0\.6/);
});
