/* Read-only Workspace history for the shared setup (#395). GET only: it never loads, restores, forks, imports or adopts
   a revision, and never reads or writes the Create draft or the setup recovery journal. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioSetupHistory=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const API='/api/workflow-studio/setup-drafts',SHA=/^[a-f0-9]{64}$/,SCOPE=/^[a-f0-9]{32}$/,PAGE=20,MAX=256,NAMES={recipe_graph:'Recipe and graph',wording:'Wording',references:'References and inputs',controls:'Controls',lineage:'Lineage',batch:'Batch',pending_inputs:'Pending inputs',authoring:'Authoring time (browser clock)',runtime:'Recorded runtime'};
  const need=(ok,message)=>{if(!ok)throw Error(message);},int=(v,max=MAX)=>Number.isSafeInteger(v)&&v>=1&&v<=max,saved=t=>t==null||typeof t==='number'&&Number.isFinite(t)&&t>0&&t<4102444800;
  function frame(v,format,ws,id){
    need(v&&typeof v==='object'&&v.format===format&&v.workspace_id===ws&&v.draft_id===id,'The history response belongs to a different Workspace, setup or format.');
    need(v.observation_only===true&&v.generation_submitted===false&&v.staging_performed===false&&v.dependencies_checked===false,'The history response lacks its read-only guarantees.');
    need(int(v.head_revision)&&SHA.test(v.head_record_sha256),'The history head observation is invalid.');
  }
  function page(v,ws,id,before,head){
    frame(v,'studio.setup-history-page/v2',ws,id);need(head===null||v.head_revision===head,'The setup changed while history was open. Refresh history to start again.');
    const r=v.revisions;need(Array.isArray(r)&&r.length<=PAGE&&(r.length>0||before===1),'The history page is malformed.');let want=before===null?v.head_revision:before-1;
    for(const s of r){need(s&&s.revision===want&&SHA.test(s.record_sha256)&&SHA.test(s.draft_sha256)&&SHA.test(s.graph_sha256)&&typeof s.preset_id==='string'&&typeof s.backend_id==='string'&&Number.isSafeInteger(s.input_count)&&s.input_count>=0&&int(s.record_bytes,2**31)&&saved(s.recorded_at),'A history summary is malformed or out of order.');want--;}
    need(v.next_before_revision===(r.length&&want>=1?r[r.length-1].revision:null),'The history continuation is inconsistent.');return v;
  }
  const side=s=>s&&SHA.test(s.sha256)&&Number.isSafeInteger(s.bytes)&&s.bytes>=0&&(s.preview===null||typeof s.preview==='string'&&[...s.preview].length<=1024)&&typeof s.truncated==='boolean'&&Number.isSafeInteger(s.omitted_bytes)&&s.omitted_bytes>=0&&typeof s.redacted==='boolean';
  function compared(v,ws,id,head,left,right){
    frame(v,'studio.setup-history-compare/v2',ws,id);need(v.head_revision===head,'The setup changed while history was open. Refresh history to start again.');
    need(v.left_revision===left&&v.right_revision===right&&SHA.test(v.left_record_sha256)&&SHA.test(v.right_record_sha256),'The comparison names different revisions.');
    need(Array.isArray(v.sections)&&v.sections.length>=1&&v.sections.length<=16&&v.sections.every(s=>s&&typeof s.section==='string'&&s.section.length<=64&&typeof s.changed==='boolean'&&side(s.left)&&side(s.right)),'The comparison is malformed.');return v;
  }
  // Reports differences between neighbouring summaries; the save time is shown beside it, not compared.
  function change(a,i,list){
    if(a.revision===1)return 'First revision.';const older=list[i+1];if(!older)return 'Older revisions are not loaded yet.';
    const parts=[];if(a.draft_sha256!==older.draft_sha256)parts.push('draft');if(a.preset_id!==older.preset_id)parts.push('preset '+older.preset_id+' to '+a.preset_id);if(a.backend_id!==older.backend_id)parts.push('backend '+older.backend_id+' to '+a.backend_id);if(a.graph_sha256!==older.graph_sha256)parts.push('graph');if(a.input_count!==older.input_count)parts.push('input files '+older.input_count+' to '+a.input_count);
    return parts.length?'Changed from revision '+older.revision+': '+parts.join(', ')+'.':'No draft, preset, backend, graph or input-count difference from revision '+older.revision+' in this summary.';
  }
  class History{
    constructor(options){Object.assign(this,options);this.token=0;this.sel=0;this.state={head:null,revisions:[],next:null,picked:[],comparison:null,busy:false};}
    note(message,error=false){this.emit({message,error,state:this.state});}
    where(){const s=this.identity()||{};need(SCOPE.test(s.workspace_id||'')&&typeof s.draft_id==='string'&&s.draft_id,'No shared setup revision is saved in this session yet. Nothing was requested.');return {ws:s.workspace_id,id:s.draft_id};}
    url(kind,query){const {ws,id}=this.where();return API+'/'+encodeURIComponent(id)+'/'+kind+'?workspace_id='+ws+query;}
    exportUrl(revision){return this.url('export','&revision='+revision);}
    // A read is dropped, result or refusal, once a newer read began or its own `live` check (the selected pair) no longer holds.
    async go(label,load,done,live=()=>true){const t=++this.token,fresh=()=>t===this.token&&live();this.state.busy=true;this.note(label);
      try{const value=await load(this.where());if(!fresh()){if(t===this.token)this.state.busy=false;return;}done(value);this.state.busy=false;}
      catch(e){if(!fresh()){if(t===this.token)this.state.busy=false;return;}this.state.busy=false;this.note('History could not be read: '+e.message+' Nothing was changed.',true);}}
    load(){return this.go('Reading the newest revisions. This is read-only.',async({ws,id})=>page(await this.read(this.url('history','&limit='+PAGE)),ws,id,null,null),v=>{
      Object.assign(this.state,{head:v.head_revision,revisions:v.revisions.slice(),next:v.next_before_revision,picked:[],comparison:null});
      this.note('Showing '+v.revisions.length+' of '+v.head_revision+' revisions, newest first.'+(v.next_before_revision?' Older revisions are available.':''));});}
    older(){const {head,next}=this.state;return this.go('Reading older revisions. This is read-only.',async({ws,id})=>{need(next,'No older revisions remain.');return page(await this.read(this.url('history','&limit='+PAGE+'&before_revision='+next+'&expected_head='+head)),ws,id,next,head);},v=>{
      this.state.revisions.push(...v.revisions);this.state.next=v.next_before_revision;this.note('Loaded '+v.revisions.length+' older revisions; '+this.state.revisions.length+' of '+head+' are listed.');});}
    pick(revision,on){const p=this.state.picked;
      if(on&&p.length>=2){this.note('Two revisions are already selected. Clear one first.',true);return false;}
      this.state.picked=on?[...p,revision].sort((a,b)=>a-b):p.filter(n=>n!==revision);this.state.comparison=null;this.sel++;return true;}
    compare(){const [left,right]=this.state.picked,head=this.state.head,sel=this.sel,same=()=>this.sel===sel&&this.state.picked.join()===left+','+right;
      return this.go('Comparing revisions '+left+' and '+right+'. This is read-only.',async({ws,id})=>{need(this.state.picked.length===2,'Select exactly two revisions to compare.');return compared(await this.read(this.url('compare','&left='+left+'&right='+right+'&expected_head='+head)),ws,id,head,left,right);},v=>{
        this.state.comparison=v;this.note('Compared revision '+left+' with revision '+right+': '+v.sections.filter(s=>s.changed).length+' of '+v.sections.length+' sections differ.');},same);}
  }
  function mount(w,options={}){
    const d=w.document;if(d.querySelector('#setupHistory'))return;const panel=d.querySelector('#sharedSetupPanel');
    if(!panel){d.addEventListener('studio:setup-draft-ready',()=>mount(w,options),{once:true});return;}
    const el=(tag,text)=>{const n=d.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
    async function read(path){
      const abort=new w.AbortController(),timer=w.setTimeout(()=>abort.abort(),15000);
      try{const response=await w.fetch(path,{signal:abort.signal,headers:{Accept:'application/json'}});const text=await response.text();need(text.length<=1048576,'The history response exceeded its size limit.');
        let value;try{value=JSON.parse(text);}catch(_){throw Error('The history response was unreadable.');}
        if(!response.ok)throw Error((value&&typeof value.error==='string'?value.error:'History is unavailable')+' (HTTP '+response.status+').');return value;}
      finally{w.clearTimeout(timer);}
    }
    const details=el('details'),status=el('p'),list=el('ul'),view=el('section'),refresh=el('button','Refresh history'),older=el('button','Load older revisions'),compare=el('button','Compare selected revisions'),actions=el('div');
    details.id='setupHistory';details.className='shared-setup-history';status.id='setupHistoryStatus';status.tabIndex=-1;status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    list.id='setupHistoryList';list.setAttribute('aria-label','Setup revisions, newest first');view.id='setupHistoryComparison';view.setAttribute('aria-label','Revision comparison');
    for(const [b,id] of [[refresh,'setupHistoryRefresh'],[older,'setupHistoryOlder'],[compare,'setupHistoryCompare']]){b.type='button';b.id=id;b.dataset.key=id;}
    actions.append(refresh,older,compare);
    details.append(el('summary','Workspace history (read-only)'),el('p','Browse the saved Workspace revisions of the shared setup and compare two of them. Viewing never changes Create, restores a revision, starts generation or copies files. Each revision shows when its save was recorded, when the Workspace has that time.'),status,actions,list,view);
    panel.append(details);
    const history=new History({read:options.read||read,identity:options.identity||(()=>w.StudioSetupApply&&w.StudioSetupApply.controller&&w.StudioSetupApply.controller.state),emit:paint});
    function paint(event){
      const s=event.state,held=d.activeElement&&d.activeElement.dataset&&d.activeElement.dataset.key;status.textContent=event.message||'';
      older.hidden=!s.next;compare.disabled=s.picked.length!==2;
      list.replaceChildren(...s.revisions.map((r,i)=>{
        const li=el('li'),label=el('label'),box=el('input'),link=el('a','Download inspection export, revision '+r.revision),when=r.recorded_at==null?el('div','Save time not recorded'):el('time',new Date(r.recorded_at*1000).toLocaleString());
        if(r.recorded_at!=null)when.setAttribute('datetime',new Date(r.recorded_at*1000).toISOString());
        box.type='checkbox';box.checked=s.picked.includes(r.revision);box.disabled=!box.checked&&s.picked.length>=2;box.dataset.key='pick-'+r.revision;box.addEventListener('change',()=>{if(!history.pick(r.revision,box.checked)){box.checked=false;return;}paint({state:history.state,message:history.state.picked.length===2?'Revisions '+history.state.picked.join(' and ')+' selected. Compare is ready.':'Selected revisions: '+(history.state.picked.join(', ')||'none')+'.'});});
        label.append(box,' Revision '+r.revision+(r.revision===s.head?' (current head)':''));
        link.href=history.exportUrl(r.revision);link.setAttribute('download','setup-revision-'+r.revision+'-inspection.json');link.dataset.key='export-'+r.revision;
        li.append(when,label,el('div','Preset'+r.preset_id+' · backend '+r.backend_id+' · '+r.input_count+' input file'+(r.input_count===1?'':'s')+' · record '+r.record_sha256.slice(0,12)),el('div',change(r,i,s.revisions)),link);return li;}));
      const c=s.comparison;view.replaceChildren(...(c?[el('h4','Revision '+c.left_revision+' compared with revision '+c.right_revision),el('p','Previews are shown as stored text; they are not a replacement revision and carry no authority.'),(()=>{const ul=el('ul');ul.append(...c.sections.map(x=>{
        const li=el('li'),side=(name,v)=>{const box=el('div'),pre=el('pre',v.redacted?'Redacted: only the hash and byte length are shown.':v.preview);box.append(el('strong',name+' · '+v.bytes+' bytes · sha256 '+v.sha256.slice(0,12)),pre);if(v.truncated)box.append(el('small','Truncated: '+v.omitted_bytes+' bytes are not shown.'));return box;};
        li.append(el('strong',(NAMES[x.section]||x.section)+': '+(x.changed?'changed':'unchanged')));if(x.changed)li.append(side('Revision '+c.left_revision,x.left),side('Revision '+c.right_revision,x.right));return li;}));return ul;})()]:[]));
      if(held){const again=[...details.querySelectorAll('[data-key]')].find(n=>n.dataset.key===held&&!n.hidden&&!n.disabled);if(again){if(again!==d.activeElement)again.focus();}else status.focus();}
    }
    details.addEventListener('toggle',()=>{if(details.open)history.load().catch(()=>{});});
    refresh.addEventListener('click',()=>history.load());older.addEventListener('click',()=>history.older());compare.addEventListener('click',()=>history.compare());
    w.StudioSetupHistory=Object.assign(w.StudioSetupHistory||{},{history});
  }
  return {History,mount,page,compared,change};
});
