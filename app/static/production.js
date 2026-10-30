let productionPlans=[], productionId=null, productionSignature='', productionRefreshing=false, productionActionPending=false;
let comparisonRecipe=null, comparisonParent=null, nativeAssets=[], blindComparison=true;
let plannedVariants=null, plannerAxes=[], plannerAxisIds=[];
let plannerWithheld=[], plannerNotice='', plannerRequestId=0;
let comparisonPositive=false, comparisonSeed='', comparisonPreparing=false, nativePreparing=false, nativeRequestId=0;
// Stored plan names are identity: the plan file, its fingerprint and every
// receipt keep the name a study was created with.  These helpers only make the
// list and the detail header readable, and never write a name back.
const PRODUCTION_EMPTY='<div class="production-empty"><p>Comparing looks, or one setting such as LoRA strength, at one seed? <a href="/#make">Use Compare in Make</a>: no plan needed.</p><p><b>Nothing here yet.</b> Compare one change at a time across a few candidates, start explicitly, review blind, keep a winner.</p><p class="muted">You get here by planning a comparison from a recipe in Full editor, by branching a finished study, or by preparing an export, scene or voice job.</p></div>';
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
// S7: machine-built study names (Combine and character imports bake the engine,
// the axes and the seeds into the stored name) read as noise in the list. The stored
// name is never rewritten: a machine-like name gets a short human title up front,
// with the full stored name kept in the second line and the title attribute.
// Anything the owner actually named keeps its display name untouched.
function planKindNoun(p){return p?.kind==='comparison'?'Comparison':p?.kind==='av'?'Scene':p?.kind==='voice'?'Voice take':p?.kind==='native'||p?.kind==='articulated'?'Export':String(p?.kind||'Plan');}
// Provenance, not wording: Combine builds its plan name from engines and seeds (the plan carries its combine record); every
// other plan keeps the name it was given, whatever characters it contains (#1415 review).
function planIsMachineName(name,p){return !!(p&&p.combine&&typeof p.combine==='object');}
function planHumanTitle(p){
  const stored=String(p?.name||'').trim();
  if(stored&&!planIsMachineName(stored,p))return planDisplayName(p);
  const count=p?.kind==='comparison'?((p.stages||[]).length+' candidate'+((p.stages||[]).length===1?'':'s')):'',date=planDate(p?.created_at);
  return [planKindNoun(p),count,date].filter(Boolean).join(' · ')||'Untitled plan';
}
function planMachineDetail(p){const stored=String(p?.name||'').trim();return stored&&planIsMachineName(stored,p)?stored:'';}
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
  const open=planOpenStatuses(),recent=[],older=[],active=typed.filter(p=>open.has(p.state?.status)&&p.put_away!==true);
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
// One review entry per awaiting study, once there is a saved candidate to review.
function planReviewNow(p){return p?.state?.status==='awaiting_review'&&(p.stages||[]).some(s=>(s.job?.outputs||[]).some(o=>o.asset_id))?'<a class="primary artifact-download plan-review-now" href="/review.html?project='+p.id+'">Review</a>':'';}
function planButton(p){const machine=planMachineDetail(p);return '<button class="production-plan '+(p.id===productionId?'chosen':'')+'" data-project="'+p.id+'" title="'+esc(p.name)+'"><b>'+esc(planHumanTitle(p))+'</b><small>'+esc(String(p.state?.status||'').replaceAll('_',' '))+' · '+(p.kind==='comparison'?(p.stages||[]).length+' candidates':p.kind==='av'?'scene':p.kind==='voice'?'voice take':'native export')+(p.put_away?' · put away':'')+'</small>'+(machine?'<small class="plan-machine">'+esc(machine)+'</small>':'')+'</button>'+planReviewNow(p);}
// #940: the owner can put a settled plan away. Only its put_away marker changes (server-side Production.put_away);
// nothing is started, stopped, retried or deleted, and a later status change brings it back on its own.
function planPutAway(p){
  if(p.put_away)return '<p class="plan-put-away"><small>Put away '+esc(planDate(p.put_away_at))+'. Its status, stages and files are unchanged; it is off your desk and the in-progress list.</small> '+(p.can_bring_back?'<button data-plan-put-away="false">Bring back</button>':'')+'</p>';
  if(p.can_put_away)return '<p class="plan-put-away"><button data-plan-put-away="true">Put away</button> <small>Takes it off your desk and the in-progress list. Nothing is started, stopped or deleted; Show all still lists it.</small></p>';
  return '';
}
const PLAN_RUNNING=['queued','submitting','running','waiting','observing','rendering'];
// One terse line above the plans: what needs the owner first. Counts follow the
// type filter; older folds the same Older group the list shows. Never submits.
function renderPlanSummary(){
  const el=$('#planSummary');if(!el)return;
  const kinds=PLAN_TYPES[planFilter.type],typed=productionPlans.filter(p=>!kinds||kinds.includes(p.kind)),desk=typed.filter(p=>p.put_away!==true);
  const review=desk.filter(p=>p?.state?.status==='awaiting_review').length,running=desk.filter(p=>PLAN_RUNNING.includes(p?.state?.status)).length,older=planGroups(productionPlans).older.length;
  const parts=[];if(review)parts.push(review+' waiting for your review');if(running)parts.push(running+' running');if(older)parts.push(older+' older');
  el.textContent=[parts.length?parts.join(' · '):(typed.length?typed.length+' '+PLAN_TYPE_NOUNS[planFilter.type]+' · nothing waiting':''),planFilter.status==='active'?'Showing plans in progress or needing attention; untouched for 7 days folds under Older':''].filter(Boolean).join('. ');
}
function renderPlanList(){
  renderPlanSummary();
  const list=$('#productionList');if(!productionPlans.length){list.innerHTML=PRODUCTION_EMPTY;return;}
  const groups=planGroups(productionPlans),shown=groups.recent.length+groups.older.length,showAll='<button data-plan-show-all>Show all</button>';
  const olderOpen=list.querySelector?.('.plan-older')?.open||groups.older.some(p=>p.id===productionId);
  const hidden=groups.hidden+' '+(groups.hidden===1?'plan':'plans')+' hidden by these filters.';
  if(!shown){list.innerHTML='<div class="production-empty plan-filter-empty"><p><b>No '+esc(planFilterPhrase())+'.</b> '+hidden+'</p>'+showAll+'</div>';return;}
  list.innerHTML=groups.recent.map(planButton).join('')+(groups.older.length?'<details class="plan-older"'+(olderOpen?' open':'')+'><summary>Older ('+groups.older.length+')</summary>'+groups.older.map(planButton).join('')+'</details>':'')+(groups.hidden?'<p class="plan-filter-note">Showing '+esc(planFilterPhrase())+(planFilter.status==='active'?'; untouched for 7 days folds under Older':'')+'. '+hidden+' '+showAll+'</p>':'');
}
// Unsent typed values in the plan detail (#772). A poll, Refresh or a filter change rebuilds the whole
// panel, so every field the user typed in is kept per plan and written back with its focus and caret.
// They are dropped only when another plan is shown or the action that sends them succeeds.
let productionDrafts={plan:null,fields:{}},productionDetailPlan=null;
// Drafts belong to the plan actually on screen: productionId can move without a re-render (studio-workbench.js).
// A number box holding a half-typed '-' or '1e' reads as '' (badInput); recording that would blank the field.
function keepProductionDraft(el){if(!el?.id||!productionDetailPlan||!['TEXTAREA','INPUT'].includes(el.tagName)||['checkbox','radio'].includes(el.type)||(el.type==='number'&&el.validity?.badInput))return;
  if(productionDrafts.plan!==productionDetailPlan)productionDrafts={plan:productionDetailPlan,fields:{}};productionDrafts.fields[el.id]=el.value;}
