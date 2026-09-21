'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const P=require('../app/static/pose-editor-core.js');
const CANVAS={width:1024,height:1536};
let count=0;const test=(name,fn)=>{fn();count++;console.log('PASS '+name);};

function drawing(x=100){
  const points=P.fromPreset('standing',CANVAS);
  points[4]={x,y:200};
  return points;
}

test('timeline records immutable pose and home snapshots for undo and redo',()=>{
  assert.equal(typeof P.timeline,'function');
  const timeline=P.timeline(60),home=drawing(90),before=drawing(100),after=drawing(200);
  timeline.record(before,home);
  before[4].x=999;home[4].x=888;
  const undo=timeline.undo(after,drawing(190));
  assert.deepEqual(undo.points[4],{x:100,y:200});
  assert.deepEqual(undo.home[4],{x:90,y:200});
  assert.equal(timeline.canUndo,false);assert.equal(timeline.canRedo,true);
  const redo=timeline.redo(undo.points,undo.home);
  assert.deepEqual(redo.points[4],{x:200,y:200});
  assert.deepEqual(redo.home[4],{x:190,y:200});
  assert.equal(timeline.canUndo,true);assert.equal(timeline.canRedo,false);
});

test('a real edit after undo clears only the redo branch',()=>{
  const timeline=P.timeline(60),home=drawing(80),a=drawing(100),b=drawing(200),c=drawing(300);
  timeline.record(a,home);timeline.record(b,home);
  const restored=timeline.undo(c,home);
  assert.deepEqual(restored.points[4],b[4]);assert.equal(timeline.canRedo,true);
  timeline.record(restored.points,restored.home);
  P.move(restored.points,4,250,200,CANVAS);
  assert.equal(timeline.canRedo,false,'a real branch edit must discard the stale future');
  assert.equal(timeline.canUndo,true,'the current branch remains undoable');
});

test('the workbench record path preserves redo across a clamped no-op',()=>{
  const timeline=P.timeline(60),home=drawing(100),before=drawing(100),after=drawing(200);
  timeline.record(before,home);
  const restored=timeline.undo(after,drawing(200));
  assert.equal(timeline.canRedo,true);
  timeline.record(restored.points,restored.home);
  const unchanged=P.move(restored.points,4,restored.points[4].x,restored.points[4].y,CANVAS);
  assert.equal(timeline.canRedo,true,'an unchanged move must not discard redo');
  assert.equal(timeline.canUndo,false,'a no-op must not add a duplicate undo entry');
  P.move(unchanged,4,101,200,CANVAS);
  assert.equal(timeline.canRedo,false,'the first later drag movement discards the abandoned future');
  assert.equal(timeline.canUndo,true,'the original pre-drag snapshot remains undoable');
});

test('a rounded typed no-op preserves redo and adds no undo entry',()=>{
  const timeline=P.timeline(60),before=drawing(100),home=drawing(100),after=drawing(300);
  timeline.record(before,home);
  const restored=timeline.undo(after,drawing(300));
  assert.equal(timeline.canRedo,true);
  timeline.record(restored.points,restored.home);
  const unchanged=P.move(restored.points,4,restored.points[4].x,restored.points[4].y,CANVAS);
  assert.equal(timeline.canRedo,true,'the exact no-op leaves the redo branch pending');
  const refused=P.move(unchanged,4,unchanged[4].x+0.001,unchanged[4].y,CANVAS);
  assert.deepEqual(P.serialize(refused,CANVAS),P.serialize(unchanged,CANVAS),
    'the workbench refuses a typed edit whose serialized pose is unchanged');
  assert.equal(timeline.canRedo,true,'a refused sub-centipixel transition must not destroy redo');
  assert.equal(timeline.canUndo,false,'a refused transition must not create an undo entry');
  const redone=timeline.redo(unchanged,restored.home);
  assert.deepEqual(redone.points[4],after[4]);
});

