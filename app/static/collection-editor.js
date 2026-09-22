// Editable drafts and immutable dispatch intents are separate, per-tab recovery evidence.
let collectionSession=null, collectionEpoch=0;
function collectionValues(){return {name:$('#collectionName').value,description:$('#collectionDescription').value};}
// Canonical storage sorts object keys; equality belongs to fields, not insertion order.
function collectionSameValues(a,b){return a.name===b.name&&a.description===b.description;}
function collectionDirty(s=collectionSession){return !!s && !collectionSameValues(collectionValues(),s.baseline);}
function collectionStatus(text,error=false){const el=$('#collectionStatus');el.textContent=text;el.classList.toggle('error',error);}
function collectionCurrent(s){return collectionSession===s && s.epoch===collectionEpoch && $('#collectionDialog').open;}
function collectionScope(s){return /^[0-9a-f]{32}$/.test(s.scope||'')&&assetState.workspace_id===s.scope;}
function collectionDraft(s,value=collectionValues()){return {id:s.id,revision:s.id?s.revision:null,baseline:{...s.baseline},values:{...value},updated_at:Date.now()};}
function collectionControls(){
  const s=collectionSession,blocked=!s||s.busy||s.pending||s.restoreRequired||s.storageError||s.stale;
  $('#saveCollection').disabled=!!blocked||!collectionDirty(s);
  $('#saveCollection').textContent=s?.busy?(s.activity==='inspect'?'Inspecting…':'Saving…'):'Save collection';
  $('#removeCollection').hidden=!s?.id;$('#removeCollection').disabled=!!blocked;
  $('#showSavedCollection').hidden=!s?.id;$('#showSavedCollection').disabled=!!(s?.busy||s?.pending||s?.restoreRequired);
  $('#restoreCollectionDraft').hidden=!s?.restoreRequired;$('#restoreCollectionDraft').disabled=!!s?.busy;
  $('#inspectCollectionCommand').hidden=!s?.pending;$('#retryCollectionCommand').hidden=!s?.pending;
  for(const id of ['inspectCollectionCommand','retryCollectionCommand'])$('#'+id).disabled=!!(s?.busy||s?.restoreRequired||s?.storageError);
  $('#discardCollectionDraft').hidden=!s||!(s.recovery||s.pending||s.storageError||collectionDirty(s));$('#discardCollectionDraft').disabled=!!s?.busy;
  $('#collectionRecoveredTargets').disabled=!!s?.busy;
  if(!s?.busy)$('#collectionName').disabled=$('#collectionDescription').disabled=!!s?.restoreRequired;
}
function collectionCompare(s,current=s.observed){
  s.observed=current;
  s.stale=!!s.id&&(!current||current.revision!==s.revision||current.name!==s.baseline.name||current.description!==s.baseline.description);
  const label=row=>row?'revision '+row.revision+' · '+row.name+'\n'+(row.description||''):'missing or deleted';
  const local=s.restoreRequired?s.recovery?.draft.values:collectionValues();
  $('#collectionComparison').textContent=(s.confirmed?'Historical receipt · '+label(s.confirmed)+'\n\n':'')+
    (s.stale?'Opened baseline · '+label({...s.baseline,revision:s.revision})+'\nSaved now · '+label(current)+'\n\nYour local draft · '+(local?.name||'')+'\n'+(local?.description||'')+'\nNo rebase or overwrite was performed. Discard local recovery and reopen the saved collection to use its current revision.':'');
  $('#collectionComparison').hidden=!$('#collectionComparison').textContent;
}
function collectionPersist(s){
  if(!s||s.restoreRequired||s.removed||s.discarded)return true;
  try{
    if(collectionDirty(s)||s.pending)s.recovery=s.journal.keep(collectionDraft(s),s.pending);
    else {if(s.journal.get(s.id))s.journal.discard(s.id);s.recovery=null;}
    s.storageError=false;return true;
  }catch(e){s.storageError=true;collectionStatus('Local recovery could not be verified: '+e.message+' No new collection write was sent. Your visible input is kept; copy it before leaving if browser storage is unavailable.',true);return false;}
}
function collectionCanLeave(){
  const s=collectionSession;
  if(s?.busy){collectionStatus('A collection operation is pending. Keep this dialog open until its outcome is known.');return false;}
  if(s?.storageError)return window.confirm('Local recovery is unavailable. Copy your visible text before closing. Closing does not cancel or undo any server work. Close this editor?');
  if(s?.pending)return window.confirm('This change may already be saved. Keep its exact command and your local draft for Restore / Inspect on reopening? Closing does not cancel a server change.');
  return s?.discarded||!collectionDirty(s)||s?.restoreRequired||window.confirm('Keep this unsaved collection draft locally and close? Cancel keeps the editor open. Discard local draft is a separate action.');
}
function closeCollection(){if(collectionCanLeave()){collectionPersist(collectionSession);$('#collectionDialog').close();}}
function collectionRecoveryList(s){
  const select=$('#collectionRecoveredTargets');select.replaceChildren();
  try{for(const entry of s.journal.list().sort((a,b)=>b.draft.updated_at-a.draft.updated_at)){
    const option=document.createElement('option');option.value=entry.draft.id??'';option.textContent=(entry.pending?'Unconfirmed · ':'Local draft · ')+(entry.draft.values.name||'New collection');select.append(option);
  }}catch(e){/* The visible storage refusal owns recovery; never parse an untrusted fallback. */}
  select.value=s.id??'';select.hidden=!s.recovery;
}
function openCollection(id=null){
  const col=id?assetState.collections.find(c=>c.id===id):null;
  if($('#collectionDialog').open){if(collectionSession?.id===id)return true;if(!collectionCanLeave())return false;}
  let journal,recovery=null,failure;
  try{journal=new StudioCollectionRecovery.Journal(sessionStorage,assetState.workspace_id);recovery=journal.get(id);}catch(e){failure=e;}
  if(id&&!col&&!recovery){if($('#collectionDialog').open)collectionStatus('This collection is no longer in the loaded Workspace. Your current edits were kept.',true);else assetMessage('Collection unavailable. Refresh the library to check it.',true);return false;}
  if($('#collectionDialog').open)collectionPersist(collectionSession);
  const s={id,revision:col?.revision,scope:assetState.workspace_id,epoch:++collectionEpoch,baseline:{name:col?.name||'',description:col?.description||''},
    busy:false,uncertain:!!recovery?.pending,pending:recovery?.pending??null,journal,recovery,restoreRequired:!!recovery,storageError:!!failure,observed:col??null,stale:false};
  collectionSession=s;collectionEditing=id;
  // A queued close event from an older session cannot own these controls.
  $('#collectionName').disabled=$('#collectionDescription').disabled=false;
  $('#collectionDialogTitle').textContent=id?'Edit collection':'New collection';
  $('#collectionName').value=s.baseline.name;$('#collectionDescription').value=s.baseline.description;
  collectionStatus(failure?'Local recovery is unavailable: '+failure.message+' No collection write can be sent. Your input will remain visible.':recovery?'A local '+(s.pending?'unconfirmed command and draft':'draft')+' is retained in this tab for this Workspace. Restore it explicitly, or discard only the local evidence.':'Collections organize existing assets. Saving does not move files or add the current selection.',!!failure);
  collectionCompare(s);collectionRecoveryList(s);collectionControls();
  if(!$('#collectionDialog').open)$('#collectionDialog').showModal();$(s.restoreRequired?'#restoreCollectionDraft':'#collectionName').focus();return true;
}
function restoreCollectionDraft(){
  const s=collectionSession;if(!s||!collectionCurrent(s)||s.busy||!collectionScope(s))return;
  try{
    const entry=s.journal.get(s.id);if(!entry)throw Error('The retained draft is no longer available');
    s.recovery=entry;s.id=entry.draft.id;s.revision=entry.draft.revision;s.baseline={...entry.draft.baseline};s.pending=entry.pending;s.uncertain=!!entry.pending;
    s.restoreRequired=false;s.storageError=false;collectionEditing=s.id;
    $('#collectionName').value=entry.draft.values.name;$('#collectionDescription').value=entry.draft.values.description;
    collectionCompare(s,s.id?assetState.collections.find(c=>c.id===s.id)??null:null);
    collectionStatus(s.pending?'Unconfirmed command restored. Inspect status or explicitly retry its exact bytes; newer typing cannot change that command.':s.stale?'Local draft restored against a changed or deleted saved collection. Both viewpoints are shown below; no rebase or write was performed.':'Local draft restored. It has not been submitted.');
  }catch(e){s.storageError=true;collectionStatus('Local recovery could not be restored: '+e.message,true);}
  collectionControls();if(!s.storageError&&!s.restoreRequired)$('#collectionName').focus();
}
function discardCollectionDraft(){
  const s=collectionSession;if(!s||!collectionCurrent(s)||s.busy||!collectionScope(s))return;
  const warning=s.storageError?'Discard all collection recovery for this Workspace in this tab? Corrupt evidence may include unconfirmed commands.':'Discard this collection’s local draft and retained command?';
  if(!window.confirm(warning+' This does not cancel, undo, or determine the outcome of any server work. Original assets are untouched.'))return;
  try{
    if(s.storageError){s.journal=s.journal||new StudioCollectionRecovery.Journal(sessionStorage,s.scope);s.journal.reset();}
    else s.journal.discard(s.id);
    s.pending=null;s.uncertain=false;s.recovery=null;s.restoreRequired=false;s.storageError=false;s.discarded=true;
    collectionRecoveryList(s);
    // Do not replace visible input or silently advance a stale source revision.
    collectionStatus('Local recovery discarded. This does not cancel or undo server work. Visible text remains here; close without editing to leave it discarded. Refresh and inspect the saved collection before sending another command.');
    collectionControls();
  }catch(e){s.storageError=true;collectionStatus('Local recovery discard could not be verified: '+e.message,true);collectionControls();}
}
function collectionDefiniteRefusal(error){
  const expected={collection_invalid_command:[400,403],collection_precondition_required:[428],collection_revision_conflict:[409],collection_not_found:[404],
    collection_workspace_conflict:[409],collection_revision_limit:[409],collection_asset_revision_limit:[409],collection_journal_full:[507]};
  return error.data?.format==='studio.collection-error/v1'&&error.data.generation_submitted===false&&expected[error.data.code]?.includes(error.status);
}
async function collectionRequest(s,pending,inspect=false){
  s.busy=true;s.activity=inspect?'inspect':'save';collectionControls();
  const command=JSON.parse(pending.body),snapshot=pending.clicked_values;
  $('#collectionName').disabled=$('#collectionDescription').disabled=!inspect&&command.action==='delete';
  collectionStatus(inspect?'Inspecting the retained request; no collection mutation will be sent…':'Sending the retained snapshot. Any newer typing remains a separate local draft.');
  const controller=new AbortController();let timer;
  try{
    const request=inspect?api('/api/collections/commands/'+pending.request_id+'?workspace_id='+s.scope,{signal:controller.signal}):
      api('/api/collections',{method:'POST',headers:{'Content-Type':'application/json'},body:pending.body,signal:controller.signal});
    const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{const e=Error('The request timed out.');e.name='AbortError';reject(e);controller.abort();},15000);});
    const reply=await Promise.race([request,deadline]);
    if(!collectionCurrent(s))return;
    if(!collectionScope(s)){collectionStatus('The page now shows a different Workspace. The original command remains retained; return there to inspect it. No replacement was sent.',true);return;}
    if(inspect&&reply?.format==='studio.collection-result/v1'&&reply.workspace_id===s.scope&&reply.request_id===pending.request_id&&reply.status==='unknown'&&reply.receipt===null&&reply.receipt_json===null&&reply.receipt_sha256===null&&reply.generation_submitted===false){
      s.uncertain=true;collectionStatus('Status is unknown, not cancelled. The original command is still locked. An explicit retry reuses exactly the retained request ID and bytes.');return;
    }
    const receipt=await StudioCollectionRecovery.verifyReceipt(reply,pending);
    if(!collectionCurrent(s))return;
    if(!collectionScope(s)){collectionStatus('Workspace changed during receipt verification. Return to the original Workspace to inspect the retained command.',true);return;}
    const result=receipt.result,visible=collectionValues();
    const unchanged=collectionSameValues(visible,snapshot);
    const nextValues=unchanged?{name:result.name,description:result.description}:visible;
    const nextDraft=result.deleted?null:{id:result.id,revision:result.revision,baseline:{name:result.name,description:result.description},values:nextValues,updated_at:Date.now()};
    s.journal.resolve(s.id,pending,nextDraft&&!collectionSameValues(nextDraft.values,nextDraft.baseline)?nextDraft:null);
    // Only a verified historical receipt advances the baseline; current is an observation.
    const recovery=nextDraft?s.journal.get(result.id):null;
    s.pending=null;s.uncertain=false;s.recovery=recovery;s.confirmed=result;
    if(result.deleted){
      s.removed=true;s.baseline=visible;$('#collectionDialog').close();
      if(assetScope==='collection:'+s.id)assetScope='all';
      assetMessage('Collection removed. Its original assets and recipes remain in the library.');
    }else{
      s.id=result.id;s.revision=result.revision;collectionEditing=result.id;s.baseline={name:result.name,description:result.description};
      if(unchanged){$('#collectionName').value=result.name;$('#collectionDescription').value=result.description;}
      $('#collectionDialogTitle').textContent='Edit collection';
      const current=reply.current;
      collectionCompare(s,current&&current.id===s.id&&Number.isSafeInteger(current.revision)&&typeof current.name==='string'&&typeof current.description==='string'?current:null);
      collectionStatus(s.stale?'Historical commit confirmed; saved metadata has changed or is unavailable. Your local text is kept. Inspect both versions below before any new edit.':collectionDirty(s)?'Snapshot saved. Your newer collection edits are still unsaved.':'Collection saved. Your asset selection has not changed.');
    }
    void refreshAssets(true);
  }catch(e){
    if(collectionCurrent(s)){
      let definite=!inspect&&collectionDefiniteRefusal(e);
      if(definite){try{s.journal.resolve(s.id,pending,collectionDraft(s));const recovery=s.journal.get(s.id);s.pending=null;s.recovery=recovery;}catch(storageError){definite=false;s.storageError=true;e=storageError;}}
      s.uncertain=!definite;
      if(definite&&e.data?.code==='collection_revision_conflict')collectionCompare(s,e.data.current??null);
      collectionStatus(definite?'Change refused: '+e.message+' Your edits remain here.':'Change not confirmed. '+e.message+' Your draft and exact command remain retained. It may already be saved; no automatic retry was sent. Request '+pending.request_id+'.',true);
    }
  }finally{
    clearTimeout(timer);s.busy=false;
    if(collectionCurrent(s)){$('#collectionName').disabled=$('#collectionDescription').disabled=false;collectionControls();}
  }
}
async function saveCollectionChange(action){
  const s=collectionSession;
  if(!s||!collectionCurrent(s)||s.busy||s.pending||s.restoreRequired||s.stale)return;
  if(!collectionScope(s)){collectionStatus('The Workspace changed or its identity is unavailable. Keep these edits and return to the original Workspace before saving.',true);return;}
  if(action!=='delete'&&!collectionDirty(s))return;
  const snapshot=collectionValues(),saved={name:snapshot.name.trim(),description:snapshot.description.trim()};
  if(action!=='delete'&&(!saved.name||snapshot.name.length>100||snapshot.description.length>1000)){collectionStatus('Enter a collection name (up to 100 characters) and a description of up to 1000 characters.',true);return;}
  if(s.id&&(!Number.isSafeInteger(s.revision)||s.revision<1||s.revision>=Number.MAX_SAFE_INTEGER)){collectionStatus('A valid writable collection revision is unavailable. Keep these edits, then refresh and inspect the saved collection before reopening it.',true);return;}
  if(s.storageError){collectionStatus('Local recovery is unavailable. No new collection write was sent. Your visible input is kept.',true);return;}
  if(action==='delete'&&(!s.id||!window.confirm('Remove collection “'+s.baseline.name+'”? This removes membership links, but keeps all original assets and recipes. Unsaved name and description edits will be discarded only after confirmation.')))return;
  if(typeof crypto.randomUUID!=='function'){collectionStatus('A secure request identity is unavailable. No save was sent.',true);return;}
  try{
    const payload={format:'studio.collection-command/v1',request_id:crypto.randomUUID(),workspace_id:s.scope,action:action==='delete'?'delete':s.id?'rename':'create',
      ...(s.id?{id:s.id,expected_revision:s.revision}:{}),...(action==='delete'?{}:saved)};
    const pending=StudioCollectionRecovery.pending(payload,Date.now(),snapshot);
    s.recovery=s.journal.keep(collectionDraft(s),pending);s.pending=pending;s.uncertain=true;s.discarded=false;
  }catch(e){s.storageError=true;collectionStatus('Local recovery could not be verified: '+e.message+' No collection write was sent. Your input is kept.',true);collectionControls();return;}
  return collectionRequest(s,s.pending);
}
async function recoverCollectionCommand(inspect){
  const s=collectionSession;if(!s||!collectionCurrent(s)||s.busy||!s.pending||s.restoreRequired||s.storageError)return;
  if(!collectionScope(s)){collectionStatus('Return to the original Workspace before inspecting or retrying this retained command.',true);return;}
  if(!inspect&&!window.confirm('Retry this exact command once, using the same request ID and bytes? Newer text will not be sent. Unknown status is not proof that the first attempt did not commit.'))return;
  try{
    const retained=s.journal.get(s.id);
    if(!retained?.pending||StudioCollectionRecovery.canonical(retained.pending)!==StudioCollectionRecovery.canonical(s.pending))throw Error('The retained pending command changed');
    if(!collectionPersist(s))return;
  }catch(e){s.storageError=true;collectionStatus('Recovery could not be verified: '+e.message+' No request was sent.',true);collectionControls();return;}
  return collectionRequest(s,s.pending,inspect);
}
$('#newCollection').onclick=()=>openCollection();
$('#renameCollection').onclick=()=>openCollection(assetScope.slice(11));
$('#recoverCollections').onclick=()=>{
  try{const entries=new StudioCollectionRecovery.Journal(sessionStorage,assetState.workspace_id).list().sort((a,b)=>b.draft.updated_at-a.draft.updated_at);
    if(entries.length)return openCollection(entries[0].draft.id);assetMessage('No collection recovery is stored for this Workspace in this tab.');
  }catch(e){openCollection();}
};
$('#collectionRecoveredTargets').onchange=e=>openCollection(e.target.value||null);
$('#restoreCollectionDraft').onclick=restoreCollectionDraft;
$('#inspectCollectionCommand').onclick=()=>recoverCollectionCommand(true);
$('#retryCollectionCommand').onclick=()=>recoverCollectionCommand(false);
$('#discardCollectionDraft').onclick=discardCollectionDraft;
$('#cancelCollection').onclick=closeCollection;
$('#collectionDialog').addEventListener('cancel',e=>{e.preventDefault();closeCollection();});
$('#collectionDialog').addEventListener('close',()=>{
  if($('#collectionDialog').open)return;collectionEpoch++;collectionSession=null;collectionEditing=null;
  $('#collectionName').disabled=$('#collectionDescription').disabled=false;
});
for(const id of ['collectionName','collectionDescription'])$('#'+id).addEventListener('input',()=>{
  const s=collectionSession;if(!s)return;
  if(s.restoreRequired){collectionStatus('Restore or discard the retained local draft before editing it. The retained command has not changed.');collectionControls();return;}
  s.discarded=false;const persisted=collectionPersist(s);collectionCompare(s);collectionControls();
  if(!persisted||s.pending)return;
  collectionStatus(s.stale?'Your local draft is retained separately from changed saved metadata.':collectionDirty(s)?'Unsaved collection changes retained locally in this tab.':'No unsaved collection changes.');
});
$('#collectionForm').onsubmit=e=>{e.preventDefault();return saveCollectionChange('save');};
$('#removeCollection').onclick=()=>saveCollectionChange('delete');
$('#deleteCollection').onclick=()=>{const id=assetScope.startsWith('collection:')?assetScope.slice(11):null;if(id&&openCollection(id))return saveCollectionChange('delete');};
$('#showSavedCollection').onclick=()=>{
  const s=collectionSession;if(!s?.id||!collectionCanLeave())return;
  if(!collectionScope(s)||!assetState.collections.some(c=>c.id===s.id)){collectionStatus('The saved collection is not in the loaded list yet. Refresh the library and inspect it; no save was repeated.',true);void refreshAssets(true);return;}
  collectionPersist(s);$('#collectionDialog').close();setAssetScope('collection:'+s.id);
};
