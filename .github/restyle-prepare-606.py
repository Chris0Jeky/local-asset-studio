from pathlib import Path
import hashlib

def blob(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

before={'app/static/references.js':'208a09b60d4d4184ad7bce1797a488bb4931600c','app/static/studio-workbench.js':'69cc013d52654de2bcd7274f98de20cd79eb6b59'}
for path,expected in before.items():
    assert blob(path)==expected, ('base mismatch',path)
p=Path('app/static/references.js');s=p.read_text()
marker='// The readiness model itself lives'
pos=s.index(marker)
s=s[:pos]+'''// Transient attachment intent belongs to the slot owner, not prompt/settings snapshots.
// Epoch changes invalidate structural edits; the per-record token also rejects an older
// upload/copy on the same unchanged slot. Tokens are never persisted as lineage or readiness.
const referenceAttachments=new WeakMap();
function beginReferenceAttachment(index){
  const slot=referenceRecords[index];
  if(!Number.isInteger(index)||index<0||!slot||!selected?.reference_slots?.[index])throw Error('The destination slot is no longer available.');
  const epoch=referenceEpoch,token={};let finished=false;
  referenceAttachments.set(slot,token);referencePending++;updateReady();$('#referenceSummary').textContent='Uploading and validating…';
  return {
    current:()=>!finished&&epoch===referenceEpoch&&referenceRecords[index]===slot&&referenceAttachments.get(slot)===token,
    finish(){if(finished)return;finished=true;if(epoch===referenceEpoch){referencePending--;renderReferenceSlots();}}
  };
}
async function attachReferenceAsset(index,id){
  const attachment=beginReferenceAttachment(index);
  try{
    const result=await post('/api/assets/reference',{id});
    if(!attachment.current())throw Error('The destination slot changed while the picture was being copied. It was not applied.');
    const slot=referenceRecords[index],previous=slot.parent_asset;Object.assign(slot,result,{missing:false});
    if(index===0&&StudioContinuation.sourceInput(selected.continuation_capability)!=='last_reference')uploaded=result.file;
    replaceParentAsset('reference',previous,id);return result;
  }finally{attachment.finish();}
}
''' +s[pos:]
a=s.index('async function uploadRoleFile(');b=s.index('\nasync function restoreReferenceSlots(',a)
s=s[:a]+'''async function uploadRoleFile(index,file){
  if(!file)return false;let attachment;
  try{
    attachment=beginReferenceAttachment(index);
    if(file.size>20*1024*1024)throw Error('Reference image exceeds 20 MiB');
    const result=await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file});
    if(!attachment.current())return false;
    const previous=referenceRecords[index].parent_asset;Object.assign(referenceRecords[index],{parent_asset:null},result,{missing:false});releaseParentAsset(previous);return true;
  }catch(e){if(!attachment||attachment.current()){message(e.message,true);$('#referenceSummary').textContent=e.message;}return false;}
  finally{attachment?.finish();}
}''' + s[b:]
p.write_text(s)
p=Path('app/static/studio-workbench.js');s=p.read_text()
s=s.replace("const epoch=referenceEpoch;await originalUploadRoleFile(...args);if(epoch===referenceEpoch){draftDirty=true;saveDraft();}","const epoch=referenceEpoch,applied=await originalUploadRoleFile(...args);if(applied&&epoch===referenceEpoch){draftDirty=true;saveDraft();}return applied;")
old="""    dismissSecondPicture();q('#reference').value='';pendingStyle=item;syncReady();
    if(!openHandoff(continuationState.source_asset_id,dest.id,undefined,intent))pendingStyle=null;"""
new="""    // Keep the choice and native File until Prepare commits (selectPreset clears both).
    // A refused opening, failed context read or cancelled modal must not consume the picture.
    pendingStyle=null;
    try{if(openHandoff(continuationState.source_asset_id,dest.id,undefined,intent))pendingStyle=item;}
    catch(error){announce('Could not open the handoff. '+error.message,true);}
    syncReady();"""
assert old in s;s=s.replace(old,new)
a=s.index('  async function pullIntoSlot(');b=s.index("\n  q('#uxSourceAssets').onclick=",a)
s=s[:a]+'''  async function pullIntoSlot(index,id){
    try{await attachReferenceAsset(index,id);draftDirty=true;saveDraft();syncCreate();return true;}
    catch(error){announce('The second picture was not attached. '+error.message,true);return false;}
  }'''+s[b:]
a=s.index("      const stamp=workbenchStamp(),result=await post('/api/assets/reference'",s.index("  q('#uxSourceAssets').onclick="));b=s.index('\n      const filled=',a)
s=s[:a]+'''      if(selected.reference_slots?.length&&slot!=='lastReference')await attachReferenceAsset(Number(slot),id);
      else{const stamp=workbenchStamp(),result=await post('/api/assets/reference',{id});if(stamp!==workbenchStamp())throw Error('The workbench changed during attachment. Reopen the picker.');if(slot==='lastReference'){lastUploaded=result.file;q('#lastReference').value='';pendingInputs.delete('lastReference');}else{uploaded=result.file;q('#reference').value='';pendingInputs.delete('reference');}replaceParentAsset(slot==='lastReference'?'lastReference':'reference',null,id);}
      draftDirty=true;saveDraft();syncCreate();'''+s[b:]
p.write_text(s)
after={'app/static/references.js':'0d56526b356b46817856d9c49d50c6dc09c78549','app/static/studio-workbench.js':'00f05bbfab8da726b4b971eb53d4426dc672a24e'}
for path,expected in after.items():
    assert blob(path)==expected, ('result mismatch',path)
print('Prepared exact locally tested source blobs:',after)
