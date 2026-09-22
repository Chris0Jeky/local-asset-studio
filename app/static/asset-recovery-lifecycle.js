/* Read-only lifecycle lens. It has no mutation transport, journal writer or retry owner. */
(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./asset-recovery-shelf.js'):root.StudioAssetRecoveryShelf);
  if(typeof module==='object'&&module.exports)module.exports=api;else {root.StudioAssetRecoveryLifecycle=api;api.install();}
})(globalThis,function(Shelf){
  'use strict';
  const format='studio.asset-recovery-observation/v1';
  const integer=v=>Number.isSafeInteger(v)&&v>=0;
  const text=(v,max)=>typeof v==='string'&&v.length<=max*2&&[...v].length<=max;
  const keys=(v,names)=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===names.length&&names.every(k=>Object.hasOwn(v,k));
  const same=(a,b)=>Shelf.canonical(a)===Shelf.canonical(b);
  function targets(record){return record.payload.operation?.command.ids||[record.payload.id];}
  function command(record){return record.payload.operation?.command;}
  function checkReceipt(record,receipt){
    if(!receipt)return;
    const c=command(record);
    if(!c||receipt.workspace_id!==record.payload.workspace_id)throw Error('Receipt Workspace does not match retained evidence.');
    if(receipt.request_id!==c.request_id||!['unknown','applied'].includes(receipt.status))throw Error('Receipt request identity or status is invalid.');
    if(receipt.status==='applied'&&(receipt.action!==c.action||!same(receipt.updated,c.ids)||!keys(receipt.revisions,c.ids)||c.ids.some(id=>receipt.revisions[id]!==c.expected_revisions[id]+1)))throw Error('Historical receipt does not match every retained target and revision.');
  }
  function validate(record,value){
    if(!keys(value,['format','workspace_id','observed_at','targets','collection','generation_submitted'])||value.format!==format||value.generation_submitted!==false||typeof value.observed_at!=='number'||!Number.isFinite(value.observed_at)||value.observed_at<0)throw Error('Invalid bounded lifecycle observation.');
    if(value.workspace_id!==record.payload.workspace_id)throw Error('Observation Workspace does not match retained evidence.');
    const ids=targets(record),c=command(record),collectionId=['add_collection','remove_collection'].includes(c?.action)?c.collection_id:null;
    if(collectionId){
      const col=value.collection;
      if(!col||typeof col.exists!=='boolean'||!keys(col,col.exists?['id','exists','name']:['id','exists'])||col.id!==collectionId||col.exists&&!text(col.name,100))throw Error('Observation collection does not match the retained target.');
    }else if(value.collection!==null)throw Error('Unexpected collection observation.');
    if(!Array.isArray(value.targets)||value.targets.length!==ids.length)throw Error('Lifecycle observation must account for every target.');
    value.targets.forEach((row,index)=>{
      if(row?.id!==ids[index])throw Error('Observation target identity or order changed.');
      if(row.state==='missing'){if(!keys(row,['id','state']))throw Error('Missing target includes unexpected fields.');return;}
      if(!keys(row,['id','state','title','metadata_revision','collection_count','collections','collections_limited',...(collectionId?['in_collection']:[])])||
         !['active','trashed'].includes(row.state)||!text(row.title,200)||!integer(row.metadata_revision)||!integer(row.collection_count)||
         !Array.isArray(row.collections)||row.collections.length!==Math.min(row.collection_count,20)||row.collections_limited!==(row.collection_count>20)||
         row.collections.some(c=>!keys(c,['id','name'])||!text(c.id,128)||!c.id||!text(c.name,100))||new Set(row.collections.map(c=>c.id)).size!==row.collections.length||
         collectionId&&(typeof row.in_collection!=='boolean'||!value.collection.exists&&row.in_collection))throw Error('Invalid lifecycle target fields or bounds.');
    });
    return value;
  }
  function project(record,observation,receipt){
    Shelf.project(record.slot,record.payload);checkReceipt(record,receipt);
    if(observation)validate(record,observation);
    const c=command(record),baseline=record.slot==='detail'?record.payload.metadata:null;
    return {collection:observation?.collection||null,targets:targets(record).map((id,index)=>{
      const row=observation?.targets[index]||{id,state:'unavailable'},expected=c?.expected_revisions[id]??baseline?.metadata_revision;
      const committed=receipt?.status==='applied'?receipt.revisions[id]:null;
      const reference=committed??expected;
      const relation=!integer(row.metadata_revision)?null:row.metadata_revision===reference?'same':row.metadata_revision>reference?'newer':'older';
      // A revision alone cannot prove a trash/restore cycle that was never retained.
      const knownTrash=baseline?.id===id&&baseline.trashed_at!=null||committed!==null&&c?.action==='trash';
      return {...row,expected_revision:expected,receipt_revision:committed,revision_relation:relation,
        restored_since_retained:!!(knownTrash&&row.state==='active'&&relation==='newer')};
    })};
  }
  function create({scope,read,validateReceipt,onUpdate,timeoutMs=15000}){
    let epoch=0,controller=null;
    function cancel(){epoch++;controller?.abort();controller=null;}
    async function load(input){
      cancel();
      const record={slot:input.slot,payload:Shelf.project(input.slot,input.payload)};
      const workspace=record.payload.workspace_id;
      if(record.payload.version!==2||workspace!==scope())throw Error('Another or unknown Workspace is local inspection/export/discard only. No read was sent.');
      const generation=epoch,own=new AbortController();controller=own;
      const current=()=>generation===epoch&&workspace===scope();
      onUpdate({phase:'loading',record,report:project(record,null,null)});
      const c=command(record),params=new URLSearchParams({workspace_id:workspace,ids:JSON.stringify(targets(record))});
      if(['add_collection','remove_collection'].includes(c?.action))params.set('collection_id',c.collection_id);
      const options={method:'GET',signal:own.signal},timer=setTimeout(()=>own.abort(),timeoutMs);
      try{
        const responses=await Promise.allSettled([
          c?read('/api/assets/commands/'+encodeURIComponent(c.request_id)+'?workspace_id='+workspace,options):Promise.resolve(null),
          read('/api/assets/recovery-observation?'+params,options)
        ]);
        if(!current())return;
        let receipt=null,observation=null,receipt_error='',observation_error='';
        try{if(responses[0].status==='rejected')throw responses[0].reason;receipt=responses[0].value;checkReceipt(record,receipt);if(receipt?.status==='applied')validateReceipt(receipt,c);}
        catch(error){receipt=null;receipt_error=String(error.message||error).slice(0,1200);}
        try{if(responses[1].status==='rejected')throw responses[1].reason;observation=validate(record,responses[1].value);}
        catch(error){observation=null;observation_error=String(error.message||error).slice(0,1200);}
        onUpdate({phase:'ready',record,receipt,observation,receipt_error,observation_error,report:project(record,observation,receipt)});
      }finally{clearTimeout(timer);if(generation===epoch)controller=null;}
    }
    return {load,cancel};
  }
  function install(){
    const dialog=document.getElementById('assetRecoveryShelfDialog');if(!dialog)return;
    const element=(tag,value)=>{const node=document.createElement(tag);if(value!==undefined)node.textContent=value;return node;};
    const panel=element('section');panel.id='assetLifecycleInspection';panel.hidden=true;
    const heading=element('h3','Recovery lifecycle inspection');heading.tabIndex=-1;heading.id='assetLifecycleTitle';panel.setAttribute('aria-labelledby',heading.id);
    const status=element('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const actions=element('div');actions.className='asset-shelf-actions';
    const refresh=element('button','Read receipt and current state again');refresh.type='button';refresh.id='assetLifecycleRefresh';
    const exportButton=element('button','Export this inspection');exportButton.type='button';exportButton.id='assetLifecycleExport';
    const local=element('div'),results=element('div');results.id='assetLifecycleResults';results.tabIndex=0;results.setAttribute('aria-label','Historical receipt and current lifecycle for every retained target');
    actions.append(refresh,exportButton);panel.append(heading,status,actions,local,results);dialog.append(panel);
    let snapshot=null,last=null,localKey='',viewEpoch=0;
    const block=(title,value)=>{const section=element('section');section.append(element('h4',title));const pre=element('pre',value.length>32000?value.slice(0,32000)+'\n[Preview limited. Export includes full retained text.]':value);section.append(pre);return section;};
    function render(value){
      last=value;panel.hidden=false;snapshot=value.record;
      const key=Shelf.canonical(value.record);
      if(key!==localKey){
        localKey=key;local.replaceChildren();const p=value.record.payload;
        local.append(element('p','Retained Workspace '+p.workspace_id+'. This is an inspection snapshot; the editor and both recovery slots are unchanged.'));
        if(value.record.slot==='detail'){
          local.append(block('Retained baseline — not current server state',JSON.stringify({metadata:p.metadata,baseline:p.baseline},null,2)));
          local.append(block('Editable draft — not a submitted or saved command',JSON.stringify(p.draft,null,2)));
        }
        local.append(block('Immutable pending command — never replaced by newer typing',p.operation?.body||'No pending command.'));
      }
      if(value.phase==='loading'){results.replaceChildren(element('p','No receipt or current-state result for this read yet.'));status.textContent='Reading scoped receipt and lifecycle only. No metadata save, asset restore or generation is sent.';return;}
      status.textContent=value.observation_error?'Current lifecycle unavailable. Retained evidence and any verified historical receipt remain separate.':'Read-only inspection complete. Every retained target is accounted for; nothing was restored or saved.';
      results.replaceChildren(element('h4','Historical server receipt — a past mutation, not current asset state'));
      if(value.receipt?.status==='applied'){
        results.append(element('p','Confirmed historical request '+value.receipt.request_id+'. Its complete target set is unchanged.'));
        const {current,...historical}=value.receipt;results.append(block('Immutable receipt fields',JSON.stringify(historical,null,2)));
      }else results.append(element('p',value.receipt_error?'Receipt unavailable: '+value.receipt_error:value.receipt?.status==='unknown'?'Receipt unknown. The earlier request may still complete; this does not authorize a new request or an automatic retry.':'No pending command to inspect.'));
      results.append(element('h4','Current lifecycle — a separate observation'));
      if(value.observation)results.append(element('p','Observed '+new Date(value.observation.observed_at*1000).toLocaleString()+'. Receipt and lifecycle are separate reads, not an atomic combined snapshot. No automatic refresh occurs.'));
      if(value.observation_error)results.append(element('p',value.observation_error));
      if(value.report.collection)results.append(element('p',value.report.collection.exists?'Target collection currently exists: '+value.report.collection.name:'Target collection is missing. A historical membership receipt does not recreate it.'));
      const counts=value.report.targets.reduce((m,t)=>(m[t.state]=(m[t.state]||0)+1,m),{});
      results.append(element('p',value.report.targets.length+' targets: '+Object.entries(counts).map(([k,v])=>v+' '+k).join(', ')+'.'));
      for(const row of value.report.targets){
        const entry=element('article');entry.className='asset-shelf-record';
        entry.append(element('h4',row.id+' · '+({active:'Active now',trashed:'In Trash now',missing:'Missing now',unavailable:'Current state unavailable'}[row.state])));
        if(row.title)entry.append(element('p',row.title));
        entry.append(element('p','Retained revision '+row.expected_revision+' · Historical receipt revision '+(row.receipt_revision??'not confirmed')+' · Observed revision '+(row.metadata_revision??'unavailable')+(row.revision_relation?' ('+row.revision_relation+' than '+(row.receipt_revision!==null?'receipt':'retained baseline')+')':'')));
        if(row.restored_since_retained)entry.append(element('p','Active at a newer revision after the retained Trash state; observed as restored. No restore was sent by this inspection.'));
        if(row.state==='missing')entry.append(element('p','This target is absent from the scoped database. Its local text and historical receipt remain inspectable/exportable. No target was silently dropped.'));
        if(Object.hasOwn(row,'in_collection'))entry.append(element('p',row.in_collection?'Currently a member of the target collection.':'Not currently a member of the target collection.'));
        if(row.collections){entry.append(element('p','Current collections ('+row.collections.length+' shown of '+row.collection_count+'): '+(row.collections.map(c=>c.name).join(', ')||'none')+'. Membership not captured in the retained baseline is not inferred.'));}
        results.append(entry);
      }
    }
    const observer=create({scope:()=>assetState.workspace_id,read:(url,options)=>api(url,options),validateReceipt:validateAssetReceipt,onUpdate:render});
    function empty(error){last=null;snapshot=null;localKey='';local.replaceChildren();results.replaceChildren();panel.hidden=false;status.textContent=error.message;}
    const load=record=>{
      const ticket=++viewEpoch;
      void observer.load(record).catch(error=>{
        if(ticket!==viewEpoch||!dialog.open)return;
        try{
          const retained={slot:record.slot,payload:Shelf.project(record.slot,record.payload)};
          render({phase:'ready',record:retained,receipt:null,observation:null,receipt_error:'Not read for this context.',observation_error:error.message,report:project(retained,null,null)});
        }catch(_){empty(error);}
      });
    };
    refresh.onclick=()=>{if(snapshot)load(snapshot);};
    exportButton.onclick=()=>{
      if(!last)return;
      assetShelfDownload(JSON.stringify({format:'studio.asset-recovery-inspection/v1',...last},null,2),'asset-recovery-inspection.json');
      status.textContent='Inspection exported locally. It contains private review text and observations, not an importable shelf bundle. No server change was made.';
    };
    dialog.addEventListener('close',()=>{if(dialog.open)return;viewEpoch++;observer.cancel();panel.hidden=true;snapshot=null;last=null;localKey='';local.replaceChildren();results.replaceChildren();});
    dialog.addEventListener('click',event=>{
      const button=event.target.closest('[data-shelf-observe],[data-recovery-observe-slot]');if(!button||button.disabled)return;
      viewEpoch++;observer.cancel();
      try{
        let record;
        if(button.dataset.recoveryObserveSlot){
          const slot=button.dataset.recoveryObserveSlot,payload=assetRecovery.read(slot);
          if(!payload)throw Error('This tab has no retained '+slot+' recovery. No read was sent.');
          record={slot,payload};
        }else record=assetShelfRecords.find(r=>r.id===button.dataset.shelfObserve);
        if(!record)throw Error('The selected recovery is unavailable; refresh local records.');
        load(record);panel.hidden=false;heading.focus();
      }catch(error){empty(error);}
    });
  }
  return {project,create,install};
});
