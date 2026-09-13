/* A client of the existing WorkflowDocuments service and retained-save state. */
(function(root){
  'use strict';
  const C=root.BundleWorkflowCore,P=root.WorkflowProjectState;
  const element=(tag,text,attrs={})=>{const node=document.createElement(tag);if(text!==null)node.textContent=text;for(const [k,v]of Object.entries(attrs))node.setAttribute(k,v);return node;};
  function mount(host,capture){
    if(!C||!P)return;
    const box=element('details',null,{class:'bundle-workflow'}),summary=element('summary','Keep this setup as a reusable workflow');
    const name=element('input',null,{maxlength:'160','aria-label':'Reusable workflow name'}),nameLabel=element('label','Workflow name');nameLabel.append(name);
    const preview=element('div',null,{class:'bundle-workflow-preview'}),message=element('p','Prepare a Steps document, inspect it, then save a new Workspace copy. No generation.',{role:'status'});
    const toolbar=element('div',null,{class:'bundle-workflow-actions'});
    const prepare=element('button','Prepare workflow',{type:'button','data-bundle-workflow':'prepare'}),download=element('button','Download document',{type:'button','data-bundle-workflow':'download'}),save=element('button','Save new workflow',{type:'button','data-bundle-workflow':'save'}),retry=element('button','Retry retained save',{type:'button','data-bundle-workflow':'retry'});
    const consent=element('input',null,{type:'checkbox','data-bundle-workflow':'consent'}),consentLabel=element('label',null,{class:'bundle-consent'});consentLabel.append(consent,document.createTextNode('Save this reviewed snapshot as a new shared workflow.'));
    const link=element('a','Go to Workflow builder →',{href:'/workflow-studio.html#builder'});link.hidden=true;
    toolbar.append(prepare,download,save,retry);box.append(summary,element('p','Retain the complete graph, including disabled-by-strength adapters. Named Steps expose the actual inputs; later saves use the builder’s revision checks.'),nameLabel,preview,consentLabel,toolbar,message,link);host.append(box);
    let state=null,prepared=null,captured=null,busy=false,epoch=0,saved=false;
    const live=()=>box.isConnected;
    const say=text=>{message.textContent=text;};
    const snapshot=()=>C.signature({bundle:capture(),name:name.value});
    try{name.value=((capture().recipe?.name||'Bundle')+' — reusable').slice(0,160);}catch{name.value='Bundle workflow';}
    try{state=new P.State(sessionStorage,()=>crypto.randomUUID());}catch(error){say('Shared saving is unavailable: '+error.message+'. You can still prepare and download a document.');}
    const ourPending=()=>!!state?.pending&&state.pending.path===P.PREFIX&&state.pending.operation==='save'&&state.pending.body.document?.source?.bundle?.format==='studio.bundle-source/v1';
    function sync(){
      const pending=!!state?.pending;
      prepare.disabled=busy||pending;download.disabled=!prepared||busy;
      save.disabled=busy||!state||pending||!prepared||!consent.checked||saved;
      retry.hidden=!ourPending();retry.disabled=busy;
      if(pending&&!ourPending()){link.hidden=false;link.href='/workflow-studio.html#builder';say('Another Workflow builder save is retained. Resolve that exact request there before saving this bundle.');}
      else if(pending&&!busy)say('A bundle save is retained. Retry the same request to reconcile it; do not create a new copy.');
    }
    async function request(path,body){
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
      try{
        const r=await fetch(path,{...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),signal:controller.signal});
        const text=await r.text();if(text.length>2*1024*1024)throw Error('Workflow response exceeded the browser limit.');
        const value=JSON.parse(text);C.check(value);
        if(!r.ok){const error=Error(value.error||'Workflow request failed');error.status=r.status;throw error;}
        return value;
      }finally{clearTimeout(timer);}
    }
    name.oninput=()=>{epoch++;prepared=null;consent.checked=false;saved=false;preview.replaceChildren();link.hidden=true;say('Name changed. Prepare and review a fresh document.');sync();};
    consent.onchange=sync;
    prepare.onclick=async()=>{
      if(busy||state?.pending)return;busy=true;const ticket=++epoch;prepared=null;preview.replaceChildren();consent.checked=false;saved=false;link.hidden=true;sync();
      try{
        const source=capture(),expected=snapshot();
        const response=await request('/api/workflow-studio/presets/'+encodeURIComponent(source.preset.id));
        if(!live()||ticket!==epoch)return;
        if(snapshot()!==expected)throw Error('The bundle changed while preparing. Review it and prepare again.');
        if(response.generation_submitted!==false)throw Error('Unexpected authoring response. No save was made.');
        const result=C.build(source,response.document,name.value);
        prepared=result.document;captured=expected;
        preview.replaceChildren(element('h4',prepared.name),element('p',Object.keys(prepared.nodes).length+' nodes · '+result.steps+' named Steps · '+result.bindings+' bound inputs.'));
        const list=element('dl',null);
        for(const step of prepared.steps){list.append(element('dt',step.name),element('dd',step.controls.map(c=>c.name).join(' · ')||step.description));}
        preview.append(list,element('p','New authoring document, not an executed or approved result. Model files stay external; server validation and runtime readiness are separate.'));
        say(state?'Prepared. Review the Steps before saving or downloading.':'Prepared for download. Browser storage is required for shared saving.');
      }catch(error){if(live()&&ticket===epoch){prepared=null;say(error.message);}}
      finally{busy=false;sync();}
    };
    download.onclick=()=>{
      if(!prepared)return;
      try{
        if(snapshot()!==captured)throw Error('The bundle changed. Prepare again before exporting.');
        const url=URL.createObjectURL(new Blob([JSON.stringify(prepared,null,2)],{type:'application/json'})),a=element('a',null,{href:url,download:'bundle-workflow.json'});
        a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say('Document downloaded. Import it in Workflow builder; no work was queued.');
      }catch(error){say(error.message);}
    };
    async function sendPending(){
      if(busy||!ourPending())return;busy=true;state.busy=true;sync();
      const pending=JSON.parse(JSON.stringify(state.pending));
      try{
        const result=await request(pending.path,pending.body);
        await C.receipt(result,pending);
        // A replacement bundle may already display this retained operation. Leave it
        // recoverable if this panel disappeared rather than clearing unseen evidence.
        if(!live())return;
        if(sessionStorage.getItem(P.KEY)!==JSON.stringify(pending))throw Error('The retained save record changed. Resolve it in Workflow builder.');
        state.success(result,prepared);saved=true;consent.checked=false;
        link.href='/workflow-studio.html#builder';link.hidden=false;
        say('Saved '+result.document.name+' as '+result.id+', revision '+result.revision+(result.head_revision>1?' (current head is revision '+result.head_revision+')':'')+'. In Workflow builder, use Refresh saved, select this name, then Open current and Steps view.');
      }catch(error){
        if(!live())return;
        try{state.failure(error.status);}catch{/* Retain the in-memory request when storage is unavailable. */}
        say(error.message+(state.pending?' The exact save request is retained. Retry retained save explicitly.':''));
      }finally{busy=false;state.busy=false;if(live())sync();}
    }
    save.onclick=async()=>{
      if(save.disabled)return;
      try{
        if(snapshot()!==captured)throw Error('The bundle changed. Prepare and review again before saving.');
        // Always a new record. Subsequent edits belong to existing shared commands.
        state.begin(prepared,true);await sendPending();
      }catch(error){say(error.message);sync();}
    };
    retry.onclick=sendPending;sync();
  }
  root.BundleWorkflow={mount};
})(globalThis);
