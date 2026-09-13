let productionPlans=[], productionId=null, productionSignature='', productionRefreshing=false, productionActionPending=false;
let comparisonRecipe=null, comparisonParent=null, nativeAssets=[], blindComparison=true;
let plannedVariants=null, plannerAxes=[], plannerAxisIds=[];
const productionMessage=(text,error=false)=>{$('#productionMessage').textContent=text;$('#productionMessage').classList.toggle('error',error);};
async function refreshProduction(force=false){
  if(productionRefreshing)return;productionRefreshing=true;
  try{const plans=await api('/api/production'),signature=JSON.stringify(plans);productionPlans=plans;
    if(!productionId&&plans.length)productionId=plans[0].id;
    if(force||signature!==productionSignature){productionSignature=signature;renderProduction();}
  }catch(e){productionMessage(e.message,true);}finally{productionRefreshing=false;}
}
function renderProduction(){
  $('#productionList').innerHTML=productionPlans.map(p=>'<button class="production-plan '+(p.id===productionId?'chosen':'')+'" data-project="'+p.id+'"><b>'+esc(p.name)+'</b><small>'+esc(p.state.status.replaceAll('_',' '))+' · '+(p.kind==='comparison'?p.stages.length+' candidates':p.kind==='av'?'scene':p.kind==='voice'?'voice take':'native export')+'</small></button>').join('')||'<p class="muted">Your next study starts with a question. Open a recipe and plan a comparison.</p>';
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  if(p.kind==='av'){
    $('#productionDetail').innerHTML='<div class="section-title"><div><span class="eyebrow">SCENE</span><h2>'+esc(p.name)+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p><p><a class="primary artifact-download" href="/av.html?project='+encodeURIComponent(p.id)+'">Open Scene editor</a> <span class="muted">Edit sources and timing, then render explicitly from the Scene editor.</span></p>';
    return;
  }
  const terminalReconciliation=p.can_reconcile_tracking===true||p.can_reconcile_batch===true,active=['queued','running','observing'].includes(p.state.status),trackingRecoveryPending=!terminalReconciliation&&(p.stages||[]).some(s=>{const d=s.job?.tracking_disposition;return (d?.status==='stopped'||d?.history?.some(event=>event.status==='stopped'))&&s.job?.status!=='completed';}),resumable=(p.kind==='voice'?p.voice_resume?.eligible===true:['interrupted','uncertain','stopped'].includes(p.state.status));
  const resume=resumable?'<button data-project-action="resume" '+(trackingRecoveryPending?'disabled':'')+'>'+(terminalReconciliation?'Reconcile outcome only':p.kind==='voice'?'Resume unstarted take':'Reconcile and resume')+'</button>':'';
  let html='<div class="section-title"><div><span class="eyebrow">'+esc(p.kind)+'</span><h2>'+esc(p.name)+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p>'+(terminalReconciliation?'<p class="callout">Record the retained failed/partial outcome or local batch disposition. No retry or later stage will start; repairs require an explicit branch.</p>':'')+(trackingRecoveryPending?'<p class="muted">Resume is unavailable until the retained prompt observation reaches a terminal record. Its execution record and reservation remain available for inspection.</p>':'')+'<div class="production-actions">'+(p.state.status==='planned'?'<button class="primary" data-project-action="start">Start '+(p.kind==='comparison'?'comparison':p.kind==='voice'?'voice take':'export')+'</button>':'')+(active?'<button data-project-action="stop">Stop after current stage</button>':'')+resume+(p.kind==='comparison'?'<button data-project-action="branch">Branch this study</button>':'')+'<a href="/api/production/'+p.id+'/files/plan.json?download" download>Full plan</a></div>';
  if(p.kind==='comparison'){
    const clock=p.state.time_budget;
    if(clock&&!p.state.time_budget_error){
      const minutes=seconds=>(seconds/60).toFixed(1);
      html+='<p class="muted">Time allowance: '+esc(minutes(clock.measured_seconds))+' min measured'+(clock.unmeasured_seconds?' + '+esc(minutes(clock.unmeasured_seconds))+' min conservatively charged (unmeasured interruption or legacy run)':'')+' / '+esc(minutes(clock.limit_seconds))+' min total. '+esc(minutes(clock.remaining_seconds))+' min remaining at last checkpoint. Stops apply between stages; an active stage may overrun. Offline time is not measured runtime.</p>';
      if(resumable&&!active&&!clock.active&&clock.limit_seconds<=14340)html+='<div class="timeExtension"><label>Additional minutes<input id="extendTimeMinutes" type="number" min="1" max="'+Math.floor((14400-clock.limit_seconds)/60)+'" value="'+Math.min(15,Math.floor((14400-clock.limit_seconds)/60))+'" required></label><label>Reason for extending time<input id="extendTimeReason" maxlength="1000" required></label><button data-project-action="extend-time">Extend time only</button><small>No generation is started and no generation allowance is added. Resume separately.</small></div>';
    }else if(p.state.time_budget_error)html+='<p role="alert">'+esc(p.state.time_budget_error)+'</p>';
    if(['awaiting_review','reviewed','failed'].includes(p.state.status))html+='<p><a class="primary artifact-download" href="/review.html?project='+p.id+'">Open review desk</a> <span class="muted">Stable blind candidates, matched crops, findings and an evidence pack. No generation.</span></p>';
    html+='<p class="muted">'+p.budget.reserved+' of '+p.budget.allowance+' graph runs reserved across this study and its branches. Uncertain attempts keep their reservation. No automatic repair runs.</p><label class="blind-toggle"><input id="blindComparison" type="checkbox" '+(blindComparison?'checked':'')+'> Hide settings while comparing</label><div class="candidate-grid">';
    for(const s of p.stages){const j=s.job,images=(j?.outputs||[]).filter(o=>o.asset_id);
      const index=p.stages.indexOf(s),variant=(p.variants||[])[index];
      html+='<article class="candidate"><h3>Candidate '+esc(s.label)+'</h3>'+(blindComparison?'':'<small>'+esc(variant?variant.label:p.axis+' '+p.values[index])+'</small>'+(variant?.rationale?'<p class="muted">'+esc(variant.rationale)+'</p>':'')+(variant?.sources||[]).map(u=>'<a href="'+safeUrl(u)+'" target="_blank" rel="noreferrer">source ↗</a>').join(' '))+'<p class="muted">'+esc(j?.status||'not started')+(j?.elapsed_seconds?' · '+j.elapsed_seconds.toFixed(1)+' s':'')+'</p>';
      for(const o of images){const url='/api/assets/'+o.asset_id+'/file';html+=o.media_type==='image'?'<button class="candidate-image" data-candidate-open="'+o.asset_id+'"><img src="'+url+'" alt="Candidate '+esc(s.label)+'"></button>':o.media_type==='video'?'<video src="'+url+'" controls preload="metadata"></video>':'<a href="'+url+'" download>Download '+esc(o.media_type)+'</a>';
        if(['awaiting_review','reviewed'].includes(p.state.status)&&!p.state.review?.desk_url)html+='<button data-choose-candidate="'+o.asset_id+'">Choose '+esc(s.label)+'</button>';
      }
      if(j)html+='<details><summary>Execution record</summary><small>'+esc(j.message)+'</small><p>'+esc((j.prompt_ids||[]).join(', '))+'</p>'+(j.tracking_disposition?.status==='stopped'?'<p><b>Tracking stopped</b>: '+esc(j.tracking_disposition.reason)+'</p>':'')+'<button data-job-recipe="'+j.id+'">Recipe</button></details>';
      html+='</article>';
    }
    html+='</div>';
    if(['awaiting_review','reviewed'].includes(p.state.status)&&!p.state.review?.desk_url)html+='<label>Review notes<textarea id="productionNotes" rows="3" placeholder="Identity, pose, silhouette, linework… What should the next pass address?">'+esc(p.state.review?.notes||'')+'</textarea></label><button data-project-action="needs_work">Needs another pass</button><p class="muted">Your choice records creative preference. Model terms and engine acceptance are separate.</p>';
  }else if(p.kind==='native'&&p.state.measurements)html+='<p>'+p.state.measurements.image_count+' images · '+p.state.measurements.canvas.join(' × ')+' · anchor '+p.state.measurements.anchor.join(', ')+'</p><p>Frame durations: '+p.state.measurements.durations_ms.join(' / ')+' ms</p>';
  const artifacts=p.state.artifacts||[],pack=artifacts.find(a=>a.path==='export.zip');
  if(pack)html+='<p><a class="primary artifact-download" href="'+pack.url+'?download" download>Download native source pack</a></p>';
  for(const a of artifacts.filter(a=>a.role==='animated-glb'))html+='<model-viewer class="native-model" camera-controls autoplay animation-name="ChestLidOpenHoldClose" src="'+a.url+'" alt="Articulated chest animation"></model-viewer>';
  for(const a of artifacts.filter(a=>a.role==='inspection-render'))html+='<img class="native-inspection" src="'+a.url+'" alt="'+esc(a.path)+'">';
  for(const a of artifacts.filter(a=>a.role==='comparison'||a.path==='native/atlas/atlas.png'))html+='<img class="comparison-sheet" src="'+a.url+'" alt="'+esc(a.role==='comparison'?'Candidate contact sheet':'Sprite atlas')+'">';
  if(p.state.engine)html+='<p class="callout">Godot import and timed playback verified for this export.</p>';
  if(p.state.krita)html+='<p class="callout">Krita saved and reopened this document. '+p.state.krita.kra.layers.length+' layer records retained.</p><p><a class="artifact-download" href="/api/production/'+p.id+'/files/native/krita/roundtrip.kra?download" download>Download Krita document</a></p><img class="comparison-sheet" src="/api/production/'+p.id+'/files/native/krita/export.png" alt="Image exported from the reopened Krita document">';
  if(artifacts.length)html+='<details><summary>Files & provenance · '+artifacts.length+'</summary><div class="artifact-files">'+artifacts.map(a=>'<a href="'+a.url+'?download" download>'+esc(a.path)+'</a>').join('')+'</div></details>';
  $('#productionDetail').innerHTML=html;
}
async function openComparison(parent=null){
  if(!selected)return;comparisonParent=parent;
  uploaded=(await uploadInput('reference'))||uploaded;lastUploaded=(await uploadInput('lastReference'))||lastUploaded;
  comparisonRecipe={preset_id:selected.id,...continuationPayload(),controls:values(),references:attachedReferencePayload(),parent_assets:[...parentAssets],expected_template_sha256:recipeTemplateHash};
  const axes=[['seed','Seed'],['lora','LoRA strength'],['cfg','Guidance'],['steps','Steps'],['denoise','Denoise']].filter(([key])=>selected[key]&&!(key==='lora'&&typeof selected.defaults?.lora==='string'));
  $('#experimentRecipe').textContent=selected.name;$('#experimentName').value=parent?'Branch · '+parent.name:selected.name+' · comparison';
  $('#experimentAxis').innerHTML=axes.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join('')||'<option value="">No single numeric setting on this recipe</option>';
  $('#experimentAxis').disabled=!axes.length;
  $('#experimentBudget').disabled=!!parent;$('#experimentBudget').value=parent?.budget.allowance||4;
  $('#experimentStatus').textContent=parent?'This branch shares the original budget.':'Preparing a plan validates the live graph and fingerprints its model files. It does not generate.';
  plannedVariants=null;plannerAxes=[];plannerAxisIds=[];plannerBlock();renderPlanner();
  if(axes.length)suggestComparisonValues();else $('#experimentValues').value='';
  if(!axes.length)productionMessage('This recipe has no single numeric axis; plan its documented settings instead.');
  $('#experimentDialog').showModal();
}
// The settings library plans several documented settings at once. It reserves
// nothing: the variants it offers still go through the same Prepare plan step.
function plannerBlock(){
  let block=$('#plannerBlock');
  if(!block){
    block=document.createElement('div');block.id='plannerBlock';block.className='planner';
    block.innerHTML='<div class="production-actions"><button type="button" id="planFromKnowledge">Plan from settings library</button><button type="button" id="planRemix">Remix LoRA weights</button><button type="button" id="clearPlanned" hidden>Clear planned variants</button></div><div id="plannerAxes" class="planner-axes"></div><div id="plannedVariants" class="variants"></div>';
    $('#experimentStatus').before(block);
    $('#planFromKnowledge').onclick=()=>requestPlan('grid');
    $('#planRemix').onclick=()=>requestPlan('remix');
    $('#clearPlanned').onclick=()=>{plannedVariants=null;renderPlanner();};
    $('#plannerAxes').onchange=()=>{plannerAxisIds=[...$('#plannerAxes').querySelectorAll('input:checked')].map(i=>i.value);requestPlan('grid');};
    $('#plannedVariants').onclick=e=>{const drop=e.target.closest('[data-drop-variant]');if(!drop)return;plannedVariants.splice(Number(drop.dataset.dropVariant),1);if(!plannedVariants.length)plannedVariants=null;renderPlanner();};
  }
  return block;
}
function renderPlanner(){
  const planned=plannedVariants||[];
  $('#plannerAxes').innerHTML=plannerAxes.length?'<small>Settings to vary</small>'+plannerAxes.map(a=>'<label class="planner-axis"><input type="checkbox" value="'+esc(a.id)+'" '+(plannerAxisIds.includes(a.id)?'checked':'')+'> '+esc(a.id)+' · '+esc(a.values.join(', '))+'</label>').join(''):'';
  $('#plannedVariants').innerHTML=planned.map((v,i)=>'<article class="planned-variant"><b>'+esc(v.label)+'</b><button type="button" data-drop-variant="'+i+'" aria-label="Remove variant '+esc(v.label)+'">✕</button><small>'+esc(v.description||Object.entries(v.controls||{}).filter(([k])=>k!=='positive'&&k!=='negative').map(([k,val])=>k+'='+val).join(', '))+'</small>'+(v.rationale?'<p class="muted">'+esc(v.rationale)+'</p>':'')+(v.sources||[]).map(s=>'<a href="'+safeUrl(s)+'" target="_blank" rel="noreferrer">source ↗</a>').join(' ')+'</article>').join('');
  $('#clearPlanned').hidden=!planned.length;
  $('#experimentValues').required=!planned.length;$('#experimentValues').disabled=!!planned.length;
  $('#experimentAxis').disabled=!!planned.length||!$('#experimentAxis').value;
  if(planned.length&&!comparisonParent)$('#experimentBudget').value=Math.max(Number($('#experimentBudget').value)||0,planned.length);
  $('#prepareExperiment').disabled=!planned.length&&!$('#experimentAxis').value;
}
async function requestPlan(mode){
  if(!comparisonRecipe)return;
  $('#experimentStatus').textContent='Reading the documented settings for this family…';
  try{
    const body={preset_id:comparisonRecipe.preset_id,controls:comparisonRecipe.controls,mode};
    if(mode==='grid'&&plannerAxisIds.length)body.axes=plannerAxisIds;
    const offer=await post('/api/experiments/plan',body);
    plannerAxes=offer.axes_available||[];plannedVariants=offer.variants||[];
    if(mode==='grid'&&!plannerAxisIds.length)plannerAxisIds=[...new Set(plannedVariants.flatMap(v=>Object.keys(v.controls||{})))].filter(k=>plannerAxes.some(a=>a.control===k)).map(k=>plannerAxes.find(a=>a.control===k).id);
    renderPlanner();
    $('#experimentStatus').textContent=plannedVariants.length+' documented variants planned. Nothing is reserved until you prepare the plan.';
  }catch(err){plannedVariants=null;renderPlanner();$('#experimentStatus').textContent=err.message;}
}
function suggestComparisonValues(){const axis=$('#experimentAxis').value,value=Number(comparisonRecipe?.controls?.[axis]??selected.defaults?.[axis]??1);$('#experimentValues').value=(axis==='seed'?[value,value+1,value+2]:axis==='steps'?[Math.max(1,value-2),value,value+2]:[Math.max(0,value*0.7),value,value*1.2]).map(v=>Number(v.toFixed(3))).join(', ');}
$('#experimentAxis').onchange=suggestComparisonValues;$('#cancelExperiment').onclick=()=>$('#experimentDialog').close();
$('#newExperiment').onclick=()=>openComparison().catch(e=>productionMessage(e.message,true));
$('#planComparison').onclick=()=>openComparison().catch(e=>message(e.message,true));
$('#refreshProduction').onclick=()=>refreshProduction(true);
$('#experimentForm').onsubmit=async e=>{e.preventDefault();$('#prepareExperiment').disabled=true;$('#experimentStatus').textContent='Checking the recipe and local model fingerprints…';try{
  const intent={name:$('#experimentName').value,recipe:comparisonRecipe,max_generations:Number($('#experimentBudget').value),max_seconds:Number($('#experimentMinutes').value)*60,parent_project:comparisonParent?.id};
  if(plannedVariants&&plannedVariants.length)intent.variants=plannedVariants.map(v=>({label:v.label,controls:v.controls,rationale:v.rationale||'',sources:v.sources||[]}));
  else{intent.axis=$('#experimentAxis').value;intent.values=$('#experimentValues').value.split(',').map(v=>v.trim()).filter(Boolean);}
  const p=await post('/api/production',intent);
  productionId=p.id;$('#experimentDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#experimentStatus').textContent=err.message;}finally{$('#prepareExperiment').disabled=false;}};
