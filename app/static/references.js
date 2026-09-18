let referenceRecords=[], referenceEpoch=0, referencePending=0;
const referenceRoles=['identity','pose','style','costume','composition','geometry','motion','mask'];
function resetReferenceSlots(){referenceEpoch++;referencePending=0;referenceRecords=(selected?.reference_slots||[]).map(s=>({role:s.role,contribution:s.contribution,avoid:s.avoid,file:null}));}
function referencesReady(){if(!selected?.reference_slots?.length)return true;if(referencePending||referenceRecords.length!==selected.reference_slots.length)return false;const filled=referenceRecords.filter(r=>r.file&&!r.missing).length;return selected.reference_board?filled>=(selected.reference_board.min??1)&&!referenceRecords.some(r=>r.missing):filled===referenceRecords.length;}
// A recipe that names its board (reference_board_label, e.g. "Pose picture (image 2)") describes it in its own words; the IP-Adapter sentence is the fallback (#367 shipped the labels without rendering them).
// The labels' "(image N)" parentheticals carry the reference order: the 4B Combine keeps its source as image 1, the 9B Combine puts the board picture first (pose first, character swapped in).
function boardSummaryLabel(preset){const label=String(preset.reference_board_label||'').replace(/\s*\(.*\)\s*$/,'').toLowerCase();if(!preset.last_reference)return label+'s only';const boardImage=/\(image (\d)\)/.exec(String(preset.reference_board_label||''))?.[1],keepImage=/\(image (\d)\)/.exec(String(preset.last_reference_label||''))?.[1];return boardImage&&keepImage&&Number(boardImage)<Number(keepImage)?'the '+label+' on the board is image '+boardImage+' (its structure is kept), the picture you keep follows it as image '+keepImage:'image 1 is the picture you keep, a '+label+' on the board follows it as image 2 (and 3)';}
function renderReferenceSlots(){
  const panel=$('#roleReferences');if(!panel)return;
  panel.hidden=!selected?.reference_slots?.length;
  if(panel.hidden)return;
  $('#referenceWrap').hidden=true;
  $('#referenceMode').value=String(selected.reference_slots.length);const modeLabel=$('#referenceMode').parentElement;if(modeLabel)modeLabel.hidden=!!selected.reference_board;
  const note=$('#referenceBoardNote');if(note)note.textContent=selected.reference_board?(selected.reference_board_hint||'Attach one to three pictures whose look you want. Each is read by the image encoder at 224 px (centre crop) and the embeddings are averaged; empty slots are skipped. The output size comes from Width and Height.'):'Give each image a role and describe what to carry over. Every reference is scaled to 1.0 MP with its aspect kept; the output size comes from Width and Height, not from a reference.';
  $('#referenceCards').innerHTML=referenceRecords.map((r,i)=>'<article class="reference-card" data-ref-drop="'+i+'"><div class="section-title"><b>Picture '+(i+1)+'</b><div><button type="button" data-ref-up="'+i+'" '+(!i?'disabled':'')+' aria-label="Move Picture '+(i+1)+' earlier">↑</button><button type="button" data-ref-down="'+i+'" '+(i===referenceRecords.length-1?'disabled':'')+' aria-label="Move Picture '+(i+1)+' later">↓</button><button type="button" data-ref-clear="'+i+'">Clear</button></div></div>'+(selected.reference_board?'':'<label>Role for Picture '+(i+1)+'<select data-ref-role="'+i+'">'+referenceRoles.map(role=>'<option '+(r.role===role?'selected':'')+'>'+role+'</option>').join('')+'</select></label>')+'<label class="reference-drop">'+(r.file&&!r.missing?'<img src="/api/uploads/'+encodeURIComponent(r.file)+'" alt="Picture '+(i+1)+' reference"><span>'+r.width+' × '+r.height+'</span>':'<span>'+(r.missing?'Reference missing. Attach it again.':'Drop or choose an image')+'</span>')+'<input type="file" data-ref-file="'+i+'" accept="image/png,image/jpeg,image/webp" aria-label="Upload Picture '+(i+1)+'"></label>'+(selected.reference_board?'':'<label>Use from Picture '+(i+1)+'<textarea rows="2" data-ref-contribution="'+i+'">'+esc(r.contribution)+'</textarea></label><label>Avoid copying<textarea rows="2" data-ref-avoid="'+i+'">'+esc(r.avoid)+'</textarea></label>')+'</article>').join('');
  const filled=referenceRecords.filter(r=>r.file&&!r.missing).length;
  $('#referenceSummary').textContent=referencePending?'Uploading and validating…':selected.reference_board?(selected.reference_board_label?filled+' / '+referenceRecords.length+' on the board · '+boardSummaryLabel(selected)+' · empty slots are skipped · output size follows width and height':filled+' / '+referenceRecords.length+' style pictures on the board · the adapter blends them; empty slots are skipped · output size follows width and height'):filled+' / '+referenceRecords.length+' attached · each scaled to 1.0 MP; output size follows width and height';
  updateReady();
}
async function uploadRoleFile(index,file){
  if(!file)return;const epoch=referenceEpoch;
  referencePending++;updateReady();$('#referenceSummary').textContent='Uploading and validating…';
  try{
    if(file.size>20*1024*1024)throw Error('Reference image exceeds 20 MiB');
    const result=await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file});
    if(epoch===referenceEpoch){const previous=referenceRecords[index].parent_asset;Object.assign(referenceRecords[index],{parent_asset:null},result,{missing:false});releaseParentAsset(previous);}
  }catch(e){message(e.message,true);$('#referenceSummary').textContent=e.message;}
  finally{if(epoch===referenceEpoch){referencePending--;renderReferenceSlots();}else{$('#referenceSummary').textContent='The slot changed while that image was uploading; it was not attached. Drop it again.';}}
}
async function restoreReferenceSlots(records){
  if(!selected?.reference_slots?.length)return;
  if(Array.isArray(records)&&records.length===selected.reference_slots.length)referenceRecords=records.map(r=>({...r}));
  const epoch=referenceEpoch;referencePending++;renderReferenceSlots();
  try{
    const status=await post('/api/references/check',{files:referenceRecords.filter(r=>r.file).map(r=>r.file)});
    if(epoch!==referenceEpoch)return;
    for(const ref of referenceRecords){const found=status.find(r=>r.file===ref.file);ref.missing=!!ref.file&&(!found?.available||(ref.sha256&&ref.sha256!==found.sha256));}
    if(referenceRecords.some(r=>r.missing))message('A saved reference is missing or changed. Reattach it; the recipe and other references remain loaded.',true);
  }catch(e){if(epoch===referenceEpoch){referenceRecords.forEach(r=>r.missing=true);message(e.message,true);}}
  finally{if(epoch===referenceEpoch){referencePending--;renderReferenceSlots();}}
}
function attachedReferencePayload(){return selected?.reference_slots?.length?referenceRecords.map(r=>({...r})):[];}
$('#referenceMode').onchange=e=>{
  const previous=referenceRecords.map(r=>({...r})),parents=[...parentAssets],inputs={...parentByInput},controls=values();
  selectPreset('qwen-'+e.target.value+'ref');parentAssets=parents;parentByInput=inputs;
  for(const [key,value] of Object.entries(controls)){
    if(key==='positive'||key==='negative')$('#'+key).value=value;
    else{const input=getControl(key);if(input)input.value=value;}
  }
  referenceRecords=referenceRecords.map((r,i)=>previous[i]||r);
  for(const dropped of previous.slice(referenceRecords.length))releaseParentAsset(dropped.parent_asset);
  renderReferenceSlots();
};
$('#referenceCards').addEventListener('change',e=>{
  const d=e.target.dataset;
  if(d.refFile!==undefined){uploadRoleFile(Number(d.refFile),e.target.files[0]);return;}
  for(const [key,field] of [['refRole','role'],['refContribution','contribution'],['refAvoid','avoid']])if(d[key]!==undefined)referenceRecords[Number(d[key])][field]=e.target.value;
});
$('#referenceCards').addEventListener('input',e=>{for(const [key,field] of [['refContribution','contribution'],['refAvoid','avoid']])if(e.target.dataset[key]!==undefined)referenceRecords[Number(e.target.dataset[key])][field]=e.target.value;});
$('#referenceCards').onclick=e=>{
  const up=e.target.closest('[data-ref-up]'),down=e.target.closest('[data-ref-down]'),clear=e.target.closest('[data-ref-clear]');
  if(!up&&!down&&!clear)return;
  referenceEpoch++;referencePending=0;
  if(clear){const i=Number(clear.dataset.refClear),previous=referenceRecords[i].parent_asset;referenceRecords[i]={...referenceRecords[i],file:null,parent_asset:null,missing:false};releaseParentAsset(previous);}
  else{const i=Number((up||down).dataset[up?'refUp':'refDown']),j=i+(up?-1:1);[referenceRecords[i],referenceRecords[j]]=[referenceRecords[j],referenceRecords[i]];}
  renderReferenceSlots();
};
$('#referenceCards').ondragover=e=>{e.preventDefault();};
$('#referenceCards').ondrop=e=>{e.preventDefault();const card=e.target.closest('[data-ref-drop]');if(card)uploadRoleFile(Number(card.dataset.refDrop),e.dataTransfer.files[0]);};
$('#previewResolvedRecipe').onclick=async()=>{
  try{const result=await post('/api/preview',{preset_id:selected.id,...continuationPayload(),controls:values(),references:attachedReferencePayload(),parent_assets:parentAssets,batch_count:$('#batch').value});$('#graphPreview').textContent=JSON.stringify(result,null,2);$('#graphPreview').closest('details').open=true;message('Resolved recipe previewed. No generation submitted.');}
  catch(e){message(e.message,true);}
};
