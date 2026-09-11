let productionPlans=[], productionId=null, productionSignature='', productionRefreshing=false;
let comparisonRecipe=null, comparisonParent=null, nativeAssets=[], blindComparison=true;
const productionMessage=(text,error=false)=>{$('#productionMessage').textContent=text;$('#productionMessage').classList.toggle('error',error);};
async function refreshProduction(force=false){
  if(productionRefreshing)return;productionRefreshing=true;
  try{const plans=await api('/api/production'),signature=JSON.stringify(plans);productionPlans=plans;
    if(!productionId&&plans.length)productionId=plans[0].id;
    if(force||signature!==productionSignature){productionSignature=signature;renderProduction();}
  }catch(e){productionMessage(e.message,true);}finally{productionRefreshing=false;}
}
function renderProduction(){
  $('#productionList').innerHTML=productionPlans.map(p=>'<button class="production-plan '+(p.id===productionId?'chosen':'')+'" data-project="'+p.id+'"><b>'+esc(p.name)+'</b><small>'+esc(p.state.status.replaceAll('_',' '))+' · '+(p.kind==='comparison'?p.stages.length+' candidates':'native export')+'</small></button>').join('')||'<p class="muted">Your next study starts with a question. Open a recipe and plan a comparison.</p>';
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  const active=['queued','running','observing'].includes(p.state.status),resumable=['interrupted','uncertain','stopped'].includes(p.state.status);
  let html='<div class="section-title"><div><span class="eyebrow">'+esc(p.kind)+'</span><h2>'+esc(p.name)+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p><div class="production-actions">'+(p.state.status==='planned'?'<button class="primary" data-project-action="start">Start '+(p.kind==='comparison'?'comparison':'export')+'</button>':'')+(active?'<button data-project-action="stop">Stop after current stage</button>':'')+(resumable?'<button data-project-action="resume">Reconcile and resume</button>':'')+(p.kind==='comparison'?'<button data-project-action="branch">Branch this study</button>':'')+'<a href="/api/production/'+p.id+'/files/plan.json?download" download>Full plan</a></div>';
  if(p.kind==='comparison'){
    html+='<p class="muted">'+p.budget.reserved+' of '+p.budget.allowance+' graph runs reserved across this study and its branches. Uncertain attempts keep their reservation. No automatic repair runs.</p><label class="blind-toggle"><input id="blindComparison" type="checkbox" '+(blindComparison?'checked':'')+'> Hide settings while comparing</label><div class="candidate-grid">';
    for(const s of p.stages){const j=s.job,images=(j?.outputs||[]).filter(o=>o.asset_id);
      html+='<article class="candidate"><h3>Candidate '+esc(s.label)+'</h3>'+(blindComparison?'':'<small>'+esc(p.axis)+' '+esc(p.values[p.stages.indexOf(s)])+'</small>')+'<p class="muted">'+esc(j?.status||'not started')+(j?.elapsed_seconds?' · '+j.elapsed_seconds.toFixed(1)+' s':'')+'</p>';
      for(const o of images){const url='/api/assets/'+o.asset_id+'/file';html+=o.media_type==='image'?'<button class="candidate-image" data-candidate-open="'+o.asset_id+'"><img src="'+url+'" alt="Candidate '+esc(s.label)+'"></button>':o.media_type==='video'?'<video src="'+url+'" controls preload="metadata"></video>':'<a href="'+url+'" download>Download '+esc(o.media_type)+'</a>';
        if(['awaiting_review','reviewed'].includes(p.state.status))html+='<button data-choose-candidate="'+o.asset_id+'">Choose '+esc(s.label)+'</button>';
      }
      if(j)html+='<details><summary>Execution record</summary><small>'+esc(j.message)+'</small><p>'+esc((j.prompt_ids||[]).join(', '))+'</p><button data-job-recipe="'+j.id+'">Recipe</button></details>';
      html+='</article>';
    }
    html+='</div>';
    if(['awaiting_review','reviewed'].includes(p.state.status))html+='<label>Review notes<textarea id="productionNotes" rows="3" placeholder="Identity, pose, silhouette, linework… What should the next pass address?">'+esc(p.state.review?.notes||'')+'</textarea></label><button data-project-action="needs_work">Needs another pass</button><p class="muted">Your choice records creative preference. Model terms and engine acceptance are separate.</p>';
  }else if(p.state.measurements)html+='<p>'+p.state.measurements.image_count+' images · '+p.state.measurements.canvas.join(' × ')+' · anchor '+p.state.measurements.anchor.join(', ')+'</p><p>Frame durations: '+p.state.measurements.durations_ms.join(' / ')+' ms</p>';
  const artifacts=p.state.artifacts||[],pack=artifacts.find(a=>a.path==='export.zip');
  if(pack)html+='<p><a class="primary artifact-download" href="'+pack.url+'?download" download>Download native source pack</a></p>';
  for(const a of artifacts.filter(a=>a.role==='comparison'||a.path==='native/atlas/atlas.png'))html+='<img class="comparison-sheet" src="'+a.url+'" alt="'+esc(a.role==='comparison'?'Candidate contact sheet':'Sprite atlas')+'">';
  if(p.state.engine)html+='<p class="callout">Godot import and timed playback verified for this export.</p>';
  if(artifacts.length)html+='<details><summary>Files & provenance · '+artifacts.length+'</summary><div class="artifact-files">'+artifacts.map(a=>'<a href="'+a.url+'?download" download>'+esc(a.path)+'</a>').join('')+'</div></details>';
  $('#productionDetail').innerHTML=html;
}
async function openComparison(parent=null){
  if(!selected)return;comparisonParent=parent;
  uploaded=(await uploadInput('reference'))||uploaded;lastUploaded=(await uploadInput('lastReference'))||lastUploaded;
  comparisonRecipe={preset_id:selected.id,controls:values(),references:attachedReferencePayload(),parent_assets:[...parentAssets],expected_template_sha256:recipeTemplateHash};
  const axes=[['seed','Seed'],['lora','LoRA strength'],['cfg','Guidance'],['steps','Steps'],['denoise','Denoise']].filter(([key])=>selected[key]&&!(key==='lora'&&typeof selected.defaults?.lora==='string'));
  if(!axes.length){message('This recipe has no numeric comparison controls. Use its Generate action or choose another recipe.',true);return;}
  $('#experimentRecipe').textContent=selected.name;$('#experimentName').value=parent?'Branch · '+parent.name:selected.name+' · comparison';
  $('#experimentAxis').innerHTML=axes.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join('');
  $('#experimentBudget').disabled=!!parent;$('#experimentBudget').value=parent?.budget.allowance||4;
  $('#experimentStatus').textContent=parent?'This branch shares the original budget.':'Preparing a plan validates the live graph and fingerprints its model files. It does not generate.';
  suggestComparisonValues();$('#experimentDialog').showModal();
}
function suggestComparisonValues(){const axis=$('#experimentAxis').value,value=Number(comparisonRecipe?.controls?.[axis]??selected.defaults?.[axis]??1);$('#experimentValues').value=(axis==='seed'?[value,value+1,value+2]:axis==='steps'?[Math.max(1,value-2),value,value+2]:[Math.max(0,value*0.7),value,value*1.2]).map(v=>Number(v.toFixed(3))).join(', ');}
$('#experimentAxis').onchange=suggestComparisonValues;$('#cancelExperiment').onclick=()=>$('#experimentDialog').close();
$('#newExperiment').onclick=()=>openComparison().catch(e=>productionMessage(e.message,true));
$('#planComparison').onclick=()=>openComparison().catch(e=>message(e.message,true));
$('#refreshProduction').onclick=()=>refreshProduction(true);
$('#experimentForm').onsubmit=async e=>{e.preventDefault();$('#prepareExperiment').disabled=true;$('#experimentStatus').textContent='Checking the recipe and local model fingerprints…';try{
  const p=await post('/api/production',{name:$('#experimentName').value,recipe:comparisonRecipe,axis:$('#experimentAxis').value,values:$('#experimentValues').value.split(',').map(v=>v.trim()).filter(Boolean),max_generations:Number($('#experimentBudget').value),max_seconds:Number($('#experimentMinutes').value)*60,parent_project:comparisonParent?.id});
  productionId=p.id;$('#experimentDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#experimentStatus').textContent=err.message;}finally{$('#prepareExperiment').disabled=false;}};