// `sent` maps field ids to the values an action sent; text typed while it was in flight is kept.
function dropProductionDrafts(sent){if(!sent){productionDrafts={plan:null,fields:{}};return;}for(const [id,value] of Object.entries(sent))if(productionDrafts.fields[id]===value)delete productionDrafts.fields[id];}
function writeProductionDetail(plan,html){
  const detail=$('#productionDetail'),active=typeof document!=='undefined'?document.activeElement:null;
  if(productionDrafts.plan!==plan)dropProductionDrafts();
  const focus=active?.id&&detail.contains?.(active)&&productionDetailPlan===plan?{id:active.id,start:active.selectionStart,end:active.selectionEnd,direction:active.selectionDirection,scroll:active.scrollTop}:null;
  const candidateFocus=detail.contains?.(active)&&productionDetailPlan===plan?Object.fromEntries(['candidateCheck','asset','candidateCheckLoad','candidateReview','candidateAsset','candidateOpen','chooseCandidate'].filter(key=>active?.dataset?.[key]!=null).map(key=>[key,active.dataset[key]])):{};
  detail.innerHTML=html;productionDetailPlan=plan;
  for(const [id,value] of Object.entries(productionDrafts.fields)){const el=detail.querySelector?.('#'+id);if(el)el.value=value;}
  const candidates=Object.keys(candidateFocus).length?[...(detail.querySelectorAll?.('[data-candidate-check],[data-candidate-check-load],[data-candidate-review],[data-candidate-open],[data-choose-candidate]')||[])]:[];
  const el=focus&&detail.querySelector?.('#'+focus.id)||candidates.find(button=>Object.entries(candidateFocus).every(([key,value])=>button.dataset[key]===value))||candidates.find(button=>candidateFocus.candidateCheckLoad&&button.dataset.asset===candidateFocus.candidateCheckLoad&&button.dataset.candidateCheck);if(!el)return;
  el.focus?.({preventScroll:true});
  // Number inputs have no caret API and throw on setSelectionRange; focus alone is right for them.
  try{if(typeof focus?.start==='number'&&typeof focus?.end==='number')el.setSelectionRange(focus.start,focus.end,focus.direction||'none');}catch(err){}
  if(typeof focus?.scroll==='number')el.scrollTop=focus.scroll;
}
// Names the file to open for a completed native export.  It reads only recorded artifacts and recorded results; it never claims
// the file was opened, inspected or accepted.  Blender's chest.blend is not an artifact of its own, so its card links the recorded pack.
const NATIVE_ENTRY={ora:{tool:'Krita',path:'native/layers.ora',how:'Krita → File → Open, then choose the downloaded file.'},godot:{tool:'Godot',path:'native/godot/project.godot',how:'Unzip the source pack, then Godot Project Manager → Import → project.godot inside native/godot.'},articulated:{tool:'Blender',path:'export.zip',file:'chest.blend',how:'Unzip the source pack, then Blender → File → Open → chest.blend.'}};
function nativeOpenCard(p,artifacts){
  const entry=NATIVE_ENTRY[p.kind==='articulated'?'articulated':p.export_kind];
  if(!entry||p.state?.status!=='completed')return '';
  const found=artifacts.find(a=>a.path===entry.path),head='<aside class="callout native-open" aria-label="Which file to open">';
  if(!found)return head+'<b>Open this in '+entry.tool+':</b> entry file not recorded for this export.</aside>';
  const name=entry.file||entry.path.split('/').pop(),record=entry.tool==='Krita'?(p.state.krita?'Recorded Krita roundtrip: saved and reopened roundtrip.kra, '+p.state.krita.kra.layers.length+' layer records retained.':'No Krita roundtrip was recorded.'):entry.tool==='Godot'?(p.state.engine?'Recorded Godot check: import and timed playback verified for this export.':'No Godot check was recorded.'):'No Blender check beyond the export run is recorded.';
  return head+'<b>Open this in '+entry.tool+':</b> <a href="'+esc(found.url)+'?download" download>'+esc(name)+'</a>'+(entry.file?' <small>(inside '+esc(found.path)+')</small>':'')+'<br><small>'+esc(entry.how)+'</small><br><small>'+esc(record)+' Studio records no art acceptance.</small></aside>';
}
function renderProduction(){
  renderPlanList();
  const p=productionPlans.find(p=>p.id===productionId);if(!p){const groups=planGroups(productionPlans);writeProductionDetail(null,groups.recent.length+groups.older.length?'<p>Choose a plan on the left. Plans are budgeted, blind comparisons; quick side-by-sides live in Make.</p><p>Native sprite atlases, layered images and Godot projects start from selected Workspace assets.</p>':'<p>No plans yet. <button type="button" data-plan-comparison><b>Plan a comparison</b></button> runs one change across a few candidates and reviews them blind. For a quick side-by-side, use <a href="/#make"><b>Compare looks</b> in Make</a>.</p>');return;}
  if(p.kind==='av'){
    writeProductionDetail(p.id,'<div class="section-title"><div><span class="eyebrow">SCENE</span><h2 title="'+esc(p.name)+'">'+esc(planHumanTitle(p))+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p><p><a class="primary artifact-download" href="/av.html?project='+encodeURIComponent(p.id)+'">Open Scene editor</a> <span class="muted">Edit sources and timing, then render explicitly from the Scene editor.</span></p>'+planPutAway(p));
    return;
  }
  const terminalReconciliation=p.can_reconcile_tracking===true||p.can_reconcile_batch===true,active=['queued','running','observing'].includes(p.state.status),trackingRecoveryPending=!terminalReconciliation&&(p.stages||[]).some(s=>{const d=s.job?.tracking_disposition;return (d?.status==='stopped'||d?.history?.some(event=>event.status==='stopped'))&&s.job?.status!=='completed';}),resumable=(p.kind==='voice'?p.voice_resume?.eligible===true:['interrupted','uncertain','stopped'].includes(p.state.status));
  const resume=resumable?'<button data-project-action="resume" '+(trackingRecoveryPending?'disabled':'')+'>'+(terminalReconciliation?'Reconcile outcome only':p.kind==='voice'?'Resume unstarted take':'Reconcile and resume')+'</button>':'';
  let html='<div class="section-title"><div><span class="eyebrow">'+esc(p.kind)+'</span><h2 title="'+esc(p.name)+'">'+esc(planHumanTitle(p))+'</h2></div><span class="badge">'+esc(p.state.status.replaceAll('_',' '))+'</span></div><p>'+esc(p.state.message)+'</p>'+(terminalReconciliation?'<p class="callout">Record the retained failed/partial outcome or local batch disposition. No retry or later stage will start; repairs require an explicit branch.</p>':'')+(trackingRecoveryPending?'<p class="muted">Resume is unavailable until the retained prompt observation reaches a terminal record. Its execution record and reservation remain available for inspection.</p>':'')+'<div class="production-actions">'+(p.state.status==='planned'?'<button class="primary" data-project-action="start">Start '+(p.kind==='comparison'?'comparison':p.kind==='voice'?'voice take':'export')+'</button>':'')+(active?'<button data-project-action="stop">Stop after current stage</button>':'')+resume+(p.kind==='comparison'&&!p.combine?'<button data-project-action="branch">Branch this study</button>':'')+(p.kind==='comparison'&&blindComparison?'<small class="muted">Full plan hidden while comparing blind. Reveal settings to download it.</small>':'<a href="/api/production/'+p.id+'/files/plan.json?download" download>Full plan</a>')+'</div>';
  if(p.kind==='comparison'){
    const clock=p.state.time_budget;
    if(clock&&!p.state.time_budget_error){
      const minutes=seconds=>(seconds/60).toFixed(1);
      html+='<p class="muted">Time allowance: '+esc(minutes(clock.measured_seconds))+' min measured'+(clock.unmeasured_seconds?' + '+esc(minutes(clock.unmeasured_seconds))+' min conservatively charged (unmeasured interruption or legacy run)':'')+' / '+esc(minutes(clock.limit_seconds))+' min total. '+esc(minutes(clock.remaining_seconds))+' min remaining at last checkpoint. Stops apply between stages; an active stage may overrun. Offline time is not measured runtime.</p>';
      if(resumable&&!active&&!clock.active&&clock.limit_seconds<=14340)html+='<div class="timeExtension"><label>Additional minutes<input id="extendTimeMinutes" type="number" min="1" max="'+Math.floor((14400-clock.limit_seconds)/60)+'" value="'+Math.min(15,Math.floor((14400-clock.limit_seconds)/60))+'" required></label><label>Reason for extending time<input id="extendTimeReason" maxlength="1000" required></label><button data-project-action="extend-time">Extend time only</button><small>No generation is started and no generation allowance is added. Resume separately.</small></div>';
    }else if(p.state.time_budget_error)html+='<p role="alert">'+esc(p.state.time_budget_error)+'</p>';
    if(['reviewed','failed'].includes(p.state.status))html+='<p><a class="primary artifact-download" href="/review.html?project='+p.id+'">Open review desk</a> <span class="muted">Stable blind candidates, matched crops, findings and an evidence pack. No generation.</span></p>';
    html+='<p class="muted">'+p.budget.reserved+' of '+p.budget.allowance+' graph runs reserved across this study and its branches. Uncertain attempts keep their reservation. No automatic repair runs.</p><label class="blind-toggle"><input id="blindComparison" type="checkbox" '+(blindComparison?'checked':'')+'> Hide settings while comparing</label><div class="candidate-grid">';
    for(const s of p.stages){const j=s.job,images=(j?.outputs||[]).filter(o=>o.asset_id);
      const index=p.stages.indexOf(s),variant=(p.variants||[])[index],checked=images.map(o=>candidateCheckAsset(o.asset_id)).filter(Boolean),counted=checked.length?StudioReviewChecks.summary(checked,candidateCheckNames(j)):'';
      html+='<article class="candidate"><h3>Candidate '+esc(s.label)+'</h3>'+(blindComparison?'':'<small>'+esc(variant?variant.label:p.axis+' '+p.values[index])+'</small>'+(variant?.rationale?'<p class="muted">'+esc(variant.rationale)+'</p>':'')+(variant?.sources||[]).map(u=>'<a href="'+safeUrl(u)+'" target="_blank" rel="noreferrer">source ↗</a>').join(' '))+'<p class="muted">'+esc(j?.status||'not started')+(j?.elapsed_seconds?' · '+j.elapsed_seconds.toFixed(1)+' s':'')+'</p>'+(counted?'<p class="muted candidate-check-count">'+esc(counted)+'</p>':'');
      for(const o of images){const url='/api/assets/'+o.asset_id+'/file';html+=o.media_type==='image'?'<button class="candidate-image" data-candidate-open="'+o.asset_id+'"><img src="'+url+'" alt="Candidate '+esc(s.label)+'"></button>':o.media_type==='video'?'<video src="'+url+'" controls preload="metadata" aria-label="Candidate '+esc(s.label)+'"></video>':'<a href="'+url+'" download>Download '+esc(o.media_type)+'</a>';
        if(['awaiting_review','reviewed'].includes(p.state.status)&&!p.state.review?.desk_url){const winner=p.state.review?.asset_id===o.asset_id;html+='<details class="candidate-quick-pick"'+(winner?' open':'')+'><summary>Quick pick</summary><button data-choose-candidate="'+o.asset_id+'">Choose '+esc(s.label)+'</button>'+(winner?'<p role="status">Winner: '+esc(s.label)+' · <button data-candidate-open="'+esc(o.asset_id)+'">Open in Library</button></p>':'')+'</details>';}
        // Workspace review of one image, through the same guarded update the asset
        // dialog uses.  Blind mode hides settings, never the pictures, so marking a
        // keeper here reveals nothing about which variant produced it.
        if(o.media_type==='image')html+='<div class="candidate-review"><button data-candidate-review="selected" data-candidate-asset="'+o.asset_id+'">Keep</button><button data-candidate-review="needs_work" data-candidate-asset="'+o.asset_id+'">Needs work</button></div>';
        // The recipe chooses the checks; only observed Workspace metadata can say whether they have an answer.
        const checkNames=o.media_type==='image'?candidateCheckNames(j):[];
        if(checkNames.length){const asset=candidateCheckAsset(o.asset_id),missing=typeof assetResolved!=='undefined'&&assetResolved.get(o.asset_id)?.state==='missing';
          html+='<div class="candidate-checks" role="group" aria-label="Quick checks for candidate '+esc(s.label)+'">'+(asset?StudioReviewChecks.chipsHTML({tags:asset.tags,names:checkNames,attr:'data-candidate-check',asset:o.asset_id,escape:esc}):'<p class="muted">'+(missing?'Saved checks unavailable: this picture is not in the Library.':'Saved checks not loaded. Read them before answering.')+'</p><button type="button" data-candidate-check-load="'+esc(o.asset_id)+'">'+(missing?'Retry saved checks':'Load saved checks')+'</button>')+'</div>';}
      }
      // The recipe carries the exact settings, so it stays hidden while blind, like the labels, until Reveal.
      if(j)html+='<details><summary>Execution record</summary><small>'+esc(j.message)+'</small><p>'+esc((j.prompt_ids||[]).join(', '))+'</p>'+(j.tracking_disposition?.status==='stopped'?'<p><b>Tracking stopped</b>: '+esc(j.tracking_disposition.reason)+'</p>':'')+(blindComparison?'<small class="muted">Recipe hidden while comparing blind. Reveal settings to see the recipe.</small>':'<button data-job-recipe="'+j.id+'">Recipe</button>')+'</details>';
      html+='</article>';
    }
    html+='</div>';
    if(['awaiting_review','reviewed'].includes(p.state.status)&&!p.state.review?.desk_url)html+='<label>Review notes<textarea id="productionNotes" rows="3" placeholder="Identity, pose, silhouette, linework… What should the next pass address?">'+esc(p.state.review?.notes||'')+'</textarea></label><button data-project-action="needs_work">Needs another pass</button><p class="muted">Your choice records creative preference. Model terms and engine acceptance are separate.</p>';
  }else if(p.kind==='native'&&p.state.measurements)html+='<p>'+p.state.measurements.image_count+' images · '+p.state.measurements.canvas.join(' × ')+' · anchor '+p.state.measurements.anchor.join(', ')+'</p><p>Frame durations: '+p.state.measurements.durations_ms.join(' / ')+' ms</p>';
  const artifacts=p.state.artifacts||[],pack=artifacts.find(a=>a.path==='export.zip');
  if(pack)html+='<p><a class="primary artifact-download" href="'+pack.url+'?download" download>Download native source pack</a></p>';
  html+=nativeOpenCard(p,artifacts);
  for(const a of artifacts.filter(a=>a.role==='animated-glb'))html+='<model-viewer class="native-model" camera-controls autoplay animation-name="ChestLidOpenHoldClose" src="'+a.url+'" alt="Articulated chest animation"></model-viewer>';
  for(const a of artifacts.filter(a=>a.role==='inspection-render'))html+='<img class="native-inspection" src="'+a.url+'" alt="'+esc(a.path)+'">';
  for(const a of artifacts.filter(a=>a.role==='comparison'||a.path==='native/atlas/atlas.png'))html+='<img class="comparison-sheet" src="'+a.url+'" alt="'+esc(a.role==='comparison'?'Candidate contact sheet':'Sprite atlas')+'">';
  if(p.state.engine)html+='<p class="callout">Godot import and timed playback verified for this export.</p>';
  if(p.state.krita)html+='<p class="callout">Krita saved and reopened this document. '+p.state.krita.kra.layers.length+' layer records retained.</p><p><a class="artifact-download" href="/api/production/'+p.id+'/files/native/krita/roundtrip.kra?download" download>Download Krita document</a></p><img class="comparison-sheet" src="/api/production/'+p.id+'/files/native/krita/export.png" alt="Image exported from the reopened Krita document">';
  if(artifacts.length)html+='<details><summary>Files & provenance · '+artifacts.length+'</summary><div class="artifact-files">'+artifacts.map(a=>'<a href="'+a.url+'?download" download>'+esc(a.path)+'</a>').join('')+'</div></details>';
  writeProductionDetail(p.id,html+planPutAway(p));
}
async function openComparison(parent=null){
  if(!selected)return;++plannerRequestId;comparisonParent=parent;
  uploaded=(await uploadInput('reference'))||uploaded;lastUploaded=(await uploadInput('lastReference'))||lastUploaded;
  comparisonRecipe={preset_id:selected.id,...continuationPayload(),controls:values(),references:attachedReferencePayload(),parent_assets:[...parentAssets],expected_template_sha256:recipeTemplateHash};
  comparisonPositive=!!selected.positive;comparisonSeed=selected.seed?String(comparisonRecipe.controls.seed??selected.defaults?.seed??''):'';
  $('#experimentMode').value='setting';$('#experimentWordingA').value=comparisonRecipe.controls.positive||'';$('#experimentWordingB').value='';
  const axes=[['seed','Seed'],['lora','LoRA strength'],['cfg','Guidance'],['steps','Steps'],['denoise','Denoise']].filter(([key])=>selected[key]&&!(key==='lora'&&typeof selected.defaults?.lora==='string'));
  $('#experimentRecipe').textContent=selected.name;$('#experimentName').value=parent?'Branch · '+parent.name:selected.name+' · comparison';
  $('#experimentAxis').innerHTML=axes.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join('')||'<option value="">No single numeric setting on this recipe</option>';
  $('#experimentAxis').disabled=!axes.length;
  $('#experimentBudget').disabled=!!parent;$('#experimentBudget').value=parent?.budget.allowance||1;$('#experimentLimits').open=false;
  $('#experimentStatus').textContent=parent?'This branch shares the original budget.':'Prepare only validates the live graph and fingerprints its model files; Prepare and start also starts the runs.';
  plannedVariants=null;plannerAxes=[];plannerAxisIds=[];plannerWithheld=[];plannerNotice='';plannerBlock();renderPlanner(false);
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
  const wordings=comparingWordings(),planned=wordings?[]:plannedVariants||[];
  $('#experimentSettings').hidden=wordings;$('#experimentWordings').hidden=!wordings;
  $('#plannerBlock').hidden=wordings;$('#experimentDialog').classList.toggle('wording-comparison',wordings);
  for(const id of ['experimentWordingA','experimentWordingB']){$('#'+id).required=wordings;$('#'+id).disabled=!wordings;}
  $('#plannerLimits').innerHTML=(plannerWithheld.length?'<p><b>Settings unavailable for this recipe</b></p><ul>'+plannerWithheld.map(a=>{const slots=a.accelerator_slots||[];return '<li><b>'+esc(a.id)+'</b>: '+esc(a.message)+(slots.length?' ('+esc(slots.join(', '))+')':'')+'</li>';}).join('')+'</ul>':'')+(plannerNotice?'<p>'+esc(plannerNotice)+'</p>':'');
  $('#plannerAxes').innerHTML=plannerAxes.length?'<small>Settings to vary</small>'+plannerAxes.map(a=>'<label class="planner-axis"><input type="checkbox" value="'+esc(a.id)+'" '+(plannerAxisIds.includes(a.id)?'checked':'')+'> '+esc(a.id)+' · '+esc(a.values.join(', '))+'</label>').join(''):'';
  $('#plannedVariants').innerHTML=planned.map((v,i)=>{const changes=variantChanges(v,comparisonRecipe?.controls);
    return '<article class="planned-variant"><b>'+esc(v.label)+'</b><button type="button" data-drop-variant="'+i+'" aria-label="Remove variant '+esc(v.label)+'">✕</button>'+(changes.length?'<small>'+esc(changes.join(', '))+'</small>':'')+(v.rationale?'<p class="muted">'+esc(v.rationale)+'</p>':'')+(v.sources||[]).map(s=>'<a href="'+safeUrl(s)+'" target="_blank" rel="noreferrer">source ↗</a>').join(' ')+'</article>';}).join('');
  $('#clearPlanned').hidden=!planned.length;
  $('#experimentValues').required=!wordings&&!planned.length;$('#experimentValues').disabled=wordings||!!planned.length;
  $('#experimentAxis').disabled=wordings||!!planned.length||!$('#experimentAxis').value;
  if(resizeBudget&&planned.length&&!comparisonParent)sizeBudgetToCandidates();
  for(const id of ['prepareExperiment','prepareExperimentOnly'])$('#'+id).disabled=comparisonPreparing||(wordings?!!wordingProblem():!planned.length&&!$('#experimentAxis').value);
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
function comparingWordings(){return $('#experimentMode').value==='wordings';}
function wordingProblem(){
  if(!comparisonPositive)return 'This recipe has no editable positive wording. Choose a recipe with a positive prompt in Full editor.';
  if(!/^\d+$/.test(comparisonSeed)||BigInt(comparisonSeed)>9223372036854775807n)return 'Set a fixed whole-number seed in Full editor before comparing two wordings.';
  const a=$('#experimentWordingA').value,b=$('#experimentWordingB').value;
  if(!a.trim()||!b.trim())return 'Enter both wordings before preparing the plan.';
  if(a.length>8000||b.length>8000)return 'Each wording must be text up to 8000 characters.';
  if(a.trim()===b.trim())return 'Use two different wordings; these differ only in surrounding space or are identical.';
  const remaining=comparisonParent?comparisonParent.budget.allowance-comparisonParent.budget.reserved:Number($('#experimentBudget').value)||0;
  return remaining<2?'Two wordings need 2 runs; only '+remaining+' remain in this budget.':'';
}
function renderPlannerSummary(){
  const summary=$('#experimentSummary'),note=$('#experimentBudgetNote');
  if(!summary)return;
  const wordings=comparingWordings(),planned=wordings?[]:plannedVariants||[],recipe=$('#experimentRecipe').textContent||'this recipe';
  const axis=$('#experimentAxis').value,values=plannedValues(),candidates=wordings?2:planned.length||values.length;
  const reserved=Number($('#experimentBudget').value)||0,per=measuredRunSeconds();
  $('#experimentLimitsSummary').textContent='Limits: '+reserved+' runs · '+$('#experimentMinutes').value+' min'+(candidates&&reserved<candidates?' · too few runs for '+candidates+' values':'');
  const what=wordings?'Compare two wordings at shared seed '+(comparisonSeed||'(not fixed)'):planned.length?planned.length+' planned variants from the settings library':axis&&values.length?'Compare '+axis+' = '+values.join(', '):'Choose one setting and the values to compare';
  const pending=estimatePending(),batch=Math.max(1,Number($('#batch')?.value)||1);
  const time=!candidates?'':per?', about '+Math.max(1,Math.round(candidates*per/60))+' min at roughly '+(per/60).toFixed(1)+' min per run'+(batch>1?' (Create’s estimate for '+batch+' outputs, shared out)':' measured in Full editor'):pending?', timing still being measured':', no measured time for this recipe yet';
  summary.textContent=candidates?what+' on '+recipe+' → '+candidates+' graph run'+(candidates===1?'':'s')+time+'.':what+' on '+recipe+'.';
  // The estimator debounces and fetches; a summary opened mid-flight re-reads once it settles.
  if(typeof setTimeout==='function'){clearTimeout(plannerSummaryRetry);if(pending&&$('#experimentDialog')?.open!==false)plannerSummaryRetry=setTimeout(renderPlannerSummary,600);}
  if(note){
    note.textContent=wordings?'2 wordings × 1 seed = 2 runs; '+reserved+' total allowance, '+(comparisonParent?.budget.reserved||0)+' already reserved. Both candidates share the recipe, references, negative prompt and other settings. Prepare only saves the plan; Prepare and start also starts it.':candidates?candidates+(planned.length?' variants':' values')+' × 1 seed = '+candidates+' run'+(candidates===1?'':'s')+'; '+reserved+' reserved. At least '+candidates+' must be reserved to prepare this study.'+(reserved<candidates?' Raise the total to at least '+candidates+'.':''):'';
    note.classList.toggle('error',wordings?!!wordingProblem():!!candidates&&reserved<candidates);
  }
  $('#experimentBudget').setCustomValidity?.(candidates&&reserved<candidates?'Reserve at least '+candidates+' graph runs for '+candidates+' candidates.':'');
}
async function requestPlan(mode){
  if(!comparisonRecipe||comparingWordings())return;
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
function sizeBudgetToCandidates(){const field=$('#experimentBudget');if(!field||field.disabled)return;const need=comparingWordings()?2:(plannedVariants||[]).length||plannedValues().length;if(need>(Number(field.value)||0))field.value=need;}
function wordingDraftChanged(){++plannerRequestId;renderPlanner(false);$('#experimentStatus').textContent=comparingWordings()?wordingProblem()||'Only the positive wording changes. Prepare the plan when both texts are ready.':'Your setting comparison is retained. Nothing was submitted.';}
$('#experimentMode').onchange=wordingDraftChanged;
$('#experimentWordingA').oninput=wordingDraftChanged;$('#experimentWordingB').oninput=wordingDraftChanged;
$('#experimentForm').oninput=()=>{++plannerRequestId;if(comparisonPreparing)$('#experimentStatus').textContent='Draft changed. The earlier plan may still be saved, but it will not start.';else if(!comparingWordings())$('#experimentStatus').textContent='Your comparison draft is retained. Prepare the plan when it is ready.';};
$('#experimentDialog').onclose=()=>{++plannerRequestId;};
$('#experimentAxis').onchange=()=>{suggestComparisonValues();sizeBudgetToCandidates();renderPlannerSummary();};$('#cancelExperiment').onclick=()=>{++plannerRequestId;$('#experimentDialog').close();};
$('#experimentMinutes').oninput=renderPlannerSummary;
for(const id of ['experimentBudget','experimentMinutes'])$('#'+id).oninvalid=()=>{$('#experimentLimits').open=true;};
$('#experimentValues').oninput=()=>{sizeBudgetToCandidates();renderPlannerSummary();};$('#experimentBudget').oninput=()=>comparingWordings()?wordingDraftChanged():renderPlannerSummary();
$('#newExperiment').onclick=()=>openComparison().catch(e=>productionMessage(e.message,true));
$('#planComparison').onclick=()=>openComparison().catch(e=>message(e.message,true));
$('#refreshProduction').onclick=()=>refreshProduction(true);
$('#experimentForm').onsubmit=async e=>{e.preventDefault();if(comparisonPreparing||productionActionPending)return;
  if(comparingWordings()&&wordingProblem()){$('#experimentStatus').textContent=wordingProblem();return;}
  const start=e.submitter?.id==='prepareExperiment',ticket=++plannerRequestId,recipe=comparisonRecipe,current=()=>ticket===plannerRequestId&&comparisonRecipe===recipe&&$('#experimentDialog').open;
  comparisonPreparing=true;$('#prepareExperiment').disabled=true;$('#prepareExperimentOnly').disabled=true;$('#experimentStatus').textContent='Checking the recipe and local model fingerprints…';try{
  const intent={name:$('#experimentName').value,recipe:comparisonRecipe,max_generations:Number($('#experimentBudget').value),max_seconds:Number($('#experimentMinutes').value)*60,parent_project:comparisonParent?.id};
  if(comparingWordings()){
    intent.recipe={...comparisonRecipe,controls:{...comparisonRecipe.controls,seed:comparisonSeed}};
    intent.variants=[{label:'Wording A',controls:{positive:$('#experimentWordingA').value}},{label:'Wording B',controls:{positive:$('#experimentWordingB').value}}];
  }else if(plannedVariants&&plannedVariants.length)intent.variants=plannedVariants.map(v=>({label:v.label,controls:v.controls,rationale:v.rationale||'',sources:v.sources||[]}));
  else{intent.axis=$('#experimentAxis').value;intent.values=$('#experimentValues').value.split(',').map(v=>v.trim()).filter(Boolean);}
  const p=await post('/api/production',intent);
  if(!current())return;
  productionId=p.id;$('#experimentDialog').close();showView('production');if(start)await startPreparedPlan(p);await refreshProduction(true);
}catch(err){if(current())$('#experimentStatus').textContent=err.message;}finally{comparisonPreparing=false;renderPlanner(false);}};
// The empty state hands the operator the same route the header button uses:
// Create, with the recipe that is already open, then the planner. It starts nothing.
function planFromEmptyState(){
  try{document.dispatchEvent(new CustomEvent('studio:navigate',{detail:'create'}));}catch(err){showView('create');}
  if(typeof selected!=='undefined'&&selected)$('#planComparison')?.click?.();
  else productionMessage('Choose a recipe in Full editor first, then press Plan comparison.');
}
// The orientation block stays closed so the plans show first; remembering the
// choice is a per-browser convenience, and a storage that refuses to answer must
// never stop the view from rendering.
const PRODUCTION_INTRO_KEY='studio.production.intro';
function restoreProductionIntro(){
  const intro=$('#productionIntro');if(!intro)return;
  try{intro.open=localStorage.getItem(PRODUCTION_INTRO_KEY)==='open';}catch(err){}
  intro.ontoggle=()=>{try{localStorage.setItem(PRODUCTION_INTRO_KEY,intro.open?'open':'closed');}catch(err){}};
}
restoreProductionIntro();restorePlanFilter();
if($('#planType'))$('#planType').onchange=()=>setPlanFilter({type:$('#planType').value});
if($('#planStatus'))$('#planStatus').onchange=()=>setPlanFilter({status:$('#planStatus').value});
$('#productionList').onclick=e=>{if(e.target.closest('[data-production-plan]')){planFromEmptyState();return;}if(e.target.closest('[data-plan-show-all]')){setPlanFilter({type:'all',status:'all'},true);return;}const p=e.target.closest('[data-project]');if(p){productionId=p.dataset.project;renderProduction();}};
$('#productionDetail').oninput=e=>keepProductionDraft(e.target);
$('#productionDetail').onchange=e=>{if(e.target.id==='blindComparison'){blindComparison=e.target.checked;renderProduction();}};
// Workspace review of a single candidate image: the same revision-guarded
// /api/assets/update command the asset dialog sends, never a new endpoint. It
// records a creative preference only; the comparison's own outcome is untouched.
const candidateReviewBusy=new Set();
// A candidate can sit outside the Library's one page: read through the resolved set and resolve by ID before a write.
const candidateRecord=id=>typeof assetRecord==='function'?assetRecord(id)||null:assetState.assets.find(a=>a.id===id)||null;
async function candidateResolve(id){await refreshAssets(true);if(!candidateRecord(id)&&typeof resolveAssetIDs==='function')await resolveAssetIDs([id]);return candidateRecord(id);}
async function reviewCandidateAsset(id,review){
  if(!id||!['selected','needs_work'].includes(review))return;
  // A second press on the same candidate while its save is in flight would queue a second library update and report it as a failure.
  if(candidateReviewBusy.has(id)){productionMessage('Still saving the last mark for this candidate. Press again in a moment. Nothing was changed.');return;}
  candidateReviewBusy.add(id);
  try{
    await candidateResolve(id);
    await mutateAssets({ids:[id],action:'edit',review});
    productionMessage((review==='selected'?'Kept':'Marked as needing work')+' in your Workspace. The comparison outcome and its reservations are unchanged.');
  }finally{candidateReviewBusy.delete(id);}
}
// #1203: quick yes/no checks on a candidate picture, saved one press at a time through the same guarded update.
// Counts per candidate come only from those owner answers; the comparison's own outcome is untouched.
function candidateCheckAsset(id){return globalThis.StudioReviewChecks&&typeof assetState!=='undefined'?candidateRecord(id):null;}
function candidateCheckNames(job){return globalThis.StudioReviewChecks&&job?StudioReviewChecks.forPreset((typeof catalog==='undefined'?[]:catalog?.presets||[]).find(p=>p.id===job.preset_id)):[];}
const candidateChecksLoading=new Set();
function candidateHasImage(plan,id){return plan?.kind==='comparison'&&(plan.stages||[]).some(stage=>(stage.job?.outputs||[]).some(output=>output.asset_id===id&&output.media_type==='image'));}
async function loadCandidateChecks(id){
  const plan=productionId,scope=typeof assetState==='undefined'?null:assetState.workspace_id,epoch=typeof assetWorkspaceEpoch==='undefined'?null:assetWorkspaceEpoch;
  const current=()=>productionId===plan&&productionDetailPlan===plan&&(typeof assetState==='undefined'?null:assetState.workspace_id)===scope&&(typeof assetWorkspaceEpoch==='undefined'?null:assetWorkspaceEpoch)===epoch&&candidateHasImage(productionPlans.find(p=>p.id===plan),id);
  if(!id||!candidateHasImage(productionPlans.find(p=>p.id===plan),id)||candidateChecksLoading.has(id))return false;
  candidateChecksLoading.add(id);productionMessage('Reading saved checks…');
  try{
    if(!scope||typeof resolveAssetIDs!=='function')throw Error('The Library is not ready. Refresh it, then load these saved checks again.');
    const observed=await resolveAssetIDs([id]);if(!current())return false;
    if(!observed)throw Error('The saved checks changed while loading. Load them again before answering.');
    renderProduction();productionMessage(candidateCheckAsset(id)?'Saved checks loaded. No answer was changed.':'This candidate is no longer in the Library. No answer was changed.');return true;
  }catch(error){if(current())productionMessage(error.message,true);return false;}
  finally{candidateChecksLoading.delete(id);}
}
let candidateCheckBusy=false;
async function checkCandidateAsset(id,name){
  if(candidateCheckBusy){productionMessage('Still saving the last answer. Press again in a moment. Nothing was changed.');return;}
  if(!id||!globalThis.StudioReviewChecks)return;
  candidateCheckBusy=true;
  try{
    const asset=await candidateResolve(id);
    if(!asset)throw Error('This candidate is no longer in the library. Nothing was saved.');
    const tags=StudioReviewChecks.cycle(asset.tags,name),now=StudioReviewChecks.answer(tags,name);
    await mutateAssets({ids:[id],action:'edit',tags});renderProduction();
    productionMessage('Saved for this candidate: '+name+' '+(now===null?'not checked':now?'yes':'no')+'. The comparison outcome is unchanged.');
  }finally{candidateCheckBusy=false;}
}
async function productionPlanAction(p,action){await post('/api/production/'+p.id+'/'+action,{});dropProductionDrafts();}
// Called only by an explicit Prepare and start submission, once its preparation succeeds.
async function startPreparedPlan(p){
  if(!p?.id){productionMessage('The plan was not confirmed, so nothing was started.',true);return;}
  if(productionActionPending){productionMessage('Wait for the current action to finish. Nothing was sent.');return;}
  productionActionPending=true;try{await productionPlanAction(p,'start');}catch(err){productionMessage(err.message,true);}finally{productionActionPending=false;}
}
$('#productionDetail').onclick=async e=>{if(e.target.closest('[data-plan-comparison]')){$('#newExperiment').click();return;}const actionButton=e.target.closest('[data-project-action]'),action=actionButton?.dataset.projectAction,coordinatorAction=['start','stop','resume','extend-time'].includes(action);
  if(coordinatorAction&&productionActionPending){productionMessage('Wait for the current action to finish. Nothing was sent.');return;}
  if(coordinatorAction){productionActionPending=true;actionButton.disabled=true;}
  try{
  const p=productionPlans.find(p=>p.id===productionId);if(!p)return;
  const putAway=e.target.closest('[data-plan-put-away]');
  if(putAway){if(productionActionPending){productionMessage('Wait for the current action to finish. Nothing was sent.');return;}productionActionPending=true;putAway.disabled=true;const away=putAway.dataset.planPutAway==='true';
    try{await post('/api/production/'+p.id+'/put-away',{put_away:away});productionMessage(away?'Put away. Status: All statuses in Your plans still lists it; Bring back returns it to your desk.':'Back on your desk and in the in-progress list.');await refreshProduction(true);}
    finally{productionActionPending=false;putAway.disabled=false;}return;}
  const choice=e.target.closest('[data-choose-candidate]')?.dataset.chooseCandidate;
  const open=e.target.closest('[data-candidate-open]')?.dataset.candidateOpen;
  const recipe=e.target.closest('[data-job-recipe]')?.dataset.jobRecipe;
  const mark=e.target.closest('[data-candidate-review]');
  if(mark){await reviewCandidateAsset(mark.dataset.candidateAsset,mark.dataset.candidateReview);return;}
  const loadChecks=e.target.closest('[data-candidate-check-load]');if(loadChecks){await loadCandidateChecks(loadChecks.dataset.candidateCheckLoad);return;}
  const checkChip=e.target.closest('[data-candidate-check]');if(checkChip){await checkCandidateAsset(checkChip.dataset.asset,checkChip.dataset.candidateCheck);return;}
  if(open){await refreshAssets();openAsset(open);return;}if(recipe){await exportRecipe(recipe);return;}
  if(action==='branch'){applySaved({preset:p.recipe.preset_id,controls:p.recipe.controls,references:p.recipe.references,parent_assets:p.recipe.parent_assets});await openComparison(p);return;}
  if(choice||action==='needs_work'){const notes=$('#productionNotes').value;await post('/api/production/'+p.id+'/review',{asset_id:choice||null,notes,reviewer:'local-user'});dropProductionDrafts({productionNotes:notes});}
  else if(action==='extend-time'){
    const minutes=$('#extendTimeMinutes').value,typed=$('#extendTimeReason').value,seconds=Number(minutes)*60,reason=typed.trim();
    if(!Number.isInteger(seconds)||seconds<60||!reason)throw Error('Give at least one whole minute of additional time and a reason.');
    await post('/api/production/'+p.id+'/extend-time',{seconds,reason,expected_revision:p.state.time_budget.revision});dropProductionDrafts({extendTimeMinutes:minutes,extendTimeReason:typed});
  }
  // A plan that starts, stops or resumes moves on; a time-extension draft from before must not come back later.
  else if(['start','stop','resume'].includes(action))await productionPlanAction(p,action);
  if(action||choice)await refreshProduction(true);
}catch(err){productionMessage(err.message,true);}finally{if(coordinatorAction){productionActionPending=false;actionButton.disabled=false;}}};
$('#productionDetail').onkeydown=async e=>{const index=globalThis.StudioReviewChecks?.keyIndex(e)??-1;if(index<0||index>4)return;const tag=(e.target?.tagName||'').toUpperCase();if(['INPUT','TEXTAREA','SELECT'].includes(tag))return;const candidate=e.target?.closest?.('article.candidate')||e.target?.closest?.('.candidate');if(!candidate)return;const chip=[...(candidate.querySelectorAll?.('[data-candidate-check]')||[])][index];if(!chip||chip.disabled)return;e.preventDefault();const {asset,candidateCheck:name}=chip.dataset;try{await checkCandidateAsset(asset,name);}catch(err){productionMessage(err.message,true);return;}const again=[...($('#productionDetail').querySelectorAll?.('[data-candidate-check]')||[])].find(c=>c.dataset?.asset===asset&&c.dataset?.candidateCheck===name);again?.focus?.({preventScroll:true});};
function renderNativeAssets(){
  $('#nativeAssetList').innerHTML=nativeAssets.map((a,i)=>'<div class="native-source"><span>'+esc(a.title)+'</span><button type="button" data-native-up="'+i+'" '+(!i?'disabled':'')+' aria-label="Move source '+(i+1)+' earlier">↑</button><button type="button" data-native-down="'+i+'" '+(i===nativeAssets.length-1?'disabled':'')+' aria-label="Move source '+(i+1)+' later">↓</button>'+(a.media_type==='image'?'<label>Duration ms<input type="number" min="1" max="60000" data-native-duration="'+a.id+'" value="'+a.duration+'"></label><label>Layer name<input data-native-layer="'+a.id+'" value="'+esc(a.layerName)+'"></label>':'<small>Optional GLB</small>')+'</div>').join('');
}
$('#nativeExport').onclick=()=>{++nativeRequestId;nativeAssets=[...assetSelection].map(id=>typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id)).filter(Boolean).map(a=>({...a,duration:100,layerName:a.title}));if(!nativeAssets.length){assetMessage('Select the source images first.',true);return;}$('#nativeStatus').textContent='Prepare and start the export now, or prepare only to start it later.';renderNativeAssets();$('#nativeDialog').showModal();};
$('#nativeDialog').onclose=()=>{++nativeRequestId;};$('#nativeForm').oninput=()=>{++nativeRequestId;};
$('#cancelNative').onclick=()=>$('#nativeDialog').close();$('#nativeKind').onchange=()=>{$('#nativeEngineWrap').hidden=$('#nativeKind').value!=='godot';$('#nativeKritaWrap').hidden=$('#nativeKind').value!=='ora';};
function readNativeInputs(){
  for(const input of $('#nativeAssetList').querySelectorAll('input')){
    const id=input.dataset.nativeDuration||input.dataset.nativeLayer,a=nativeAssets.find(a=>a.id===id);
    if(a)a[input.dataset.nativeDuration?'duration':'layerName']=input.dataset.nativeDuration?Number(input.value):input.value;
  }
}
$('#nativeAssetList').oninput=readNativeInputs;
$('#nativeAssetList').onclick=e=>{const up=e.target.closest('[data-native-up]'),down=e.target.closest('[data-native-down]');if(!up&&!down)return;++nativeRequestId;const i=Number((up||down).dataset[up?'nativeUp':'nativeDown']),j=i+(up?-1:1);[nativeAssets[i],nativeAssets[j]]=[nativeAssets[j],nativeAssets[i]];renderNativeAssets();};
$('#nativeForm').onsubmit=async e=>{e.preventDefault();if(nativePreparing||productionActionPending)return;
  const start=e.submitter?.id==='prepareNative',ticket=++nativeRequestId,current=()=>ticket===nativeRequestId&&$('#nativeDialog').open;
  nativePreparing=true;$('#prepareNative').disabled=true;$('#prepareNativeOnly').disabled=true;try{
  readNativeInputs();
  const images=nativeAssets.filter(a=>a.media_type==='image'),kind=$('#nativeKind').value,options={clip:$('#nativeClip').value,duration_ms:images.map(a=>a.duration),layer_names:images.map(a=>a.layerName),loop:$('#nativeLoop').checked,filter:$('#nativeFilter').value};
  const x=$('#nativeAnchorX').value,y=$('#nativeAnchorY').value;if(x!==''||y!==''){if(x===''||y==='')throw Error('Set both anchor coordinates, or leave both automatic.');options.anchor=[Number(x),Number(y)];}
  const p=await post('/api/production-export',{kind,ids:nativeAssets.map(a=>a.id),options,verify_engine:kind==='godot'&&$('#nativeEngine').checked,verify_krita:kind==='ora'&&$('#nativeKrita').checked});if(!current())return;productionId=p.id;$('#nativeDialog').close();showView('production');if(start)await startPreparedPlan(p);await refreshProduction(true);
}catch(err){if(current())$('#nativeStatus').textContent=err.message;}finally{nativePreparing=false;$('#prepareNative').disabled=false;$('#prepareNativeOnly').disabled=false;}};

$('#newArticulated').onclick=()=>$('#articulatedDialog').showModal();
$('#cancelArticulated').onclick=()=>$('#articulatedDialog').close();
$('#articulatedForm').onsubmit=async e=>{e.preventDefault();$('#prepareArticulated').disabled=true;try{
  const p=await post('/api/articulated',{name:$('#articulatedName').value,options:{width:Number($('#propWidth').value),depth:Number($('#propDepth').value),body_height:Number($('#propBody').value),lid_height:Number($('#propLid').value)}});
  productionId=p.id;$('#articulatedDialog').close();showView('production');await refreshProduction(true);
}catch(err){$('#articulatedStatus').textContent=err.message;}finally{$('#prepareArticulated').disabled=false;}};
