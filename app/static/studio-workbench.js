/* Migration adapter: enhances the existing no-build UI without replacing its services.
 * All legacy function interception lives here. Core policy and shell are independent.
 * Remove a hook when its legacy component is migrated; do not add a second executor.
 */
(function(){
  'use strict';
  if(!document.querySelector('#createView'))return;
  const U=StudioUX,q=s=>document.querySelector(s),escape=esc;
  let sharedAdoptionError='';
  let selectionEpoch=0,sourceContext=null,handoffBaseline=null,sourceReadError='';
  let intentId='create',handoffId=null,handoffIntent='edit',handoffBusy=false,pickerBusy=false,handoffEpoch=0;
  let draftPrefix=null,draftPaused=false,draftDirty=false,restoring=false,draftTimer=null,knownDrafts=new Map(),pendingInputs=new Set();
  let homeBusy=false,homeData=null,homeErrors=[],homeUpdated=null,homeSignature='';
  const main=q('main'),editor=q('#createView .editor');
  function after(name,callback){const original=window[name];window[name]=function(...args){const result=original.apply(this,args);callback(...args);return result;};}
  function element(tag,className,html){const el=document.createElement(tag);if(className)el.className=className;if(html)el.innerHTML=html;return el;}
  function announce(text,error=false){message(text,error);q('#uxNotice').textContent=text;q('#uxNotice').classList.toggle('error',error);}
  const notice=element('p','ux-notice');notice.id='uxNotice';notice.setAttribute('role','status');main.prepend(notice);
  // Home is a work queue, not a separate project store. Unknown API state is not zero.
  const home=element('section','view ux-home');home.id='homeView';home.setAttribute('aria-labelledby','homeTitle');home.innerHTML='<div class="ux-home-heading"><div><span class="eyebrow">YOUR LOCAL CREATIVE WORKSPACE</span><h1 id="homeTitle" tabindex="-1">Pick up the thread.</h1><p>Start with an idea. Keep what works. Take it somewhere new.</p></div><button id="uxRefreshHome">Refresh overview</button></div><div id="uxHomeHealth" class="ux-home-health" role="status">Reading saved work…</div><div id="uxStats" class="ux-stats"></div><div class="section-title"><h2>What are you making?</h2><a href="/#create">Browse all recipes ↗</a></div><div id="uxJourneys" class="ux-journeys"></div><div class="ux-home-columns"><section class="panel"><div class="section-title"><h2>On your desk</h2><a href="/#production">All runs ↗</a></div><div id="uxAttention"></div></section><section class="panel ux-workflow-map"><span class="eyebrow">ONE IDEA. MANY DESTINATIONS.</span><h2>Keep the thread intact.</h2><div class="ux-flow-map"><a href="/prompt-lab.html">Brief<small>Shape the intent</small></a><span aria-hidden="true">→</span><a href="/#create">Create<small>Choose a recipe</small></a><span aria-hidden="true">→</span><a href="/#production">Review<small>Make a decision</small></a><span aria-hidden="true">→</span><a href="/#assets">Reuse<small>Carry the source</small></a></div><p>Bring outputs back as references, finish them in native tools, or assemble a scene. Every handoff is yours to review.</p><div class="ux-tool-links"><a href="/av.html">Assemble a scene ↗</a><a href="/voice.html">Prepare a voice take ↗</a><a href="/#learn">Understand the workflow ↗</a></div></section></div><div class="section-title"><h2>Recent assets</h2><a href="/#assets">Open library ↗</a></div><div id="uxRecent" class="ux-recent"></div>';
  main.prepend(home);home.before(notice);
  q('#uxJourneys').innerHTML=U.INTENTS.map((item,i)=>'<button class="ux-journey" data-ux-intent="'+item.id+'"><span class="ux-journey-number">0'+(i+1)+' <span aria-hidden="true">↗</span></span><b>'+item.name+'</b><span>'+item.description+'</span><small>'+item.hint+'</small></button>').join('');
  // Keep every existing control ID. The workbench adapter only changes grouping.
  const createHeading=element('div','ux-create-heading','<div><span class="eyebrow">CREATE / PILOT THE NEXT PASS</span><h1>Follow the idea.</h1></div><div class="ux-stage-track" aria-label="Creative workflow"><span aria-current="step">1 · Prepare</span><span>2 · Run</span><a href="/#production">3 · Review</a><a href="/#assets">4 · Reuse</a></div>');q('#createView').prepend(createHeading);
  const recipeTools=element('div','ux-intent-tools','<label for="uxIntent">Start with a task<select id="uxIntent"><option value="all">Every recipe</option>'+U.INTENTS.map(i=>'<option value="'+i.id+'">'+i.name+'</option>').join('')+'</select></label><p id="uxIntentHint" class="muted">Choose by outcome, then inspect the exact recipe.</p>');q('#presetSearch').closest('label').before(recipeTools);
  const setup=q('#createView .setup'),drawer=element('details','ux-recipe-drawer');drawer.open=window.innerWidth>850;drawer.innerHTML='<summary>Recipe library <small id="uxRecipeLabel">Choose a starting point</small></summary>';while(setup.firstChild)drawer.append(setup.firstChild);setup.append(drawer);
  const drafts=element('div','ux-draft-bar');drafts.id='uxDraftBar';drafts.innerHTML='<span id="uxDraftStatus">Draft recovery is browser-local.</span><div><button id="uxRestoreDraft" hidden>Restore draft</button><button id="uxDiscardDraft" hidden>Discard saved draft</button><button id="uxExportDraft">Export draft</button><button id="uxImportDraftButton">Import draft</button><input id="uxImportDraft" type="file" accept="application/json,.json" hidden><button id="uxKeepDraft" hidden>Keep this tab</button></div>';editor.prepend(drafts);
  q('#positiveWrap').before(element('div','ux-section-heading','<span>01</span><h3>Describe the result</h3><a href="/prompt-lab.html">Open Prompt Lab ↗</a>'));
  const referenceHeading=element('div','ux-section-heading','<span>02</span><h3>Bring in your sources</h3><button id="uxFindReferenceRecipes" hidden>Show reference recipes</button><button id="uxPullAsset">Pull from library</button>');q('#roleReferences').before(referenceHeading);
  const sourceNote=element('p','ux-source-note');sourceNote.id='uxSourceNote';referenceHeading.after(sourceNote);
  // A wrong turn must say something. The sources section stays on screen for every recipe; on a
  // text-only one it is inert and carries this line, which is also the button's described reason (#278 friction 1).
  const NO_SOURCE_SLOT='This recipe takes no reference image. Choose a reference recipe (Qwen Atelier 1–3 references, Krea refine) to keep a source.';
  const takesSource=()=>!!selected?.reference||!!selected?.reference_slots?.length;
  q('#uxPullAsset').setAttribute('aria-describedby','uxSourceNote');
  // Switching intent selects the first reference recipe, which resets the prompt; a typed brief is asked about first.
  q('#uxFindReferenceRecipes').onclick=()=>{const typed=q('#positive')?.value.trim();if(typed&&typed!==(selected?.defaults?.positive||'')&&!confirm('Showing reference recipes selects the first one and resets the prompt and variation count in Create. Continue?'))return;chooseIntent('edit');};
  const advanced=element('details','ux-parameters');advanced.innerHTML='<summary>Parameters & adapter stack <small>Seed, size, sampling and model controls</small></summary>';q('#controls').before(advanced);advanced.append(q('#controls'),q('#loraSlots'));advanced.open=false;
  const runBox=element('div','ux-run-box','<div class="ux-section-heading"><span>03</span><h3>Review, then run</h3></div><p id="uxRunSummary"></p><div class="ux-readiness-heading"><p id="uxReadinessSummary" role="status" aria-live="polite" aria-atomic="true"></p><button type="button" id="uxRecheckReadiness">Recheck connection</button></div><div id="uxBlockers"></div><p id="uxReadinessActionStatus" class="muted" role="status" aria-live="polite"></p><p class="muted">Generate starts this recipe. Plan comparison prepares a budgeted study; Start remains separate.</p>');q('#generate').closest('.actions').before(runBox);runBox.append(q('#generate').closest('.actions'),q('#status'));
  q('#generate').setAttribute('aria-describedby','uxRunSummary uxReadinessSummary uxBlockers');q('.dependencies').open=false;
  q('.gallery-panel .section-title h2').textContent='Recent runs';q('.gallery-panel .muted').textContent='Compare results, inspect recipes, or continue with a saved output.';
  q('#assetsView .view-heading h2').textContent='A library, not a dead end.';
  q('#productionView .view-heading h2').textContent='Run with a question. Leave with a decision.';
  q('#assetScopes').insertAdjacentHTML('beforeend','<button data-scope="unreviewed">Awaiting review</button>');
  const originalVisibleAssets=visibleAssets;visibleAssets=function(){const assets=originalVisibleAssets();return assetScope==='unreviewed'?assets.filter(a=>!a.review||a.review==='unreviewed'):assets;};
  // The legacy app and its tools call showView; this is the single navigation seam.
  showView=function(next){saveDraft();next=U.normalizeView(next);view=next;for(const name of U.VIEWS)q('#'+name+'View').hidden=name!==next;const hero=q('.hero');if(hero)hero.hidden=true;StudioShell.setView(next);if(location.hash!=='#'+next)location.hash=next;if(next==='home')refreshHome();if(next==='assets')refreshAssets();if(next==='production')refreshProduction();if(next==='models'||next==='learn')refreshLibrary();};
  document.addEventListener('studio:navigate',e=>{showView(e.detail);main.focus({preventScroll:true});window.scrollTo({top:0});});window.addEventListener('hashchange',()=>{const next=U.normalizeView(location.hash);if(next!==view)showView(next);});
  const originalRenderPresets=renderPresets;renderPresets=function(){originalRenderPresets();if(!catalog)return;const id=q('#uxIntent').value;if(id==='all')return;const allowed=new Set(U.recipesFor(id,catalog.presets).map(p=>p.id));let count=0;for(const button of q('#presetList').querySelectorAll('[data-id]')){button.hidden=!allowed.has(button.dataset.id);if(!button.hidden)count++;}q('#filteredCount').textContent=count;if(!count)q('#presetList').append(element('p','muted','No recipes match this task and the current filters. Clear search or choose Every recipe.'));};
  function chooseIntent(id){if(!catalog){announce('The recipe catalog is still loading.');return;}intentId=id;q('#uxIntent').value=id;q('#presetSearch').value='';q('#categorySelect').value='All';mode='all';document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode==='all'));const recipes=U.recipesFor(id,catalog.presets);if(recipes.length)selectPreset(recipes[0].id);renderPresets();q('#uxIntentHint').textContent=U.INTENTS.find(i=>i.id===id)?.hint||'Choose by outcome.';showView('create');}
  q('#uxIntent').onchange=()=>{intentId=q('#uxIntent').value;renderPresets();q('#uxIntentHint').textContent=U.INTENTS.find(i=>i.id===intentId)?.hint||'Every installed and planned recipe. Readiness is checked separately.';};
  after('selectPreset',()=>{sharedAdoptionError='';selectionEpoch++;draftDirty=false;pendingInputs.clear();if(typeof dismissSecondPicture==='function')dismissSecondPicture();syncCreate();renderDraftNotice();});
  after('applySaved',()=>{if(!restoring)draftDirty=true;hydrateContinuation();});after('applyRecipe',()=>{draftDirty=true;syncReady();saveDraft();});
  const originalSelectPreset=selectPreset;selectPreset=function(...args){saveDraft();return originalSelectPreset(...args);};
  after('renderSelected',syncCreate);after('updateReady',syncReady);
  const originalUploadRoleFile=uploadRoleFile;uploadRoleFile=async function(...args){const epoch=referenceEpoch;await originalUploadRoleFile(...args);if(epoch===referenceEpoch){draftDirty=true;saveDraft();}};
  // Collapse six overlapping output actions into one reviewed, compatible handoff.
  after('renderJobs',()=>{for(const card of q('#gallery').querySelectorAll('.imageCard')){const actions=[...card.querySelectorAll('.reference-output')];if(!actions.length)continue;const first=actions.shift();first.textContent='Continue with this →';first.classList.add('primary');actions.forEach(button=>button.remove());}});
  function syncCreate(){if(!selected)return;q('#uxRecipeLabel').textContent=selected.name;referenceHeading.hidden=false;q('#uxSourceNote').hidden=false;q('#uxFindReferenceRecipes').hidden=takesSource();syncReady();}
  let readinessMarkup='',readinessChecking=false;
  const readinessLabels={recipes:'Choose a recipe',models:'Open Models & setup',dependencies:'Show required files',references:'Show the empty slot',parameters:'Review motion settings',continuation:'Show the source panel','source-back':'Put the source back',wording:'Write the description',second:'Decide about this picture'};
  // A continuation blocker names a control; the button beside it performs or shows that repair, nothing more.
  const continuationActions={source:'source-back',inputs:'references',board:'references',wording:'wording'};
  function readinessItems(){
    const required=[...pendingInputs].filter(id=>!q('#'+id).files.length&&(id==='reference'?!uploaded:!lastUploaded));
    const items=U.readinessItems({preset:selected,online,schemaAvailable,workerAlive,missing:missingByPreset[selected?.id]||[],referencesReady:referencesReady()&&!required.length,switching:typeof backendSwitching!=='undefined'&&backendSwitching,backend:typeof backendActive!=='undefined'?backendActive:null,busy:submitting||handoffBusy||pickerBusy||restoring});
    const modeBlock=i2vModeBlocker();if(modeBlock)items.push({code:'motion',message:modeBlock,action:'parameters'});
    const specific=continuationBlockerItems().map(item=>({code:'continuation-'+item.code,message:item.message,action:continuationActions[item.code]||'continuation'}));
    // The continuation names the exact empty slot; the generic reference line would only repeat it.
    if(specific.some(item=>['continuation-board','continuation-inputs','continuation-source'].includes(item.code)))items.splice(items.findIndex(item=>item.code==='references')>>>0,1);
    items.push(...specific);
    if(secondPicture)items.push({code:'second',message:'You added a second picture, but this recipe reads one. Say what it is for.',action:'second'});
    if(sharedAdoptionError)items.push({code:'shared-setup',message:sharedAdoptionError,action:null});
    if(continuationState&&!continuationSource)items.push({code:'source',message:sourceReadError||'Checking the retained source metadata…',action:'continuation'});
    return{items,required};
  }
  function syncReady(){
    if(!q('#uxRunSummary'))return;
    const {items,required}=readinessItems();
    q('#generate').disabled=items.length>0;syncContinuation();
    const markup=items.map(item=>'<div class="ux-blocker" data-readiness-code="'+item.code+'"><p>'+escape(item.message)+'</p>'+(readinessLabels[item.action]?'<button type="button" data-ux-resolve="'+item.action+'">'+readinessLabels[item.action]+'</button>':'')+'</div>').join('');
    // Polling identical evidence must not replace a focused action or announce the same status again.
    if(markup!==readinessMarkup){readinessMarkup=markup;q('#uxBlockers').innerHTML=markup;}
    const summary=items.length?items.length+' condition'+(items.length===1?' needs':'s need')+' attention. Your draft remains editable.':'No blockers reported by the current checks. Generate still validates the request on the server.';
    if(q('#uxReadinessSummary').textContent!==summary)q('#uxReadinessSummary').textContent=summary;
    q('#uxRecheckReadiness').disabled=readinessChecking;
    q('#uxRunSummary').textContent=selected?selected.name+' · '+q('#batch').value+' output(s) · '+(selected.backend_id||'primary')+' environment':'Choose a recipe to prepare your next run.';
    const refs=selected?.reference_slots?.length?referenceRecords.filter(r=>r.file&&!r.missing).length+(selected.last_reference&&lastUploaded?1:0):(uploaded?1:0)+(lastUploaded?1:0);
    q('#uxSourceNote').textContent=!takesSource()?NO_SOURCE_SLOT:refs?refs+' attached reference(s) · '+parentAssets.length+' source asset(s) retained in lineage.':required.length?'Saved input is unavailable. Reattach it; no example fallback will be used.':selected?.reference_slots?.length?'Assign a role to each image. Required slots must be filled.':continuationState?'The continuation source is not attached. Use Put the source back, or reopen Continue with this asset.':'No personal source attached. This recipe may use its authored example until replaced.';
  }
  function focusReadinessTarget(target){
    if(!target||target.closest('[hidden]')||target.disabled)return false;
    for(let ancestor=target.parentElement;ancestor;ancestor=ancestor.parentElement)if(ancestor.tagName==='DETAILS')ancestor.open=true;
    if(!target.getClientRects().length)return false;
    if(!target.matches('button,input,select,textarea,a[href],summary,[tabindex]'))target.setAttribute('tabindex','-1');
    target.focus({preventScroll:true});target.scrollIntoView({block:'center',behavior:'instant'});return true;
  }
  function resolveReadiness(action){
    // Resolve against live state: a detached/stale action is not a saved instruction.
    if(!readinessItems().items.some(item=>item.action===action))return;
    let target=null;
    if(action==='recipes')target=q('#presetSearch');
    if(action==='dependencies')target=q('.dependencies > summary');
    if(action==='models'){showView('models');target=q('#backendChoice')||q('#refreshModels');}
    if(action==='references'){
      const lastMissing=selected?.last_reference&&!lastUploaded&&!q('#lastReference').files.length;
      if(selected?.reference_slots?.length){const index=referenceRecords.findIndex(r=>!r.file||r.missing);target=index>=0?q('[data-ref-file="'+index+'"]'):lastMissing?q('#lastReference'):q('#referenceSummary');}
      else target=[...pendingInputs].filter(id=>!q('#'+id).files.length&&(id==='reference'?!uploaded:!lastUploaded)).map(id=>q('#'+id))[0]||(lastMissing&&uploaded?q('#lastReference'):q('#reference'));
    }
    if(action==='parameters')target=q('#i2vMode')||getControl('frames');
    if(action==='wording')target=q('#positive');
    if(action==='second')target=q('#uxSecondPicture');
    if(action==='source-back'){void reattachSource();return;}
    if(action==='continuation')target=selected?.positive&&!q('#positive').value.trim()?q('#positive'):q('#uxContinuation');
    if(!focusReadinessTarget(target))q('#uxReadinessActionStatus').textContent='That control is not available in the current view. Recheck the recipe before continuing.';
    else q('#uxReadinessActionStatus').textContent='Shown for review. No settings, attachments or execution permissions were changed.';
  }
  q('#uxBlockers').onclick=e=>{const button=e.target.closest('[data-ux-resolve]');if(button)resolveReadiness(button.dataset.uxResolve);};
  q('#uxRecheckReadiness').onclick=async()=>{
    if(readinessChecking)return;readinessChecking=true;q('#uxRecheckReadiness').disabled=true;
    q('#uxReadinessActionStatus').textContent='Reading connection and node readiness. No generation or installation is requested.';
    let deadline=null;
    try{await Promise.race([health(),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(Error('Connection check timed out; the shared read may still finish. Your draft is unchanged.')),15000);})]);q('#uxReadinessActionStatus').textContent=healthError?'Connection could not be checked. Your draft is unchanged.':'Connection check finished. Review any remaining conditions; no generation was requested.';}
    catch(error){q('#uxReadinessActionStatus').textContent='Connection check unavailable: '+error.message;}
    finally{clearTimeout(deadline);readinessChecking=false;syncReady();}
  };

  const contextPanel=element('section','ux-continuation');contextPanel.id='uxContinuation';contextPanel.hidden=true;
  contextPanel.innerHTML='<img id="uxContinuationImage" alt="Source image for this pass"><div><span class="eyebrow">CONTINUING YOUR IMAGE</span><h3 id="uxContinuationTitle"></h3><p id="uxContinuationOrigin"></p><div id="uxContinuationGuidance"></div><details><summary>Source wording and provenance</summary><pre id="uxContinuationPrompt"></pre><small id="uxContinuationRecord"></small></details><div class="ux-context-actions"><button id="uxRestoreSourcePrompt">Restore source wording</button><button id="uxChangeRoute">Change route</button><button id="uxLeaveContinuation">Leave this continuation</button></div><p id="uxContinuationContract">Setup choices keep this source and your wording; they reset sampling and adapters to their defaults. Check Parameters before running.</p></div>';
  q('#selectedPreset').before(contextPanel);
  function workbenchStamp(){return JSON.stringify({preset:selected?.id,controls:values(),parents:parentAssets,references:attachedReferencePayload(),continuation:continuationState,batch:q('#batch').value,pending:['reference','lastReference'].map(id=>[...(q('#'+id).files||[])].map(f=>[f.name,f.size,f.lastModified]))});}
  function syncContinuation(){
    contextPanel.hidden=!continuationState;if(!continuationState)return;
    const source=continuationSource,cap=selected?.continuation_capability;
    q('#uxContinuationImage').src='/api/assets/'+encodeURIComponent(continuationState.source_asset_id)+'/file';
    q('#uxContinuationTitle').textContent=source?.title||'Saved source · '+continuationState.source_asset_id;
    const reusable=source?.prompt_origin==='submitted-output'&&source?.prompt_role==='description'&&typeof source.positive==='string';
    q('#uxContinuationOrigin').textContent=cap?.prompt_role==='none'?'This operation has no text prompt.':reusable&&q('#positive').value===source.positive?'Prompt matches this output’s submitted description.':q('#positive').value.trim()?'Using your editable wording for this pass.':'Wording needed: '+(cap?.prompt_role==='instruction'?'say what to change and what to preserve.':cap?.prompt_role==='motion'?'describe the motion and camera movement.':'describe the resulting image you want.');
    q('#positive').placeholder=cap?.prompt_role==='instruction'?'For example: Change the lighting. Keep the subject, clothing, pose and composition.':cap?.prompt_role==='motion'?'For example: A gentle breeze moves the clothing; the camera slowly moves closer.':'Describe the subject, clothing, scene and style to preserve. The recipe example is not used.';
    q('#uxContinuationGuidance').innerHTML=StudioContinuation.guidance(selected,source).map(text=>'<p>'+escape(text)+'</p>').join('');
    q('#uxContinuationPrompt').textContent=source?.positive||sourceReadError||'No submitted source wording is available.';
    q('#uxContinuationRecord').textContent=source?'Prompt '+(source.prompt_id||'unavailable')+' · source SHA-256 '+source.sha256:'Reading the retained source; no new model request.';
    q('#uxRestoreSourcePrompt').disabled=!reusable||cap?.prompt_role!=='description'||submitting;
    q('#uxChangeRoute').disabled=submitting;q('#uxLeaveContinuation').disabled=submitting;
    q('#generate').textContent=cap?.operation==='upscale'?'Upscale source →':cap?.operation==='restyle'?'Restyle source →':cap?.prompt_role==='motion'?'Animate source →':'Generate source-based pass →';
  }
  async function readSource(id){return api('/api/assets/'+encodeURIComponent(id)+'/context',{signal:AbortSignal.timeout(30000)});}
  async function hydrateContinuation(){
    const claim=continuationState,stamp=JSON.stringify(claim);sourceReadError='';syncReady();if(!claim)return;
    try{const source=await readSource(claim.source_asset_id);if(stamp!==JSON.stringify(continuationState))return;if(source?.asset_id!==claim.source_asset_id||source.sha256!==claim.source_sha256)throw Error('Source identity changed. Reopen the handoff.');continuationSource=source;}
    catch(error){if(stamp===JSON.stringify(continuationState))sourceReadError='Could not verify source metadata: '+error.message;}
    finally{if(stamp===JSON.stringify(continuationState))syncReady();}
  }
  q('#uxRestoreSourcePrompt').onclick=()=>{const source=continuationSource;if(!source||q('#uxRestoreSourcePrompt').disabled)return;if(q('#positive').value!==source.positive&&!window.confirm('Replace your current wording with this output’s submitted description?'))return;q('#positive').value=source.positive;if(selected.negative)q('#negative').value=source.negative||'';draftDirty=true;saveDraft();syncReady();};
  q('#uxChangeRoute').onclick=()=>openHandoff(continuationState.source_asset_id,selected.id);
  q('#uxLeaveContinuation').onclick=leaveContinuation;
  async function reattachSource(){
    if(!continuationState||pickerBusy||handoffBusy||submitting||restoring)return;
    const claim=continuationState,stamp=JSON.stringify(claim);pickerBusy=true;syncReady();
    try{
      const result=await post('/api/assets/reference',{id:claim.source_asset_id});
      if(stamp!==JSON.stringify(continuationState))throw Error('The task changed while the source was being put back. Nothing was attached.');
      if(result.sha256!==claim.source_sha256||result.parent_asset!==claim.source_asset_id||result.context?.sha256!==claim.source_sha256)throw Error('The library copy of the source changed. Reopen Continue with this asset.');
      // A fresh staged copy has a fresh name; the claim follows it, the identity (source hash) does not change.
      const renamed=StudioContinuation.normalize({...claim,reference_file:result.file});if(!renamed)throw Error('The staged copy could not be verified. Reopen Continue with this asset.');
      continuationState=renamed;continuationSource=result.context;secondPicture=null;secondPanel.hidden=true;
      attachContinuationSource(result,false);pendingInputs.delete(StudioContinuation.sourceInput(selected.continuation_capability)==='last_reference'?'lastReference':'reference');
      draftDirty=true;saveDraft();syncCreate();announce(StudioContinuation.sourceLabel(selected)+' holds the source again. No generation submitted.');
    }catch(error){announce(error.message,true);}
    finally{pickerBusy=false;syncReady();}
  }
  // One slot, two pictures: the second picture is a question, not a silent replacement (owner report, 14 Sep 2026).
  let secondPicture=null,pendingStyle=null;
  const secondPanel=element('div','ux-second-picture callout');secondPanel.id='uxSecondPicture';secondPanel.hidden=true;secondPanel.setAttribute('role','group');secondPanel.setAttribute('aria-labelledby','uxSecondTitle');
  secondPanel.innerHTML='<b id="uxSecondTitle">One slot, two pictures.</b><p id="uxSecondText"></p><div class="ux-context-actions"><button type="button" id="uxSecondRestyle" class="primary">Use its look → Restyle the source</button><button type="button" id="uxSecondReplace">Start from this picture instead</button><button type="button" id="uxSecondKeep">Keep the source, drop this picture</button></div><p id="uxSecondHint" class="muted"></p>';
  q('#createView .references').after(secondPanel);
  function secondName(item){return item?.file?item.file.name:item?.asset?.title||'this picture';}
  function offerSecondPicture(item){
    secondPicture=item;const dest=StudioContinuation.destinations('restyle',catalog?.presets||[],continuationSource)[0];
    q('#uxSecondText').textContent=StudioContinuation.sourceLabel(selected)+' already holds the picture you are continuing. What is “'+secondName(item)+'” for?';
    q('#uxSecondRestyle').disabled=!dest;q('#uxSecondRestyle').title=dest?'':'No restyle recipe is installed.';
    q('#uxSecondHint').textContent=dest?'Restyle keeps the source’s pose and paints it in the look of the new picture ('+dest.name+'). Starting from the new picture ends this continuation; the original stays in your library.':'No restyle recipe is available; start from the new picture, or keep the source.';
    secondPanel.hidden=false;syncReady();focusReadinessTarget(q('#uxSecondRestyle').disabled?q('#uxSecondReplace'):q('#uxSecondRestyle'));
  }
  function dismissSecondPicture(){secondPicture=null;secondPanel.hidden=true;}
  const legacyReferenceChange=q('#reference').onchange;
  q('#reference').onchange=function(e){
    const file=q('#reference').files?.[0];
    if(continuationState&&file&&!selected?.reference_slots?.length&&StudioContinuation.sourceInput(selected?.continuation_capability)==='reference'){offerSecondPicture({file});return;}
    dismissSecondPicture();return legacyReferenceChange?.call(this,e);
  };
  q('#uxSecondKeep').onclick=()=>{dismissSecondPicture();q('#reference').value='';syncReady();announce('Kept the source. The extra picture was not attached.');};
  q('#uxSecondRestyle').onclick=()=>{
    const item=secondPicture,dest=StudioContinuation.destinations('restyle',catalog?.presets||[],continuationSource)[0];if(!item||!dest||!continuationState)return;
    dismissSecondPicture();q('#reference').value='';pendingStyle=item;syncReady();
    openHandoff(continuationState.source_asset_id,dest.id,undefined,'restyle');
  };
  q('#uxSecondReplace').onclick=async()=>{
    const item=secondPicture;if(!item||!continuationState)return;
    if(!window.confirm('Start from this picture instead? The continuation ends and Create resets to the recipe defaults. The original stays in your library.'))return;
    dismissSecondPicture();selectPreset(selected.id,true,true);
    try{
      if(item.file){const transfer=new DataTransfer();transfer.items.add(item.file);q('#reference').files=transfer.files;legacyReferenceChange?.call(q('#reference'),new Event('change'));}
      else{const result=await post('/api/assets/reference',{id:item.asset.id});uploaded=result.file;q('#reference').value='';replaceParentAsset('reference',null,item.asset.id);}
      draftDirty=true;saveDraft();syncCreate();announce('Continuation ended. '+secondName(item)+' is now the reference; the prompt is the recipe default.');
    }catch(error){announce(error.message,true);}
  };
  // A modal handoff carries IDs, not paths; selecting a destination never runs it.
  const handoff=element('dialog','studio-dialog ux-handoff');handoff.id='uxHandoff';handoff.setAttribute('aria-labelledby','uxHandoffTitle');handoff.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">CONTINUE WITH THIS ASSET</span><h2 id="uxHandoffTitle">Where should it go next?</h2></div><button data-ux-close="uxHandoff" aria-label="Close handoff">✕</button></div><div class="ux-handoff-layout"><div id="uxHandoffSource"></div><div><div id="uxHandoffIntents" class="ux-handoff-intents"></div><label for="uxDestination">Destination recipe<select id="uxDestination"></select></label><div id="uxHandoffDetails"></div><details><summary>Wording prepared for this pass</summary><pre id="uxHandoffPrompt"></pre></details><details><summary>Technical recipe notes</summary><p id="uxHandoffTechnical"></p></details><p class="callout">Prepare attaches a copy and fills the settings. Nothing runs until you press Generate.</p><p id="uxHandoffStatus" role="status"></p><button id="uxPrepareHandoff" class="primary">Prepare in Create →</button></div></div>';document.body.append(handoff);
  function destinationDetails(){
    const p=catalog?.presets.find(p=>p.id===q('#uxDestination').value),cap=p?.continuation_capability;
    q('#uxHandoffDetails').innerHTML=p?StudioContinuation.guidance(p,sourceContext).map(text=>'<p>'+escape(text)+'</p>').join(''):'No supported source-consuming recipe is available for this task.';
    q('#uxHandoffTechnical').textContent=p?.description||'';
    q('#uxHandoffPrompt').textContent=cap?.prompt_role==='none'?'No prompt is used.':cap?.prompt_role==='description'&&sourceContext?.prompt_role==='description'&&typeof sourceContext.positive==='string'?sourceContext.positive:'No recipe example will be inserted. '+(cap?.prompt_role==='instruction'?'Write the requested change after preparing.':cap?.prompt_role==='motion'?'Write a motion brief after preparing.':'Write a description of the intended image after preparing.');
    q('#uxPrepareHandoff').disabled=!p||!sourceContext||!!cap?.requires_mask||handoffBusy||submitting;q('#uxDestination').disabled=handoffBusy;
  }
  function handoffRecipes(preferred){q('#uxHandoffIntents').innerHTML=U.INTENTS.filter(i=>i.id!=='create').map(i=>'<button data-ux-destination="'+i.id+'" aria-pressed="'+(i.id===handoffIntent)+'">'+i.verb+'</button>').join('');const recipes=StudioContinuation.destinations(handoffIntent,catalog?.presets||[],sourceContext);q('#uxDestination').innerHTML=recipes.map(p=>'<option value="'+escape(p.id)+'">'+escape(p.name)+(p.continuation_capability.requires_mask?' · mask preparation required':'')+'</option>').join('');if(recipes.some(p=>p.id===preferred))q('#uxDestination').value=preferred;destinationDetails();}
  function assetDetailsDirty(){return q('#assetDialog').open&&activeAsset&&(q('#assetTitle').value!==activeAsset.title||q('#assetNotes').value!==activeAsset.notes||q('#assetTags').value!==activeAsset.tags.join(', ')||q('#assetReview').value!==activeAsset.review);}
  function warnUnsavedAsset(){let notice=q('#uxAssetUnsaved');if(!notice){notice=element('p','callout');notice.id='uxAssetUnsaved';notice.setAttribute('role','status');q('#assetHandoffs').before(notice);}notice.textContent='Save your asset details before continuing. Your changes are still here.';q('#saveAssetDetails').focus();}
  document.addEventListener('click',e=>{if(e.target.closest('.ux-scene-link,#assetRecipe')&&assetDetailsDirty()){e.preventDefault();e.stopImmediatePropagation();warnUnsavedAsset();}},true);
  function openHandoff(id,preferred,epoch,intent){
    if(epoch!=null&&epoch!==handoffEpoch)return;const request=++handoffEpoch;
    if(assetDetailsDirty()){warnUnsavedAsset();return;}if(!catalog){announce('Recipes are still loading.');return;}
    const a=assetState.assets.find(a=>a.id===id);if(!a||a.trashed_at||a.media_type!=='image'){announce('Choose an available image from the Asset library.',true);return;}
    handoffId=id;sourceContext=null;handoffBaseline=workbenchStamp();
    handoffIntent=intent||(/wan|h3/.test(preferred||'')?'animate':/trellis|hunyuan/.test(preferred||'')?'mesh':/style-pose|restyle-/.test(preferred||'')?'restyle':/fix|refine|upscale|esrgan/.test(preferred||'')?'repair':'edit');
    q('#uxHandoffSource').innerHTML=assetPreview(a,true)+'<b>'+escape(a.title)+'</b><small>Source preserved · '+escape(a.review||'unreviewed')+'</small>';
    q('#uxHandoffStatus').textContent='Reading this output’s exact submitted prompt…';handoffRecipes(preferred);handoff.showModal();
    readSource(id).then(source=>{if(request!==handoffEpoch||!handoff.open)return;if(source?.version!==1||source.asset_id!==id||source.sha256!==a.sha256)throw Error('Source identity changed; refresh the library.');sourceContext=source;q('#uxHandoffStatus').textContent=source.warning||'Source and output-specific wording found. Preparing remains separate from running.';const current=q('#uxDestination').value;handoffRecipes(preferred||current);}).catch(error=>{if(request===handoffEpoch&&handoff.open){q('#uxHandoffStatus').textContent='Could not read source context: '+error.message;sourceContext=null;destinationDetails();}});
  }
  q('#uxDestination').onchange=destinationDetails;
  q('#uxPrepareHandoff').onclick=async()=>{
    if(handoffBusy||q('#uxPrepareHandoff').disabled)return;
    const id=handoffId,preset=q('#uxDestination').value,epoch=handoffEpoch,source=sourceContext;
    handoffBusy=true;destinationDetails();syncReady();
    try{
      if(handoffBaseline!==workbenchStamp())throw Error('The workbench changed while this handoff was open. Reopen it to review the current task.');
      const result=await api('/api/assets/reference',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id}),signal:AbortSignal.timeout(30000)});
      if(epoch!==handoffEpoch||!handoff.open||preset!==q('#uxDestination').value||handoffBaseline!==workbenchStamp())throw Error('The task changed during attachment. The copy was staged but not applied; reopen the handoff.');
      if(result.context?.sha256!==source.sha256||result.context?.asset_id!==id||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The source record changed during attachment. Reopen the handoff before applying it.');
      beginContinuation(result,preset,handoffIntent);sourceReadError='';const style=pendingStyle;pendingStyle=null;
      const restyle=StudioContinuation.sourceInput(selected.continuation_capability)==='last_reference';
      q(restyle?'#lastReferenceHint':'#referenceHint').textContent='Attached source · '+result.width+' × '+result.height;q('#assetDialog').close();handoff.close();draftDirty=true;showView('create');saveDraft();syncCreate();
      if(!restyle){announce('Source attached. Check the prompt, then press Generate.');contextPanel.scrollIntoView({block:'center'});}
      else if(style?.file){announce('Source attached as the pose picture; your style picture is uploading to Picture 1.');void uploadRoleFile(0,style.file);}
      else if(style?.asset){announce('Source attached as the pose picture; your style picture goes on Picture 1.');void pullIntoSlot(0,style.asset.id);}
      else{announce('Source attached as the pose picture. Now add the picture whose look you want to Picture 1, then press Generate.');focusReadinessTarget(q('[data-ref-file="0"]'));}
    }catch(error){q('#uxHandoffStatus').textContent=error.message;}
    finally{handoffBusy=false;destinationDetails();syncReady();}
  };
  handoff.addEventListener('close',()=>{if(!handoff.open){handoffEpoch++;sourceContext=null;pendingStyle=null;}});
  handoff.addEventListener('cancel',e=>{if(handoffBusy)e.preventDefault();});
  // Capture the old action before its old handler can perform an immediate transfer.
  async function openGalleryHandoff(id,preferred){const epoch=++handoffEpoch;if(!id){announce('This output has no saved asset identity. Refresh the workspace before attaching it.',true);return;}let asset=assetState.assets.find(a=>a.id===id);if(!asset)try{const data=await api('/api/workspace');if(epoch!==handoffEpoch)return;if(!data||!Array.isArray(data.assets))throw Error('Workspace assets are unavailable.');assetState=data;renderAssets();asset=assetState.assets.find(a=>a.id===id);}catch(err){if(epoch===handoffEpoch)announce('Could not refresh this output. '+err.message,true);return;}if(epoch!==handoffEpoch)return;openHandoff(id,preferred,epoch);}
  document.addEventListener('click',e=>{const button=e.target.closest('.reference-output,[data-handoff]');if(!button)return;e.preventDefault();e.stopImmediatePropagation();const output=button.dataset.job?jobs.find(j=>j.id===button.dataset.job)?.outputs?.[Number(button.dataset.index)]:null;if(button.classList.contains('reference-output')){void openGalleryHandoff(output?.asset_id,button.dataset.preset);return;}const id=activeAsset?.id;if(!id){announce('Choose an available image from the Asset library.',true);return;}openHandoff(id,button.dataset.preset||button.dataset.handoff);},true);
  after('openAsset',()=>{q('#uxAssetUnsaved')?.remove();if(!activeAsset)return;const a=activeAsset;const eligibility=U.sceneEligibility([a]);q('#assetHandoffs').innerHTML=(!a.trashed_at&&a.media_type==='image'?'<button class="primary" data-ux-handoff="'+a.id+'">Continue with this →</button><button id="uxFindSourceRecipes">Find recipes for this image</button>':'')+(!a.trashed_at&&['image','video','audio'].includes(a.media_type)?'<a class="ux-scene-link" href="/av.html?asset_ids='+encodeURIComponent(a.id)+'">'+(eligibility.ok?'Use in a scene':'Open scene source picker')+' ↗</a>':'');q('#assetRecipe').disabled=!a.job_id;});
  document.addEventListener('click',e=>{if(!e.target.closest('#uxFindSourceRecipes'))return;
    if(assetDetailsDirty()){warnUnsavedAsset();return;}const a=activeAsset;
    if(!a||a.trashed_at||a.media_type!=='image'||!window.RecipeShortlist){announce('Choose an available image after recipe guidance has loaded.',true);return;}
    // Read-only advice identity; do not reuse the source-staging or setup-apply handlers.
    const source={asset_id:a.id,sha256:a.sha256,title:a.title};q('#assetDialog').close();showView('create');
    document.dispatchEvent(new CustomEvent('studio:shortlist-source',{detail:source}));
  });
  after('renderAssets',()=>{if(assetScope==='unreviewed')q('#assetScopeTitle').textContent='Awaiting review';});
  after('renderAssetSelection',()=>{const assets=[...assetSelection].map(id=>assetState.assets.find(a=>a.id===id)).filter(Boolean),eligibility=U.sceneEligibility(assets),link=q('#createScene');link.setAttribute('aria-disabled',String(!eligibility.ok));link.title=eligibility.reason;link.classList.toggle('ux-disabled',!eligibility.ok);});
  document.addEventListener('click',e=>{const link=e.target.closest('#createScene');if(link&&link.getAttribute('aria-disabled')==='true'){e.preventDefault();e.stopImmediatePropagation();assetMessage(link.title,true);}},true);
  after('renderAssetSelection',()=>{
    let button=q('#uxFindSelectedRecipes');if(!button){button=element('button');button.id='uxFindSelectedRecipes';button.type='button';q('#createScene').before(button);}
    button.textContent='Find recipes for selected images ('+assetSelection.size+')';button.disabled=assetSelection.size===0;
    button.title='Review one to three selected library images in selection order; no attachment or generation.';
  });
  document.addEventListener('click',e=>{if(!e.target.closest('#uxFindSelectedRecipes'))return;
    if(assetDetailsDirty()){warnUnsavedAsset();return;}
    const ids=[...assetSelection],items=ids.map(id=>assetState.assets.find(a=>a.id===id));
    if(!window.RecipeShortlist||ids.length<1||ids.length>3||items.some(a=>!a||a.trashed_at||a.media_type!=='image'||typeof a.sha256!=='string'||! /^[0-9a-f]{64}$/.test(a.sha256))){assetMessage('Select one to three available images. Every selected image must have a saved identity; none were dropped.',true);return;}
    // Preserve selection order, including selections outside the current filter. The chooser displays every image before Check.
    const sources=items.map(a=>({asset_id:a.id,sha256:a.sha256,title:a.title,role:'source'}));q('#assetDialog').close();showView('create');
    document.dispatchEvent(new CustomEvent('studio:shortlist-sources',{detail:sources}));
  });
  // Pull any existing image into a named reference slot, without changing the recipe.
  const picker=element('dialog','studio-dialog');picker.id='uxSourcePicker';picker.setAttribute('aria-labelledby','uxPickerTitle');picker.innerHTML='<div class="dialog-heading"><h2 id="uxPickerTitle">Pull from your library</h2><button data-ux-close="uxSourcePicker" aria-label="Close source picker">✕</button></div><label for="uxSourceSlot">Use as<select id="uxSourceSlot"></select></label><label for="uxSourceSearch">Search saved images<input id="uxSourceSearch" type="search" placeholder="Title, tags or recipe…"></label><p id="uxPickerStatus" role="status"></p><div id="uxSourceAssets" class="ux-picker-grid"></div>';document.body.append(picker);
  // Three references cost three round trips only if the picker closes after each pick. It stays open,
  // advances to the next unfilled slot, and closes itself when every required slot holds one (#278 friction 4).
  function sourceSlotOptions(){return selected.reference_slots?.length?selected.reference_slots.map((r,i)=>'<option value="'+i+'">Picture '+(i+1)+' · '+escape(referenceRecords[i]?.role||r.role)+(referenceRecords[i]?.file&&!referenceRecords[i]?.missing?' · attached':'')+'</option>').join('')+(selected.last_reference?'<option value="lastReference">'+escape(selected.last_reference_label||'Last frame')+'</option>':''):'<option value="reference">'+escape(selected.reference_label||'Reference / first frame')+'</option>'+(selected.last_reference?'<option value="lastReference">'+escape(selected.last_reference_label||'Last frame')+'</option>':'');}
  function nextEmptySlot(){return selected.reference_slots?.length?referenceRecords.findIndex(r=>!r.file||r.missing):-1;}
  function renderSources(){const query=q('#uxSourceSearch').value.toLowerCase();const assets=assetState.assets.filter(a=>!a.trashed_at&&a.media_type==='image'&&[a.title,a.preset_name,...a.tags].join(' ').toLowerCase().includes(query));q('#uxSourceAssets').innerHTML=assets.map(a=>'<button data-ux-pull="'+a.id+'">'+assetPreview(a)+'<b>'+escape(a.title)+'</b><small>'+escape(a.review)+'</small></button>').join('')||'<p>No matching saved images. Import an image in the Asset library first.</p>';}
  q('#uxPullAsset').onclick=async()=>{if(!takesSource()){announce(NO_SOURCE_SLOT);return;}const epoch=selectionEpoch;await refreshAssets();if(epoch!==selectionEpoch||view!=='create')return;q('#uxSourceSearch').value='';q('#uxPickerStatus').textContent='Attach a copy. The original stays in your library.';q('#uxSourceSlot').innerHTML=sourceSlotOptions();const first=nextEmptySlot();if(first>=0)q('#uxSourceSlot').value=String(first);renderSources();picker.showModal();};
  q('#uxSourceSearch').oninput=renderSources;
  after('selectPreset',()=>{if(picker.open)picker.close();});
  async function pullIntoSlot(index,id){const result=await post('/api/assets/reference',{id});const previous=referenceRecords[index].parent_asset;Object.assign(referenceRecords[index],result,{missing:false});if(index===0&&StudioContinuation.sourceInput(selected.continuation_capability)!=='last_reference')uploaded=result.file;renderReferenceSlots();replaceParentAsset('reference',previous,id);draftDirty=true;saveDraft();syncCreate();}
  q('#uxSourceAssets').onclick=async e=>{const button=e.target.closest('[data-ux-pull]');if(!button||pickerBusy)return;pickerBusy=true;button.disabled=true;syncReady();try{const id=button.dataset.uxPull,slot=q('#uxSourceSlot').value;
      if(continuationState){const input=StudioContinuation.sourceInput(selected.continuation_capability),isSource=input==='last_reference'?slot==='lastReference':slot==='reference'||slot==='0';
        if(isSource&&!selected.reference_slots?.length){picker.close();offerSecondPicture({asset:assetState.assets.find(a=>a.id===id)});return;}
        if(isSource)throw Error(StudioContinuation.sourceLabel(selected)+' is the picture you are continuing. Pull into another slot, or use Leave this continuation to start from this one.');}
      const stamp=workbenchStamp(),result=await post('/api/assets/reference',{id});if(stamp!==workbenchStamp())throw Error('The workbench changed during attachment. Reopen the picker.');let previous=null;if(slot==='lastReference'){lastUploaded=result.file;q('#lastReference').value='';pendingInputs.delete('lastReference');}else if(selected.reference_slots?.length){previous=referenceRecords[Number(slot)].parent_asset;Object.assign(referenceRecords[Number(slot)],result,{missing:false});if(Number(slot)===0)uploaded=result.file;renderReferenceSlots();}else{uploaded=result.file;q('#reference').value='';pendingInputs.delete('reference');}replaceParentAsset(slot==='lastReference'?'lastReference':'reference',previous,id);draftDirty=true;saveDraft();syncCreate();
      const filled=referenceRecords.filter(r=>r.file&&!r.missing).length,boardDone=!!selected.reference_board&&filled>=(selected.reference_board.min??1);
      const remaining=boardDone?-1:nextEmptySlot();
      if(remaining<0){picker.close();announce('Saved source attached. No generation submitted.');}
      else{q('#uxSourceSlot').innerHTML=sourceSlotOptions();q('#uxSourceSlot').value=String(remaining);q('#uxPickerStatus').textContent='Attached. Picture '+(remaining+1)+' of '+referenceRecords.length+' is still empty; pick its image or close this picker.';announce('Saved source attached. No generation submitted.');}}catch(err){q('#uxPickerStatus').textContent=err.message;}finally{pickerBusy=false;button.disabled=false;syncReady();}};
  picker.addEventListener('cancel',e=>{if(pickerBusy)e.preventDefault();});picker.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();if(!pickerBusy)picker.close();}});
  // Drafts are data only, scoped to the server's workspace identity. No File bytes.
  function snapshot(){if(!selected)return null;return U.normalizeDraft({version:1,updatedAt:Date.now(),recipe:{preset:selected.id,...continuationPayload(),controls:values(),batch:q('#batch').value,parent_assets:parentAssets,parent_by_input:{...parentByInput},references:attachedReferencePayload()},pendingInputs:['reference','lastReference'].filter(id=>pendingInputs.has(id)||(q('#'+id).files.length&&(id==='reference'?!uploaded:!lastUploaded))),templateHash:recipeTemplateHash});}
  // This remains the sole owner of Create mutation; commands persist before adoption.
  function setupStamp(){return JSON.stringify([workbenchStamp(),referenceEpoch,referencePending,selectionEpoch,recipeTemplateHash,parentByInput,typeof backendActive==='undefined'?null:backendActive]);}
  function setupBusy(){return !!referencePending||!!pickerBusy||!!restoring||!!submitting||!!handoffBusy||typeof backendSwitching!=='undefined'&&!!backendSwitching;}
  function adoptSharedSetup(value,expectedStamp,backendId){
    if(setupBusy()||expectedStamp!==setupStamp())throw Error('Create changed before loading the shared revision. Current inputs were preserved.');
    const draft=U.normalizeDraft(JSON.parse(JSON.stringify(value))),target=catalog?.presets.find(p=>p.id===draft?.recipe.preset);
    if(!draft||draft.pendingInputs.length||!target)throw Error('The shared revision cannot be represented by this editor. Export and inspect it first.');
    if(typeof backendActive==='undefined'||backendId!==backendActive)throw Error('The active backend changed before loading this revision.');
    const controls=draft.recipe.controls,slots=target.reference_slots||[];
    if(draft.templateHash&&target.continuation_capability?.template_sha256!==draft.templateHash)throw Error('The browser catalog has a different graph. Refresh and review before loading.');
    for(const key of Object.keys(controls)){
      const bound=['positive','negative','reference','last_reference'].includes(key)?target[key]:key==='mode'?target.i2v_modes?.some(m=>m.id===controls[key]):controlKeys.includes(key)&&(target[key]||key.endsWith('_name')&&target[key.slice(0,-5)]);
      if(!bound)throw Error('This editor cannot retain control '+key+'. No settings were changed.');
    }
    if(draft.recipe.references.length&&draft.recipe.references.length!==slots.length)throw Error('The saved reference slots do not match this recipe.');
    if(slots.length&&draft.recipe.references.some(r=>!referenceRoles.includes(r.role)))throw Error('The saved reference role is not available in this editor.');
    restoring=true;sharedAdoptionError='';
    try{
      selectPreset(target.id,true,true);
      for(const key of controlKeys){const input=getControl(key);if(input)input.value=Object.hasOwn(controls,key)?controls[key]:'';}
      for(const key of ['positive','negative'])q('#'+key).value=controls[key]||'';
      if(controls.mode)q('#i2vMode').value=controls.mode;
      uploaded=controls.reference||null;lastUploaded=controls.last_reference||null;
      if(slots.length&&draft.recipe.references.length)referenceRecords=draft.recipe.references.map(r=>({...r}));
      parentAssets=[...draft.recipe.parent_assets];parentByInput={...(draft.recipe.parent_by_input||{})};
      continuationState=draft.recipe.continuation?StudioContinuation.normalize(draft.recipe.continuation):null;continuationSource=null;sourceReadError='';
      recipeTemplateHash=draft.templateHash;pendingInputs.clear();q('#batch').value=String(draft.recipe.batch);
      renderReferenceSlots();updateLoraHints();syncCreate();
      const actual=values();for(const key of Object.keys(controls))if(String(actual[key]??'')!==String(controls[key]))throw Error('The editor could not retain control '+key+'. Inspect the Workspace revision and browser backup.');
      draftDirty=true;recipeChanged();
    }catch(error){sharedAdoptionError='Shared setup loading was incomplete. Generate is held; inspect the saved revision and browser backup. '+error.message;throw error;}
    finally{restoring=false;syncReady();}
    saveDraft();if(continuationState)hydrateContinuation();
  }
  window.StudioSetupDraft={capture(){const value=snapshot();if(!value)return null;value.updatedAt=0;value.recipe.parent_by_input=value.recipe.parent_by_input||{};return JSON.parse(JSON.stringify(value));},stamp:setupStamp,busy:setupBusy,adopt:adoptSharedSetup};
  document.dispatchEvent(new Event('studio:setup-draft-ready'));
  function draftKey(){return draftPrefix&&selected?draftPrefix+selected.id:null;}
  function readDraft(key=draftKey()){if(!key)return null;try{const value=U.normalizeDraft(JSON.parse(localStorage.getItem(key)));if(value)knownDrafts.set(key,value.updatedAt);return value;}catch(_){return null;}}
  function saveDraft(){if(restoring||draftPaused||!draftDirty||!draftPrefix||!selected)return;const key=draftKey(),draft=snapshot();if(!draft)return;try{const current=U.normalizeDraft(JSON.parse(localStorage.getItem(key)));if(current&&knownDrafts.has(key)&&knownDrafts.get(key)!==current.updatedAt){draftPaused=true;renderDraftNotice();return;}if(current&&JSON.stringify({...current,updatedAt:0})===JSON.stringify({...draft,updatedAt:0}))return;localStorage.setItem(key,JSON.stringify(draft));knownDrafts.set(key,draft.updatedAt);q('#uxDraftStatus').textContent='Draft saved in this browser · '+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}catch(_){q('#uxDraftStatus').textContent='Browser storage is unavailable. Export this draft or save a named setup.';}}
  function renderDraftNotice(){const draft=readDraft();q('#uxRestoreDraft').hidden=!draft;q('#uxDiscardDraft').hidden=!draft;q('#uxKeepDraft').hidden=!draftPaused;q('#uxDraftStatus').textContent=draftPaused?'Another tab changed the saved draft. Autosave is paused; export yours or keep this tab.':draft?'Saved draft from '+new Date(draft.updatedAt).toLocaleString()+'. Restore it to continue.':'Draft recovery is browser-local. Named setups live in your workspace.';}
  async function restoreDraft(draft){
    if(!draft)return;if(!catalog?.presets.some(p=>p.id===draft.recipe.preset)){announce('This draft needs a recipe that is not in the current catalog.',true);return;}
    restoring=true;let epoch=null;
    try{applySaved(draft.recipe);epoch=selectionEpoch;recipeTemplateHash=draft.templateHash;pendingInputs=new Set(draft.pendingInputs);syncReady();
      if(!selected.reference_slots?.length){const files=[uploaded,lastUploaded].filter(Boolean);if(files.length){const checks=await post('/api/references/check',{files});if(epoch!==selectionEpoch)return;for(const [name,file]of [['reference',uploaded],['lastReference',lastUploaded]])if(file&&!checks.some(c=>c.file===file&&c.available)){pendingInputs.add(name);if(name==='reference')uploaded=null;else lastUploaded=null;releaseInputParent(name);}}}
      syncCreate();announce('Draft restored. Reattach any missing local files, then review before running.');
    }catch(err){if(epoch===selectionEpoch){if(uploaded)pendingInputs.add('reference');if(lastUploaded)pendingInputs.add('lastReference');uploaded=lastUploaded=null;announce('Input availability could not be checked: '+err.message,true);}}
    finally{restoring=false;if(epoch===selectionEpoch)draftDirty=false;syncReady();}
  }
  q('#uxRestoreDraft').onclick=()=>restoreDraft(readDraft());
  q('#uxImportDraftButton').onclick=()=>q('#uxImportDraft').click();
  q('#uxImportDraft').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>131072)throw Error('Draft files must be under 128 KiB.');const draft=U.normalizeDraft(JSON.parse(await file.text()));if(!draft)throw Error('This is not a supported Studio draft.');saveDraft();await restoreDraft(draft);}catch(err){announce(err.message,true);}finally{e.target.value='';}};
  q('#uxDiscardDraft').onclick=()=>{try{const key=draftKey();if(key)localStorage.removeItem(key);knownDrafts.delete(key);draftDirty=false;renderDraftNotice();}catch(_){announce('Browser storage is unavailable.',true);}};
  q('#uxKeepDraft').onclick=()=>{draftPaused=false;readDraft();saveDraft();renderDraftNotice();};
  q('#uxExportDraft').onclick=()=>{const draft=snapshot();if(!draft)return;const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(draft,null,2)],{type:'application/json'}));a.href=url;a.download='studio-draft-'+draft.recipe.preset+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  window.addEventListener('storage',e=>{if(e.key===draftKey()){draftPaused=true;renderDraftNotice();}});
  window.addEventListener('pagehide',saveDraft);
  for(const event of ['input','change'])q('#createView').addEventListener(event,e=>{if(e.target.closest('.editor'))draftDirty=true;syncReady();clearTimeout(draftTimer);draftTimer=setTimeout(saveDraft,350);});
  q('#createView').addEventListener('click',e=>{if(e.target.closest('[data-variant],#randomSeed,[data-ref-clear],[data-ref-up],[data-ref-down]')){draftDirty=true;syncReady();saveDraft();}});
  const originalLoadSetups=loadSetups;loadSetups=async function(){try{localStorage.getItem('studio-storage-probe');}catch(_){serverSetups=await api('/api/setups');renderSaved();return;}return originalLoadSetups();};
  // Explicitly apply a reviewed Prompt Lab text handoff; never infer model bindings.
  const transfer=element('section','panel ux-transfer');transfer.id='uxTransfer';transfer.hidden=true;transfer.innerHTML='<h2>Text from Prompt Lab</h2><p id="uxTransferNotice"></p><pre id="uxTransferPreview"></pre><button id="uxApplyPrompt" class="primary">Apply text to the selected recipe</button><button id="uxDismissPrompt">Dismiss</button>';createHeading.after(transfer);
  let promptHandoff=null;
  q('#uxApplyPrompt').onclick=()=>{if(!promptHandoff||!selected?.positive){announce('Choose a recipe with a text prompt first.',true);return;}saveDraft();q('#positive').value=promptHandoff.positive;if(selected.negative)q('#negative').value=promptHandoff.negative;transfer.hidden=true;draftDirty=true;saveDraft();syncReady();announce('Compiled text applied. '+(!selected.negative&&promptHandoff.negative?'This recipe has no negative-prompt field; the negative text was not applied. ':'')+'References and sampling settings were not transferred. Review before generating.');};q('#uxDismissPrompt').onclick=()=>{transfer.hidden=true;};
  async function initializeDrafts(){try{const identity=await api('/api/identity');draftPrefix='studio-draft-v1:'+identity.workspace+':';renderDraftNotice();try{const raw=sessionStorage.getItem('studio-prompt-handoff');if(raw){sessionStorage.removeItem('studio-prompt-handoff');const handoff=JSON.parse(raw);if(handoff.workspace===identity.workspace&&Date.now()-handoff.createdAt<3600000&&handoff.createdAt<=Date.now()&&typeof handoff.transfer?.positive==='string'&&handoff.transfer.positive.length<=8000){promptHandoff=U.promptTransfer({fields:handoff.transfer,profile:{id:handoff.transfer.profile},recipes:handoff.transfer.recipes});if(!promptHandoff)return;const renderNames=()=>{const named=promptHandoff.recipes.map(id=>catalog?.presets.find(p=>p.id===id)?.name||id);q('#uxTransferNotice').textContent=promptHandoff.notice+(named.length?' Matching recipes: '+named.join(', ')+'. Naming them selects nothing.':'');};renderNames();/* The catalog usually lands after this notice; re-render with names once it does, bounded. */if(!catalog&&typeof setTimeout==='function'){let tries=0;const wait=()=>{if(catalog)renderNames();else if(++tries<60)setTimeout(wait,250);};setTimeout(wait,250);}q('#uxTransferPreview').textContent=promptHandoff.positive+(promptHandoff.negative?'\n\nNegative (applied only when supported):\n'+promptHandoff.negative:'');transfer.hidden=false;showView('create');}}}catch(_){/* Exported briefs remain usable when session storage is disabled. */}}catch(_){q('#uxDraftStatus').textContent='Workspace identity unavailable. Draft storage is disabled until reload.';}}
  async function refreshHome(){if(homeBusy)return;homeBusy=true;q('#uxRefreshHome').disabled=true;try{const result=await Promise.allSettled(['/api/workspace','/api/production','/api/jobs'].map(path=>api(path)));homeErrors=result.map((r,i)=>r.status==='rejected'?['Asset library','Runs','Jobs'][i]+': '+r.reason.message:null).filter(Boolean);homeData={workspace:result[0].status==='fulfilled'?result[0].value:null,plans:result[1].status==='fulfilled'?result[1].value:null,jobs:result[2].status==='fulfilled'?result[2].value:null};homeUpdated=new Date();renderHome();}finally{homeBusy=false;q('#uxRefreshHome').disabled=false;}}
  function renderHome(){if(!homeData)return;const {workspace,plans,jobs:runJobs}=homeData,assets=workspace?.assets||[],s=U.summarize(assets,plans||[],runJobs||[]);q('#uxHomeHealth').textContent=homeErrors.length?'Some data is unavailable. '+homeErrors.join(' · '):'Saved records refreshed '+homeUpdated.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' · execution, creative review and licensing remain separate.';q('#uxHomeHealth').classList.toggle('error',!!homeErrors.length);const signature=JSON.stringify(homeData);if(signature===homeSignature)return;homeSignature=signature;
    q('#uxStats').innerHTML=[['Saved assets',workspace?s.assets:'—','all'],['Awaiting review',workspace?s.unreviewed:'—','unreviewed'],['Keepers',workspace?s.keepers:'—','selected'],['Needs another pass',workspace?s.needsWork:'—','needs_work']].map(([label,value,scope])=>'<button data-ux-scope="'+scope+'"><span>'+label+'</span><b>'+value+'</b><small>Open library →</small></button>').join('');
    const ordered=[...s.reviewPlans,...s.attentionPlans,...s.activePlans,...s.prepared].slice(0,6),seenJobs=new Set((plans||[]).flatMap(p=>(p.stages||[]).map(stage=>stage.job?.id).filter(Boolean)));
    const records=ordered.map(p=>'<a class="ux-desk-row" href="'+(p.state.status==='awaiting_review'&&p.kind==='comparison'?'/review.html?project='+encodeURIComponent(p.id):p.kind==='av'?'/av.html?project='+encodeURIComponent(p.id):p.kind==='voice'?'/voice.html':'/#production')+'" data-ux-project="'+escape(p.id)+'"><span class="ux-state-dot '+escape(p.state.status)+'" aria-hidden="true"></span><span><b>'+escape(p.name)+'</b><small>'+escape(p.state.status.replaceAll('_',' '))+' · '+escape(p.kind)+'</small></span><span aria-hidden="true">↗</span></a>');
    for(const j of [...s.attentionJobs,...s.activeJobs].filter(j=>!seenJobs.has(j.id)).slice(0,3))records.push('<a class="ux-desk-row" href="/#create"><span class="ux-state-dot '+escape(j.status)+'" aria-hidden="true"></span><span><b>'+escape(j.preset_name)+'</b><small>'+escape(j.status)+' · inspect existing record; do not repeat uncertain work</small></span><span aria-hidden="true">↗</span></a>');
    q('#uxAttention').innerHTML=records.join('')||(plans&&runJobs?'<div class="ux-empty"><b>A clear desk.</b><p>Prepare a comparison to test one change, or start with a recipe above.</p><a href="/#create">Prepare your first pass →</a></div>':'<p>Run status is unavailable. Refresh before deciding what to start.</p>');
    const recent=assets.filter(a=>!a.trashed_at).sort((a,b)=>b.created_at-a.created_at).slice(0,6);q('#uxRecent').innerHTML=recent.map(a=>'<button class="ux-recent-card" data-ux-open-asset="'+escape(a.id)+'">'+assetPreview(a)+'<span><b>'+escape(a.title)+'</b><small>'+escape(a.media_type)+' · '+escape(a.review||'unreviewed')+'</small></span></button>').join('')||'<div class="ux-empty panel"><h3>'+(workspace?'Make room for your first asset.':'Asset library is unavailable.')+'</h3><p>Import an existing image or create from a recipe. Sources stay available for the next step.</p><a href="/#assets">Open Asset library →</a></div>';
  }
  q('#uxRefreshHome').onclick=()=>refreshHome();
  document.addEventListener('click',async e=>{try{const close=e.target.closest('[data-ux-close]');if(close){if((close.dataset.uxClose==='uxHandoff'&&handoffBusy)||(close.dataset.uxClose==='uxSourcePicker'&&pickerBusy))return;q('#'+close.dataset.uxClose).close();}const intent=e.target.closest('[data-ux-intent]');if(intent)chooseIntent(intent.dataset.uxIntent);const dest=e.target.closest('[data-ux-destination]');if(dest&&!handoffBusy){handoffIntent=dest.dataset.uxDestination;handoffRecipes();}const hand=e.target.closest('[data-ux-handoff]');if(hand)openHandoff(hand.dataset.uxHandoff);const scope=e.target.closest('[data-ux-scope]');if(scope){assetScope=scope.dataset.uxScope;q('#assetSearch').value='';q('#assetType').value='all';assetSelection.clear();showView('assets');renderAssets();}const open=e.target.closest('[data-ux-open-asset]');if(open){await refreshAssets();openAsset(open.dataset.uxOpenAsset);}const project=e.target.closest('[data-ux-project]');if(project){productionId=project.dataset.uxProject;if(view==='production')renderProduction();}}catch(err){announce(err.message,true);}});
  // Native file input remains the accessible fallback for drag-and-drop imports.
  const drop=element('div','ux-import-drop','<b>Bring existing work into the studio</b><span>Drop up to 32 PNG, JPG or WebP images here, or use Import images.</span>');drop.id='uxImportDrop';q('#assetsView .asset-workspace').before(drop);drop.ondragover=e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();drop.classList.add('dragover');}};drop.ondragleave=()=>drop.classList.remove('dragover');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('dragover');const files=[...e.dataTransfer.files];if(files.length>32||files.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type))){assetMessage('Import up to 32 PNG, JPEG or WebP images. No files were submitted.',true);return;}const transfer=new DataTransfer();files.forEach(f=>transfer.items.add(f));q('#importAssets').files=transfer.files;q('#importAssets').dispatchEvent(new Event('change',{bubbles:true}));};
  q('#importAssets').closest('label').tabIndex=0;q('#importAssets').closest('label').setAttribute('role','button');q('#importAssets').closest('label').onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();q('#importAssets').click();}};
  let overviewPollingAttached=false;
  function attachOverviewPolling(){
    if(overviewPollingAttached||!window.StudioReadPoller)return;
    const readHome=refreshHome;overviewPollingAttached=true;
    window.StudioReadPoller.register('overview',{interval:12000,shouldPoll:()=>view==='home',task:readHome});
    refreshHome=(...args)=>window.StudioReadPoller.refresh('overview',...args);
  }
  window.addEventListener('studio-read-poller-ready',attachOverviewPolling);attachOverviewPolling();
  showView(U.normalizeView(location.hash));initializeDrafts();
})();
