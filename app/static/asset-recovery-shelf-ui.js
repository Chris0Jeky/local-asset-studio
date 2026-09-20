/* Local shelf controls. Import/restore never call api(), post(), or generation. */
let assetShelfStore=StudioAssetRecoveryShelf.create({storage:()=>localStorage,locks:()=>navigator.locks});
let assetShelfSession=StudioAssetRecoveryShelfSession.create({journal:assetRecovery,store:assetShelfStore,onStatus:assetShelfStatus});
let assetShelfRecords=[],assetShelfImported=null,assetShelfReading=false,assetShelfChanging=false,assetShelfReadEpoch=0,assetShelfImportEpoch=0,assetShelfReturnFocus=null;
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
  return (record.slot==='detail'?payload.draft.title||payload.id:'Library selection ('+command.ids.length+' assets)')+
    ' · '+(command?'Unconfirmed '+command.action+' · '+command.request_id:'Editable draft')+
    ' · Workspace '+(record.workspace_id||'unknown')+' · '+new Date(record.updated_at).toLocaleString();
}
function assetShelfRender(){
  const panel=document.getElementById('assetShelfRecords');
  panel.innerHTML=assetShelfRecords.length?assetShelfRecords.map(r=>{
    const foreign=!r.workspace_id||r.workspace_id!==assetState.workspace_id;
    return '<article class="asset-shelf-record"><h3>'+esc(assetShelfSummary(r))+'</h3>'+
      (foreign?'<p>Another or unknown Workspace: inspect, export or discard only.</p>':'<p>Local evidence, not current saved metadata. Restoring sends no save.</p>')+
      '<div class="asset-shelf-actions"><button type="button" data-shelf-inspect="'+r.id+'">Inspect</button><button type="button" data-shelf-restore="'+r.id+'"'+(foreign?' disabled':'')+'>Restore to this tab</button><button type="button" data-shelf-export="'+r.id+'">Export record</button><button type="button" data-shelf-discard="'+r.id+'">Discard record</button></div></article>';
  }).join(''):'<p>No recovery records on this origin. Enable device checkpoints to retain future detail and library updates.</p>';
  document.getElementById('assetShelfCount').textContent=assetShelfRecords.length+' of '+StudioAssetRecoveryShelf.LIMITS.records+' records. No automatic eviction or expiry.';
}
async function assetShelfRefresh(){
  const epoch=++assetShelfReadEpoch;assetShelfReading=true;
  try{
    const records=await assetShelfStore.list();if(epoch!==assetShelfReadEpoch)return;
    assetShelfRecords=records;assetShelfRender();document.getElementById('assetShelfRawExport').hidden=true;
  }catch(error){
    if(epoch!==assetShelfReadEpoch)return;
    assetShelfRecords=[];assetShelfRender();assetShelfStatus(error.message+' Retained bytes were not replaced.',true);
    document.getElementById('assetShelfRawExport').hidden=false;
  }finally{if(epoch===assetShelfReadEpoch)assetShelfReading=false;}
}
async function assetShelfAction(action){
  if(assetShelfChanging)return;
  assetShelfChanging=true;document.getElementById('assetShelfEnabled').disabled=true;
  try{await action();}catch(error){assetShelfStatus(error.message,true);}
  finally{assetShelfChanging=false;document.getElementById('assetShelfEnabled').disabled=false;document.getElementById('assetShelfEnabled').checked=assetShelfSession.enabled;}
}
function assetShelfInspect(record){
  const panel=document.getElementById('assetShelfInspection'),raw=JSON.stringify(record.payload,null,2);
  panel.hidden=false;panel.querySelector('h3').textContent=assetShelfSummary(record);
  panel.querySelector('pre').textContent=raw.slice(0,32000)+(raw.length>32000?'\n[Preview limited to 32,000 characters. Export retains the complete record.]':'');
  panel.querySelector('p').textContent='SHA-256 '+record.sha256+'. This detects corruption, not authenticity. Imported text is never executable.';
}
(function installAssetRecoveryShelf(){
  const library=document.createElement('div');library.className='asset-shelf-launch';
  library.innerHTML='<button type="button" id="openAssetRecoveryShelf">Local recovery shelf</button><small id="assetShelfLocalStatus" role="status">Device persistence is optional. The existing tab journal remains active.</small>';
  document.getElementById('assetCommandRecovery').before(library);
  const detail=document.createElement('div');detail.className='asset-shelf-launch';
  detail.innerHTML='<button type="button" id="openAssetRecoveryShelfDetails">Local recovery shelf</button><small id="assetShelfDetailStatus" role="status">Keep a device checkpoint before closing this tab.</small>';
  // Keep the established Notes → Save keyboard path; the optional shelf follows actions.
  document.getElementById('saveAssetDetails').parentElement.after(detail);
  const dialog=document.createElement('dialog');dialog.id='assetRecoveryShelfDialog';dialog.setAttribute('aria-labelledby','assetShelfTitle');
  dialog.innerHTML='<div class="asset-shelf-heading"><h2 id="assetShelfTitle">Local recovery shelf</h2><button type="button" id="closeAssetRecoveryShelf" aria-label="Close local recovery shelf">Close</button></div>'+
    '<p>Optional review-text recovery on this browser origin, including drafts and exact unconfirmed metadata commands. No media or model files are included. Clearing browser data removes it. Export files contain your review text; store them privately.</p>'+
    '<label class="asset-shelf-opt"><input type="checkbox" id="assetShelfEnabled">Keep detail and library recovery on this device for this tab</label>'+
    '<p>Wait for “checkpoint verified” before closing. Clearing a tab record or disabling checkpoints does not delete shelf records or cancel server work. Review-queue bulk shortcuts are not included in this shelf.</p>'+
    '<p id="assetShelfStatus" role="status" aria-live="polite"></p><p id="assetShelfCount"></p>'+
    '<div class="asset-shelf-actions"><button type="button" id="assetShelfRefresh">Refresh local records</button><button type="button" id="assetShelfExport">Export shelf</button><button type="button" id="assetShelfRawExport" hidden>Export retained raw evidence</button></div>'+
    '<label>Inspect a recovery JSON bundle (at most 2 MiB)<input id="assetShelfImport" type="file" accept=".json,application/json"></label>'+
    '<section id="assetShelfImportPreview" hidden><h3>Inspected import</h3><p></p><button type="button" id="assetShelfImportConfirm">Import inspected records locally</button></section>'+
    '<div id="assetShelfRecords"></div><section id="assetShelfInspection" hidden><h3></h3><p></p><pre tabindex="0" aria-label="Retained recovery text"></pre></section>';
  document.body.append(dialog);
  const open=event=>{
    assetShelfReturnFocus=event.currentTarget;document.getElementById('assetShelfEnabled').checked=assetShelfSession.enabled;
    if(!dialog.open)dialog.showModal();void assetShelfRefresh();
  };
  document.getElementById('openAssetRecoveryShelf').onclick=open;document.getElementById('openAssetRecoveryShelfDetails').onclick=open;
  document.getElementById('closeAssetRecoveryShelf').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{
    if(dialog.open)return;
    assetShelfReadEpoch++;assetShelfImportEpoch++;assetShelfReading=false;assetShelfImported=null;
    document.getElementById('assetShelfImportPreview').hidden=true;document.getElementById('assetShelfImport').value='';
    if(assetShelfReturnFocus?.isConnected)assetShelfReturnFocus.focus();
  });
  document.getElementById('assetShelfEnabled').onchange=event=>void assetShelfAction(async()=>{
    const enable=event.target.checked;
    if(assetDetailBusy||assetLibraryBusy){event.target.checked=assetShelfSession.enabled;throw Error('Wait for the current metadata operation before changing device persistence.');}
    const raw=enable?'1':'0';sessionStorage.setItem(assetShelfOptKey,raw);
    if(sessionStorage.getItem(assetShelfOptKey)!==raw){event.target.checked=assetShelfSession.enabled;throw Error('The tab preference could not be retained safely.');}
    if(enable){if(document.getElementById('assetDialog').open)retainAssetDraft();await assetShelfSession.enable();}
    else await assetShelfSession.disable();
    await assetShelfRefresh();
  });
  document.getElementById('assetShelfRefresh').onclick=()=>void assetShelfRefresh();
  document.getElementById('assetShelfExport').onclick=()=>void assetShelfAction(async()=>assetShelfDownload(await assetShelfStore.export(),'asset-review-recovery.json'));
  document.getElementById('assetShelfRawExport').onclick=()=>void assetShelfAction(async()=>{
    const raw=assetShelfStore.raw();if(raw!==null)assetShelfDownload(raw,'unverified-asset-review-recovery.json');
  });
  document.getElementById('assetShelfImport').onchange=event=>{
    const file=event.target.files?.[0],epoch=++assetShelfImportEpoch;assetShelfImported=null;document.getElementById('assetShelfImportPreview').hidden=true;
    void assetShelfAction(async()=>{
      if(!file)return;if(file.size>StudioAssetRecoveryShelf.LIMITS.total)throw Error('Recovery import exceeds 2 MiB; no content was read.');
      const records=await StudioAssetRecoveryShelf.decode(await assetShelfImportText(file));
      if(epoch!==assetShelfImportEpoch||!dialog.open)return;
      assetShelfImported=records;const preview=document.getElementById('assetShelfImportPreview');preview.hidden=false;
      preview.querySelector('p').textContent=records.length+' records inspected; nothing stored or sent. '+records.map(assetShelfSummary).join('\n');
      assetShelfStatus('Import inspected. Choose Import inspected records locally to store it. Restoration is a separate action.');
    });
  };
  document.getElementById('assetShelfImportConfirm').onclick=()=>void assetShelfAction(async()=>{
    const inspected=assetShelfImported;if(!inspected)throw Error('Inspect a valid bundle first.');
    await assetShelfStore.importRecords(inspected);assetShelfImported=null;document.getElementById('assetShelfImportPreview').hidden=true;
    assetShelfStatus('Imported locally. No draft restored, receipt queried, metadata saved or job submitted.');await assetShelfRefresh();
  });
  dialog.addEventListener('click',event=>{
    const button=event.target.closest('[data-shelf-inspect],[data-shelf-restore],[data-shelf-export],[data-shelf-discard]');if(!button||button.disabled)return;
    const action=['inspect','restore','export','discard'].find(a=>button.hasAttribute('data-shelf-'+a)),record=assetShelfRecords.find(r=>r.id===button.getAttribute('data-shelf-'+action));
    if(!record)return;
    void assetShelfAction(async()=>{
      if(action==='inspect'){assetShelfInspect(record);return;}
      if(action==='export'){assetShelfDownload(await StudioAssetRecoveryShelf.encode([record]),'asset-review-'+record.id+'.json');return;}
      if(action==='discard'){
        if(!window.confirm('Discard only this local recovery record? Its command may already have committed. This does not cancel or undo server work. Export first to keep a copy.'))return;
        await assetShelfSession.discard(record);
        await assetShelfRefresh();assetShelfStatus('Local record discarded. No server change was made.');document.getElementById('assetShelfRefresh').focus();return;
      }
      if(document.getElementById('assetDialog').open||assetDetailBusy||assetLibraryBusy)throw Error('Close the asset editor before restoring. Its current typing must not be replaced.');
      await assetShelfSession.flush();const latest=(await assetShelfStore.list()).find(r=>r.id===record.id);
      if(latest?.sha256!==record.sha256)throw Error('Recovery changed since inspection. Refresh to compare it; no draft was replaced.');
      if(!dialog.open||document.getElementById('assetDialog').open||assetDetailBusy||assetLibraryBusy)throw Error('The editor changed during inspection; no draft was replaced.');
      const value=assetShelfSession.restore(record,assetState.workspace_id);
      if(record.slot==='detail')assetRetainedDetail=value;
      else {assetLibraryPending={...value.operation,selection:value.selection};assetRetainedSelection=value.selection;}
      renderLibraryRecovery();dialog.close();assetMessage('Recovery restored to this tab only. Review its draft or explicitly check its receipt; no save was sent.');
    });
  });
  try{if(sessionStorage.getItem(assetShelfOptKey)==='1'){document.getElementById('assetShelfEnabled').checked=true;void assetShelfSession.enable().catch(error=>assetShelfStatus(error.message,true));}}
  catch(error){assetShelfStatus('Device preference is unavailable. The session journal remains separate.',true);}
})();