test('a precomputed edit survives cleanup of an earlier no-op',()=>{
  const timeline=P.timeline(60),home=drawing(100),before=drawing(100);
  timeline.record(before,home);
  const unchanged=P.move(before,4,100,200,CANVAS);
  assert.equal(timeline.canUndo,false,'the no-op remains pending without adding history');
  const typed=P.move(unchanged,4,175,200,CANVAS);
  timeline.record(unchanged,home);
  assert.equal(timeline.canUndo,true,
    'cleaning up the earlier pending no-op must not delete the already-published typed transition');
  const restored=timeline.undo(typed,drawing(175));
  assert.deepEqual(restored.points[4],{x:100,y:200});
});

test('undo and redo preserve unknown-joint homes and resize both stacks',()=>{
  const timeline=P.timeline(60),home=drawing(123),known=drawing(123),unknown=P.setUnknown(known,4),small={width:512,height:768};
  timeline.record(known,home);
  let restored=timeline.undo(unknown,home);
  assert.deepEqual(restored.points[4],known[4]);
  assert.deepEqual(restored.home[4],home[4]);
  timeline.resize(CANVAS,small);
  restored=timeline.redo(P.resize(restored.points,CANVAS,small),P.resize(restored.home,CANVAS,small));
  assert.equal(restored.points[4],null);
  assert.deepEqual(restored.home[4],{x:home[4].x/2,y:home[4].y/2});
});

test('timeline enforces a bounded history and safe no-op edges',()=>{
  const timeline=P.timeline(2),home=drawing(50);
  assert.equal(timeline.undo(drawing(1),home),null);assert.equal(timeline.redo(drawing(1),home),null);
  timeline.record(drawing(1),home);timeline.record(drawing(2),home);timeline.record(drawing(3),home);
  assert.equal(timeline.pastCount,2);
  assert.deepEqual(timeline.undo(drawing(4),home).points[4],drawing(3)[4]);
  assert.deepEqual(timeline.undo(drawing(3),home).points[4],drawing(2)[4]);
  assert.equal(timeline.undo(drawing(2),home),null,'the oldest entry beyond the cap is gone');
  timeline.reset();assert.equal(timeline.canUndo,false);assert.equal(timeline.canRedo,false);
  for(const bad of [0,-1,1.5,Infinity,true,'2'])assert.throws(()=>P.timeline(bad));
});

test('a precomputed typed transition enables undo and clears an abandoned redo branch',()=>{
  const timeline=P.timeline(60),before=drawing(100),home=drawing(100);
  const typed=P.move(before,4,200,200,CANVAS);
  timeline.record(before,home);
  assert.equal(timeline.canUndo,true,'record must retain a move that was validated before history recording');
  assert.equal(timeline.canRedo,false);
  const restored=timeline.undo(typed,drawing(200));
  assert.deepEqual(restored.points[4],before[4]);
  assert.equal(timeline.canRedo,true);
  const branch=P.move(restored.points,4,150,200,CANVAS);
  timeline.record(restored.points,restored.home);
  assert.equal(timeline.canUndo,true,'the precomputed branch edit must remain undoable');
  assert.equal(timeline.canRedo,false,'the precomputed branch edit must clear stale redo');
  assert.deepEqual(branch[4],{x:150,y:200});
});

test('the Combine editor exposes and wires redo without adding a generation path',()=>{
  const workbench=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
  assert.match(workbench,/id="uxPoseRedo">Redo<\/button>/);
  assert.match(workbench,/poseTimeline=StudioPoseEditor\.timeline\(POSE_UNDO\)/);
  assert.match(workbench,/poseTimeline\.resize\(poseCanvas,next\)/);
  assert.match(workbench,/poseTimeline\.record\(posePoints,poseHome\)/);
  assert.match(workbench,/poseTimeline\.undo\(posePoints,poseHome\)/);
  assert.match(workbench,/poseTimeline\.redo\(posePoints,poseHome\)/);
  assert.match(workbench,/redo\.disabled=.*!poseTimeline\.canRedo/);
  const redoHandler=workbench.match(/q\('#uxPoseRedo'\)\.onclick=\(\)=>\{[^\n]+\};/);
  assert.ok(redoHandler,'the workbench must own one explicit redo handler');
  assert.doesNotMatch(redoHandler[0],/\b(?:post|fetch|usePose)\s*\(/,
    'redo remains a local drawing operation');
});

console.log(count+' pose editor redo contracts passed.');
