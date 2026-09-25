let productionPlans=[], productionId=null, productionSignature='', productionRefreshing=false, productionActionPending=false;
let comparisonRecipe=null, comparisonParent=null, nativeAssets=[], blindComparison=true;
let plannedVariants=null, plannerAxes=[], plannerAxisIds=[];
let plannerWithheld=[], plannerNotice='', plannerRequestId=0;
// Stored plan names are identity: the plan file, its fingerprint and every
// receipt keep the name a study was created with.  These helpers only make the
// list and the detail header readable, and never write a name back.
const PRODUCTION_EMPTY='<div class="production-empty"><p><b>Nothing here yet.</b> Compare one change at a time across a few candidates, start explicitly, review blind, keep a winner.</p><p class="muted">You get here by planning a comparison from a recipe in Create, by branching a finished study, or by preparing an export, scene or voice job.</p><button class="primary" data-production-plan>Plan a comparison</button></div>';
function planDate(value){
  const seconds=Number(value);if(!Number.isFinite(seconds)||seconds<=0)return '';
  try{return new Date(seconds*1000).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});}catch(e){return '';}
}
function planDisplayName(p){
  const stored=String(p?.name||'').trim();
  const readable=stored.replace(/\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,}\b/gi,'').replace(/\s{2,}/g,' ').replace(/[\s·\/,-]+$/,'').trim()||stored||'Untitled plan';
  if(p?.kind!=='comparison')return readable;
  const values=p.values||[];
  const change=p.axis==='variants'?(values.length?values.length+' planned variants':''):p.axis&&values.length?p.axis+' = '+values.join(', '):'';
  return [readable,change,planDate(p.created_at)].filter(Boolean).join(' · ');
}
const productionMessage=(text,error=false)=>{$('#productionMessage').textContent=text;$('#productionMessage').classList.toggle('error',error);};
async function refreshProduction(force=false){
  if(productionRefreshing)return;productionRefreshing=true;
  try{const plans=await api('/api/production'),signature=JSON.stringify(plans);productionPlans=plans;
    if(!productionId&&plans.length)productionId=plans[0].id;
    if(force||signature!==productionSignature){productionSignature=signature;renderProduction();}
  }catch(e){productionMessage(e.message,true);}finally{productionRefreshing=false;}
}
// Your plans filters (#940): presentation over the list already fetched. They never
// start, stop, re-read or change a plan; a hidden plan keeps its detail and records.
const PLAN_FILTER_KEY='studio.production.filters',PLAN_RECENT_SECONDS=7*86400;
const PLAN_TYPES={all:null,comparison:['comparison'],scene:['av'],voice:['voice'],export:['native','articulated']};
const PLAN_TYPE_NOUNS={all:'plans',comparison:'comparisons',scene:'scenes',voice:'voice takes',export:'exports'};
// Open work = StudioUX ACTIVE ∪ ATTENTION (studio-core.js, one source of truth) plus the two plan states that
// wait on the owner. studio-core loads after this file, so it is read per render; the literal mirrors it for
// pages and tests without it. A Studio restart turns running plans into `interrupted`, which must stay in view.
const PLAN_OPEN_FALLBACK=['queued','submitting','running','waiting','observing','rendering','failed','partial','uncertain','interrupted','stopped'];
function planOpenStatuses(){const ux=globalThis.StudioUX,core=Array.isArray(ux?.ACTIVE)&&Array.isArray(ux?.ATTENTION)?[...ux.ACTIVE,...ux.ATTENTION]:PLAN_OPEN_FALLBACK;return new Set([...core,'planned','awaiting_review']);}
let planFilter={type:'all',status:'active'};
function cleanPlanFilter(value){return {type:Object.hasOwn(PLAN_TYPES,value?.type)?value.type:'all',status:value?.status==='all'?'all':'active'};}
// The newest thing known about a plan: its creation, its own run (voice, scene and export plans have
// no stages), its attempts, its stage jobs and its review.
function planActivity(p){const stamps=r=>[r?.created_at,r?.started_at,r?.finished_at,r?.at],state=p?.state||{};
  const known=[p?.created_at,state.started_at,state.finished_at,state.review?.at,...Object.values(state.attempts&&typeof state.attempts==='object'?state.attempts:{}).flatMap(stamps),...(p?.stages||[]).flatMap(s=>stamps(s?.job))].map(Number).filter(t=>Number.isFinite(t)&&t>0);return known.length?Math.max(...known):null;}
