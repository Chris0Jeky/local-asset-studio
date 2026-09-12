let referenceRecords=[], referenceEpoch=0, referencePending=0;
const referenceRoles=['identity','pose','style','costume','composition','geometry','motion','mask'];
function resetReferenceSlots(){referenceEpoch++;referencePending=0;referenceRecords=(selected?.reference_slots||[]).map(s=>({role:s.role,contribution:s.contribution,avoid:s.avoid,file:null}));}
function referencesReady(){return !selected?.reference_slots?.length||(!referencePending&&referenceRecords.length===selected.reference_slots.length&&referenceRecords.every(r=>r.file&&!r.missing));}
function renderReferenceSlots(){
  const panel=$('#roleReferences');if(!panel)return;
  panel.hidden=!selected?.reference_slots?.length;
  if(panel.hidden)return;
  $('#referenceWrap').hidden=true;
  $('#referenceMode').value=String(selected.reference_slots.length);
  $('#referenceCards').innerHTML=referenceRecords.map((r,i)=>'<article class="reference-card" data-ref-drop="'+i+'"><div class="section-title"><b>Picture '+(i+1)+'</b><div><button type="button" data-ref-up="'+i+'" '+(!i?'disabled':'')+' aria-label="Move Picture '+(i+1)+' earlier">↑</button><button type="button" data-ref-down="'+i+'" '+(i===referenceRecords.length-1?'disabled':'')+' aria-label="Move Picture '+(i+1)+' later">↓</button><button type="button" data-ref-clear="'+i+'">Clear</button></div></div><label>Role for Picture '+(i+1)+'<select data-ref-role="'+i+'">'+referenceRoles.map(role=>'<option '+(r.role===role?'selected':'')+'>'+role+'</option>').join('')+'</select></label><label class="reference-drop">'+(r.file&&!r.missing?'<img src="/api/uploads/'+encodeURIComponent(r.file)+'" alt="Picture '+(i+1)+' reference"><span>'+r.width+' × '+r.height+'</span>':'<span>'+(r.missing?'Reference missing. Attach it again.':'Drop or choose an image')+'</span>')+'<input type="file" data-ref-file="'+i+'" accept="image/png,image/jpeg,image/webp" aria-label="Upload Picture '+(i+1)+'"></label><label>Use from Picture '+(i+1)+'<textarea rows="2" data-ref-contribution="'+i+'">'+esc(r.contribution)+'</textarea></label><label>Avoid copying<textarea rows="2" data-ref-avoid="'+i+'">'+esc(r.avoid)+'</textarea></label></article>').join('');
  $('#referenceSummary').textContent=referencePending?'Uploading and validating…':referenceRecords.filter(r=>r.file&&!r.missing).length+' / '+referenceRecords.length+' attached · each scaled to 1.0 MP; output size follows width and height';
  updateReady();
}
async function uploadRoleFile(index,file){
  if(!file)return;const epoch=referenceEpoch;
  referencePending++;updateReady();$('#referenceSummary').textContent='Uploading and validating…';
  try{
    if(file.size>20*1024*1024)throw Error('Reference image exceeds 20 MiB');
    const result=await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file});
    if(epoch===referenceEpoch)Object.assign(referenceRecords[index],result,{missing:false});
  }catch(e){message(e.message,true);$('#referenceSummary').textContent=e.message;}
  finally{if(epoch===referenceEpoch){referencePending--;renderReferenceSlots();}}
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
  const previous=referenceRecords.map(r=>({...r})),parents=[...parentAssets],controls=values();
  selectPreset('qwen-'+e.target.value+'ref');parentAssets=parents;
  for(const [key,value] of Object.entries(controls)){
    if(key==='positive'||key==='negative')$('#'+key).value=value;
    else{const input=getControl(key);if(input)input.value=value;}
  }
  referenceRecords=referenceRecords.map((r,i)=>previous[i]||r);renderReferenceSlots();
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
  if(clear){const i=Number(clear.dataset.refClear);referenceRecords[i]={...referenceRecords[i],file:null,missing:false};}
  else{const i=Number((up||down).dataset[up?'refUp':'refDown']),j=i+(up?-1:1);[referenceRecords[i],referenceRecords[j]]=[referenceRecords[j],referenceRecords[i]];}
  renderReferenceSlots();
};
$('#referenceCards').ondragover=e=>{e.preventDefault();};
$('#referenceCards').ondrop=e=>{e.preventDefault();const card=e.target.closest('[data-ref-drop]');if(card)uploadRoleFile(Number(card.dataset.refDrop),e.dataTransfer.files[0]);};
$('#previewResolvedRecipe').onclick=async()=>{
  try{const result=await post('/api/preview',{preset_id:selected.id,controls:values(),references:attachedReferencePayload(),parent_assets:parentAssets,batch_count:$('#batch').value});$('#graphPreview').textContent=JSON.stringify(result,null,2);$('#graphPreview').closest('details').open=true;message('Resolved recipe previewed. No generation submitted.');}
  catch(e){message(e.message,true);}
};
