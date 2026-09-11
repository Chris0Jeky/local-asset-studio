const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const safeUrl = url => { try { const u = new URL(url); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const gib = n => (Number(n || 0) / 1024 ** 3).toFixed(2) + ' GiB';
const controlKeys = ['seed','steps','cfg','width','height','denoise','lora','frames','fps','sampler','scheduler'];
let catalog, selected, online = false, schemaAvailable = false, missingByPreset = {}, jobs = [], pinned = [], uploaded = null, lastUploaded = null, library, mode = 'all', submitting = false, view = 'create', jobsSignature = '', activeJobId = null;
let recipeTemplateHash = null, parentAssets = [], serverSetups = [];
async function api(path, options={}) { const r = await fetch(path, options); const data = await r.json(); if (!r.ok) throw Error(data.error || 'Request failed'); return data; }
const post = (path, data) => api(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const getControl = key => document.querySelector('[data-key="' + key + '"]');
function message(text, error=false) { $('#status').textContent = text; $('#status').classList.toggle('error', error); }
function clearReference() { uploaded = lastUploaded = null; parentAssets=[]; if(typeof resetReferenceSlots==='function')resetReferenceSlots(); $('#reference').value = ''; $('#lastReference').value = ''; $('#referenceHint').textContent = "PNG, JPG or WebP · up to 20 MiB. The recipe's example is used until replaced."; }
function renderPresets() {
  if (!catalog) return;
  const query = $('#presetSearch').value.toLowerCase(), category = $('#categorySelect').value;
  const list = catalog.presets.filter(p => (mode === 'all' || (p.modality || 'image') === mode) && (category === 'All' || p.category === category) && [p.name,p.family,p.description,p.category].join(' ').toLowerCase().includes(query));
  $('#filteredCount').textContent = list.length;
  $('#presetList').innerHTML = list.map(p => '<button class="preset ' + (selected?.id === p.id ? 'chosen' : '') + '" data-id="' + esc(p.id) + '"><b>' + esc(p.name) + '</b><span>' + esc(p.description) + '</span><div class="recipe-meta"><span>' + esc(p.family || p.category) + '</span><em class="badge ' + (p.verified ? 'tested' : '') + '">' + (p.verified ? 'Executed' : 'Experimental') + '</em></div></button>').join('') || '<p class="muted">No recipes match. Try another collection or search.</p>';
}
function updateReady() {
  const missing = missingByPreset[selected?.id] || [];
  $('#generate').disabled = submitting || !online || !schemaAvailable || !selected || !!selected.runtime_block || missing.length > 0 || (typeof referencesReady==='function'&&!referencesReady());
  $('#health').textContent = !online ? 'ComfyUI offline' : !schemaAvailable ? 'Checking node readiness' : missing.length ? 'Recipe needs models' : 'ComfyUI connected';
  $('#health').className = 'pill ' + (online && schemaAvailable && !missing.length ? 'ready' : 'offline');
}
function renderSelected() {
  if (!selected) return;
  $('#selectedPreset').innerHTML = '<span class="badge">' + esc(selected.family || selected.category) + '</span> <span class="badge ' + (selected.verified ? 'tested' : '') + '">' + (selected.verified ? 'Execution recorded' : 'Experimental · not quality-approved') + '</span><h2>' + esc(selected.name) + '</h2><p>' + esc(selected.description) + '</p><small>' + esc(selected.commercial_note) + '</small>';
  $('#positiveWrap').hidden = !selected.positive;
  $('#positive').value = selected.defaults?.positive || ''; $('#negative').value = selected.defaults?.negative || ''; $('#negativeWrap').hidden = !selected.negative;
  $('#pipeline').innerHTML = (selected.stages || ['Load model','Conditioning','Sample','Decode','Save output']).map(s => '<span>' + esc(s) + '</span>').join('');
  const variants = selected.variants || [{name:'3-seed audition',batch_count:3}];
  $('#variants').innerHTML = variants.map((v,i) => '<button data-variant="' + i + '">' + esc(v.name) + '</button>').join('');
  const specs = [['seed','Seed','number','min="0" max="9007199254740991" step="1"'],['steps','Steps','number','min="1" max="150"'],['cfg','Guidance (CFG)','number','min="0" max="30" step="0.1"'],['width','Width','number','min="64" max="1536" step="' + (selected.dimension_multiple || 8) + '"'],['height','Height','number','min="64" max="1536" step="' + (selected.dimension_multiple || 8) + '"'],['denoise','Denoise','number','min="0" max="1" step="0.01"'],['lora','LoRA strength','number','min="0" max="2" step="0.05"'],['frames','Frames','number','min="5" max="365" step="' + (selected.frame_grid || 1) + '"'],['fps','Frames per second','number','min="1" max="60" step="1"'],['sampler','Sampler','select',''],['scheduler','Schedule','select','']];
  $('#controls').innerHTML = specs.filter(([k]) => selected[k] || selected.bindings_extra?.[k]).map(([key,label,type,attrs]) => {
    if (type === 'select') return '<label>' + label + '<select data-key="' + key + '">' + (selected.choices?.[key] || []).map(v => '<option>' + esc(v) + '</option>').join('') + '</select></label>';
    if (key === 'lora' && typeof selected.defaults?.lora === 'string') { type='text'; attrs=''; label='LoRA filename'; }
    return '<label>' + label + '<input data-key="' + key + '" type="' + type + '" ' + attrs + '>' + (key === 'frames' ? '<small>' + (selected.family==='MiniMax H3'?'24fps · 124 ≈ 5.2s · use 17k+5 frames':'24fps · 81 ≈ 3.4s · use 4k+1 frames') + '</small>' : '') + '</label>';
  }).join('');
  controlKeys.forEach(k => { const input=getControl(k); if (input) input.value=selected.defaults?.[k] ?? ''; });
  $('#referenceWrap').hidden = !selected.reference; $('#lastReferenceWrap').hidden = !selected.last_reference;
  if(typeof renderReferenceSlots==='function')renderReferenceSlots();
  $('#workflow').href = '/api/workflows/' + encodeURIComponent(selected.id);
  $('#visualWorkflow').hidden = !selected.visual; $('#visualWorkflow').href = $('#workflow').href + '?visual';
  $('#sourceLink').hidden = !selected.source; $('#sourceLink').href = safeUrl(selected.source);
  $('#generate').textContent = selected.modality === 'video' ? 'Generate video →' : selected.modality === '3d' ? 'Generate mesh →' : 'Generate image →';
  updateReady(); inspectSelected();
  if(selected.runtime_block) message(selected.runtime_block,true);
}
async function inspectSelected() {
  const id = selected?.id; if (!id) return;
  try {
    const data = await api('/api/inspect/' + encodeURIComponent(id)); if (selected?.id !== id) return;
    $('#dependencyCount').textContent = data.requirements.filter(r => r.present).length + ' / ' + data.requirements.length + ' present';
    $('#dependencies').innerHTML = data.requirements.map(r => '<div class="dependency ' + (r.present ? '' : 'missing') + '"><span class="dot">' + (r.present ? '●' : '○') + '</span><div class="file-text"><code>' + esc(r.file) + '</code><small>' + (r.present ? 'File present' : 'Missing · place in the indicated folder') + '</small></div><button data-copy="' + esc(r.path) + '" title="Copy full file path">Copy path</button>' + (!r.present && r.asset_id ? '<button data-install="' + esc(r.asset_id) + '">Install</button>' : '') + '</div>').join('') || '<p class="muted">No separate weight files in this workflow.</p>';
    $('#nodeList').innerHTML = data.nodes.map(n => '<code>' + esc(n.type) + '</code>').join('');
    $('#graphPreview').textContent = JSON.stringify(data.graph,null,2);
  } catch(e) { $('#dependencies').textContent=e.message; }
}
function selectPreset(id, reset=true) {
  recipeTemplateHash=null;
  selected=catalog.presets.find(p=>p.id===id); if (!selected) return;
  if(reset) clearReference(); $('#batch').value=1; renderPresets(); renderSelected();
  message(selected.runtime_block || 'Recipe loaded. Change a setting or choose a variation, then generate when ready.',!!selected.runtime_block);
}
async function health() {
  try {
    const h=await api('/api/health'); online=h.online; schemaAvailable=!!h.schema_available; missingByPreset=h.missing_models || {};
    if(h.devices?.[0]) $('#hardware').textContent=h.devices[0].name.replace(/^cuda:\d+ /,'').replace(' : native','') + ' · ' + (h.devices[0].vram_total/1024**3).toFixed(0) + ' GB VRAM';
    if(h.comfy_url) $('#comfyLink').href=safeUrl(h.comfy_url);
    updateReady();
    if(!online) message('ComfyUI is offline. Start it with the Asset Studio launcher.',true);
    else if(!schemaAvailable) message('The node schema is unavailable; readiness cannot yet be verified.',true);
    else if(missingByPreset[selected?.id]?.length) message('This recipe needs: ' + missingByPreset[selected.id].join(', '),true);
  } catch(e) { online=false; schemaAvailable=false; updateReady(); }
}
function values() {
  const c={}; if(selected.positive)c.positive=$('#positive').value; if(selected.negative)c.negative=$('#negative').value;
  controlKeys.forEach(k=>{const input=getControl(k); if(input&&input.value!=='')c[k]=input.value;});
  if(selected.reference&&uploaded)c.reference=uploaded; if(selected.last_reference&&lastUploaded)c.last_reference=lastUploaded; return c;
}
async function uploadInput(id) {
  const file=$('#'+id).files[0]; if(!file)return null;
  if(file.size>20*1024*1024)throw Error('Reference image exceeds 20 MiB');
  return (await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file})).file;
}
function mediaCard(job,index,output) {
  const id=esc(job.id), url='/api/image/'+id+'/'+index, type=output.media_type || 'image';
  const media=type==='video'?'<video controls preload="metadata" src="'+url+'"></video>':type==='audio'?'<audio controls src="'+url+'"></audio>':type==='3d'?'<model-viewer loading="lazy" camera-controls touch-action="pan-y" environment-image="neutral" shadow-intensity="0.7" src="'+url+'" alt="'+esc(job.preset_name)+' mesh"><span slot="poster">Load interactive 3D preview</span></model-viewer>':'<img loading="lazy" src="'+url+'" alt="'+esc(job.preset_name)+' output">';
  return '<article class="imageCard">'+media+'<div class="card-actions">'+(type==='image'?'<button class="pin" data-job="'+id+'" data-index="'+index+'">Compare</button><button class="reference-output" data-job="'+id+'" data-index="'+index+'">Use as reference</button><button class="reference-output" data-preset="wan22-i2v" data-job="'+id+'" data-index="'+index+'">Animate</button><button class="reference-output" data-preset="trellis-auto-cutout" data-job="'+id+'" data-index="'+index+'">Make 3D</button>':'')+'<a download="'+esc(output.filename || 'asset')+'" href="'+url+'">Download</a><button class="recipe" data-job="'+id+'">Recipe</button></div><p>'+esc(job.controls.positive || job.preset_name)+'<br><small>Seed '+esc(output.seed ?? job.controls.seed ?? 'default')+' · '+esc(job.preset_name)+'</small></p></article>';
}
function renderCompare() { $('#compare').hidden=!pinned.length; $('#compareImages').innerHTML=pinned.map(p=>'<img src="/api/image/'+esc(p.job)+'/'+esc(p.index)+'" alt="Pinned comparison">').join(''); }
function renderJobs() {
  const signature=JSON.stringify(jobs); if(signature===jobsSignature)return; jobsSignature=signature;
  const cards=[];
  jobs.forEach(job=>{
    if(job.status!=='completed')cards.push('<article class="jobStatus '+esc(job.status)+'"><b>'+esc(job.preset_name)+' · '+esc(job.status)+'</b><p>'+esc(job.message)+'</p>'+(['uncertain','partial'].includes(job.status)&&job.prompt_ids?.length?'<button class="resume" data-job="'+esc(job.id)+'">Resume observation</button>':'')+'</article>');
    job.outputs?.forEach((o,i)=>{if(cards.length>=10)return;const a=typeof assetState!=='undefined'&&assetState.assets.find(a=>a.id===o.asset_id);if(!a?.trashed_at)cards.push(mediaCard(job,i,o));});
  });
  $('#gallery').className=cards.length?'gallery':'galleryEmpty'; $('#gallery').innerHTML=cards.length?cards.join(''):'The next good idea starts here.<small>Your outputs and recipes stay on this computer.</small>'; renderCompare();
}
async function refresh(){try{jobs=await api('/api/jobs');renderJobs();const job=jobs.find(j=>j.id===activeJobId);if(job){message(job.preset_name+': '+job.message,['failed','uncertain'].includes(job.status));if(['completed','failed','partial','uncertain'].includes(job.status))activeJobId=null;}}catch(e){message(e.message,true);}}
function showView(next){view=next;['create','assets','production','models','learn'].forEach(name=>{$('#'+name+'View').hidden=name!==next;document.querySelector('[data-view="'+name+'"]').classList.toggle('active',name===next);});$('.hero').hidden=next!=='create';if(next==='models'||next==='learn')refreshLibrary();if(next==='assets')refreshAssets();if(next==='production')refreshProduction();location.hash=next;}
function renderInventory(){if(!library)return;const q=$('#modelSearch').value.toLowerCase();$('#inventory').innerHTML=library.inventory.filter(m=>m.file.toLowerCase().includes(q)).map(m=>'<div class="inventory-row"><code>'+esc(m.file)+'</code><span>'+gib(m.bytes)+'</span></div>').join('')||'<p class="muted">No matching installed weights.</p>';}
async function refreshLibrary(){
  try{
    library=await api('/api/library');const s=library.storage;
    $('#storage').innerHTML='<div><b>'+gib(s.free_bytes)+'</b><small> free on the model drive</small></div><div class="bar"><span style="width:'+Math.min(100,s.free_bytes/s.total_bytes*100)+'%"></span></div><small>Downloads keep '+gib(s.reserve_bytes)+' free for cache, outputs and system memory. Model folder: '+esc(library.model_root)+'</small>';
    const busy=library.assets.some(a=>['queued','downloading','verifying'].includes(a.download?.status)&&Date.now()/1000-a.download.updated_at<180);
    $('#modelCards').innerHTML=library.assets.map(a=>{
      const d=a.download||{},active=['queued','downloading','verifying'].includes(d.status)&&Date.now()/1000-d.updated_at<180;
      const state=a.verified?'SHA-256 verified':a.present?'Present · verify file':active?d.status:'Not installed';
      return '<article class="model-card"><span class="badge '+(a.verified?'tested':'')+'">'+esc(state)+'</span><h3>'+esc(a.name)+'</h3><p>'+esc(a.family)+' · '+gib(a.bytes)+'</p><code>'+esc(a.file)+'</code>'+(a.trigger?'<p>Trigger: <b>'+esc(a.trigger)+'</b></p>':'')+'<p>'+esc(a.license)+'</p>'+(active?'<progress max="'+a.bytes+'" value="'+(d.bytes_done||0)+'"></progress><p>'+gib(d.bytes_done)+' / '+gib(a.bytes)+'</p>':'')+(d.status==='failed'?'<p class="error">'+esc(d.message)+'</p>':'')+'<div class="model-actions"><a href="'+esc(safeUrl(a.source))+'" target="_blank" rel="noreferrer">Source ↗</a><button data-install="'+esc(a.id)+'" '+(a.verified||busy?'disabled':'')+'>'+(a.verified?'Installed':a.present?'Verify existing file':'Install / use download')+'</button></div></article>';
    }).join('');
    $('#folders').innerHTML=library.folders.map(f=>'<article class="folder"><b>'+esc(f.label)+'</b><code>'+esc(f.path)+'</code><button data-folder="'+esc(f.id)+'">Open folder</button><button data-copy="'+esc(f.path)+'">Copy path</button></article>').join('');
    $('#collections').innerHTML=(library.collections || []).map(c=>'<article class="collection"><b><a href="'+esc(safeUrl(c.url))+'" target="_blank" rel="noreferrer">'+esc(c.name)+' ↗</a></b><p>'+esc(c.description)+'</p><small>'+esc(c.status || '')+'</small></article>').join('');
    renderInventory();
  }catch(e){$('#downloadStatus').textContent=e.message;}
}
async function install(id){try{const data=await post('/api/models/install',{id});$('#downloadStatus').textContent=data.message;message('Model installation started. Progress is in Models & folders.');await refreshLibrary();}catch(e){$('#downloadStatus').textContent=e.message;message(e.message,true);}}
function saved(){return serverSetups.map(s=>({...s.recipe,name:s.name,id:s.id}));}
async function loadSetups(){
  serverSetups=await api('/api/setups');
  const identity=await api('/api/identity'), migrationKey='asset-studio-setups-migrated:'+identity.workspace;
  if(!localStorage.getItem(migrationKey)){
    let old=[];try{old=JSON.parse(localStorage.getItem('asset-studio-saved')||'[]');}catch{}
    if(Array.isArray(old))for(const recipe of old){
      if(serverSetups.some(s=>s.name===recipe.name&&JSON.stringify(s.recipe)===JSON.stringify(recipe)))continue;
      const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(recipe)));
      const id='legacy-'+[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');
      await post('/api/setups',{id,name:recipe.name,recipe});
    }
    localStorage.setItem(migrationKey,'1');serverSetups=await api('/api/setups');
  }
  renderSaved();
}
function renderSaved(){$('#savedList').innerHTML=saved().map((s,i)=>'<span class="saved-chip"><button data-load="'+i+'">'+esc(s.name)+'</button><button data-delete-setup="'+esc(s.id)+'" aria-label="Delete '+esc(s.name)+' setup">×</button></span>').join('')||'<small>Save a variation once it is worth coming back to.</small>';}
function applySaved(s){
  if(!s||!catalog.presets.some(p=>p.id===s.preset))throw Error('This recipe uses an unavailable preset');
  selectPreset(s.preset);
  parentAssets=Array.isArray(s.parent_assets)?s.parent_assets.filter(id=>typeof id==='string'):[];
  if(selected.reference_slots)restoreReferenceSlots(s.references);
  Object.entries(s.controls||{}).forEach(([k,v])=>{const el=k==='positive'?$('#positive'):k==='negative'?$('#negative'):getControl(k);if(el)el.value=v;});
  if(selected.reference&&typeof s.controls?.reference==='string')uploaded=s.controls.reference;
  if(selected.last_reference&&typeof s.controls?.last_reference==='string')lastUploaded=s.controls.last_reference;
  $('#batch').value=s.batch_count||s.batch||1;message('Recipe loaded. Review the settings before generating.');
}
async function exportRecipe(id){const data=await api('/api/jobs/'+encodeURIComponent(id)+'/recipe'),a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='asset-studio-recipe.json';a.click();URL.revokeObjectURL(a.href);}
document.querySelector('nav').onclick=e=>{if(e.target.dataset.view)showView(e.target.dataset.view);};
$('#presetSearch').oninput=renderPresets;$('#categorySelect').onchange=renderPresets;
$('#modalities').onclick=e=>{if(!e.target.dataset.mode)return;mode=e.target.dataset.mode;$('#categorySelect').value='All';document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));renderPresets();};
$('#presetList').onclick=e=>{const id=e.target.closest('[data-id]')?.dataset.id;if(id)selectPreset(id);};
$('#variants').onclick=e=>{const i=e.target.closest('[data-variant]')?.dataset.variant;if(i===undefined)return;const v=(selected.variants||[{name:'3-seed audition',batch_count:3}])[i];Object.entries(v.controls||{}).forEach(([k,val])=>{const input=getControl(k);if(input)input.value=val;});$('#batch').value=v.batch_count||1;message(v.name+' loaded. Press Generate to run.');};
$('#randomSeed').onclick=()=>{const input=getControl('seed');if(input)input.value=Math.floor(Math.random()*2147483647);};
$('#reference').onchange=()=>uploaded=null;$('#lastReference').onchange=()=>lastUploaded=null;
$('#generate').onclick=async()=>{
  if(submitting||!selected)return;submitting=true;updateReady();
  try{
    uploaded=(await uploadInput('reference'))||uploaded;lastUploaded=(await uploadInput('lastReference'))||lastUploaded;
    const job=await post('/api/jobs',{preset_id:selected.id,controls:values(),batch_count:$('#batch').value,expected_template_sha256:recipeTemplateHash,parent_assets:parentAssets,references:attachedReferencePayload()});activeJobId=job.id;message(job.message);await refresh();
  }catch(e){message(e.message,true);}finally{submitting=false;updateReady();}
};
$('#gallery').onclick=async e=>{
  try{
    const pin=e.target.closest('.pin');if(pin){const p={job:pin.dataset.job,index:pin.dataset.index};pinned=pinned.some(x=>x.job===p.job&&x.index===p.index)?pinned.filter(x=>x.job!==p.job||x.index!==p.index):[...pinned.slice(-1),p];renderCompare();}
    const recipe=e.target.closest('.recipe');if(recipe)await exportRecipe(recipe.dataset.job);
    const resume=e.target.closest('.resume');if(resume){await post('/api/jobs/'+encodeURIComponent(resume.dataset.job)+'/resume',{});await refresh();}
    const ref=e.target.closest('.reference-output');if(ref){
      const blob=await (await fetch('/api/image/'+encodeURIComponent(ref.dataset.job)+'/'+ref.dataset.index)).blob();
      if(ref.dataset.preset)selectPreset(ref.dataset.preset);
      if(!selected.reference)selectPreset(catalog.presets.find(p=>p.id==='gentle-variation')?.id || catalog.presets.find(p=>p.reference&&p.modality==='image').id);
      uploaded=(await api('/api/upload',{method:'POST',headers:{'Content-Type':blob.type,'X-Filename':'previous-output.png'},body:blob})).file;
      $('#reference').value='';
      $('#referenceHint').textContent='Using the selected output as the reference. It has been copied into this recipe.';
      message('Reference attached. Adjust the prompt, then generate when ready.');
    }
  }catch(err){message(err.message,true);}
};
$('#save').onclick=async()=>{if(!selected)return;const name=$('#saveName').value.trim();if(!name){message('Give this setup a name first.');return;}try{await post('/api/setups',{name,recipe:{preset:selected.id,controls:values(),batch:$('#batch').value,parent_assets:parentAssets,references:attachedReferencePayload()}});$('#saveName').value='';await loadSetups();message('Setup saved in your workspace, available in every browser.');}catch(e){message(e.message,true);}};
$('#savedList').onclick=async e=>{try{if(e.target.dataset.load!==undefined)applySaved(saved()[e.target.dataset.load]);if(e.target.dataset.deleteSetup){await post('/api/setups',{action:'delete',id:e.target.dataset.deleteSetup});await loadSetups();}}catch(err){message(err.message,true);}};
$('#importRecipe').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw Error('Recipe must be under 1 MiB');const recipe=JSON.parse(await file.text());const check=await post('/api/recipe-check',recipe);applySaved({preset:recipe.preset_id,controls:recipe.controls,batch_count:recipe.batch_count,parent_assets:recipe.parent_assets,references:recipe.references});recipeTemplateHash=check.template_sha256;message('Recipe loaded: embedded workflow matches this preset. Referenced inputs and model files remain local dependencies.');}catch(err){message('Could not import recipe: '+err.message,true);}finally{e.target.value='';}};
$('#refreshModels').onclick=async()=>{await api('/api/health?refresh');await health();await refreshLibrary();};$('#modelSearch').oninput=renderInventory;
document.addEventListener('click',async e=>{
  const copy=e.target.closest('[data-copy]'),folder=e.target.closest('[data-folder]'),button=e.target.closest('[data-install]');
  try{if(copy){await navigator.clipboard.writeText(copy.dataset.copy);copy.textContent='Copied';}if(folder)await post('/api/folders/open',{id:folder.dataset.folder});if(button)await install(button.dataset.install);}catch(err){message(err.message,true);$('#downloadStatus').textContent=err.message;}
});
$('#importWorkflow').onchange=async e=>{
  try{const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw Error('Workflow JSON must be under 1 MiB');const report=await post('/api/workflow-inspect',{workflow:JSON.parse(await file.text()),name:file.name});$('#importReport').innerHTML='<p><b>'+report.node_count+' nodes inspected</b> · '+esc(report.format)+'</p><p>Missing nodes: '+esc(report.missing_nodes.join(', ')||'none detected')+'</p><p>Model filenames: '+esc(report.models.join(', ')||'none found in saved values')+'</p><p>Missing files: '+esc(report.missing_models.join(', ')||'none detected')+'</p><small>'+esc(report.note)+'</small>';}catch(err){$('#importReport').textContent=err.message;}finally{e.target.value='';}
};
(async()=>{
  try{
    catalog=await api('/api/catalog');$('#recipeCount').textContent=catalog.presets.length+' editable recipes';
    $('#categorySelect').innerHTML=['All',...new Set(catalog.presets.map(p=>p.category||'Other'))].map(c=>'<option>'+esc(c)+'</option>').join('');
    selectPreset(catalog.presets.find(p=>p.id==='anima-portrait')?.id||catalog.presets[0].id);await loadSetups();await health();await refresh();await refreshAssets();await refreshLibrary();
    const initial=location.hash.slice(1);if(['create','assets','production','models','learn'].includes(initial))showView(initial);
    setInterval(async()=>{await refresh();if(view==='production')await refreshProduction();if(view==='assets'||jobs.some(j=>['running','waiting','queued'].includes(j.status)))await refreshAssets();},4000);setInterval(async()=>{await health();if(view==='models')await refreshLibrary();},15000);
  }catch(e){message(e.message,true);}
})();
