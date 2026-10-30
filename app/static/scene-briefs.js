/* Real Workspace cards and paged candidates. No execution endpoint is called. */
(function(){
  'use strict';
  const C=StudioBriefCore,root=document.querySelector('#briefsView');if(!root)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const q=s=>root.querySelector(s),same=(a,b)=>C.content(a)===C.content(b);
  let scope=null,briefs=[],card=null,saved=null,base=null,states={},collectionAvailable=true,collections=[],collectionCursor=null,looks=[];
  let busy=false,epoch=0,notice='',blockedRaw=null,recoveryFailed=false,conflict=false,picker=null,pickerError='',loadedRoute='',lastRoute=null;
  const memories=new Map();
  const allowed=()=>!window.StudioPrivacy||(StudioPrivacy.scope()==='regular'&&StudioPrivacy.creation()==='regular');
  const dirty=()=>!!card&&(!saved||!same(card,saved));
  const route=()=>C.route(location.hash);
  function message(text){notice=text;const el=q('#briefStatus');if(el)el.textContent=text;}
  async function api(path,body){if(!allowed())throw Error('Scene briefs require Regular view and creation.');const options=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};const response=await (window.StudioPrivacy?StudioPrivacy.fetch(path,options):fetch(path,options));let data;try{data=await response.json();}catch(_){throw Error('Studio returned an unreadable response. Your draft is retained; reload the saved record before retrying.');}if(!response.ok)throw Object.assign(Error(data.error||'Request failed'),{status:response.status,code:data.code});return data;}
  function remember(){if(!card||blockedRaw!==null)return;const raw=JSON.stringify(C.envelope(card,base));memories.set(card.id,raw);try{sessionStorage.setItem(C.storageKey(scope,card.id),raw);recoveryFailed=false;}catch(_){recoveryFailed=true;message('Browser recovery could not be stored. Keep this tab open, save to Workspace or download your draft.');}}
  function recovery(identifier){let raw=memories.get(identifier);if(raw===undefined){try{raw=sessionStorage.getItem(C.storageKey(scope,identifier));}catch(_){recoveryFailed=true;return null;}}if(raw===undefined)raw=null;try{return C.recovery(raw,scope,identifier);}catch(error){blockedRaw=raw;notice=error.message;return null;}}
  function recoveredChoices(){
    if(!scope)return [];
    const records=new Map(memories),prefix=C.storageKey(scope,'');
    try{for(let i=0;i<sessionStorage.length;i++){const key=sessionStorage.key(i);if(key?.startsWith(prefix)){const id=key.slice(prefix.length);if(C.route('#briefs?id='+encodeURIComponent(id)).id===id&&!records.has(id))records.set(id,sessionStorage.getItem(key));}}}catch(_){recoveryFailed=true;}
    return [...records].filter(([id])=>!briefs.some(b=>b.id===id)&&id!==card?.id).map(([id,raw])=>{try{const draft=C.recovery(raw,scope,id);return {id,name:draft.card.name||'Unnamed draft'};}catch(_){return {id,name:'Unreadable recovery'};}});
  }
  function navigate(next){remember();location.hash=C.hash({...route(),...next});}
  function download(raw,name){const url=URL.createObjectURL(new Blob([raw],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function workingPack(){
    if(!saved||dirty())throw Error('Save the brief before downloading a working pack.');
    if(conflict)throw Error('Reload the saved brief before downloading a working pack.');
    const token=epoch,id=card.id,revision=base,workspace=scope;
    const current=()=>token===epoch&&allowed()&&route().view==='briefs'&&route().id===id&&card?.id===id&&base===revision&&scope===workspace&&!dirty();
    const pending='Preparing working pack…';message(pending);try{
    const result=await api('/api/briefs/export',{id,expected_revision:revision,workspace_id:workspace});
    if(!current())return;
    const response=await (window.StudioPrivacy?StudioPrivacy.fetch(result.url):fetch(result.url));
    if(!response.ok)throw Error('The working pack is unavailable. Reload the saved brief and try again.');
    const blob=await response.blob();if(!current())return;
    // Recheck the live Workspace after the binary transfer, before browser download.
    const latest=await api('/api/briefs/'+encodeURIComponent(id));if(!current())return;
    if(latest.card.body.workspace_id!==workspace||latest.card.revision!==revision)throw Error('The brief or Workspace changed. Reload the saved brief and try again.');
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=result.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    message('Working pack downloaded.');
    }finally{if(notice===pending)message('');}// a discarded or failed transfer must not leave the progress text; act() writes any error after this
  }
  async function loadCollections(cursor=null){const p=new URLSearchParams({workspace_id:scope,limit:'30'});if(cursor)p.set('cursor',cursor);const data=await api('/api/collections?'+p);return data;}
  async function loadCard(identifier,token){
    blockedRaw=null;conflict=false;const recovered=recovery(identifier);let result=null;
    try{result=await api('/api/briefs/'+encodeURIComponent(identifier));}catch(error){if(error.status!==404||!recovered||recovered.base_revision!==null)throw error;}
    if(token!==epoch||!allowed())return;
    saved=result?.card||null;states=result?.candidates||{};collectionAvailable=result?.collection_available??true;
    if(saved&&(!C.validBody(saved.body)||saved.body.workspace_id!==scope))throw Error('The saved brief belongs to another Workspace or version.');
    card=recovered?recovered.card:C.copy(saved);base=recovered?recovered.base_revision:saved.revision;
    if(saved&&same(card,saved)){card=C.copy(saved);base=saved.revision;}
    conflict=!!saved&&base!==saved.revision;
    if(!card)throw Error('Brief unavailable.');
    remember();
  }
  async function loadPicker(token){
    const r=route();picker=null;pickerError='';if(!r.picker||!card)return;
    const p=new URLSearchParams({workspace_id:scope,limit:'12',media_type:C.SLOTS[r.slot][1]});if(card.body.collection_id)p.set('collection_id',card.body.collection_id);if(r.q)p.set('q',r.q);if(r.cursor)p.set('cursor',r.cursor);
    try{const data=await api('/api/assets/page?'+p);if(token===epoch&&allowed())picker=data;}catch(error){if(token===epoch)pickerError=error.message;}
  }
  async function refresh(){
    const token=++epoch,r=route();if(r.view!=='briefs')return;
    if(!allowed()){root.innerHTML='<div class="view-heading"><div><h1>Scene briefs</h1><p>Briefs use Regular Workspace storage. Private and All views are unavailable here. Switch to Regular view and creation to continue.</p></div></div>';return;}
    if(busy)return;
    try{
      if(!scope){root.innerHTML='<p role="status">Loading scene briefs…</p>';const data=await api('/api/briefs');if(token!==epoch||!allowed())return;scope=data.workspace_id;briefs=data.briefs;const [collectionResult,lookResult]=await Promise.all([loadCollections(),api('/api/looks').catch(()=>({looks:[]}))]);if(token!==epoch||!allowed())return;collections=collectionResult.collections;collectionCursor=collectionResult.next_cursor;looks=(lookResult.looks||[]).filter(l=>!l.trashed_at&&l.usable!==false);}
      if(r.id&&card?.id!==r.id){remember();card=null;notice='';root.innerHTML='<p role="status">Loading this brief…</p>';await loadCard(r.id,token);}
      if(!r.id){remember();card=null;saved=null;}
      if(token!==epoch||!allowed())return;
      if(card&&r.returned!==null&&r.returned!==base)notice='This brief changed since preparation. Review its saved revision before choosing a return candidate.';
      if(loadedRoute!==location.hash){const loading=location.hash;await loadPicker(token);if(token===epoch)loadedRoute=loading;}// an invalidated request leaves the route unloaded so the next refresh reloads it
      if(token!==epoch||!allowed())return;
      const slotChanged=lastRoute&&lastRoute.slot!==r.slot;render();lastRoute=r;if(slotChanged)q('#briefSlotTitle')?.focus({preventScroll:true});
    }catch(error){if(token!==epoch||!allowed())return;notice=error.message;render();}
  }
  function editor(){
    const r=route(),slot=card.body.slots[r.slot],candidate=states[r.slot],unchanged=JSON.stringify(saved?.body.slots[r.slot].selected)===JSON.stringify(slot.selected);
    const picked=Object.values(card.body.slots).filter(s=>s.selected).length;
    const unavailable=slot.selected&&unchanged&&candidate?.state==='unavailable';
    const selectedText=!slot.selected?'No candidate selected':unavailable?'Saved candidate unavailable':unchanged&&candidate?.title?candidate.title:'Candidate '+slot.selected.asset_id;
    return `<div class="brief-layout"><nav class="brief-slots" aria-label="Asset slots"><p>${picked} of 6 slots have candidates</p>${Object.entries(C.SLOTS).map(([key,[label]])=>`<a href="${esc(C.hash({...r,slot:key,picker:false,cursor:'',q:'',returned:null}))}" ${r.slot===key?'aria-current="step"':''}><span>${esc(label)}</span><small>${card.body.slots[key].selected?'Candidate selected':'Open slot'}</small></a>`).join('')}<p class="muted">Selection records intent. Art, licence and export checks remain yours.</p></nav><div class="brief-editor"><fieldset ${busy||blockedRaw!==null?'disabled':''}><div class="brief-shared"><label>Brief name<input id="briefName" maxlength="120" value="${esc(card.name)}"></label><label>Shared direction<textarea id="briefDirection" rows="3" maxlength="4000" placeholder="The place, mood and visual language these assets should share">${esc(card.body.direction)}</textarea></label><div class="brief-collection"><label>Source collection<select id="briefCollection"><option value="">All Regular assets</option>${card.body.collection_id&&!collections.some(c=>c.id===card.body.collection_id)?`<option value="${esc(card.body.collection_id)}" selected>Saved collection · ${esc(card.body.collection_id)}</option>`:''}${collections.map(c=>`<option value="${esc(c.id)}" ${c.id===card.body.collection_id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label>${collectionCursor?'<button type="button" data-action="collections">More collections</button>':''}<button type="button" data-action="refreshCollections">Refresh collections</button></div>${!collectionAvailable?'<p class="brief-warning">The saved collection is unavailable. Choose a current collection or All Regular assets.</p>':''}</div><div class="brief-slot-editor"><span class="eyebrow">ASSET SLOT</span><h2 id="briefSlotTitle" tabindex="-1">${C.SLOTS[r.slot][0]}</h2><label>What this asset should do<textarea id="briefIntent" rows="3" maxlength="2000" placeholder="Describe this asset’s role in the scene">${esc(slot.intent)}</textarea></label><label>Acceptance notes<textarea id="briefCriteria" rows="2" maxlength="2000" placeholder="What you will check: dimensions, timing, readability, topology…">${esc(slot.criteria)}</textarea></label><section class="brief-candidate" aria-label="Current candidate"><h3>${esc(selectedText)}</h3>${slot.selected?`<details><summary>Saved candidate identity</summary><p>${esc(slot.selected.asset_id)} · metadata revision ${slot.selected.metadata_revision}</p><code>${esc(slot.selected.sha256)}</code></details>`:'<p>Choose an existing Workspace asset, or prepare a supported next step.</p>'}${unavailable?'<p class="brief-warning">Its immutable snapshot is retained. Choose the current record again or replace it.</p>':''}<div class="brief-actions"><button type="button" data-action="picker">${slot.selected?'Replace candidate':'Choose candidate'}</button>${slot.selected?'<button type="button" data-action="clear">Clear slot</button>':''}${slot.previous?'<button type="button" data-action="restore">Restore previous candidate</button>':''}</div></section><section class="brief-prepare" aria-label="Prepare next step">${preparation(r.slot)}<p class="muted">Preparation starts no generation or rendering. Save changes before preparing.</p></section></div></fieldset>${r.picker?pickerMarkup(r):''}</div></div>`;
  }
  function preparation(slot){
    if(['background','icon'].includes(slot))return `<label>Look for this ${slot==='icon'?'icon':'background'}<select id="briefLook"><option value="">Choose a look…</option>${looks.map(l=>`<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('')}</select></label><button type="button" data-action="prepare" ${dirty()||conflict?'disabled':''}>Prepare in Full editor</button><small>Shared direction and both slot fields must total at most 1,000 characters for a look.</small>`;
    if(slot==='video')return `<p>Prepare a scene from the selected background, video and audio. Scenes accepts PNG, MP4 and 48 kHz PCM WAV.</p><button type="button" data-action="prepare" ${dirty()||conflict?'disabled':''}>Prepare in Scene editor</button>`;
    return '<p>'+({sprite:'Directional sprite-sheet preparation is unavailable. An image candidate can still be selected.',audio:'Ambience generation is unavailable here. Voice takes needs its own speaker, lines and pinned bundle.',mesh:'3D preparation needs a suitable reference and supported recipe. Choose an existing 3D asset, or continue in Full editor.'}[slot])+'</p>';
  }
  function pickerMarkup(r){return `<section class="brief-picker" aria-labelledby="briefPickerTitle"><div class="brief-actions"><h3 id="briefPickerTitle">Choose ${C.SLOTS[r.slot][0].toLowerCase()} candidate</h3><button type="button" data-action="closePicker">Close picker</button></div>${r.returned!==null?'<p>Returning from preparation: choose a real asset for this slot, then save the brief. This does not certify how the asset was made.</p>':''}<form id="briefSearch"><label>Search candidates<input name="q" type="search" maxlength="200" value="${esc(r.q)}"></label><button>Search</button><button type="button" data-action="refreshPicker">Refresh from first page</button></form>${pickerError?`<p class="brief-warning" role="alert">${esc(pickerError)}. Refresh from first page; the current selection is retained.</p>`:''}<div class="brief-grid">${(picker?.assets||[]).map(a=>`<article>${a.media_type==='image'?`<img src="/api/assets/${encodeURIComponent(a.id)}/thumb?w=256" alt="" loading="lazy">`:`<div class="brief-media-kind">${esc(a.media_type)}</div>`}<h4>${esc(a.title||a.filename)}</h4><small>${esc(a.filename)} · revision ${a.metadata_revision}</small><button type="button" data-candidate="${esc(a.id)}" ${busy||blockedRaw!==null||r.returned!==null&&(r.returned!==base||dirty()||conflict)?'disabled':''}>Use in this slot</button></article>`).join('')}</div>${picker&&!picker.assets.length&&!pickerError?'<p>No active candidates match. Change the search or collection, or import an asset in Library.</p>':''}<div class="brief-actions"><button type="button" data-action="first" ${!r.cursor?'disabled':''}>First page</button><button type="button" data-action="next" ${!picker?.next_cursor?'disabled':''}>Next page</button><small>Up to 12 candidates per page · browser Back returns to the previous page</small></div></section>`;}
  function render(){
    if(!allowed())return;
    root.innerHTML=`<div class="view-heading"><div><span class="eyebrow">ONE SCENE · SIX ASSET TYPES</span><h1>Scene briefs</h1><p>Keep the direction, candidates and next step together. Browser drafts recover in this tab; Save brief keeps them in Workspace.</p></div><button type="button" data-action="new" ${busy?'disabled':''}>New brief</button></div><div class="brief-toolbar"><label>Open brief<select id="briefSelect" ${busy?'disabled':''}><option value="">Choose a brief…</option>${briefs.map(b=>`<option value="${esc(b.id)}" ${b.id===card?.id?'selected':''}>${esc(b.name)}${b.available?'':' · unreadable'}</option>`).join('')}${recoveredChoices().map(d=>`<option value="${esc(d.id)}">${esc(d.name)} · browser draft</option>`).join('')}${card&&!briefs.some(b=>b.id===card.id)?`<option value="${esc(card.id)}" selected>${esc(card.name)} · new</option>`:''}</select></label>${card?`<button type="button" data-action="save" class="primary" ${busy||blockedRaw!==null||conflict?'disabled':''}>Save brief</button><button type="button" data-action="reload" ${busy?'disabled':''}>Reload saved brief</button><button type="button" data-action="download">Download draft</button><button type="button" data-action="workingPack" ${busy||blockedRaw!==null?'disabled':''}>Download working pack</button><span id="briefSaveState">${dirty()?'Unsaved changes':'Saved · revision '+base}</span>`:''}</div><p id="briefStatus" role="status" aria-live="polite">${esc(notice)}</p>${conflict?'<div class="brief-warning" role="alert">A newer saved revision exists. Your draft is retained. Download it before reloading the saved brief; no automatic overwrite is available.</div>':''}${blockedRaw!==null?'<div class="brief-warning" role="alert">Unrecognized recovery data is preserved. <button data-action="downloadRecovery">Download original recovery</button> <button data-action="discardRecovery">Discard this recovery copy</button></div>':''}${recoveryFailed?'<p class="brief-warning">Browser recovery is unavailable. Keep this tab open until you save or download your draft.</p>':''}${card?editor():'<div class="brief-empty"><h2>A shared direction, six open slots</h2><p>Start a brief for a scene or collection. Add background, sprite, icon, video, audio and 3D candidates as they become available.</p></div>'}`;
  }
  async function act(work){if(busy)return;busy=true;const token=epoch;render();try{await work();}catch(error){if(token===epoch&&allowed()){if(error.status===409&&error.code==='card_revision_conflict')conflict=true;notice=error.message+' Your draft is retained.';}}finally{busy=false;if(allowed()&&route().view==='briefs'){if(route().id!==card?.id)refresh();else render();}}}
  async function save(){
    if(!card.name.trim())throw Error('Give the brief a name.');
    const before=C.copy(card),id=card.id,payload=base===null?{action:'create',kind:'brief',id,name:card.name,body:card.body}:{action:'edit',id,expected_revision:base,name:card.name,body:card.body};
    const result=await api('/api/briefs',payload);
    // Navigation/privacy changes cannot redirect this acknowledgment into a new draft.
    memories.set(id,JSON.stringify(C.envelope(result,result.revision)));try{sessionStorage.setItem(C.storageKey(result.body.workspace_id,id),memories.get(id));}catch(_){recoveryFailed=true;}
    if(card?.id!==id||!same(card,before))return;
    card=C.copy(result);saved=C.copy(result);base=result.revision;conflict=false;notice='Saved to Workspace. Candidate selection is separate from acceptance.';
    briefs=briefs.filter(b=>b.id!==id);briefs.unshift({id,name:result.name,available:true});const inspected=await api('/api/briefs/'+id);if(card?.id===id){states=inspected.candidates;collectionAvailable=inspected.collection_available;}remember();
  }
  root.addEventListener('input',event=>{if(!card||busy||blockedRaw!==null)return;const r=route(),value=event.target.value;switch(event.target.id){case 'briefName':card.name=value;break;case 'briefDirection':card.body.direction=value;break;case 'briefIntent':card.body.slots[r.slot].intent=value;break;case 'briefCriteria':card.body.slots[r.slot].criteria=value;break;default:return;}remember();const state=q('#briefSaveState');if(state)state.textContent='Unsaved changes';q('[data-action="prepare"]')?.setAttribute('disabled','');});
  root.addEventListener('change',event=>{if(event.target.id==='briefSelect'){navigate({id:event.target.value||null,picker:false,cursor:'',returned:null});return;}if(event.target.id==='briefCollection'&&card&&!busy){card.body.collection_id=event.target.value||null;collectionAvailable=true;for(const s of Object.values(card.body.slots)){s.previous=s.selected;s.selected=null;}notice='Collection changed. Current candidates moved to each slot’s previous candidate; they must be checked before restoring.';remember();loadedRoute='';navigate({cursor:'',returned:null});refresh();}});
  root.addEventListener('submit',event=>{if(event.target.id!=='briefSearch')return;event.preventDefault();navigate({q:new FormData(event.target).get('q').trim(),cursor:''});});
  root.addEventListener('click',event=>{const button=event.target.closest('[data-action],[data-candidate]');if(!button||button.disabled||busy)return;const action=button.dataset.action,r=route();
    if(button.dataset.candidate){const asset=picker?.assets.find(a=>a.id===button.dataset.candidate);if(!asset)return;try{card=C.choose(card,r.slot,asset);states[r.slot]={state:'selected',title:asset.title||asset.filename};notice='Candidate selected in your draft. Save the brief to keep it.';remember();navigate({picker:false,cursor:'',returned:null});}catch(error){message(error.message);}return;}
    if(action==='new'){remember();card=C.newCard(scope,crypto.randomUUID());saved=null;base=null;blockedRaw=null;conflict=false;states={};notice='New brief. Write the shared direction, then fill the slots as you work.';remember();navigate({id:card.id,slot:'background',picker:false,q:'',cursor:'',returned:null});render();return;}
    if(action==='download'){download(JSON.stringify(C.envelope(card,base),null,2),'scene-brief-draft.json');return;}
    if(action==='downloadRecovery'){download(blockedRaw,'scene-brief-recovery-original.json');return;}
    if(action==='discardRecovery'){if(!confirm('Discard only this unrecognized browser recovery copy? The saved Workspace brief stays unchanged.'))return;try{sessionStorage.removeItem(C.storageKey(scope,card?.id||r.id));}catch(error){message('Recovery storage is unavailable; the original was retained.');return;}memories.delete(card?.id||r.id);blockedRaw=null;card=null;refresh();return;}
    if(action==='picker'){navigate({picker:true,cursor:'',q:''});return;}if(action==='closePicker'){navigate({picker:false,cursor:'',returned:null});return;}
    if(action==='first'||action==='refreshPicker'){loadedRoute='';navigate({cursor:''});refresh();return;}if(action==='next'){navigate({cursor:picker.next_cursor});return;}
    if(action==='clear'){const s=card.body.slots[r.slot];s.previous=s.selected;s.selected=null;remember();render();return;}
    const chosenLook=looks.find(l=>l.id===q('#briefLook')?.value);
    act(async()=>{
      if(action==='save')await save();
      else if(action==='workingPack')await workingPack();
      else if(action==='reload'){if(dirty()&&!confirm('Replace this tab’s draft with the saved brief? Download your draft first if you need both.'))return;memories.delete(card.id);sessionStorage.removeItem(C.storageKey(scope,card.id));card=null;await loadCard(r.id,epoch);notice='Loaded the saved revision.';}
      else if(action==='restore'){const ref=card.body.slots[r.slot].previous;const data=await api('/api/assets/selection',{workspace_id:scope,ids:[ref.asset_id]});const item=data.items[0];const asset=item?.asset||item;if(!asset||asset.sha256!==ref.sha256||asset.metadata_revision!==ref.metadata_revision)throw Error('Previous candidate changed or is unavailable. Choose its current record in the picker.');card=C.choose(card,r.slot,asset);remember();notice='Previous candidate restored in the draft. Save to keep it.';}
      else if(action==='collections'||action==='refreshCollections'){const data=await loadCollections(action==='collections'?collectionCursor:null);collections=action==='collections'?[...collections,...data.collections]:data.collections;collectionCursor=data.next_cursor;}
      else if(action==='prepare'){
        const look=chosenLook;const result=await api('/api/briefs/prepare',{id:card.id,slot:r.slot,expected_revision:base,...(look?{look_id:look.id,look_revision:look.revision}:{})});
        if(!allowed()||route().id!==result.context.id||route().slot!==result.context.slot||dirty())return;
        if(!C.context(result.context))throw Error('Invalid preparation response.');
        // Persist the minimal return address before leaving. No prompt or private record is copied.
        sessionStorage.setItem('studio.brief-return.v1',JSON.stringify(result.context));
        if(result.target==='create'){if(!window.StudioLooks?.openPrepared)throw Error('Full editor is still loading.');if(!StudioLooks.openPrepared(result.prepared))return;document.dispatchEvent(new CustomEvent('studio:brief-return-change'));document.dispatchEvent(new CustomEvent('studio:navigate',{detail:'create'}));}
        else if(result.target==='scene'&&result.url.startsWith('/av.html?'))location.assign(result.url);
        else throw Error('Unsupported handoff destination.');
      }
    });
  });
  document.addEventListener('studio:privacy-change',()=>{remember();++epoch;loadedRoute='';if(route().view==='briefs')refresh();});
  window.addEventListener('beforeunload',event=>{if(dirty()){remember();event.preventDefault();event.returnValue='';}});
  window.StudioBriefs={refresh};if(route().view==='briefs')refresh();
})();