function planGroups(plans,filter=planFilter,now=Date.now()/1000){
  const kinds=PLAN_TYPES[filter.type],typed=plans.filter(p=>!kinds||kinds.includes(p.kind));
  if(filter.status==='all')return {recent:typed,older:[],hidden:plans.length-typed.length};
  const open=planOpenStatuses(),recent=[],older=[],active=typed.filter(p=>open.has(p.state?.status));
  // A plan with no readable date cannot be shown to be old, so it stays in view.
  for(const p of active){const at=planActivity(p);(at!==null&&now-at>PLAN_RECENT_SECONDS?older:recent).push(p);}
  return {recent,older,hidden:plans.length-active.length};
}
function planFilterPhrase(filter=planFilter){return PLAN_TYPE_NOUNS[filter.type]+(filter.status==='active'?' in progress or needing attention':'');}
function syncPlanFilter(){const type=$('#planType'),status=$('#planStatus');if(type)type.value=planFilter.type;if(status)status.value=planFilter.status;}
function setPlanFilter(next,focus=false){planFilter=cleanPlanFilter({...planFilter,...next});syncPlanFilter();try{localStorage.setItem(PLAN_FILTER_KEY,JSON.stringify(planFilter));}catch(err){}renderProduction();
  // Show all lives inside the list it re-renders; hand keyboard focus to the Status select instead of losing it.
  if(focus)$('#planStatus')?.focus?.();}
