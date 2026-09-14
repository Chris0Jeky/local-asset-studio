/* Read-only starting-preset advice. Selection and execution stay with Create. */
(function(root,factory){
  const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;
  if(root&&root.document){root.RecipeShortlist=api;if(root.document.readyState==='loading')root.addEventListener('DOMContentLoaded',()=>api.mount(root),{once:true});else api.mount(root);}
})(typeof window!=='undefined'?window:null,function(){
  'use strict';
  const goals={'new-image':'Create a new image','edit-image':'Change an existing image','reference-image':'Create with pose or identity references','upscale-image':'Upscale an image','masked-repair':'Repair a selected region','animate-image':'Animate an image','image-to-3d':'Build 3D from an image'};
  const sourceRoles={source:'Whole image / first frame',identity:'Identity guidance',pose:'Pose guidance',style:'Style guidance',costume:'Costume guidance',composition:'Composition guidance'};
  const statuses={observed:'Listed prerequisites observed',unknown:'Some checks are unknown',needs_setup:'Needs attention before preparation'};
  const plain=x=>!!x&&typeof x==='object'&&!Array.isArray(x),integer=(x,lo,hi)=>Number.isSafeInteger(x)&&x>=lo&&x<=hi;
  const hash=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x),text=(x,max)=>typeof x==='string'&&x.length<=max;
  function need(ok,message){if(!ok)throw Error(message);}
  function sourceMatches(x,want){return plain(x)&&x.asset_id===want.asset_id&&x.sha256===want.sha256&&x.role===want.role&&x.bytes_verified===true&&x.staged===false&&text(x.title,160)&&integer(x.width,1,Number.MAX_SAFE_INTEGER)&&integer(x.height,1,Number.MAX_SAFE_INTEGER);}
  function boardShape(candidate){
    const board=candidate?.reference_board;
    return plain(board)&&Object.keys(board).sort().join(',')==='minimum,slot_count,source_input'
      &&candidate.operation==='restyle'&&integer(board.minimum,1,3)&&integer(board.slot_count,board.minimum,3)
      &&board.source_input==='last_reference'&&candidate.reference_count===board.slot_count+1?board:null;
  }
  function assignmentMatches(a,want,slot,board){
    const modes=board?['style-board','unsupported']:['whole-image','prompt-guidance','unsupported'];
    const binding=a?.binding;
    return plain(a)&&a.asset_id===want.asset_id&&a.sha256===want.sha256&&a.role===want.role&&a.slot===slot
      &&modes.includes(a.role_mode)&&(binding===null||Array.isArray(binding)&&binding.length===2&&text(binding[0],96)&&binding[1]==='image')
      &&(!board||a.role_mode!=='style-board'||binding!==null);
  }
  function validate(r,q){
    const message='Shortlist response does not match this request context. Check again.';
    need(plain(r)&&r.format==='studio.recipe-shortlist/v1'&&r.goal===q.goal&&r.reference_count===q.reference_count,message);
    if(q.source_asset_id){
      const x=r.source;need(plain(x)&&x.asset_id===q.source_asset_id&&x.sha256===q.source_sha256&&x.role===q.source_role&&x.bytes_verified===true&&x.staged===false&&text(x.title,160)&&integer(x.width,1,Number.MAX_SAFE_INTEGER)&&integer(x.height,1,Number.MAX_SAFE_INTEGER),message);
    }else need(r.source===undefined||r.source===null,message);
    if(q.sources!==undefined){
      need(!q.source_asset_id&&Array.isArray(q.sources)&&q.sources.length>=1&&q.sources.length<=3&&Array.isArray(r.sources)&&r.sources.length===q.sources.length,message);
      need(r.sources.every((x,i)=>sourceMatches(x,q.sources[i])&&x.slot===i+1),message);
    }else need(r.sources===undefined||r.sources===null,message);
    need(r.generation_submitted===false&&r.execution_authorized===false&&hash(r.snapshot_sha256),message);
    need(!q.expected_snapshot||q.expected_snapshot===r.snapshot_sha256,message);
    need(integer(r.total,0,256)&&r.offset===q.offset&&Array.isArray(r.candidates)&&r.candidates.length<=q.limit&&r.candidates.length<=12,message);
    need(r.candidates.length===Math.min(q.limit,Math.max(0,r.total-r.offset)),message);
    need(r.next_offset===(r.offset+q.limit<r.total?r.offset+q.limit:null),message);
    need(plain(r.counts)&&Object.keys(statuses).every(k=>integer(r.counts[k],0,256))&&Object.keys(statuses).reduce((n,k)=>n+r.counts[k],0)===r.total,message);
    need(Number.isFinite(r.checked_at)&&text(r.scope,2000)&&Array.isArray(r.diagnostics)&&r.diagnostics.length<=256,message);
    const seen=new Set();
    for(const c of r.candidates){
      need(plain(c)&&text(c.preset_id,96)&&/^[A-Za-z0-9_.-]+$/.test(c.preset_id)&&!seen.has(c.preset_id)&&Object.hasOwn(statuses,c.status),message);seen.add(c.preset_id);
      const board=boardShape(c),ordinary=c.reference_board===undefined&&integer(c.reference_count,0,3);
      need(text(c.name,160)&&text(c.description,800)&&text(c.backend_id,96)&&text(c.operation,96)&&text(c.prompt_role,96)&&(ordinary||!!board),message);
      need(c.template_sha256===null||c.template_sha256===undefined||hash(c.template_sha256),message);
      if(c.source_assignment!==undefined){
        const a=c.source_assignment;need(q.source_asset_id&&assignmentMatches(a,{asset_id:q.source_asset_id,sha256:q.source_sha256,role:q.source_role},1,board),message);
      }
      if(q.sources!==undefined){
        need(c.source_assignment===undefined&&Array.isArray(c.source_assignments)&&c.source_assignments.length===q.sources.length&&c.source_assignments.every((a,i)=>assignmentMatches(a,q.sources[i],i+1,board)),message);
      }else need(c.source_assignments===undefined,message);
      need(Array.isArray(c.checks)&&c.checks.length<=32&&c.checks.every(x=>plain(x)&&text(x.code,96)&&['observed','unknown','blocked'].includes(x.state)&&text(x.message,800)),message);
      need(Array.isArray(c.requirements)&&c.requirements.length<=128&&c.requirements.every(x=>plain(x)&&Object.values(x).every(v=>v===null||typeof v==='boolean'||text(v,500))),message);
    }
    need(r.diagnostics.every(x=>plain(x)&&text(x.preset_id,96)&&text(x.message,800)),message);
    return r;
  }
  class Session{
    constructor(transport,emit,timers={set:fn=>setTimeout(fn,15000),clear:id=>clearTimeout(id)}){this.transport=transport;this.emit=emit;this.timers=timers;this.epoch=0;this.current=null;this.busy=false;}
    invalidate(message='Choices changed. Check again to see current suggestions.'){
      this.epoch++;const active=this.current;this.current=null;this.busy=false;
      if(active){this.timers.clear(active.timer);active.controller.abort();}
      this.emit({busy:false,message});
    }
    async load(query){
      if(this.busy)return;const q={...query,...(Array.isArray(query.sources)?{sources:query.sources.map(x=>({...x}))}:{})},epoch=++this.epoch,controller=new AbortController();
      const active={controller,timer:null};this.current=active;this.busy=true;this.emit({busy:true,message:'Checking starting recipes…'});
      active.timer=this.timers.set(()=>{if(this.current===active)this.invalidate('The check timed out. No result was accepted. Check again explicitly.');});
      try{
        const response=await this.transport(q,controller.signal);if(epoch!==this.epoch||this.current!==active)return;
        const report=validate(response,q);this.busy=false;this.emit({busy:false,report});
      }catch(error){if(epoch===this.epoch&&this.current===active){this.busy=false;this.emit({busy:false,message:String(error?.message||error)});}}
      finally{this.timers.clear(active.timer);if(this.current===active){this.current=null;this.busy=false;}}
    }
  }
  function mount(w){
    const d=w.document,$=s=>d.querySelector(s);
    function el(tag,content,cls){const n=d.createElement(tag);if(content!==undefined)n.textContent=content;if(cls)n.className=cls;return n;}
    if(!$('#createView')){
      const host=$('#journeys');if(host&&!$('#recipeShortlistLink')){const p=el('p');p.id='recipeShortlistLink';const a=el('a','Find a starting recipe and see what it needs');a.href='/?recipe_goal=new-image#create';p.append(a);host.prepend(p);}return;
    }
    const list=$('#presetList');if(!list||$('#recipeShortlist'))return;
    const panel=el('details',undefined,'recipe-shortlist');panel.id='recipeShortlist';
    panel.append(el('summary','Help me choose a recipe'));
    const intro=el('p','Find a starting route for your goal. Your current setup stays unchanged.');panel.append(intro);
    const form=el('form'),goal=el('select'),count=el('select');goal.id='shortlistGoal';count.id='shortlistReferences';
    for(const [value,label] of Object.entries(goals)){const option=el('option',label);option.value=value;goal.append(option);}
    for(let i=0;i<=3;i++){const option=el('option',String(i));option.value=String(i);count.append(option);}
    const gl=el('label','What are you making?');gl.htmlFor=goal.id;
    const cl=el('label','Reference images I plan to attach');cl.htmlFor=count.id;
    const check=el('button','Check starting recipes');check.id='checkStartingRecipes';check.type='submit';
    const role=el('select');role.id='shortlistSourceRole';role.disabled=true;
    for(const [value,label] of Object.entries(sourceRoles)){const option=el('option',label);option.value=value;role.append(option);}
    const rl=el('label','Use the selected image for');rl.htmlFor=role.id;
    const sourceNote=el('p','To check a saved source, open an image in Asset library and choose Find recipes for this image.','muted');sourceNote.id='shortlistSourceStatus';
    const clear=el('button','Clear advice source');clear.type='button';clear.id='clearShortlistSource';clear.hidden=true;
    const sourceList=el('div');sourceList.id='shortlistSourceList';
    const choose=el('button','Choose images in library');choose.type='button';choose.id='shortlistChooseImages';choose.onclick=()=>{if(typeof showView==='function')showView('assets');};
    form.append(gl,goal,cl,count,sourceNote,choose,rl,role,sourceList,clear,check);panel.append(form);
    const note=el('p','Selected advice images are byte-checked only on request. A count alone is a declaration, not an upload. Checking never changes settings or starts generation.');note.className='muted';panel.append(note);
    const status=el('p','Choose an outcome, then check.','shortlist-status');status.id='shortlistStatus';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const result=el('div');result.id='shortlistResults';panel.append(status,result);list.before(panel);
    let last=null,source=null,ordered=null;
    const session=new Session(async(q,signal)=>{
      const response=await w.fetch('/api/workflow-studio/shortlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q),signal});
      const raw=await response.text();need(raw.length<=1024*1024,'Shortlist response exceeds the browser limit.');
      let value;try{value=JSON.parse(raw);}catch(_){throw Error('The shortlist response was unreadable. Check again.');}
      need(response.ok,typeof value?.error==='string'?value.error:'Recipe inspection is unavailable.');return value;
    },event=>{
      check.disabled=event.busy;panel.setAttribute('aria-busy',String(event.busy));last=null;result.replaceChildren();
      if(event.report){last=event.report;render(last);}else{status.textContent=event.message;d.dispatchEvent(new Event('studio:shortlist-invalidated'));}
    });
    function currentQuery(offset=0,expected){const q={goal:goal.value,reference_count:Number(count.value),limit:6,offset};if(expected)q.expected_snapshot=expected;if(ordered)q.sources=ordered.map(x=>({asset_id:x.asset_id,sha256:x.sha256,role:x.role}));if(source)Object.assign(q,{source_asset_id:source.asset_id,source_sha256:source.sha256,source_role:role.value});return q;}
    clear.onclick=()=>{source=null;ordered=null;sourceList.replaceChildren();count.disabled=false;rl.hidden=false;role.hidden=false;role.disabled=true;clear.hidden=true;sourceNote.textContent='No advice source selected. The reference count is only a declaration.';session.invalidate('Advice source cleared. Your Create attachments are unchanged.');};
    d.addEventListener('studio:shortlist-source',e=>{
      const x=e.detail;if(!plain(x)||!text(x.asset_id,96)||! /^[A-Za-z0-9_.-]+$/.test(x.asset_id)||!hash(x.sha256))return;
      session.invalidate('Source selected for advice. Check explicitly; nothing was attached or applied.');
      ordered=null;sourceList.replaceChildren();count.disabled=false;rl.hidden=false;role.hidden=false;
      source={asset_id:x.asset_id,sha256:x.sha256};goal.value='edit-image';count.value='1';role.value='source';role.disabled=false;clear.hidden=false;
      sourceNote.textContent='Advice source: '+(text(x.title,160)?x.title:x.asset_id)+'. Bytes will be checked when requested; this does not attach the image.';
      panel.open=true;const drawer=panel.closest('.ux-recipe-drawer');if(drawer)drawer.open=true;check.focus();panel.scrollIntoView({block:'nearest',behavior:'auto'});
    });
    function renderSources(focusSlot){
      sourceList.replaceChildren();count.value=String(ordered.length);count.disabled=true;
      role.disabled=true;role.hidden=true;rl.hidden=true;clear.hidden=false;
      sourceNote.textContent=ordered.length+' advice image(s), in Picture order. Every selected file will be checked. Nothing is attached or applied.';
      ordered.forEach((item,index)=>{
        const box=el('fieldset',undefined,'shortlist-source-row');box.dataset.slot=String(index+1);
        box.append(el('legend','Picture '+(index+1)+' · '+item.title));
        const label=el('label','Intended role'),choice=el('select');choice.id='shortlistRole'+(index+1);label.htmlFor=choice.id;
        for(const [value,name] of Object.entries(sourceRoles)){const option=el('option',name);option.value=value;choice.append(option);}choice.value=item.role;
        choice.onchange=()=>{item.role=choice.value;session.invalidate('Picture roles changed. Check again; nothing was applied.');};
        box.append(label,choice);const buttons=el('div',undefined,'shortlist-pages');
        for(const [delta,title] of [[-1,'Move earlier'],[1,'Move later']]){
          const button=el('button',delta<0?'↑':'↓');button.type='button';button.dataset.move=String(delta);button.title=title;
          button.setAttribute('aria-label',title+': Picture '+(index+1));button.disabled=index+delta<0||index+delta>=ordered.length;
          button.onclick=()=>{[ordered[index],ordered[index+delta]]=[ordered[index+delta],ordered[index]];session.invalidate('Picture order changed. Review each role and check again.');renderSources(index+delta+1);};buttons.append(button);
        }
        const remove=el('button','Remove');remove.type='button';remove.dataset.remove=String(index+1);remove.setAttribute('aria-label','Remove Picture '+(index+1)+' from advice');
        remove.onclick=()=>{ordered.splice(index,1);session.invalidate('Advice image removed. Create attachments are unchanged.');if(ordered.length)renderSources(Math.min(index+1,ordered.length));else{clear.onclick();count.value='0';check.focus();}};
        buttons.append(remove);box.append(buttons);sourceList.append(box);
      });
      if(focusSlot)$('#shortlistRole'+focusSlot)?.focus();
    }
    d.addEventListener('studio:shortlist-sources',e=>{
      const items=e.detail;
      if(!Array.isArray(items)||items.length<1||items.length>3||!items.every(x=>plain(x)&&text(x.asset_id,96)&&/^[A-Za-z0-9_.-]+$/.test(x.asset_id)&&hash(x.sha256)&&(x.role===undefined||Object.hasOwn(sourceRoles,x.role)))){session.invalidate('Choose one to three available library images. No existing advice sources were replaced.');return;}
      session.invalidate('Images selected for advice. Review their order and roles, then check explicitly.');source=null;
      ordered=items.map(x=>({asset_id:x.asset_id,sha256:x.sha256,title:text(x.title,160)?x.title:x.asset_id,role:Object.hasOwn(sourceRoles,x.role)?x.role:'source'}));
      goal.value='reference-image';renderSources();panel.open=true;const drawer=panel.closest('.ux-recipe-drawer');if(drawer)drawer.open=true;
      check.focus();panel.scrollIntoView({block:'nearest',behavior:'auto'});
    });
    function findPreset(row){
      try{
        need(last&&(!last.backend_id||typeof backendActive==='undefined'||backendActive===null||last.backend_id===backendActive)&&!(typeof backendSwitching!=='undefined'&&backendSwitching),'The environment changed. Check starting recipes again.');
        const entry=typeof catalog!=='undefined'&&catalog?.presets?.find(p=>p.id===row.preset_id);
        need(entry&&entry.continuation_capability?.template_sha256===row.template_sha256&&hash(row.template_sha256),'The recipe library and this report differ. Refresh the Studio catalog before checking again.');
        need(typeof renderPresets==='function'&&$('#presetSearch')&&$('#categorySelect'),'The recipe library is not available yet.');
        // Only picker filters change. Never call selectPreset/applyRecipe or touch editor inputs.
        mode='all';$('#presetSearch').value='';$('#categorySelect').value='All';
        const intent=$('#uxIntent');if(intent){intent.value='all';intent.onchange?.();}
        d.querySelectorAll('#modalities [data-mode]').forEach(n=>n.classList.toggle('active',n.dataset.mode==='all'));
        renderPresets();const button=Array.from(list.querySelectorAll('button[data-id]')).find(n=>n.dataset.id===row.preset_id);
        need(button&&!button.hidden,'This recipe is no longer in the visible library. Refresh before choosing.');
        button.focus();button.scrollIntoView({block:'nearest',behavior:'auto'});
        status.textContent='Recipe located in the library. Review it and use its existing button to select it; your current setup is unchanged.';
      }catch(error){status.textContent=error.message;}
    }
    function render(report){
      status.textContent=report.total+' matching route(s). '+report.counts.observed+' observed · '+report.counts.unknown+' unknown · '+report.counts.needs_setup+' need setup.';
      result.append(el('p','Default graphs · '+new Date(report.checked_at*1000).toLocaleTimeString()+'. This is not permission to run.','muted'));
      const scope=el('details');scope.append(el('summary','What this check covers'),el('p',report.scope));
      if(report.source_semantics)scope.append(el('p',report.source_semantics));result.append(scope);
      if(report.source){const x=report.source;result.append(el('p','Source checked: '+x.title+' · '+x.width+' × '+x.height+' · '+sourceRoles[x.role]+'. Not attached.','shortlist-source'));}
      for(const x of report.sources||[])result.append(el('p','Picture '+x.slot+' checked: '+x.title+' · '+x.width+' × '+x.height+' · '+sourceRoles[x.role]+'. Not attached.','shortlist-source'));
      if(!report.total)result.append(el('p','No registered default route matches this outcome. Try another outcome or inspect the existing workflow builder; no substitute was selected.'));
      for(const row of report.candidates){
        const card=el('article',undefined,'shortlist-card');card.dataset.presetId=row.preset_id;card.dataset.state=row.status;
        card.append(el('h4',row.name),el('p',statuses[row.status],'shortlist-verdict'));
        const attention=row.checks.find(c=>c.state==='blocked')||row.checks.find(c=>c.state==='unknown');
        card.append(el('p',attention?.message||'Listed prerequisites were observed. Select this recipe, review the settings and use the normal preparation checks.'));
        const find=el('button','Find in recipe library');find.type='button';find.onclick=()=>findPreset(row);card.append(find);
        const wanted=ordered?ordered.map(({asset_id,sha256,role})=>({asset_id,sha256,role})):(source?[{asset_id:source.asset_id,sha256:source.sha256,role:role.value}]:null);
        const board=row.reference_board,boardReady=board&&wanted&&wanted.length>=board.minimum&&wanted.length<=board.slot_count
          &&Array.isArray(row.source_assignments)&&row.source_assignments.every(a=>a.role_mode==='style-board');
        if(wanted&&(boardReady||!board&&wanted.length===row.reference_count)){const preview=el('button','Preview proposed setup');preview.type='button';preview.dataset.setupProposal=row.preset_id;
          preview.onclick=()=>{if(!last)return;d.dispatchEvent(new CustomEvent('studio:setup-proposal',{detail:{goal:last.goal,preset_id:row.preset_id,expected_template_sha256:row.template_sha256,sources:wanted}}));};card.append(preview);}
        const routeSummary=board
          ?row.operation+' · style board '+board.minimum+'–'+board.slot_count+' picture(s) + separate pose/continuation source · '+row.backend_id
          :row.operation+' · '+row.reference_count+' reference image(s) · '+row.backend_id;
        const detail=el('details');detail.append(el('summary','How it works and what it needs'),el('p',row.description),el('p',routeSummary,'muted'));
        if(row.source_assignment){const a=row.source_assignment;detail.append(el('p','Selected source → '+(a.binding?'node '+a.binding[0]+'.'+a.binding[1]:'no supported binding')+' · '+sourceRoles[a.role]+' · '+a.role_mode+'. Advice only; assign and review inputs in Create.'));}
        for(const a of row.source_assignments||[])detail.append(el('p','Picture '+a.slot+' → '+(a.binding?'node '+a.binding[0]+'.'+a.binding[1]:'no supported binding')+' · '+sourceRoles[a.role]+' · '+a.role_mode+'. Advice only; nothing was applied.'));
        const wording={description:'Describe the result you want to see.',instruction:'Describe the change to make and what must stay the same.',motion:'Describe the motion you want, not just the still image.',none:'This route has no authored text-prompt control.'};
        detail.append(el('p',wording[row.prompt_role]||'Inspect the recipe for its wording controls.'));
        const checks=el('ul');for(const c of row.checks)checks.append(el('li',c.message));detail.append(checks);
        if(row.requirements.length){
          const locations=el('details');locations.append(el('summary','Required model locations ('+row.requirements.length+')'));
          for(const r of row.requirements){const p=el('p');p.append(el('strong',r.file||'Unresolved model'),el('br'),el('span',r.path||'Location unknown'),el('br'),el('span',(r.present===true?'Observed':r.present===false?'Missing or unusable':'Unknown')+(r.note?' — '+r.note:'')));locations.append(p);}detail.append(locations);
        }
        card.append(detail);result.append(card);
      }
      if(report.diagnostics.length){const details=el('details');details.append(el('summary','Routes with unavailable operation evidence ('+report.diagnostics.length+')'));for(const x of report.diagnostics)details.append(el('p',x.preset_id+': '+x.message));result.append(details);}
      const pages=el('div',undefined,'shortlist-pages');
      if(report.offset){const first=el('button','Check first page');first.type='button';first.onclick=()=>session.load(currentQuery());pages.append(first);}
      if(report.next_offset!==null){const next=el('button','Next suggestions');next.type='button';next.onclick=()=>session.load(currentQuery(report.next_offset,report.snapshot_sha256));pages.append(next);}
      result.append(pages);
    }
    form.onsubmit=e=>{e.preventDefault();session.load(currentQuery());};
    form.onchange=()=>session.invalidate();
    panel.addEventListener('toggle',()=>{if(!panel.open&&session.busy)session.invalidate('Check paused. Open this section and check again.');});
    w.addEventListener('pagehide',()=>session.invalidate('Check again after returning to this page.'));
    // #197 supplies recipe events. On older shells input edits still invalidate safely.
    const changed=e=>{if(!panel.contains(e.target))session.invalidate('Studio inputs changed. Check starting recipes again when needed.');};
    $('#createView').addEventListener('input',changed);$('#createView').addEventListener('change',changed);
    d.addEventListener('studio:recipe',()=>session.invalidate('Recipe changed. This report does not cover your current settings.'));
    w.addEventListener('hashchange',()=>{if(w.location.hash!=='#create')session.invalidate('Return to Create and check again when needed.');});
    d.addEventListener('change',e=>{if(e.target.id==='backendChoice')session.invalidate('Environment choice changed. Check after any explicit switch.');});
    d.addEventListener('click',e=>{if(e.target.closest?.('#switchBackend'))session.invalidate('Environment change requested. Check after it finishes.');});
    const initial=new URLSearchParams(w.location.search).get('recipe_goal');if(Object.hasOwn(goals,initial)){goal.value=initial;panel.open=true;const drawer=panel.closest('.ux-recipe-drawer');if(drawer)drawer.open=true;}
    return {session,panel};
  }
  return {validate,Session,mount,goals};
});