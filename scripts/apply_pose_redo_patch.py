#!/usr/bin/env python3
"""One-shot guarded patch for the large no-build workbench; deleted after CI applies it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / 'app/static/studio-workbench.js'
BROWSER_TEST = ROOT / 'tests/pose_editor_handoff_browser.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


workbench = WORKBENCH.read_text(encoding='utf-8')
workbench = replace_once(
    workbench,
    '<div class="ux-pose-actions"><button type="button" id="uxPoseUnknown">Mark unknown</button><button type="button" id="uxPoseUndo">Undo</button><button type="button" id="uxPoseUse" class="primary" aria-describedby="uxPoseReason">Use this pose</button></div>',
    '<div class="ux-pose-actions"><button type="button" id="uxPoseUnknown">Mark unknown</button><button type="button" id="uxPoseUndo">Undo</button><button type="button" id="uxPoseRedo">Redo</button><button type="button" id="uxPoseUse" class="primary" aria-describedby="uxPoseReason">Use this pose</button></div>',
    'pose action buttons',
)
workbench = replace_once(
    workbench,
    "let posePoints=null,poseHome=null,poseCanvas={width:1024,height:1536},poseHistory=[],poseJoint=0,poseBusy=false,poseDrag=-1,poseSignature='',posePositionSignature='';",
    "let posePoints=null,poseHome=null,poseCanvas={width:1024,height:1536},poseTimeline=StudioPoseEditor.timeline(POSE_UNDO),poseJoint=0,poseBusy=false,poseDrag=-1,poseSignature='',posePositionSignature='';",
    'pose timeline state',
)
workbench = replace_once(
    workbench,
    "  // Undo carries the remembered positions with the drawing: otherwise restoring an unknown joint after an undo\n  // would put it back where the undone edit had left it (Codex review, PR #466).\n  function pushPose(){poseHistory.push(JSON.parse(JSON.stringify({points:posePoints,home:poseHome})));if(poseHistory.length>POSE_UNDO)poseHistory.shift();}",
    "  // Undo and redo carry remembered positions with the drawing, so restoring an unknown joint follows the\n  // reviewed geometry rather than a later edit. A new authored edit clears only the abandoned redo branch.\n  function pushPose(){poseTimeline.record(posePoints,poseHome);}",
    'history recorder',
)
workbench = replace_once(
    workbench,
    "    const reason=poseBlockedReason(),use=q('#uxPoseUse'),unknown=q('#uxPoseUnknown'),undo=q('#uxPoseUndo');",
    "    const reason=poseBlockedReason(),use=q('#uxPoseUse'),unknown=q('#uxPoseUnknown'),undo=q('#uxPoseUndo'),redo=q('#uxPoseRedo');",
    'action references',
)
workbench = replace_once(
    workbench,
    "    unknown.disabled=poseBusy||positionPending;undo.disabled=poseBusy||positionPending||!poseHistory.length;undo.title=poseHistory.length?'Steps back one change.':'Nothing to undo yet.';\n    if(poseBusy)unknown.title=undo.title='The drawing is being rendered.';",
    "    unknown.disabled=poseBusy||positionPending;\n    undo.disabled=poseBusy||positionPending||!poseTimeline.canUndo;redo.disabled=poseBusy||positionPending||!poseTimeline.canRedo;\n    undo.title=poseTimeline.canUndo?'Steps back one change.':'Nothing to undo yet.';redo.title=poseTimeline.canRedo?'Restores the change just stepped back.':'Nothing to redo yet.';\n    if(poseBusy)unknown.title=undo.title=redo.title='The drawing is being rendered.';",
    'action readiness',
)
workbench = replace_once(
    workbench,
    "    if(!posePoints){posePoints=StudioPoseEditor.fromPreset('standing',next);poseHome=StudioPoseEditor.fromPreset('standing',next);poseHistory=[];poseCanvas=next;}",
    "    if(!posePoints){posePoints=StudioPoseEditor.fromPreset('standing',next);poseHome=StudioPoseEditor.fromPreset('standing',next);poseTimeline.reset();poseCanvas=next;}",
    'timeline initialization',
)
workbench = replace_once(
    workbench,
    "      // The undo stack follows the canvas too, so stepping back after a size change cannot restore old-canvas pixels.\n      poseHistory=poseHistory.map(step=>({points:StudioPoseEditor.resize(step.points,poseCanvas,next),home:StudioPoseEditor.resize(step.home,poseCanvas,next)}));",
    "      // Both history directions follow the canvas, so undo or redo cannot restore old-canvas pixels.\n      poseTimeline.resize(poseCanvas,next);",
    'timeline resize',
)
workbench = replace_once(
    workbench,
    "  q('#uxPoseUndo').onclick=()=>{if(q('#uxPoseUndo').disabled||!poseHistory.length)return;const step=poseHistory.pop();poseHome=step.home;poseEdit(step.points,false);poseStatus('One change stepped back.');};",
    "  q('#uxPoseUndo').onclick=()=>{if(q('#uxPoseUndo').disabled)return;const step=poseTimeline.undo(posePoints,poseHome);if(!step)return;poseHome=step.home;poseEdit(step.points,false);poseStatus('One change stepped back. Redo restores it.');};\n  q('#uxPoseRedo').onclick=()=>{if(q('#uxPoseRedo').disabled)return;const step=poseTimeline.redo(posePoints,poseHome);if(!step)return;poseHome=step.home;poseEdit(step.points,false);poseStatus('One change restored.');};",
    'undo and redo handlers',
)
if 'poseHistory' in workbench:
    raise RuntimeError('legacy poseHistory owner remains after patch')
WORKBENCH.write_text(workbench, encoding='utf-8', newline='\n')

browser = BROWSER_TEST.read_text(encoding='utf-8')
browser = replace_once(
    browser,
    "    page.locator('#uxPoseUndo').click()\n    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == initial, 'Existing Undo restores both displayed coordinates')\n",
    "    page.locator('#uxPoseUndo').click()\n    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == initial, 'Undo restores both displayed coordinates')\n    undone = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')\n    page.locator('#uxPoseRedo').focus(); page.keyboard.press('ArrowRight')\n    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == undone, 'Arrow keys on Redo do not nudge the drawing')\n    page.locator('#uxPoseRedo').click()\n    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == ['0', '123.45'], 'Redo restores both displayed coordinates')\n    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == applied, 'Redo restores the exact drawing')\n    page.locator('#uxPoseUndo').click()\n    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == initial, 'Undo remains available after redo')\n",
    'browser redo coverage',
)
BROWSER_TEST.write_text(browser, encoding='utf-8', newline='\n')
