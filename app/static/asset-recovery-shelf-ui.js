/* Local shelf controls. Import/restore never call api(), post(), or generation. */
const assetShelfScope=()=>typeof assetPrivacyScope==='function'?assetPrivacyScope():'regular';
const assetShelfRecordScope=record=>record.privacy||'regular';
const assetShelfStores=new Map(),assetShelfSessions=new Map();
function assetShelfStoreFor(scope){
  if(!assetShelfStores.has(scope))assetShelfStores.set(scope,scope==='regular'?StudioAssetRecoveryShelf.create({storage:()=>localStorage,locks:()=>navigator.locks}):StudioAssetRecoveryShelf.createTab({storage:()=>sessionStorage,privacy:scope}));
  return assetShelfStores.get(scope);
}
function assetShelfSessionFor(scope){
  if(!assetShelfSessions.has(scope))assetShelfSessions.set(scope,StudioAssetRecoveryShelfSession.create({journal:typeof assetJournalFor==='function'?assetJournalFor(scope):assetRecovery,store:assetShelfStoreFor(scope),privacy:scope,onStatus:(text,error)=>{if(assetShelfScope()===scope)assetShelfStatus(text,error);}}));
  return assetShelfSessions.get(scope);
}
let assetShelfStore=assetShelfStoreFor(assetShelfScope()),assetShelfSession=assetShelfSessionFor(assetShelfScope());
let assetShelfRecords=[],assetShelfImported=null,assetShelfReading=false,assetShelfChanging=false,assetShelfReadEpoch=0,assetShelfImportEpoch=0,assetShelfReturnFocus=null;
let assetShelfReadError=false,assetShelfLegacyReview=null;
const assetShelfOptKey='studio.asset-recovery.shelf.enabled.v1';
function assetShelfStatus(text,error=false){
  for(const id of ['assetShelfStatus','assetShelfLocalStatus','assetShelfDetailStatus']){
    const element=document.getElementById(id);if(element){element.textContent=text.slice(0,1200);element.classList.toggle('error',error);}
  }
}
function assetShelfDownload(text,name){
  const url=URL.createObjectURL(new Blob([text],{type:'application/json;charset=utf-8'})),a=document.createElement('a');
  a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function assetShelfImportText(file){
  const data=await file.arrayBuffer();
  try{return new TextDecoder('utf-8',{fatal:true}).decode(data);}
  catch(_){throw Error('Recovery import must be valid UTF-8 JSON.');}
}
function assetShelfSummary(record){
  const payload=record.payload,command=payload.operation?.command;
  return (assetShelfRecordScope(record)==='regular'?'':'['+assetShelfRecordScope(record)+'] ')+(record.slot==='detail'?payload.draft.title||payload.id:'Library selection ('+command.ids.length+' assets)')+
    ' · '+(command?'Unconfirmed '+command.action+' · '+command.request_id:'Editable draft')+
    ' · Workspace '+(record.workspace_id||'unknown')+' · '+new Date(record.updated_at).toLocaleString();
}
function assetShelfRender(){
  const panel=document.getElementById('assetShelfRecords');
  if(assetShelfReadError){
    panel.innerHTML='<p>Recovery records could not be read. Retained data has not been replaced. Use the export controls to keep a copy where available.</p>';
    document.getElementById('assetShelfCount').textContent='Record count unavailable.';return;
  }
  panel.innerHTML=assetShelfRecords.length?assetShelfRecords.map(r=>{
    const foreign=!r.workspace_id||r.workspace_id!==assetState.workspace_id;
    const other=assetShelfRecordScope(r)!==assetShelfScope();
    return '<article class="asset-shelf-record"><h3>'+esc(assetShelfSummary(r))+'</h3>'+
      (foreign?'<p>Another or unknown Workspace: inspect, export or discard only.</p>':'<p>Local evidence, not current saved metadata. Restoring sends no save.</p>')+
      '<div class="asset-shelf-actions"><button type="button" data-shelf-inspect="'+r.id+'">Inspect</button><button type="button" data-shelf-observe="'+r.id+'"'+(foreign?' disabled':'')+'>Inspect receipt and current state</button><button type="button" data-shelf-restore="'+r.id+'"'+(foreign||other?' disabled':'')+'>Restore to this tab</button>'+(other?'<button type="button" data-shelf-view="'+assetShelfRecordScope(r)+'">Use '+assetShelfRecordScope(r)+' view to restore</button>':'')+'<button type="button" data-shelf-export="'+r.id+'">Export record</button><button type="button" data-shelf-discard="'+r.id+'">Discard record</button></div></article>';
  }).join(''):'<p>No recovery records in this view. Enable '+(assetShelfScope()==='regular'?'device':'tab')+' checkpoints to retain future detail and library updates.</p>';
  document.getElementById('assetShelfCount').textContent=assetShelfRecords.length+' of '+(StudioAssetRecoveryShelf.LIMITS.records*(assetShelfScope()==='all'?3:1))+' records. No automatic eviction or expiry.';
}
async function assetShelfRefresh(){
  const epoch=++assetShelfReadEpoch;assetShelfReading=true;
  assetShelfLegacyReview=null;document.getElementById('assetShelfAcceptLegacy').hidden=true;
  try{
    const stores=assetShelfScope()==='all'?['regular','private','all'].map(assetShelfStoreFor):[assetShelfStore];
    const [records,legacy]=await Promise.allSettled([Promise.all(stores.map(store=>store.list())).then(parts=>parts.flat()),assetShelfStore.legacyRaw()]);if(epoch!==assetShelfReadEpoch)return;
    // The older bytes stay exportable even when the current owner cannot be read.
    // An unavailable legacy read leaves its explicit export control discoverable.
    const older=legacy.status==='rejected'||legacy.value!==null;
    document.getElementById('assetShelfLegacyExport').hidden=!older;
    document.getElementById('assetShelfLegacyNotice').hidden=!older;
    if(records.status==='rejected')throw records.reason;
    const recovered=assetShelfReadError;assetShelfReadError=false;
    if(new Set(records.value.map(record=>record.id)).size!==records.value.length)throw Error('Recovery identities occur in more than one view. Choose the individual privacy view to inspect them.');
    assetShelfRecords=records.value;assetShelfRender();document.getElementById('assetShelfRawExport').hidden=true;
    if(recovered)assetShelfStatus('Local recovery records read. No server changes were made.');
  }catch(error){
    if(epoch!==assetShelfReadEpoch)return;
    assetShelfReadError=true;assetShelfRecords=[];assetShelfRender();assetShelfStatus(error.message+' Retained bytes were not replaced.',true);
    assetShelfLegacyReview=error.code==='asset_recovery_legacy_changed'?error.review||null:null;
    document.getElementById('assetShelfAcceptLegacy').hidden=!assetShelfLegacyReview;
    if(assetShelfLegacyReview)document.getElementById('assetShelfLegacyNotice').hidden=false;
    document.getElementById('assetShelfRawExport').hidden=false;
  }finally{if(epoch===assetShelfReadEpoch)assetShelfReading=false;}
}
async function assetShelfAction(action){
  if(assetShelfChanging)return;
  const scope=assetShelfScope(),epoch=assetShelfPrivacyEpoch;assetShelfChanging=true;document.getElementById('assetShelfEnabled').disabled=true;
  try{await action(()=>epoch===assetShelfPrivacyEpoch&&scope===assetShelfScope());}catch(error){if(epoch===assetShelfPrivacyEpoch&&scope===assetShelfScope())assetShelfStatus(error.message,true);}
  finally{if(epoch===assetShelfPrivacyEpoch){assetShelfChanging=false;document.getElementById('assetShelfEnabled').disabled=false;document.getElementById('assetShelfEnabled').checked=assetShelfSession.enabled;}}
}
function assetShelfInspect(record){
  const panel=document.getElementById('assetShelfInspection'),raw=JSON.stringify(record.payload,null,2);
  panel.hidden=false;panel.querySelector('h3').textContent=assetShelfSummary(record);
  panel.querySelector('pre').textContent=raw.slice(0,32000)+(raw.length>32000?'\n[Preview limited to 32,000 characters. Export retains the complete record.]':'');
  panel.querySelector('p').textContent='SHA-256 '+record.sha256+'. This detects corruption, not authenticity. Imported text is never executable.';
}
(function installAssetRecoveryShelf(){
  const library=document.createElement('div');library.className='asset-shelf-launch';
  library.innerHTML='<details id="assetRecoveryDisclosure"><summary>Recovery</summary><div><button type="button" id="openAssetRecoveryShelf">Local recovery shelf</button><small id="assetShelfLocalStatus" role="status">Device persistence is optional. The existing tab journal remains active.</small></div></details>';
  document.getElementById('assetCommandRecovery').before(library);
  const detail=document.createElement('div');detail.className='asset-shelf-launch';
  detail.innerHTML='<button type="button" id="openAssetRecoveryShelfDetails">Local recovery shelf</button><small id="assetShelfDetailStatus" role="status">Keep a device checkpoint before closing this tab.</small>';
  // Keep the established Notes → Save keyboard path; the optional shelf follows actions.
  document.getElementById('saveAssetDetails').parentElement.after(detail);
  const dialog=document.createElement('dialog');dialog.id='assetRecoveryShelfDialog';dialog.setAttribute('aria-labelledby','assetShelfTitle');
  dialog.innerHTML='<div class="asset-shelf-heading"><h2 id="assetShelfTitle">Local recovery shelf</h2><button type="button" id="closeAssetRecoveryShelf" aria-label="Close local recovery shelf">Close</button></div>'+
    '<p id="assetShelfStorageDescription">Optional review-text recovery on this browser origin, including drafts and exact unconfirmed metadata commands. No media or model files are included. Clearing browser data removes it. Export files contain your review text; store them privately.</p>'+
    '<label class="asset-shelf-opt"><input type="checkbox" id="assetShelfEnabled"><span id="assetShelfRetentionLabel">Keep detail and library recovery on this device for this tab</span></label>'+
    '<p id="assetShelfCheckpointHelp">Wait for “checkpoint verified” before closing. Clearing a tab record or disabling checkpoints does not delete shelf records or cancel server work. Review-queue bulk shortcuts are not included in this shelf.</p>'+
    '<p id="assetShelfStatus" role="status" aria-live="polite"></p><p id="assetShelfCount"></p>'+
    '<div class="asset-shelf-actions"><button type="button" id="assetShelfRefresh">Refresh local records</button><button type="button" id="assetShelfExport">Export shelf</button><button type="button" id="assetShelfRawExport" hidden>Export retained raw evidence</button><button type="button" id="assetShelfLegacyExport" hidden>Export older recovery</button><button type="button" id="assetShelfAcceptLegacy" hidden>Continue with current shelf</button></div>'+
    '<p id="assetShelfLegacyNotice" hidden>Recovery data saved by an older Studio version stays separate and can be exported. Close or reload older Studio tabs before continuing. Continuing with the current shelf does not merge or delete the older data.</p>'+
    '<div class="asset-shelf-actions"><button type="button" data-recovery-observe-slot="detail">Inspect this tab’s asset recovery</button><button type="button" data-recovery-observe-slot="library">Inspect this tab’s library recovery</button></div>'+
    '<label>Inspect a recovery JSON bundle (at most 2 MiB)<input id="assetShelfImport" type="file" accept=".json,application/json"></label>'+
    '<section id="assetShelfImportPreview" hidden><h3>Inspected import</h3><p></p><button type="button" id="assetShelfImportConfirm">Import inspected records locally</button></section>'+
    '<div id="assetShelfRecords"></div><section id="assetShelfInspection" hidden><h3></h3><p></p><pre tabindex="0" aria-label="Retained recovery text"></pre></section>';
  document.body.append(dialog);
  const open=event=>{
    assetShelfReturnFocus=event.currentTarget;document.getElementById('assetShelfEnabled').checked=assetShelfSession.enabled;
    if(!dialog.open){
      // A queued close event can arrive after this opening and must not preserve
      // the previous dialog's pending file read or inspected import.
      assetShelfImportEpoch++;assetShelfImported=null;document.getElementById('assetShelfImportPreview').hidden=true;document.getElementById('assetShelfImport').value='';
      dialog.showModal();
    }
    void assetShelfRefresh();
  };
  document.getElementById('openAssetRecoveryShelf').onclick=open;document.getElementById('openAssetRecoveryShelfDetails').onclick=open;
  document.getElementById('closeAssetRecoveryShelf').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{
    if(dialog.open)return;
    assetShelfReadEpoch++;assetShelfImportEpoch++;assetShelfReading=false;assetShelfImported=null;
    assetShelfLegacyReview=null;document.getElementById('assetShelfAcceptLegacy').hidden=true;
    document.getElementById('assetShelfImportPreview').hidden=true;document.getElementById('assetShelfImport').value='';
    if(assetShelfReturnFocus?.isConnected)assetShelfReturnFocus.focus();
  });
  document.getElementById('assetShelfEnabled').onchange=event=>void assetShelfAction(async current=>{
    const enable=event.target.checked;
    if(assetDetailBusy||assetLibraryBusy){event.target.checked=assetShelfSession.enabled;throw Error('Wait for the current metadata operation before changing device persistence.');}
    const storage=typeof assetPrivacyStorage==='function'?assetPrivacyStorage():sessionStorage,raw=enable?'1':'0';storage.setItem(assetShelfOptKey,raw);
    if(storage.getItem(assetShelfOptKey)!==raw){event.target.checked=assetShelfSession.enabled;throw Error('The tab preference could not be retained safely.');}
    if(enable){if(document.getElementById('assetDialog').open)retainAssetDraft();await assetShelfSession.enable();}
    else await assetShelfSession.disable();
    if(current())await assetShelfRefresh();
  });
  document.getElementById('assetShelfRefresh').onclick=()=>void assetShelfRefresh();
  document.getElementById('assetShelfExport').onclick=()=>void assetShelfAction(async current=>{const raw=await assetShelfStore.export();if(current())assetShelfDownload(raw,'asset-review-recovery.json');});
  document.getElementById('assetShelfRawExport').onclick=()=>void assetShelfAction(async current=>{
    const raw=await assetShelfStore.raw();if(!current())return;if(raw!==null)assetShelfDownload(raw,'unverified-asset-review-recovery.json');
    else assetShelfStatus('No retained raw recovery data is available.');
  });
  document.getElementById('assetShelfLegacyExport').onclick=()=>void assetShelfAction(async current=>{
    const raw=await assetShelfStore.legacyRaw();if(!current())return;if(raw!==null)assetShelfDownload(raw,'older-asset-review-recovery.json');
    else assetShelfStatus('No older recovery data is available.');
  });
  document.getElementById('assetShelfAcceptLegacy').onclick=()=>void assetShelfAction(async()=>{
    const review=assetShelfLegacyReview,epoch=assetShelfReadEpoch;
    const current=()=>dialog.open&&assetShelfReadEpoch===epoch&&assetShelfLegacyReview===review;
    if(!review||!current())throw Error('Refresh local records and inspect the older recovery warning before continuing.');
    if(!window.confirm('Continue using the current shelf records? Older recovery data stays separate and can be exported. Close or reload older Studio tabs first. Nothing will be merged or deleted.'))return;
    if(!current())return;
    try{await assetShelfStore.acceptLegacy(review);}
    catch(error){if(!current())return;throw error;}
    if(!current())return;
    const button=document.getElementById('assetShelfAcceptLegacy'),moveFocus=document.activeElement===button,refreshEpoch=assetShelfReadEpoch+1;
    assetShelfStatus('Continuing with the current shelf. Older recovery data remains separately available to export.');
    await assetShelfRefresh();
    if(moveFocus&&dialog.open&&assetShelfReadEpoch===refreshEpoch&&(document.activeElement===button||document.activeElement===document.body))document.getElementById('assetShelfRefresh').focus();
  });
  document.getElementById('assetShelfImport').onchange=event=>{
    const file=event.target.files?.[0],epoch=++assetShelfImportEpoch;assetShelfImported=null;document.getElementById('assetShelfImportPreview').hidden=true;
    void assetShelfAction(async()=>{
      if(!file)return;if(file.size>StudioAssetRecoveryShelf.LIMITS.total)throw Error('Recovery import exceeds 2 MiB; no content was read.');
      let records;
      try{records=await StudioAssetRecoveryShelf.decode(await assetShelfImportText(file));}
      catch(error){if(epoch!==assetShelfImportEpoch||!dialog.open)return;throw error;}
      if(epoch!==assetShelfImportEpoch||!dialog.open)return;
      if(assetShelfScope()!=='all'&&records.some(record=>assetShelfRecordScope(record)!==assetShelfScope()))throw Error('Choose the matching privacy view, or All, before inspecting this recovery bundle.');
      assetShelfImported=records;const preview=document.getElementById('assetShelfImportPreview');preview.hidden=false;
      preview.querySelector('p').textContent=records.length+' records inspected; nothing stored or sent. '+records.map(assetShelfSummary).join('\n');
      assetShelfStatus('Import inspected. Choose Import inspected records locally to store it. Restoration is a separate action.');
    });
  };
  document.getElementById('assetShelfImportConfirm').onclick=()=>void assetShelfAction(async()=>{
    const inspected=assetShelfImported,epoch=assetShelfImportEpoch;if(!inspected)throw Error('Inspect a valid bundle first.');
    try{await assetShelfStore.importRecords(inspected);}
    catch(error){if(epoch!==assetShelfImportEpoch||!dialog.open||assetShelfImported!==inspected)return;throw error;}
    if(epoch!==assetShelfImportEpoch||!dialog.open||assetShelfImported!==inspected)return;
    const confirm=document.getElementById('assetShelfImportConfirm'),moveFocus=document.activeElement===confirm;
    assetShelfImported=null;document.getElementById('assetShelfImportPreview').hidden=true;
    assetShelfStatus('Imported locally. No draft restored, receipt queried, metadata saved or job submitted.');await assetShelfRefresh();
    if(moveFocus&&epoch===assetShelfImportEpoch&&dialog.open&&(document.activeElement===confirm||document.activeElement===document.body)){
      const first=inspected[0]&&document.querySelector('[data-shelf-inspect="'+inspected[0].id+'"]');
      (first||document.getElementById('assetShelfImport')).focus();
    }
  });
  dialog.addEventListener('click',event=>{
    const view=event.target.closest('[data-shelf-view]');if(view){window.StudioPrivacy?.setScope?.(view.dataset.shelfView);return;}
    const button=event.target.closest('[data-shelf-inspect],[data-shelf-restore],[data-shelf-export],[data-shelf-discard]');if(!button||button.disabled)return;
    const action=['inspect','restore','export','discard'].find(a=>button.hasAttribute('data-shelf-'+a)),record=assetShelfRecords.find(r=>r.id===button.getAttribute('data-shelf-'+action));
    if(!record)return;
    void assetShelfAction(async current=>{
      if(action==='inspect'){assetShelfInspect(record);return;}
      if(action==='export'){const raw=await StudioAssetRecoveryShelf.encode([record]);if(current())assetShelfDownload(raw,'asset-review-'+record.id+'.json');return;}
      if(action==='discard'){
        if(!window.confirm('Discard only this local recovery record? Its command may already have committed. This does not cancel or undo server work. Export first to keep a copy.'))return;
        await assetShelfSessionFor(assetShelfRecordScope(record)).discard(record);
        if(!current())return;await assetShelfRefresh();if(!current())return;assetShelfStatus('Local record discarded. No server change was made.');document.getElementById('assetShelfRefresh').focus();return;
      }
      if(document.getElementById('assetDialog').open||assetDetailBusy||assetLibraryBusy)throw Error('Close the asset editor before restoring. Its current typing must not be replaced.');
      if(assetShelfRecordScope(record)!==assetShelfScope())throw Error('Choose the '+assetShelfRecordScope(record)+' view before restoring this recovery.');
      // Restore is a local journal operation. Re-read and compare the selected record without flushing unrelated checkpoints; a stale error must not block a still-current restore.
      const latest=(await assetShelfStore.list()).find(r=>r.id===record.id);
      if(!current())return;
      if(latest?.sha256!==record.sha256)throw Error('Recovery changed since inspection. Refresh to compare it; no draft was replaced.');
      if(!dialog.open||document.getElementById('assetDialog').open||assetDetailBusy||assetLibraryBusy)throw Error('The editor changed during inspection; no draft was replaced.');
      const value=assetShelfSession.restore(record,assetState.workspace_id);
      if(record.slot==='detail')assetRetainedDetail=value;
      else {assetLibraryPending={...value.operation,selection:value.selection};assetRetainedSelection=value.selection;}
      renderLibraryRecovery();dialog.close();assetMessage('Recovery restored to this tab only. Review its draft or explicitly check its receipt; no save was sent.');
    });
  });
  try{if((typeof assetPrivacyStorage==='function'?assetPrivacyStorage():sessionStorage).getItem(assetShelfOptKey)==='1'){document.getElementById('assetShelfEnabled').checked=true;void assetShelfSession.enable().catch(error=>assetShelfStatus(error.message,true));}}
  catch(error){assetShelfStatus('Device preference is unavailable. The session journal remains separate.',true);}
})();
let assetShelfPrivacyEpoch=0;
function assetShelfPrivacyLabels(){
  const privateView=assetShelfScope()!=='regular';
  const label=document.getElementById('assetShelfRetentionLabel');if(label)label.textContent=privateView?'Keep review checkpoints in this tab only':'Keep detail and library recovery on this device for this tab';
  document.getElementById('assetShelfStorageDescription').textContent=privateView?'Private and All recovery stays in this tab and can survive a reload here. Closing the tab removes this recovery. No media or model files are included. Export files contain your review text; store them privately.':'Optional review-text recovery on this browser origin, including drafts and exact unconfirmed metadata commands. No media or model files are included. Clearing browser data removes it. Export files contain your review text; store them privately.';
  document.getElementById('assetShelfCheckpointHelp').textContent=privateView?'Wait for “checkpoint verified” before reloading this tab. Export first to keep a copy after closing. Disabling checkpoints does not delete existing records or cancel server work. Review-queue bulk shortcuts are not included in this shelf.':'Wait for “checkpoint verified” before closing. Clearing a tab record or disabling checkpoints does not delete shelf records or cancel server work. Review-queue bulk shortcuts are not included in this shelf.';
  document.getElementById('assetShelfExport').textContent='Export '+assetShelfScope()+' view recovery';
  if(privateView)assetShelfStatus('Private and All recovery stays in this tab. Device persistence is unavailable in these views.');
}
assetShelfPrivacyLabels();
document.addEventListener?.('studio:privacy-change',event=>{
  if(event.detail?.previousScope===event.detail?.scope)return;
  assetShelfPrivacyEpoch++;assetShelfReadEpoch++;assetShelfImportEpoch++;assetShelfReading=false;assetShelfChanging=false;
  const dialog=document.getElementById('assetRecoveryShelfDialog');assetShelfReturnFocus=null;if(dialog.open)dialog.close();
  assetShelfRecords=[];assetShelfImported=null;assetShelfLegacyReview=null;assetShelfReadError=false;
  for(const id of ['assetShelfAcceptLegacy','assetShelfLegacyNotice','assetShelfLegacyExport','assetShelfRawExport'])document.getElementById(id).hidden=true;
  for(const id of ['assetShelfRecords','assetShelfInspection','assetShelfImportPreview']){const node=document.getElementById(id);node.hidden=id!=='assetShelfRecords';if(id==='assetShelfRecords')node.innerHTML='';else for(const tag of ['pre','p','h3']){const child=node.querySelector?.(tag);if(child)child.textContent='';}}
  document.getElementById('assetShelfImport').value='';
  assetShelfStore=assetShelfStoreFor(assetShelfScope());assetShelfSession=assetShelfSessionFor(assetShelfScope());
  document.getElementById('assetShelfEnabled').disabled=false;document.getElementById('assetShelfEnabled').checked=assetShelfSession.enabled;
  assetShelfStatus('');assetShelfPrivacyLabels();assetShelfRender();
  const scope=assetShelfScope(),epoch=assetShelfPrivacyEpoch,session=assetShelfSession;
  try{if(!session.enabled&&(typeof assetPrivacyStorage==='function'?assetPrivacyStorage():sessionStorage).getItem(assetShelfOptKey)==='1'){
    document.getElementById('assetShelfEnabled').checked=true;
    void session.enable().catch(error=>{if(epoch===assetShelfPrivacyEpoch&&scope===assetShelfScope())assetShelfStatus(error.message,true);});
  }}catch(error){assetShelfStatus('The tab preference is unavailable. Its recovery evidence remains separate.',true);}
});
// The library launch sits behind a Recovery disclosure, closed unless something waits to be recovered.
const baseRenderLibraryRecovery=renderLibraryRecovery;renderLibraryRecovery=function(){baseRenderLibraryRecovery();const panel=document.getElementById('assetRecoveryDisclosure');if(panel&&!panel.open)panel.open=!!(assetLibraryPending||assetRetainedDetail||assetRecoveryError)||assetShelfRecords.length>0;};
