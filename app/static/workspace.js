let assetState = {assets:[], collections:[]}, assetScope = 'all', assetSelection = new Set(), activeAsset = null, collectionEditing = null;
let assetSignature = '', assetRefreshing = false;
function assetMessage(text, error=false) { const el=$('#assetMessage'); el.textContent=text; el.classList.toggle('error',error); }
async function refreshAssets(force=false) {
  if(assetRefreshing)return;
  assetRefreshing=true;
  try {
    const data=await api('/api/workspace'), signature=JSON.stringify(data);
    assetState=data;
    if(force||signature!==assetSignature){assetSignature=signature;renderAssets();jobsSignature='';renderJobs();}
  } catch(e) { assetMessage(e.message,true); }
  finally {assetRefreshing=false;}
}
function visibleAssets() {
  const query=$('#assetSearch').value.trim().toLowerCase(), type=$('#assetType').value;
  const list=assetState.assets.filter(a=>{
    if(assetScope==='trash'?!a.trashed_at:!!a.trashed_at)return false;
    if(assetScope==='favorite'&&!a.favorite)return false;
    if(['selected','needs_work'].includes(assetScope)&&a.review!==assetScope)return false;
    if(assetScope.startsWith('collection:')&&!a.collections.includes(assetScope.slice(11)))return false;
    return (type==='all'||a.media_type===type)&&[a.title,a.preset_name,a.notes,...a.tags].join(' ').toLowerCase().includes(query);
  });
  const sort=$('#assetSort').value;
  return list.sort((a,b)=>sort==='title'?a.title.localeCompare(b.title):sort==='oldest'?a.created_at-b.created_at:b.created_at-a.created_at);
}
function assetPreview(asset, detail=false) {
  const url=asset.url, alt=esc(asset.title);
  if(asset.media_type==='image')return '<img loading="lazy" src="'+url+'" alt="'+alt+'">';
  if(asset.media_type==='video')return '<video '+(detail?'controls':'muted')+' preload="metadata" src="'+url+'" aria-label="'+alt+'"></video>';
  if(asset.media_type==='audio')return detail?'<audio controls src="'+url+'"></audio>':'<span class="asset-type-placeholder">♫<small>Audio</small></span>';
  return detail?'<model-viewer camera-controls touch-action="pan-y" environment-image="neutral" src="'+url+'" alt="'+alt+'"></model-viewer>':'<span class="asset-type-placeholder">◇<small>3D model</small></span>';
}
function renderAssets() {
  const assets=visibleAssets(), col=assetState.collections.find(c=>'collection:'+c.id===assetScope);
  $('#assetTotal').textContent=assetState.assets.filter(a=>!a.trashed_at).length;
  $('#assetVisibleCount').textContent=assets.length+' assets';
  $('#assetScopeTitle').textContent=col?.name||({all:'All assets',favorite:'Favorites',selected:'Selected',needs_work:'Needs work',trash:'Trash'}[assetScope]||'Collection');
  $('#collectionActions').hidden=!col;
  $('#assetCollections').innerHTML=assetState.collections.map(c=>'<button data-scope="collection:'+c.id+'" class="'+(col?.id===c.id?'active':'')+'"><span>▱ '+esc(c.name)+'</span><small>'+c.count+'</small></button>').join('')||'<p class="muted">Collect a character, a project, or an idea.</p>';
  document.querySelectorAll('#assetScopes [data-scope]').forEach(b=>b.classList.toggle('active',b.dataset.scope===assetScope));
  const destination=$('#bulkCollection').value;
  $('#bulkCollection').innerHTML='<option value="">Choose collection…</option>'+assetState.collections.map(c=>'<option value="'+c.id+'">'+esc(c.name)+'</option>').join('');
  if(assetState.collections.some(c=>c.id===destination))$('#bulkCollection').value=destination;
  $('#assetGrid').innerHTML=assets.map(a=>'<article class="asset-card '+(assetSelection.has(a.id)?'is-selected':'')+'"><div class="asset-card-preview"><button class="asset-open" data-asset-open="'+a.id+'" aria-label="Open '+esc(a.title)+'">'+assetPreview(a)+'</button><label class="asset-check"><input type="checkbox" data-asset-check="'+a.id+'" '+(assetSelection.has(a.id)?'checked':'')+' aria-label="Select '+esc(a.title)+'"></label><button class="asset-star '+(a.favorite?'starred':'')+'" data-asset-favorite="'+a.id+'" aria-label="'+(a.favorite?'Unfavorite':'Favorite')+' '+esc(a.title)+'">'+(a.favorite?'★':'☆')+'</button><span class="asset-kind">'+esc(a.media_type)+'</span></div><button class="asset-card-title" data-asset-open="'+a.id+'">'+esc(a.title)+'</button><div class="asset-card-meta"><span>'+esc(a.preset_name)+'</span><span class="review-'+a.review+'">'+esc(a.review.replace('_',' '))+'</span></div><div class="asset-tags">'+a.tags.slice(0,4).map(t=>'<span>'+esc(t)+'</span>').join('')+'</div></article>').join('')||'<div class="asset-empty"><h3>'+(assetScope==='trash'?'Trash is empty.':'Room for the next idea.')+'</h3><p>'+(assetScope==='trash'?'Deleted assets can be restored here.':'Generate an asset, or change your filters to see more of your work.')+'</p></div>';
  renderAssetSelection();
}
function renderAssetSelection() {
  $('#assetBulk').hidden=!assetSelection.size;
  $('#assetSelectionCount').textContent=assetSelection.size+' selected';
  document.querySelectorAll('[data-bulk="restore"]').forEach(b=>b.hidden=assetScope!=='trash');
  document.querySelectorAll('[data-bulk="trash"]').forEach(b=>b.hidden=assetScope==='trash');
}
async function mutateAssets(payload) { await post('/api/assets/update',payload);await refreshAssets(true); }
function setAssetScope(scope){assetScope=scope;assetSelection.clear();renderAssets();assetMessage(scope==='trash'?'Trash is recoverable. Original files and recipes remain on disk.':'');}
function openCollection(id=null) {
  collectionEditing=id; const col=assetState.collections.find(c=>c.id===id);
  $('#collectionDialogTitle').textContent=id?'Edit collection':'New collection';
  $('#collectionName').value=col?.name||'';$('#collectionDescription').value=col?.description||'';
  $('#collectionDialog').showModal();$('#collectionName').focus();
}
function openAsset(id) {
  activeAsset=assetState.assets.find(a=>a.id===id);if(!activeAsset)return;
  const a=activeAsset;
  $('#assetDetailMedia').innerHTML=assetPreview(a,true);
  $('#assetTitle').value=a.title;$('#assetTags').value=a.tags.join(', ');$('#assetReview').value=a.review;$('#assetNotes').value=a.notes;
  $('#assetDetails').innerHTML='<p>'+esc(a.preset_name)+' · '+new Date(a.created_at*1000).toLocaleString()+'</p><p>'+esc(a.filename)+' · '+(a.bytes/1024/1024).toFixed(2)+' MiB</p><p>Seed '+esc(a.source.seed??'not recorded')+'</p><details><summary>File identity</summary><code>'+a.sha256+'</code><p>Prompt '+esc(a.source.prompt_id||'not recorded')+'</p></details>';
  $('#assetFavorite').textContent=a.favorite?'★ Favorited':'☆ Favorite';$('#assetTrash').textContent=a.trashed_at?'Restore':'Move to Trash';
  $('#assetDownload').href=a.url+'?download';
  $('#assetHandoffs').innerHTML=a.media_type==='image'?'<button data-handoff="reference">Edit image</button><button data-handoff="wan22-i2v">Animate</button><button data-handoff="trellis-auto-cutout">Make 3D</button><button data-handoff="anime-upscale">Upscale</button>':'';
  $('#assetLineage').innerHTML=a.lineage.length?'<h3>Source assets</h3>'+a.lineage.map(id=>{const parent=assetState.assets.find(p=>p.id===id);return '<button data-lineage="'+esc(id)+'">'+esc(parent?.title||id)+'</button>';}).join(''):'';
  if(!$('#assetDialog').open)$('#assetDialog').showModal();
}
async function handoffAsset(id,presetId) {
  const result=await post('/api/assets/reference',{id});
  let preset=catalog.presets.find(p=>p.id===presetId);
  if(presetId==='reference')preset=catalog.presets.find(p=>p.id==='gentle-variation')||catalog.presets.find(p=>p.reference&&(p.modality||'image')==='image');
  if(presetId==='anime-upscale')preset=catalog.presets.find(p=>p.id==='anime-esrgan-2x')||catalog.presets.find(p=>p.reference&&/upscale/i.test(p.name));
  if(!preset)throw Error('That recipe is unavailable');
  selectPreset(preset.id);uploaded=result.file;parentAssets=[id];
  $('#referenceHint').textContent='Attached '+(assetState.assets.find(a=>a.id===id)?.title||'asset')+' · '+result.width+' × '+result.height;
  $('#assetDialog').close();showView('create');$('#selectedPreset').scrollIntoView({block:'start',behavior:'smooth'});message('Source asset attached. Adjust your brief, then generate.');
}
$('#workspaceRefresh').onclick=()=>refreshAssets(true);
$('#assetSearch').oninput=renderAssets;$('#assetType').onchange=renderAssets;$('#assetSort').onchange=renderAssets;
$('#newCollection').onclick=()=>openCollection();$('#renameCollection').onclick=()=>openCollection(assetScope.slice(11));
$('#cancelCollection').onclick=()=>$('#collectionDialog').close();
$('#collectionForm').onsubmit=async e=>{e.preventDefault();try{const col=await post('/api/collections',{action:collectionEditing?'rename':'create',id:collectionEditing,name:$('#collectionName').value,description:$('#collectionDescription').value});$('#collectionDialog').close();assetScope='collection:'+col.id;await refreshAssets(true);}catch(err){assetMessage(err.message,true);}};
$('#deleteCollection').onclick=async()=>{try{await post('/api/collections',{action:'delete',id:assetScope.slice(11)});assetScope='all';await refreshAssets(true);assetMessage('Collection removed. Its assets are still in your workspace.');}catch(e){assetMessage(e.message,true);}};
$('#selectVisible').onclick=()=>{assetSelection=new Set(visibleAssets().slice(0,200).map(a=>a.id));renderAssets();};
$('#clearAssetSelection').onclick=()=>{assetSelection.clear();renderAssets();};
$('#closeAssetDialog').onclick=()=>$('#assetDialog').close();
$('#assetDialog').addEventListener('close',()=>{$('#assetDetailMedia').innerHTML='';});
$('#saveAssetDetails').onclick=async()=>{try{await mutateAssets({ids:[activeAsset.id],action:'edit',title:$('#assetTitle').value,tags:$('#assetTags').value.split(',').map(t=>t.trim()).filter(Boolean),review:$('#assetReview').value,notes:$('#assetNotes').value});$('#assetDialog').close();assetMessage('Asset details saved.');}catch(e){assetMessage(e.message,true);}};
$('#assetFavorite').onclick=async()=>{await mutateAssets({ids:[activeAsset.id],action:'edit',favorite:!activeAsset.favorite});openAsset(activeAsset.id);};
$('#assetTrash').onclick=async()=>{const action=activeAsset.trashed_at?'restore':'trash';await mutateAssets({ids:[activeAsset.id],action});$('#assetDialog').close();assetMessage(action==='trash'?'Moved to Trash. Restore it at any time.':'Asset restored.');};
$('#assetRecipe').onclick=()=>exportRecipe(activeAsset.job_id);
document.addEventListener('click',async e=>{
  try{
    const scope=e.target.closest('[data-scope]');if(scope)setAssetScope(scope.dataset.scope);
    const open=e.target.closest('[data-asset-open]');if(open)openAsset(open.dataset.assetOpen);
    const favorite=e.target.closest('[data-asset-favorite]');if(favorite){const a=assetState.assets.find(a=>a.id===favorite.dataset.assetFavorite);await mutateAssets({ids:[a.id],action:'edit',favorite:!a.favorite});}
    const lineage=e.target.closest('[data-lineage]');if(lineage)openAsset(lineage.dataset.lineage);
    const handoff=e.target.closest('[data-handoff]');if(handoff)await handoffAsset(activeAsset.id,handoff.dataset.handoff);
    const bulk=e.target.closest('[data-bulk]');
    if(bulk){
      const ids=[...assetSelection], action=bulk.dataset.bulk;if(!ids.length)return;
      if(action==='export'){assetMessage('Building a pack with originals, recipes and metadata…');const result=await post('/api/assets/export',{ids});const link=document.createElement('a');link.href=result.url;link.download='asset-pack.zip';link.click();assetMessage('Export ready: '+result.count+' assets with recipes and provenance.');return;}
      const payload={ids,action,collection_id:$('#bulkCollection').value};
      if(action==='favorite')Object.assign(payload,{action:'edit',favorite:true});
      if(action==='selected')Object.assign(payload,{action:'edit',review:'selected'});
      await mutateAssets(payload);assetSelection.clear();renderAssets();assetMessage(action==='trash'?'Moved to Trash. Originals and recipes are preserved.':'Updated '+ids.length+' assets.');
    }
  }catch(err){assetMessage(err.message,true);message(err.message,true);}
});
document.addEventListener('change',e=>{const id=e.target.dataset.assetCheck;if(id){e.target.checked?assetSelection.add(id):assetSelection.delete(id);e.target.closest('.asset-card').classList.toggle('is-selected',e.target.checked);renderAssetSelection();}});
