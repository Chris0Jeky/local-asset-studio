/* Tab-local drafts observe the existing Workspace metadata/receipt service. */
(() => {
  'use strict';
  const R=window.StudioReviewRecovery;
  if(!R)return;
  const fields=['id','title','notes','tags','favorite','review','trashed_at','metadata_revision'];
  let scope=null, offered=null, restoring=false, storageWarning='', unprotected=false;
  const shelf=document.createElement('section');shelf.id='assetReviewShelf';shelf.className='asset-review-recovery';shelf.hidden=true;
  $('#assetGrid').before(shelf);
  const panel=document.createElement('section');panel.id='assetReviewReload';panel.className='asset-review-recovery';panel.hidden=true;
  $('#assetTitle').closest('label').before(panel);
  const warning=document.createElement('p');warning.id='assetReviewStorage';warning.className='status error';warning.setAttribute('role','status');warning.setAttribute('aria-live','polite');panel.after(warning);
  const journal=()=>R.journal(window.sessionStorage); // Access can itself throw SecurityError.
  const workspace=()=>/^[0-9a-f]{32}$/.test(assetState.workspace_id||'')?assetState.workspace_id:null;
  const same=()=>scope!==null && scope===workspace();
  function fail(error){storageWarning='Reload recovery unavailable: '+error.message+' Keep a copy of your edits. Existing local records were not removed.';warning.textContent=storageWarning;}
  function envelope(operation=assetDetailPending){
    return {version:1,workspace:scope,asset:activeAsset.id,
      opened:Object.fromEntries(fields.map(k=>[k,k==='trashed_at'?activeAsset[k]??null:activeAsset[k]])),
      draft:assetDetailValues(),pending:operation?{body:operation.body,snapshot:operation.snapshot}:null};
  }
  function shelfRefresh(){
    if(!workspace()){shelf.hidden=true;return;}
    try{
      const records=journal().list(workspace());shelf.hidden=!records.length;
      shelf.innerHTML='<h3>Review recovery · this tab</h3><p>Local drafts and save identities survive reload in this tab. Closing the tab clears them. Nothing is restored or sent automatically.</p>'+records.map(r=>{
        const exists=assetState.assets.some(a=>a.id===r.asset);
        return '<div class="asset-review-entry"><b>'+esc(r.opened.title||r.asset)+'</b><span>'+ (r.pending?'Save unconfirmed':'Unsaved local draft')+'</span>'+
          (exists?'<button data-review-open="'+esc(r.asset)+'">Resume review</button>':'<span>Asset not in the loaded library</span>')+
          '<details><summary>Inspect local record</summary><pre>'+esc(JSON.stringify(r,null,2))+'</pre></details><button data-review-forget="'+esc(r.asset)+'">Discard local record</button></div>';
      }).join('');
    }catch(error){shelf.hidden=false;shelf.textContent='Review recovery could not be read. '+error.message;fail(error);}
  }
  function present(){
    panel.hidden=!offered;
    panel.innerHTML=offered?'<h3>A local review is available</h3><p>'+ (offered.pending?'It includes an unconfirmed save. Restoring will not retry it.':'Your unsaved draft was kept in this tab.')+'</p><div class="asset-detail-actions"><button data-review-restore>Restore for review</button><button data-review-discard>Discard local record</button></div><details><summary>Inspect local record</summary><pre>'+esc(JSON.stringify(offered,null,2))+'</pre></details>':'';
    panel.querySelectorAll('button').forEach(b=>b.disabled=restoring);
    assetDetailControls();
  }
  function changed(resolved=false){
    if(offered || !activeAsset || !scope || unprotected)return;
    if(!same()){fail(Error('The workspace changed; this editor must be reopened before any save.'));return;}
    try{
      if(assetDetailDirty() || assetDetailPending)journal().put(envelope(),{resolved});
      else journal().remove(scope,activeAsset.id,{resolved});
      warning.textContent='Local recovery kept in this tab. This is separate from saved server metadata.';storageWarning='';shelfRefresh();
    }catch(error){fail(error);}
  }
  function opened(){
    scope=workspace();offered=null;restoring=false;unprotected=false;storageWarning='';warning.textContent='';
    try{if(!scope)throw Error('Workspace identity is unavailable. Refresh the library to enable reload recovery.');offered=journal().get(scope,activeAsset.id);}
    catch(error){fail(error);}
    present();
    if(offered){
      assetDetailStatus('Saved metadata is shown below. Restore the local record to review its draft or unconfirmed save.');
      panel.querySelector('[data-review-restore]').focus();
    }
  }
  function closed(){
    // A user-approved nonpending close is a discard; page reload does not fire dialog.close.
    if(scope && activeAsset && !offered){
      if(assetDetailPending)changed();
      else try{journal().remove(scope,activeAsset.id);}catch(error){fail(error);}
    }
    scope=null;offered=null;restoring=false;present();shelfRefresh();
  }
  function beforeSend(operation){
    if(offered || restoring)return false;
    if(scope && !same()){fail(Error('The workspace changed; reopen this asset before saving.'));return false;}
    try{
      if(!scope)throw Error('Workspace identity is unavailable.');
      operation.command={...operation.command,workspace_id:scope};operation.body=JSON.stringify(operation.command);
      journal().put(envelope(operation));unprotected=false;
      warning.textContent='Exact save identity retained locally before sending. Newer typing remains separate.';storageWarning='';shelfRefresh();return true;
    }catch(error){
      fail(error);
      // A retained older command is never bypassed, even after a storage failure.
      let retained;try{retained=scope&&journal().get(scope,activeAsset.id);}catch{return false;}
      if(retained?.pending){assetDetailStatus('An older local save identity must be resolved before another save.',true);return false;}
      if(!window.confirm('Reload recovery could not be stored. Save without reload protection? Keep this tab open; the pending identity will otherwise be lost.'))return false;
      unprotected=true;warning.textContent='Saving without reload protection by your choice. Do not reload or close this tab until the save is confirmed.';return true;
    }
  }
  function recoveredSuccess(record,result){
    const before=assetDetailValues();Object.assign(activeAsset,result.applied);
    const acknowledged=metadataForm(activeAsset);
    // Only confirmed fields advance. Favorite/Trash never certify unsaved notes.
    for(const key of Object.keys(assetFormIds))if(Object.hasOwn(result.applied,key)){
      assetDetailBaseline[key]=acknowledged[key];
      if(before[key]===record.pending.snapshot[key])$('#'+assetFormIds[key]).value=acknowledged[key];
    }
    $('#assetFavorite').textContent=activeAsset.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=activeAsset.trashed_at?'Restore':'Move to Trash';
    assetDetailStatus(assetDetailDirty()?'Earlier save confirmed. Your newer edits remain unsaved.':'Earlier save confirmed. Nothing was generated.');
  }
  async function restore(){
    if(!offered || restoring || !same())return;
    const record=offered,id=activeAsset.id,epoch=assetDetailEpoch,controller=new AbortController();
    restoring=true;present();assetDetailStatus('Reading current metadata before restoring the local draft…');
    const timer=setTimeout(()=>controller.abort(),15000);
    try{
      const snapshot=await api('/api/workspace',{signal:controller.signal});
      if(!assetDetailContextCurrent(id,epoch) || offered!==record)return;
      if(snapshot.workspace_id!==scope)throw Error('Workspace identity changed. Local recovery was not applied to this workspace.');
      const current=await api('/api/assets/'+encodeURIComponent(id)+'/metadata',{signal:controller.signal});
      if(!assetDetailContextCurrent(id,epoch) || offered!==record)return;
      if(!validAssetMetadata(current) || current.id!==id)throw Error('Current asset metadata is unavailable.');
      Object.assign(activeAsset,record.opened);assetDetailBaseline=metadataForm(record.opened);
      for(const [key,control] of Object.entries(assetFormIds))$('#'+control).value=record.draft[key];
      assetDetailPending=record.pending?{id,epoch,command:JSON.parse(record.pending.body),body:record.pending.body,snapshot:record.pending.snapshot,
        success:result=>recoveredSuccess(record,result)}:null;
      assetDetailConflict=!record.pending && current.metadata_revision!==record.opened.metadata_revision?{current:[current]}:null;
      offered=null;renderAssetSaveRecovery();renderAssetConflict();
      // The existing conflict heading must not imply a rejected write on read-only restore.
      if(assetDetailConflict)$('#assetDetailConflict > p').textContent='Saved metadata changed while this local draft was away. Restoration made no write. Compare before saving.';
      $('#assetFavorite').textContent=activeAsset.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=activeAsset.trashed_at?'Restore':'Move to Trash';
      assetDetailStatus(record.pending?'Local draft and exact earlier save restored. Check save status first; no request was replayed.':assetDetailConflict?'Local draft restored with a newer saved revision. Compare before saving.':'Local draft restored. No server metadata was changed.');
    }catch(error){assetDetailStatus('Recovery not applied. '+error.message+' The local record is retained.',true);}
    finally{clearTimeout(timer);restoring=false;present();if(!offered){changed();$('#assetNotes').focus();}}
  }
  function forget(id){
    if(restoring || assetDetailBusy)return;
    try{
      const targetScope=workspace(),record=journal().get(targetScope,id);if(!record)return;
      if(!window.confirm(record.pending?'Discard this local draft and save identity? This does not cancel an unconfirmed server change. Copy the request ID before proceeding.':'Discard the local recovery draft? Saved server metadata is unchanged.'))return;
      journal().remove(targetScope,id,{resolved:true});
      if(offered?.asset===id){offered=null;present();$('#assetNotes').focus();}
      shelfRefresh();
    }catch(error){fail(error);}
  }
  document.addEventListener('click',e=>{
    const open=e.target.closest('[data-review-open]');if(open)openAsset(open.dataset.reviewOpen);
    if(e.target.closest('[data-review-restore]'))void restore();
    if(e.target.closest('[data-review-discard]'))forget(offered?.asset);
    const discard=e.target.closest('[data-review-forget]');if(discard)forget(discard.dataset.reviewForget);
  });
  assetReviewRecovery={opened,closed,changed,beforeSend,leavingBlocked:()=>restoring || !!offered,blocked:()=>restoring || !!offered || !!scope && !same(),refreshed:()=>{shelfRefresh();if(scope && !same())assetDetailControls();}};
  shelfRefresh();
})();
