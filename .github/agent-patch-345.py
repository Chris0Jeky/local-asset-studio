from pathlib import Path

path = Path('app/static/studio-workbench.js')
source = path.read_text(encoding='utf-8')

open_start = source.index('  function openHandoff(')
open_end_marker = "\n  q('#uxDestination').onchange=destinationDetails;"
open_end = source.index(open_end_marker, open_start)
handoff = source[open_start:open_end]

replacements = [
    ("if(epoch!=null&&epoch!==handoffEpoch)return;const request=++handoffEpoch;",
     "if(epoch!=null&&epoch!==handoffEpoch)return false;const request=++handoffEpoch;"),
    ("if(assetDetailsDirty()){warnUnsavedAsset();return;}if(!catalog){announce('Recipes are still loading.');return;}",
     "if(assetDetailsDirty()){warnUnsavedAsset();return false;}if(!catalog){announce('Recipes are still loading.');return false;}"),
    ("if(!a||a.trashed_at||a.media_type!=='image'){announce('Choose an available image from the Asset library.',true);return;}",
     "if(!a||a.trashed_at||a.media_type!=='image'){announce('Choose an available image from the Asset library.',true);return false;}"),
]
for old, new in replacements:
    if handoff.count(old) != 1:
        raise SystemExit(f'expected one handoff fragment, found {handoff.count(old)}: {old}')
    handoff = handoff.replace(old, new)

closing = '\n  }'
if not handoff.endswith(closing):
    raise SystemExit('openHandoff closing marker changed')
handoff = handoff[:-len(closing)] + '\n    return true;\n  }'
source = source[:open_start] + handoff + source[open_end:]

old_second = "    openHandoff(continuationState.source_asset_id,dest.id,undefined,intent);"
new_second = "    if(!openHandoff(continuationState.source_asset_id,dest.id,undefined,intent))pendingStyle=null;"
if source.count(old_second) != 1:
    raise SystemExit(f'expected one second-picture handoff call, found {source.count(old_second)}')
source = source.replace(old_second, new_second)

old_pull = "  async function pullIntoSlot(index,id){const result=await post('/api/assets/reference',{id});const previous=referenceRecords[index].parent_asset;Object.assign(referenceRecords[index],result,{missing:false});if(index===0&&StudioContinuation.sourceInput(selected.continuation_capability)!=='last_reference')uploaded=result.file;renderReferenceSlots();replaceParentAsset('reference',previous,id);draftDirty=true;saveDraft();syncCreate();}"
new_pull = """  async function pullIntoSlot(index,id,stamp=workbenchStamp()){
    try{
      const result=await post('/api/assets/reference',{id});
      if(stamp!==workbenchStamp())throw Error('The workbench changed while the picture was being copied. It was not applied.');
      const slot=referenceRecords[index];if(!slot)throw Error('The destination slot is no longer available.');
      const previous=slot.parent_asset;Object.assign(slot,result,{missing:false});
      if(index===0&&StudioContinuation.sourceInput(selected.continuation_capability)!=='last_reference')uploaded=result.file;
      renderReferenceSlots();replaceParentAsset('reference',previous,id);draftDirty=true;saveDraft();syncCreate();return true;
    }catch(error){announce('The second picture was not attached. '+error.message,true);return false;}
  }"""
if source.count(old_pull) != 1:
    raise SystemExit(f'expected one pullIntoSlot implementation, found {source.count(old_pull)}')
source = source.replace(old_pull, new_pull)
path.write_text(source, encoding='utf-8')
