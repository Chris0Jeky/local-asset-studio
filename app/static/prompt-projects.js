/* Explicit Workspace saves. The editor and reference-review modules own unsaved state. */
(() => {
  'use strict';
  const el=id=>document.getElementById(id),owner=globalThis.StudioPromptDraft,review=globalThis.StudioReferenceReview;
  if(!el('prompt-projects')||!owner||!review)return;
  const prefix='/api/prompt/projects/',storageKey='studio.prompt-project.pending/v1',cap=512*1024;
  const clone=v=>JSON.parse(JSON.stringify(v));
  const stable=v=>JSON.stringify(v,(k,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(key=>[key,x[key]])):x);
  const same=(a,b)=>stable(a)===stable(b),flags=x=>x&&['generation_submitted','inference_submitted','execution_authorized'].every(k=>x[k]===false);
  let scope=null,active=null,prepared=null,busy=false,pending=null,journalInvalid=false,saved=null;
  const text=s=>{el('pp-status').textContent=s;};
  const node=(tag,value)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;return e;};
  function capture(){return {draft:owner.capture(),reference:review.capture(),name:el('pp-name').value};}
  function matches(ticket){return ticket&&owner.matches(ticket.draft)&&same(ticket.reference,review.capture())&&ticket.name===el('pp-name').value;}
  function makeDocument(ticket){return {format:'studio.prompt-document/v1',name:ticket.name,profile_id:ticket.draft.profile,intent:ticket.draft.intent,reference_context:ticket.reference.context};}
  function controls(){
    const held=!!pending||journalInvalid;
    el('pp-create').disabled=!scope||busy||held;el('pp-save').disabled=!scope||!active||busy||held;
    el('pp-preview').disabled=!scope||!el('pp-list').value||busy;
    el('pp-open').disabled=!prepared||busy||held;
    el('pp-history').disabled=!scope||!el('pp-list').value||busy;
    el('pp-old').disabled=!scope||!el('pp-revision').value||busy;
    el('pp-restore').disabled=!prepared||!active||prepared.row.id!==active.id||prepared.row.revision===active.revision||busy||held;
    el('pp-refresh').disabled=busy;
    el('pp-recovery').hidden=!held;
    el('pp-check').disabled=busy||!pending||scope!==pending.value.workspace_id;
    el('pp-retry').disabled=busy||!pending||scope!==pending.value.workspace_id;
    el('pp-forget').disabled=busy;
    if(active){
      let dirty=true;try{dirty=!same(makeDocument(capture()),saved);}catch(_){}
      el('pp-current').textContent='Saved brief '+active.id.slice(0,8)+' · revision '+active.revision+(dirty?' · unsaved editor changes':' · editor matches this revision')+'.';
    }else el('pp-current').textContent='No saved brief is open. Edits are not automatically saved.';
  }
  function parsePending(raw){
    if(typeof raw!=='string'||new TextEncoder().encode(raw).length>cap)throw Error('Pending save is too large or invalid.');
    const parsed=JSON.parse(raw);
    if(!parsed||parsed.format!=='studio.prompt-pending/v1'||!['create','save','restore'].includes(parsed.action)||typeof parsed.body!=='string')throw Error('Pending save format is not supported.');
    const value=JSON.parse(parsed.body);
    if(!value||!/^[a-f0-9]{32}$/.test(value.workspace_id)||!/^[A-Za-z0-9_-]{16,128}$/.test(value.request_id))throw Error('Pending save identity is not valid.');
    return {raw,action:parsed.action,body:parsed.body,value};
  }
  function retain(action,value){
    const raw=JSON.stringify({format:'studio.prompt-pending/v1',action,body:JSON.stringify(value)});
    const parsed=parsePending(raw);
    try{
      if(sessionStorage.getItem(storageKey)!==null)throw Error('A previous save handle is still retained.');
      sessionStorage.setItem(storageKey,raw);
      if(sessionStorage.getItem(storageKey)!==raw)throw Error('Save journal did not read back exactly.');
    }catch(error){throw Error('The exact save could not be retained in this tab. Nothing was sent. '+error.message);}
    return parsed;
  }
  function clearPending(){
    if(!pending)return;
    if(sessionStorage.getItem(storageKey)!==pending.raw)throw Error('Local save journal changed; its handle was retained.');
    sessionStorage.removeItem(storageKey);
    if(sessionStorage.getItem(storageKey)!==null)throw Error('Could not clear the confirmed save handle.');
    pending=null;
  }
  async function request(route,params=null,body=null){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
    try{
      const response=await fetch(prefix+route+(params?'?'+new URLSearchParams(params):''),body===null?{signal:controller.signal}:{method:'POST',headers:{'Content-Type':'application/json'},body,signal:controller.signal});
      const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let raw='',bytes=0;
      try{while(true){const part=await reader.read();if(part.done)break;bytes+=part.value.byteLength;
        if(bytes>1024*1024){await reader.cancel();throw Error('Prompt project reply exceeds its limit.');}
        raw+=decoder.decode(part.value,{stream:true});}raw+=decoder.decode();}finally{reader.releaseLock();}
      const value=JSON.parse(raw);
      if(!response.ok){const error=Error(value.error||'Local project request failed');error.status=response.status;error.code=value.code;throw error;}
      if(!flags(value))throw Error('Unexpected prompt project authority flags.');
      return value;
    }finally{clearTimeout(timer);}
  }
  function checkedRow(row){
    if(!flags(row)||row.format!=='studio.prompt-project/v1'||row.workspace_id!==scope||!/^[a-f0-9]{32}$/.test(row.id)||!Number.isSafeInteger(row.revision)||row.revision<1||!Number.isSafeInteger(row.head_revision)||row.head_revision<row.revision||row.source_bytes_verified!==false||row.document?.format!=='studio.prompt-document/v1')throw Error('Saved revision did not match the current Workspace contract.');
    return row;
  }
  function showPreview(row,ticket=capture()){
    checkedRow(row);prepared={row:clone(row),ticket};
    el('pp-preview-box').hidden=false;el('pp-preview-box').open=true;
    el('pp-diff').textContent='Saved revision '+row.revision+' (observed head '+row.head_revision+')\n'+JSON.stringify(row.document,null,2)+'\n\nCurrent editor\n'+JSON.stringify(makeDocument(ticket),null,2);
    controls();
  }
  function invalidate(){if(prepared&&!matches(prepared.ticket)){prepared=null;text('The editor or reference review changed. Preview the saved revision again.');}controls();}
  async function refresh(){
    const data=await request('capabilities');
    if(data.format!=='studio.prompt-projects/v1'||!/^[a-f0-9]{32}$/.test(data.workspace_id))throw Error('Invalid Workspace identity.');
    if(scope&&scope!==data.workspace_id){active=null;prepared=null;saved=null;}
    scope=data.workspace_id;
    const list=await request('list',{workspace_id:scope});
    if(list.workspace_id!==scope||!Array.isArray(list.projects)||list.projects.length>128)throw Error('Invalid saved brief listing.');
    const selected=el('pp-list').value;el('pp-list').replaceChildren(node('option','Choose a saved brief'));el('pp-list').firstChild.value='';
    for(const row of list.projects){const option=node('option',(row.unreadable?'Unreadable brief':row.name)+' · r'+row.revision);option.value=row.id;el('pp-list').append(option);}
    if(list.projects.some(x=>x.id===selected))el('pp-list').value=selected;
    controls();
  }
  async function action(work){if(busy)return;busy=true;controls();try{await work();}catch(error){text(error.message);}finally{busy=false;controls();}}
  function receipt(value,command){
    if(value.format!=='studio.prompt-command/v1'||!flags(value)||value.workspace_id!==scope||value.action!==command.action||!same(value.request,command.value)||value.request_id!==command.value.request_id)throw Error('Save receipt does not match the retained request.');
    const row=checkedRow(value.project),expected=command.action==='create'?1:command.value.expected_revision+1;
    if(row.revision!==expected||(command.action!=='create'&&row.id!==command.value.id)||(command.action!=='restore'&&!same(row.document,command.value.document)))throw Error('Save receipt has a different document or revision.');
    return row;
  }
  async function send(command,ticket=null){
    try{
      const value=await request(command.action,null,command.body),row=receipt(value,command);
      clearPending();active={id:row.id,revision:row.revision};saved=clone(row.document);
      // A response acknowledges only its submitted snapshot. Never assign its words over later typing.
      if(ticket&&matches(ticket)&&command.action==='restore')showPreview(row,ticket);
      else if(!ticket)showPreview(row);
      text('Save confirmed at revision '+row.revision+'. Your editor was not overwritten.');
      try{await refresh();el('pp-list').value=row.id;}catch(error){text('Save confirmed, but the list could not refresh: '+error.message);}
    }catch(error){text(error.message+' Check save status; the exact command remains retained.');}
  }
  function save(actionName){return action(async()=>{
    if(!scope||pending||journalInvalid)throw Error('Resolve the retained save before starting another.');
    const ticket=capture();if(!ticket.name.trim())throw Error('Give this brief a name before saving.');
    let value={workspace_id:scope,request_id:crypto.randomUUID().replaceAll('-',''),document:makeDocument(ticket)};
    if(actionName==='save'){
      if(!active)throw Error('Open a saved brief first.');value={...value,id:active.id,expected_revision:active.revision};
    }
    if(actionName==='restore'){
      if(!prepared||!matches(prepared.ticket)||!active||prepared.row.id!==active.id)throw Error('Preview an earlier revision of the open brief first.');
      value={workspace_id:scope,request_id:value.request_id,id:active.id,expected_revision:active.revision,restore_revision:prepared.row.revision};
    }
    pending=retain(actionName,value);prepared=null;controls();await send(pending,ticket);
  });}
  el('pp-create').addEventListener('click',()=>save('create'));el('pp-save').addEventListener('click',()=>save('save'));el('pp-restore').addEventListener('click',()=>save('restore'));
  el('pp-refresh').addEventListener('click',()=>action(async()=>{await refresh();text('Saved brief list refreshed. No editor or saved data changed.');}));
  el('pp-list').addEventListener('change',()=>{prepared=null;el('pp-revision').replaceChildren(node('option','Read history first'));el('pp-revision').firstChild.value='';controls();});
  async function preview(older=false){return action(async()=>{
    const key=el('pp-list').value,number=older?Number(el('pp-revision').value):null,ticket=capture();prepared=null;controls();
    if(!key||older&&!number)throw Error('Choose a saved brief and revision.');
    const row=checkedRow(await request('read',{workspace_id:scope,id:key,...(number?{revision:number}:{})}));
    if(!matches(ticket)||el('pp-list').value!==key||number&&Number(el('pp-revision').value)!==number)throw Error('Selection or editor changed while reading. Preview again.');
    if(row.id!==key||number&&row.revision!==number)throw Error('Saved response has a different revision.');
    showPreview(row,ticket);text('Saved revision previewed. Open it explicitly to replace the editor.');
  });}
  el('pp-preview').addEventListener('click',()=>preview());el('pp-old').addEventListener('click',()=>preview(true));
  el('pp-open').addEventListener('click',()=>{
    try{
      if(busy||pending||journalInvalid||!prepared||!matches(prepared.ticket))throw Error('The editor changed or a save is pending. Preview again after resolving it.');
      const selected=prepared,row=selected.row;
      owner.openSaved(selected.ticket.draft,row.document);review.restore(row.document.reference_context);
      el('pp-name').value=row.document.name;active={id:row.id,revision:row.revision};saved=clone(row.document);prepared=null;
      text('Opened revision '+row.revision+'. Saved descriptions are restored; original pictures must be reselected.');controls();
    }catch(error){text(error.message);controls();}
  });
  el('pp-history').addEventListener('click',()=>action(async()=>{
    const key=el('pp-list').value,rows=await request('history',{workspace_id:scope,id:key});
    if(rows.workspace_id!==scope||rows.id!==key||el('pp-list').value!==key||!Array.isArray(rows.revisions))throw Error('The history selection changed.');
    el('pp-revision').replaceChildren(node('option','Choose revision'));el('pp-revision').firstChild.value='';
    for(const row of rows.revisions){const option=node('option','Revision '+row.revision);option.value=String(row.revision);el('pp-revision').append(option);}
    text(rows.next_before?'Showing the latest 32 revisions. The headless history API can read older pages.':'Revision history loaded; nothing changed.');
  }));
  el('pp-revision').addEventListener('change',()=>{prepared=null;controls();});
  el('pp-check').addEventListener('click',()=>action(async()=>{
    if(!pending||scope!==pending.value.workspace_id)throw Error('Reconnect to the Workspace of the retained save.');
    const command=pending,value=await request('status',{workspace_id:scope,request_id:command.value.request_id}),row=receipt(value,command);
    clearPending();showPreview(row);text('Save confirmed at revision '+row.revision+'. Open the preview explicitly; newer editor words were preserved.');await refresh();el('pp-list').value=row.id;
  }));
  el('pp-retry').addEventListener('click',()=>action(async()=>{
    if(!pending||scope!==pending.value.workspace_id)throw Error('Reconnect to the Workspace of the retained save.');
    if(sessionStorage.getItem(storageKey)!==pending.raw)throw Error('Pending journal changed; refusing a retry.');
    await send(pending);
  }));
  el('pp-forget').addEventListener('click',()=>{
    try{
      if(busy||!el('pp-forget-ack').checked)throw Error('Acknowledge what forgetting the handle means first.');
      sessionStorage.removeItem(storageKey);if(sessionStorage.getItem(storageKey)!==null)throw Error('The local handle could not be cleared.');
      pending=null;journalInvalid=false;el('pp-forget-ack').checked=false;text('Local handle forgotten. No server save was cancelled or undone.');controls();
    }catch(error){text(error.message);}
  });
  el('pp-export').addEventListener('click',()=>{
    let raw;try{raw=pending?.raw||sessionStorage.getItem(storageKey);}catch(error){text('Local recovery is unavailable: '+error.message);return;}if(!raw)return;
    const url=URL.createObjectURL(new Blob([raw],{type:'application/json'})),link=node('a');link.href=url;link.download='pending-prompt-save.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  el('pp-name').addEventListener('input',invalidate);document.addEventListener('studio-prompt-state',invalidate);
  el('reference-review').addEventListener('input',invalidate);el('reference-review').addEventListener('change',invalidate);
  try{const raw=sessionStorage.getItem(storageKey);if(raw!==null)pending=parsePending(raw);}catch(error){journalInvalid=true;text('The retained save cannot be read: '+error.message);}
  action(async()=>{await refresh();text(pending?'Unconfirmed save recovered. Check save status; no command was replayed.':journalInvalid?'Resolve the unreadable local save handle before writing.':'Local brief storage is ready. Save is explicit; no automatic writes.');});
})();
