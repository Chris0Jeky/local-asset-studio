// An open collection editor owns a draft, not saved metadata or command receipts.
let collectionSession=null, collectionEpoch=0;
function collectionValues(){return {name:$('#collectionName').value,description:$('#collectionDescription').value};}
function collectionDirty(s=collectionSession){return !!s && JSON.stringify(collectionValues())!==JSON.stringify(s.baseline);}
function collectionStatus(text,error=false){const el=$('#collectionStatus');el.textContent=text;el.classList.toggle('error',error);}
function collectionCurrent(s){return collectionSession===s && s.epoch===collectionEpoch && $('#collectionDialog').open;}
function collectionControls(){
  const s=collectionSession;
  $('#saveCollection').disabled=!s || s.busy || s.uncertain || !collectionDirty(s);
  $('#saveCollection').textContent=s?.busy?'Saving…':'Save collection';
  $('#removeCollection').hidden=!s?.id;$('#removeCollection').disabled=!!(s?.busy||s?.uncertain);
  $('#showSavedCollection').hidden=!s?.id;$('#showSavedCollection').disabled=!!(s?.busy||s?.uncertain);
}
function collectionCanLeave(){
  const s=collectionSession;
  if(s?.busy){collectionStatus('A collection change is still pending. Keep this dialog open until its outcome is known.');return false;}
  if(s?.uncertain)return window.confirm('This change may already be saved. Closing discards these local edits, not the server change. Inspect the collection list before trying again. Close this editor?');
  return !collectionDirty(s)||window.confirm('Discard unsaved collection changes? Cancel keeps the name and description here.');
}
function closeCollection(){if(collectionCanLeave())$('#collectionDialog').close();}
function openCollection(id=null){
  const col=id?assetState.collections.find(c=>c.id===id):null;
  if(id&&!col){if($('#collectionDialog').open)collectionStatus('This collection is no longer in the loaded Workspace. Your current edits were kept.',true);else assetMessage('Collection unavailable. Refresh the library to check it.',true);return false;}
  if($('#collectionDialog').open){if(collectionSession?.id===id)return true;if(!collectionCanLeave())return false;}
  const s={id,scope:assetState.workspace_id,epoch:++collectionEpoch,baseline:{name:col?.name||'',description:col?.description||''},busy:false,uncertain:false};
  collectionSession=s;collectionEditing=id;
  $('#collectionDialogTitle').textContent=id?'Edit collection':'New collection';
  $('#collectionName').value=s.baseline.name;$('#collectionDescription').value=s.baseline.description;
  collectionStatus('Collections organize existing assets. Saving here does not move files or add the current selection.');collectionControls();
  if(!$('#collectionDialog').open)$('#collectionDialog').showModal();$('#collectionName').focus();return true;
}
async function saveCollectionChange(action){
  const s=collectionSession;
  if(!s||!collectionCurrent(s)||s.busy||s.uncertain)return;
  if(!/^[0-9a-f]{32}$/.test(s.scope||'')||assetState.workspace_id!==s.scope){collectionStatus('The Workspace changed or its identity is unavailable. Keep these edits and return to the original Workspace before saving.',true);return;}
  if(action!=='delete'&&!collectionDirty(s))return;
  const snapshot=collectionValues(),saved={name:snapshot.name.trim(),description:snapshot.description.trim()};
  if(action!=='delete'&&(!saved.name||snapshot.name.length>100||snapshot.description.length>1000)){collectionStatus('Enter a collection name (up to 100 characters) and a description of up to 1000 characters.',true);return;}
  if(action==='delete'){
    if(!s.id)return;
    const text='Remove collection “'+s.baseline.name+'”? This removes its grouping, including membership links, but keeps all original assets and recipes.'+(collectionDirty(s)?' Unsaved name and description edits will be discarded.':'');
    if(!window.confirm(text))return;
  }
  const payload={action:action==='delete'?'delete':s.id?'rename':'create',id:s.id,workspace_id:s.scope,...(action==='delete'?{}:saved)};
  s.busy=true;collectionControls();
  // Pause destructive writes; ordinary saves preserve any newer typing separately.
  $('#collectionName').disabled=$('#collectionDescription').disabled=action==='delete';
  collectionStatus(action==='delete'?'Removing this collection; originals stay in the library…':'Saving the clicked snapshot. Any further edits will remain unsaved.');
  const controller=new AbortController();let timer;
  try{
    const request=api('/api/collections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
    const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{const e=Error('The request timed out.');e.name='AbortError';reject(e);controller.abort();},15000);});
    const result=await Promise.race([request,deadline]);
    if(!collectionCurrent(s))return;
    if(!result||result.workspace_id!==s.scope||!/^[0-9a-f]{32}$/.test(result.id||'')||(s.id&&result.id!==s.id)||(action==='delete'?result.deleted!==true:result.name!==saved.name||result.description!==saved.description))throw Error('The response did not confirm the expected collection change.');
    if(assetState.workspace_id!==s.scope){s.uncertain=true;collectionStatus('A change was confirmed in the original Workspace, but this page now shows a different Workspace. Return there to inspect it; no automatic repeat was sent.',true);return;}
    if(action==='delete'){
      s.baseline=collectionValues();$('#collectionDialog').close();
      if(assetScope==='collection:'+s.id)assetScope='all';
      assetMessage('Collection removed. Its original assets and recipes remain in the library.');
    }else{
      const unchanged=JSON.stringify(collectionValues())===JSON.stringify(snapshot);
      s.id=result.id;collectionEditing=result.id;s.baseline=saved;
      if(unchanged){$('#collectionName').value=saved.name;$('#collectionDescription').value=saved.description;}
      $('#collectionDialogTitle').textContent='Edit collection';
      collectionStatus(collectionDirty(s)?'Snapshot saved. Your newer collection edits are still unsaved.':'Collection saved. Close to keep browsing, or show this collection. Your asset selection has not changed.');
    }
    void refreshAssets(true);
  }catch(e){
    if(collectionCurrent(s)){
      // Only the existing server's pre-commit validation/scope refusals are definite.
      s.uncertain=![400,403,409].includes(e.status);
      collectionStatus(s.uncertain?'Change not confirmed. '+(e.name==='AbortError'?'The request timed out.':e.message)+' Your edits remain here. It may already be saved; no retry was sent. Close and inspect the collection list before trying again.':'Change refused: '+e.message+' Your edits remain here.',true);
    }
  }finally{
    clearTimeout(timer);s.busy=false;
    if(collectionCurrent(s)){$('#collectionName').disabled=$('#collectionDescription').disabled=false;collectionControls();}
  }
}
$('#newCollection').onclick=()=>openCollection();
$('#renameCollection').onclick=()=>openCollection(assetScope.slice(11));
$('#cancelCollection').onclick=closeCollection;
$('#collectionDialog').addEventListener('cancel',e=>{e.preventDefault();closeCollection();});
$('#collectionDialog').addEventListener('close',()=>{
  if($('#collectionDialog').open)return;collectionEpoch++;collectionSession=null;collectionEditing=null;
  $('#collectionName').disabled=$('#collectionDescription').disabled=false;
});
for(const id of ['collectionName','collectionDescription'])$('#'+id).addEventListener('input',()=>{
  collectionControls();const s=collectionSession;
  if(!s||s.uncertain)return;
  collectionStatus(s.busy?'Saving the earlier snapshot; your newer edits remain unsaved.':collectionDirty(s)?'Unsaved collection changes.':'No unsaved collection changes.');
});
$('#collectionForm').onsubmit=e=>{e.preventDefault();return saveCollectionChange('save');};
$('#removeCollection').onclick=()=>saveCollectionChange('delete');
$('#deleteCollection').onclick=()=>{const id=assetScope.startsWith('collection:')?assetScope.slice(11):null;if(id&&openCollection(id))return saveCollectionChange('delete');};
$('#showSavedCollection').onclick=()=>{
  const s=collectionSession;if(!s?.id||!collectionCanLeave())return;
  if(assetState.workspace_id!==s.scope||!assetState.collections.some(c=>c.id===s.id)){collectionStatus('The saved collection is not in the loaded list yet. Refresh the library and inspect it; no save was repeated.',true);void refreshAssets(true);return;}
  $('#collectionDialog').close();setAssetScope('collection:'+s.id);
};
