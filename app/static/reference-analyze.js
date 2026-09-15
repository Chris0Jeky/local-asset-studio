/* Explicit analysis on the shared Studio worker. Reads/reload never replay a POST. */
(() => {
  'use strict';
  const el=id=>document.getElementById(id);
  if(!el('reference-analyze')||!globalThis.StudioPromptDraft)return;
  const prefix='/api/prompt/reference-jobs/', key='studio.reference-analysis.handle.v1';
  const active=new Set(['queued','preparing','submitting']);
  const states=new Set([...active,'completed','failed','uncertain','cancelled']);
  const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  let caps=null,files=[],epoch=0,handle=null,last=null,busy=false,timer=null,storageError=false;
  const say=text=>{el('ra-status').textContent=text;};
  function validHandle(value){return value&&Object.keys(value).length===2&&typeof value.workspace_id==='string'&&/^[a-f0-9]{32}$/.test(value.workspace_id)&&typeof value.request_id==='string'&&/^[A-Za-z0-9_.:-]{16,128}$/.test(value.request_id);}
  function remember(value){
    if(!validHandle(value))throw Error('Invalid analysis recovery identity.');
    const text=JSON.stringify(value);sessionStorage.setItem(key,text);
    if(sessionStorage.getItem(key)!==text)throw Error('Recovery identity was not saved.');
    handle=value;storageError=false;el('ra-identity').textContent=value.request_id;
  }
  function controls(){
    const held=last?.state.resource_hold, settled=last&&!active.has(last.state.status);
    el('ra-start').disabled=busy||!!handle||storageError||!caps?.enabled||!!caps?.busy||!files.length;
    el('ra-check').disabled=busy||!handle;
    el('ra-use').disabled=busy||!last?.result?.analysis;
    el('ra-cancel').disabled=busy||last?.state.status!=='queued';
    el('ra-release').disabled=busy||!settled||!held;
    el('ra-new').disabled=busy||!settled||!!held;
    el('ra-recover').disabled=busy||!!handle||!el('ra-recent').value;
    el('ra-hold').hidden=!held;
  }
  async function request(route,body){
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timeout=controller?setTimeout(()=>controller.abort(),body===undefined?20000:60000):null;
    try{
      const response=await fetch(prefix+route,{...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),...(controller?{signal:controller.signal}:{})});
      const value=await response.json();if(!response.ok)throw Error(value.error||'Analysis request failed. Check its saved identity before taking another action.');
      return value;
    }finally{clearTimeout(timeout);}
  }

  function accept(value){
    if(!handle||value?.format!=='studio.reference-job/v1'||value.workspace_id!==handle.workspace_id||value.request_id!==handle.request_id||value.generation_submitted!==false||!states.has(value.state?.status)||typeof value.state.resource_hold!=='boolean'||typeof value.state_sha256!=='string')throw Error('Analysis reply does not match the saved operation.');
    last=value;say(value.state.status+': '+value.state.message);controls();
  }
  function schedule(){
    clearTimeout(timer);timer=null;
    if(!document.hidden&&handle&&(!last||active.has(last.state.status)))timer=setTimeout(check,2000);
  }
  async function check(){
    if(busy||!handle)return;busy=true;controls();
    try{accept(await request('status?'+new URLSearchParams(handle)));}
    catch(error){say(error.message+' The saved request has not been repeated.');}
    finally{busy=false;controls();if(last&&active.has(last.state.status))schedule();}
  }
  async function capabilities(){
    try{
      const value=await request('capabilities');
      if(value?.format!=='studio.reference-jobs/v1'||typeof value.enabled!=='boolean'||typeof value.workspace_id!=='string')throw Error('Invalid analysis capabilities.');
      caps=value;el('ra-config').textContent=(value.model?value.model+' — ':'')+value.message;
      el('ra-recent').replaceChildren(node('option','Choose a recent operation'));el('ra-recent').children[0].value='';
      for(const row of value.recent||[]){const option=node('option',row.status+' · '+row.request_id);option.value=row.request_id;el('ra-recent').append(option);}
      if(handle&&handle.workspace_id!==value.workspace_id)say('The saved operation belongs to another Workspace. Return to that Workspace to inspect it; nothing was resubmitted.');
    }catch(error){caps=null;el('ra-config').textContent=error.message;}
    controls();
  }
  el('ra-files').addEventListener('change',event=>{
    epoch++;files=Array.from(event.target.files);controls();
    if(files.length>4||files.some(f=>!f.size||f.size>8*1024*1024)){files=[];say('Choose one to four pictures, each at most 8 MiB.');controls();return;}
    say(handle?'Pictures selected for reviewing the saved result. No new analysis started.':'Pictures selected. Your current brief will be used when you press Analyze pictures.');
  });
  el('ra-start').addEventListener('click',async()=>{
    if(busy||handle||storageError||!caps?.enabled||caps.busy||!files.length)return;
    busy=true;controls();const version=epoch,snapshot=StudioPromptDraft.capture(),sources=[...files];
    try{
      if(sources.length>4)throw Error('At most four reference pictures.');
      const references=[],images=[],seen=new Set();
      for(let i=0;i<sources.length;i++){
        const file=sources[i];if(!file.size||file.size>8*1024*1024||/[\\/:]/.test(file.name))throw Error('Use PNG/JPEG/WebP originals under 8 MiB with portable filenames.');
        const raw=await file.arrayBuffer(),bytes=new Uint8Array(raw);
        if(!bytes.length||bytes.length>8*1024*1024)throw Error('Reference bytes exceed 8 MiB.');
        const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),x=>x.toString(16).padStart(2,'0')).join('');
        if(seen.has(sha))throw Error('Select each original once. Duplicate picture content is not a second reference.');seen.add(sha);
        let text='';for(let j=0;j<bytes.length;j+=4096)text+=String.fromCharCode(...bytes.subarray(j,j+4096));
        const id='picture-'+(i+1);references.push({id,path:file.name,sha256:sha,role_hint:'auto'});images.push({reference_id:id,media_base64:btoa(text)});
      }
      if(version!==epoch||!StudioPromptDraft.matches(snapshot))throw Error('Pictures or brief changed while reading. Nothing was queued; press Analyze again with the intended inputs.');
      const identity={workspace_id:caps.workspace_id,request_id:crypto.randomUUID()};
      try{remember(identity);}catch(_){throw Error('The recovery identity could not be saved in session storage. No analysis was sent.');}
      const body={...identity,request:{format:'studio.reference-analysis.request/v1',brief:snapshot.intent.brief,references},images};
      say('Submitting one analysis request. Closing the page does not cancel the model.');
      accept(await request('create',body));
    }catch(error){say(error.message+(handle?' Use Check status for the saved operation; do not submit again.':''));}
    finally{busy=false;controls();schedule();}
  });
  el('ra-check').addEventListener('click',check);
  el('ra-use').addEventListener('click',async()=>{
    if(busy||!last?.result?.analysis)return;busy=true;controls();
    try{
      await globalThis.StudioReferenceReview.load(last.result,files);
      say('Opened observations for review below. Your brief is unchanged until Preview and Apply.');
      el('reference-review').scrollIntoView({block:'start'});
    }catch(error){say(error.message);}
    finally{busy=false;controls();}
  });
  async function command(action){
    if(busy||!last)return;busy=true;controls();
    try{
      const body={...handle,expected_state_sha256:last.state_sha256};
      if(action==='release')body.acknowledge_unknown=el('ra-acknowledge').checked;
      accept(await request(action,body));
    }catch(error){say(error.message+' Check status before another command.');}
    finally{busy=false;controls();schedule();}
  }
  el('ra-cancel').addEventListener('click',()=>command('cancel'));
  el('ra-release').addEventListener('click',()=>command('release'));
  el('ra-new').addEventListener('click',async()=>{
    if(busy||!last||active.has(last.state.status)||last.state.resource_hold)return;
    try{sessionStorage.removeItem(key);if(sessionStorage.getItem(key)!==null)throw Error('Could not clear the local handle.');}
    catch(error){say(error.message);return;}
    handle=null;last=null;storageError=false;el('ra-identity').textContent='';clearTimeout(timer);await capabilities();
    say('Ready for a separately requested analysis. The previous operation remains in Workspace history.');controls();
  });
  el('ra-recent').addEventListener('change',controls);
  el('ra-recover').addEventListener('click',async()=>{
    if(busy||handle||!caps||!el('ra-recent').value)return;
    try{remember({workspace_id:caps.workspace_id,request_id:el('ra-recent').value});last=null;await check();}
    catch(error){say(error.message);}
    controls();
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else schedule();});
  window.addEventListener('beforeunload',()=>clearTimeout(timer));
  try{
    const raw=sessionStorage.getItem(key);
    if(raw!==null){if(raw.length>1024)throw Error('Recovery handle too large');handle=JSON.parse(raw);if(!validHandle(handle))throw Error('Invalid saved recovery handle');el('ra-identity').textContent=handle.request_id;}
  }catch(_){handle=null;storageError=true;say('Local recovery storage is unavailable or malformed. Inspect a recent server operation; no analysis will be sent automatically.');}
  controls();capabilities().then(()=>{if(handle&&caps?.workspace_id===handle.workspace_id)check();});
})();
