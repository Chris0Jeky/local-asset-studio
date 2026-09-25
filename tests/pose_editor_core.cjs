'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const P=require('../app/static/pose-editor-core.js');
const CANVAS={width:1024,height:1536};
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}

test('the joint order is the COCO-18 order the server reads',()=>{
  const python=fs.readFileSync(path.join(__dirname,'../studio_workflow/pose_artifact.py'),'utf8');
  const declared=/JOINTS = \(([\s\S]*?)\)\n/.exec(python)[1].match(/'([a-z_]+)'/g).map(name=>name.replace(/'/g,''));
  assert.deepEqual(P.JOINTS,declared,'the editor and pose_artifact must name the same joints in the same order');
  assert.equal(P.LABELS[4],'Right wrist');assert.equal(P.COLORS.length,18);
  const raster=fs.readFileSync(path.join(__dirname,'../studio_workflow/pose_raster.py'),'utf8');
  const limbs=/LIMBS = \(([\s\S]*?)\)\n/.exec(raster)[1].match(/\((\d+), (\d+)\)/g).map(pair=>pair.match(/\d+/g).map(Number));
  assert.deepEqual(P.LIMBS,limbs,'the canvas must draw the limbs the renderer draws');
});

test('a preset lands inside the canvas and keeps the research figure exactly',()=>{
  const bent=P.fromPreset('bent',CANVAS);
  assert.equal(bent.length,18);assert.equal(P.known(bent),17);
  assert.equal(bent[16],null,'the research figure has no right ear');
  assert.deepEqual(bent[1],{x:.34*1024,y:.17*1536},'the second joint is the recorded fraction of the canvas');
  for(const point of bent.filter(Boolean)){assert.ok(point.x>=0&&point.x<=CANVAS.width);assert.ok(point.y>=0&&point.y<=CANVAS.height);}
  assert.equal(P.known(P.fromPreset('standing',CANVAS)),18);
  assert.equal(P.fromPreset('mirror',CANVAS),null,'mirror is an operation on the drawing, not a figure');
  assert.equal(P.fromPreset('invented',CANVAS),null);
});

test('a drag moves one joint, clamped to the canvas, and never touches the others',()=>{
  const before=P.fromPreset('standing',CANVAS);
  const moved=P.move(before,4,700,900,CANVAS);
  assert.deepEqual(moved[4],{x:700,y:900});
  assert.deepEqual(before[4],P.fromPreset('standing',CANVAS)[4],'the input array is never mutated');
  assert.deepEqual(moved.filter((_,i)=>i!==4),before.filter((_,i)=>i!==4));
  assert.deepEqual(P.move(before,4,-40,99999,CANVAS)[4],{x:0,y:CANVAS.height},'a drag past the edge stops at the edge');
  for(const bad of [[-1,5,5],[18,5,5],[1.5,5,5],[4,NaN,5],[4,5,Infinity],[4,'5',5]])
    assert.deepEqual(P.move(before,bad[0],bad[1],bad[2],CANVAS),before,'a nonsense edit changes nothing: '+JSON.stringify(bad));
  assert.throws(()=>P.move(before,4,1,1,{width:0,height:10}));
});

test('arrow keys move one per cent of the canvas, Shift five, and never an unknown joint',()=>{
  const start=P.fromPreset('standing',CANVAS);
  const right=P.nudge(start,4,1,0,CANVAS,.01),up=P.nudge(start,4,0,-1,CANVAS,.05);
  assert.equal(Math.round(right[4].x-start[4].x),Math.round(.01*CANVAS.width));
  assert.equal(Math.round(start[4].y-up[4].y),Math.round(.05*CANVAS.height));
  const unknown=P.setUnknown(start,4);
  assert.deepEqual(P.nudge(unknown,4,1,0,CANVAS,.01),unknown,'an omitted joint has no position to nudge');
  assert.deepEqual(P.nudge(start,4,1,0,CANVAS,NaN),start);
});

test('a mirror flips the drawing about the canvas centre and keeps every joint its own',()=>{
  const start=P.fromPreset('bent',CANVAS),flipped=P.mirror(start,CANVAS);
  start.forEach((point,index)=>{
    if(!point){assert.equal(flipped[index],null,'an unknown joint stays unknown through a mirror');return;}
    assert.equal(Math.round(flipped[index].x+point.x),CANVAS.width);assert.equal(flipped[index].y,point.y);
  });
  assert.deepEqual(P.serialize(P.mirror(flipped,CANVAS),CANVAS),P.serialize(start,CANVAS),'mirroring twice is the drawing you started with');
  assert.deepEqual(P.start('mirror',start,CANVAS),flipped);
  assert.deepEqual(P.start('',start,CANVAS),start,'an empty choice keeps the current drawing');
});

test('unknown is not coordinate zero: it is omitted and restored where it was',()=>{
  const start=P.fromPreset('standing',CANVAS),home=start[10];
  const hidden=P.toggle(start,10,home,CANVAS);
  assert.equal(hidden[10],null);assert.equal(P.known(hidden),17);
  assert.deepEqual(P.toggle(hidden,10,home,CANVAS)[10],home,'restoring puts it back where it last was');
  assert.deepEqual(P.toggle(hidden,10,null,CANVAS)[10],P.fromPreset('standing',CANVAS)[10],'with nothing remembered it falls back to standing');
  assert.deepEqual(P.setUnknown(start,99),start);
});

test('the nearest joint is the one under the pointer, and only within reach',()=>{
  const start=P.fromPreset('standing',CANVAS),wrist=start[4];
  assert.equal(P.nearest(start,wrist.x+5,wrist.y+5,40),4);
  assert.equal(P.nearest(start,wrist.x,wrist.y,0),4,'an exact hit needs no radius');
  assert.equal(P.nearest(start,5,5,10),-1,'empty canvas is not a joint');
  assert.equal(P.nearest(P.setUnknown(start,4),wrist.x,wrist.y,40)===4,false,'an omitted joint cannot be grabbed');
});

test('changing the canvas carries the drawing instead of discarding it',()=>{
  const start=P.fromPreset('bent',CANVAS),smaller={width:512,height:768};
  const resized=P.resize(start,CANVAS,smaller);
  assert.deepEqual(resized[1],{x:start[1].x/2,y:start[1].y/2});
  assert.equal(resized[16],null);
  assert.deepEqual(P.serialize(P.resize(resized,smaller,CANVAS),CANVAS),P.serialize(start,CANVAS),'the canvas can go back and the figure comes with it');
});

test('serialisation is pixel coordinates, nulls for the unknown, and the canvas it was drawn on',()=>{
  const drawn=P.setUnknown(P.move(P.fromPreset('standing',CANVAS),0,123.456,234.567,CANVAS),17);
  const value=P.serialize(drawn,CANVAS);
  assert.deepEqual(Object.keys(value).sort(),['height','keypoints','width']);
  assert.equal(value.width,1024);assert.equal(value.height,1536);assert.equal(value.keypoints.length,18);
  assert.deepEqual(value.keypoints[0],[123.46,234.57],'coordinates are rounded, never rewritten');
  assert.equal(value.keypoints[17],null);
  assert.equal(JSON.stringify(value).length<2048,true,'one pose stays well inside the endpoint body cap');
  for(const point of value.keypoints)if(point)for(const axis of point)assert.equal(Number.isFinite(axis),true);
  assert.throws(()=>P.serialize(drawn.slice(1),CANVAS),/exactly 18 joints/);
  assert.throws(()=>P.serialize(drawn,{width:'wide',height:10}),/width and a height/);
});

test('an attached drawn guide holds Generate once Width or Height move off its canvas (#844)',()=>{
  const guide={file:'a'.repeat(32)+'_drawn-pose.png',width:1024,height:1536,renderer:'studio.coco18-lines/v1',missing:false};
  assert.equal(P.guideSizeReason([guide],CANVAS),'','a guide drawn at this canvas is current');
  assert.equal(P.guideSizeReason([guide],{width:832,height:1216}),'The pose guide was drawn at 1024×1536; press Use this pose again for the new size (832×1216).');
  assert.match(P.guideSizeReason([guide],{width:1024,height:1024}),/drawn at 1024×1536/,'one changed axis is enough');
  assert.match(P.guideSizeReason([{},guide],{width:1024,height:1024},'Replace pose picture with drawing'),/press Replace pose picture with drawing again/,'the hold names the button on screen');
  assert.equal(P.guideSizeReason([Object.assign({},guide,{width:832,height:1216})],{width:832,height:1216}),'','drawing again at the new size clears the hold');
  const upload=Object.assign({},guide,{file:'b'.repeat(32)+'_upload.png',width:512,height:768});
  assert.equal(P.guideSizeReason([upload],CANVAS),'','an uploaded picture keeps its own size and is not a stale guide');
  assert.equal(P.guideSizeReason([Object.assign({},guide,{missing:true})],{width:832,height:1216}),'','a missing guide is the references blocker, not this one');
  assert.equal(P.guideSizeReason(null,CANVAS),'');
  const workbench=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(workbench,/StudioPoseEditor\.guideSizeReason\(referenceRecords,poseCanvasSize\(\)/,'readiness compares the attached guide with the canvas Use this pose would render');
  assert.match(workbench,/items\.push\(\{code:'pose-size',message:staleGuide,action:'pose-size'\}\)/,'the stale guide is a Generate readiness blocker');
  assert.match(workbench,/q\('#uxPoseReason'\)\.textContent=reason\|\|poseSizeHold\(\)/,'the pose panel shows the same hold beside Use this pose');
});

test('the hold promises a resize only for the drawing the editor holds, and names a disabled button\'s blocker first (#947, #952)',()=>{
  const id='a'.repeat(64),guide={file:'a'.repeat(32)+'_drawn-pose.png',width:832,height:1216,artifact_id:id,missing:false},now={width:640,height:1216};
  assert.equal(P.guideSizeReason([guide],now,'Use this pose',{artifact:id}),'The pose guide was drawn at 832×1216; press Use this pose again for the new size (640×1216).','the editor holds this guide: a redraw is a resize');
  const unheld=P.guideSizeReason([guide],now,'Use this pose',{artifact:'b'.repeat(64)});
  assert.equal(unheld,'The pose guide was drawn at 832×1216, not the new size (640×1216), and the editor does not hold that drawing. Set Width and Height back to 832×1216, or redraw the pose and press Use this pose.');
  assert.doesNotMatch(unheld,/again for the new size/,'an unrelated drawing is never promised as a resize');
  assert.match(P.guideSizeReason([Object.assign({},guide,{artifact_id:undefined})],now,'Use this pose',{artifact:''}),/does not hold that drawing/,'a guide with no retained drawing is not held either');
  assert.equal(P.guideSizeReason([guide],now,'Use this pose',{artifact:'',loading:id}),'The pose guide was drawn at 832×1216, not the new size (640×1216). Its drawing is loading into the editor.');
  const blocked='Remove the extra board picture before replacing the pose with a drawing.';
  const held=P.guideSizeReason([guide],now,'Replace pose picture with drawing',{artifact:id,blocked});
  assert.equal(held,'The pose guide was drawn at 832×1216, not the new size (640×1216). '+blocked+' Then press Replace pose picture with drawing again.');
  assert.ok(held.indexOf(blocked)<held.indexOf('press Replace'),'the real next step comes before the disabled button');
  assert.equal(P.guideSizeReason([guide],now,'Use this pose',{artifact:'',blocked:'Finish the attachment in progress first'}),
    'The pose guide was drawn at 832×1216, not the new size (640×1216), and the editor does not hold that drawing. Set Width and Height back to 832×1216, or redraw the pose. Finish the attachment in progress first. Then press Use this pose.');
  assert.equal(P.guideSizeReason([guide],{width:832,height:1216},'Use this pose',{artifact:'',blocked}),'','a current guide holds nothing, held or not');
  assert.equal(P.drawnGuide([{},{file:'x.png'},guide]),guide);assert.equal(P.drawnGuide([Object.assign({},guide,{missing:true})]),null);assert.equal(P.drawnGuide(null),null);
});

test('a restored guide\'s stored drawing comes back as editor points, only for that exact guide (#947)',()=>{
  const id='c'.repeat(64),guide={file:'c'.repeat(32)+'_drawn-pose.png',width:832,height:1216,artifact_id:id};
  const joints=Object.fromEntries(P.JOINTS.map((name,i)=>[name,i===16?null:{x:10+i*40,y:20+i*60,confidence:null,origin:'manual'}]));
  const artifact={schema:'studio.pose-artifact/v1',id,canvas:{width:832,height:1216},joints,authority:'none',review:'unreviewed'};
  const points=P.fromArtifact(artifact,guide);
  assert.equal(points.length,18);assert.equal(points[16],null,'an unknown joint stays unknown');
  assert.deepEqual(points[4],{x:170,y:260});
  assert.deepEqual(P.serialize(points,guide).keypoints[0],[10,20],'the drawing is in the guide\'s own pixels');
  const bad=[['another artifact',Object.assign({},artifact,{id:'d'.repeat(64)})],['another canvas',Object.assign({},artifact,{canvas:{width:640,height:1216}})],
    ['another schema',Object.assign({},artifact,{schema:'x'})],['a joint outside',Object.assign({},artifact,{joints:Object.assign({},joints,{nose:{x:900,y:1}})})],
    ['a missing joint key',Object.assign({},artifact,{joints:Object.fromEntries(Object.entries(joints).slice(1))})],
    ['fewer than two joints',Object.assign({},artifact,{joints:Object.fromEntries(P.JOINTS.map((n,i)=>[n,i?null:joints.nose]))})],['nothing',null]];
  for(const [label,value] of bad)assert.throws(()=>P.fromArtifact(value,guide),/does not match/,label);
  assert.throws(()=>P.fromArtifact(artifact,Object.assign({},guide,{artifact_id:undefined})),/does not match/,'a guide with no artifact id loads nothing');
  const before=P.fromPreset('standing',guide),history=P.timeline(5);
  history.record(before,before);const adopted=P.adopt(before,points);
  assert.deepEqual(adopted,points);assert.ok(history.canUndo,'loading a stored drawing is one undoable edit');
  assert.deepEqual(history.undo(adopted,adopted).points,before);
  const held={id,points,canvas:{width:832,height:1216}};
  assert.ok(P.holds(points,{width:832,height:1216},held),'the adopted drawing is held');
  assert.ok(P.holds(P.resize(P.resize(points,held.canvas,{width:640,height:1216}),{width:640,height:1216},{width:512,height:960}),{width:512,height:960},held),'a held drawing stays held through canvas changes');
  assert.ok(!P.holds(before,{width:832,height:1216},held),'after Undo the editor no longer holds the guide');
  assert.ok(!P.holds(P.nudge(points,4,1,0,{width:832,height:1216},.01),{width:832,height:1216},held),'any edit breaks the match');
  assert.ok(!P.holds(P.setUnknown(points,4),{width:832,height:1216},held),'an omitted joint breaks the match');
  assert.ok(!P.holds(points,{width:832,height:1216},null),'nothing adopted, nothing held');
});

// The panel itself needs a DOM this sandbox does not have (canvas, pointer capture, dialogs); what is pinned
// here is the wiring around the pure module, the way tests/frontend_handoffs.cjs pins the picker's.
test('the workbench sends the drawing to the guide endpoint and to no generation route',()=>{
  const workbench=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(workbench,/request=StudioPoseEditor\.serialize\(posePoints,poseCanvas\)/,'the request freezes the intended drawing');
  assert.match(workbench,/body=StudioPoseEditor\.renderRequest\(request,StudioPoseEditor\.guideRenderer\(selected\)\)/,'the recipe picks the renderer; the geometry stays the frozen request');
  assert.match(workbench,/post\('\/api\/pose\/render',body\)/,'Use this pose renders the frozen guide request');
  assert.match(workbench,/drawing!==JSON\.stringify\(StudioPoseEditor\.serialize\(posePoints,poseCanvas\)\)/,'changed geometry invalidates the reply');
  assert.match(workbench,/POSE_RECIPE='combine-klein-9b-skeleton'/,'the drawing belongs to the proved drawn-skeleton recipe');
  assert.match(workbench,/switchCombineEngine\(POSE_RECIPE,result\)/,'explicit replacement uses the checked new guide through the shared switch path');
  assert.match(workbench,/StudioPoseEditor\.guideResponse\(response,body\)/,'response validation precedes attachment');
  assert.match(workbench,/guideResponse\(response,body\);poseHeld=\{id:result\.artifact_id,points:/,'a rendered guide is the drawing the editor holds');
  assert.match(workbench,/api\('\/api\/pose\/artifacts\/'\+id\)/,'a restored guide reads its own stored drawing, a GET that renders and submits nothing');
  assert.match(workbench,/StudioPoseEditor\.fromArtifact\(value,guide\)/,'the stored drawing is checked against the attached guide before it is loaded');
  assert.match(workbench,/\{artifact:poseHeldArtifact\(\),loading:poseLoading\?\.artifact_id,blocked:poseBlockedReason\(\)\}/,'the hold knows what the editor holds and why its button is disabled');
  assert.match(workbench,/if\(poseLoading\)return 'The attached pose guide’s drawing is loading into the editor\.';/,'Use this pose waits for an in-flight read');
  assert.match(workbench,/const edited=!StudioPoseEditor\.holds\(posePoints,poseCanvas,before\)/,'an edit made during the read wins over the late stored drawing');
  assert.match(workbench,/combineSwitchReason\(selected,target,referenceRecords\)/,'ordinary engine switches retain their representation guard');
  assert.doesNotMatch(workbench,/post\('\/api\/jobs'/,'the workbench submits no generation of its own');
  const html=fs.readFileSync(path.join(__dirname,'../app/static/index.html'),'utf8');
  assert.ok(html.indexOf('/static/pose-editor-core.js')>=0,'the page loads the geometry module');
  assert.ok(html.indexOf('/static/pose-editor-core.js')<html.indexOf('/static/studio-workbench.js'),'the geometry module loads before the workbench reads it');
});

console.log(count+' pose editor geometry checks passed.');
