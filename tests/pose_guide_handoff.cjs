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
  assert.deepEqual(P.positionInput('1e3','1E2',{width:1024,height:1536}),{x:1000,y:100});
  for(const bad of ['', ' ', '0x10', 'NaN', 'Infinity', '-1', '1025', true, null, [], {}])
    assert.throws(()=>P.positionInput(bad,'5',{width:1024,height:1536}));
  try{P.positionInput('1e4','5',{width:1024,height:1536});assert.fail('1e4 must stay out of range');}
  catch(error){assert.equal(error.axis,'x');}
  try{P.positionInput('1','1537',{width:1024,height:1536});assert.fail('Y overflow must name axis y');}
  catch(error){assert.equal(error.axis,'y');}
  assert.throws(()=>P.positionInput('1','2',{width:0,height:1536}));
});
test('replacing a pose picture with a drawing clears only the pose answer in the shared switch path',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(code,/const replacingPose=!!guide&&selected.id!==target.id/);
  assert.match(code,/replacingPose\?StudioContinuation.combineGuideAnswers\(combineAnswers\(\)\):combineAnswers\(\)/);
  assert.match(code,/the old pose picture’s description was not kept/);
});
test('typed drafts have an actionable generation hold and use the existing undo history',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(code,/code:'pose-position',message:.*action:'pose-position'/);
  assert.match(code,/if\(action==='pose-position'\)target=q\('#uxPoseX'\)/);
  assert.match(code,/pushPose\(\);poseEdit\(next\)/);
  const ready=code.indexOf('function syncReady(){'),pose=code.indexOf('syncPoseEditor();',ready),items=code.indexOf('readinessItems()',ready);
  assert.ok(ready>=0&&pose>=0&&items>pose,'Canvas refresh must run before the pose-position readiness check');
  assert.match(code,/if\(error\.axis!=='y'\)q\('#uxPoseX'\)\.setAttribute\('aria-invalid','true'\)/);
  assert.match(code,/if\(error\.axis!=='x'\)q\('#uxPoseY'\)\.setAttribute\('aria-invalid','true'\)/);
});
test('actual arrow handler nudges only the canvas and joint buttons',()=>{
  const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
  const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  const start=code.indexOf('  function poseKeys(e){'),end=code.indexOf("  posePanel.addEventListener('keydown',poseKeys)",start);
  assert.ok(start>=0&&end>start);
  for(const target of ['apply','reset','undo','use','input','canvas','joint']){
    let edits=0,history=0,prevented=0;
    const context={posePoints:[{x:1,y:1}],poseBusy:false,posePositionDirty:()=>false,poseJoint:0,
      poseCanvas:{width:1024,height:1536},poseStatus:()=>{},pushPose:()=>history++,poseEdit:()=>edits++,
      StudioPoseEditor:{nudge:()=>[{x:2,y:1}]}};
    vm.createContext(context);vm.runInContext(code.slice(start,end),context);
    context.poseKeys({key:'ArrowRight',shiftKey:false,preventDefault:()=>prevented++,
      target:{closest:selector=>selector==='#uxPoseCanvas,[data-ux-joint]'?['canvas','joint'].includes(target):selector==='select,input,textarea'&&target==='input'}});
    const expected=['canvas','joint'].includes(target)?1:0;
    assert.equal(edits,expected,target+' must not unexpectedly alter the drawing');
    assert.equal(history,expected,target+' must not add a spurious undo entry');
    assert.equal(prevented,expected,target+' retains its keyboard event');
  }
});
async function pendingAttachmentTests(){
  const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
  const code=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  const start=code.indexOf('  async function usePose(){'),end=code.indexOf("  q('#uxPoseUse').onclick",start);
  assert.ok(start>=0&&end>start,'exercise the actual usePose implementation');
  for(const conflict of ['pending-upload','reference-epoch','picker','none']){
    let resolveReply,switches=0;
    const state={pending:0,epoch:0,picker:false};
    const context={poseBusy:false,posePoints:P.fromPreset('standing',{width:1024,height:1536}),poseCanvas:{width:1024,height:1536},
      poseBlockedReason:()=>'',syncPoseActions:()=>{},workbenchStamp:()=>'unchanged source pair',
      setupStamp:()=>JSON.stringify([state.pending,state.epoch]),setupBusy:()=>state.pending>0||state.picker,
      selected:{id:'picture'},POSE_RECIPE:'skeleton',StudioPoseEditor:P,syncReady:()=>{},
      post:()=>new Promise(resolve=>{resolveReply=resolve;}),
      switchCombineEngine:()=>{switches++;throw Error('test stops before attachment');},poseStatus:()=>{},announce:()=>{}};
    vm.createContext(context);vm.runInContext(code.slice(start,end),context);
    const pending=context.usePose();
    assert.equal(context.poseBusy,true,'the real function admitted the render');
    if(conflict==='pending-upload')state.pending=1;
    if(conflict==='reference-epoch')state.epoch++;
    if(conflict==='picker')state.picker=true;
    resolveReply(reply);await pending;
    assert.equal(switches,conflict==='none'?1:0,conflict+' must not let the old guide discard a newer reference operation');
    assert.equal(context.poseBusy,false,'the render hold is released');
  }
  count++;console.log('PASS actual handoff invalidates pending uploads, reference epochs and active picker operations');
}
pendingAttachmentTests().then(()=>{
  test('render identity fields must be strings, not coercible arrays',()=>{
    for(const key of ['file','sha256','artifact_id'])assert.throws(()=>P.guideResponse({...reply,[key]:[reply[key]]},request));
  });
  console.log(count+' pose guide handoff contracts passed.');
}).catch(error=>{console.error(error);process.exitCode=1;});
