// Thumbnail rendering version; keep in step with THUMB_VERSION in app/asset_thumbs.py (tests/test_asset_thumbs.py pins both).
const ASSET_THUMB_VERSION = 1;
let assetState = {assets:[], collections:[]}, assetScope = 'all', assetSelection = new Set(), activeAsset = null, collectionEditing = null;
let assetSignature = '', assetRefreshing = false, assetWorkspaceEpoch = 0, assetObservedWorkspace;
// The tab journal retains drafts and exact commands; Workspace owns saved metadata.
let assetDetailEpoch = 0, assetDetailBaseline = null, assetDetailBusy = false, assetDetailDiscarding = false, assetDiagnosticRequest = 0;
let assetDetailPending = null, assetDetailConflict = null, assetLibraryPending = null, assetLibraryBusy = false;
// Async completions own one request, not whichever editor or Workspace is visible later.
let assetDetailRequest = null, assetLibraryRequest = null;
const assetFormIds = {title:'assetTitle',tags:'assetTags',review:'assetReview',notes:'assetNotes'};
const assetRecovery = StudioAssetRecovery.create(()=>sessionStorage);
let assetRetainedDetail = null, assetRecoveryError = '', assetRecoveryLoadError = '', assetRetainedSelection = null;
// Queue, grouping and reason chips are projections over the same saved review states; the server schema is unchanged.
let assetGroupMode = 'none', assetSearchTimer = null, assetQueue = null, assetBulkReviewBusy = false;
const assetGroupModes = ['recipe','day','run'], assetGroupStorageKey = 'studio.assets.group';
// Source is a view preference like grouping: an asset with a run label (set by API callers, never by Create) is an agent run (#939).
// Until the operator chooses, the library shows Mine once any labelled asset exists; with none, every source is shown.
const assetSourceModes = ['mine','agent','all'], assetSourceStorageKey = 'studio.assets.source';
let assetSourceMode = null;
function assetIsAgentRun(asset){return typeof asset?.run_label==='string' && asset.run_label!=='';}
function assetSource(){return !assetState.assets.some(assetIsAgentRun)?'all':assetSourceModes.includes(assetSourceMode)?assetSourceMode:'mine';}
function assetSourceFilter(list, source=assetSource()){return source==='all'?list:list.filter(a=>assetIsAgentRun(a)===(source==='agent'));}
// A title still equal to the registered default ("<recipe> · N") says nothing; the prompt excerpt does.
function assetDefaultTitle(asset){return asset.title===(asset.preset_name||'Untitled')+' · '+(Number(asset.output_index)+1);}
function assetSubtitle(asset){return typeof asset.prompt_excerpt==='string' && asset.prompt_excerpt && assetDefaultTitle(asset)?asset.prompt_excerpt:'';}
const assetReviewLabels = {unreviewed:'Unreviewed',selected:'Keeper',needs_work:'Needs work',rejected:'Rejected'};
const assetReviewShortcuts = {k:'selected',w:'needs_work',x:'rejected'};
const assetReasonTags = ['hands','face','style off','composition','anatomy','artifacts','crop'];
function recoveryScopeMessage(scope) {
  if(!StudioAssetRecovery.workspace(scope))return 'This retained record has no verified Workspace identity. Its text is available for inspection, but it cannot safely be restored or retried here. Inspect or copy its text before discarding the local record.';
  if(!StudioAssetRecovery.workspace(assetState.workspace_id))return 'Workspace identity is unavailable. Refresh the library before using this recovery.';
  return scope!==assetState.workspace_id?'This recovery belongs to a different Workspace. Return to that Workspace, or inspect and discard the local record. Recovery is paused.':'';
}
function requireAssetScope(scope){const problem=recoveryScopeMessage(scope);if(problem)throw Error(problem);}
// Gallery handoffs and ordinary refreshes both render the observed Workspace.
function observeAssetWorkspaceIdentity() {
  if(assetObservedWorkspace!==assetState.workspace_id){assetObservedWorkspace=assetState.workspace_id;assetWorkspaceEpoch++;}
}
function assetReceiptURL(command){return '/api/assets/commands/'+command.request_id+'?workspace_id='+encodeURIComponent(command.workspace_id);}

