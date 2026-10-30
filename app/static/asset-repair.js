/* #1837: "Import repaired version" from an opened picture. The server validates the parent and records the link; this only asks, with the picture's own privacy. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetRepair=api;
})(globalThis,function(){
  'use strict';
  const NOTE_MAX=280,SIZE_MAX=20*1024*1024;
  const privacyOf=asset=>asset?.privacy===undefined?'regular':asset.privacy;
  // The reason this picture cannot take a repair right now, '' when it can. Dynamic flags come from the detail editor's own busy state.
  function blocked(asset,state={}){
    if(!asset)return 'Open a picture first.';
    if(asset.media_type!=='image')return 'Only a picture can have a repaired version.';
    if(asset.trashed_at)return 'This picture is in the Bin. Restore it before importing its repair.';
    if(!['regular','private'].includes(privacyOf(asset)))return 'This picture has no valid privacy classification.';
    if(state.importing)return 'An import is already running. Wait for it to finish.';
    if(state.busy)return 'A save is still pending. Wait for it to finish.';
    if(state.pending||state.conflict)return 'Settle the earlier save of this picture first.';
    return '';
  }
  function fileProblem(file){
    if(!file)return 'Choose the repaired PNG.';
    if(file.type!=='image/png')return 'Choose a PNG file. Other formats cannot be imported as a repair yet.';
    if(!file.size)return file.name+' is empty.';
    if(file.size>SIZE_MAX)return file.name+' exceeds 20 MiB.';
    return '';
  }
  const cleanNote=note=>String(note??'').split(/\s+/).filter(Boolean).join(' ');
  function noteProblem(note){return cleanNote(note).length>NOTE_MAX?'Keep the note to '+NOTE_MAX+' characters.':'';}
  // The same privacy scope and creation destination as the parent: a repair never crosses between Regular and Private.
  function request(asset,file,note){
    const privacy=privacyOf(asset),text=cleanNote(note);
    return {path:'/api/assets/import',options:{method:'POST',body:file,headers:{'Content-Type':'image/png',
      'X-Filename':/^[\x20-\x7e]*$/.test(file.name)?file.name:'repaired.png','X-Studio-Privacy':privacy,'X-Studio-Creation-Privacy':privacy,
      'X-Parent-Asset':asset.id,...(text?{'X-Editor-Note':encodeURIComponent(text)}:{})}}};
  }
  // One import. `current()` says whether the editor still shows this picture; the result is returned either way so the caller can still report the link.
  async function submit({asset,file,note,state,api,current}){
    const problem=blocked(asset,state())||fileProblem(file)||noteProblem(note);if(problem)throw Error(problem);
    const {path,options}=request(asset,file,note),result=await api(path,options);
    if(!result?.asset?.id||!Array.isArray(result.asset.lineage)||!result.asset.lineage.includes(asset.id))throw Error('The picture was imported but its link to this one was not confirmed. Check the family before importing again.');
    return {id:result.asset.id,parent:asset.id,current:current()};
  }
  return {blocked,fileProblem,noteProblem,request,submit,NOTE_MAX};
});

(function(){
  'use strict';
  if(typeof document==='undefined'||typeof module==='object'||!document.querySelector('#assetRepair'))return;
  const q=s=>document.querySelector(s),R=globalThis.StudioAssetRepair;
  let importing=false;
  const state=()=>({busy:assetDetailBusy,pending:!!assetDetailPending,conflict:!!assetDetailConflict,importing});
  function say(text,error=false){const line=q('#assetRepairStatus');line.textContent=text;line.classList.toggle('error',error);}
  // Static reasons (kind, Bin, privacy) disable the controls and say why; busy reasons are checked again when the button is pressed.
  function sync(){
    const asset=q('#assetDialog').open?activeAsset:null,why=R.blocked(asset,{}),open=q('#assetRepairOpen');
    for(const id of ['#assetRepairFile','#assetRepairNote','#assetRepairImport'])q(id).disabled=!!why||importing;
    q('#assetRepairImport').title=why;
    if(why){open.hidden=true;say(why);}
  }
  q('#assetRepair').addEventListener('toggle',sync);
  new MutationObserver(()=>{q('#assetRepairOpen').hidden=true;q('#assetRepairFile').value='';q('#assetRepairNote').value='';say('');sync();}).observe(q('#assetDetailMedia'),{childList:true});
  q('#assetRepairImport').onclick=async()=>{
    const asset=activeAsset,id=asset?.id,epoch=assetDetailEpoch,workspace=assetState.workspace_id,file=q('#assetRepairFile').files[0],open=q('#assetRepairOpen');
    open.hidden=true;
    try{
      // submit() checks the reasons synchronously before its first await, so the single-flight flag goes up only after it has started.
      const run=R.submit({asset,file,note:q('#assetRepairNote').value,state,api,current:()=>assetDetailContextCurrent(id,epoch)&&assetState.workspace_id===workspace});
      importing=true;sync();say('Importing the repaired version… Nothing is generated.');
      const done=await run;
      try{await refreshAssets(true);}catch(_){/* The import is already confirmed; the library refreshes on its next read. */}
      const text='Imported. The new picture is linked as a repair of this one, unreviewed. This picture is unchanged.';
      if(done.current){q('#assetRepairFile').value='';q('#assetRepairNote').value='';open.dataset.id=done.id;open.hidden=false;say(text);}
      else message(text);
    }catch(error){say(error.message,true);}
    finally{importing=false;sync();}
  };
  q('#assetRepairOpen').onclick=async()=>{const id=q('#assetRepairOpen').dataset.id;if(id&&await openAsset(id)===false)say('The repaired picture could not be opened. Find it in the Library.',true);};
})();
