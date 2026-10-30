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
  // One import. The confirmed result is returned; whether the editor still shows this picture is decided later, by settle().
  async function submit({asset,file,note,state,api}){
    const problem=blocked(asset,state())||fileProblem(file)||noteProblem(note);if(problem)throw Error(problem);
    const {path,options}=request(asset,file,note),result=await api(path,options);
    if(!result?.asset?.id||!Array.isArray(result.asset.lineage)||!result.asset.lineage.includes(asset.id))throw Error('The picture was imported but its link to this one was not confirmed. Check the family before importing again.');
    return {id:result.asset.id,parent:asset.id};
  }
  // After the library refresh (which can outlast the owner's navigation) the dialog is only updated if it still shows the parent; otherwise the page-level notice carries the news.
  async function settle(done,{refresh,current,show,notice}){
    try{await refresh();}catch(_){/* The import is already confirmed; the library refreshes on its next read. */}
    if(current())show(done.id,'Imported. The new picture is linked as a repair of this one, unreviewed. This picture is unchanged.');
    else notice('Imported. The new picture is linked as a repair of the picture you were viewing, unreviewed. Find it in the Library.');
  }
  // #1860: Edit in Krita. The server owns the working file and the session; this only asks, with the picture's own privacy, and reports what came back.
  function kritaBlocked(asset,krita,state={},needsKrita=true){
    if(!asset)return 'Open a picture first.';
    if(asset.media_type!=='image')return 'Only a picture can be opened in Krita.';
    if(asset.trashed_at)return 'This picture is in the Bin. Restore it before editing it.';
    if(!['regular','private'].includes(privacyOf(asset)))return 'This picture has no valid privacy classification.';
    if(needsKrita&&krita?.available!==true)return krita?.reason||'Krita availability is not known yet. Reload the page.';
    if(state.running)return 'A Krita step is already running. Wait for it to finish.';
    return '';
  }
  function kritaRequest(asset,step,session){
    const privacy=privacyOf(asset),base='/api/assets/'+encodeURIComponent(asset.id)+'/edit-in-krita';
    return {path:step==='back'?base+'/bring-back':base,options:{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Privacy':privacy,'X-Studio-Creation-Privacy':privacy},
      body:JSON.stringify(step==='back'&&session?{session}:{})}};
  }
  async function kritaStart({asset,krita,state,api}){
    const problem=kritaBlocked(asset,krita,state());if(problem)throw Error(problem);
    const {path,options}=kritaRequest(asset,'start'),session=await api(path,options);
    if(!session?.id||session.asset_id!==asset.id)throw Error('Krita was asked to open the picture but the edit was not confirmed. Check Krita before pressing Bring back.');
    return session;
  }
  // 'unchanged' and 'already_imported' import nothing; 'imported' is trusted only with the recorded link to this picture.
  async function kritaBringBack({asset,session,state,api}){
    const problem=kritaBlocked(asset,null,state(),false);if(problem)throw Error(problem);
    const {path,options}=kritaRequest(asset,'back',session),result=await api(path,options);
    if(result?.status==='unchanged')return {status:'unchanged',text:'Nothing changed since Krita was opened. Save in Krita first (File, Save), then bring it back. Nothing was imported.'};
    if(result?.status==='already_imported'&&result.asset_id)return {status:'already_imported',id:result.asset_id,text:'That saved version was already brought back. Nothing was imported again.'};
    if(result?.status==='imported'&&result.asset?.id&&Array.isArray(result.asset.lineage)&&result.asset.lineage.includes(asset.id))return {status:'imported',id:result.asset.id,parent:asset.id};
    throw Error('The answer from the Studio was not recognised. Check the family before bringing the edit back again.');
  }
  // Bringing back an unchanged or already-imported file refreshes nothing; the dialog is only spoken to while it still shows the picture.
  function kritaReport(done,{current,show,notice}){if(current())show(done.text,done.id);else notice(done.text);}
  return {blocked,fileProblem,noteProblem,request,submit,settle,kritaBlocked,kritaRequest,kritaStart,kritaBringBack,kritaReport,NOTE_MAX};
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
      const run=R.submit({asset,file,note:q('#assetRepairNote').value,state,api});
      importing=true;sync();say('Importing the repaired version… Nothing is generated.');
      await R.settle(await run,{refresh:()=>refreshAssets(true),notice:message,
        current:()=>assetDetailContextCurrent(id,epoch)&&assetState.workspace_id===workspace,
        show:(newId,text)=>{q('#assetRepairFile').value='';q('#assetRepairNote').value='';open.dataset.id=newId;open.hidden=false;say(text);}});
    }catch(error){say(error.message,true);}
    finally{importing=false;sync();}
  };
  q('#assetRepairOpen').onclick=async()=>{const id=q('#assetRepairOpen').dataset.id;if(id&&await openAsset(id)===false)say('The repaired picture could not be opened. Find it in the Library.',true);};
  // #1860: Edit in Krita / Bring back from Krita. One step at a time; the dialog is only spoken to while it still shows the picture the step began on.
  if(!q('#assetKrita'))return;
  let krita=null,running=false,asked=null;const sessions=new Map(),kstate=()=>({running});
  const kritaSay=(text,error=false)=>{const line=q('#assetKritaStatus');line.textContent=text;line.classList.toggle('error',error);};
  function kritaSync(speak){
    const asset=q('#assetDialog').open?activeAsset:null,why=R.kritaBlocked(asset,krita,kstate()),backWhy=R.kritaBlocked(asset,null,kstate(),false);
    q('#assetKritaOpen').disabled=!!why;q('#assetKritaOpen').title=why;q('#assetKritaBack').disabled=!!backWhy;q('#assetKritaBack').title=backWhy;
    if(speak&&why)kritaSay(why);
  }
  // The flag is read once per page (config/local.json changes need a Studio restart anyway); a failed read is retried on the next picture.
  function kritaLoad(){
    if(!asked)asked=api('/api/edit-in-krita').then(v=>{krita=v;},()=>{asked=null;krita={available:false,reason:'Krita availability could not be read. Reload the page.'};}).then(()=>kritaSync(true));
  }
  new MutationObserver(()=>{q('#assetKritaView').hidden=true;kritaSay('');kritaSync(true);kritaLoad();}).observe(q('#assetDetailMedia'),{childList:true});
  const kritaContext=()=>{const asset=activeAsset,id=asset?.id,epoch=assetDetailEpoch,workspace=assetState.workspace_id;return {asset,id,current:()=>assetDetailContextCurrent(id,epoch)&&assetState.workspace_id===workspace};};
  async function kritaRun(work){
    const here=kritaContext();q('#assetKritaView').hidden=true;
    try{
      // The reasons are checked synchronously inside the step before its first await, so the single-flight flag goes up after it has started.
      const run=work(here);running=true;kritaSync(false);
      await run;
    }catch(error){if(here.current())kritaSay(error.message,true);else message(error.message,true);}
    finally{running=false;kritaSync(false);}
  }
  q('#assetKritaOpen').onclick=()=>kritaRun(async({asset,id,current})=>{
    const run=R.kritaStart({asset,krita,state:kstate,api});kritaSay('Opening the picture in Krita… Nothing is generated.');
    const session=await run;sessions.set(id,session.id);
    const text='Krita is opening a copy of this picture. Edit and save it there (File, Save), then press Bring back from Krita. This picture is unchanged.';
    if(current())kritaSay(text);else message(text);
  });
  q('#assetKritaBack').onclick=()=>kritaRun(async({asset,id,current})=>{
    const run=R.kritaBringBack({asset,session:sessions.get(id),state:kstate,api});kritaSay('Reading the saved file…');
    const done=await run,show=(text,newId)=>{if(newId){q('#assetKritaView').dataset.id=newId;q('#assetKritaView').hidden=false;}kritaSay(text);};
    if(done.status==='imported')return R.settle(done,{refresh:()=>refreshAssets(true),notice:message,current,
      show:newId=>show('Brought back from Krita. The new picture is linked as a repair of this one, unreviewed. This picture is unchanged.',newId)});
    R.kritaReport(done,{current,show,notice:message});
  });
  q('#assetKritaView').onclick=async()=>{const id=q('#assetKritaView').dataset.id;if(id&&await openAsset(id)===false)kritaSay('The edited picture could not be opened. Find it in the Library.',true);};
})();
