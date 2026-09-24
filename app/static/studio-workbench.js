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
  let intentId='create',handoffId=null,handoffIntent='edit',handoffBusy=false,pickerBusy=false,pickerLoading=false,sourcePickerEpoch=0,handoffEpoch=0;
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
  // A recipe's bracketed fills (who, the pose, the clothes) are short fields that write the prepared wording for you; the
  // paragraph stays visible and editable underneath, and a hand edit stops the fields from rewriting it (#422 slice A).
  const fillsBlock=element('div','ux-fills');fillsBlock.id='uxFills';fillsBlock.hidden=true;q('#positiveWrap').before(fillsBlock);
  let fillsPreset=null,fillsSource=null,fillsTemplate='',fillsAssembled=null,transferredFills=null;
  const fillInputs=()=>[...fillsBlock.querySelectorAll('[data-ux-fill]')];
  function fillValues(){return Object.fromEntries(fillInputs().map(input=>[input.dataset.uxFill,input.value]));}
  function fillsKey(){return continuationState?'studio-fills:'+continuationState.source_asset_id:null;}
  function rememberedFills(){const key=fillsKey();if(!key)return{};try{const value=JSON.parse(localStorage.getItem(key)||'{}');return value&&typeof value==='object'?value:{};}catch(e){return{};}}
  function rememberFills(){const key=fillsKey();if(!key)return;const remembered={...rememberedFills(),...fillValues()};for(const [placeholder,value]of Object.entries(fillValues())){const meaning=StudioContinuation.fillMeaning(placeholder);if(meaning)remembered['@'+meaning]=value;}try{localStorage.setItem(key,JSON.stringify(remembered));}catch(e){}}
  function assembleFills(){
    const text=StudioContinuation.assemble(fillsTemplate,fillValues());fillsAssembled=text;rememberFills();
    if(q('#positive').value!==text){q('#positive').value=text;q('#positive').dispatchEvent(new Event('input',{bubbles:true}));if(typeof updateReady==='function')updateReady();}
  }
  function syncFills(){
    const spec=selected&&typeof StudioContinuation!=='undefined'?StudioContinuation.fills(selected,selected.continuation_prompt):[];
    if(!spec.length){fillsBlock.hidden=true;fillsPreset=null;fillsSource=null;return;}
    const current=q('#positive').value,carries=spec.every(f=>current.includes(f.placeholder)),source=continuationState?.source_asset_id||null;
    // The block belongs to one recipe and one source picture: another source (or leaving the continuation) starts from that
    // source's remembered answers, never from the previous character's.
    if(fillsPreset!==selected.id||fillsSource!==source||(carries&&current!==fillsTemplate)){
      // The template is the prepared wording: the textarea while it still carries every fill, otherwise the recipe's continuation
      // wording with `{source}` resolved the way Continue with this resolves it (the literal token must never reach the model).
      fillsPreset=selected.id;fillsSource=source;fillsTemplate=carries?current:String(StudioContinuation.promptFor(selected,continuationSource)||'');fillsAssembled=null;const remembered={...rememberedFills(),...(transferredFills?.preset===selected.id&&transferredFills.source===source?transferredFills.values:{})};
      fillsBlock.innerHTML='<p class="muted">Answer these in a few words; they write the wording below for you. The paragraph stays editable.</p>'+spec.map(f=>'<label>'+escape(f.label)+'<input data-ux-fill="'+escape(f.placeholder)+'" placeholder="'+escape(f.example?'e.g. '+f.example:'')+'" value="'+escape(remembered[f.placeholder]||'')+'" autocomplete="off"></label>').join('')+'<p id="uxFillsNote" class="muted" hidden>The wording below is not what the fields would write (restored, or edited by hand), so they leave it alone. <button type="button" id="uxRebuildFills">Rebuild it from the fields</button></p>';
    }
    fillsBlock.hidden=!fillsTemplate;if(fillsBlock.hidden)return;
    if(carries&&Object.values(fillValues()).some(v=>String(v).trim()))assembleFills();
    // Wording the fields did not write (a restored draft, a bracket answered in the paragraph, a hand edit) stays until Rebuild is
    // pressed; an empty box, the template itself and the recipe's own example text are not hand edits.
    const text=q('#positive').value,detached=!carries&&!!text.trim()&&text!==fillsAssembled&&text!==String(selected.defaults?.positive||'');
    const note=q('#uxFillsNote');if(note)note.hidden=!detached;
  }
  fillsBlock.addEventListener('input',e=>{if(!e.target.matches('[data-ux-fill]'))return;const note=q('#uxFillsNote');if(note&&!note.hidden)return;assembleFills();});
  fillsBlock.addEventListener('click',e=>{if(e.target.closest('#uxRebuildFills'))assembleFills();});
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
  after('selectPreset',()=>{sharedAdoptionError='';selectionEpoch++;draftDirty=false;pendingInputs.clear();dismissSecondPicture();syncCreate();renderDraftNotice();});
  after('applySaved',()=>{if(!restoring)draftDirty=true;hydrateContinuation();});after('applyRecipe',()=>{draftDirty=true;syncReady();saveDraft();});
  const originalSelectPreset=selectPreset;selectPreset=function(...args){saveDraft();return originalSelectPreset(...args);};
  after('renderSelected',syncCreate);after('updateReady',syncReady);
  const originalUploadRoleFile=uploadRoleFile;uploadRoleFile=async function(...args){const epoch=referenceEpoch,applied=await originalUploadRoleFile(...args);if(applied&&epoch===referenceEpoch){draftDirty=true;saveDraft();}return applied;};
  // Collapse six overlapping output actions into one reviewed, compatible handoff.
  after('renderJobs',()=>{for(const card of q('#gallery').querySelectorAll('.imageCard')){const actions=[...card.querySelectorAll('.reference-output')];if(!actions.length)continue;const first=actions.shift();first.textContent='Continue with this →';first.classList.add('primary');actions.forEach(button=>button.remove());}});
  function syncCreate(){if(!selected)return;q('#uxRecipeLabel').textContent=selected.name;referenceHeading.hidden=false;q('#uxSourceNote').hidden=false;q('#uxFindReferenceRecipes').hidden=takesSource();syncReady();}
  let readinessMarkup='',readinessChecking=false;
  const readinessLabels={recipes:'Choose a recipe',models:'Open Models & setup',dependencies:'Show required files',references:'Show the empty slot',parameters:'Review motion settings',continuation:'Show the source panel','source-back':'Put the source back',wording:'Write the description',fills:'Fill in the wording',second:'Decide about this picture',source:'Choose your picture','pose-position':'Review joint coordinates','pose-size':'Show the pose editor'};
  // A continuation blocker names a control; the button beside it performs or shows that repair, nothing more.
  const continuationActions={source:'source-back',inputs:'references',board:'references',wording:'wording'};
  function readinessItems(){
    const required=[...pendingInputs].filter(id=>!q('#'+id).files.length&&(id==='reference'?!uploaded:!lastUploaded));
    // A continuation's own blockers already name the unreplaced fills; the plain route needs the generic line (#367).
    const unfilled=!continuationState&&selected&&typeof StudioContinuation!=='undefined'?StudioContinuation.unfilled(selected,q('#positive')?.value):[];
    // A recipe that transforms a picture (a board with a picture to keep, or a declared restyle/combine) needs it on every route.
    const sourceKey=selected?.last_reference?'lastReference':selected?.reference?'reference':null;
    // On the continuation route the continuation's own blocker names the detached source (Put the source back); do not double it.
    const sourceMissing=!continuationState&&!!sourceKey&&!!(selected.reference_board&&selected.last_reference||selected.continuation_operation)&&!(sourceKey==='lastReference'?lastUploaded:uploaded)&&!q('#'+sourceKey)?.files?.length;
    const items=U.readinessItems({preset:selected,online,schemaAvailable,workerAlive,missing:missingByPreset[selected?.id]||[],referencesReady:referencesReady()&&!required.length,switching:typeof backendSwitching!=='undefined'&&backendSwitching,backend:typeof backendActive!=='undefined'?backendActive:null,busy:submitting||handoffBusy||pickerBusy||restoring||pairActionBusy||poseBusy,unfilled,sourceMissing});
    if(posePositionDirty())items.push({code:'pose-position',message:'Set the typed joint position or reset its fields before continuing.',action:'pose-position'});
    const staleGuide=poseSizeHold();if(staleGuide)items.push({code:'pose-size',message:staleGuide,action:'pose-size'});
    const modeBlock=i2vModeBlocker();if(modeBlock)items.push({code:'motion',message:modeBlock,action:'parameters'});
    const specific=continuationBlockerItems().map(item=>({code:'continuation-'+item.code,message:item.message,action:continuationActions[item.code]||'continuation'}));
    // The continuation names the exact empty slot; the generic reference line would only repeat it.
    if(specific.some(item=>['continuation-board','continuation-inputs','continuation-source'].includes(item.code)))items.splice(items.findIndex(item=>item.code==='references')>>>0,1);
    items.push(...specific);
    if(secondPicture)items.push({code:'second',message:selected?.reference_slots?.length>1?'Picture 1 remains your source. Choose another slot or explicitly start from the extra picture.':'You added a second picture, but this recipe reads one. Say what it is for.',action:'second'});
    if(sharedAdoptionError)items.push({code:'shared-setup',message:sharedAdoptionError,action:null});
    if(continuationState&&!continuationSource)items.push({code:'source',message:sourceReadError||'Checking the retained source metadata…',action:'continuation'});
    return{items,required};
  }
  function syncReady(){
    if(!q('#uxRunSummary'))return;
    // Resize/refresh the pose canvas before readiness so a typed draft is not a stale blocker for one tick.
    syncContinuation();syncFills();syncCombinePair();syncPoseEditor();
    const {items,required}=readinessItems();
    q('#generate').disabled=items.length>0;
    const markup=items.map(item=>'<div class="ux-blocker" data-readiness-code="'+item.code+'"><p>'+escape(item.message)+'</p>'+(readinessLabels[item.action]?'<button type="button" data-ux-resolve="'+item.action+'">'+readinessLabels[item.action]+'</button>':'')+'</div>').join('');
    // Polling identical evidence must not replace a focused action or announce the same status again.
    if(markup!==readinessMarkup){readinessMarkup=markup;q('#uxBlockers').innerHTML=markup;}
    const summary=items.length?items.length+' condition'+(items.length===1?' needs':'s need')+' attention. Your draft remains editable.':'No blockers reported by the current checks. Generate still validates the request on the server.';
    if(q('#uxReadinessSummary').textContent!==summary)q('#uxReadinessSummary').textContent=summary;
    q('#uxRecheckReadiness').disabled=readinessChecking;
    q('#uxRunSummary').textContent=selected?selected.name+' · '+q('#batch').value+' output(s) · '+(selected.backend_id||'primary')+' environment':'Choose a recipe to prepare your next run.';
    syncSourceAvailability();
    const refs=selected?.reference_slots?.length?referenceRecords.filter(r=>r.file&&!r.missing).length+(selected.last_reference&&lastUploaded?1:0):(uploaded?1:0)+(lastUploaded?1:0);
    q('#uxSourceNote').textContent=!takesSource()?NO_SOURCE_SLOT:refs?refs+' attached reference(s) · '+parentAssets.length+' source asset(s) retained in lineage.':required.length?'Saved input is unavailable. Reattach it; no example fallback will be used.':selected?.reference_slots?.length?'Assign a role to each image. Required slots must be filled.':continuationState?'The continuation source is not attached. Use Put the source back, or reopen Continue with this asset.':(selected?.reference_board&&selected?.last_reference||selected?.continuation_operation?'No personal source attached. Choose your picture; this recipe never runs the authored example picture.':'No personal source attached. This recipe may use its authored example until replaced.');
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
    if(action==='pose-position')target=q('#uxPoseX');
    // A disabled button cannot be the next step (#952): show the reason beside it instead.
    if(action==='pose-size')target=q('#uxPoseUse').disabled?q('#uxPoseReason'):q('#uxPoseUse');
    if(action==='parameters')target=q('#i2vMode')||getControl('frames');
    if(action==='wording'||action==='fills')target=(!fillsBlock.hidden&&fillInputs().find(input=>!input.value.trim()))||q('#positive');
    if(action==='source')target=q(selected?.last_reference?'#lastReference':'#reference');
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
  // A Combine is two pictures: show them next to each other, in the order the model reads them, with the recipe's own
  // labels; an empty tile offers the same repair the readiness list does (#422 slice A).
  const pairPanel=element('section','ux-pair');pairPanel.id='uxPair';pairPanel.hidden=true;q('#selectedPreset').before(pairPanel);
  let pairMarkup='';
  const imageNumber=label=>Number(/\(image (\d)\)/.exec(String(label||''))?.[1])||0;
  function syncCombinePair(){
    const combine=!!selected&&(selected.continuation_capability?.operation==='combine'||selected.continuation_operation==='combine')&&!!selected.reference_board&&!!selected.last_reference;
    pairPanel.hidden=!combine;if(!combine){pairMarkup='';syncCombineEngines();syncCombineResults();return;}
    const board=referenceRecords[0],boardFile=board?.file&&!board.missing?board.file:null,keepAsset=continuationState?.source_asset_id||null;
    const tiles=[{label:selected.reference_board_label||'Pose picture',n:imageNumber(selected.reference_board_label)||2,src:boardFile?'/api/uploads/'+encodeURIComponent(boardFile):null,empty:'No pose picture yet.',action:'board',button:'Pull it from the library'},
                 {label:selected.last_reference_label||'Picture to keep',n:imageNumber(selected.last_reference_label)||1,src:lastUploaded?'/api/uploads/'+encodeURIComponent(lastUploaded):keepAsset?'/api/assets/'+encodeURIComponent(keepAsset)+'/file':null,empty:'No picture to keep yet.',action:'keep',button:'Choose your picture'}].sort((a,b)=>a.n-b.n);
    const markup=tiles.map(t=>'<figure class="ux-pair-tile">'+(t.src?'<img src="'+escape(t.src)+'" alt="'+escape(t.label)+'">':'<div class="ux-pair-empty"><span>'+escape(t.empty)+'</span><button type="button" data-ux-pair="'+t.action+'">'+escape(t.button)+'</button></div>')+'<figcaption>'+escape(t.label)+'</figcaption></figure>').join('');
    if(markup!==pairMarkup){pairMarkup=markup;pairPanel.innerHTML='<span class="eyebrow">THE TWO PICTURES, IN THE ORDER THE MODEL READS THEM</span><div class="ux-pair-tiles">'+markup+'</div>';}
    syncCombineEngines();syncCombineResults();
  }
  pairPanel.onclick=e=>{
    const button=e.target.closest('[data-ux-pair]');if(!button)return;
    if(button.dataset.uxPair==='board')q('#uxPullAsset').click();
    else if(!focusReadinessTarget(q('#lastReference')))q('#uxPullAsset').click();
  };
  // One experiment retains semantic source roles; image numbers and graph bindings belong to the selected recipe.
  const enginePanel=element('section','ux-combine-engines');enginePanel.id='uxCombineEngines';enginePanel.hidden=true;pairPanel.after(enginePanel);
  const resultPanel=element('section','ux-pair-results');resultPanel.id='uxPairResults';resultPanel.hidden=true;runBox.after(resultPanel);
  const combineWording=new Map();let engineMarkup='',resultMarkup='',pairActionBusy=false;
  function currentPair(){return{preset_id:selected?.id,controls:values(),continuation:continuationState,references:attachedReferencePayload()};}
  function pairKey(){const record=currentPair();return JSON.stringify([record.continuation?.source_sha256||record.controls.last_reference,(record.references||[]).filter(r=>r.file).map(r=>r.sha256||r.file)]);}
  function combineAnswers(){const saved=rememberedFills(),answers=Object.fromEntries(['who','pose','clothes','outfit'].map(key=>[key,saved['@'+key]||'']));for(const [placeholder,value]of Object.entries(fillValues())){const meaning=StudioContinuation.fillMeaning(placeholder);if(meaning)answers[meaning]=value;}return answers;}
  function combineBusy(){return submitting||handoffBusy||pickerBusy||restoring||referencePending>0||pairActionBusy||poseBusy||posePositionDirty();}
  function syncCombineEngines(){
    enginePanel.hidden=!continuationState||!StudioContinuation.combineKind(selected);if(enginePanel.hidden){engineMarkup='';return;}
    const options=StudioContinuation.destinations('combine',catalog.presets,continuationSource),busy=combineBusy();
    const markup='<h3>Try this pair with another recipe</h3><p>Pictures and answers stay here. Each recipe keeps its edited wording. Generate starts the next run.</p><div class="ux-engine-options">'+options.map(p=>{
      const reason=StudioContinuation.combineSwitchReason(selected,p,referenceRecords)||p.runtime_block||'',run=jobs.find(j=>j.preset_id===p.id&&j.status==='completed'&&Number(j.elapsed_seconds)>0);
      const label=({'combine-klein':'Klein 4B','combine-klein-9b':'Klein 9B · pose','combine-klein-9b-depth':'Klein 9B · depth','combine-klein-9b-copypose':'Klein 9B · Copy Pose','combine-klein-9b-replace':'Klein 9B · replace','combine-klein-9b-skeleton':'Klein 9B · skeleton'})[p.id]||p.name;
      const timing=run?'Last completed run: '+durationLabel(run.elapsed_seconds)+' · '+(run.batch_count||1)+' output(s)':'No completed timing yet';
      return '<button type="button" data-ux-engine="'+escape(p.id)+'" aria-pressed="'+(p.id===selected.id)+'" '+(reason||busy?'disabled':'')+' title="'+escape(reason||p.name)+'"><b>'+escape(label)+'</b><small>'+escape(timing)+'</small>'+(reason?'<small>'+escape(reason)+'</small>':'')+'</button>';
    }).join('')+'</div>';
    if(markup!==engineMarkup){engineMarkup=markup;enginePanel.innerHTML=markup;}
  }
  enginePanel.onclick=e=>{
    const button=e.target.closest('[data-ux-engine]');if(!button||button.disabled||combineBusy()||button.dataset.uxEngine===selected.id)return;
    try{switchCombineEngine(button.dataset.uxEngine);}catch(error){announce(error.message,true);}
  };
  // The one path that moves this pair to another Combine recipe: the engine buttons and the pose editor
  // both take it, so pictures, lineage and the three answers survive a switch the same way in both.
  function switchCombineEngine(presetId,guide=null){
      const target=catalog.presets.find(p=>p.id===presetId),reason=guide?StudioContinuation.combinePoseReplacementReason(selected,target,referenceRecords):StudioContinuation.combineSwitchReason(selected,target,referenceRecords);if(reason||target?.runtime_block)throw Error(reason||target.runtime_block);
      if(!continuationSource||lastUploaded!==continuationState.reference_file)throw Error('Put the source back before changing recipes.');
      if(['reference','lastReference'].some(id=>q('#'+id).files?.length))throw Error('Finish attaching the chosen picture before changing recipes.');
      const replacingPose=!!guide&&selected.id!==target.id;
      const source=continuationSource,prepared=StudioContinuation.initial(source,target,'combine',lastUploaded),answers=replacingPose?StudioContinuation.combineGuideAnswers(combineAnswers()):combineAnswers(),mapped=StudioContinuation.combineFillValues(target,answers);
      const identity=pairKey(),oldWords=q('#positive').value,manual=q('#uxFillsNote')&&!q('#uxFillsNote').hidden;
      if(manual)combineWording.set(identity+'|'+selected.id,oldWords);else combineWording.delete(identity+'|'+selected.id);
      const previous=guide?referenceRecords[0]?.parent_asset:null,refs=StudioContinuation.combineReferences(target,guide?[guide]:referenceRecords),parents=[...parentAssets],inputs={...parentByInput},prior=values(),batch=q('#batch').value,keep=lastUploaded;
      if(guide)Object.assign(refs[0],guide,{parent_asset:null,missing:false});
      const restored=guide?undefined:combineWording.get(identity+'|'+target.id),positive=restored??StudioContinuation.assemble(prepared.positive,mapped);
      rememberFills();transferredFills={preset:target.id,source:source.asset_id,values:mapped};
      selectPreset(target.id,true,true);continuationState=prepared.claim;continuationSource=source;lastUploaded=keep;uploaded=null;parentAssets=parents;parentByInput=inputs;referenceRecords=refs;
      if(previous!==source.asset_id)releaseParentAsset(previous);
      q('#positive').value=positive;if(selected.negative)q('#negative').value=prepared.negative;
      for(const key of ['seed','width','height']){const input=getControl(key);if(input&&prior[key]!=null)input.value=prior[key];}q('#batch').value=batch;
      fillsPreset=null;renderReferenceSlots();syncFills();if(restored===undefined)fillsAssembled=positive;transferredFills=null;
      rememberFills();draftDirty=true;saveDraft();updateReady();recipeChanged();scheduleTimeEstimate();
      const note=restored!==undefined?'Your edited wording for this recipe is restored. ':replacingPose?'Describe this pose in the wording; the old pose picture’s description was not kept. ':'The wording now uses this recipe’s image order. ';
      announce((guide?'Picture 1 is now the drawing, ':'Same pictures, ')+target.name+'. '+note+'Review it, then Generate.');
      return target;
  }
  // A pose you draw here becomes the skeleton recipe's image 1: a coloured stick figure on black, the input that
  // carried the pose on 3 of 3 research seeds. Drawing and rendering submit nothing; Generate stays your press (#444).
  const POSE_RECIPE='combine-klein-9b-skeleton',POSE_GRID=8,POSE_LIMITS=[64,1536],POSE_DISPLAY=320,POSE_GRAB=18,POSE_UNDO=60;
  const posePanel=element('section','ux-pose-editor');posePanel.id='uxPoseEditor';posePanel.hidden=true;pairPanel.after(posePanel);
  posePanel.innerHTML='<h3>Draw the pose</h3><p>Drag a joint, or pick one below and nudge it with the arrow keys (1 %, or 5 % with Shift). Use this pose puts the drawing on Picture 1; nothing runs until you press Generate.</p>'
    +'<div class="ux-pose-layout"><canvas id="uxPoseCanvas" tabindex="0" role="img" aria-label="Pose skeleton. Drag a joint, or pick one in the joint list and use the arrow keys."></canvas>'
    +'<div class="ux-pose-side"><label for="uxPoseStart">Start from<select id="uxPoseStart"><option value="">Keep this drawing</option>'
    +StudioPoseEditor.PRESETS.map(p=>'<option value="'+escape(p.id)+'">'+escape(p.label)+'</option>').join('')+'</select></label>'
    +'<div id="uxPoseJoints" class="ux-pose-joints" role="group" aria-label="Joints"></div>'
    +'<fieldset class="ux-pose-position"><legend id="uxPosePositionLabel">Joint position (pixels)</legend><label for="uxPoseX">X<input id="uxPoseX" type="number" min="0" step="0.01" inputmode="decimal"></label><label for="uxPoseY">Y<input id="uxPoseY" type="number" min="0" step="0.01" inputmode="decimal"></label><button type="button" id="uxPosePositionApply">Set joint position</button><button type="button" id="uxPosePositionReset">Reset fields</button></fieldset>'
    +'<div class="ux-pose-actions"><button type="button" id="uxPoseUnknown">Mark unknown</button><button type="button" id="uxPoseUndo">Undo</button><button type="button" id="uxPoseRedo">Redo</button><button type="button" id="uxPoseUse" class="primary" aria-describedby="uxPoseReason">Use this pose</button></div>'
    +'<p id="uxPoseReason" class="muted"></p><p id="uxPoseStatus" role="status"></p></div></div>';
  let posePoints=null,poseHome=null,poseSource='',poseLoading='',poseCanvas={width:1024,height:1536},poseTimeline=StudioPoseEditor.timeline(POSE_UNDO),poseJoint=0,poseBusy=false,poseDrag=-1,poseSignature='',posePositionSignature='';
  const poseStatus=text=>{q('#uxPoseStatus').textContent=text;};
  // The canvas the recipe will actually render at: the width and height controls when they are usable, else the recipe's own.
  function poseCanvasSize(){
    const read=key=>{const value=Number(getControl(key)?.value);return Number.isFinite(value)&&value>=POSE_LIMITS[0]&&value<=POSE_LIMITS[1]&&!(value%POSE_GRID)?Math.round(value):0;};
    return{width:read('width')||1024,height:read('height')||1536};
  }
  function poseDisplaySize(){
    const ratio=poseCanvas.width/poseCanvas.height;
    return ratio>=1?{width:POSE_DISPLAY,height:Math.max(1,Math.round(POSE_DISPLAY/ratio))}:{width:Math.max(1,Math.round(POSE_DISPLAY*ratio)),height:POSE_DISPLAY};
  }
  // Undo and redo carry remembered positions with the drawing, so restoring an unknown joint follows the
  // reviewed geometry rather than a later edit. A new authored edit clears only the abandoned redo branch.
  function pushPose(){poseTimeline.record(posePoints,poseHome);}
  function poseAt(event){const rect=q('#uxPoseCanvas').getBoundingClientRect();
    return{x:(event.clientX-rect.left)/(rect.width||1)*poseCanvas.width,y:(event.clientY-rect.top)/(rect.height||1)*poseCanvas.height};}
  function drawPose(){
    const el=q('#uxPoseCanvas'),ctx=el&&el.getContext&&el.getContext('2d');if(!ctx||!posePoints)return;
    const sx=el.width/poseCanvas.width,sy=el.height/poseCanvas.height,stroke=Math.max(3,Math.round(Math.min(el.width,el.height)/48));
    ctx.fillStyle='#000';ctx.fillRect(0,0,el.width,el.height);ctx.lineCap='round';ctx.lineWidth=stroke;
    // A joint marked unknown is omitted, and so is every limb that touches it: exactly what the server renders.
    // Limb colours follow the renderer this recipe's guide is drawn with (the SDXL OpenPose drawing shades each limb).
    for(const [from,to,colour] of StudioPoseEditor.limbColours(StudioPoseEditor.guideRenderer(selected))){const a=posePoints[from],b=posePoints[to];if(!a||!b)continue;
      ctx.strokeStyle=colour;ctx.beginPath();ctx.moveTo(a.x*sx,a.y*sy);ctx.lineTo(b.x*sx,b.y*sy);ctx.stroke();}
    posePoints.forEach((point,index)=>{if(!point)return;
      ctx.beginPath();ctx.arc(point.x*sx,point.y*sy,stroke,0,Math.PI*2);ctx.fillStyle=StudioPoseEditor.COLORS[index];ctx.fill();
      if(index===poseJoint){ctx.strokeStyle='#ffffff';ctx.lineWidth=2;ctx.stroke();ctx.lineWidth=stroke;}});
  }
  // The joint buttons are built once and then only updated: rebuilding them would take the keyboard focus away mid-edit.
  function renderPoseJoints(){
    const list=q('#uxPoseJoints');
    if(!list.children.length)list.innerHTML=StudioPoseEditor.LABELS.map((label,index)=>'<button type="button" data-ux-joint="'+index+'"><span class="ux-pose-swatch" style="background:'+StudioPoseEditor.COLORS[index]+'"></span><b>'+escape(label)+'</b><small></small></button>').join('');
    [...list.children].forEach((button,index)=>{button.setAttribute('aria-pressed',String(index===poseJoint));
      button.querySelector('small').textContent=posePoints&&posePoints[index]?'':'unknown';});
  }
  // Why Use this pose cannot run right now, in the words on screen. Empty means it can.
  function poseBlockedReason(){
    if(!selected)return 'Choose a Combine recipe first.';
    if(StudioPoseEditor.known(posePoints||[])<2)return 'Mark at least two joints: a guide with fewer draws no limb.';
    if(poseBusy)return 'The drawing is being rendered.';
    if(posePositionDirty())return 'Set the typed joint position or reset its fields before continuing.';
    if(combineBusy())return 'Finish the attachment in progress first.';
    if(selected.id===POSE_RECIPE||StudioPoseEditor.drawsGuide(selected))return '';
    const target=catalog?.presets.find(p=>p.id===POSE_RECIPE);
    if(!target)return 'The drawn-skeleton recipe is not in this catalog.';
    if(!continuationState||!continuationSource)return 'Open this pair through Continue with this, then draw the pose.';
    if(lastUploaded!==continuationState.reference_file)return 'Put the character source back before replacing the pose picture.';
    if(['reference','lastReference'].some(id=>q('#'+id).files?.length))return 'Finish attaching the chosen picture first.';
    return StudioContinuation.combinePoseReplacementReason(selected,target,referenceRecords)||target.runtime_block||'';
  }
  // The panel serves every Combine recipe and any recipe that declares its own drawn-guide slot (an SDXL skeleton recipe).
  function poseActive(){return !!selected&&(!!StudioContinuation.combineKind(selected)||StudioPoseEditor.drawsGuide(selected));}
  // A guide drawn for another Width/Height would be stretched to this canvas; drawing it again at this size clears the hold (#844).
  // The hold promises a resize only when the editor holds the guide's own drawing (#947), and names the blocker first when
  // the button is disabled (#952).
  function poseSizeHold(){return poseActive()?StudioPoseEditor.guideSizeReason(referenceRecords,poseCanvasSize(),selected.id!==POSE_RECIPE&&!StudioPoseEditor.drawsGuide(selected)?'Replace pose picture with drawing':'Use this pose',{artifact:poseSource,loading:poseLoading,blocked:poseBlockedReason()}):'';}
  function posePositionDirty(){
    if(!poseActive()||!posePoints?.[poseJoint]||posePositionSignature!==JSON.stringify([poseJoint,posePoints[poseJoint],poseCanvas]))return false;
    try{const value=StudioPoseEditor.positionInput(q('#uxPoseX').value,q('#uxPoseY').value,poseCanvas),point=posePoints[poseJoint];
      return value.x!==Math.round(point.x*100)/100||value.y!==Math.round(point.y*100)/100;
    }catch(_){return true;}
  }
  function syncPosePosition(){
    const point=posePoints?.[poseJoint],signature=JSON.stringify([poseJoint,point,poseCanvas]);
    q('#uxPosePositionLabel').textContent=StudioPoseEditor.LABELS[poseJoint]+' position (pixels)';
    for(const key of ['x','y']){
      const input=q(key==='x'?'#uxPoseX':'#uxPoseY');input.max=key==='x'?poseCanvas.width:poseCanvas.height;
      input.disabled=poseBusy||!point;
      // Readiness polling must not replace partially typed coordinates for the same joint.
      if(signature!==posePositionSignature){input.value=point?Math.round(point[key]*100)/100:'';input.removeAttribute('aria-invalid');}
    }
    posePositionSignature=signature;q('#uxPosePositionApply').disabled=poseBusy||!point;
    q('#uxPosePositionReset').disabled=poseBusy||!posePositionDirty();
  }
  function syncPoseActions(){
    const reason=poseBlockedReason(),use=q('#uxPoseUse'),unknown=q('#uxPoseUnknown'),undo=q('#uxPoseUndo'),redo=q('#uxPoseRedo');
    const replacing=selected?.id!==POSE_RECIPE&&!StudioPoseEditor.drawsGuide(selected);
    use.textContent=replacing?'Replace pose picture with drawing':'Use this pose';
    use.disabled=!!reason;use.title=reason||'Renders the drawing and puts it on Picture 1.';
    q('#uxPoseReason').textContent=reason||poseSizeHold()||(replacing?'Replaces Picture 1 and selects the skeleton recipe. Your character stays. Describe this pose before Generate; the old pose picture’s wording is not kept.':'');
    const positionPending=posePositionDirty();
    q('#uxPoseStart').disabled=poseBusy||positionPending;syncPosePosition();
    q('#uxPoseJoints').querySelectorAll('button').forEach(button=>{button.disabled=poseBusy||positionPending;});
    const named=StudioPoseEditor.LABELS[poseJoint].toLowerCase(),drawn=!!(posePoints&&posePoints[poseJoint]);
    unknown.textContent=(drawn?'Mark ':'Restore ')+named;unknown.title=drawn?'Leaves it out of the guide, with its limbs.':'Puts it back where it last was.';
    unknown.disabled=poseBusy||positionPending;
    undo.disabled=poseBusy||positionPending||!poseTimeline.canUndo;redo.disabled=poseBusy||positionPending||!poseTimeline.canRedo;
    undo.title=poseTimeline.canUndo?'Steps back one change.':'Nothing to undo yet.';redo.title=poseTimeline.canRedo?'Restores the change just stepped back.':'Nothing to redo yet.';
    if(poseBusy)unknown.title=undo.title=redo.title='The drawing is being rendered.';
  }
  function syncPoseEditor(){
    const active=poseActive();
    posePanel.hidden=!active;if(!active)return;
    const next=poseCanvasSize();
    if(!posePoints){posePoints=StudioPoseEditor.fromPreset('standing',next);poseHome=StudioPoseEditor.fromPreset('standing',next);poseTimeline.reset();poseCanvas=next;}
    else if(next.width!==poseCanvas.width||next.height!==poseCanvas.height){
      // Both history directions follow the canvas, so undo or redo cannot restore old-canvas pixels.
      poseTimeline.resize(poseCanvas,next);
      posePoints=StudioPoseEditor.resize(posePoints,poseCanvas,next);poseHome=StudioPoseEditor.resize(poseHome,poseCanvas,next);poseCanvas=next;}
    const el=q('#uxPoseCanvas'),display=poseDisplaySize();
    const signature=JSON.stringify([posePoints,poseCanvas,poseJoint,display]);
    if(el.width!==display.width||el.height!==display.height){el.width=display.width;el.height=display.height;poseSignature='';}
    if(signature!==poseSignature){poseSignature=signature;renderPoseJoints();drawPose();}
    syncPoseActions();loadPoseSource();
  }
  // A guide restored from a saved setup, a draft or a same-tab setup load brings its picture back but not its drawing.
  // Read the drawing behind it (its artifact_id) into the editor, so Use this pose redraws that pose and never silently
  // replaces it with whatever figure the editor held (#947). One read per guide; a failure leaves the hold's fallback wording.
  const poseSourceFailed=new Set();
  function loadPoseSource(){
    const guide=StudioPoseEditor.drawnGuide(referenceRecords),id=guide?.artifact_id;
    if(!guide||!/^[a-f0-9]{64}$/.test(id||'')||id===poseSource||id===poseLoading||poseSourceFailed.has(id)||poseBusy||poseDrag>=0||posePositionDirty())return;
    poseLoading=id;let loaded=null;
    api('/api/pose/artifacts/'+id).then(value=>{loaded=StudioPoseEditor.fromArtifact(value,guide);}).catch(()=>{poseSourceFailed.add(id);}).then(()=>{
      if(poseLoading===id)poseLoading='';
      // A newer guide, a render in flight or an unfinished edit wins; a later sync reads the guide again.
      if(loaded&&StudioPoseEditor.drawnGuide(referenceRecords)?.artifact_id===id&&!poseBusy&&poseDrag<0&&!posePositionDirty()&&poseActive()){
        pushPose();poseSource=id;poseEdit(StudioPoseEditor.adopt(posePoints,StudioPoseEditor.resize(loaded,guide,poseCanvas)));
        poseStatus('The attached pose guide’s drawing is back in the editor. Nothing was submitted.');
      }else if(loaded===null)poseStatus('The drawing behind the attached pose guide could not be read. The picture stays attached.');
      syncReady();
    });
  }
  function poseEdit(next,remember=true){
    posePoints=next;if(remember)poseHome=poseHome.map((point,index)=>posePoints[index]||point);
    poseSignature='';renderPoseJoints();drawPose();syncPoseActions();
  }
  function applyPosePosition(){
    if(poseBusy||!posePoints?.[poseJoint])return;
    try{
      const point=StudioPoseEditor.positionInput(q('#uxPoseX').value,q('#uxPoseY').value,poseCanvas),next=StudioPoseEditor.move(posePoints,poseJoint,point.x,point.y,poseCanvas);
      if(JSON.stringify(StudioPoseEditor.serialize(next,poseCanvas))===JSON.stringify(StudioPoseEditor.serialize(posePoints,poseCanvas))){posePositionSignature='';syncReady();poseStatus('The joint is already at that position.');return;}
      pushPose();poseEdit(next);syncReady();poseStatus(StudioPoseEditor.LABELS[poseJoint]+' moved. Undo steps back this change.');
    }catch(error){
      if(error.axis!=='y')q('#uxPoseX').setAttribute('aria-invalid','true');
      if(error.axis!=='x')q('#uxPoseY').setAttribute('aria-invalid','true');
      poseStatus(error.message);
    }
  }
  q('#uxPosePositionApply').onclick=applyPosePosition;
  q('#uxPosePositionReset').onclick=()=>{if(poseBusy)return;posePositionSignature='';syncReady();poseStatus('Typed coordinates reset to the drawing.');};
  for(const id of ['#uxPoseX','#uxPoseY']){
    q(id).oninput=()=>{q('#uxPoseX').removeAttribute('aria-invalid');q('#uxPoseY').removeAttribute('aria-invalid');poseDrag=-1;syncReady();};
    q(id).onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();applyPosePosition();}};
  }
  q('#uxPoseStart').onchange=e=>{
    const id=e.target.value;e.target.value='';if(!id||!posePoints||poseBusy||posePositionDirty())return;
    pushPose();poseEdit(StudioPoseEditor.start(id,posePoints,poseCanvas));
    poseStatus((StudioPoseEditor.PRESETS.find(p=>p.id===id)||{}).label+' loaded. Nothing was submitted.');
  };
  q('#uxPoseJoints').onclick=e=>{const button=e.target.closest('[data-ux-joint]');if(!button)return;poseJoint=Number(button.dataset.uxJoint);poseEdit(posePoints,false);};
  q('#uxPoseJoints').addEventListener('focusin',e=>{const button=e.target.closest('[data-ux-joint]');if(!button)return;poseJoint=Number(button.dataset.uxJoint);poseEdit(posePoints,false);});
  q('#uxPoseUnknown').onclick=()=>{if(q('#uxPoseUnknown').disabled||!posePoints)return;
    pushPose();poseEdit(StudioPoseEditor.toggle(posePoints,poseJoint,poseHome[poseJoint],poseCanvas),false);
    poseStatus(StudioPoseEditor.LABELS[poseJoint]+(posePoints[poseJoint]?' is back in the guide.':' is left out, with the limbs that touch it.'));};
  q('#uxPoseUndo').onclick=()=>{if(q('#uxPoseUndo').disabled)return;const step=poseTimeline.undo(posePoints,poseHome);if(!step)return;poseHome=step.home;poseEdit(step.points,false);poseStatus('One change stepped back. Redo restores it.');};
  q('#uxPoseRedo').onclick=()=>{if(q('#uxPoseRedo').disabled)return;const step=poseTimeline.redo(posePoints,poseHome);if(!step)return;poseHome=step.home;poseEdit(step.points,false);poseStatus('One change restored.');};
  function poseKeys(e){
    const step={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];
    // Native select/number editing keeps its own arrow keys; only the drawing and joint buttons nudge geometry.
    if(!step||!posePoints||poseBusy||posePositionDirty()||!e.target.closest('#uxPoseCanvas,[data-ux-joint]'))return;
    e.preventDefault();
    if(!posePoints[poseJoint]){poseStatus(StudioPoseEditor.LABELS[poseJoint]+' is unknown. Restore it before moving it.');return;}
    pushPose();poseEdit(StudioPoseEditor.nudge(posePoints,poseJoint,step[0],step[1],poseCanvas,e.shiftKey?.05:.01));
  }
  posePanel.addEventListener('keydown',poseKeys);
  q('#uxPoseCanvas').addEventListener('pointerdown',e=>{
    if(!posePoints||poseBusy||posePositionDirty())return;
    const at=poseAt(e),index=StudioPoseEditor.nearest(posePoints,at.x,at.y,POSE_GRAB*poseCanvas.width/Math.max(1,q('#uxPoseCanvas').width));
    if(index<0){poseStatus('Nothing to grab there. Drag a coloured joint, or pick one in the list.');return;}
    e.preventDefault();pushPose();poseJoint=index;poseDrag=index;
    try{q('#uxPoseCanvas').setPointerCapture(e.pointerId);}catch(_){}
    poseEdit(StudioPoseEditor.move(posePoints,index,at.x,at.y,poseCanvas));
  });
  q('#uxPoseCanvas').addEventListener('pointermove',e=>{if(poseDrag<0||!posePoints||poseBusy)return;e.preventDefault();const at=poseAt(e);poseEdit(StudioPoseEditor.move(posePoints,poseDrag,at.x,at.y,poseCanvas));});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])q('#uxPoseCanvas').addEventListener(name,()=>{poseDrag=-1;});
  async function usePose(){
    if(poseBusy||!posePoints)return;
    const blocked=poseBlockedReason();if(blocked){poseStatus(blocked);syncPoseActions();return;}
    const stamp=setupStamp(),inPlace=StudioPoseEditor.drawsGuide(selected),switching=selected.id!==POSE_RECIPE&&!inPlace,request=StudioPoseEditor.serialize(posePoints,poseCanvas),drawing=JSON.stringify(request);
    // A replacement always lands on the Klein skeleton recipe, so only an in-place guide recipe picks another renderer.
    const body=StudioPoseEditor.renderRequest(request,StudioPoseEditor.guideRenderer(selected));
    poseDrag=-1;poseBusy=true;syncReady();
    try{
      const response=await post('/api/pose/render',body);
      if(stamp!==setupStamp()||setupBusy()||drawing!==JSON.stringify(StudioPoseEditor.serialize(posePoints,poseCanvas)))throw Error('The workbench or drawing changed while the pose was rendering. Nothing was attached.');
      const result=StudioPoseEditor.guideResponse(response,body);poseSource=result.artifact_id;
      if(switching)switchCombineEngine(POSE_RECIPE,result);
      else{
        const previous=referenceRecords[0]?.parent_asset;
        referenceRecords=StudioContinuation.combineReferences(selected,[result]);
        Object.assign(referenceRecords[0],result,{parent_asset:null,missing:false});
        if(previous!==continuationState?.source_asset_id)releaseParentAsset(previous);
      }
      if(!inPlace&&StudioContinuation.sourceInput(selected.continuation_capability)!=='last_reference')uploaded=result.file;
      renderReferenceSlots();draftDirty=true;saveDraft();syncCreate();
      poseStatus('Your drawing is on Picture 1. No generation was submitted.');
      announce('Your drawn pose is on Picture 1'+(switching?', and this pair is now on '+selected.name+'.':'.')+' Check the wording, then press Generate.');
    }catch(error){poseStatus(error.message);announce(error.message,true);}
    finally{poseBusy=false;syncReady();}
  }
  q('#uxPoseUse').onclick=()=>{void usePose();};
  function syncCombineResults(){
    const active=!!StudioContinuation.combineKind(selected);resultPanel.hidden=!active;if(!active){resultMarkup='';return;}
    const record=currentPair(),matches=jobs.filter(job=>StudioContinuation.sameCombinePair(record,job,catalog.presets));
    const outputs=matches.flatMap(job=>(job.outputs||[]).map((output,index)=>({job,output,index}))).filter(({output})=>!assetState.assets.find(a=>a.id===output.asset_id)?.trashed_at);
    const sources=[...referenceRecords.filter(r=>r.file&&!r.missing).map(r=>({file:r.file,label:'Pose source'})),{file:lastUploaded,label:'Character'}].filter(r=>r.file);
    const sourceTiles='<div class="ux-result-sources">'+sources.map(s=>'<figure><img src="/api/uploads/'+encodeURIComponent(s.file)+'" alt="'+s.label+'"><figcaption>'+s.label+'</figcaption></figure>').join('')+'</div>';
    const tiles=outputs.slice(0,24).map(({job,output,index})=>{
      const asset=assetState.assets.find(a=>a.id===output.asset_id),id=escape(job.id),review=asset?.review||'unreviewed',rerun=job.status==='completed'&&!combineBusy();
      return '<article class="ux-result-tile"><img src="/api/image/'+encodeURIComponent(job.id)+'/'+index+'" alt="Combine result, seed '+escape(output.seed??job.controls?.seed??'unknown')+'"><b>Seed '+escape(output.seed??job.controls?.seed??'unknown')+'</b><small>'+escape(job.preset_name)+(Number(job.elapsed_seconds)>0?' · '+durationLabel(job.elapsed_seconds):'')+'</small><span>'+escape(review==='selected'?'Keeper':review.replaceAll('_',' '))+'</span><div class="ux-result-actions">'+(output.asset_id?'<button type="button" data-ux-review="selected" data-asset="'+escape(output.asset_id)+'" '+(pairActionBusy?'disabled':'')+'>Keep</button><button type="button" data-ux-review="needs_work" data-asset="'+escape(output.asset_id)+'" '+(pairActionBusy?'disabled':'')+'>Needs work</button>':'')+'<button type="button" data-ux-rerun="same" data-job="'+id+'" data-index="'+index+'" '+(rerun?'':'disabled')+'>Prepare same seed</button><button type="button" data-ux-rerun="new" data-job="'+id+'" data-index="'+index+'" '+(rerun?'':'disabled')+'>Prepare new seed</button><button type="button" data-ux-result-recipe="'+id+'">Recipe</button></div>'+(job.status!=='completed'?'<small>Run '+escape(job.status)+'. Resolve it in Problems before preparing another.</small>':'')+'</article>';
    }).join('');
    const activeRuns=matches.filter(j=>j.status!=='completed').map(j=>'<p>'+escape(j.preset_name)+' · '+escape(j.status)+': '+escape(j.message||'')+'</p>').join('');
    const markup='<h3>Runs for these pictures</h3><p>Review each seed beside its sources. Preparing a seed loads the recorded recipe; Generate remains a separate step.</p><div class="ux-experiment-strip">'+sourceTiles+(tiles||'<p class="ux-no-results">'+(sources.length>1?'No saved results for these pictures yet.':'Attach both pictures to see their results.')+'</p>')+'</div>'+activeRuns+(outputs.length>24?'<p>Showing the latest 24 of '+outputs.length+' outputs. All saved outputs remain in the library.</p>':'')+'<p id="uxPairActionStatus" role="status"></p>';
    if(markup!==resultMarkup){resultMarkup=markup;resultPanel.innerHTML=markup;}
  }
  resultPanel.onclick=async e=>{
    const button=e.target.closest('button');if(!button||button.disabled||pairActionBusy)return;
    if(button.dataset.uxResultRecipe){try{await exportRecipe(button.dataset.uxResultRecipe);}catch(error){announce(error.message,true);}return;}
    if(!button.dataset.uxReview&&!button.dataset.uxRerun)return;
    const stamp=setupStamp();pairActionBusy=true;syncReady();let status='';
    try{
      if(button.dataset.uxReview){
        await refreshAssets(true);await mutateAssets({action:'edit',ids:[button.dataset.asset],review:button.dataset.uxReview});
        status=button.dataset.uxReview==='selected'?'Keeper saved.':'Needs-work decision saved.';
      }else{
        const job=jobs.find(j=>j.id===button.dataset.job),index=Number(button.dataset.index),output=job?.outputs?.[index];
        if(job?.status!=='completed'||!output)throw Error('Only a completed run can prepare another seed. Inspect unresolved work in Problems.');
        const recipe=await api('/api/jobs/'+encodeURIComponent(job.id)+'/recipe'),check=await post('/api/recipe-check',recipe);
        if(stamp!==setupStamp())throw Error('The workbench changed while reading this recipe. Your current work was kept.');
        const target=catalog.presets.find(p=>p.id===recipe.preset_id);if(!target)throw Error('This recipe is no longer available.');
        const seed=output.seed??recipe.controls?.seed;if(seed==null)throw Error('This run has no recorded seed. Inspect its recipe before preparing another.');let next=seed;
        if(button.dataset.uxRerun==='new'){next=crypto.getRandomValues(new Uint32Array(1))[0];if(String(next)===String(seed))next=(next+1)%4294967296;}
        const setup={preset:target.id,continuation:recipe.continuation,controls:{...recipe.controls,seed:String(next)},batch_count:1,parent_assets:recipe.parent_assets,references:StudioContinuation.combineReferences(target,recipe.references||[])};
        selectPreset(target.id,true,true);applySaved(setup);
        recipeTemplateHash=check.template_sha256;draftDirty=true;saveDraft();updateReady();recipeChanged();
        status=(button.dataset.uxRerun==='new'?'New seed ':'Recorded seed ')+next+' prepared. Review the recipe, then Generate.';
      }
    }catch(error){status=error.message;announce(status,true);}
    finally{pairActionBusy=false;syncReady();const line=q('#uxPairActionStatus');if(line)line.textContent=status;}
  };
  after('renderJobs',()=>{syncCombineEngines();syncCombineResults();});after('renderAssets',syncCombineResults);
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
    q('#generate').textContent=cap?.operation==='upscale'?'Upscale source →':cap?.operation==='restyle'?'Restyle source →':cap?.operation==='combine'?'Combine pictures →':cap?.prompt_role==='motion'?'Animate source →':'Generate source-based pass →';
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
  secondPanel.innerHTML='<b id="uxSecondTitle">One slot, two pictures.</b><p id="uxSecondText"></p><div id="uxSecondSlots" class="ux-context-actions"></div><div class="ux-context-actions"><button type="button" id="uxSecondCombine" class="primary">Use its pose → Combine</button><button type="button" id="uxSecondRestyle">Use its look → Restyle the source</button><button type="button" id="uxSecondReplace">Start from this picture instead</button><button type="button" id="uxSecondKeep">Keep the source, drop this picture</button></div><p id="uxSecondHint" class="muted"></p>';
  q('#createView .references').after(secondPanel);
  function secondName(item){return item?.file?item.file.name:item?.asset?.title||'this picture';}
  const boardDestination=intent=>StudioContinuation.destinations(intent,catalog?.presets||[],continuationSource).find(p=>p.continuation_capability?.board_min>0);
  function offerSecondPicture(item){
    secondPicture=item;const dest=boardDestination('restyle'),pose=boardDestination('combine');
    const slots=item.asset&&StudioContinuation.sourceInput(selected?.continuation_capability)==='reference'?selected.reference_slots||[]:[];
    q('#uxSecondTitle').textContent=slots.length?'Keep your source. Place the extra picture.':'One slot, two pictures.';
    q('#uxSecondSlots').innerHTML=slots.slice(1).map((slot,index)=>{
      const i=index+1,occupied=!!referenceRecords[i]?.file&&!referenceRecords[i]?.missing;
      return '<button type="button" data-ux-second-slot="'+i+'">'+(occupied?'Replace Picture ':'Use as Picture ')+(i+1)+' · '+escape(referenceRecords[i]?.role||slot.role)+'</button>';
    }).join('');
    q('#uxSecondText').textContent=StudioContinuation.sourceLabel(selected)+' already holds the picture you are continuing. What is “'+secondName(item)+'” for?';
    q('#uxSecondCombine').disabled=!pose;q('#uxSecondCombine').title=pose?'':'No combine recipe is available.';
    q('#uxSecondRestyle').disabled=!dest;q('#uxSecondRestyle').title=dest?'':'No style-board restyle recipe is available.';
    q('#uxSecondHint').textContent=(pose?'Combine keeps the source character and draws it in the new picture’s pose ('+pose.name+'). ':'')+(dest?(dest.continuation_capability?.keeps_picture?'Restyle keeps the source and repaints it '+(dest.continuation_capability?.prompt_role==='instruction'?'the way the new picture is drawn ('+dest.name+').':'in the recipe’s finish ('+dest.name+'); the new picture goes on the style board, which adds its palette only as far as Style weight says (0 = off).'):'Restyle keeps the source’s pose and paints it in the look of the new picture ('+dest.name+').')+' ':'No restyle recipe is available. ')+'Starting from the new picture ends this continuation; the original stays in your library.';
    secondPanel.hidden=false;syncReady();focusReadinessTarget(q('[data-ux-second-slot]')||(pose?q('#uxSecondCombine'):dest?q('#uxSecondRestyle'):q('#uxSecondReplace')));
  }
  function dismissSecondPicture(){secondPicture=null;secondPanel.hidden=true;}
  const legacyReferenceChange=q('#reference').onchange;
  q('#reference').onchange=function(e){
    const file=q('#reference').files?.[0];
    if(continuationState&&file&&!selected?.reference_slots?.length&&StudioContinuation.sourceInput(selected?.continuation_capability)==='reference'){offerSecondPicture({file});return;}
    dismissSecondPicture();return legacyReferenceChange?.call(this,e);
  };
  q('#uxSecondKeep').onclick=()=>{if(pickerBusy)return;dismissSecondPicture();q('#reference').value='';syncReady();announce('Kept the source. The extra picture was not attached.');};
  const useSecondPicture=intent=>()=>{
    const item=secondPicture,dest=boardDestination(intent);if(pickerBusy||!item||!dest||!continuationState)return;
    // Keep the choice and native File until Prepare commits (selectPreset clears both).
    // A refused opening, failed context read or cancelled modal must not consume the picture.
    pendingStyle=null;
    try{if(openHandoff(continuationState.source_asset_id,dest.id,undefined,intent))pendingStyle=item;}
    catch(error){announce('Could not open the handoff. '+error.message,true);}
    syncReady();
  };
  q('#uxSecondRestyle').onclick=useSecondPicture('restyle');q('#uxSecondCombine').onclick=useSecondPicture('combine');
  q('#uxSecondReplace').onclick=async()=>{
    const item=secondPicture;if(pickerBusy||handoffBusy||submitting||restoring||referencePending||!item||!continuationState)return;
    if(!window.confirm('Start from this picture instead? The continuation ends and Create resets to the recipe defaults. The original stays in your library.'))return;
    pickerBusy=true;syncReady();
    try{
      if(item.file){const transfer=new DataTransfer();transfer.items.add(item.file);selectPreset(selected.id,true,true);q('#reference').files=transfer.files;legacyReferenceChange?.call(q('#reference'),new Event('change'));}
      else{
        // Keep the reviewed draft live until a verified copy is ready. The reset and
        // existing source owner then commit synchronously, with no second request.
        const stamp=workbenchStamp(),epoch=selectionEpoch,refs=referenceEpoch,result=await post('/api/assets/reference',{id:item.asset.id});
        if(referencePending||epoch!==selectionEpoch||refs!==referenceEpoch||stamp!==workbenchStamp()||secondPicture!==item)throw Error('The workbench changed while the picture was being copied. It was not applied.');
        if(result?.parent_asset!==item.asset.id||result?.sha256!==item.asset.sha256||result?.context?.asset_id!==item.asset.id||result?.context?.sha256!==item.asset.sha256||!StudioContinuation.normalize({...continuationState,reference_file:result?.file,source_asset_id:item.asset.id,source_sha256:item.asset.sha256}))throw Error('The replacement attachment could not be verified. The current source was kept.');
        selectPreset(selected.id,true,true);attachContinuationSource(result);
      }
      dismissSecondPicture();
      draftDirty=true;saveDraft();syncCreate();announce('Continuation ended. '+secondName(item)+' is now the reference; the prompt is the recipe default.');
    }catch(error){announce(error.message,true);}
    finally{pickerBusy=false;syncReady();}
  };
  // The existing slot attachment owner arbitrates late copies and preserves slot roles.
  q('#uxSecondSlots').onclick=async e=>{
    const button=e.target.closest('[data-ux-second-slot]'),item=secondPicture,index=Number(button?.dataset.uxSecondSlot);
    if(!button||pickerBusy||handoffBusy||submitting||restoring||referencePending||!item?.asset||!continuationState)return;
    if(StudioContinuation.sourceInput(selected.continuation_capability)!=='reference'||!Number.isInteger(index)||index<1||!selected.reference_slots?.[index])return;
    if(referenceRecords[index]?.file&&!referenceRecords[index]?.missing&&!window.confirm('Replace Picture '+(index+1)+' with '+secondName(item)+'? Picture 1 and your wording stay unchanged.'))return;
    const ownedFocus=secondPanel.contains(document.activeElement);
    pickerBusy=true;button.disabled=true;secondPanel.setAttribute('aria-busy','true');syncReady();
    try{
      if(!await pullIntoSlot(index,item.asset.id))return;
      const returnFocus=ownedFocus&&view==='create'&&(secondPanel.contains(document.activeElement)||document.activeElement===document.body);
      if(secondPicture===item)dismissSecondPicture();
      announce('Picture '+(index+1)+' attached. Your source and wording were kept. Review its role before generating.');
      if(returnFocus)focusReadinessTarget(q('[data-ref-contribution="'+index+'"]')||q('[data-ref-file="'+index+'"]'));
    }finally{pickerBusy=false;button.disabled=false;secondPanel.setAttribute('aria-busy','false');syncReady();}
  };
  // A modal handoff carries IDs, not paths; selecting a destination never runs it.
  const handoff=element('dialog','studio-dialog ux-handoff');handoff.id='uxHandoff';handoff.setAttribute('aria-labelledby','uxHandoffTitle');handoff.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">CONTINUE WITH THIS ASSET</span><h2 id="uxHandoffTitle">Where should it go next?</h2></div><button data-ux-close="uxHandoff" aria-label="Close handoff">✕</button></div><div class="ux-handoff-layout"><div id="uxHandoffSource"></div><div><div id="uxHandoffIntents" class="ux-handoff-intents"></div><label for="uxDestination">Destination recipe<select id="uxDestination"></select></label><div id="uxHandoffDetails"></div><details><summary>Wording prepared for this pass</summary><pre id="uxHandoffPrompt"></pre></details><details><summary>Technical recipe notes</summary><p id="uxHandoffTechnical"></p></details><p class="callout">Prepare attaches a copy and fills the settings. Nothing runs until you press Generate.</p><p id="uxHandoffStatus" role="status"></p><button id="uxPrepareHandoff" class="primary">Prepare in Create →</button></div></div>';document.body.append(handoff);
  function destinationDetails(){
    const p=catalog?.presets.find(p=>p.id===q('#uxDestination').value),cap=p?.continuation_capability;
    q('#uxHandoffDetails').innerHTML=p?StudioContinuation.guidance(p,sourceContext).map(text=>'<p>'+escape(text)+'</p>').join(''):'No supported source-consuming recipe is available for this task.';
    q('#uxHandoffTechnical').textContent=p?.description||'';
    const prepared=p?StudioContinuation.promptFor(p,sourceContext):null;
    q('#uxHandoffPrompt').textContent=cap?.prompt_role==='none'?'No prompt is used.':prepared!=null?prepared:cap?.prompt_role==='description'&&sourceContext?.prompt_role==='description'&&typeof sourceContext.positive==='string'?sourceContext.positive:'No recipe example will be inserted. '+(cap?.prompt_role==='instruction'?'Write the requested change after preparing.':cap?.prompt_role==='motion'?'Write a motion brief after preparing.':'Write a description of the intended image after preparing.');
    q('#uxPrepareHandoff').disabled=!p||!sourceContext||!!cap?.requires_mask||handoffBusy||submitting;q('#uxDestination').disabled=handoffBusy;
  }
  function handoffRecipes(preferred){q('#uxHandoffIntents').innerHTML=U.INTENTS.filter(i=>i.id!=='create').map(i=>'<button data-ux-destination="'+i.id+'" aria-pressed="'+(i.id===handoffIntent)+'">'+i.verb+'</button>').join('');const recipes=StudioContinuation.destinations(handoffIntent,catalog?.presets||[],sourceContext);q('#uxDestination').innerHTML=recipes.map(p=>'<option value="'+escape(p.id)+'">'+escape(p.name)+(p.continuation_capability.requires_mask?' · mask preparation required':'')+'</option>').join('');if(recipes.some(p=>p.id===preferred))q('#uxDestination').value=preferred;destinationDetails();}
  function assetDetailsDirty(){return q('#assetDialog').open&&activeAsset&&(q('#assetTitle').value!==activeAsset.title||q('#assetNotes').value!==activeAsset.notes||q('#assetTags').value!==activeAsset.tags.join(', ')||q('#assetReview').value!==activeAsset.review);}
  function warnUnsavedAsset(){let notice=q('#uxAssetUnsaved');if(!notice){notice=element('p','callout');notice.id='uxAssetUnsaved';notice.setAttribute('role','status');q('#assetHandoffs').before(notice);}notice.textContent='Save your asset details before continuing. Your changes are still here.';q('#saveAssetDetails').focus();}
  document.addEventListener('click',e=>{if(e.target.closest('.ux-scene-link,#assetRecipe')&&assetDetailsDirty()){e.preventDefault();e.stopImmediatePropagation();warnUnsavedAsset();}},true);
  function openHandoff(id,preferred,epoch,intent){
    if(epoch!=null&&epoch!==handoffEpoch)return false;const request=++handoffEpoch;
    if(assetDetailsDirty()){warnUnsavedAsset();return false;}if(!catalog){announce('Recipes are still loading.');return false;}
    const a=assetState.assets.find(a=>a.id===id);if(!a||a.trashed_at||a.media_type!=='image'){announce('Choose an available image from the Asset library.',true);return false;}
    handoffId=id;sourceContext=null;handoffBaseline=workbenchStamp();
    handoffIntent=intent||(/wan|h3/.test(preferred||'')?'animate':/trellis|hunyuan/.test(preferred||'')?'mesh':/^combine-/.test(preferred||'')?'combine':/style-pose|restyle-/.test(preferred||'')?'restyle':/fix|refine|upscale|esrgan/.test(preferred||'')?'repair':'edit');
    q('#uxHandoffSource').innerHTML=assetPreview(a,true)+'<b>'+escape(a.title)+'</b><small>Source preserved · '+escape(a.review||'unreviewed')+'</small>';
    q('#uxHandoffStatus').textContent='Reading this output’s exact submitted prompt…';handoffRecipes(preferred);handoff.showModal();
    readSource(id).then(source=>{if(request!==handoffEpoch||!handoff.open)return;if(source?.version!==1||source.asset_id!==id||source.sha256!==a.sha256)throw Error('Source identity changed; refresh the library.');sourceContext=source;q('#uxHandoffStatus').textContent=source.warning||'Source and output-specific wording found. Preparing remains separate from running.';const current=q('#uxDestination').value;handoffRecipes(preferred||current);}).catch(error=>{if(request===handoffEpoch&&handoff.open){q('#uxHandoffStatus').textContent='Could not read source context: '+error.message;sourceContext=null;destinationDetails();}});
    return true;
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
      if(!restyle){announce(style?'Source attached. This recipe has no style board, so the second picture was not attached; the prepared wording carries the look. Check it, then press Generate.':'Source attached. Check the prompt, then press Generate.');contextPanel.scrollIntoView({block:'center'});}
      else{const label=StudioContinuation.sourceLabel(selected).toLowerCase(),op=selected.continuation_capability?.operation,board=op==='combine'?'Picture 1 (the picture whose pose you want)':selected.continuation_capability?.keeps_picture&&selected.style_weight?'the style board (off until you raise Style weight)':selected.continuation_capability?.prompt_role==='instruction'?'Picture 1 (the picture drawn the way you want)':'the style board';
        if(style?.file){announce('Source attached as the '+label+'; your picture is uploading to Picture 1.');void uploadRoleFile(0,style.file);}
        else if(style?.asset){announce('Source attached as the '+label+'; your picture goes on Picture 1.');void pullIntoSlot(0,style.asset.id);}
        else{announce('Source attached as the '+label+'. Now add '+(op==='combine'?'the picture whose pose you want to Picture 1':'a picture to Picture 1 of '+board)+', then press Generate.');focusReadinessTarget(q('[data-ref-file="0"]'));}}
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
  function syncSourceAvailability(){
    // The modal already blocks duplicate interaction. Keep its opener focusable for native return.
    q('#uxPullAsset').disabled=!takesSource();
    q('#uxPullAsset').setAttribute('aria-busy',String(pickerBusy||pickerLoading));
    q('#uxPullAsset').title=takesSource()?'Attach a saved image without changing your recipe':NO_SOURCE_SLOT;
  }
  async function openSourcePicker(){
    if(!takesSource()){announce(NO_SOURCE_SLOT);return;}
    if(picker.open||pickerBusy)return;
    const request=++sourcePickerEpoch,epoch=selectionEpoch;
    pickerLoading=true;syncSourceAvailability();
    q('#uxSourceSearch').value='';q('#uxSourceSearch').disabled=true;q('#uxSourceSlot').disabled=true;
    q('#uxSourceSlot').innerHTML=sourceSlotOptions();
    const first=nextEmptySlot();if(first>=0)q('#uxSourceSlot').value=String(first);
    q('#uxSourceAssets').replaceChildren();q('#uxSourceAssets').setAttribute('aria-busy','true');
    const status=q('#uxPickerStatus');status.textContent='Loading saved images…';status.tabIndex=-1;
    picker.showModal();status.focus({preventScroll:true});
    try{
      const loaded=await refreshAssets();
      if(request!==sourcePickerEpoch||!picker.open)return;
      if(epoch!==selectionEpoch||view!=='create'){picker.close();return;}
      if(!loaded){status.textContent='The library is unavailable or another refresh is still running. Close and reopen to retry; no cached image was attached.';return;}
      renderSources();status.textContent='Attach a copy. The original stays in your library.';
      q('#uxSourceSearch').disabled=false;q('#uxSourceSlot').disabled=false;
      if(document.activeElement===status)q('#uxSourceSearch').focus({preventScroll:true});
    }catch(error){if(request===sourcePickerEpoch&&picker.open)status.textContent='Could not read the library. Close and reopen to retry. '+error.message;}
    finally{if(request===sourcePickerEpoch){pickerLoading=false;q('#uxSourceAssets').setAttribute('aria-busy','false');syncSourceAvailability();}}
  }
  q('#uxPullAsset').onclick=openSourcePicker;
  picker.addEventListener('close',()=>{if(picker.open)return;sourcePickerEpoch++;pickerLoading=false;syncSourceAvailability();});
  q('#uxSourceSearch').oninput=renderSources;
  after('selectPreset',()=>{if(picker.open)picker.close();});
  async function pullIntoSlot(index,id){
    try{await attachReferenceAsset(index,id);draftDirty=true;saveDraft();syncCreate();return true;}
    catch(error){announce('The second picture was not attached. '+error.message,true);return false;}
  }
  q('#uxSourceAssets').onclick=async e=>{const button=e.target.closest('[data-ux-pull]');if(!button||pickerBusy)return;pickerBusy=true;button.disabled=true;syncReady();try{const id=button.dataset.uxPull,slot=q('#uxSourceSlot').value;
      if(continuationState){const input=StudioContinuation.sourceInput(selected.continuation_capability),isSource=input==='last_reference'?slot==='lastReference':slot==='reference'||slot==='0';
        if(isSource&&(!selected.reference_slots?.length||input==='reference')){picker.close();offerSecondPicture({asset:assetState.assets.find(a=>a.id===id)});return;}
        if(isSource)throw Error(StudioContinuation.sourceLabel(selected)+' is the picture you are continuing. Pull into another slot, or use Leave this continuation to start from this one.');}
      if(selected.reference_slots?.length&&slot!=='lastReference')await attachReferenceAsset(Number(slot),id);
      else{const stamp=workbenchStamp(),result=await post('/api/assets/reference',{id});if(stamp!==workbenchStamp())throw Error('The workbench changed during attachment. Reopen the picker.');if(slot==='lastReference'){lastUploaded=result.file;q('#lastReference').value='';pendingInputs.delete('lastReference');}else{uploaded=result.file;q('#reference').value='';pendingInputs.delete('reference');}replaceParentAsset(slot==='lastReference'?'lastReference':'reference',null,id);}
      draftDirty=true;saveDraft();syncCreate();
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
  restoring=true;let epoch=null,checkedInputs=[];
  try{applySaved(draft.recipe);epoch=selectionEpoch;recipeTemplateHash=draft.templateHash;pendingInputs=new Set(draft.pendingInputs);syncReady();
    checkedInputs=[...(!selected.reference_slots?.length&&selected.reference&&uploaded?[['reference',uploaded]]:[]),...(selected.last_reference&&lastUploaded?[['lastReference',lastUploaded]]:[])];
    if(checkedInputs.length){const files=[...new Set(checkedInputs.map(([,file])=>file))],checks=await post('/api/references/check',{files});if(epoch!==selectionEpoch)return;for(const [name,file]of checkedInputs)if(!checks.some(c=>c.file===file&&c.available)){pendingInputs.add(name);if(name==='reference')uploaded=null;else lastUploaded=null;releaseInputParent(name);}}
    syncCreate();announce('Draft restored. Reattach any missing local files, then review before running.');
  }catch(err){if(epoch===selectionEpoch){for(const [name,file]of checkedInputs){if(!file)continue;pendingInputs.add(name);if(name==='reference')uploaded=null;else lastUploaded=null;}announce('Input availability could not be checked: '+err.message,true);}}
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
  const jobInspector=element('dialog','studio-dialog');jobInspector.id='uxJobInspector';jobInspector.setAttribute('aria-labelledby','uxJobInspectorTitle');document.body.append(jobInspector);
  function inspectJob(id){
    const job=homeData?.jobs?.find(item=>item.id===id);
    if(!job){announce('This job is no longer in the Overview snapshot. Refresh the overview to inspect its current record.',true);return;}
    const failure=U.failureDetails(job);
    jobInspector.innerHTML='<div class="dialog-heading"><h2 id="uxJobInspectorTitle">'+escape(job.preset_name||job.id)+'</h2><button type="button" data-ux-close="uxJobInspector">Close</button></div><p><b>'+escape(job.status)+'</b> · Saved record, read-only</p><p>Job ID: <code>'+escape(job.id)+'</code></p><p>'+escape(job.message||'No message recorded.')+'</p>'+(failure?'<p>'+escape(failure.summary)+'</p><p><b>Next:</b> '+escape(failure.action)+'</p><details><summary>Engine detail</summary><pre>'+escape(failure.detail)+'</pre></details>':'')+'<p>Known prompt IDs: '+escape((job.prompt_ids||[]).join(', ')||'None recorded')+'</p><details><summary>Recorded recipe and controls</summary><pre>'+escape(JSON.stringify(job.recipe||{preset:job.preset_id,controls:job.controls||{}},null,2))+'</pre></details><small>Overview snapshot '+escape(homeUpdated?.toLocaleString()||'time unavailable')+'. Inspecting does not retry, cancel or change your current setup.</small>';
    if(!jobInspector.open)jobInspector.showModal();
  }
  async function refreshHome(){if(homeBusy)return;homeBusy=true;q('#uxRefreshHome').disabled=true;try{const result=await Promise.allSettled(['/api/workspace','/api/production','/api/jobs'].map(path=>api(path)));homeErrors=result.map((r,i)=>r.status==='rejected'?['Asset library','Runs','Jobs'][i]+': '+r.reason.message:null).filter(Boolean);homeData={workspace:result[0].status==='fulfilled'?result[0].value:null,plans:result[1].status==='fulfilled'?result[1].value:null,jobs:result[2].status==='fulfilled'?result[2].value:null};homeUpdated=new Date();renderHome();}finally{homeBusy=false;q('#uxRefreshHome').disabled=false;}}
  function renderHome(){if(!homeData)return;const {workspace,plans,jobs:runJobs}=homeData,assets=workspace?.assets||[],s=U.summarize(assets,plans||[],runJobs||[]);q('#uxHomeHealth').textContent=homeErrors.length?'Some data is unavailable. '+homeErrors.join(' · '):'Saved records refreshed '+homeUpdated.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' · execution, creative review and licensing remain separate.';q('#uxHomeHealth').classList.toggle('error',!!homeErrors.length);const signature=JSON.stringify(homeData);if(signature===homeSignature)return;homeSignature=signature;
    q('#uxStats').innerHTML=[['Saved assets',workspace?s.assets:'—','all'],['Awaiting review',workspace?s.unreviewed:'—','unreviewed'],['Keepers',workspace?s.keepers:'—','selected'],['Needs another pass',workspace?s.needsWork:'—','needs_work']].map(([label,value,scope])=>'<button data-ux-scope="'+scope+'"><span>'+label+'</span><b>'+value+'</b><small>Open library →</small></button>').join('');
    const ordered=[...s.reviewPlans,...s.attentionPlans,...s.activePlans,...s.prepared].slice(0,6),seenJobs=new Set((plans||[]).flatMap(p=>(p.stages||[]).map(stage=>stage.job?.id).filter(Boolean)));
    const records=ordered.map(p=>'<a class="ux-desk-row" href="'+(p.state.status==='awaiting_review'&&p.kind==='comparison'?'/review.html?project='+encodeURIComponent(p.id):p.kind==='av'?'/av.html?project='+encodeURIComponent(p.id):p.kind==='voice'?'/voice.html':'/#production')+'" data-ux-project="'+escape(p.id)+'"><span class="ux-state-dot '+escape(p.state.status)+'" aria-hidden="true"></span><span><b>'+escape(p.name)+'</b><small>'+escape(p.state.status.replaceAll('_',' '))+' · '+escape(p.kind)+'</small></span><span aria-hidden="true">↗</span></a>');
    for(const j of [...s.attentionJobs,...s.activeJobs].filter(j=>!seenJobs.has(j.id)).slice(0,3))records.push('<button type="button" class="ux-desk-row" data-ux-inspect-job="'+escape(j.id)+'"><span class="ux-state-dot '+escape(j.status)+'" aria-hidden="true"></span><span><b>'+escape(j.preset_name)+'</b><small>'+escape(j.status)+' · inspect existing record; do not repeat uncertain work</small></span><span aria-hidden="true">↗</span></button>');
    q('#uxAttention').innerHTML=records.join('')||(plans&&runJobs?'<div class="ux-empty"><b>A clear desk.</b><p>Prepare a comparison to test one change, or start with a recipe above.</p><a href="/#create">Prepare your first pass →</a></div>':'<p>Run status is unavailable. Refresh before deciding what to start.</p>');
    const recent=assets.filter(a=>!a.trashed_at).sort((a,b)=>b.created_at-a.created_at).slice(0,6);q('#uxRecent').innerHTML=recent.map(a=>'<button class="ux-recent-card" data-ux-open-asset="'+escape(a.id)+'">'+assetPreview(a)+'<span><b>'+escape(a.title)+'</b><small>'+escape(a.media_type)+' · '+escape(a.review||'unreviewed')+'</small></span></button>').join('')||'<div class="ux-empty panel"><h3>'+(workspace?'Make room for your first asset.':'Asset library is unavailable.')+'</h3><p>Import an existing image or create from a recipe. Sources stay available for the next step.</p><a href="/#assets">Open Asset library →</a></div>';
  }
  q('#uxRefreshHome').onclick=()=>refreshHome();
  document.addEventListener('click',async e=>{try{const inspect=e.target.closest('[data-ux-inspect-job]');if(inspect){inspectJob(inspect.dataset.uxInspectJob);return;}const close=e.target.closest('[data-ux-close]');if(close){if((close.dataset.uxClose==='uxHandoff'&&handoffBusy)||(close.dataset.uxClose==='uxSourcePicker'&&pickerBusy))return;q('#'+close.dataset.uxClose).close();}const intent=e.target.closest('[data-ux-intent]');if(intent)chooseIntent(intent.dataset.uxIntent);const dest=e.target.closest('[data-ux-destination]');if(dest&&!handoffBusy){const next=dest.dataset.uxDestination;if(pendingStyle&&next!==handoffIntent){pendingStyle=null;announce('The extra picture was not attached because you changed the handoff task. Choose it again if the new task needs it.');}handoffIntent=next;handoffRecipes();}const hand=e.target.closest('[data-ux-handoff]');if(hand)openHandoff(hand.dataset.uxHandoff);const scope=e.target.closest('[data-ux-scope]');if(scope){assetScope=scope.dataset.uxScope;q('#assetSearch').value='';q('#assetType').value='all';assetSelection.clear();showView('assets');renderAssets();}const open=e.target.closest('[data-ux-open-asset]');if(open){await refreshAssets();openAsset(open.dataset.uxOpenAsset);}const project=e.target.closest('[data-ux-project]');if(project){productionId=project.dataset.uxProject;if(view==='production')renderProduction();}}catch(err){announce(err.message,true);}});
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