function restorePlanFilter(){try{planFilter=cleanPlanFilter(JSON.parse(localStorage.getItem(PLAN_FILTER_KEY)||'{}'));}catch(err){}syncPlanFilter();}
function planButton(p){return '<button class="production-plan '+(p.id===productionId?'chosen':'')+'" data-project="'+p.id+'" title="'+esc(p.name)+'"><b>'+esc(planDisplayName(p))+'</b><small>'+esc(String(p.state?.status||'').replaceAll('_',' '))+' · '+(p.kind==='comparison'?(p.stages||[]).length+' candidates':p.kind==='av'?'scene':p.kind==='voice'?'voice take':'native export')+'</small></button>';}
function renderPlanList(){
  const list=$('#productionList');if(!productionPlans.length){list.innerHTML=PRODUCTION_EMPTY;return;}
  const groups=planGroups(productionPlans),shown=groups.recent.length+groups.older.length,showAll='<button data-plan-show-all>Show all</button>';
  const olderOpen=list.querySelector?.('.plan-older')?.open||groups.older.some(p=>p.id===productionId);
  const hidden=groups.hidden+' '+(groups.hidden===1?'plan':'plans')+' hidden by these filters.';
  if(!shown){list.innerHTML='<div class="production-empty plan-filter-empty"><p><b>No '+esc(planFilterPhrase())+'.</b> '+hidden+'</p>'+showAll+'</div>';return;}
  list.innerHTML=groups.recent.map(planButton).join('')+(groups.older.length?'<details class="plan-older"'+(olderOpen?' open':'')+'><summary>Older ('+groups.older.length+')</summary>'+groups.older.map(planButton).join('')+'</details>':'')+(groups.hidden?'<p class="plan-filter-note">Showing '+esc(planFilterPhrase())+(planFilter.status==='active'?'; untouched for 7 days folds under Older':'')+'. '+hidden+' '+showAll+'</p>':'');
}
function renderProduction(){
  renderPlanList();
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  if(p.kind==='av'){
    $('#productionDetail').innerHTML='<div class="section-title"><div><span class="eyebrow">SCENE</span><h2 title="'+esc(p.name)+'">'+esc(planDisplayName(p))+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p><p><a class="primary artifact-download" href="/av.html?project='+encodeURIComponent(p.id)+'">Open Scene editor</a> <span class="muted">Edit sources and timing, then render explicitly from the Scene editor.</span></p>';
    return;
  }
  const terminalReconciliation=p.can_reconcile_tracking===true||p.can_reconcile_batch===true,active=['queued','running','observing'].includes(p.state.status),trackingRecoveryPending=!terminalReconciliation&&(p.stages||[]).some(s=>{const d=s.job?.tracking_disposition;return (d?.status==='stopped'||d?.history?.some(event=>event.status==='stopped'))&&s.job?.status!=='completed';}),resumable=(p.kind==='voice'?p.voice_resume?.eligible===true:['interrupted','uncertain','stopped'].includes(p.state.status));
  const resume=resumable?'<button data-project-action="resume" '+(trackingRecoveryPending?'disabled':'')+'>'+(terminalReconciliation?'Reconcile outcome only':p.kind==='voice'?'Resume unstarted take':'Reconcile and resume')+'</button>':'';
  let html='<div class="section-title"><div><span class="eyebrow">'+esc(p.kind)+'</span><h2 title="'+esc(p.name)+'">'+esc(planDisplayName(p))+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p>'+(terminalReconciliation?'<p class="callout">Record the retained failed/partial outcome or local batch disposition. No retry or later stage will start; repairs require an explicit branch.</p>':'')+(trackingRecoveryPending?'<p class="muted">Resume is unavailable until the retained prompt observation reaches a terminal record. Its execution record and reservation remain available for inspection.</p>':'')+'<div class="production-actions">'+(p.state.status==='planned'?'<button class="primary" data-project-action="start">Start '+(p.kind==='comparison'?'comparison':p.kind==='voice'?'voice take':'export')+'</button>':'')+(active?'<button data-project-action="stop">Stop after current stage</button>':'')+resume+(p.kind==='comparison'?'<button data-project-action="branch">Branch this study</button>':'')+'<a href="/api/production/'+p.id+'/files/plan.json?download" download>Full plan</a></div>';
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
        // Workspace review of one image, through the same guarded update the asset
        // dialog uses.  Blind mode hides settings, never the pictures, so marking a
        // keeper here reveals nothing about which variant produced it.
        if(o.media_type==='image')html+='<div class="candidate-review"><button data-candidate-review="selected" data-candidate-asset="'+o.asset_id+'">Keeper</button><button data-candidate-review="needs_work" data-candidate-asset="'+o.asset_id+'">Needs work</button></div>';
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
  if(!selected)return;++plannerRequestId;comparisonParent=parent;
  uploaded=(await uploadInput('reference'))||uploaded;lastUploaded=(await uploadInput('lastReference'))||lastUploaded;
  comparisonRecipe={preset_id:selected.id,...continuationPayload(),controls:values(),references:attachedReferencePayload(),parent_assets:[...parentAssets],expected_template_sha256:recipeTemplateHash};
  const axes=[['seed','Seed'],['lora','LoRA strength'],['cfg','Guidance'],['steps','Steps'],['denoise','Denoise']].filter(([key])=>selected[key]&&!(key==='lora'&&typeof selected.defaults?.lora==='string'));
  $('#experimentRecipe').textContent=selected.name;$('#experimentName').value=parent?'Branch · '+parent.name:selected.name+' · comparison';
  $('#experimentAxis').innerHTML=axes.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join('')||'<option value="">No single numeric setting on this recipe</option>';
  $('#experimentAxis').disabled=!axes.length;
  $('#experimentBudget').disabled=!!parent;$('#experimentBudget').value=parent?.budget.allowance||4;
  $('#experimentStatus').textContent=parent?'This branch shares the original budget.':'Preparing a plan validates the live graph and fingerprints its model files. It does not generate.';
  plannedVariants=null;plannerAxes=[];plannerAxisIds=[];plannerWithheld=[];plannerNotice='';plannerBlock();renderPlanner();
  if(axes.length)suggestComparisonValues();else $('#experimentValues').value='';
  sizeBudgetToCandidates();
  renderPlannerSummary();
  if(!axes.length)productionMessage('This recipe has no single numeric axis; plan its documented settings instead.');
  $('#experimentDialog').showModal();
}
// The settings library plans several documented settings at once. It reserves
// nothing: the variants it offers still go through the same Prepare plan step.
function plannerBlock(){
  let block=$('#plannerBlock');
  if(!block){
    block=document.createElement('div');block.id='plannerBlock';block.className='planner';
    block.innerHTML='<details id="plannerAdvanced" class="planner-advanced"><summary>Advanced: plan several settings from the library</summary><p class="muted">The settings library holds values documented for this model family. Planning from it replaces the single-setting comparison above and still reserves nothing until you prepare the plan.</p><div class="production-actions"><button type="button" id="inspectSettings">Inspect available settings</button><button type="button" id="planFromKnowledge">Plan from settings library</button><button type="button" id="planRemix">Remix LoRA weights</button><button type="button" id="clearPlanned" hidden>Clear planned variants</button></div><div id="plannerLimits" class="muted" role="status"></div><div id="plannerAxes" class="planner-axes"></div></details><div id="plannedVariants" class="variants"></div>';
    $('#experimentStatus').before(block);
    $('#inspectSettings').onclick=()=>requestPlan('inspect');
    $('#planFromKnowledge').onclick=()=>requestPlan('grid');
    $('#planRemix').onclick=()=>requestPlan('remix');
    $('#clearPlanned').onclick=()=>{++plannerRequestId;plannedVariants=null;renderPlanner();$('#experimentStatus').textContent='Planned variants cleared locally. Nothing was reserved or submitted.';};
    $('#plannerAxes').onchange=()=>{plannerAxisIds=[...$('#plannerAxes').querySelectorAll('input:checked')].map(i=>i.value);requestPlan('grid');};
    $('#plannedVariants').onclick=e=>{const drop=e.target.closest('[data-drop-variant]');if(!drop)return;++plannerRequestId;plannedVariants.splice(Number(drop.dataset.dropVariant),1);if(!plannedVariants.length)plannedVariants=null;renderPlanner();$('#experimentStatus').textContent='Variant removed locally. Nothing was reserved or submitted.';};
  }
  return block;
}
// /api/experiments/plan returns `description` already shaped as
// "label · every setting — rationale".  Printing it next to <b>label</b> and the
// rationale paragraph repeated both, so each card now states every fact once:
// the label, then only the settings this variant actually moves off the recipe.
const PLANNER_PROSE=new Set(['positive','negative']);
function variantChanges(variant,base){
  const controls=variant?.controls||{},from=base||{},label=String(variant?.label||'');
  const stated=key=>new RegExp('(^|[^a-z0-9_])'+String(key+'='+controls[key]).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?![0-9.])','i').test(label);
  return Object.keys(controls).sort().filter(key=>!PLANNER_PROSE.has(key)&&String(controls[key])!==String(from[key]??'')&&!stated(key)).map(key=>key+'='+controls[key]);
}
function renderPlanner(resizeBudget=true){
  const planned=plannedVariants||[];
  $('#plannerLimits').innerHTML=(plannerWithheld.length?'<p><b>Settings unavailable for this recipe</b></p><ul>'+plannerWithheld.map(a=>{const slots=a.accelerator_slots||[];return '<li><b>'+esc(a.id)+'</b>: '+esc(a.message)+(slots.length?' ('+esc(slots.join(', '))+')':'')+'</li>';}).join('')+'</ul>':'')+(plannerNotice?'<p>'+esc(plannerNotice)+'</p>':'');
  $('#plannerAxes').innerHTML=plannerAxes.length?'<small>Settings to vary</small>'+plannerAxes.map(a=>'<label class="planner-axis"><input type="checkbox" value="'+esc(a.id)+'" '+(plannerAxisIds.includes(a.id)?'checked':'')+'> '+esc(a.id)+' · '+esc(a.values.join(', '))+'</label>').join(''):'';
  $('#plannedVariants').innerHTML=planned.map((v,i)=>{const changes=variantChanges(v,comparisonRecipe?.controls);
    return '<article class="planned-variant"><b>'+esc(v.label)+'</b><button type="button" data-drop-variant="'+i+'" aria-label="Remove variant '+esc(v.label)+'">✕</button>'+(changes.length?'<small>'+esc(changes.join(', '))+'</small>':'')+(v.rationale?'<p class="muted">'+esc(v.rationale)+'</p>':'')+(v.sources||[]).map(s=>'<a href="'+safeUrl(s)+'" target="_blank" rel="noreferrer">source ↗</a>').join(' ')+'</article>';}).join('');
  $('#clearPlanned').hidden=!planned.length;
  $('#experimentValues').required=!planned.length;$('#experimentValues').disabled=!!planned.length;
  $('#experimentAxis').disabled=!!planned.length||!$('#experimentAxis').value;
  if(resizeBudget&&planned.length&&!comparisonParent)sizeBudgetToCandidates();
  $('#prepareExperiment').disabled=!planned.length&&!$('#experimentAxis').value;
  if(planned.length&&$('#plannerAdvanced'))$('#plannerAdvanced').open=true;
  renderPlannerSummary();
}
// The Create view already measures this recipe against completed local runs.
// Reading its label back keeps one number in the Studio: no second estimator,
// and no claim at all when Create has not measured this recipe yet.
// Create's estimate covers its whole variation batch; comparison stages run one output each, so the
// batch is divided out (a rough share, not a second estimator) and the label says so.
function measuredRunSeconds(){
  const match=/^([0-9]+(?:\.[0-9]+)?)\s*(s|min|h)$/.exec(String($('#estimateValue')?.textContent||'').trim());
  if(!match)return null;
  const value=Number(match[1]),batch=Math.max(1,Number($('#batch')?.value)||1);
  return Number.isFinite(value)&&value>0?value*({s:1,min:60,h:3600}[match[2]])/batch:null;
}
function estimatePending(){return /calculating/i.test(String($('#estimateValue')?.textContent||''));}
let plannerSummaryRetry=0;
function plannedValues(){return String($('#experimentValues').value||'').split(',').map(v=>v.trim()).filter(Boolean);}
function renderPlannerSummary(){
  const summary=$('#experimentSummary'),note=$('#experimentBudgetNote');
  if(!summary)return;
  const planned=plannedVariants||[],recipe=$('#experimentRecipe').textContent||'this recipe';
  const axis=$('#experimentAxis').value,values=plannedValues(),candidates=planned.length||values.length;
  const reserved=Number($('#experimentBudget').value)||0,per=measuredRunSeconds();
  const what=planned.length?planned.length+' planned variants from the settings library':axis&&values.length?'Compare '+axis+' = '+values.join(', '):'Choose one setting and the values to compare';
  const pending=estimatePending(),batch=Math.max(1,Number($('#batch')?.value)||1);
  const time=!candidates?'':per?', about '+Math.max(1,Math.round(candidates*per/60))+' min at roughly '+(per/60).toFixed(1)+' min per run'+(batch>1?' (Create’s estimate for '+batch+' outputs, shared out)':' measured in Create'):pending?', timing still being measured':', no measured time for this recipe yet';
  summary.textContent=candidates?what+' on '+recipe+' → '+candidates+' graph run'+(candidates===1?'':'s')+time+'.':what+' on '+recipe+'.';
  // The estimator debounces and fetches; a summary opened mid-flight re-reads once it settles.
  if(typeof setTimeout==='function'){clearTimeout(plannerSummaryRetry);if(pending&&$('#experimentDialog')?.open!==false)plannerSummaryRetry=setTimeout(renderPlannerSummary,600);}
  if(note){
    note.textContent=candidates?candidates+(planned.length?' variants':' values')+' × 1 seed = '+candidates+' run'+(candidates===1?'':'s')+'; '+reserved+' reserved. At least '+candidates+' must be reserved to prepare this study.'+(reserved<candidates?' Raise the total to at least '+candidates+'.':''):'';
    note.classList.toggle('error',!!candidates&&reserved<candidates);
  }
  $('#experimentBudget').setCustomValidity?.(candidates&&reserved<candidates?'Reserve at least '+candidates+' graph runs for '+candidates+' candidates.':'');
}
async function requestPlan(mode){
  if(!comparisonRecipe)return;
  const ticket=++plannerRequestId,recipe=comparisonRecipe,snapshot=JSON.stringify(recipe);
  const current=()=>ticket===plannerRequestId&&comparisonRecipe===recipe&&JSON.stringify(recipe)===snapshot&&$('#experimentDialog').open;
  $('#experimentStatus').textContent='Reading the documented settings for this family…';
  try{
    const body={preset_id:recipe.preset_id,controls:recipe.controls,mode};
    if(mode==='grid'&&plannerAxisIds.length)body.axes=[...plannerAxisIds];
    const offer=await post('/api/experiments/plan',body);
    if(!current())return;
    plannerAxes=offer.axes_available||[];plannerWithheld=offer.axes_withheld||[];plannerNotice=offer.notice||'';
    if(mode!=='inspect')plannedVariants=offer.variants||[];
    if(mode==='grid'&&!plannerAxisIds.length)plannerAxisIds=[...new Set(plannedVariants.flatMap(v=>Object.keys(v.controls||{})))].filter(k=>plannerAxes.some(a=>a.control===k)).map(k=>plannerAxes.find(a=>a.control===k).id);
    renderPlanner(mode!=='inspect');
    $('#experimentStatus').textContent=mode==='inspect'?plannerAxes.length+' settings available; '+plannerWithheld.length+' unavailable. Existing variants are unchanged. Nothing was reserved or submitted.':plannedVariants.length+' documented variants planned. Nothing is reserved until you prepare the plan.';
  }catch(err){
    if(!current())return;
    if(mode!=='inspect')plannedVariants=null;
    plannerAxes=[];plannerAxisIds=[];plannerWithheld=[];plannerNotice='';renderPlanner(mode!=='inspect');$('#experimentStatus').textContent=err.message;
  }
}
function suggestComparisonValues(){const axis=$('#experimentAxis').value,value=Number(comparisonRecipe?.controls?.[axis]??selected.defaults?.[axis]??1);$('#experimentValues').value=(axis==='seed'?[value,value+1,value+2]:axis==='steps'?[Math.max(1,value-2),value,value+2]:[Math.max(0,value*0.7),value,value*1.2]).map(v=>Number(v.toFixed(3))).join(', ');}
// The planner must not propose candidates it then refuses to run: the allowance follows its own
// proposal. It only ever rises, so a total the operator raised is never reduced, and a branch that
// shares its parent's budget (a disabled allowance) is left alone (#278 friction 5).
function sizeBudgetToCandidates(){const field=$('#experimentBudget');if(!field||field.disabled)return;const need=(plannedVariants||[]).length||plannedValues().length;if(need>(Number(field.value)||0))field.value=need;}
$('#experimentAxis').onchange=()=>{suggestComparisonValues();sizeBudgetToCandidates();renderPlannerSummary();};$('#cancelExperiment').onclick=()=>{++plannerRequestId;$('#experimentDialog').close();};
$('#experimentValues').oninput=renderPlannerSummary;$('#experimentBudget').oninput=renderPlannerSummary;
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
// The empty state hands the operator the same route the header button uses:
// Create, with the recipe that is already open, then the planner. It starts nothing.
function planFromEmptyState(){
  try{document.dispatchEvent(new CustomEvent('studio:navigate',{detail:'create'}));}catch(err){showView('create');}
  if(typeof selected!=='undefined'&&selected)$('#planComparison')?.click?.();
  else productionMessage('Choose a recipe in Create first, then press Plan comparison.');
}
// Remembering the orientation block is a per-browser convenience; a storage that
// refuses to answer must never stop the view from rendering.
const PRODUCTION_INTRO_KEY='studio.production.intro';
function restoreProductionIntro(){
  const intro=$('#productionIntro');if(!intro)return;
  try{intro.open=localStorage.getItem(PRODUCTION_INTRO_KEY)!=='closed';}catch(err){}
  intro.ontoggle=()=>{try{localStorage.setItem(PRODUCTION_INTRO_KEY,intro.open?'open':'closed');}catch(err){}};
}
restoreProductionIntro();restorePlanFilter();
if($('#planType'))$('#planType').onchange=()=>setPlanFilter({type:$('#planType').value});
if($('#planStatus'))$('#planStatus').onchange=()=>setPlanFilter({status:$('#planStatus').value});
$('#productionList').onclick=e=>{if(e.target.closest('[data-production-plan]')){planFromEmptyState();return;}if(e.target.closest('[data-plan-show-all]')){setPlanFilter({type:'all',status:'all'},true);return;}const p=e.target.closest('[data-project]');if(p){productionId=p.dataset.project;renderProduction();}};
$('#productionDetail').onchange=e=>{if(e.target.id==='blindComparison'){blindComparison=e.target.checked;renderProduction();}};
// Workspace review of a single candidate image: the same revision-guarded
// /api/assets/update command the asset dialog sends, never a new endpoint. It
// records a creative preference only; the comparison's own outcome is untouched.
async function reviewCandidateAsset(id,review){
  if(!id||!['selected','needs_work'].includes(review))return;
  await refreshAssets(true);
  await mutateAssets({ids:[id],action:'edit',review});
  productionMessage((review==='selected'?'Marked as a keeper':'Marked as needing work')+' in your Workspace. The comparison outcome and its reservations are unchanged.');
}
$('#productionDetail').onclick=async e=>{const actionButton=e.target.closest('[data-project-action]'),action=actionButton?.dataset.projectAction,coordinatorAction=['start','stop','resume','extend-time'].includes(action);
  if(coordinatorAction&&productionActionPending)return;
  if(coordinatorAction){productionActionPending=true;actionButton.disabled=true;}
  try{
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  const choice=e.target.closest('[data-choose-candidate]')?.dataset.chooseCandidate;
  const open=e.target.closest('[data-candidate-open]')?.dataset.candidateOpen;
  const recipe=e.target.closest('[data-job-recipe]')?.dataset.jobRecipe;
  const mark=e.target.closest('[data-candidate-review]');
  if(mark){await reviewCandidateAsset(mark.dataset.candidateAsset,mark.dataset.candidateReview);return;}
  if(open){await refreshAssets();openAsset(open);return;}if(recipe){await exportRecipe(recipe);return;}
  if(action==='branch'){applySaved({preset:p.recipe.preset_id,controls:p.recipe.controls,references:p.recipe.references,parent_assets:p.recipe.parent_assets});await openComparison(p);return;}
  if(choice||action==='needs_work')await post('/api/production/'+p.id+'/review',{asset_id:choice||null,notes:$('#productionNotes').value,reviewer:'local-user'});
  else if(action==='extend-time'){
    const seconds=Number($('#extendTimeMinutes').value)*60,reason=$('#extendTimeReason').value.trim();
    if(!Number.isInteger(seconds)||seconds<60||!reason)throw Error('Give at least one whole minute of additional time and a reason.');
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
