'use strict';
const $=selector=>document.querySelector(selector),esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
let avProjects=[],avId=null,avDocument=null,avDrafts=new Map(),avSelection=null,avPolling=null,avPollBusy=false,avWorkspace=[],avDraftRevision=null,avMutationBusy=false;
const activeRenderStatuses=new Set(['queued','running','rendering']);
function avMessage(text,error=false){const el=$('#avStatus');el.textContent=text;el.classList.toggle('error',error);}
async function avApi(path,options={}){const response=await fetch(path,options);let data={};try{data=await response.json();}catch(_){throw Error('The Studio returned an unreadable response.');}if(!response.ok)throw Error(data.error||'Request failed');return data;}
async function avPost(path,body){return avApi(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
function sameOriginUrl(value){return typeof value==='string'&&value.startsWith('/')&&!value.startsWith('//')?value:'';}
function queryIds(){const raw=new URLSearchParams(location.search).get('asset_ids')||'';return new Set(raw.split(',').filter(Boolean));}
function requestedProject(){return new URLSearchParams(location.search).get('project');}
function seconds(value,rate,precision=2){if(!Number.isFinite(Number(value))||!rate)return '—';return (Number(value)/rate).toFixed(precision)+' s';}
function frameRate(doc){const fps=doc?.project?.fps||[24,1];return Number(fps[0])/Number(fps[1]||1);}
function sourceMap(){return new Map((avDocument?.sources||[]).map(source=>[source.key,source]));}
function draftFor(section,id){const key=section+':'+id;if(!avDrafts.has(key))avDrafts.set(key,{});return avDrafts.get(key);}
function draftValue(section,clip,field){const draft=avDrafts.get(section+':'+clip.id);return draft&&Object.hasOwn(draft,field)?draft[field]:clip[field];}
function setDraft(section,id,field,value){if(!avDrafts.size)avDraftRevision=avDocument.revision;draftFor(section,id)[field]=value;}
function clearDraft(section,id){avDrafts.delete(section+':'+id);if(!avDrafts.size)avDraftRevision=null;}
function hasDrafts(){return avDrafts.size>0;}
function clearDrafts(){avDrafts.clear();avDraftRevision=null;}
function draftActionDisabled(){return hasDrafts()?' disabled':'';}
function requireSavedDocument(action){if(!hasDrafts())return true;avMessage('Save or discard unsaved clip changes before '+action+'.',true);return false;}
function integer(raw,label){const n=Number(raw);if(!Number.isSafeInteger(n))throw Error(label+' must be a whole number.');return n;}
function number(raw,label){const n=Number(raw);if(!Number.isFinite(n))throw Error(label+' must be a number.');return n;}
function selected(section,id){return avSelection?.section===section&&avSelection?.id===id;}
function selectClip(section,id){avSelection={section,id};renderDocument();}
function sourceLabel(key){const source=sourceMap().get(key);return source?source.filename+' · '+source.kind:'Missing source '+key;}
function clipInput(section,clip,field,label,kind='integer',hint='',min=0,max=''){
  const value=draftValue(section,clip,field),checked=kind==='boolean'&&value;
  if(kind==='boolean')return '<label class="av-check"><input type="checkbox" data-field="'+field+'" data-section="'+section+'" data-clip="'+clip.id+'" '+(checked?'checked':'')+'> '+esc(label)+'</label>';
  const step=kind==='number'?'step="0.1"':'step="1"',maxAttr=max!==''?' max="'+max+'"':'';
  return '<label>'+esc(label)+'<input type="number" '+step+' min="'+min+'"'+maxAttr+' value="'+esc(value)+'" data-field="'+field+'" data-section="'+section+'" data-clip="'+clip.id+'">'+(hint?'<small class="av-control-hint">'+esc(hint)+'</small>':'')+'</label>';
}
function renderProjects(){
  $('#avProjectList').innerHTML=avProjects.map(project=>'<button class="av-project '+(project.id===avId?'chosen':'')+'" data-project="'+esc(project.id)+'"><b>'+esc(project.name)+'</b><small>Revision '+esc(project.revision)+' · '+esc(project.status||'saved')+'</small>'+(project.render_stale?'<small>Preview is stale</small>':'')+'</button>').join('')||'<p class="muted">No scenes yet. Select Workspace media and create one here.</p>';
}
function updatePolledStatus(document){const project=avProjects.find(item=>item.id===document.id);if(project){project.status=document.status;project.render_stale=!!document.render?.stale;renderProjects();}const status=$('#avDocumentStatus');if(status)status.textContent='Revision '+avDocument.revision+' · '+(avDocument.status||'saved');}
function capabilityText(capabilities){if(!capabilities)return '';
  const missing=capabilities.missing_tools||[];return capabilities.render_ready?'Rendering is ready locally.':missing.length?'Render unavailable: '+missing.join(', ')+'.':'Render readiness is unavailable.';
}
async function refreshProjects(preferred=null){
  const data=await avApi('/api/av');avProjects=data.projects||[];$('#avCapabilities').textContent=capabilityText(data.capabilities);
  if(preferred)avId=preferred;if(!avId&&avProjects.length)avId=avProjects[0].id;
  renderProjects();if(avId&&(!avDocument||avDocument.id!==avId))await loadScene(avId);
  else avMessage(avProjects.length?'Scene list refreshed.':'Create a scene from saved Workspace media.');
}
function stopPolling(){if(avPolling){clearInterval(avPolling);avPolling=null;}avPollBusy=false;}
function maintainPolling(){
  const active=activeRenderStatuses.has(avDocument?.render?.status);
  if(!active){stopPolling();return;}
  if(avPolling)return;
  avPolling=setInterval(async()=>{if(avPollBusy||!avId)return;avPollBusy=true;try{await loadScene(avId,true);}catch(error){avMessage(error.message,true);}finally{avPollBusy=false;}},1000);
}
async function loadScene(id=avId,poll=false){
  if(!id)return;const document=await avApi('/api/av/'+encodeURIComponent(id));
  if(id!==avId)return;
  if(poll){
    if(document.revision!==avDocument.revision)avMessage('A newer server revision is available. Reload to compare; unsaved fields are retained.');
    avDocument.render=document.render;avDocument.status=document.status;updatePolledStatus(document);
    const panel=$('.av-preview');
    if(panel){const video=panel.querySelector('video'),url=video?.getAttribute('src');panel.outerHTML=renderPreview(avDocument);const replacement=$('.av-preview video');if(video&&replacement&&replacement.getAttribute('src')===url)replacement.replaceWith(video);}
  }else{avDocument=document;if(avDrafts.size){avDraftRevision=document.revision;for(const draft of avDrafts.values())delete draft.conflict;}renderDocument();}
  maintainPolling();
  if(!poll)avMessage('Loaded revision '+document.revision+'.');
}
function renderPreview(doc){
  const render=doc.render,ready=doc.capabilities?.render_ready,active=activeRenderStatuses.has(render?.status),previewUrl=sameOriginUrl(render?.preview_url),stale=!!render?.stale;
  const status=render?render.status:'Not rendered';
  const preview=previewUrl?'<video controls preload="metadata" src="'+esc(previewUrl)+'" aria-label="Scene preview"></video>':'<p class="muted">No rendered preview yet.</p>';
  const label=previewUrl?(stale?'Preview from saved revision '+esc(render.preview_revision)+' · older than saved scene':'Preview from saved revision '+esc(render.preview_revision)):'No preview available';
  const artifacts=(render?.artifacts||[]).map(a=>'<a href="'+esc(sameOriginUrl(a.url))+'?download" download>'+esc(a.role||a.path)+'</a>').join('');
  return '<section class="panel av-preview"><div class="av-preview-media">'+preview+'</div><div class="av-preview-meta"><div><span class="eyebrow">RENDER</span><h3><span class="av-status-dot '+(active?'active':'')+'"></span> '+esc(status)+'</h3><p>'+esc(render?.message||'Rendering never starts automatically.')+'</p></div><p class="'+(stale?'av-warning':'muted')+'">'+label+'</p>'+(Number.isFinite(render?.progress)?'<p>Progress '+Math.round(render.progress)+'%</p>':'')+'<div class="av-document-actions">'+(active?'<button data-render-action="cancel">Cancel this render</button>':'<button class="primary" data-render-action="render" '+(!ready||hasDrafts()?'disabled':'')+'>Render scene</button>')+'<button data-render-action="export"'+draftActionDisabled()+'>Export companion ZIP</button></div><div class="av-render-artifacts">'+artifacts+'</div></div></section>';
}
function sectionSources(section){const sources=avDocument?.sources||[];return sources.filter(source=>section==='audio'?source.kind==='audio':section==='overlays'?source.kind==='image':['image','video'].includes(source.kind));}
function addControl(section){const sources=sectionSources(section);return '<div class="av-add"><select data-add-source="'+section+'" aria-label="Source for new '+section+'">'+sources.map(source=>'<option value="'+esc(source.key)+'">'+esc(source.filename)+' · '+esc(source.kind)+'</option>').join('')+'</select><button data-add="'+section+'" '+(!sources.length||hasDrafts()?'disabled':'')+'>Add</button></div>';}
function renderClip(section,clip){
  const doc=avDocument,rate=frameRate(doc),sampleRate=Number(doc.project.sample_rate||48000),isShot=section==='shots',isAudio=section==='audio';
  let inputs='';
  if(isShot)inputs=clipInput(section,clip,'source_in','Source in','integer','frames · '+seconds(draftValue(section,clip,'source_in'),rate),0,216000)+clipInput(section,clip,'frames','Length','integer','frames · '+seconds(draftValue(section,clip,'frames'),rate),1,7200)+clipInput(section,clip,'transition_frames','Dissolve','integer','frames · '+seconds(draftValue(section,clip,'transition_frames'),rate),0,doc.timing?.frames??'');
  else if(isAudio)inputs='<label>Bus<select data-field="bus" data-section="audio" data-clip="'+clip.id+'">'+['dialogue','music','fx','ambience'].map(bus=>'<option value="'+bus+'" '+(draftValue(section,clip,'bus')===bus?'selected':'')+'>'+bus+'</option>').join('')+'</select></label>'+clipInput(section,clip,'start_sample','Start','integer','samples · '+seconds(draftValue(section,clip,'start_sample'),sampleRate,3),0,doc.timing?.samples??'')+clipInput(section,clip,'source_sample','Source offset','integer','samples · '+seconds(draftValue(section,clip,'source_sample'),sampleRate,3),0,'')+clipInput(section,clip,'samples','Length','integer','samples · '+seconds(draftValue(section,clip,'samples'),sampleRate,3),1,doc.timing?.samples??'')+clipInput(section,clip,'gain_db','Gain','number','dB',-96,24)+clipInput(section,clip,'fade_in','Fade in','integer','samples · '+seconds(draftValue(section,clip,'fade_in'),sampleRate,3),0,doc.timing?.samples??'')+clipInput(section,clip,'fade_out','Fade out','integer','samples · '+seconds(draftValue(section,clip,'fade_out'),sampleRate,3),0,doc.timing?.samples??'')+clipInput(section,clip,'mute','Mute','boolean');
  else inputs=clipInput(section,clip,'start','Start','integer','frames · '+seconds(draftValue(section,clip,'start'),rate),0,doc.timing?.frames??'')+clipInput(section,clip,'frames','Length','integer','frames · '+seconds(draftValue(section,clip,'frames'),rate),1,doc.timing?.frames??'')+clipInput(section,clip,'x','X','integer','pixels',0,doc.project.size?.[0]??'')+clipInput(section,clip,'y','Y','integer','pixels',0,doc.project.size?.[1]??'')+clipInput(section,clip,'width','Width','integer','pixels',1,doc.project.size?.[0]??'')+clipInput(section,clip,'height','Height','integer','pixels',1,doc.project.size?.[1]??'')+clipInput(section,clip,'opacity','Opacity','number','0 to 1',0,1);
  const source=sourceMap().get(clip.asset),timing=(doc.timing?.shots||[]).find(item=>item.id===clip.id);
  const title=(source?.filename||clip.asset)+' · '+(timing?timing.start_frame+'–'+timing.end_frame+' frames':section);
  return '<article class="av-clip '+(selected(section,clip.id)?'selected':'')+'" data-select-clip="'+section+':'+clip.id+'"><div class="av-clip-title"><h4>'+esc(title)+'</h4><small>'+esc(clip.id)+'</small></div><div class="av-controls">'+inputs+'</div><div class="av-clip-actions"><button class="primary" data-save="'+section+':'+clip.id+'">Save changes</button><button data-remove="'+section+':'+clip.id+'"'+draftActionDisabled()+'>Remove</button></div></article>';
}
function renderSection(section,label){const clips=avDocument.project[section]||[];return '<section class="av-section"><div class="av-section-head"><div><h3>'+label+'</h3><small>'+clips.length+' clip'+(clips.length===1?'':'s')+'</small></div>'+addControl(section)+'</div>'+clips.map(clip=>renderClip(section,clip)).join('')+'</section>';}
function splitChoices(){return ['shots','audio'].flatMap(section=>(avDocument?.project?.[section]||[]).map(clip=>'<option value="'+section+':'+esc(clip.id)+'" '+(selected(section,clip.id)?'selected':'')+'>'+section.slice(0,-1)+' · '+esc(sourceLabel(clip.asset))+'</option>')).join('');}
function renderTimeline(){
  const doc=avDocument,total=Math.max(1,Number(doc.timing?.frames)||1),rate=frameRate(doc),shots=doc.project.shots||[];
  const blocks=shots.map(shot=>{const time=(doc.timing?.shots||[]).find(item=>item.id===shot.id),start=Number(time?.start_frame)||0,end=Number(time?.end_frame)||start+Number(shot.frames||0),width=Math.max(8,Math.round((end-start)/total*100));return '<button class="av-timeline-clip '+(selected('shots',shot.id)?'selected':'')+'" style="flex-basis:'+width+'%" data-select-clip="shots:'+shot.id+'"><b>'+esc(sourceLabel(shot.asset))+'</b><small>'+start+'–'+end+' f</small></button>';}).join('');
  const selectedShot=selected('shots',avSelection?.id)?shots.find(shot=>shot.id===avSelection.id):null,selectedIndex=selectedShot?shots.indexOf(selectedShot):-1;
  const choice=avSelection?.section==='audio'?'samples':'frames',disabled=draftActionDisabled();return '<section class="panel av-timeline"><div class="section-title"><div><h3>Timeline</h3><small>'+doc.timing.frames+' frames · '+seconds(doc.timing.frames,rate)+' · '+doc.timing.samples+' samples</small></div></div><div class="av-timeline-track">'+blocks+'</div><div class="av-timeline-controls"><button data-move="-1" '+(selectedIndex<=0?'disabled':disabled)+'>Move earlier</button><button data-move="1" '+(selectedIndex<0||selectedIndex>=shots.length-1?'disabled':disabled)+'>Move later</button><label>Split clip<select id="splitClip">'+splitChoices()+'</select></label><label>At <input id="splitAt" type="number" min="1" step="1" value="1"><small id="splitUnit">'+choice+'</small></label><button data-split'+disabled+'>Split</button></div></section>';
}
function renderSources(){return '<details class="av-history"><summary>Source provenance · '+avDocument.sources.length+'</summary><div class="av-history-list">'+avDocument.sources.map(source=>{const url=sameOriginUrl(source.url),preview=source.kind==='image'?'<img src="'+esc(url)+'" alt="'+esc(source.filename)+'">':source.kind==='video'?'<video controls preload="metadata" src="'+esc(url)+'"></video>':'<audio controls preload="metadata" src="'+esc(url)+'"></audio>';return '<div class="av-history-item av-source-provenance">'+preview+'<div><b>'+esc(source.filename)+'</b><span>'+esc(source.kind)+' · '+esc(source.bytes)+' bytes · '+esc(source.asset_id)+'</span><code>'+esc(source.sha256)+'</code></div></div>';}).join('')+'</div></details>';}
function renderHistory(){return '<details class="av-history"><summary>Revision history · '+(avDocument.history||[]).length+'</summary><div class="av-history-list">'+(avDocument.history||[]).slice().reverse().map(item=>'<div class="av-history-item"><b>r'+esc(item.revision)+' · '+esc(item.action)+'</b><span>'+esc(item.summary||'')+' · '+esc(item.actor||'')+' · '+esc(item.at||'')+'</span>'+(item.revision!==avDocument.revision?'<button data-restore="'+esc(item.revision)+'"'+draftActionDisabled()+'>Restore as new revision</button>':'')+'</div>').join('')+'</div></details>';}
function renderDocument(){
  if(!avDocument){$('#avEmpty').hidden=false;$('#avContent').hidden=true;return;}$('#avEmpty').hidden=true;$('#avContent').hidden=false;
  const doc=avDocument,conflicts=[...avDrafts.values()].some(draft=>draft.conflict),render=doc.render;
  const unsaved=hasDrafts()?'<p class="av-warning">'+avDrafts.size+' clip '+(avDrafts.size===1?'change is':'changes are')+' unsaved. Preview and document actions use saved revision '+doc.revision+'. Save each clip or <button data-discard-drafts>Discard unsaved changes</button>.</p>':'';
  $('#avContent').innerHTML='<section class="panel"><div class="av-document-head"><div><span class="eyebrow">SCENE</span><h2>'+esc(doc.name)+'</h2><p id="avDocumentStatus" class="av-revision">Revision '+doc.revision+' · '+esc(doc.status||'saved')+'</p></div><div class="av-document-actions"><button id="documentReload">Reload server revision</button></div></div>'+unsaved+(conflicts?'<p class="av-warning">The server changed this scene. Your unsaved fields are still retained here. Reload to compare, then save the fields you want to keep.</p>':'')+'</section>'+renderPreview(doc)+renderTimeline()+'<section class="av-sections">'+renderSection('shots','Shots · cuts and dissolves')+renderSection('audio','Audio · trim, gain and fades')+renderSection('overlays','Static overlays')+'</section>'+renderSources()+renderHistory();
}
function clipBy(section,id){return (avDocument?.project?.[section]||[]).find(clip=>clip.id===id);}
function collectChanges(section,id){const clip=clipBy(section,id),fields=[...document.querySelectorAll('[data-section="'+CSS.escape(section)+'"][data-clip="'+CSS.escape(id)+'"]')];if(!clip||!fields.length)throw Error('That clip is no longer available. Reload the scene.');const dirty=avDrafts.get(section+':'+id)||{};const changes={};for(const input of fields){const field=input.dataset.field;if(!Object.hasOwn(dirty,field))continue;const value=input.type==='checkbox'?input.checked:input.value;changes[field]=input.type==='checkbox'?value:(field==='bus'?value:(field==='gain_db'||field==='opacity'?number(value,field):integer(value,field)));}return changes;}
async function mutate(body,success){if(avMutationBusy)return;if(['add','move','split','remove','restore','render'].includes(body.action)&&!requireSavedDocument(body.action))return;avMutationBusy=true;const id=avId,revision=body.action==='edit'&&avDraftRevision!==null?avDraftRevision:avDocument.revision;try{const doc=await avPost('/api/av/'+encodeURIComponent(id),{...body,expected_revision:revision,actor:'user'});if(id!==avId)return;avDocument=doc;if(success)success();if(body.action==='edit'&&hasDrafts())avDraftRevision=doc.revision;renderDocument();maintainPolling();await refreshProjects(id);avMessage(body.action==='render'?'Render queued for revision '+doc.revision+'.':'Saved revision '+doc.revision+'.');}catch(error){if(/^Scene conflict:/i.test(error.message)){if(avSelection)draftFor(avSelection.section,avSelection.id).conflict=true;renderDocument();}avMessage(error.message,true);}finally{avMutationBusy=false;}}
async function openNewScene(){
  $('#sceneCreateStatus').textContent='Loading registered Workspace media…';$('#sceneAssets').innerHTML='';$('#sceneDialog').showModal();
  try{const data=await avApi('/api/workspace');avWorkspace=(data.assets||[]).filter(asset=>!asset.trashed_at&&/\.(png|mp4|wav)$/i.test(asset.filename||''));const preselected=queryIds();$('#sceneAssets').innerHTML=avWorkspace.map(asset=>'<label class="av-source-choice"><input type="checkbox" value="'+esc(asset.id)+'" '+(preselected.has(asset.id)?'checked':'')+'><span><b>'+esc(asset.title||asset.filename)+'</b><small>'+esc(asset.filename)+' · '+esc(asset.media_type)+' · '+esc(asset.bytes)+' bytes</small></span></label>').join('')||'<p class="muted">No supported PNG, MP4 or WAV sources are registered in Workspace.</p>';$('#sceneCreateStatus').textContent=avWorkspace.length?'Select at least one visual source. Audio is optional.':'';}catch(error){$('#sceneCreateStatus').textContent=error.message;}
}
async function createScene(event){event.preventDefault();const ids=[...document.querySelectorAll('#sceneAssets input:checked')].map(input=>input.value),assets=ids.map(id=>avWorkspace.find(asset=>asset.id===id)).filter(Boolean),visual=assets.filter(asset=>asset.media_type==='image'||asset.media_type==='video'),audio=assets.filter(asset=>asset.media_type==='audio');if(!ids.length){$('#sceneCreateStatus').textContent='Select at least one registered source.';return;}if(!visual.length){$('#sceneCreateStatus').textContent='Select at least one PNG or MP4 visual source.';return;}if(visual.length>16||audio.length>32){$('#sceneCreateStatus').textContent='A scene accepts up to 16 visual sources and 32 audio sources.';return;}$('#createScene').disabled=true;try{const doc=await avPost('/api/av',{action:'create',name:$('#sceneName').value,asset_ids:ids,fps:[24,1],size:[640,360],frames_per_shot:72,actor:'user'});avId=doc.id;avDocument=doc;avDrafts.clear();$('#sceneDialog').close();renderDocument();await refreshProjects(avId);avMessage('Created scene revision '+doc.revision+'.');}catch(error){$('#sceneCreateStatus').textContent=error.message;}finally{$('#createScene').disabled=false;}}
$('#newScene').onclick=()=>openNewScene();$('#cancelScene').onclick=()=>$('#sceneDialog').close();$('#sceneForm').onsubmit=createScene;
$('#refreshScenes').onclick=()=>refreshProjects().catch(error=>avMessage(error.message,true));$('#reloadScene').onclick=()=>loadScene(avId).catch(error=>avMessage(error.message,true));
$('#avProjectList').onclick=event=>{const project=event.target.closest('[data-project]');if(!project||avMutationBusy)return;stopPolling();avId=project.dataset.project;avDrafts.clear();avSelection=null;renderProjects();loadScene(avId).catch(error=>avMessage(error.message,true));};
$('#avContent').addEventListener('input',event=>{const input=event.target;if(!input.dataset.field)return;setDraft(input.dataset.section,input.dataset.clip,input.dataset.field,input.type==='checkbox'?input.checked:input.value);});
$('#avContent').addEventListener('change',event=>{if(event.target.id==='splitClip'){const section=event.target.value.split(':')[0];$('#splitUnit').textContent=section==='audio'?'samples':'frames';}});
$('#avContent').onclick=async event=>{
  if(event.target.closest('#documentReload')){await loadScene(avId);return;}
  if(event.target.closest('[data-discard-drafts]')){clearDrafts();renderDocument();avMessage('Discarded unsaved clip changes.');return;}
  const save=event.target.closest('[data-save]');if(save){const [section,id]=save.dataset.save.split(':');avSelection={section,id};await mutate({action:'edit',section,clip_id:id,changes:collectChanges(section,id)},()=>clearDraft(section,id));return;}
  const remove=event.target.closest('[data-remove]');if(remove){const [section,id]=remove.dataset.remove.split(':');avSelection={section,id};await mutate({action:'remove',section,clip_id:id},()=>clearDraft(section,id));return;}
  const add=event.target.closest('[data-add]');if(add){const section=add.dataset.add,source=$('[data-add-source="'+section+'"]').value;await mutate({action:'add',section,asset_key:source});return;}
  const move=event.target.closest('[data-move]');if(move&&avSelection?.section==='shots'){const clips=avDocument.project.shots,index=clips.findIndex(clip=>clip.id===avSelection.id);await mutate({action:'move',clip_id:avSelection.id,index:index+Number(move.dataset.move)});return;}
  if(event.target.closest('[data-split]')){const [section,id]=$('#splitClip').value.split(':'),at=integer($('#splitAt').value,'Split position');avSelection={section,id};await mutate({action:'split',section,clip_id:id,at});return;}
  const restore=event.target.closest('[data-restore]');if(restore){await mutate({action:'restore',source_revision:integer(restore.dataset.restore,'Revision')});return;}
  const renderAction=event.target.closest('[data-render-action]')?.dataset.renderAction;if(renderAction==='render'){await mutate({action:'render'});return;}if(renderAction==='export'){if(!requireSavedDocument('export'))return;try{const doc=await avPost('/api/av/'+encodeURIComponent(avId),{action:'export',expected_revision:avDocument.revision,actor:'user'});avDocument=doc;renderDocument();const url=sameOriginUrl(doc.export_url);if(url)location.assign(url);avMessage('Companion ZIP is ready.');}catch(error){avMessage(error.message,true);}return;}if(renderAction==='cancel'&&avDocument.render?.id){try{const doc=await avPost('/api/av/'+encodeURIComponent(avId),{action:'cancel',render_id:avDocument.render.id,actor:'user'});avDocument=doc;renderDocument();maintainPolling();avMessage('Cancel requested for this render.');}catch(error){avMessage(error.message,true);}return;}
  if(event.target.closest('input,select,label,video,audio,a'))return;
  const select=event.target.closest('[data-select-clip]');if(select){const [section,id]=select.dataset.selectClip.split(':');selectClip(section,id);}
};
avId=requestedProject()||null;
refreshProjects().catch(error=>avMessage(error.message,true));