$('#productionList').onclick=e=>{const p=e.target.closest('[data-project]');if(p){productionId=p.dataset.project;renderProduction();}};
$('#productionDetail').onchange=e=>{if(e.target.id==='blindComparison'){blindComparison=e.target.checked;renderProduction();}};
$('#productionDetail').onclick=async e=>{const actionButton=e.target.closest('[data-project-action]'),action=actionButton?.dataset.projectAction,coordinatorAction=['start','stop','resume','extend-time'].includes(action);
  if(coordinatorAction&&productionActionPending)return;
  if(coordinatorAction){productionActionPending=true;actionButton.disabled=true;}
  try{
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  const choice=e.target.closest('[data-choose-candidate]')?.dataset.chooseCandidate;
  const open=e.target.closest('[data-candidate-open]')?.dataset.candidateOpen;
  const recipe=e.target.closest('[data-job-recipe]')?.dataset.jobRecipe;
  if(open){await refreshAssets();openAsset(open);return;}if(recipe){await exportRecipe(recipe);return;}
  if(action==='branch'){applySaved({preset:p.recipe.preset_id,controls:p.recipe.controls,references:p.recipe.references,parent_assets:p.recipe.parent_assets});await openComparison(p);return;}
  if(choice||action==='needs_work')await post('/api/production/'+p.id+'/review',{asset_id:choice||null,notes:$('#productionNotes').value,reviewer:'local-user'});
  else if(action==='extend-time'){
    const seconds=Number($('#extendTimeMinutes').value)*60,reason=$('#extendTimeReason').value.trim();
    if(!Number.isInteger(seconds)||seconds<60||!reason)throw Error('Give additional time in whole seconds and a reason.');
    await post('/api/production/'+p.id+'/extend-time',{seconds,reason,expected_revision:p.state.time_budget.revision});
  }
  else if(['start','stop','resume'].includes(action))await post('/api/production/'+p.id+'/'+action,{});
  if(action||choice)await refreshProduction(true);
}catch(err){productionMessage(err.message,true);}finally{if(coordinatorAction){productionActionPending=false;actionButton.disabled=false;}}};
function renderNativeAssets(){
  $('#nativeAssetList').innerHTML=nativeAssets.map((a,i)=>'<div class="native-source"><span>'+esc(a.title)+'</span><button type="button" data-native-up="'+i+'" '+(!i?'disabled':'')+' aria-label="Move source '+(i+1)+' earlier">↑</button><button type="button" data-native-down="'+i+'" '+(i===nativeAssets.length-1?'disabled':'')+' aria-label="Move source '+(i+1)+' later">↓</button>'+(a.media_type==='image'?'<label>Duration ms<input type="number" min="1" max="60000" data-native-duration="'+a.id+'" value="'+a.duration+'"></label><label>Layer name<input data-native-layer="'+a.id+'" value="'+esc(a.layerName)+'"></label>':'<small>Optional GLB</small>')+'</div>').join('');
}
$('#nativeExport').onclick=()=>{nativeAssets=[...assetSelection].map(id=>assetState.assets.find(a=>a.id===id)).filter(Boolean).map(a=>({...a,duration:100,layerName:a.title}));if(!nativeAssets.length){assetMessage('Select the source images first.',true);return;}$('#nativeStatus').textContent='Prepare the export, then start it from Experiments.';renderNativeAssets();$('#nativeDialog').showModal();};
$('#cancelNative').onclick=()=>$('#nativeDialog').close();$('#nativeKind').onchange=()=>{$('#nativeEngineWrap').hidden=$('#nativeKind').value!=='godot';$('#nativeKritaWrap').hidden=$('#nativeKind').value!=='ora';};
function readNativeInputs(){
  for(const input of $('#nativeAssetList').querySelectorAll('input')){
    const id=input.dataset.nativeDuration||input.dataset.nativeLayer,a=nativeAssets.find(a=>a.id===id);
    if(a)a[input.dataset.nativeDuration?'duration':'layerName']=input.dataset.nativeDuration?Number(input.value):input.value;
  }
}
$('#nativeAssetList').oninput=readNativeInputs;
$('#nativeAssetList').onclick=e=>{const up=e.target.closest('[data-native-up]'),down=e.target.closest('[data-native-down]');if(!up&&!down)return;const i=Number((up||down).dataset[up?'nativeUp':'nativeDown']),j=i+(up?-1:1);[nativeAssets[i],nativeAssets[j]]=[nativeAssets[j],nativeAssets[i]];renderNativeAssets();};
$('#nativeForm').onsubmit=async e=>{e.preventDefault();$('#prepareNative').disabled=true;try{
  readNativeInputs();
  const images=nativeAssets.filter(a=>a.media_type==='image'),kind=$('#nativeKind').value,options={clip:$('#nativeClip').value,duration_ms:images.map(a=>a.duration),layer_names:images.map(a=>a.layerName),loop:$('#nativeLoop').checked,filter:$('#nativeFilter').value};
  const x=$('#nativeAnchorX').value,y=$('#nativeAnchorY').value;if(x!==''||y!==''){if(x===''||y==='')throw Error('Set both anchor coordinates, or leave both automatic.');options.anchor=[Number(x),Number(y)];}
  const p=await post('/api/production-export',{kind,ids:nativeAssets.map(a=>a.id),options,verify_engine:kind==='godot'&&$('#nativeEngine').checked,verify_krita:kind==='ora'&&$('#nativeKrita').checked});productionId=p.id;$('#nativeDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#nativeStatus').textContent=err.message;}finally{$('#prepareNative').disabled=false;}};

$('#newArticulated').onclick=()=>$('#articulatedDialog').showModal();
$('#cancelArticulated').onclick=()=>$('#articulatedDialog').close();
$('#articulatedForm').onsubmit=async e=>{e.preventDefault();$('#prepareArticulated').disabled=true;try{
  const p=await post('/api/articulated',{name:$('#articulatedName').value,options:{width:Number($('#propWidth').value),depth:Number($('#propDepth').value),body_height:Number($('#propBody').value),lid_height:Number($('#propLid').value)}});
  productionId=p.id;$('#articulatedDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#articulatedStatus').textContent=err.message;}finally{$('#prepareArticulated').disabled=false;}};
