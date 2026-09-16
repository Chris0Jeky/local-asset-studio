'use strict';
const assert=require('node:assert/strict');
const C=require('../app/static/continuation-core.js');
const P=require('../app/static/pose-editor-core.js');
let count=0;const test=(name,fn)=>{fn();count++;console.log('PASS '+name);};
const recipe=(kind='picture')=>({id:kind,reference_board:{min:1},reference_slots:[{role:'pose'}],last_reference:['20','image'],reference_board_label:kind==='skeleton'?'Pose skeleton (image 1)':'Pose picture (image 1)',continuation_capability:{operation:'combine',source_input:'last_reference'}});
const picture=recipe(),skeleton=recipe('skeleton'),refs=[{file:'pose.png',sha256:'b'.repeat(64),parent_asset:'pose-asset'}];

test('an explicit new guide replaces one picture without weakening ordinary engine compatibility',()=>{
  assert.equal(typeof C.combinePoseReplacementReason,'function','a fresh guide needs its own replacement contract');
  assert.match(C.combineSwitchReason(picture,skeleton,refs),/different inputs/);
  assert.equal(C.combinePoseReplacementReason(picture,skeleton,refs),'');
  assert.equal(C.combinePoseReplacementReason(skeleton,skeleton,refs),'');
  assert.match(C.combineSwitchReason(picture,skeleton,refs),/different inputs/);
});
test('empty or missing replaced input does not block a freshly drawn guide',()=>{
  for(const input of [[],[{file:null}],[{file:'gone.png',missing:true}]])
    assert.equal(C.combinePoseReplacementReason(picture,skeleton,input),'');
});
test('a new guide cannot silently discard a second reference or bypass the target layout',()=>{
  for(const input of [[...refs,{file:'extra.png'}],[...refs,{missing:true}]])
    assert.match(C.combinePoseReplacementReason(picture,skeleton,input),/extra|additional/i);
  for(const target of [picture,null,{...skeleton,reference_slots:[]},{...skeleton,reference_slots:[{role:'style'}]},
                       {...skeleton,reference_slots:[{role:'pose'},{role:'pose'}]}])
    assert.notEqual(C.combinePoseReplacementReason(picture,target,refs),'');
  assert.notEqual(C.combinePoseReplacementReason(null,skeleton,refs),'');
});
const request=P.serialize(P.fromPreset('standing',{width:1024,height:1536}),{width:1024,height:1536});
const reply={file:'f'.repeat(32)+'_drawn-pose.png',sha256:'d'.repeat(64),artifact_id:'e'.repeat(64),bytes:4096,width:1024,height:1536,renderer:'studio.coco18-lines/v1',generation_submitted:false};
test('the guide response is checked against the requested canvas and strips inherited attachment claims',()=>{
  assert.equal(typeof P.guideResponse,'function');
  const sanitized=P.guideResponse({...reply,parent_asset:'wrong-parent',role:'style',missing:true},request);
  for(const field of Object.keys(reply))assert.deepEqual(sanitized[field],reply[field]);
  for(const field of ['parent_asset','role','missing'])assert.equal(field in sanitized,false);
});
test('malformed or mismatched render replies cannot replace the existing picture',()=>{
  for(const patch of [{file:'../pose.png'},{file:'f'.repeat(32)+'_picture.jpg'},{sha256:'bad'},
                      {artifact_id:'bad'},{bytes:0},{bytes:Infinity},{bytes:true},{width:512},
                      {height:1535},{renderer:'unknown'},{generation_submitted:true}])
    assert.throws(()=>P.guideResponse({...reply,...patch},request));
  for(const value of [null,[],{},false])assert.throws(()=>P.guideResponse(value,request));
});
test('typed coordinates are explicit, bounded and preserve coordinate zero',()=>{
  assert.equal(typeof P.positionInput,'function');
  assert.deepEqual(P.positionInput('0','1536',{width:1024,height:1536}),{x:0,y:1536});
  assert.deepEqual(P.positionInput(' 123.25 ','4.50',{width:1024,height:1536}),{x:123.25,y:4.5});
  for(const bad of ['', ' ', '0x10', 'NaN', 'Infinity', '-1', '1025', true, null, [], {}])
    assert.throws(()=>P.positionInput(bad,'5',{width:1024,height:1536}));
  assert.throws(()=>P.positionInput('1','1537',{width:1024,height:1536}));
  assert.throws(()=>P.positionInput('1','2',{width:0,height:1536}));
});
test('typed drafts have an actionable generation hold and use the existing undo history',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(code,/code:'pose-position',message:.*action:'pose-position'/);
  assert.match(code,/if\(action==='pose-position'\)target=q\('#uxPoseX'\)/);
  assert.match(code,/pushPose\(\);poseEdit\(next\)/);
});
console.log(count+' pose guide handoff contracts passed.');
