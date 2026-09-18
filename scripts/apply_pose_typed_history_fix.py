#!/usr/bin/env python3
"""One-shot exact repair for typed pose edits; removed after CI applies it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "app/static/studio-workbench.js"
WORKFLOW = ROOT / ".github/workflows/pose-typed-history-fix.yml"
SELF = Path(__file__).resolve()

old = """  function applyPosePosition(){
    if(poseBusy||!posePoints?.[poseJoint])return;
    try{
      const point=StudioPoseEditor.positionInput(q('#uxPoseX').value,q('#uxPoseY').value,poseCanvas),next=StudioPoseEditor.move(posePoints,poseJoint,point.x,point.y,poseCanvas);
      if(JSON.stringify(StudioPoseEditor.serialize(next,poseCanvas))===JSON.stringify(StudioPoseEditor.serialize(posePoints,poseCanvas))){posePositionSignature='';syncReady();poseStatus('The joint is already at that position.');return;}
      pushPose();poseEdit(next);syncReady();poseStatus(StudioPoseEditor.LABELS[poseJoint]+' moved. Undo steps back this change.');
    }catch(error){
"""
new = """  function applyPosePosition(){
    if(poseBusy||!posePoints?.[poseJoint])return;
    try{
      const point=StudioPoseEditor.positionInput(q('#uxPoseX').value,q('#uxPoseY').value,poseCanvas);
      const current=StudioPoseEditor.serialize(posePoints,poseCanvas).keypoints[poseJoint],round=value=>Math.round(value*100)/100;
      if(current[0]===round(point.x)&&current[1]===round(point.y)){posePositionSignature='';syncReady();poseStatus('The joint is already at that position.');return;}
      pushPose();poseEdit(StudioPoseEditor.move(posePoints,poseJoint,point.x,point.y,poseCanvas));syncReady();poseStatus(StudioPoseEditor.LABELS[poseJoint]+' moved. Undo steps back this change.');
    }catch(error){
"""

text = WORKBENCH.read_text(encoding="utf-8")
count = text.count(old)
if count != 1:
    raise RuntimeError(f"typed-position handler: expected exactly one match, found {count}")
text = text.replace(old, new, 1)
WORKBENCH.write_text(text, encoding="utf-8", newline="\n")

# This bootstrap is an implementation transport, not a permanent product or CI surface.
SELF.unlink()
WORKFLOW.unlink()
