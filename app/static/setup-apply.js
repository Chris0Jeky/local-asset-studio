/* Explicit Workspace setup commands. Reads recover receipts; they never replay writes. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioSetupApply=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const API='/api/workflow-studio/setup-drafts',KEY='studio-shared-setup-v1';
  const clone=x=>JSON.parse(JSON.stringify(x)),need=(ok,message)=>{if(!ok)throw Error(message);};
  function same(a,b){if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&same(a[k],b[k]));}
  const settled=d=>d&&Array.isArray(d.pendingInputs)&&d.pendingInputs.length===0;
  class Controller{
    constructor(options){Object.assign(this,options);this.key=KEY;this.running=false;this.active=true;this.seen=null;this.state={version:1,pending:null};this.problem='';
      try{this.seen=this.storage.getItem(KEY);if(this.seen){need(this.seen.length<=3*1048576,'The retained setup session is too large. Export it before clearing it.');const s=JSON.parse(this.seen);need(s&&s.version===1&&typeof s==='object','The retained setup session is unreadable. Export it before clearing it.');this.state=s;}}catch(e){this.problem=e.message;}
    }
    notify(message,error=false){this.emit({message,error,busy:this.running,state:clone(this.state)});}
    save(next){need(this.active,'This page is leaving. Inspect the original request from the next page.');need(!this.problem,this.problem);need(this.storage.getItem(KEY)===this.seen,'Another tab changed the setup session. Reload and inspect its receipt; nothing was repeated.');const text=JSON.stringify(next);need(text.length<=3*1048576,'Setup session exceeds the browser recovery limit. Export it before continuing.');this.storage.setItem(KEY,text);need(this.storage.getItem(KEY)===text,'The setup session could not be verified in browser storage.');this.seen=text;this.state=next;}
    usable(){need(this.active,'This page is leaving.');need(!this.problem,this.problem);need(!this.state.pending,'Inspect the original pending request before starting another command.');need(!this.draft.busy(),'Let the current attachment or editor operation settle first.');need(settled(this.draft.capture()),'Attach or remove pending local files first; their bytes cannot be checkpointed.');}
    async work(action){if(this.running)return;this.running=true;this.notify('Working on the shared setup. No generation is requested.');try{await (this.withLock|| (fn=>fn()))(action);}catch(e){this.notify(e.message+(this.state.pending?' Original request: '+this.state.pending.request_id+'. Use Inspect original request; do not repeat the write.':''),true);}finally{this.running=false;this.emit({busy:false,state:clone(this.state)});}}
    async send(command){const q=clone(command);this.save({...this.state,pending:q});let result=await this.request(API,q);result=await this.validate(result,q);this.accept(result,q);return result;}
    accept(result,q){const next={...this.state,last:clone(result)};if(result.status==='committed'){
        need(Number.isSafeInteger(result.revision)&&result.revision>=1&&result.draft_id,'The committed setup revision is incomplete.');
        Object.assign(next,{workspace_id:result.workspace_id,draft_id:result.draft_id,revision:result.revision});
        if(q.action==='apply')next.undo_revision=q.expected_revision;
        if(q.action==='restore')next.undo_revision=null;
      }
      next.pending=['checking','staging'].includes(result.status)?q:null;this.save(next);
    }
    command(action,extra={}){return{action,workspace_id:this.state.workspace_id,request_id:this.uuid(),...(action==='create'?{}:{draft_id:this.state.draft_id,expected_revision:this.state.revision}),...extra};}
    current(stamp,matches=()=>true){return this.active&&!this.draft.busy()&&this.draft.stamp()===stamp&&matches();}
    adopt(result,stamp,matches=()=>true){if(!this.current(stamp,matches)){this.notify('The Workspace revision was saved, but Create or the review changed. Your current editor was preserved. Inspect and load the revision explicitly.');return false;}
      this.save({...this.state,backup:this.draft.capture()});this.draft.adopt(result.draft,stamp,result.runtime.backend_id);this.save({...this.state,loadedDraft:this.draft.capture(),loadedRevision:result.revision});return true;
    }
    async apply(report,matches){return this.work(async()=>{this.usable();const r=clone(report),before=this.draft.capture(),stamp=this.draft.stamp();need(matches()&&same(before,r.before),'The review no longer describes the current Create draft. Build a new proposal.');
      const scope=await this.request(API);need(typeof scope.workspace_id==='string'&&/^[a-f0-9]{32}$/.test(scope.workspace_id),'Workspace identity is unavailable.');need(!this.state.workspace_id||this.state.workspace_id===scope.workspace_id,'The Workspace changed. Export this session before starting another.');need(this.current(stamp,matches),'Create or the review changed before checkpointing. Nothing was applied.');
      this.save({...this.state,workspace_id:scope.workspace_id});const checkpoint=await this.send(this.command(this.state.draft_id?'replace':'create',{draft:before}));need(checkpoint.status==='committed','The checkpoint was not confirmed. Inspect the request before continuing.');
      need(this.current(stamp,matches),'Your before-state was checkpointed, but Create or the review changed. No source staging was requested.');
      const applied=await this.send(this.command('apply',{proposal_json:r.proposal_json,approved_proposal_sha256:r.proposal_sha256}));
      if(applied.status!=='committed'){this.notify(applied.message||'Application is not committed. Inspect retained copies and the original request before continuing.',true);return;}
      if(this.adopt(applied,stamp,matches))this.notify('Reviewed setup applied to Create and saved as Workspace revision '+applied.revision+'. Review readiness before Generate. Undo preserves copied files.');
    });}
    async undo(){return this.work(async()=>{this.usable();need(this.state.undo_revision,'No applied setup in this session can be undone.');need(same(this.state.loadedDraft,this.draft.capture()),'Create was edited after application. Export or checkpoint those edits before choosing a previous revision.');const stamp=this.draft.stamp();const result=await this.send(this.command('restore',{revision:this.state.undo_revision}));if(result.status==='committed'&&this.adopt(result,stamp))this.notify('Previous setup restored as a new Workspace revision. No source files or history were deleted.');});}
    async recover(){return this.work(async()=>{const q=this.state.pending;need(q,'No pending request to inspect.');let result=await this.request(API+'/requests/'+encodeURIComponent(q.request_id));result=await this.validate(result,q);this.accept(result,q);this.notify(result.status==='committed'?'The original request committed revision '+result.revision+'. Create was not changed. Inspect and load that revision explicitly.':result.message||'Original request is '+result.status+'. No write was repeated.',result.status==='failed');});}
    async load(){return this.work(async()=>{this.usable();need(this.state.draft_id,'No shared setup is attached to this session.');const stamp=this.draft.stamp();let result=await this.request(API+'/'+encodeURIComponent(this.state.draft_id)+'/check/'+this.state.revision);result=await this.validate(result);need(result.workspace_id===this.state.workspace_id&&result.draft_id===this.state.draft_id&&result.revision===this.state.revision&&result.head_revision===result.revision&&result.inputs_available===true,'The shared revision or Workspace changed. Inspect it before loading.');if(this.adopt(result,stamp))this.notify('Checked Workspace revision loaded into Create. No generation was requested.');});}
    async abandon(){return this.work(async()=>{const q=this.state.pending;need(q&&q.draft_id&&q.expected_revision,'Inspect the unresolved checkpoint before detaching this session.');const command={action:'abandon',workspace_id:q.workspace_id,request_id:this.uuid(),draft_id:q.draft_id,expected_revision:q.expected_revision,operation_id:q.request_id};
      // Preserve the original journal until the separate abandonment result is checked.
      this.save({...this.state,abandoned_request:q});const result=await this.send(command);this.notify(result.message||'Pending operation released. Possible staged files and original receipts were retained.');});}
    dispose(){this.active=false;}
  }
  async function verify(result,q,hash){
    need(result&&result.generation_submitted===false,'Unexpected setup response authority. Inspect the original request.');
    async function exact(text,sha){need(typeof text==='string'&&text.length<=1048576&&typeof sha==='string'&&await hash(text)===sha,'Setup response failed its content check.');return JSON.parse(text);}
    if(q){need(result.request_id===q.request_id&&result.workspace_id===q.workspace_id&&result.action===q.action&&(!q.draft_id||result.draft_id===q.draft_id),'Setup receipt does not match the original command.');need(['committed','checking','staging','failed','abandoned'].includes(result.status),'Unknown setup receipt state.');}
    if(result.receipt_json){const core=await exact(result.receipt_json,result.receipt_sha256);for(const k of Object.keys(core))need(same(core[k],result[k]),'Setup receipt fields disagree.');}else need(!q,'Setup command receipt is missing.');
    if(result.draft){const core=await exact(result.record_json,result.record_sha256);for(const k of Object.keys(core))need(same(core[k],result[k]),'Setup revision fields disagree.');need(core.draft?.version===1&&core.runtime&&Array.isArray(core.inputs)&&settled(core.draft),'Setup revision is incomplete.');}
    if(result.status==='committed'){need(result.draft,'Committed setup data is absent.');need(Number.isSafeInteger(result.revision)&&Number.isSafeInteger(result.head_revision)&&result.revision>=1&&result.revision<=256&&result.head_revision>=result.revision,'Invalid committed setup revision.');if(q){need(result.revision===(q.action==='create'?1:q.expected_revision+1),'Unexpected committed setup revision.');if(q.action==='create'||q.action==='replace')need(same(result.draft,q.draft),'The checkpoint differs from the submitted draft.');if(q.action==='apply')need(result.approved_proposal_sha256===q.approved_proposal_sha256,'The applied receipt names a different proposal.');}}return result;
  }
  function mount(w,options={}){const d=w.document,host=d.querySelector('#uxDraftBar');if(d.querySelector('#sharedSetupPanel'))return;if(!host||!w.StudioSetupDraft){d.addEventListener('studio:setup-draft-ready',()=>mount(w,options),{once:true});return;}
    const el=(tag,text)=>{const n=d.createElement(tag);if(text!==undefined)n.textContent=text;return n;};const panel=el('section');panel.id='sharedSetupPanel';panel.className='shared-setup-panel';panel.hidden=true;
    panel.append(el('h3','Shared setup & recovery'));const status=el('p');status.id='sharedSetupStatus';status.tabIndex=-1;status.setAttribute('role','status');panel.append(status);const identity=el('p'),actions=el('div'),details=el('details'),receipt=el('pre');details.append(el('summary','Retained operation details'),receipt);panel.append(identity,actions,details);host.after(panel);
    async function request(path,body){
      const abort=new w.AbortController(),timer=w.setTimeout(()=>abort.abort(),30000);
      try{
        const response=await w.fetch(path,{...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}),signal:abort.signal});
        const reader=response.body.getReader(),chunks=[];let size=0;
        try{for(;;){const {value,done}=await reader.read();if(done)break;size+=value.length;need(size<=3*1048576,'Setup response exceeds the recovery limit.');chunks.push(value);}}
        finally{await reader.cancel();}
        const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
        let value;try{value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}catch(_){throw Error('Setup response was unreadable.');}
        need(response.ok,typeof value?.error==='string'?value.error:'Setup request unavailable ('+response.status+').');return value;
      }finally{w.clearTimeout(timer);}
    }
    const withLock=options.withLock|| (async fn=>{
      need(w.navigator.locks?.request,'This browser cannot protect setup recovery across tabs. Use the headless commands or a browser with Web Locks.');
      return w.navigator.locks.request(KEY,{ifAvailable:true},lock=>{need(lock,'Another tab is handling this setup session. Inspect it before continuing.');return fn();});
    });
    const hash=options.hashText|| (async text=>{need(w.crypto?.subtle,'Browser integrity checks are unavailable. No setup command was sent.');return Array.from(new Uint8Array(await w.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');});
    let controller;const buttons=[];function paint(event){panel.hidden=false;if(event.message){status.textContent=event.message;const inline=d.querySelector('#setupApplyStatus');if(inline)inline.textContent=event.message;}const s=event.state;identity.textContent=s.draft_id?'Workspace revision '+s.revision+' · draft '+s.draft_id.slice(0,12)+'…':s.pending?'Original request: '+s.pending.request_id:'No shared revision yet.';receipt.textContent=JSON.stringify(s.last||s.pending||{},null,2);for(const b of buttons){b.hidden=b.unavailable(s);b.disabled=!!event.busy;}}
    let storage;try{storage=w.localStorage;}catch(_){storage={getItem(){throw Error('Browser storage is unavailable; use the explicit headless commands.');},setItem(){throw Error('Browser storage is unavailable.');}};}
    controller=new Controller({request,withLock,storage,draft:w.StudioSetupDraft,uuid:options.uuid||(()=>w.crypto.randomUUID()),validate:(r,q)=>verify(r,q,hash),emit:paint});
    function button(id,label,run,unavailable){const b=el('button',label);b.id=id;b.type='button';b.unavailable=unavailable;b.onclick=run;actions.append(b);buttons.push(b);}
    button('undoSharedSetup','Undo applied setup',()=>controller.undo(),s=>!s.undo_revision||!!s.pending);
    button('recoverSharedSetup','Inspect original request',()=>controller.recover(),s=>!s.pending);
    button('loadSharedSetup','Load checked Workspace revision',()=>{if(w.confirm('Replace the current Create editor with this checked Workspace revision? Its current draft will be retained in this browser session backup.'))controller.load();},s=>!s.draft_id||!!s.pending);
    button('abandonSharedSetup','Release pending operation',()=>{if(w.confirm('Release this interrupted operation without retrying it? Copies and receipts remain. This does not cancel a source copy already in progress.'))controller.abandon();},s=>!s.pending?.draft_id);
    button('exportSharedSetup','Export recovery session',()=>{const text=controller.problem?controller.seen:JSON.stringify(controller.state,null,2),url=w.URL.createObjectURL(new Blob([text||'null'],{type:'application/json'})),a=el('a');a.href=url;a.download='studio-setup-session.json';a.click();w.setTimeout(()=>w.URL.revokeObjectURL(url),1000);},()=>false);
    panel.append(el('p','Apply copies inputs; Generate remains separate. Session exports contain private prompts and reference metadata.'));
    if(controller.seen||controller.problem)controller.notify(controller.problem||'A shared setup session was retained. Inspect any pending request before loading a revision.',!!controller.problem);
    w.StudioSetupApply.offer=(report,matches)=>{const b=el('button','Apply reviewed setup');b.id='applyReviewedSetup';b.type='button';b.onclick=async()=>{if(controller.running)return;try{need(options.hashText||w.crypto?.subtle,'Browser integrity checks are unavailable.');need(matches(),'Build a current proposal before applying.');if(!w.confirm('Checkpoint the current Create draft, copy the reviewed references to this backend, and replace Create with the complete proposed setup? No generation will start.'))return;b.disabled=true;const previous=controller.state.last?.request_id;await controller.apply(report,matches);if(controller.state.last?.request_id!==previous&&controller.state.loadedRevision===controller.state.revision&&controller.state.last?.action==='apply'&&controller.state.last?.status==='committed'){d.querySelector('#setupProposalDialog')?.close();status.focus();}}catch(e){controller.notify(e.message,true);}finally{b.disabled=false;}};const box=el('div'),inline=el('p');inline.id='setupApplyStatus';inline.setAttribute('role','status');box.append(b,inline);return box;};
    for(const type of ['input','change','studio:recipe'])d.addEventListener(type,e=>{if(!controller.running&&controller.state.loadedDraft&&(type==='studio:recipe'||e.target.closest?.('#createView'))&&!same(controller.state.loadedDraft,controller.draft.capture()))controller.notify('Create contains local edits. The shared revision is unchanged. Undo will not overwrite these edits.');});
    w.addEventListener('pagehide',()=>controller.dispose());w.StudioSetupApply.controller=controller;
  }
  return{Controller,verify,mount,same};
});
