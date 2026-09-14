/* Exact, read-only setup review. No mutation, upload or execution interface. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.StudioSetupProposal=api;})(typeof window!=='undefined'?window:null,function(){
  'use strict';
  const FORMAT='studio.setup-proposal/v1',API='/api/workflow-studio/setup-proposal',HASH=/^[0-9a-f]{64}$/;
  const clone=x=>JSON.parse(JSON.stringify(x));
  function need(ok,message){if(!ok)throw Error(message);}
  function stable(x){if(Array.isArray(x))return '['+x.map(stable).join(',')+']';if(x&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+stable(x[k])).join(',')+'}';return JSON.stringify(x);}
  const same=(a,b)=>stable(a)===stable(b);
  function expectedDiff(before,intent){const r=before.recipe;return [
    ['Recipe',{preset:r.preset,template:before.templateHash},{preset:intent.preset_id,template:intent.template_sha256}],
    ['Settings and wording',r.controls,intent.controls],['Batch',r.batch,intent.batch],['References',r.references,intent.sources],
    ['Lineage',{parents:r.parent_assets,by_input:r.parent_by_input},intent.lineage],
    ['Continuation context',r.continuation??null,null],['Pending local inputs',before.pendingInputs,[]]
  ].map(([section,before,proposed])=>({section,before,proposed,changed:!same(before,proposed)}));}
  async function sha256(text){need(globalThis.crypto?.subtle,'Exact review requires a secure browser context. Open Studio on its configured loopback address.');return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),x=>x.toString(16).padStart(2,'0')).join('');}
  async function validate(r,q,hashText=sha256){
    const message='Setup proposal response does not match the captured request.';
    need(r&&r.format===FORMAT&&r.can_apply===false&&r.generation_submitted===false&&r.execution_authorized===false,message);
    need(same(r.request,q)&&same(r.before,q.draft)&&r.precondition?.scope==='caller-declared browser draft; not a server revision'&&HASH.test(r.precondition?.draft_sha256||''),message);
    need(typeof r.proposal_json==='string'&&new TextEncoder().encode(r.proposal_json).length<=1048576&&HASH.test(r.proposal_sha256||''),message);
    const {proposal_json,proposal_sha256,...body}=r;
    need(same(JSON.parse(proposal_json),body)&&await hashText(proposal_json)===proposal_sha256,message);
    need(r.intent?.preset_id===q.preset_id&&r.intent?.template_sha256===q.expected_template_sha256&&r.intent.batch===1,message);
    need(r.intent.controls&&typeof r.intent.controls==='object'&&!Array.isArray(r.intent.controls)&&!['reference','last_reference'].some(k=>Object.hasOwn(r.intent.controls,k)),message);
    for(const key of ['positive','negative'])need((r.intent.controls[key]??'')===q[key],message);
    need(Array.isArray(r.intent.sources)&&r.intent.sources.length===q.sources.length&&r.intent.sources.every((x,i)=>x?.asset_id===q.sources[i].asset_id&&x.sha256===q.sources[i].sha256&&x.role===q.sources[i].role&&x.slot===i+1&&x.staged===false&&Array.isArray(x.binding)&&x.binding.length===2&&x.binding[1]==='image'&&['contribution','avoid'].every(k=>x[k]===q.guidance[i][k].trim())),message);
    need(same(r.diff,expectedDiff(q.draft,r.intent))&&Array.isArray(r.side_effects)&&Array.isArray(r.limits)&&Array.isArray(r.observation?.candidate?.checks),message);
    return r;
  }
  class Session{
    constructor(transport,matches,emit,options={}){this.transport=transport;this.matches=matches;this.emit=emit;this.hashText=options.hashText||sha256;this.set=options.set||(fn=>setTimeout(fn,15000));this.clear=options.clear||(id=>clearTimeout(id));this.epoch=0;this.busy=false;this.current=null;}
    invalidate(message='Proposal inputs changed. Build a new preview.'){this.epoch++;const a=this.current;this.current=null;this.busy=false;if(a){this.clear(a.timer);a.controller.abort();}this.emit({busy:false,message});}
    async load(value){
      if(this.busy)return;const q=clone(value),epoch=++this.epoch,active={controller:new AbortController(),timer:null};this.current=active;this.busy=true;this.emit({busy:true,message:'Building a review-only proposal…'});
      active.timer=this.set(()=>{if(this.current===active)this.invalidate('The preview timed out. No proposal was accepted. Retry explicitly.');});
      const current=()=>epoch===this.epoch&&this.current===active;
      try{const response=await this.transport(q,active.controller.signal);if(!current())return;need(this.matches(),'The current draft changed. Close this preview and check recipes again.');const report=await validate(response,q,this.hashText);if(!current())return;need(this.matches(),'The draft changed while the proposal was checked. Reopen the chooser.');this.busy=false;this.emit({busy:false,report});}
      catch(error){if(current()){this.busy=false;this.emit({busy:false,message:String(error?.message||error)});}}
      finally{this.clear(active.timer);if(this.current===active){this.current=null;this.busy=false;}}
    }
  }
  function mount(w,options={}){
    const d=w.document,$=s=>d.querySelector(s);if(!$('#createView')||$('#setupProposalDialog'))return;
    function el(tag,text,cls){const n=d.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
    const dialog=el('dialog',undefined,'setup-proposal');dialog.id='setupProposalDialog';dialog.setAttribute('aria-labelledby','setupProposalTitle');
    const title=el('h2','Review a proposed setup');title.id='setupProposalTitle';
    const close=el('button','Close preview');close.type='button';close.id='closeSetupProposal';
    const heading=el('div',undefined,'proposal-heading');heading.append(title,close);
    const intro=el('p','Nothing is applied here. Review the target defaults, wording and every source before a future setup handoff. Your current Create setup stays untouched.');
    const summary=el('p',undefined,'muted');summary.id='setupProposalSummary';
    const inputs=el('details'),inputsTitle=el('summary','Wording and source contributions');inputs.id='setupProposalInputs';inputs.open=true;inputs.append(inputsTitle);
    const form=el('form'),positive=el('textarea'),negative=el('textarea'),sources=el('div');
    positive.id='proposalPositive';negative.id='proposalNegative';positive.maxLength=negative.maxLength=8000;positive.rows=3;negative.rows=2;
    function field(parent,labelText,input){const label=el('label',labelText);label.htmlFor=input.id;parent.append(label,input);}
    field(form,'Desired result — starts from your current wording, not a recipe example',positive);field(form,'Negative wording — clear this for a route without a negative-prompt input',negative);
    form.append(sources);const build=el('button','Build proposal');build.id='buildSetupProposal';build.type='submit';form.append(build);
    const status=el('p','Review wording and source contributions, then build the proposal.');status.id='setupProposalStatus';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const output=el('div');output.id='setupProposalResult';const download=el('button','Export proposal JSON');download.id='exportSetupProposal';download.type='button';download.disabled=true;
    inputs.append(form);dialog.append(heading,intro,summary,inputs,status,output,download,el('p','Export contains your captured prompt, reference metadata and proposed settings. No image bytes are included.','muted'));d.body.append(dialog);
    let context=null,before=null,stamp=null,opener=null,report=null,stale=false;
    const fields=[];
    const matches=()=>!!context&&!stale&&stamp===w.StudioSetupDraft?.stamp();
    const session=new Session(async(q,signal)=>{
      const response=await w.fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q),signal});const text=await response.text();need(new TextEncoder().encode(text).length<=2*1048576,'Proposal exceeds the browser response limit.');
      let value;try{value=JSON.parse(text);}catch(_){throw Error('The preview response was unreadable. Retry explicitly.');}need(response.ok,typeof value?.error==='string'?value.error:'Setup preview unavailable.');return value;
    },matches,event=>{report=null;output.replaceChildren();download.disabled=true;build.disabled=event.busy||stale;dialog.setAttribute('aria-busy',String(event.busy));if(event.report){report=event.report;render(report);download.disabled=false;}else status.textContent=event.message;},options);
    function invalidate(message,contextChanged=false){if(!dialog.open)return;if(contextChanged)stale=true;session.invalidate(message);}
    function render(r){
      status.textContent='Proposal ready for review only. No settings, files or jobs were changed.';
      inputs.open=false;inputsTitle.textContent='Edit wording and source contributions';const resultTitle=el('h3','What would change');resultTitle.tabIndex=-1;output.append(resultTitle);
      for(const row of r.diff){const detail=el('details',undefined,'proposal-change');detail.open=row.changed&&['Recipe','Settings and wording','References','Batch','Pending local inputs'].includes(row.section);detail.append(el('summary',row.section+' · '+(row.changed?'would change':'unchanged')));
        if(row.section==='Settings and wording'){
          const table=el('table'),head=el('tr');for(const label of ['Control','Current','Proposed'])head.append(el('th',label));const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
          for(const key of Array.from(new Set([...Object.keys(row.before),...Object.keys(row.proposed)])).sort()){const tr=el('tr');tr.append(el('th',key),el('td',Object.hasOwn(row.before,key)?String(row.before[key]):'Not present'),el('td',Object.hasOwn(row.proposed,key)?String(row.proposed[key]):'Would be removed'));body.append(tr);}table.append(body);detail.append(table);
        }else if(row.section==='References'){
          detail.append(el('p',row.before.length+' current role reference(s) would be replaced. Any filename-based inputs are listed in Settings and wording.'));
          for(const item of row.proposed){const card=el('section',undefined,'proposal-source');card.append(el('h4','Picture '+item.slot+' · '+item.title+' · '+item.role),el('p','Use: '+(item.contribution||'the assigned visual role')+' · Do not transfer: '+(item.avoid||'unrequested details')));
            const t=item.transform;card.append(el('p',item.width+' × '+item.height+' source pixels · '+t.policy+(t.resized_size?' → '+t.resized_size.join(' × '):'')));
            const exact=el('details');exact.append(el('summary','Exact source, slot and transform'),el('pre',JSON.stringify(item,null,2)));card.append(exact);detail.append(card);}
        }else{const columns=el('div',undefined,'proposal-columns');for(const [label,value]of [['Current',row.before],['Proposed',row.proposed]]){const box=el('section');box.append(el('h4',label),el('pre',JSON.stringify(value,null,2)));columns.append(box);}detail.append(columns);}output.append(detail);
      }
      if(r.intent.compiled_positive!==null){const detail=el('details');detail.append(el('summary','Exact primary prompt after role guidance'),el('pre',r.intent.compiled_positive),el('p','This uses the existing reference compiler. Any other positive bindings receive the unprefixed desired-result text.'));output.append(detail);}
      const holds=el('details');holds.append(el('summary','Prerequisites and remaining checks'));for(const item of r.observation.candidate.checks)holds.append(el('p',item.message));output.append(holds);
      const boundaries=el('details');boundaries.append(el('summary','Side effects and limits'));for(const note of [...r.side_effects,...r.limits])boundaries.append(el('p',note,'muted'));output.append(boundaries);
      const identity=el('details');identity.append(el('summary','Proposal identity and draft boundary'),el('code',r.proposal_sha256),el('p',r.precondition.scope));output.append(identity);const apply=w.StudioSetupApply?.offer?.(r,()=>dialog.open&&report===r&&matches());if(apply)output.append(apply);dialog.scrollTop=0;resultTitle.focus({preventScroll:true});
    }
    function open(event){
      try{
        const detail=event.detail;need(detail&&Array.isArray(detail.sources)&&detail.sources.length>=1&&detail.sources.length<=3,'Choose exact source images before previewing a setup.');
        need(w.StudioSetupDraft,'The Create draft is not available yet.');before=w.StudioSetupDraft.capture();need(before,'Select a current Create recipe before reviewing a replacement.');
        need(!w.StudioSetupDraft.busy(),'Wait for the current reference attachment to settle before previewing.');
        context=clone(detail);stamp=w.StudioSetupDraft.stamp();stale=false;opener=d.activeElement;report=null;
        positive.value=before.recipe.controls.positive||'';negative.value=before.recipe.controls.negative||'';fields.length=0;sources.replaceChildren();
        summary.textContent='Target: '+context.preset_id+' · '+context.sources.length+' source image(s). Sampling and adapter settings start from the target graph defaults; the comparison lists every removed current control.';
        context.sources.forEach((source,index)=>{const box=el('fieldset');box.append(el('legend','Picture '+(index+1)+' · '+source.role));const contribution=el('textarea'),avoid=el('textarea');contribution.id='proposalContribution'+(index+1);avoid.id='proposalAvoid'+(index+1);contribution.rows=avoid.rows=2;contribution.maxLength=avoid.maxLength=1500;
          field(box,'Use from this image',contribution);field(box,'Do not transfer',avoid);box.append(el('small','Workspace identity: '+source.asset_id));fields.push({contribution,avoid});sources.append(box);});
        inputs.open=true;inputsTitle.textContent='Wording and source contributions';session.invalidate('Review wording and contributions, then build the proposal.');if(!dialog.open)dialog.showModal();positive.focus();
      }catch(error){const message=$('#shortlistStatus');if(message)message.textContent=error.message;}
    }
    form.onsubmit=e=>{e.preventDefault();try{need(matches(),'The draft or recipe advice changed. Close this preview and check again.');need(!w.StudioSetupDraft.busy(),'A reference attachment is in progress. Reopen after it settles.');session.load({...context,draft:before,positive:positive.value,negative:negative.value,guidance:fields.map(x=>({contribution:x.contribution.value,avoid:x.avoid.value}))});}catch(error){invalidate(error.message,true);}};
    form.addEventListener('input',()=>invalidate('Wording or contributions changed. Build a new proposal.'));
    download.onclick=()=>{try{need(report&&matches(),'The draft changed; this proposal cannot be exported as current.');const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),link=el('a');link.href=url;link.download='setup-proposal-'+report.proposal_sha256.slice(0,12)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){invalidate(error.message,true);}};
    close.onclick=()=>dialog.close();dialog.addEventListener('close',()=>{session.invalidate('Preview closed. Any explicit setup operation is reported in Shared setup & recovery.');if(opener?.isConnected)opener.focus();else $('#checkStartingRecipes')?.focus();});
    d.addEventListener('studio:setup-proposal',open);
    d.addEventListener('studio:shortlist-invalidated',()=>invalidate('Recipe advice changed. Close this preview and check again.',true));
    d.addEventListener('studio:recipe',()=>invalidate('The Create setup changed. Close this preview and check again.',true));
    for(const name of ['input','change'])$('#createView').addEventListener(name,()=>invalidate('The Create inputs changed. Close this preview and check again.',true));
    w.addEventListener('pagehide',()=>{session.invalidate('Preview closed.');if(dialog.open)dialog.close();});
    w.addEventListener('hashchange',()=>{if(w.location.hash!=='#create'&&dialog.open)dialog.close();});
  }
  return{validate,Session,same,mount};
});
