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

// The panel itself needs a DOM this sandbox does not have (canvas, pointer capture, dialogs); what is pinned
// here is the wiring around the pure module, the way tests/frontend_handoffs.cjs pins the picker's.
test('the workbench sends the drawing to the guide endpoint and to no generation route',()=>{
  const workbench=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(workbench,/request=StudioPoseEditor\.serialize\(posePoints,poseCanvas\)/,'the request freezes the intended drawing');
  assert.match(workbench,/post\('\/api\/pose\/render',request\)/,'Use this pose renders the frozen guide request');
  assert.match(workbench,/drawing!==JSON\.stringify\(StudioPoseEditor\.serialize\(posePoints,poseCanvas\)\)/,'changed geometry invalidates the reply');
  assert.match(workbench,/POSE_RECIPE='combine-klein-9b-skeleton'/,'the drawing belongs to the proved drawn-skeleton recipe');
  assert.match(workbench,/switchCombineEngine\(POSE_RECIPE,result\)/,'explicit replacement uses the checked new guide through the shared switch path');
  assert.match(workbench,/StudioPoseEditor\.guideResponse\(response,request\)/,'response validation precedes attachment');
  assert.match(workbench,/combineSwitchReason\(selected,target,referenceRecords\)/,'ordinary engine switches retain their representation guard');
  assert.doesNotMatch(workbench,/post\('\/api\/jobs'/,'the workbench submits no generation of its own');
  const html=fs.readFileSync(path.join(__dirname,'../app/static/index.html'),'utf8');
  assert.ok(html.indexOf('/static/pose-editor-core.js')>=0,'the page loads the geometry module');
  assert.ok(html.indexOf('/static/pose-editor-core.js')<html.indexOf('/static/studio-workbench.js'),'the geometry module loads before the workbench reads it');
});

console.log(count+' pose editor geometry checks passed.');