function rememberAssetDetails() {
  if(assetRecoveryLoadError)throw Error(assetRecoveryLoadError);
  if(!activeAsset || !assetDetailBaseline)return;
  if(!StudioAssetRecovery.workspace(activeAsset.workspace_id))throw Error('Workspace identity is unavailable. Keep a copy of this draft before leaving.');
  if(assetRetainedDetail && assetRetainedDetail.workspace_id!==activeAsset.workspace_id)throw Error('A retained draft belongs to a different Workspace. It has not been replaced.');
  if(!assetDetailDirty() && !assetDetailPending && !assetDetailConflict){assetRecovery.clear('detail');assetRetainedDetail=null;return;}
  const metadata=Object.fromEntries(['id','workspace_id','metadata_revision','title','notes','tags','review','favorite','trashed_at'].map(k=>[k,activeAsset[k]]));
  const operation=assetDetailPending?Object.fromEntries(['command','body','kind','snapshot'].map(k=>[k,assetDetailPending[k]])):null;
  assetRetainedDetail=assetRecovery.write('detail',{version:2,workspace_id:activeAsset.workspace_id,id:activeAsset.id,metadata,baseline:assetDetailBaseline,draft:assetDetailValues(),operation,conflict:assetDetailConflict});
}
function retainAssetDraft() {
  try{rememberAssetDetails();assetRecoveryError='';return true;}
  catch(error){assetRecoveryError=error.message;assetDetailStatus(error.message,true);return false;}
  finally{renderLibraryRecovery();}
}
function metadataForm(asset) { return {title:asset.title||'',tags:(asset.tags||[]).join(', '),review:asset.review||'unreviewed',notes:asset.notes||''}; }
function validAssetMetadata(value) {
  return value && typeof value.id==='string' && Number.isSafeInteger(value.metadata_revision) && value.metadata_revision>=0 &&
    typeof value.title==='string' && typeof value.notes==='string' && Array.isArray(value.tags) && value.tags.every(t=>typeof t==='string') &&
    typeof value.favorite==='boolean' && ['unreviewed','selected','needs_work','rejected'].includes(value.review) &&
    (value.trashed_at==null || (typeof value.trashed_at==='number' && Number.isFinite(value.trashed_at)));
}
// Registered titles may exceed the 200-character edit limit (REGISTERED_TITLE_MAX in app/workspace.py).
const assetRegisteredTitleMax=1024;
// Only a complete, matching POST conflict may release the pending command for
// explicit comparison. A GET failure or malformed observation is not a refusal
// receipt. Keep foreign/extra fields out of the retained conflict projection.
function assetRevisionConflict(error,command) {
  const data=error?.data,id=command.ids[0];
  const exactly=(value,ids)=>Array.isArray(value) && value.length===ids.length && value.every((v,i)=>v===ids[i]);
  if(error.status!==409 || !data || data.code!=='asset_revision_conflict' || command.ids.length!==1 ||
     data.request_id!==command.request_id || data.workspace_id!==command.workspace_id ||
     !exactly(data.conflict_ids,[id]) || !exactly(data.missing_ids,[]) || !Array.isArray(data.current) || data.current.length!==1)return null;
  const row=data.current[0],fields=['id','workspace_id','metadata_revision','title','notes','tags','review','favorite','trashed_at'];
  const text=(value,max)=>typeof value==='string' && value.length<=max*2 && [...value].length<=max;
  if(!validAssetMetadata(row) || !fields.every(k=>Object.hasOwn(row,k)) || row.id!==id || row.workspace_id!==command.workspace_id ||
     row.metadata_revision<=command.expected_revisions[id] || !text(row.title,assetRegisteredTitleMax) || !text(row.notes,8000) ||
     row.tags.length>30 || row.tags.some(tag=>!text(tag,60)))return null;
  const metadata=Object.fromEntries(fields.map(k=>[k,k==='tags'?[...row.tags]:row[k]]));
  return {code:data.code,workspace_id:data.workspace_id,request_id:data.request_id,conflict_ids:[id],missing_ids:[],current:[metadata]};
}
function assetCommand(payload, records, workspaceId=assetState.workspace_id) {
  requireAssetScope(workspaceId);
  const expected_revisions={};
  for(const id of payload.ids){
    const record=records.find(a=>a.id===id);
    if(!record || !Number.isSafeInteger(record.metadata_revision) || record.metadata_revision<0)throw Error('Reload the asset library before saving: its metadata revision is unavailable.');
    if(record.workspace_id && record.workspace_id!==workspaceId)throw Error('Asset metadata belongs to a different Workspace; refresh the library.');
    expected_revisions[id]=record.metadata_revision;
  }
  const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
  return {...payload,workspace_id:workspaceId,expected_revisions,request_id:Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('')};
}
function validateAssetReceipt(result, command) {
  if(result?.workspace_id!==command.workspace_id)throw Error('The save receipt belongs to a different Workspace. Your recovery is retained.');
  if(result?.status!=='applied' || result.request_id!==command.request_id || result.action!==command.action ||
     JSON.stringify(result.updated)!==JSON.stringify(command.ids) ||
     JSON.stringify(Object.keys(result.revisions||{}).sort())!==JSON.stringify([...command.ids].sort()) ||
     command.ids.some(id=>result.revisions[id]!==command.expected_revisions[id]+1))throw Error('The server did not return a matching save receipt.');
  const applied=result.applied, keys=command.action==='edit'?['title','notes','tags','favorite','review'].filter(k=>Object.hasOwn(command,k)):
    ['trash','restore'].includes(command.action)?['trashed_at']:['collection_id'];
  if(!applied || JSON.stringify(Object.keys(applied).sort())!==JSON.stringify(keys.sort()) || keys.some(k=>{
    if(k==='trashed_at')return command.action==='restore'?applied[k]!==null:typeof applied[k]!=='number' || !Number.isFinite(applied[k]);
    if(k==='tags')return !Array.isArray(applied[k]) || applied[k].some(t=>typeof t!=='string');
    return typeof applied[k]!==typeof command[k];
  }))throw Error('The save receipt contains invalid applied metadata.');
  if(!Array.isArray(result.current) || result.current.length>10 ||
     result.current.some(m=>!validAssetMetadata(m) || m.workspace_id!==command.workspace_id || !command.ids.includes(m.id)) ||
     new Set(result.current.map(m=>m.id)).size!==result.current.length)throw Error('The receipt observation is invalid; the exact save remains retained.');
  return result;
}
function assetDetailValues() {
  return {title:$('#assetTitle').value, tags:$('#assetTags').value, review:$('#assetReview').value, notes:$('#assetNotes').value};
}
function assetDetailDirty() { return !!assetDetailBaseline && JSON.stringify(assetDetailValues())!==JSON.stringify(assetDetailBaseline); }
function assetDetailStatus(text, error=false) {
  let status=$('#assetDetailStatus');
  if(!status){status=document.createElement('p');status.id='assetDetailStatus';status.className='muted';status.setAttribute('role','status');status.setAttribute('aria-live','polite');$('#saveAssetDetails').parentElement.before(status);}
  status.textContent=text;status.classList.toggle('error',error);
}
function assetDetailControls() {
  for(const id of ['saveAssetDetails','assetFavorite','assetTrash'])$('#'+id).disabled=assetDetailBusy || !!assetDetailConflict || (id!=='saveAssetDetails' && !!assetDetailPending);
  $('#saveAssetDetails').textContent=assetDetailBusy?'Saving…':assetDetailPending?'Confirm earlier save':'Save details';
  for(const id of ['assetTitle','assetTags','assetReview','assetNotes'])$('#'+id).disabled=assetDetailBusy && assetDetailDiscarding;
}
function assetDetailCanLeave() {
  if(assetDetailBusy){assetDetailStatus('A save is still pending. Your edits remain here until its outcome is known.');return false;}
  if(assetDetailPending || assetDetailConflict){if(!retainAssetDraft())return false;return window.confirm('Close this editor and retain its draft and save recovery in this tab? Reopen it from the library to continue.');}
  return !assetDetailDirty() || window.confirm('Discard unsaved changes to this asset? Cancel keeps your edits here.');
}
function closeAssetDetails() { if(assetDetailCanLeave())$('#assetDialog').close(); }
function assetDetailContextCurrent(id,epoch) { return $('#assetDialog').open && activeAsset?.id===id && assetDetailEpoch===epoch; }
// Replace only the recovery view. Return focus only when this render removes the
// focused recovery control; late results must never steal focus from newer typing.
function renderAssetRecoveryPanel(panel,html,hidden,selectors,fallback) {
  const focused=document.activeElement;
  const selector=focused && panel.contains?.(focused)?selectors.find(value=>focused.matches(value)):null;
  panel.hidden=hidden;
  if(panel.innerHTML!==html)panel.innerHTML=html;
  if(selector && (hidden || !focused.isConnected)){
    const target=!hidden && panel.querySelector(selector);
    (target||fallback)?.focus();
  }
}
function renderAssetSaveRecovery() {
  const panel=$('#assetDetailRecovery');
  const html=assetDetailPending?'<p>The earlier save is unconfirmed. Check its receipt or retry that exact request; newer typing is not sent.</p><code>'+esc(assetDetailPending.command.request_id)+'</code><div class="asset-detail-actions"><button data-asset-save-check>Check save status</button><button data-asset-save-retry>Retry exact save</button></div>':'';
  const fallback=assetDetailConflict?$('#assetDetailConflict').querySelector?.('[data-asset-rebase]')||$('#assetNotes'):$('#saveAssetDetails');
  renderAssetRecoveryPanel(panel,html,!assetDetailPending,['[data-asset-save-check]','[data-asset-save-retry]'],$('#assetDialog').open?fallback:null);
}
function renderAssetConflict() {
  const panel=$('#assetDetailConflict');panel.hidden=!assetDetailConflict;
  if(!assetDetailConflict){panel.innerHTML='';return;}
  const current=assetDetailConflict.current?.find(a=>a.id===activeAsset.id),draft=assetDetailValues();
  const valid=validAssetMetadata(current) && current.workspace_id===activeAsset.workspace_id;
  const remote=valid?metadataForm(current):null;
  const fields=remote?Object.keys(assetFormIds).filter(k=>draft[k]!==assetDetailBaseline[k] || remote[k]!==assetDetailBaseline[k]).map(k=>{
    const both=draft[k]!==assetDetailBaseline[k] && remote[k]!==assetDetailBaseline[k] && draft[k]!==remote[k];
    return '<div class="asset-conflict-field"><h4>'+esc(k)+(both?' · Both changed':'')+'</h4><div><b>Your draft</b><pre>'+esc(draft[k])+'</pre></div><div><b>Saved elsewhere</b><pre>'+esc(remote[k])+'</pre></div><details><summary>Value when opened</summary><pre>'+esc(assetDetailBaseline[k])+'</pre></details></div>';
  }).join(''):'';
  panel.innerHTML='<h3>This asset changed elsewhere</h3><p>'+(assetDetailConflict.confirmed_request_id?'The earlier save is confirmed, but newer saved metadata also exists. Review both versions before another save.':'Nothing in your save was applied. Your draft is still here.')+'</p>'+fields+
    (valid?'<p>Saved revision '+current.metadata_revision+' · '+(current.favorite?'Favorite':'Not favorited')+' · '+(current.trashed_at?'In Trash':'Not in Trash')+'</p><div class="asset-detail-actions"><button data-asset-rebase>Keep my edits for review</button><button data-asset-current>Use saved snapshot</button></div><small>Neither choice saves. Review the result, then Save details. Favorite and Trash are never replayed.</small>':'<p>The asset or its current revision is unavailable. Keep a copy of your draft and refresh the library.</p>');
}
function resolveAssetConflict(keepEdits) {
  if(assetDetailBusy || !assetDetailConflict)return;
  const current=assetDetailConflict.current?.find(a=>a.id===activeAsset.id);
  if(!validAssetMetadata(current) || current.workspace_id!==activeAsset.workspace_id)return;
  try{requireAssetScope(activeAsset.workspace_id);}catch(error){assetDetailStatus(error.message,true);return;}
  const local=assetDetailValues(),remote=metadataForm(current),previous=assetDetailBaseline;
  for(const [key,id] of Object.entries(assetFormIds))$('#'+id).value=keepEdits && local[key]!==previous[key]?local[key]:remote[key];
  for(const key of [...Object.keys(assetFormIds),'metadata_revision','favorite','trashed_at'])activeAsset[key]=current[key];
  assetDetailBaseline=remote;assetDetailConflict=null;renderAssetConflict();assetDetailControls();
  $('#assetFavorite').textContent=activeAsset.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=activeAsset.trashed_at?'Restore':'Move to Trash';
  assetDetailStatus(keepEdits?'Your edits are rebased for review, not saved. Check the fields, then Save details.':'Saved snapshot loaded. Nothing was written.');
  retainAssetDraft();
  $('#saveAssetDetails').focus();
}
async function performAssetSave(operation, observe=false) {
  if(assetDetailBusy || assetDetailPending!==operation || !assetDetailContextCurrent(operation.id,operation.epoch))return;
  try{requireAssetScope(operation.command.workspace_id);}catch(error){assetDetailStatus(error.message,true);return;}
  if(!retainAssetDraft())return;
  const {id,epoch,command,body}=operation,controller=new AbortController();
  const request={},workspaceEpoch=assetWorkspaceEpoch;
  assetDetailRequest=request;
  const ownsRequest=()=>assetDetailRequest===request;
  const ownsEditor=()=>assetDetailContextCurrent(id,epoch) && assetDetailPending===operation && activeAsset.workspace_id===command.workspace_id;
  const current=()=>ownsRequest() && ownsEditor() && assetState.workspace_id===command.workspace_id && assetWorkspaceEpoch===workspaceEpoch;
  assetDetailBusy=true;assetDetailDiscarding=['trash','restore'].includes(command.action);assetDetailControls();
  assetDetailStatus(observe?'Checking the earlier save receipt…':'Saving this snapshot… Newer typing stays in your draft.');
  const timer=setTimeout(()=>controller.abort(),15000);
  try {
    const result=await (observe?api(assetReceiptURL(command),{signal:controller.signal}):assetRecovery.dispatch('detail',operation,()=>api('/api/assets/update',{method:'POST',headers:{'Content-Type':'application/json'},body,signal:controller.signal}),()=>current() && assetDetailPending===operation && assetState.workspace_id===command.workspace_id && !controller.signal.aborted));
    if(!current())return;
    if(result?.workspace_id!==command.workspace_id)throw Error('The response belongs to a different Workspace; the original recovery is retained.');
    if(observe && result?.status==='unknown' && result.request_id===command.request_id){assetDetailStatus('Save still not confirmed. No receipt exists yet; the earlier request may still complete. No retry was sent.',true);return;}
    validateAssetReceipt(result,command);
    applyAssetSaveReceipt(operation,result);
    syncAssetAfterSave(operation,result);
  } catch(error) {
    if(!current())return;
    const conflict=!observe && assetRevisionConflict(error,command);
    if(error.data?.code==='asset_workspace_conflict'){
      assetDetailStatus('The server is using a different Workspace. No changes were applied there. The exact save is retained for the original Workspace.',true);
    } else if(conflict){
      assetDetailPending=null;assetDetailConflict=conflict;renderAssetConflict();assetDetailStatus('Conflict: this asset changed elsewhere. Compare the saved values with your draft before saving again.',true);
    } else if(error.data?.code==='asset_revision_conflict'){
      assetDetailStatus('Conflict reply could not be verified for this save. The exact command and your draft remain retained. Check its receipt, inspect lifecycle, or explicitly discard local recovery before a different save. No comparison was loaded.',true);
    } else if(!observe && error.status>=400 && error.status<500){
      // A refusal describes this attempt, not the outcome of an earlier lost response.
      assetDetailStatus('This attempt was refused. '+error.message+' The exact command and your draft remain retained. Check its receipt, or close and explicitly discard local recovery before a different save.',true);
    } else {
      assetDetailStatus('Save not confirmed. '+(error.name==='AbortError'?'The request timed out.':error.message)+' Your edits remain here. No automatic retry was sent.',true);
    }
  } finally {
    clearTimeout(timer);
    if(ownsRequest()){
      assetDetailRequest=null;assetDetailBusy=false;assetDetailDiscarding=false;
      // A confirmed result clears Pending before finally; retain the same editor's
      // newer typing, but never let a stale completion touch a replacement view.
      if(!$('#assetDialog').open)assetDetailControls();
      else if(assetDetailContextCurrent(id,epoch) && activeAsset.workspace_id===command.workspace_id &&
         assetState.workspace_id===command.workspace_id && assetWorkspaceEpoch===workspaceEpoch &&
         (!assetDetailPending || assetDetailPending===operation)){
        assetDetailControls();renderAssetSaveRecovery();retainAssetDraft();
      }else if(ownsEditor()){
        assetDetailControls();renderAssetSaveRecovery();assetDetailStatus('The Workspace changed while this request was pending. The original recovery is retained; return to its Workspace and check status explicitly.',true);
      }
    }
  }
}
// A confirmed single save updates the loaded record in place. A whole workspace refetch is not evidence of anything more.
function syncAssetAfterSave(operation,result) {
  const record=assetState.assets.find(a=>a.id===operation.id),revision=result.revisions[operation.id];
  if(!record || record.workspace_id!==operation.command.workspace_id || record.metadata_revision!==operation.command.expected_revisions[operation.id])return void refreshAssets(true);
  Object.assign(record,result.applied,{metadata_revision:revision});
  if(operation.kind==='trash')renderAssets();else updateAssetCard(record.id);
}
function applyAssetSaveReceipt(operation,result) {
  const unchanged=JSON.stringify(assetDetailValues())===JSON.stringify(operation.snapshot);
  const revision=result.revisions[operation.id];
  const observations=[...result.current];
  const library=assetState.assets.find(a=>a.id===operation.id);
  if(library && library.workspace_id===operation.command.workspace_id)observations.push(library);
  const latest=observations.filter(a=>a.id===operation.id && a.workspace_id===operation.command.workspace_id)
    .sort((a,b)=>b.metadata_revision-a.metadata_revision)[0];
  const observed=result.current.find(a=>a.id===operation.id);
  // A receipt confirms one historical mutation, not the latest metadata or the whole form.
  Object.assign(activeAsset,result.applied,{metadata_revision:revision});
  if(operation.kind==='details') {
    const applied=metadataForm(activeAsset);
    for(const key of Object.keys(assetFormIds))if(Object.hasOwn(result.applied,key))assetDetailBaseline[key]=applied[key];
    if(unchanged)for(const [key,id] of Object.entries(assetFormIds))if(Object.hasOwn(result.applied,key))$('#'+id).value=assetDetailBaseline[key];
  }
  const changed=!observed || observed.metadata_revision<revision || (latest && latest.metadata_revision>revision);
  assetDetailConflict=changed?{code:'asset_revision_conflict',workspace_id:operation.command.workspace_id,
    current:observed && latest?[latest]:[],confirmed_request_id:operation.command.request_id}:null;
  assetDetailPending=null;
  try {
    if(operation.kind==='trash' && unchanged && !changed){assetRecovery.clear('detail');assetRetainedDetail=null;}
    else rememberAssetDetails();
  }catch(error){assetDetailPending=operation;throw error;}
  $('#assetFavorite').textContent=activeAsset.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=activeAsset.trashed_at?'Restore':'Move to Trash';
  renderAssetConflict();
  if(changed)assetDetailStatus('The earlier save is confirmed. Current saved metadata differs or is unavailable; review it alongside your retained draft.',true);
  else if(operation.kind==='trash'){
    const text=operation.command.action==='trash'?'Moved to Trash. Restore it at any time.':'Asset restored.';
    if(unchanged){assetDetailBaseline=null;$('#assetDialog').close();assetMessage(text);}
    else assetDetailStatus(text+(assetDetailDirty()?' Your newer edits are still unsaved.':' Your draft remains open.'));
  }else assetDetailStatus(assetDetailDirty()?'Snapshot saved. Your newer edits are still unsaved.':'Details saved. Continue with this asset whenever you are ready.');
  renderLibraryRecovery();
}
// Receipt retries preserve immutable request bytes. They never become generation retries.
async function writeAssetDetails(payload, kind) {
  if(assetDetailBusy || assetDetailConflict || !activeAsset || !$('#assetDialog').open)return;
  if(assetDetailPending)return performAssetSave(assetDetailPending);
  try {
    const command=assetCommand({...payload,ids:[activeAsset.id]},[activeAsset],activeAsset.workspace_id);
    if(assetRecoveryLoadError)throw Error(assetRecoveryLoadError);
    assetDetailPending={id:activeAsset.id,epoch:assetDetailEpoch,command,body:JSON.stringify(command),kind,snapshot:assetDetailValues()};
    await performAssetSave(assetDetailPending);
  } catch(error){assetDetailStatus(error.message,true);}
}
async function checkAssetSave(){if(assetDetailPending)return performAssetSave(assetDetailPending,true);}
for(const id of ['assetTitle','assetTags','assetReview','assetNotes']) {
  const changed=()=>{if(id==='assetTags')renderAssetReasons();if(!retainAssetDraft())return;if(assetDetailConflict){renderAssetConflict();return;}assetDetailStatus(assetDetailBusy?'Saving the earlier snapshot. Any newer edits remain unsaved.':assetDetailPending?'The earlier save is unconfirmed. Newer edits remain local.':assetDetailDirty()?'Unsaved changes. This tab retains your draft across reloads.':'No unsaved changes.');};
  $('#'+id).addEventListener('input',changed);$('#'+id).addEventListener('change',changed);
}
// Existing continuation/scene/recipe guards still own their handoffs. Do not leave during a write.
document.addEventListener('click',e=>{
  if((assetDetailBusy || assetDetailPending || assetDetailConflict) && $('#assetDialog').open && e.target.closest('[data-ux-handoff],[data-handoff],.ux-scene-link,#assetRecipe')){
    e.preventDefault();e.stopImmediatePropagation();assetDetailStatus('Finish the pending save before continuing with this asset.');
  }
},true);
$('#importAssets').onchange=async e=>{
  const files=[...e.target.files];if(!files.length)return;
  if(files.length>32){assetMessage('Import up to 32 images at a time.',true);return;}
  const ids=[];
  try{
    for(let i=0;i<files.length;i++){
      const file=files[i];assetMessage('Importing '+(i+1)+' of '+files.length+'…');
      if(file.size>20*1024*1024)throw Error(file.name+' exceeds 20 MiB');
      const result=await api('/api/assets/import',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file});ids.push(result.asset.id);
    }
    assetScope='all';$('#assetSearch').value='';await refreshAssets(true);assetSelection=new Set(ids);renderAssets();assetMessage('Imported '+ids.length+' originals. They are selected for organization or native export.');
  }catch(err){await refreshAssets(true);assetMessage(err.message+' '+ids.length+' earlier imports are preserved.',true);}
  finally{e.target.value='';}
};
function assetMessage(text, error=false) { const el=$('#assetMessage'); el.textContent=text; el.classList.toggle('error',error); }
async function refreshAssets(force=false) {
  if(assetRefreshing)return false;
  assetRefreshing=true;
  try {
    const data=await api('/api/workspace'), signature=JSON.stringify(data);
    const previousScope=assetState.workspace_id;
    assetState=data;
    if(previousScope && previousScope!==data.workspace_id){assetSelection.clear();if(assetLibraryPending?.command.workspace_id===data.workspace_id)assetRetainedSelection=assetLibraryPending.selection;}
    renderLibraryRecovery();
    if(force||signature!==assetSignature){assetSignature=signature;renderAssets();jobsSignature='';renderJobs();}
    return true;
  } catch(e) { assetMessage(e.message,true); return false; }
  finally {assetRefreshing=false;}
}
// Scope, filters and checkbox selection are separate projections over the loaded Workspace.
const assetSelectionLimit=200;
function assetScopeAssets() {
  if(assetScope.startsWith('collection:') && !assetState.collections.some(c=>'collection:'+c.id===assetScope))return [];
  return assetState.assets.filter(a=>{
    if(assetScope==='trash'?!a.trashed_at:!!a.trashed_at)return false;
    if(assetScope==='favorite'&&!a.favorite)return false;
    if(['selected','needs_work','unreviewed'].includes(assetScope)&&(a.review||'unreviewed')!==assetScope)return false;
    return !assetScope.startsWith('collection:') || a.collections.includes(assetScope.slice(11));
  });
}
function assetFiltersActive(){return !!$('#assetSearch').value.trim() || $('#assetType').value!=='all';}
function visibleAssets() {
  const query=$('#assetSearch').value.trim().toLowerCase(), type=$('#assetType').value;
  const list=assetSourceFilter(assetScopeAssets()).filter(a=>(type==='all'||a.media_type===type)&&[a.title,a.preset_name,a.notes,a.run_label||'',a.prompt_excerpt||'',...a.tags].join(' ').toLowerCase().includes(query));
  const sort=$('#assetSort').value;
  return list.sort((a,b)=>sort==='title'?a.title.localeCompare(b.title):sort==='oldest'?a.created_at-b.created_at:b.created_at-a.created_at);
}
// Pure projection: the same assets and mode always give the same sections, in first-seen order.
function assetGroupOf(asset, mode) {
  if(mode==='recipe')return {key:'recipe:'+(asset.preset_name||''),label:asset.preset_name||'No recipe recorded'};
  if(mode==='run')return {key:'run:'+(asset.job_id||''),label:asset.job_id?'Run '+String(asset.job_id).slice(0,10)+(asset.preset_name?' · '+asset.preset_name:''):'No run recorded'};
  if(mode==='day'){
    const at=Number(asset.created_at);
    if(!Number.isFinite(at))return {key:'day:',label:'No date recorded'};
    const when=new Date(at*1000),pad=n=>String(n).padStart(2,'0');
    const day=when.getFullYear()+'-'+pad(when.getMonth()+1)+'-'+pad(when.getDate());
    return {key:'day:'+day,label:day};
  }
  return {key:'',label:''};
}
function assetGroups(assets, mode) {
  if(!assetGroupModes.includes(mode))return [{key:'',label:'',assets:[...assets]}];
  const sections=new Map();
  for(const asset of assets){const group=assetGroupOf(asset,mode);if(!sections.has(group.key))sections.set(group.key,{...group,assets:[]});sections.get(group.key).assets.push(asset);}
  return [...sections.values()];
}
function assetUnreviewed(list){return list.filter(a=>(a.review||'unreviewed')==='unreviewed');}
function assetSelectionInfo(visible=visibleAssets()) {
  const records=new Map(assetState.assets.map(a=>[a.id,a])),shown=new Set(visible.map(a=>a.id));
  const entries=[...assetSelection].map(id=>({id,asset:records.get(id),visible:shown.has(id)}));
  return {entries,visible:entries.filter(e=>e.visible).length,hidden:entries.filter(e=>!e.visible).length,missing:entries.filter(e=>!e.asset).length};
}
function assetEmptyState() {
  const everySource=assetScopeAssets(),scope=assetSourceFilter(everySource),collection=assetScope.startsWith('collection:');
  let title,description,action='<button data-scope="all" data-asset-browse-scope>Browse all assets</button>';
  if(collection && !assetState.collections.some(c=>'collection:'+c.id===assetScope)){
    title='Collection unavailable';description='This collection is no longer in the loaded Workspace. Your original assets are not deleted with a collection.';
  }else if(!scope.length && everySource.length){
    const mine=assetSource()==='mine';
    title=mine?'None of your own runs here':'No agent runs here';description='This view holds '+everySource.length+(mine?' agent-run':' of your own')+' assets, hidden by the source filter.';
    action='<button data-asset-source="all">Show all sources</button>';
  }else if(scope.length && assetFiltersActive()){
    title='No matching assets';description='This view contains '+scope.length+' assets, but none match your search and media filter. Your selection is unchanged.';
    action='<button data-asset-clear-filters>Clear filters in this view</button>';
  }else if(assetScope==='trash'){
    title='Trash is empty';description='Assets moved to Trash remain recoverable here.';
  }else if(collection){
    title='This collection has no assets';description='Select assets in the library, choose this collection as the destination, then add them.';
  }else if(assetScope==='favorite'){
    title='No favorites yet';description='Use the star on an asset to find it here. Favorites do not change your review notes.';
  }else if(assetScope==='selected'){
    title='No keepers yet';description='Mark a reviewed asset as a keeper to find it here. Checking a selection box only chooses assets for an action.';
  }else if(assetScope==='unreviewed'){
    title='No assets awaiting review';description='Your active assets already have a saved review. Browse all assets to revisit a decision.';
  }else if(assetScope==='needs_work'){
    title='No assets marked Needs work';description='Open an asset and save a Needs work review to collect candidates for correction here.';
  }else if(assetState.assets.some(a=>a.trashed_at)){
    title='Your assets are in Trash';description='Open Trash to review and restore them. Moving assets to Trash does not delete their originals.';
    action='<button data-scope="trash" data-asset-browse-scope>Open Trash</button>';
  }else{
    title='Your asset library is empty';description='Import an existing image to organize or continue working on it. Importing does not generate a new image.';
    action='<button data-asset-import>Import images</button>';
  }
  return '<div class="asset-empty"><h3>'+title+'</h3><p>'+description+'</p>'+action+'</div>';
}
// This guards ordinary pointer/keyboard activation. Existing execution and native-tool gates still apply.
function assetSelectionCanProceed(action) {
  if(!assetSelection.size)return false;
  const selection=assetSelectionInfo();
  if(selection.missing){assetMessage(selection.missing+(selection.missing===1?' selected asset is unavailable.':' selected assets are unavailable.')+' Review the selection or keep only visible assets before continuing.',true);return false;}
  if(assetSelection.size>assetSelectionLimit){assetMessage('Choose at most '+assetSelectionLimit+' assets per action. The current selection has not been changed.',true);return false;}
  if(selection.entries.some(e=>e.asset.workspace_id && e.asset.workspace_id!==assetState.workspace_id)){assetMessage('Selected assets belong to a different Workspace. Refresh the library before continuing.',true);return false;}
  const labels={trash:'Move to Trash',restore:'Restore',favorite:'Favorite',selected:'Mark as keeper',review:'Mark a review',add_collection:'Add to collection',remove_collection:'Remove from collection',export:'Export pack',scene:'Create scene',native:'Create native export'};
  return !selection.hidden || window.confirm((labels[action]||'This action')+' will include '+selection.hidden+(selection.hidden===1?' selected asset':' selected assets')+' outside this view. Continue with all '+assetSelection.size+' selected assets? Cancel to review the selection or keep only visible assets.');
}
function clearAssetFilters() {clearTimeout(assetSearchTimer);assetSearchTimer=null;$('#assetSearch').value='';$('#assetType').value='all';renderAssets();$('#assetSearch').focus();}
// Small previews use the server's cached WEBP thumbnail; detail and review views keep the original.
// ?v=<rendering version>-<sha256 prefix> names the bytes, so only then may the server mark the response immutable
// (an ID alone can recur across Workspaces).
function assetThumbUrl(asset) {return '/api/assets/'+encodeURIComponent(asset.id)+'/thumb?v='+ASSET_THUMB_VERSION+'-'+encodeURIComponent(String(asset.sha256||'').slice(0,16));}
function assetPreview(asset, detail=false) {
  const url=asset.url, alt=esc(asset.title);
  if(asset.media_type==='image')return detail?'<img loading="lazy" decoding="async" src="'+url+'" alt="'+alt+'">':'<img loading="lazy" decoding="async" src="'+esc(assetThumbUrl(asset))+'" data-full-src="'+esc(url)+'" alt="'+alt+'">';
  if(asset.media_type==='video')return '<video '+(detail?'controls':'muted')+' preload="metadata" src="'+url+'" aria-label="'+alt+'"></video>';
  if(asset.media_type==='audio')return detail?'<audio controls src="'+url+'"></audio>':'<span class="asset-type-placeholder">♫<small>Audio</small></span>';
  return detail?'<model-viewer camera-controls touch-action="pan-y" environment-image="neutral" src="'+url+'" alt="'+alt+'"></model-viewer>':'<span class="asset-type-placeholder">◇<small>3D model</small></span>';
}
function assetCardHTML(a) {return '<article class="asset-card '+(assetSelection.has(a.id)?'is-selected':'')+'" data-asset-card="'+esc(a.id)+'"><div class="asset-card-preview"><button class="asset-open" data-asset-open="'+a.id+'" aria-label="Open '+esc(a.title)+'">'+assetPreview(a)+'</button><label class="asset-check"><input type="checkbox" data-asset-check="'+a.id+'" '+(assetSelection.has(a.id)?'checked':'')+' aria-label="Select '+esc(a.title)+'"></label><button class="asset-star '+(a.favorite?'starred':'')+'" data-asset-favorite="'+a.id+'" aria-label="'+(a.favorite?'Unfavorite':'Favorite')+' '+esc(a.title)+'">'+(a.favorite?'★':'☆')+'</button><span class="asset-kind">'+esc(a.media_type)+'</span></div><button class="asset-card-title" data-asset-open="'+a.id+'">'+esc(a.title)+'</button>'+(assetSubtitle(a)?'<small class="asset-card-prompt" title="'+esc(assetSubtitle(a))+'">'+esc(assetSubtitle(a))+'</small>':'')+'<div class="asset-card-meta"><span>'+esc(a.preset_name)+'</span><span class="review-'+a.review+'">'+esc(a.review==='selected'?'keeper':a.review.replace('_',' '))+'</span></div><div class="asset-tags">'+(assetIsAgentRun(a)?'<span class="asset-run-label" title="Agent run label">'+esc(a.run_label)+'</span>':'')+a.tags.slice(0,4).map(t=>'<span>'+esc(t)+'</span>').join('')+'</div></article>';}
function renderAssets() {
  observeAssetWorkspaceIdentity();
  const assets=visibleAssets(), col=assetState.collections.find(c=>'collection:'+c.id===assetScope), source=assetSource();
  const inScope=assetScopeAssets(), sourced=assetSourceFilter(inScope,source), sourceHidden=inScope.length-sourced.length;
  $('#assetTotal').textContent=assetState.assets.filter(a=>!a.trashed_at).length;
  $('#assetSource').hidden=!assetState.assets.some(assetIsAgentRun);$('#assetSource').value=source;
  $('#assetVisibleCount').textContent=(assetFiltersActive()?assets.length+' of '+sourced.length+' assets':assets.length+' assets')+(sourceHidden?' · '+sourceHidden+(source==='mine'?' agent runs hidden':' of yours hidden'):'');
  $('#clearAssetFilters').hidden=!assetFiltersActive();
  $('#selectVisible').disabled=!assets.length;
  $('#selectVisible').textContent=assets.length>assetSelectionLimit?'Select first '+assetSelectionLimit+' of '+assets.length:'Select visible';
  $('#assetScopeTitle').textContent=col?.name||({all:'All assets',unreviewed:'Awaiting review',favorite:'Favorites',selected:'Keepers',needs_work:'Needs work',trash:'Trash'}[assetScope]||'Collection');
  $('#collectionActions').hidden=!col;
  $('#assetCollections').innerHTML=assetState.collections.map(c=>'<button data-scope="collection:'+c.id+'" class="'+(col?.id===c.id?'active':'')+'"><span>▱ '+esc(c.name)+'</span><small>'+c.count+'</small></button>').join('')||'<p class="muted">Collect a character, a project, or an idea.</p>';
  document.querySelectorAll('#assetScopes [data-scope]').forEach(b=>b.classList.toggle('active',b.dataset.scope===assetScope));
  const destination=$('#bulkCollection').value;
  $('#bulkCollection').innerHTML='<option value="">Choose collection…</option>'+assetState.collections.map(c=>'<option value="'+c.id+'">'+esc(c.name)+'</option>').join('');
  if(assetState.collections.some(c=>c.id===destination))$('#bulkCollection').value=destination;
  const pending=assetUnreviewed(assets);
  $('#reviewNext').textContent='Review next ('+pending.length+' unreviewed)';
  $('#reviewNext').disabled=!pending.length;
  const groups=assetGroups(assets,assetGroupMode),grouped=!!groups[0]?.key;
  $('#assetGrid').classList.toggle('is-grouped',grouped && !!assets.length);
  StudioAssetGrid.render($('#assetGrid'),assets,{groups,workspaceId:assetState.workspace_id,selected:assetSelection,cardHTML:assetCardHTML,groupActionsHTML:assetGroupActionsHTML,emptyHTML:assets.length?'':assetEmptyState(),focusFallback:$('#assetSearch')});
  renderAssetSelection();assetBulkReviewControls();
}
// Reconcile the saved record without fetching; retain cached nodes and current group membership.
function updateAssetCard() {renderAssets();}
function renderAssetSelection() {
  $('#assetBulk').hidden=!assetSelection.size;
  $('#assetSelectionCount').textContent=assetSelection.size+' selected';
  const selection=assetSelectionInfo();
  $('#assetSelectionSummary').textContent=selection.visible+' visible · '+selection.hidden+' outside this view'+(selection.missing?' · '+selection.missing+' unavailable':'')+'. Actions use the whole selection, not just matching results.';
  $('#keepVisibleSelection').disabled=!selection.hidden;
  $('#assetSelectedList').innerHTML=selection.entries.slice(0,assetSelectionLimit).map(e=>'<li><span>'+esc(e.asset?.title||e.id)+'</span><small>'+(!e.asset?'Unavailable':e.asset.trashed_at?'In Trash':e.visible?'Visible':'Outside this view')+'</small></li>').join('')+(selection.entries.length>assetSelectionLimit?'<li>Only the first '+assetSelectionLimit+' selections are listed. Reduce the selection before acting.</li>':'');
  $('#createScene').href='/av.html?asset_ids='+encodeURIComponent([...assetSelection].join(','));
  document.querySelectorAll('[data-bulk="restore"]').forEach(b=>b.hidden=assetScope!=='trash');
  document.querySelectorAll('[data-bulk="trash"]').forEach(b=>b.hidden=assetScope==='trash');
}
function renderAssetQueue() {
  const panel=$('#assetQueue');
  panel.hidden=!assetQueue;
  if(!assetQueue){panel.innerHTML='';return;}
  panel.innerHTML='<div class="asset-queue-head"><b>Review queue</b><span role="status" aria-live="polite">'+(assetQueue.index+1)+' of '+assetQueue.ids.length+'</span></div>'+
    '<div class="asset-queue-actions"><button type="button" data-queue-review="selected">Keeper <kbd>K</kbd></button><button type="button" data-queue-review="needs_work">Needs work <kbd>W</kbd></button><button type="button" data-queue-review="rejected">Rejected <kbd>X</kbd></button><button type="button" data-queue-skip>Skip <kbd>S</kbd></button><button type="button" data-queue-step="-1">← Previous</button><button type="button" data-queue-step="1">Next →</button><button type="button" data-queue-exit>Leave queue</button></div>'+
    '<small class="asset-queue-legend">K keeper · W needs work · X rejected · S skip without saving · ← / → move. Typing in a field is never a shortcut. Each decision saves through Save details and then advances.</small>';
}
function startReviewQueue() {
  const pending=assetUnreviewed(visibleAssets()).slice().sort((a,b)=>(b.created_at||0)-(a.created_at||0));
  if(!pending.length){assetMessage('No unreviewed assets match this view. Change the scope or filters to review more.');return false;}
  assetQueue={ids:pending.map(a=>a.id),index:0};
  if(!openAsset(assetQueue.ids[0])){assetQueue=null;renderAssetQueue();return false;}
  renderAssetQueue();assetMessage('Review queue: '+pending.length+' unreviewed assets in this view. Nothing is saved until you choose.');return true;
}
function assetQueueStep(delta) {
  if(!assetQueue)return false;
  const next=assetQueue.index+delta;
  if(next<0){assetDetailStatus('This is the first asset in the queue.');return false;}
  // Leaving the queue is an ordinary close: unsaved typing still gets its discard consent.
  if(next>=assetQueue.ids.length){assetQueue=null;renderAssetQueue();closeAssetDetails();assetMessage('Review queue finished. Reopen it for anything still unreviewed.');return false;}
  const previous=assetQueue.index;assetQueue.index=next;
  if(!openAsset(assetQueue.ids[next])){if(assetQueue)assetQueue.index=previous;renderAssetQueue();return false;}
  return true;
}
async function assetQueueDecide(review) {
  if(!assetQueue || !activeAsset || assetDetailBusy || !assetReviewLabels[review] || review==='unreviewed')return false;
  // A shortcut must never re-send an unrelated unconfirmed command as if it were this decision.
  if(assetDetailPending || assetDetailConflict){assetDetailStatus('Resolve the earlier save for this asset before recording a queue decision.',true);return false;}
  if(assetQueue.ids[assetQueue.index]!==activeAsset.id)return false;
  $('#assetReview').value=review;renderAssetReasons();
  const target=activeAsset.id;
  await saveAssetDetails();
  // Only a confirmed save advances: an unconfirmed, conflicted or refused save keeps this asset and its reason on screen.
  if(assetDetailBusy || assetDetailPending || assetDetailConflict || activeAsset?.id!==target)return false;
  if(assetState.assets.find(a=>a.id===target)?.review!==review)return false;
  return assetQueueStep(1);
}
function assetTagList(){return $('#assetTags').value.split(',').map(t=>t.trim()).filter(Boolean);}
function renderAssetReasons() {
  const chosen=new Set(assetTagList().map(t=>t.toLowerCase()));
  $('#assetReviewReasons').innerHTML=assetReasonTags.map(reason=>'<button type="button" class="asset-reason'+(chosen.has(reason)?' is-on':'')+'" data-review-reason="'+esc(reason)+'" aria-pressed="'+(chosen.has(reason)?'true':'false')+'">'+esc(reason)+'</button>').join('');
}
function toggleAssetReason(reason) {
  if(!assetReasonTags.includes(reason) || assetDetailBusy)return;
  const tags=assetTagList(),at=tags.findIndex(t=>t.toLowerCase()===reason);
  if(at>=0)tags.splice(at,1);else tags.push(reason);
  $('#assetTags').value=tags.join(', ');renderAssetReasons();
  if(!retainAssetDraft())return;
  assetDetailStatus(assetDetailDirty()?'Unsaved changes. Reason tags are saved with Save details or a queue decision.':'No unsaved changes.');
}
function renderAssetSiblings(asset) {
  const panel=$('#assetSameRun');
  const siblings=asset&&asset.job_id?assetState.assets.filter(a=>a.job_id===asset.job_id&&!a.trashed_at):[];
  panel.hidden=siblings.length<2;
  panel.innerHTML=siblings.length<2?'':'<h3>Same run</h3><div class="asset-sibling-strip">'+siblings.map(s=>'<button type="button" class="asset-sibling'+(s.id===asset.id?' is-current':'')+'" data-asset-open="'+esc(s.id)+'" aria-current="'+(s.id===asset.id?'true':'false')+'">'+assetPreview(s)+'<small>'+esc(s.title)+'</small></button>').join('')+'</div><small>'+siblings.length+' outputs from this job. Opening one keeps your unsaved draft rules.</small>';
}
function assetBulkReviewControls(){document.querySelectorAll('[data-review-bulk],[data-group-review]').forEach(b=>{if(b.disabled!==assetBulkReviewBusy)b.disabled=assetBulkReviewBusy;});}
// Selection and group review share one write: the ordinary /api/assets/update edit with expected_revisions.
async function postAssetCommand(command) {
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try{return await api('/api/assets/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command),signal:controller.signal});}finally{clearTimeout(timer);}
}
// A confirmed receipt updates only records still at the revision it was issued against.
function applyAssetReviewReceipt(command,result) {
  for(const id of command.ids){
    const record=assetState.assets.find(a=>a.id===id);
    if(record && (!record.workspace_id || record.workspace_id===command.workspace_id) && record.metadata_revision===command.expected_revisions[id])Object.assign(record,result.applied,{metadata_revision:result.revisions[id]});
  }
}
// Bulk review sends the ordinary single-asset save per asset, three at a time; no failure is dropped.
async function bulkReviewSelected(review) {
  if(assetBulkReviewBusy || !assetReviewLabels[review] || review==='unreviewed')return;
  if(assetLibraryPending || assetLibraryBusy){assetMessage('Resolve the earlier library update before marking reviews.',true);return;}
  if(assetDetailBusy || assetDetailPending || assetDetailConflict){assetMessage('Finish the open asset save before marking the selection.',true);return;}
  if(!assetSelectionCanProceed('review'))return;
  const ids=[...assetSelection],label=assetReviewLabels[review],failures=[];
  let done=0;
  const status=text=>{$('#assetBulkReviewStatus').textContent=text;};
  assetBulkReviewBusy=true;assetBulkReviewControls();status('Marking 0 of '+ids.length+' as '+label+'…');
  const queue=ids.slice();
  const worker=async()=>{
    while(queue.length){
      const id=queue.shift(),record=assetState.assets.find(a=>a.id===id);
      try {
        const command=assetCommand({ids:[id],action:'edit',review},[record],record?.workspace_id||assetState.workspace_id);
        const result=validateAssetReceipt(await postAssetCommand(command),command);
        applyAssetReviewReceipt(command,result);
        done++;
      } catch(error) {
        const refused=error.status>=400 && error.status<500 && error.data?.code!=='asset_workspace_conflict';
        failures.push((record?.title||id)+' — '+(refused?'not applied. ':'not confirmed. ')+(error.name==='AbortError'?'The request timed out after 15 s.':error.message));
      }
      status('Marking '+(done+failures.length)+' of '+ids.length+' as '+label+'…');
    }
  };
  try{await Promise.all(Array.from({length:Math.max(1,Math.min(3,ids.length))},worker));}
  finally {
    assetBulkReviewBusy=false;assetBulkReviewControls();renderAssets();
    status(failures.length?done+' of '+ids.length+' marked as '+label+'. '+failures.length+' failed and no retry was sent: '+failures.join(' · ')
      :'Marked '+done+' of '+ids.length+' as '+label+'.');
  }
}
// Group triage (#939): one confirmed decision for a visible group's unreviewed assets. The ids and their revisions are
// fixed when the operator confirms; batches stay within the server's 200-asset command limit and each carries its own
// expected_revisions, so a later refresh can never turn a stale snapshot into an overwrite. The first batch that is
// refused, conflicted or unconfirmed stops the run. Status is owned by the Workspace generation it started in (#830).
const assetGroupReviewBatch=assetSelectionLimit;
function assetGroupReviewPlan(key, visible=visibleAssets()) {
  if(!assetGroupModes.includes(assetGroupMode))return null;
  const group=assetGroups(visible,assetGroupMode).find(g=>g.key===key);
  if(!group)return null;
  const pending=assetUnreviewed(group.assets);
  return {key,label:group.label,ids:pending.map(a=>a.id),reviewed:group.assets.length-pending.length,images:pending.every(a=>a.media_type==='image')};
}
function assetGroupNoun(plan,count){return plan.images?(count===1?'picture':'pictures'):(count===1?'asset':'assets');}
function assetGroupReviewPrompt(plan, review) {
  const count=plan.ids.length,noun=assetGroupNoun(plan,count);
  return 'Mark '+count+' unreviewed '+noun+' in \''+plan.label+'\' as '+assetReviewLabels[review]+'?\n\n'+
    'Only the unreviewed '+noun+' shown in this group with the current filters change'+(plan.reviewed?'; '+plan.reviewed+' already reviewed '+(plan.reviewed===1?'keeps its':'keep their')+' review':'')+'. '+
    'Each review can be changed back individually by opening the asset.';
}
function assetGroupActionsHTML(group) {
  const pending=assetUnreviewed(group.assets).length;
  if(!pending)return '';
  return '<span class="asset-group-mark">Mark '+pending+' unreviewed as</span>'+['needs_work','rejected','selected'].map(review=>
    '<button type="button" data-group-review="'+review+'" data-group-key="'+esc(group.key)+'" aria-label="'+esc('Mark '+pending+' unreviewed in '+group.label+' as '+assetReviewLabels[review])+'">'+esc(assetReviewLabels[review])+'</button>').join('');
}
async function bulkReviewGroup(key, review) {
  if(assetBulkReviewBusy || !assetReviewLabels[review] || review==='unreviewed')return false;
  if(assetLibraryPending || assetLibraryBusy){assetMessage('Resolve the earlier library update before marking reviews.',true);return false;}
  if(assetDetailBusy || assetDetailPending || assetDetailConflict){assetMessage('Finish the open asset save before marking a group.',true);return false;}
  const plan=assetGroupReviewPlan(key);
  if(!plan){assetMessage('That group is no longer shown. Nothing was changed.',true);return false;}
  if(!plan.ids.length){assetMessage('Every asset shown in \''+plan.label+'\' already has a review. Nothing was changed.');return false;}
  const workspace=assetState.workspace_id,epoch=assetWorkspaceEpoch,label=assetReviewLabels[review],total=plan.ids.length;
  const snapshot=plan.ids.map(id=>{const record=assetState.assets.find(a=>a.id===id);return {id,workspace_id:record.workspace_id,metadata_revision:record.metadata_revision};});
  if(!window.confirm(assetGroupReviewPrompt(plan,review))){assetMessage('Nothing was changed.');return false;}
  const owns=()=>assetState.workspace_id===workspace && assetWorkspaceEpoch===epoch;
  const where=' in \''+plan.label+'\' as '+label;
  let done=0,stop='';
  // Disabling the focused trigger can drop focus to <body>, outside the grid's own handoff; restore it after the run.
  const trigger=document.activeElement?.closest?.('[data-group-review]')?document.activeElement:null;
  assetBulkReviewBusy=true;assetBulkReviewControls();assetMessage('Marking 0 of '+total+where+'…');
  try {
    for(let at=0;at<total;at+=assetGroupReviewBatch){
      if(!owns()){stop='The Workspace changed, so no further batch was sent.';break;}
      const ids=plan.ids.slice(at,at+assetGroupReviewBatch),batch='Batch '+(at/assetGroupReviewBatch+1)+' ('+ids.length+' '+assetGroupNoun(plan,ids.length)+')';
      let command;
      try{command=assetCommand({ids,action:'edit',review},snapshot,workspace);}catch(error){stop=error.message;break;}
      try {
        const result=validateAssetReceipt(await postAssetCommand(command),command);
        done+=ids.length;
        if(owns())applyAssetReviewReceipt(command,result);
      } catch(error) {
        const code=error.data?.code;
        if(code==='asset_revision_conflict'){
          const changed=(error.data.conflict_ids?.length||0)+(error.data.missing_ids?.length||0);
          stop=batch+' was not applied: '+(changed||'some')+' of its assets changed elsewhere or no longer exist since you confirmed.';
        }else if(code!=='asset_workspace_conflict' && error.status>=400 && error.status<500)stop=batch+' was refused and not applied. '+error.message;
        else stop=batch+' is not confirmed: it may or may not have been applied. '+(error.name==='AbortError'?'The request timed out after 15 s.':error.message);
        break;
      }
      if(owns())assetMessage('Marking '+done+' of '+total+where+'…');
    }
  } finally {
    assetBulkReviewBusy=false;assetBulkReviewControls();
    if(!owns())assetMessage('Group review stopped: the Workspace changed while it ran. '+done+' of '+total+' were confirmed'+where+' in the earlier Workspace. Nothing was marked in the Workspace now shown.',true);
    else {
      renderAssets();
      const focused=document.activeElement;
      if(trigger && (!focused || focused===document.body || focused===trigger && (!trigger.isConnected || trigger.disabled)))StudioAssetGrid.focusGroup?.($('#assetGrid'),key,review);
      assetMessage(stop?done+' of '+total+' marked'+where+'. Stopped: '+stop+' No retry was sent; refresh the library before marking what remains.':
        'Marked '+done+' of '+total+where+'. Each review can be changed back individually by opening the asset.',!!stop);
    }
  }
  return !stop;
}
function renderLibraryRecovery() {
  observeAssetWorkspaceIdentity();
  if(assetRetainedSelection && StudioAssetRecovery.workspace(assetLibraryPending?.command.workspace_id) && assetLibraryPending.command.workspace_id===assetState.workspace_id){assetSelection=new Set(assetRetainedSelection);assetRetainedSelection=null;}
  const panel=$('#assetCommandRecovery');
  const detail=assetRetainedDetail?'<p>This tab has a retained asset draft'+(assetRetainedDetail.operation?' and an unconfirmed save':'')+'. Reloading sends no save.</p><button data-asset-recover-open>Review retained draft</button><details><summary>Retained draft text</summary><pre>'+esc(JSON.stringify(assetRetainedDetail.draft,null,2))+'</pre></details>':'';
  const scopeProblem=assetRetainedDetail?recoveryScopeMessage(assetRetainedDetail.workspace_id):assetLibraryPending?recoveryScopeMessage(assetLibraryPending.command.workspace_id):'';
  const discard=(assetRetainedDetail?'<button data-asset-recovery-discard="detail">Discard local draft and recovery</button>':'')+(assetLibraryPending?'<button data-asset-recovery-discard="library">Discard local update recovery</button>':'');
  const html=(assetRecoveryError?'<p>'+esc(assetRecoveryError)+'</p>':'')+(scopeProblem?'<p>'+esc(scopeProblem)+'</p>':'')+detail+discard+(assetLibraryPending?'<p>The earlier library update is unconfirmed. Selection is retained.</p><code>'+esc(assetLibraryPending.command.request_id)+'</code><details><summary>Retained update details</summary><pre>'+esc(JSON.stringify(assetLibraryPending.command,null,2))+'</pre></details><div class="asset-detail-actions"><button data-asset-batch-check>Check update status</button><button data-asset-batch-retry>Retry exact update</button></div>':'');
  renderAssetRecoveryPanel(panel,html,!assetLibraryPending && !assetRetainedDetail && !assetRecoveryError,
    ['[data-asset-recover-open]','[data-asset-batch-check]','[data-asset-batch-retry]','[data-asset-recovery-discard=\"detail\"]','[data-asset-recovery-discard=\"library\"]'],$('#workspaceRefresh'));
}
async function performLibraryCommand(operation,observe=false) {
  if(assetLibraryBusy)throw Error('A library update is still pending.');
  if(assetLibraryPending!==operation)throw Error('This update no longer owns the library recovery. No request was sent.');
  const request={},workspaceEpoch=assetWorkspaceEpoch,command=operation.command;
  assetLibraryRequest=request;
  const ownsRequest=()=>assetLibraryRequest===request;
  const current=()=>ownsRequest() && assetLibraryPending===operation && assetState.workspace_id===command.workspace_id && assetWorkspaceEpoch===workspaceEpoch;
  assetLibraryBusy=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try {
    if(assetRecoveryLoadError)throw Error(assetRecoveryLoadError);
    requireAssetScope(command.workspace_id);
    assetRecovery.write('library',{version:2,workspace_id:command.workspace_id,operation,selection:operation.selection||[...assetSelection]});
    const result=await (observe?api(assetReceiptURL(command),{signal:controller.signal}):assetRecovery.dispatch('library',operation,()=>api('/api/assets/update',{method:'POST',headers:{'Content-Type':'application/json'},body:operation.body,signal:controller.signal}),()=>current() && !controller.signal.aborted));
    if(!current())throw Error('The library or Workspace changed while this request was pending. Its original recovery is retained.');
    if(observe && result?.status==='unknown')throw Error('No receipt yet; the earlier update may still complete. No retry was sent.');
    validateAssetReceipt(result,command);assetRecovery.clear('library');assetLibraryPending=null;
    // A confirmed snapshot is not a new permission to overwrite another client's later changes.
    for(const id of command.ids){
      const asset=assetState.assets.find(a=>a.id===id);
      if(asset && asset.workspace_id===command.workspace_id && asset.metadata_revision===command.expected_revisions[id]){
        asset.metadata_revision=result.revisions[id];
        if(['edit','trash','restore'].includes(command.action))Object.assign(asset,result.applied);
      }
    }
    void refreshAssets(true);assetMessage('Library update confirmed.');return result;
  } catch(error) {
    if(current() && !observe && error.data?.code!=='asset_workspace_conflict' && error.status>=400 && error.status<500){throw Error('This attempt was refused. '+error.message+' The exact command and complete selection remain retained. Check its receipt or explicitly discard local recovery before a different update.');}
    throw Error('Library update not confirmed. '+error.message+' No automatic retry was sent.');
  } finally {
    clearTimeout(timer);
    if(ownsRequest()){assetLibraryRequest=null;assetLibraryBusy=false;if(!assetLibraryPending || assetLibraryPending===operation)renderLibraryRecovery();}
  }
}
async function mutateAssets(payload) {
  if(assetLibraryPending || assetLibraryBusy)throw Error('Resolve the earlier library update before starting another. Use Check update status or Retry exact update.');
  const command=assetCommand(payload,assetState.assets);assetLibraryPending={command,body:JSON.stringify(command),selection:[...assetSelection]};
  return performLibraryCommand(assetLibraryPending);
}
function setAssetScope(scope){assetScope=scope;assetSelection.clear();renderAssets();assetMessage(scope==='trash'?'Trash is recoverable. Original files and recipes remain on disk.':'');}
function diagnosticArtifact(record, label) {
  return record?.present && record.url ? '<a href="' + esc(record.url) + '" target="_blank" rel="noreferrer">' + esc(label) + '</a>' : '<span class="muted">' + esc(label) + ' unavailable</span>';
}
function renderI2VDiagnostic(report) {
  const source=report.source||{}, requested=report.requested||{}, prep=report.preprocessing||{}, probe=report.video?.probe||{};
  const models=(report.models||[]).map(model=>'<li><code>'+esc(model.filename)+'</code> · <span class="review-'+(model.pin_status==='verified'?'selected':'rejected')+'">'+esc(model.pin_status||'unknown')+'</span><br><small>'+esc(model.sha256||'hash unavailable')+' · '+(model.bytes?esc((model.bytes/1024/1024/1024).toFixed(2)+' GiB'):'size unavailable')+'</small></li>').join('')||'<li>No model records found in the submitted graph.</li>';
  const diff=(report.graph?.semantic_diff||[]).map(change=>'<li><code>'+esc(change.kind||'change')+'</code> · node '+esc(change.actual_node_id||change.canonical_node_id||change.position||'')+' · '+esc(change.field||change.class_type||'graph')+'<br><small>canonical '+esc(JSON.stringify(change.canonical??null))+'<br>actual '+esc(JSON.stringify(change.actual??null))+'</small></li>').join('')||'<li>No semantic differences detected.</li>';
  const warning=prep.warning?'<p class="i2v-warning">'+esc(prep.warning)+'</p>':'';
  $('#assetDiagnostic').innerHTML='<section class="i2v-diagnostic"><h3>Offline I2V diagnostic</h3><p><b>No generation submitted.</b> This report reads the recorded job, local media, graph, runtime and model files.</p>'+warning+'<div class="i2v-diagnostic-grid"><div><b>Source</b><p>'+esc(source.dimensions?.join(' × ')||'unknown')+' · '+esc(source.aspect_ratio??'unknown')+' aspect · '+esc(source.orientation||'unknown')+'</p><small><code>'+esc(source.path||source.filename||'unavailable')+'</code><br>'+esc(source.sha256||'hash unavailable')+'</small></div><div><b>Requested</b><p>'+esc(requested.dimensions?.join(' × ')||'unknown')+' · '+esc(requested.aspect_ratio??'unknown')+' aspect · '+esc(requested.frames??'unknown')+' frames · '+esc(requested.steps??'unknown')+' steps</p><small>Mode: '+esc(requested.mode||'not recorded')+' · '+esc(requested.sampler||'unknown')+' / '+esc(requested.scheduler||'unknown')+'</small></div><div><b>Decoded output</b><p>'+esc(probe.stream?.width??'unknown')+' × '+esc(probe.stream?.height??'unknown')+' · '+esc(probe.frame_count??'unknown')+' frames</p><small>Execution review: '+esc(report.job?.review||'not recorded')+' · quality acceptance: not inferred</small></div><div><b>Preprocessing</b><p>'+esc(prep.strategy||'unknown')+'</p><small>Crop box: '+esc(JSON.stringify(prep.crop_box||null))+' · letterbox: '+esc(prep.letterbox??'unknown')+' · full-source stretch: '+esc(prep.stretches_full_source??'unknown')+'</small></div></div><p><b>Artifacts:</b> '+diagnosticArtifact(report.artifacts?.contact_sheet,'Contact sheet')+' · '+diagnosticArtifact(report.artifacts?.preprocessed_first_frame,'Preprocessed first frame')+' · '+diagnosticArtifact(report.artifacts?.report,'JSON report')+'</p><details><summary>Model files and hashes</summary><ul>'+models+'</ul></details><details><summary>Exact prompts</summary><pre>'+esc(JSON.stringify(report.prompts||{},null,2))+'</pre></details><details><summary>Semantic graph diff from canonical upstream</summary><p>Canonical: <code>'+esc(report.graph?.canonical_path||'unavailable')+'</code></p><ul>'+diff+'</ul></details></section>';
}
function renderI2VDiagnosticAction(asset,error='') {
  const supported=asset?.media_type==='video'&&asset?.job_id&&asset?.preset_id==='wan22-i2v';
  $('#assetDiagnostic').innerHTML=supported?'<button data-i2v-diagnostic="'+esc(asset.job_id)+'">Offline I2V diagnostic</button><small>Reads the existing video and recipe only; no generation is submitted.</small>'+(error?'<p class="i2v-warning">'+esc(error)+'</p>':''):'';
}
function openAsset(id) {
  if(assetRetainedDetail){const problem=recoveryScopeMessage(assetRetainedDetail.workspace_id);if(problem){assetMessage(problem,true);renderLibraryRecovery();return false;}}
  const candidate=assetState.assets.find(a=>a.id===id);
  if(!candidate){assetDetailStatus('This asset is no longer in the loaded workspace. Refresh the library to check it.',true);return false;}
  if($('#assetDialog').open && activeAsset?.id===id)return true;
  if($('#assetDialog').open && !assetDetailCanLeave())return false;
  if(assetRetainedDetail && assetRetainedDetail.id!==id){
    if(assetRetainedDetail.operation || assetRetainedDetail.conflict){assetMessage('Review the retained draft before opening another asset. Its save recovery is still in this tab.',true);renderLibraryRecovery();return false;}
    if(!$('#assetDialog').open && !window.confirm('Discard the retained draft before opening another asset? Cancel keeps it in this tab.'))return false;
    try{assetRecovery.clear('detail');assetRetainedDetail=null;}catch(error){assetMessage(error.message,true);return false;}
  }
  activeAsset={...candidate,workspace_id:assetState.workspace_id};assetDetailEpoch++;assetDiagnosticRequest++;assetDetailPending=null;assetDetailConflict=null;renderAssetConflict();renderAssetSaveRecovery();
  const a=activeAsset;
  $('#assetDetailMedia').innerHTML=assetPreview(a,true);
  $('#assetTitle').value=a.title||'';$('#assetTags').value=(a.tags||[]).join(', ');$('#assetReview').value=a.review||'unreviewed';$('#assetNotes').value=a.notes||'';
  assetDetailBaseline=assetDetailValues();assetDetailControls();assetDetailStatus('No unsaved changes.');
  // Opening something outside the queue (a Same run sibling, lineage, the library) ends queue mode:
  // a position that no longer describes what is on screen would skip a queued asset on the next decision.
  if(assetQueue){const at=assetQueue.ids.indexOf(id);if(at>=0)assetQueue.index=at;else{assetQueue=null;assetMessage('Left the review queue to open an asset outside it. Review next starts a fresh queue.');}}
  renderAssetReasons();renderAssetSiblings(a);renderAssetQueue();
  $('#assetDetails').innerHTML='<p>'+esc(a.preset_name)+' · '+new Date(a.created_at*1000).toLocaleString()+'</p><p>'+esc(a.filename)+' · '+(a.bytes/1024/1024).toFixed(2)+' MiB</p><p>Seed '+esc(a.source.seed??'not recorded')+'</p>'+(a.prompt_excerpt?'<p class="asset-prompt-excerpt">Prompt text: '+esc(a.prompt_excerpt)+'</p>':'')+(assetIsAgentRun(a)?'<p>Run label: '+esc(a.run_label)+'</p>':'')+'<details><summary>File identity</summary><code>'+a.sha256+'</code><p>Prompt '+esc(a.source.prompt_id||'not recorded')+'</p></details>';
  $('#assetFavorite').textContent=a.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=a.trashed_at?'Restore':'Move to Trash';
  $('#assetDownload').href=a.url+'?download';
  $('#assetHandoffs').innerHTML=a.media_type==='image'?'<button data-handoff="reference">Edit image</button><button data-handoff="anime-detail-fix" title="Repaint detected hands and faces; review settings before generating">Fix hands &amp; face</button><button data-handoff="krea-refine" title="Open Krea image refinement; review settings before generating">Refine image</button><button data-handoff="wan22-i2v">Animate</button><button data-handoff="trellis-auto-cutout">Make 3D</button><button data-handoff="anime-upscale">Upscale</button>':'';
  renderI2VDiagnosticAction(a);
  $('#assetLineage').innerHTML=a.lineage.length?'<h3>Source assets</h3>'+a.lineage.map(id=>{const parent=assetState.assets.find(p=>p.id===id);return '<button data-lineage="'+esc(id)+'">'+esc(parent?.title||id)+'</button>';}).join(''):'';
  if(assetRetainedDetail?.id===id){
    const retained=assetRetainedDetail;Object.assign(activeAsset,retained.metadata);assetDetailBaseline=retained.baseline;
    for(const [key,field] of Object.entries(assetFormIds))$('#'+field).value=retained.draft[key];
    assetDetailPending=retained.operation?{...retained.operation,id,epoch:assetDetailEpoch}:null;assetDetailConflict=retained.conflict;
    $('#assetFavorite').textContent=activeAsset.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=activeAsset.trashed_at?'Restore':'Move to Trash';
    renderAssetConflict();renderAssetSaveRecovery();assetDetailControls();renderAssetReasons();assetDetailStatus('Retained draft restored. No save was sent. Review it or check the earlier save status.');
  }
  if(!$('#assetDialog').open)$('#assetDialog').showModal();
  return true;
}
async function handoffAsset(id,presetId) {
  const result=await post('/api/assets/reference',{id});
  let preset=catalog.presets.find(p=>p.id===presetId);
  if(presetId==='reference')preset=catalog.presets.find(p=>p.id==='qwen-1ref')||catalog.presets.find(p=>p.id==='gentle-variation')||catalog.presets.find(p=>p.reference&&(p.modality||'image')==='image');
  if(presetId==='anime-upscale')preset=catalog.presets.find(p=>p.id==='anime-esrgan-2x')||catalog.presets.find(p=>p.reference&&/upscale/i.test(p.name));
  if(!preset)throw Error('That recipe is unavailable');
  const intent=preset.modality==='video'?'animate':preset.modality==='3d'?'mesh':/fix|refine|upscale|esrgan/.test(preset.id)?'repair':'edit';
  beginContinuation(result,preset.id,intent);
  $('#referenceHint').textContent='Attached '+(assetState.assets.find(a=>a.id===id)?.title||'asset')+' · '+result.width+' × '+result.height;
  $('#assetDialog').close();showView('create');$('#selectedPreset').scrollIntoView({block:'start',behavior:'smooth'});message('Source asset attached. Adjust your brief, then generate.');
}
$('#workspaceRefresh').onclick=()=>refreshAssets(true);
// Typing repaints once the operator pauses; every other control is immediate.
$('#assetSearch').oninput=()=>{clearTimeout(assetSearchTimer);assetSearchTimer=setTimeout(()=>{assetSearchTimer=null;renderAssets();},150);};
$('#assetType').onchange=renderAssets;$('#assetSort').onchange=renderAssets;
function chooseAssetSource(value){assetSourceMode=assetSourceModes.includes(value)?value:null;try{localStorage.setItem(assetSourceStorageKey,assetSourceMode||'');}catch(error){}renderAssets();}
$('#assetSource').onchange=()=>chooseAssetSource($('#assetSource').value);
$('#assetGroup').onchange=()=>{assetGroupMode=assetGroupModes.includes($('#assetGroup').value)?$('#assetGroup').value:'none';try{localStorage.setItem(assetGroupStorageKey,assetGroupMode);}catch(error){}renderAssets();};
$('#reviewNext').onclick=()=>startReviewQueue();
$('#selectVisible').onclick=()=>{const assets=visibleAssets();assetSelection=new Set(assets.slice(0,assetSelectionLimit).map(a=>a.id));renderAssets();assetMessage(assets.length>assetSelectionLimit?'Selected the first '+assetSelectionLimit+' of '+assets.length+' matching assets in the current sort order. Choose smaller groups for the rest.':'Selected '+assets.length+' visible assets. Any earlier selection was replaced.');};
$('#clearAssetFilters').onclick=clearAssetFilters;
$('#keepVisibleSelection').onclick=()=>{const visible=new Set(visibleAssets().map(a=>a.id));assetSelection=new Set([...assetSelection].filter(id=>visible.has(id)));renderAssets();$('#assetSearch').focus();assetMessage('Selection now contains only visible assets. Any earlier unconfirmed command is unchanged.');};
document.addEventListener('click',e=>{
  const control=e.target.closest('[data-bulk],#createScene,#nativeExport');
  if(!control || control.getAttribute?.('aria-disabled')==='true')return;
  const action=control.dataset?.bulk || (control.id==='createScene'?'scene':control.id==='nativeExport'?'native':null);
  if(action && !assetSelectionCanProceed(action)){e.preventDefault();e.stopImmediatePropagation();}
},true);
$('#clearAssetSelection').onclick=()=>{assetSelection.clear();renderAssets();};
$('#closeAssetDialog').onclick=closeAssetDetails;
$('#assetDialog').addEventListener('cancel',e=>{e.preventDefault();closeAssetDetails();});
$('#assetDialog').addEventListener('close',()=>{
  // A queued close event can arrive after a new session has already opened.
  if($('#assetDialog').open)return;
  if(assetDetailPending || assetDetailConflict)retainAssetDraft();
  else if(!assetRecoveryLoadError)try{assetRecovery.clear('detail');assetRetainedDetail=null;}catch(error){assetRecoveryError=error.message;}
  assetDetailEpoch++;assetDiagnosticRequest++;assetDetailBaseline=null;assetQueue=null;renderAssetQueue();
  $('#assetDetailMedia').innerHTML='';$('#assetDiagnostic').innerHTML='';$('#assetSameRun').innerHTML='';$('#assetSameRun').hidden=true;
  renderLibraryRecovery();
});
// Queue shortcuts never fire while an editor has focus, and never while a decision is in flight.
document.addEventListener('keydown',e=>{
  if(!assetQueue || !$('#assetDialog').open || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey)return;
  const tag=(e.target?.tagName||'').toUpperCase();
  if(['INPUT','TEXTAREA','SELECT'].includes(tag) || e.target?.isContentEditable)return;
  const key=(e.key||'').toLowerCase();
  if(assetReviewShortcuts[key]){e.preventDefault();void assetQueueDecide(assetReviewShortcuts[key]);return;}
  if(key==='s'){e.preventDefault();assetDetailStatus('Skipped. No review was saved for this asset.');assetQueueStep(1);return;}
  if(e.key==='ArrowRight'){e.preventDefault();assetQueueStep(1);return;}
  if(e.key==='ArrowLeft'){e.preventDefault();assetQueueStep(-1);}
});
// Queue decisions and the Save details button share one save path, payload and revision guard.
async function saveAssetDetails() {
  const snapshot=assetDetailValues();
  const saved={title:snapshot.title.trim(),tags:[...new Set(snapshot.tags.split(',').map(t=>t.trim()).filter(Boolean))],review:snapshot.review,notes:snapshot.notes.trim()};
  const changes=Object.fromEntries(Object.keys(saved).filter(key=>snapshot[key]!==assetDetailBaseline?.[key]).map(key=>[key,saved[key]]));
  if(!Object.keys(changes).length && !assetDetailPending){assetDetailStatus('No unsaved changes.');return;}
  await writeAssetDetails({action:'edit',...changes},'details');
}
$('#saveAssetDetails').onclick=saveAssetDetails;
$('#assetFavorite').onclick=async()=>{
  const favorite=!activeAsset?.favorite;
  await writeAssetDetails({action:'edit',favorite},'favorite');
};
$('#assetTrash').onclick=async()=>{
  if(!activeAsset || !assetDetailCanLeave())return;
  const action=activeAsset.trashed_at?'restore':'trash';
  await writeAssetDetails({action},'trash');
};
$('#assetRecipe').onclick=()=>exportRecipe(activeAsset.job_id);
document.addEventListener('click',async e=>{
  try{
    const discard=e.target.closest('[data-asset-recovery-discard]');
    if(discard){
      const slot=discard.dataset.assetRecoveryDiscard;
      if(!['detail','library'].includes(slot) || assetDetailBusy || assetLibraryBusy || $('#assetDialog').open)return;
      if(!window.confirm('Discard this local draft/recovery record? An unconfirmed save may already have committed. This does not cancel or undo any server change.'))return;
      assetRecovery.clear(slot);
      if(slot==='detail')assetRetainedDetail=null;else {assetLibraryPending=null;assetRetainedSelection=null;assetSelection.clear();}
      renderLibraryRecovery();assetMessage('Local recovery discarded. No server change was made.');return;
    }
    if(e.target.closest('[data-asset-recover-open]')){if(assetRetainedDetail)openAsset(assetRetainedDetail.id);return;}
    if(e.target.closest('[data-asset-save-check]')){await checkAssetSave();return;}
    if(e.target.closest('[data-asset-save-retry]')){if(assetDetailPending)await performAssetSave(assetDetailPending);return;}
    if(e.target.closest('[data-asset-rebase]')){resolveAssetConflict(true);return;}
    if(e.target.closest('[data-asset-current]')){resolveAssetConflict(false);return;}
    if(e.target.closest('[data-asset-batch-check]')){if(assetLibraryPending)await performLibraryCommand(assetLibraryPending,true);return;}
    if(e.target.closest('[data-asset-batch-retry]')){if(assetLibraryPending)await performLibraryCommand(assetLibraryPending);return;}
    const diagnostic=e.target.closest('[data-i2v-diagnostic]');
    if(diagnostic){
      const asset=activeAsset, epoch=assetDetailEpoch, request=++assetDiagnosticRequest;
      if(!asset || asset.media_type!=='video' || asset.preset_id!=='wan22-i2v' || asset.job_id!==diagnostic.dataset.i2vDiagnostic)return;
      const current=()=>assetDetailContextCurrent(asset.id,epoch) && request===assetDiagnosticRequest;
      diagnostic.disabled=true;$('#assetDiagnostic').innerHTML='<p class="muted" role="status">Building offline report from the existing recording…</p>';
      try {const report=await api('/api/jobs/'+encodeURIComponent(asset.job_id)+'/i2v-diagnostic');if(current())renderI2VDiagnostic(report);}
      catch(err){if(current())renderI2VDiagnosticAction(asset,err.message);}
      return;
    }
    const reason=e.target.closest('[data-review-reason]');if(reason){toggleAssetReason(reason.dataset.reviewReason);return;}
    const decide=e.target.closest('[data-queue-review]');if(decide){await assetQueueDecide(decide.dataset.queueReview);return;}
    if(e.target.closest('[data-queue-skip]')){assetDetailStatus('Skipped. No review was saved for this asset.');assetQueueStep(1);return;}
    const step=e.target.closest('[data-queue-step]');if(step){assetQueueStep(Number(step.dataset.queueStep));return;}
    if(e.target.closest('[data-queue-exit]')){assetQueue=null;renderAssetQueue();assetMessage('Left the review queue. Saved reviews are unchanged.');return;}
    const bulkReview=e.target.closest('[data-review-bulk]');if(bulkReview){await bulkReviewSelected(bulkReview.dataset.reviewBulk);return;}
    const groupReview=e.target.closest('[data-group-review]');if(groupReview){await bulkReviewGroup(groupReview.dataset.groupKey,groupReview.dataset.groupReview);return;}
    if(e.target.closest('[data-asset-clear-filters]')){clearAssetFilters();return;}
    const sourceChoice=e.target.closest('[data-asset-source]');if(sourceChoice){chooseAssetSource(sourceChoice.dataset.assetSource);return;}
    if(e.target.closest('[data-asset-import]')){$('#importAssets').click();return;}
    const scope=e.target.closest('[data-scope]');if(scope){if(scope.hasAttribute?.('data-asset-browse-scope')){$('#assetSearch').value='';$('#assetType').value='all';}setAssetScope(scope.dataset.scope);}
    const open=e.target.closest('[data-asset-open]');if(open)openAsset(open.dataset.assetOpen);
    const favorite=e.target.closest('[data-asset-favorite]');if(favorite){const a=assetState.assets.find(a=>a.id===favorite.dataset.assetFavorite);await mutateAssets({ids:[a.id],action:'edit',favorite:!a.favorite});}
    const lineage=e.target.closest('[data-lineage]');if(lineage)openAsset(lineage.dataset.lineage);
    const handoff=e.target.closest('[data-handoff]');if(handoff)await handoffAsset(activeAsset.id,handoff.dataset.handoff);
    const bulk=e.target.closest('[data-bulk]');
    if(bulk){
      const ids=[...assetSelection], action=bulk.dataset.bulk;if(!ids.length)return;
      if(action==='export'){assetMessage('Building a pack with originals, recipes and metadata…');const result=await post('/api/assets/export',{ids});const link=document.createElement('a');link.href=result.url;link.download='asset-pack.zip';link.click();assetMessage('Export ready: '+result.count+' assets with recipes and provenance.');return;}
      const payload={ids,action,collection_id:$('#bulkCollection').value};
      if(action==='favorite')Object.assign(payload,{action:'edit',favorite:true});
      if(action==='selected')Object.assign(payload,{action:'edit',review:'selected'});
      await mutateAssets(payload);const changed=JSON.stringify([...assetSelection])!==JSON.stringify(ids);if(!changed)assetSelection.clear();renderAssets();assetMessage((action==='trash'?'Moved to Trash. Originals and recipes are preserved.':'Updated '+ids.length+' assets.')+(changed?' Your changed selection was kept.':''));
    }
  }catch(err){assetMessage(err.message,true);message(err.message,true);}
});
// A thumbnail the server cannot produce (unreadable image, older server) falls back once to the original file.
document.addEventListener('error',e=>{const image=e.target;if(image?.tagName!=='IMG'||!image.dataset?.fullSrc||!image.isConnected||!image.getAttribute('src'))return;const full=image.dataset.fullSrc;delete image.dataset.fullSrc;image.src=full;},true);
document.addEventListener('change',e=>{const id=e.target.dataset.assetCheck;if(id){if(e.target.checked&&!assetSelection.has(id)&&assetSelection.size>=assetSelectionLimit){e.target.checked=false;assetMessage('Choose at most '+assetSelectionLimit+' assets per action. Your existing selection is unchanged.',true);return;}e.target.checked?assetSelection.add(id):assetSelection.delete(id);e.target.closest('.asset-card').classList.toggle('is-selected',e.target.checked);renderAssetSelection();}});
// Reload recovery is read-only until the operator chooses Check or Retry.
try{
  assetRetainedDetail=assetRecovery.read('detail');
  const library=assetRecovery.read('library');
  if(library){assetLibraryPending={...library.operation,selection:library.selection};assetRetainedSelection=library.selection;}
}catch(error){assetRecoveryError=assetRecoveryLoadError=error.message;}
// Grouping is a local view preference only; losing it never loses an asset or a review.
try{const stored=localStorage.getItem(assetGroupStorageKey);if(assetGroupModes.includes(stored)){assetGroupMode=stored;$('#assetGroup').value=stored;}}catch(error){}
try{const stored=localStorage.getItem(assetSourceStorageKey);if(assetSourceModes.includes(stored))assetSourceMode=stored;}catch(error){}
renderAssetReasons();renderLibraryRecovery();