$('#productionList').onclick=e=>{const p=e.target.closest('[data-project]');if(p){productionId=p.dataset.project;renderProduction();}};
$('#productionDetail').onchange=e=>{if(e.target.id==='blindComparison'){blindComparison=e.target.checked;renderProduction();}};
$('#productionDetail').onclick=async e=>{try{
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  const action=e.target.closest('[data-project-action]')?.dataset.projectAction;
  const choice=e.target.closest('[data-choose-candidate]')?.dataset.chooseCandidate;
  const open=e.target.closest('[data-candidate-open]')?.dataset.candidateOpen;
  const recipe=e.target.closest('[data-job-recipe]')?.dataset.jobRecipe;
  if(open){await refreshAssets();openAsset(open);return;}if(recipe){await exportRecipe(recipe);return;}
  if(action==='branch'){applySaved({preset:p.recipe.preset_id,controls:p.recipe.controls,references:p.recipe.references,parent_assets:p.recipe.parent_assets});await openComparison(p);return;}
  if(choice||action==='needs_work')await post('/api/production/'+p.id+'/review',{asset_id:choice||null,notes:$('#productionNotes').value,reviewer:'local-user'});
  else if(['start','stop','resume'].includes(action))await post('/api/production/'+p.id+'/'+action,{});
  if(action||choice)await refreshProduction(true);
}catch(err){productionMessage(err.message,true);}};
function renderNativeAssets(){
  $('#nativeAssetList').innerHTML=nativeAssets.map((a,i)=>'<div class="native-source"><span>'+esc(a.title)+'</span><button type="button" data-native-up="'+i+'" '+(!i?'disabled':'')+' aria-label="Move source '+(i+1)+' earlier">↑</button><button type="button" data-native-down="'+i+'" '+(i===nativeAssets.length-1?'disabled':'')+' aria-label="Move source '+(i+1)+' later">↓</button>'+(a.media_type==='image'?'<label>Duration ms<input type="number" min="1" max="60000" data-native-duration="'+a.id+'" value="'+a.duration+'"></label><label>Layer name<input data-native-layer="'+a.id+'" value="'+esc(a.layerName)+'"></label>':'<small>Optional GLB</small>')+'</div>').join('');
}
$('#nativeExport').onclick=()=>{nativeAssets=[...assetSelection].map(id=>assetState.assets.find(a=>a.id===id)).filter(Boolean).map(a=>({...a,duration:100,layerName:a.title}));if(!nativeAssets.length){assetMessage('Select the source images first.',true);return;}$('#nativeStatus').textContent='Prepare the export, then start it from Experiments.';renderNativeAssets();$('#nativeDialog').showModal();};
$('#cancelNative').onclick=()=>$('#nativeDialog').close();$('#nativeKind').onchange=()=>$('#nativeEngineWrap').hidden=$('#nativeKind').value!=='godot';
$('#nativeAssetList').onchange=e=>{const id=e.target.dataset.nativeDuration||e.target.dataset.nativeLayer,a=nativeAssets.find(a=>a.id===id);if(a)a[e.target.dataset.nativeDuration?'duration':'layerName']=e.target.dataset.nativeDuration?Number(e.target.value):e.target.value;};
$('#nativeAssetList').onclick=e=>{const up=e.target.closest('[data-native-up]'),down=e.target.closest('[data-native-down]');if(!up&&!down)return;const i=Number((up||down).dataset[up?'nativeUp':'nativeDown']),j=i+(up?-1:1);[nativeAssets[i],nativeAssets[j]]=[nativeAssets[j],nativeAssets[i]];renderNativeAssets();};
$('#nativeForm').onsubmit=async e=>{e.preventDefault();$('#prepareNative').disabled=true;try{
  const images=nativeAssets.filter(a=>a.media_type==='image'),kind=$('#nativeKind').value,options={clip:$('#nativeClip').value,duration_ms:images.map(a=>a.duration),layer_names:images.map(a=>a.layerName),loop:$('#nativeLoop').checked,filter:$('#nativeFilter').value};
  const x=$('#nativeAnchorX').value,y=$('#nativeAnchorY').value;if(x!==''||y!==''){if(x===''||y==='')throw Error('Set both anchor coordinates, or leave both automatic.');options.anchor=[Number(x),Number(y)];}
  const p=await post('/api/production-export',{kind,ids:nativeAssets.map(a=>a.id),options,verify_engine:kind==='godot'&&$('#nativeEngine').checked});productionId=p.id;$('#nativeDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#nativeStatus').textContent=err.message;}finally{$('#prepareNative').disabled=false;}};
