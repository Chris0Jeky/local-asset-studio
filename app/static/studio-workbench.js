/* Migration adapter: enhances the existing no-build UI without replacing its services.
 * All legacy function interception lives here. Core policy and shell are independent.
 * Remove a hook when its legacy component is migrated; do not add a second executor.
 */
(function(){
  'use strict';
  if(!document.querySelector('#createView'))return;
  const U=StudioUX,q=s=>document.querySelector(s),escape=esc;
  let sharedAdoptionError='';
  let selectionEpoch=0,sourceContext=null,handoffBaseline=null,sourceReadError='',varyUnapplied=null;
  let intentId='create',handoffId=null,handoffIntent='edit',handoffBusy=false,pickerBusy=false,pickerLoading=false,sourcePickerEpoch=0,handoffEpoch=0,handoffBusyOwner=null,pickerBusyOwner=null,handoffAsset=null,repairBoxes=[],repairDrag=null;
  let draftPrefix=null,draftPaused=false,draftDirty=false,restoring=false,draftTimer=null,knownDrafts=new Map(),pendingInputs=new Set();
  let draftPrivacy=globalThis.StudioPrivacy?.creation()||'regular',knownFills=new Map();
  const draftStorage=(classification=draftPrivacy)=>classification==='private'?sessionStorage:localStorage;
  const draftStorageKey=(key,classification=draftPrivacy)=>key+(classification==='private'?'.private':'');
  let homeBusy=false,homeData=null,homeErrors=[],homeUpdated=null,homeSignature='',homeEpoch=0;
  const main=q('main'),editor=q('#createView .editor');
  function after(name,callback){const original=window[name];window[name]=function(...args){const result=original.apply(this,args);if(result?.then)return result.then(value=>{if(value!==false)callback(...args);return value;});callback(...args);return result;};}
  function element(tag,className,html){const el=document.createElement(tag);if(className)el.className=className;if(html)el.innerHTML=html;return el;}
  function announce(text,error=false,details=[]){message(text,error);q('#uxNotice').textContent=text;q('#uxNotice').classList.toggle('error',error);if(details.length){const fold=element('details','ux-notice-details','<summary>Details</summary>');for(const line of details)fold.append(Object.assign(element('div'),{textContent:line}));q('#uxNotice').append(fold);}}
  // #308: a Generate the memory check refuses says why in plain words; the server's own wording follows in brackets.
  const plainMessage=message;message=function(text,error=false){const plain=error?U.headroomExplanation?.(text):null;return plainMessage.call(this,plain?plain+' ('+text+')':text,error);};
  const notice=element('p','ux-notice');notice.id='uxNotice';notice.setAttribute('role','status');main.prepend(notice);
  // Home is a work queue, not a separate project store. Unknown API state is not zero.
  const home=element('section','view ux-home');home.id='homeView';home.setAttribute('aria-labelledby','homeTitle');home.innerHTML='<div class="ux-home-heading"><div><span class="eyebrow">YOUR LOCAL CREATIVE WORKSPACE</span><h1 id="homeTitle" tabindex="-1">Pick up the thread.</h1><p>Start with an idea. Keep what works. Take it somewhere new.</p></div><button id="uxRefreshHome">Refresh overview</button></div><div id="uxHomeHealth" class="ux-home-health" role="status">Reading saved work…</div><div id="uxStats" class="ux-stats"></div><div class="section-title"><h2>What are you making?</h2><a href="/#create">Browse all recipes ↗</a></div><div id="uxJourneys" class="ux-journeys"></div><div class="ux-home-columns"><section class="panel"><div class="section-title"><h2>On your desk</h2><a href="/#production">All runs ↗</a></div><div id="uxAttention"></div></section><section class="panel ux-workflow-map"><span class="eyebrow">ONE IDEA. MANY DESTINATIONS.</span><h2>Keep the thread intact.</h2><div class="ux-flow-map"><a href="/prompt-lab.html">Brief<small>Shape the intent</small></a><span aria-hidden="true">→</span><a href="/#create">Create<small>Choose a recipe</small></a><span aria-hidden="true">→</span><a href="/#production">Review<small>Make a decision</small></a><span aria-hidden="true">→</span><a href="/#assets">Reuse<small>Carry the source</small></a></div><p>Bring outputs back as references, finish them in native tools, or assemble a scene. Every handoff is yours to review.</p><div class="ux-tool-links"><a href="/av.html">Assemble a scene ↗</a><a href="/voice.html">Prepare a voice take ↗</a><a href="/#learn">Understand the workflow ↗</a></div></section></div><div class="section-title"><h2>Recent assets</h2><a href="/#assets">Open library ↗</a></div><div id="uxRecent" class="ux-recent"></div>';
  main.prepend(home);home.before(notice);
  q('#uxJourneys').innerHTML=U.INTENTS.map((item,i)=>'<button class="ux-journey" data-ux-intent="'+item.id+'"><span class="ux-journey-number">0'+(i+1)+' <span aria-hidden="true">↗</span></span><b>'+item.name+'</b><span>'+item.description+'</span><small>'+item.hint+'</small></button>').join('');
  // Keep every existing control ID. The workbench adapter only changes grouping.
  const createHeading=element('div','ux-create-heading','<div><span class="eyebrow">FULL EDITOR</span><h1>Full editor — every setting for one recipe</h1></div><div class="ux-stage-track" aria-label="Creative workflow"><span aria-current="step">1 · Prepare</span><span>2 · Run</span><a href="/#production">3 · Review</a><a href="/#assets">4 · Reuse</a></div>');q('#createView').prepend(createHeading);
  const recipeTools=element('div','ux-intent-tools','<label for="uxIntent">Start with a task<select id="uxIntent"><option value="all">Every recipe</option>'+U.INTENTS.map(i=>'<option value="'+i.id+'">'+i.name+'</option>').join('')+'</select></label><p id="uxIntentHint" class="muted">Choose by outcome, then inspect the exact recipe.</p>');q('#presetSearch').closest('label').before(recipeTools);
  const setup=q('#createView .setup'),drawer=element('details','ux-recipe-drawer');drawer.open=window.innerWidth>850;drawer.innerHTML='<summary>Recipe library <small id="uxRecipeLabel">Choose a starting point</small></summary>';while(setup.firstChild)drawer.append(setup.firstChild);setup.append(drawer);
  const drafts=element('div','ux-draft-bar');drafts.id='uxDraftBar';drafts.innerHTML='<span id="uxDraftStatus">Your unsaved draft is kept in this browser. Save a setup to keep it in your workspace.</span><div><button id="uxRestoreDraft" hidden>Restore draft</button><button id="uxDiscardDraft" hidden>Discard saved draft</button><button id="uxExportDraft">Export draft</button><button id="uxImportDraftButton">Import draft</button><input id="uxImportDraft" type="file" accept="application/json,.json" hidden><button id="uxKeepDraft" hidden>Keep this tab</button></div>';editor.prepend(drafts);
  q('#positiveWrap').before(element('div','ux-section-heading','<span>01</span><h3>Describe the result</h3><a href="/prompt-lab.html">Open Prompt Lab ↗</a>'));
  // A recipe's bracketed fills (who, the pose, the clothes) are short fields that write the prepared wording for you; the
  // paragraph stays visible and editable underneath, and a hand edit stops the fields from rewriting it (#422 slice A).
  const fillsBlock=element('div','ux-fills');fillsBlock.id='uxFills';fillsBlock.hidden=true;q('#positiveWrap').before(fillsBlock);
  let fillsPreset=null,fillsSource=null,fillsTemplate='',fillsAssembled=null,transferredFills=null;
  const fillInputs=()=>[...fillsBlock.querySelectorAll('[data-ux-fill]')];
  function fillValues(){return Object.fromEntries(fillInputs().map(input=>[input.dataset.uxFill,input.value]));}
  function fillsKey(){return continuationState?draftStorageKey('studio-fills:'+continuationState.source_asset_id):null;}
  function rememberedFills(){const key=fillsKey();if(!key)return{};try{const raw=draftStorage().getItem(key),value=JSON.parse(raw||'{}');if(value&&typeof value==='object'&&!Array.isArray(value)){knownFills.set(key,raw);return value;}return{};}catch(e){return{};}}
  function rememberFills(){const key=fillsKey();if(!key)return;const remembered={...rememberedFills(),...fillValues()};for(const [placeholder,value]of Object.entries(fillValues())){const meaning=StudioContinuation.fillMeaning(placeholder);if(meaning)remembered['@'+meaning]=value;}try{const raw=JSON.stringify(remembered);draftStorage().setItem(key,raw);knownFills.set(key,raw);}catch(e){}}
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
  q('.gallery-panel .section-title h2').textContent='Recent runs';q('.gallery-panel .muted').textContent='Keep, flag or reject each result here (K, W, X on a focused card), or continue with it.';
  q('#assetsView .view-heading h2').textContent='A library, not a dead end.';
  q('#productionView .view-heading h2').textContent='Run with a question. Leave with a decision.';
  q('#assetScopes').insertAdjacentHTML('beforeend','<button data-scope="unreviewed">Awaiting review</button>');
  const originalVisibleAssets=visibleAssets;visibleAssets=function(){const assets=originalVisibleAssets();return assetScope==='unreviewed'?assets.filter(a=>!a.review||a.review==='unreviewed'):assets;};
  // The legacy app and its tools call showView; this is the single navigation seam.
  showView=function(next){saveDraft();const route=String(next||'');next=U.normalizeView(next);view=next;for(const name of U.VIEWS)q('#'+name+'View').hidden=name!==next;const skipReview=q('#skipReview');if(skipReview)skipReview.hidden=next!=='assets'||q('#reviewNext').disabled;const hero=q('.hero');if(hero)hero.hidden=true;StudioShell.setView(next);const hash=['models','briefs'].includes(next)&&route.replace(/^#/,'').startsWith(next+'?')?route.replace(/^#/,''):next;if(location.hash!=='#'+hash)location.hash=hash;if(next==='home')refreshHome();if(next==='make')window.StudioMake?.refresh();if(next==='briefs')window.StudioBriefs?.refresh();if(next==='assets')refreshAssets();if(next==='production')refreshProduction();if(next==='models'||next==='learn')refreshLibrary();};
  document.addEventListener('studio:navigate',e=>{showView(e.detail);main.focus({preventScroll:true});window.scrollTo({top:0});});window.addEventListener('hashchange',()=>{const next=U.normalizeView(location.hash);if(next!==view||next==='models'||location.hash!=='#'+next)showView(location.hash);});
  const originalRenderPresets=renderPresets;renderPresets=function(){originalRenderPresets();if(!catalog)return;const id=q('#uxIntent').value;if(id==='all')return;const allowed=new Set(U.recipesFor(id,catalog.presets).map(p=>p.id));let count=0;for(const button of q('#presetList').querySelectorAll('[data-id]')){button.hidden=!allowed.has(button.dataset.id);if(!button.hidden)count++;}q('#filteredCount').textContent=count;if(!count)q('#presetList').append(element('p','muted','No recipes match this task and the current filters. Clear search or choose Every recipe.'));};
  function chooseIntent(id){if(!catalog){announce('The recipe catalog is still loading.');return;}intentId=id;q('#uxIntent').value=id;q('#presetSearch').value='';q('#categorySelect').value='All';mode='all';document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode==='all'));const recipes=U.recipesFor(id,catalog.presets);if(recipes.length)selectPreset(recipes[0].id);renderPresets();q('#uxIntentHint').textContent=U.INTENTS.find(i=>i.id===id)?.hint||'Choose by outcome.';showView('create');}
  q('#uxIntent').onchange=()=>{intentId=q('#uxIntent').value;renderPresets();q('#uxIntentHint').textContent=U.INTENTS.find(i=>i.id===intentId)?.hint||'Every installed and planned recipe. Readiness is checked separately.';};
  after('selectPreset',()=>{sharedAdoptionError='';selectionEpoch++;draftDirty=false;pendingInputs.clear();dismissSecondPicture();syncCreate();renderDraftNotice();});
  after('applySaved',()=>{if(!restoring)draftDirty=true;hydrateContinuation();});after('applyRecipe',()=>{draftDirty=true;syncReady();saveDraft();});
  after('beginParallax',()=>{draftDirty=true;saveDraft();});
  const originalSelectPreset=selectPreset;selectPreset=function(...args){saveDraft();return originalSelectPreset(...args);};
  // #1100: loading a recipe still loads its wording, but wording you wrote gets one explicit way back until you type, dismiss
  // or put it back (reversible choice; nothing is carried over silently, nothing is sent). "Yours" means different from the
  // wording the Studio itself last loaded (preset example or applied recipe). Setups, drafts and continuations clear the offer.
  // A staged picture the load cleared (picked file, pulled or attached slot, with its lineage) gets one too, but only as a way
  // back to the recipe it was staged for, with that recipe's wording and settings as they were: a picture bound to one recipe's
  // input never moves into another graph. Your own edit after the switch withdraws it; a later write by code makes it refuse.
  const wordingUndo=element('div','ux-wording-undo');wordingUndo.id='uxWordingUndo';wordingUndo.hidden=true;
  const wordingText=element('span'),wordingRestore=element('button','','Put my wording back'),wordingBack=element('button'),wordingDismiss=element('button','subtle','Keep the recipe wording');
  wordingText.setAttribute('role','status');wordingRestore.type=wordingBack.type=wordingDismiss.type='button';wordingRestore.id='uxWordingUndoRestore';wordingBack.id='uxWordingUndoBack';wordingDismiss.id='uxWordingUndoDismiss';wordingUndo.append(wordingText,wordingRestore,wordingBack,wordingDismiss);
  q('#positiveWrap')?.after(wordingUndo);let wordingKept=null,wordingBase=null,wordingDepth=0,pictureKept=null;
  const wording=()=>({positive:q('#positive')?.value??'',negative:q('#negative')?.value??''});
  const presetWording=p=>({positive:p?.defaults?.positive||'',negative:p?.defaults?.negative||''});
  const forgetWording=()=>{wordingKept=pictureKept=null;wordingUndo.hidden=true;};
  const pickedFiles=id=>[...(q('#'+id)?.files||[])],stagedPicture=()=>!!(pickedFiles('reference').length||pickedFiles('lastReference').length||uploaded||lastUploaded||referenceRecords.some(r=>r.file));
  const pictureStamp=()=>JSON.stringify([selected?.id,wording(),values(),recipeTemplateHash,q('#batch')?.value,uploaded,lastUploaded,parentAssets,parentByInput,referenceRecords,['reference','lastReference'].map(id=>pickedFiles(id).map(f=>[f.name,f.size,f.lastModified]))]);
  const pictureSnapshot=()=>({id:selected.id,name:selected.name,templateHash:recipeTemplateHash,controls:values(),batch:q('#batch')?.value,wording:wording(),uploaded,lastUploaded,parentAssets:[...parentAssets],parentByInput:{...parentByInput},records:referenceRecords.map(r=>({...r})),files:{reference:pickedFiles('reference'),lastReference:pickedFiles('lastReference')}});
  function renderUndo(){const kept=wordingKept,pic=pictureKept;if(!pic&&!kept?.line){wordingUndo.hidden=true;return;}
    wordingRestore.hidden=!kept?.restorable;wordingBack.hidden=!pic;if(pic)wordingBack.textContent='Go back to '+pic.name+' with your picture';
    wordingDismiss.textContent=pic?'Keep '+selected.name:'Keep the recipe wording';
    wordingText.textContent=[kept?.line,pic&&'Your picture was cleared.'].filter(Boolean).join(' ');wordingUndo.hidden=false;}
  function offerWording(name){const kept=wordingKept,now=wording();if(!selected)return;
    if(pictureKept&&pictureStamp()!==pictureKept.loaded)pictureKept=null;
    // Written by something else after the load in the same task: that write stands, so there is nothing to offer (#1144).
    if(kept&&kept.loaded&&(now.positive!==kept.loaded.positive||now.negative!==kept.loaded.negative))wordingKept=null;
    else if(kept){const positive=kept.positive!==null&&kept.positive!==now.positive,negativeFits=!!selected.negative&&!!q('#negative');
      const negative=kept.negative!==null&&negativeFits&&kept.negative!==now.negative,lost=kept.negative!==null&&!negativeFits;
      if(!positive&&!negative&&!lost)wordingKept=null;
      else{kept.restorable=positive||negative;kept.line=(kept.restorable?name+' loaded its own wording. Yours is kept until you type or choose.':'')+(lost?(kept.restorable?' ':'')+selected.name+' has no negative prompt, so your negative wording is not used: “'+kept.negative.slice(0,160)+(kept.negative.length>160?'…':'')+'”':'');}}
    const pic=pictureKept;if(!wordingKept&&!pic){forgetWording();return;}
    renderUndo();if(selected.runtime_block)return;
    if(pic)message('Recipe loaded. Your picture was cleared: Go back to '+pic.name+' under the prompt restores it.');
    else if(wordingKept.restorable)message('Loaded with its own wording. Yours is kept under the prompt: Put my wording back, or keep typing.');}
  function trackWording(name,kind){const original=window[name];window[name]=function(...args){
    const outer=wordingDepth===0,before=outer?wording():null,base=wordingBase||presetWording(selected),picture=outer&&kind!=='setup'&&selected&&stagedPicture()?pictureSnapshot():null;wordingDepth++;
    let result;try{result=original.apply(this,args);}finally{wordingDepth--;}
    if(!outer)return result;
    // A setup, import or draft loads its own wording: that text is loaded, not typed, like a recipe's (#1144).
    if(kind==='setup'||kind==='preset'&&args[2]===true){forgetWording();wordingBase=kind==='setup'?wording():presetWording(selected);return result;}
    const own=key=>!!String(before[key]).trim()&&before[key]!==base[key]?before[key]:null,positive=own('positive'),negative=own('negative');
    // Your wording replaces an older offer; a load over untouched wording keeps the older one (a misclick in between).
    if(positive!==null||negative!==null)wordingKept={positive,negative};
    // A picture this load cleared replaces an older way back; a plain switch over nothing staged keeps it (a misclick in between).
    if(picture&&!stagedPicture())pictureKept=picture;else if(kind!=='preset'||args[1]===false)pictureKept=null;
    const recipe=kind==='recipe'?args[0]:null;wordingBase=recipe?{positive:recipe.controls?.positive??wording().positive,negative:recipe.controls?.negative??wording().negative}:presetWording(selected);
    // Measured after the caller finishes (a bundle apply sets its own wording in the same task).
    // The loaded wording is recorded as this call ends, so a write later in the same task counts as an edit (#1144).
    if(wordingKept)wordingKept.loaded=wording();if(pictureKept)pictureKept.loaded=pictureStamp();
    if(wordingKept||pictureKept){const label=recipe?'Loading '+(recipe.name||'this recipe'):'Switching to '+selected.name;queueMicrotask(()=>offerWording(label));}else wordingUndo.hidden=true;
    return result;};}
  trackWording('selectPreset','preset');trackWording('applyRecipe','recipe');trackWording('applySaved','setup');
  wordingRestore.onclick=()=>{const kept=wordingKept;forgetWording();if(!kept||!selected)return;const now=wording(),field=q('#positive');
    // Anything that changed the wording after the switch wins; the offer never overwrites it.
    if(now.positive!==kept.loaded?.positive||now.negative!==kept.loaded?.negative){announce('The wording changed after the switch, so nothing was replaced.');return;}
    if(kept.positive!==null&&kept.positive!==now.positive){field.value=kept.positive;field.dispatchEvent(new Event('input',{bubbles:true}));}
    if(kept.negative!==null&&selected.negative&&q('#negative')){q('#negative').value=kept.negative;q('#negative').dispatchEvent(new Event('input',{bubbles:true}));}
    field.focus();announce('Your wording is back. The recipe stays '+selected.name+'.');};
  // Going back is the switch undone: the earlier recipe with its own picture, lineage, wording and settings, nothing carried across.
  wordingBack.onclick=()=>{if(referencePending>0){announce('Wait for the picture upload to finish before going back. Nothing was replaced.',true);return;}const pic=pictureKept;forgetWording();if(!pic||!selected)return;
    if(pictureStamp()!==pic.loaded){announce('Something changed after the switch, so nothing was replaced.');return;}
    try{selectPreset(pic.id);}catch(e){announce(e.message,true);return;}
    const mode=q('#i2vMode');if(mode&&pic.controls.mode)mode.value=pic.controls.mode;
    for(const [key,value] of Object.entries(pic.controls)){if(['positive','negative','reference','last_reference','mode'].includes(key))continue;const input=getControl(key);if(input)input.value=value;}
    for(const key of ['positive','negative'])if(q('#'+key))q('#'+key).value=pic.wording[key];if(q('#batch'))q('#batch').value=pic.batch;
    recipeTemplateHash=pic.templateHash;uploaded=pic.uploaded;lastUploaded=pic.lastUploaded;parentAssets=[...pic.parentAssets];parentByInput={...pic.parentByInput};referenceRecords=pic.records.map(r=>({...r}));
    // A picked file goes back into its own input without a change event (that handler would drop an uploaded copy).
    for(const id of ['reference','lastReference']){const input=q('#'+id),files=pic.files[id];if(!input||!files.length)continue;const t=new DataTransfer();files.forEach(f=>t.items.add(f));input.files=t.files;}
    updateLoraHints();q('#positive').dispatchEvent(new Event('input',{bubbles:true}));if(typeof renderReferenceSlots==='function')renderReferenceSlots();updateReady();recipeChanged();
    draftDirty=true;saveDraft();q('#positive').focus();announce('Back to '+selected.name+' with your picture and wording.');};
  wordingDismiss.onclick=()=>{forgetWording();q('#positive')?.focus();};
  for(const id of ['positive','negative'])q('#'+id)?.addEventListener('input',()=>{const kept=wordingKept;if(kept?.loaded&&(wording().positive!==kept.loaded.positive||wording().negative!==kept.loaded.negative))forgetWording();});
  // Your own edit after the switch is a decision: going back would discard it, so the way back is withdrawn.
  // Every edit fires input (text, select, checkbox, file); a blur-time change after an earlier edit is not a new one.
  q('#createView .editor')?.addEventListener('input',e=>{if(!e.isTrusted||!pictureKept)return;pictureKept=null;renderUndo();},true);
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
    const items=U.readinessItems({preset:selected,online,schemaAvailable,workerAlive,missing:missingByPreset[selected?.id]||[],referencesReady:referencesReady()&&!required.length,switching:typeof backendSwitching!=='undefined'&&backendSwitching,workBlocker:typeof backendWorkBlocker!=='undefined'?backendWorkBlocker:'',backend:typeof backendActive!=='undefined'?backendActive:null,busy:combineBusy()||tileBusy||parallaxBusy,unfilled,sourceMissing});
    if(posePositionDirty())items.push({code:'pose-position',message:'Set the typed joint position or reset its fields before continuing.',action:'pose-position'});
    poseHeldShown=poseHeldArtifact();const staleGuide=poseSizeHold();if(staleGuide)items.push({code:'pose-size',message:staleGuide,action:'pose-size'});
    const modeBlock=i2vModeBlocker();if(modeBlock)items.push({code:'motion',message:modeBlock,action:'parameters'});
    const specific=continuationBlockerItems().map(item=>({code:'continuation-'+item.code,message:item.message,action:continuationActions[item.code]||'continuation'}));
    // The continuation names the exact empty slot; the generic reference line would only repeat it.
    if(specific.some(item=>['continuation-board','continuation-inputs','continuation-source'].includes(item.code)))items.splice(items.findIndex(item=>item.code==='references')>>>0,1);
    items.push(...specific);
    if(secondPicture)items.push({code:'second',message:selected?.reference_slots?.length>1?'Picture 1 remains your source. Choose another slot or explicitly start from the extra picture.':'You added a second picture, but this recipe reads one. Say what it is for.',action:'second'});
    if(sharedAdoptionError)items.push({code:'shared-setup',message:sharedAdoptionError,action:null});
    if(continuationState&&!continuationSource)items.push({code:'source',message:sourceReadError||'Checking the retained source metadata…',action:'continuation'});
    // A Vary round whose carried stack did not apply stays blocked while that same continuation is open.
    if(varyUnapplied&&continuationState&&varyUnapplied.stamp===JSON.stringify(continuationState))items.push({code:'vary',message:varyUnapplied.message,action:null});
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
  contextPanel.innerHTML='<img id="uxContinuationImage" alt="Source image for this pass"><div><span class="eyebrow">CONTINUING YOUR IMAGE</span><h3 id="uxContinuationTitle"></h3><p id="uxContinuationOrigin"></p><div id="uxContinuationGuidance"></div><details><summary>Source wording and provenance</summary><pre id="uxContinuationPrompt"></pre><small id="uxContinuationRecord"></small></details><div class="ux-context-actions"><button id="uxRestoreSourcePrompt">Restore source wording</button><button id="uxChangeRoute">Change route</button><button id="uxLeaveContinuation">Leave this continuation</button></div><p class="disabledReason"><small id="uxRestoreSourceReason"></small></p><p id="uxContinuationContract">Setup choices keep this source and your wording; they reset sampling and adapters to their defaults. Check Parameters before running.</p></div>';
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
    const tiles=[{label:selected.reference_board_label||'Pose picture',n:imageNumber(selected.reference_board_label)||2,src:boardFile?referenceMediaUrl(boardFile):null,empty:'No pose picture yet.',action:'board',button:'Pull it from the library'},
                 {label:selected.last_reference_label||'Picture to keep',n:imageNumber(selected.last_reference_label)||1,src:lastUploaded?referenceMediaUrl(lastUploaded):keepAsset?'/api/assets/'+encodeURIComponent(keepAsset)+'/file'+(draftPrivacy==='private'?'?privacy=all':''):null,empty:'No picture to keep yet.',action:'keep',button:'Choose your picture'}].sort((a,b)=>a.n-b.n);
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
  // The runs sit directly under their two pictures, so the pair and its newest seeds share one screen (#422, J4).
  const enginePanel=element('section','ux-combine-engines');enginePanel.id='uxCombineEngines';enginePanel.hidden=true;pairPanel.after(enginePanel);
  const resultPanel=element('section','ux-pair-results');resultPanel.id='uxPairResults';resultPanel.hidden=true;pairPanel.after(resultPanel);
  const combineWording=new Map();let engineMarkup='',resultMarkup='',pairActionBusy=false;
  function currentPair(){return{preset_id:selected?.id,controls:values(),continuation:continuationState,references:attachedReferencePayload()};}
  function pairKey(){const record=currentPair();return JSON.stringify([record.continuation?.source_sha256||record.controls.last_reference,(record.references||[]).filter(r=>r.file).map(r=>r.sha256||r.file)]);}
  function combineAnswers(){const saved=rememberedFills(),answers=Object.fromEntries(['who','pose','clothes','outfit'].map(key=>[key,saved['@'+key]||'']));for(const [placeholder,value]of Object.entries(fillValues())){const meaning=StudioContinuation.fillMeaning(placeholder);if(meaning)answers[meaning]=value;}return answers;}
  // sendBusy counts only requests in flight; Make and the library use it, since they cannot clear Create's draft state (a typed pose, an upload).
  function sendBusy(){return submitting||handoffBusy||pickerBusy||restoring||pairActionBusy||poseBusy||varyBusy||planBusy||polishBusy.size>0||makeVaryBusy.size>0;}
  function combineBusy(){return sendBusy()||referencePending>0||posePositionDirty();}
  // Each engine's time per picture: this PC's own completed runs of it first; otherwise the read-only local estimate
  // (POST /api/estimate reads timing history and runs nothing), asked once per engine and canvas; otherwise say so (K13).
  const engineEstimates=new Map();let engineEstimateQueue=Promise.resolve();
  function engineEstimate(preset){
    const controls=values(),size={};for(const key of ['width','height'])if(controls[key]!=null&&controls[key]!=='')size[key]=controls[key];
    const payload={preset_id:preset.id,controls:size,batch_count:1,reference_count:estimateReferenceCount()},key=JSON.stringify(payload);
    if(!engineEstimates.has(key)){
      if(engineEstimates.size>60)engineEstimates.clear();engineEstimates.set(key,null);
      engineEstimateQueue=engineEstimateQueue.then(()=>api('/api/estimate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)}))
        .then(value=>{engineEstimates.set(key,value);},()=>{engineEstimates.set(key,{available:false});}).then(()=>{engineMarkup='';syncCombineEngines();});
    }
    return engineEstimates.get(key);
  }
  function engineTime(preset){
    const here=StudioContinuation.combineTiming(jobs,preset.id);
    if(here)return '~'+durationLabel(here.seconds)+' per picture here · '+here.count+' run'+(here.count===1?'':'s');
    const guess=engineEstimate(preset);
    return guess?.available&&guess.confidence!=='none'?'Estimate ~'+durationLabel(guess.estimate_seconds)+' per picture · '+guess.confidence+' confidence':'No timing on this PC yet';
  }
  function syncCombineEngines(){
    enginePanel.hidden=!continuationState||!StudioContinuation.combineKind(selected);if(enginePanel.hidden){engineMarkup='';syncCombinePlan();return;}
    const options=StudioContinuation.destinations('combine',catalog.presets,continuationSource),busy=combineBusy();
    const markup='<h3>Try this pair with another recipe</h3><p>Pictures and answers stay here. Each recipe keeps its edited wording. Generate starts the next run.</p><div class="ux-engine-options">'+options.map(p=>{
      const reason=StudioContinuation.combineSwitchReason(selected,p,referenceRecords)||p.runtime_block||'',hint=StudioContinuation.combineEngineHint(p);
      return '<button type="button" data-ux-engine="'+escape(p.id)+'" aria-pressed="'+(p.id===selected.id)+'" '+(reason||busy?'disabled':'')+' title="'+escape(reason||p.name)+'"><b>'+escape(StudioContinuation.combineEngineLabel(p))+'</b>'+(hint?'<small class="ux-engine-hint">'+escape(hint)+'</small>':'')+'<small>'+escape(engineTime(p))+'</small>'+'<small class="ux-engine-checks">'+escape(engineChecks(p))+'</small>'+(reason?'<small>'+escape(reason)+'</small>':'')+'</button>';
    }).join('')+'</div>';
    if(markup!==engineMarkup){engineMarkup=markup;q('#uxEngineList').innerHTML=markup;}
    syncCombinePlan();
  }
  // #1163: the same pair on several recipes with the same seeds as ONE prepared plan. Prepare checks every recipe on the
  // server and shows the expected total; nothing runs until Start plan is pressed, and each picture lands under the pair.
  enginePanel.innerHTML='<div id="uxEngineList"></div><details id="uxEnginePlan" class="ux-engine-plan"><summary><b>Run several recipes on this pair</b> <small>one plan, the same seeds, one Start</small></summary>'
    +'<p>Tick the recipes and type the seeds. Prepare plan checks every recipe and shows the expected total time; nothing runs until you press Start plan. Each picture lands under Runs for these pictures.</p>'
    +'<fieldset id="uxPlanEngines" class="ux-plan-engines"><legend>Recipes</legend></fieldset><label for="uxPlanSeeds">Seeds<input id="uxPlanSeeds" inputmode="numeric" autocomplete="off" placeholder="e.g. 11, 12"></label><div id="uxPlanFills" class="ux-fills ux-plan-fills" hidden></div>'
    +'<p id="uxPlanSummary"></p><div class="ux-plan-actions"><button type="button" id="uxPlanPrepare">Prepare plan</button><button type="button" id="uxPlanStart" class="primary" hidden>Start plan</button></div><p id="uxPlanStatus" role="status"></p></details>';
  const planChoice=new Set(),planFills={};let planEnginesMarkup='',planFillsMarkup='',planPrepared=null,planBusy=false,planPreset=null,planPair=null,planSeeded=false;
  const planStatus=text=>{q('#uxPlanStatus').textContent=text;};
  function planOptions(){return StudioContinuation.destinations('combine',catalog.presets,continuationSource).map(p=>({preset:p,reason:StudioContinuation.combineSwitchReason(selected,p,referenceRecords)||p.runtime_block||''}));}
  function planSeeds(){return StudioContinuation.combinePlanSeeds(q('#uxPlanSeeds').value);}
  function planEngines(){return planOptions().filter(o=>!o.reason&&planChoice.has(o.preset.id)).map(o=>o.preset);}
  // Seconds per picture the page already shows on each engine button: this PC's runs first, then the read-only estimate.
  function planPerPicture(preset){const here=StudioContinuation.combineTiming(jobs,preset.id);if(here)return here.seconds;const guess=engineEstimate(preset);return guess?.available&&guess.confidence!=='none'?Number(guess.estimate_seconds):null;}
  // #1163 live defect (27 Sep 2026): Klein 4B asks who and pose, a ticked Copy Pose also reads the clothes, and Prepare was refused
  // for a field the page never showed. Each fill a ticked recipe reads and the open recipe lacks is shown here, starting from this
  // character's remembered answer; a recipe with its own edited wording reads no answers. The server still refuses any bracket left.
  function planNeeds(engines=planEngines()){const identity=pairKey();return StudioContinuation.combinePlanFills(selected,engines.filter(p=>p.id!==selected.id&&!combineWording.has(identity+'|'+p.id)));}
  function planFill(meaning){if(meaning==='outfit')return String(planFills.outfit||'');if(Object.prototype.hasOwnProperty.call(planFills,meaning))return String(planFills[meaning]||'');const saved=rememberedFills();return String(saved['@'+meaning]||'');}
  // What Prepare sends: the recipe Generate would run, the ticked recipes, the seeds, the answers and any wording edited per recipe.
  function planIntent(engines,seeds){
    const identity=pairKey(),wording={},answers=combineAnswers();for(const fill of planNeeds(engines))answers[fill.meaning]=planFill(fill.meaning);
    for(const p of engines)if(p.id!==selected.id&&combineWording.has(identity+'|'+p.id))wording[p.id]=combineWording.get(identity+'|'+p.id);
    const base={preset_id:selected.id,controls:values(),continuation:continuationState?{...continuationState}:null,parent_assets:[...parentAssets],references:attachedReferencePayload(),expected_template_sha256:recipeTemplateHash};
    const name=('Combine · '+engines.map(p=>StudioContinuation.combineEngineLabel(p)).join(' / ')+' · seed'+(seeds.length>1?'s ':' ')+seeds.join(', ')).slice(0,120);
    return{name,combine_plan:{base,engines:engines.map(p=>p.id),seeds,answers:Object.fromEntries(Object.entries(answers).filter(([,v])=>String(v||'').trim())),wording}};
  }
  function planStamp(){return JSON.stringify(planIntent(planEngines(),planSeeds().seeds));}
  function syncCombinePlan(){
    if(enginePanel.hidden){planEnginesMarkup='';return;}
    // #1198: the form belongs to one pair. Switching engines keeps it; another pair starts from its own recipe and seed.
    const pair=pairKey();
    if(pair!==planPair){planPair=pair;planChoice.clear();planPreset=null;planSeeded=false;q('#uxPlanSeeds').value='';for(const key of Object.keys(planFills))delete planFills[key];if(!planBusy){planPrepared=null;planStatus('');}}
    // A recipe opened here starts the choice with itself ticked; the ticks otherwise survive switching engines.
    if(planPreset!==selected.id){if(!planChoice.size)planChoice.add(selected.id);planPreset=selected.id;}
    // The seeds start from the open recipe's seed once per pair, so the field can be emptied and retyped (#1198).
    if(!planSeeded&&getControl('seed')?.value){planSeeded=true;if(!q('#uxPlanSeeds').value)q('#uxPlanSeeds').value=getControl('seed').value;}
    const busy=combineBusy(),options=planOptions();
    const markup='<legend>Recipes</legend>'+options.map(({preset:p,reason})=>{const per=planPerPicture(p);
      return '<label class="ux-plan-engine"><input type="checkbox" data-ux-plan-engine="'+escape(p.id)+'" '+(planChoice.has(p.id)&&!reason?'checked ':'')+(reason||busy?'disabled ':'')+'title="'+escape(reason||p.name)+'"> <b>'+escape(StudioContinuation.combineEngineLabel(p))+'</b> <small>'+escape(reason||(per?'~'+durationLabel(per)+' per picture':'no timing yet'))+'</small></label>';}).join('');
    if(markup!==planEnginesMarkup){planEnginesMarkup=markup;q('#uxPlanEngines').innerHTML=markup;}
    // Re-rendered only when the set of fields changes, never while one is being typed in.
    const needs=planNeeds(),needsKey=JSON.stringify(needs);
    if(needsKey!==planFillsMarkup){planFillsMarkup=needsKey;q('#uxPlanFills').hidden=!needs.length;
      q('#uxPlanFills').innerHTML=needs.length?'<p class="muted">The ticked recipes also read these; the open recipe does not ask for them.</p>'+needs.map(f=>'<label>'+escape(f.label)+' <small>for '+escape(f.recipes.join(', '))+'</small><input data-ux-plan-fill="'+escape(f.meaning)+'" placeholder="'+escape(f.example?'e.g. '+f.example:'')+'" value="'+escape(planFill(f.meaning))+'" autocomplete="off"></label>').join(''):'';}
    const engines=planEngines(),{seeds,error}=planSeeds(),count=engines.length*seeds.length,time=StudioContinuation.combinePlanTime(engines.map(planPerPicture),seeds.length);
    const timing=time.unknown?(time.seconds?' · at least ~'+durationLabel(time.seconds)+'; '+time.unknown+' recipe'+(time.unknown===1?' has':'s have')+' no timing yet':' · no timing on this PC yet'):' · about '+durationLabel(time.seconds);
    q('#uxPlanSummary').textContent=!engines.length?'Tick at least one recipe.':error?error:count>16?count+' pictures: a plan runs at most 16. Untick a recipe or a seed.'
      :engines.length+' recipe'+(engines.length===1?'':'s')+' × '+seeds.length+' seed'+(seeds.length===1?'':'s')+' = '+count+' picture'+(count===1?'':'s')+timing+'. Prepare gives the checked total.';
    q('#uxPlanPrepare').disabled=busy||!engines.length||!!error||count>16;
    // Start runs exactly what was prepared: any later change to the pair, recipes, seeds or wording withdraws it.
    const fresh=!!planPrepared&&!planPrepared.started&&planPrepared.stamp===planStamp();
    q('#uxPlanStart').hidden=!fresh;q('#uxPlanStart').disabled=busy;
    if(planPrepared&&!planPrepared.started&&!fresh&&!planPrepared.stale){planPrepared.stale=true;if(!planPrepared.failure)planStatus('Changed since preparing, so Start plan is withdrawn. Prepare again; the earlier plan stays in Compare & review, not started.');}
    // Undoing the change brings Start back with its Prepared line; the next change is announced again (#1198).
    else if(fresh&&planPrepared.stale){planPrepared.stale=false;delete planPrepared.failure;planStatus(planPrepared.message);}
  }
  q('#uxPlanEngines').onchange=e=>{const box=e.target.closest('[data-ux-plan-engine]');if(!box)return;if(box.checked)planChoice.add(box.dataset.uxPlanEngine);else planChoice.delete(box.dataset.uxPlanEngine);syncCombinePlan();};
  q('#uxPlanSeeds').oninput=()=>syncCombinePlan();
  // Outfit stays with this pair; other answers are saved by meaning for engine switches, not the fresh recipe's placeholder fields.
  q('#uxPlanFills').oninput=e=>{
    const meaning=e.target?.dataset?.uxPlanFill;if(!meaning)return;planFills[meaning]=e.target.value;
    if(meaning!=='outfit'){const key=fillsKey();if(key)try{const raw=JSON.stringify({...rememberedFills(),['@'+meaning]:e.target.value});draftStorage().setItem(key,raw);knownFills.set(key,raw);}catch(error){}}
    syncCombinePlan();
  };
  const planTime=seconds=>Number(seconds)>0?durationLabel(seconds):'unknown';
  q('#uxPlanPrepare').onclick=async()=>{
    if(planBusy||combineBusy())return;
    try{
      const blocked=continuationBlockers();if(blocked.length)throw Error(blocked.join(' '));
      if(!continuationSource||lastUploaded!==continuationState?.reference_file)throw Error('Put the source back before preparing a plan.');
      if(['reference','lastReference'].some(id=>q('#'+id).files?.length))throw Error('Finish attaching the chosen picture before preparing a plan.');
      const engines=planEngines(),{seeds,error}=planSeeds();if(error)throw Error(error);if(!engines.length)throw Error('Tick at least one recipe.');
      const intent=planIntent(engines,seeds),stamp=JSON.stringify(intent);
      planBusy=true;planPrepared=null;syncReady();syncCombinePlan();planStatus('Checking every recipe, its models and the pictures. Nothing is submitted.');
      const project=await post('/api/production',intent),estimate=project.combine?.estimate||{};
      planPrepared={project,stamp,message:'Prepared '+project.stages.length+' pictures: expected about '+planTime(estimate.total_seconds)+(estimate.total_upper_seconds?' (up to about '+planTime(estimate.total_upper_seconds)+')':'')+', '+(estimate.confidence||'no')+' confidence. Nothing has run. Press Start plan to run it.'};
      planStatus(planPrepared.message);
      if(typeof refreshProduction==='function')void refreshProduction(true);
    }catch(error){planStatus(error.message);announce(error.message,true);}
    finally{planBusy=false;syncReady();syncCombinePlan();}
  };
  q('#uxPlanStart').onclick=async()=>{
    const prepared=planPrepared;if(planBusy||combineBusy()||!prepared||prepared.started||prepared.stamp!==planStamp())return;
    planBusy=true;prepared.started=true;syncReady();syncCombinePlan();
    // Once the Start request returns, the plan has started: a failed refresh after it must not offer Start again (#1198).
    let begun=false;
    try{
      const project=await post('/api/production/'+encodeURIComponent(prepared.project.id)+'/start',{});begun=true;
      planStatus('Started. '+project.state.message+'. Each picture appears under Runs for these pictures as it finishes; the plan is in Compare & review.');
      await refresh();
    }catch(error){if(begun)announce('The plan started; the page could not refresh: '+error.message,true);else{prepared.started=false;prepared.failure=error.message;planStatus(error.message);announce(error.message,true);}}
    finally{planBusy=false;syncReady();syncCombinePlan();}
  };
  // #1203: this PC's owner answers for every picture the recipe made, e.g. "pose 3/4 · face 1/4"; none reads as such (K14).
  function engineChecks(preset){return 'Loaded checks: '+(StudioReviewChecks.summary((typeof assetRecords==='function'?assetRecords():assetState.assets).filter(a=>a.preset_id===preset.id&&a.media_type==='image'&&a.trashed_at==null),StudioReviewChecks.forPreset(preset))||'none');}
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
  const posePanel=element('section','ux-pose-editor');posePanel.id='uxPoseEditor';posePanel.hidden=true;enginePanel.after(posePanel);
  // Folded on a picture route (the pose picture is the input there), open on a recipe that is drawn for (#422).
  posePanel.innerHTML='<details id="uxPoseDisclosure"><summary><h3>Draw the pose</h3><small id="uxPoseSummaryHint"></small></summary><p>Drag a joint, or pick one below and nudge it with the arrow keys (1 %, or 5 % with Shift). Use this pose puts the drawing on Picture 1; nothing runs until you press Generate.</p>'
    +'<div class="ux-pose-layout"><canvas id="uxPoseCanvas" tabindex="0" role="application" aria-roledescription="pose editor" aria-label="Pose skeleton. Drag a joint, or pick one in the joint list and use the arrow keys. Select a joint in the list, then arrow keys move it 1%, Shift+arrow moves 5%."></canvas>'
    +'<div class="ux-pose-side"><label for="uxPoseStart">Start from<select id="uxPoseStart"><option value="">Keep this drawing</option>'
    +StudioPoseEditor.PRESETS.map(p=>'<option value="'+escape(p.id)+'">'+escape(p.label)+'</option>').join('')+'</select></label>'
    +'<div id="uxPoseJoints" class="ux-pose-joints" role="group" aria-label="Joints"></div>'
    +'<fieldset class="ux-pose-position"><legend id="uxPosePositionLabel">Joint position (pixels)</legend><label for="uxPoseX">X<input id="uxPoseX" aria-describedby="uxPoseStatus" type="number" min="0" step="0.01" inputmode="decimal"></label><label for="uxPoseY">Y<input id="uxPoseY" aria-describedby="uxPoseStatus" type="number" min="0" step="0.01" inputmode="decimal"></label><button type="button" id="uxPosePositionApply">Set joint position</button><button type="button" id="uxPosePositionReset">Reset fields</button></fieldset>'
    +'<div class="ux-pose-actions"><button type="button" id="uxPoseUnknown">Mark unknown</button><button type="button" id="uxPoseUndo">Undo</button><button type="button" id="uxPoseRedo">Redo</button><button type="button" id="uxPoseUse" class="primary" aria-describedby="uxPoseReason">Use this pose</button></div>'
    +'<p id="uxPoseReason" class="muted"></p><p id="uxPoseStatus" role="status"></p></div></div></details>';
  let posePoints=null,poseHome=null,poseHeld=null,poseHeldShown='',poseLoading=null,poseCanvas={width:1024,height:1536},poseTimeline=StudioPoseEditor.timeline(POSE_UNDO),poseJoint=0,poseBusy=false,poseDrag=-1,poseSignature='',posePositionSignature='';
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
    if(poseLoading)return 'The attached pose guide’s drawing is loading into the editor.';
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
  function poseSizeHold(){return poseActive()?StudioPoseEditor.guideSizeReason(referenceRecords,poseCanvasSize(),selected.id!==POSE_RECIPE&&!StudioPoseEditor.drawsGuide(selected)?'Replace pose picture with drawing':'Use this pose',{artifact:poseHeldArtifact(),loading:poseLoading?.artifact_id,blocked:poseBlockedReason()}):'';}
  function posePositionDirty(){
    if(!poseActive()||!posePoints?.[poseJoint]||posePositionSignature!==JSON.stringify([poseJoint,posePoints[poseJoint],poseCanvas]))return false;
    try{const value=StudioPoseEditor.positionInput(q('#uxPoseX').value,q('#uxPoseY').value,poseCanvas),point=posePoints[poseJoint];
      return value.x!==Math.round(point.x*100)/100||value.y!==Math.round(point.y*100)/100;
    }catch(_){return true;}
  }
  function syncPosePosition(){
    const point=posePoints?.[poseJoint],signature=JSON.stringify([poseJoint,point,poseCanvas]);
    q('#uxPosePositionLabel').textContent=StudioPoseEditor.LABELS[poseJoint]+(point?' position (pixels)':' is unknown · restore it to set a position');
    for(const key of ['x','y']){
      const input=q(key==='x'?'#uxPoseX':'#uxPoseY');input.max=key==='x'?poseCanvas.width:poseCanvas.height;
      input.disabled=poseBusy||!point;
      // Readiness polling must not replace partially typed coordinates for the same joint.
      if(signature!==posePositionSignature){input.value=point?Math.round(point[key]*100)/100:'';input.removeAttribute('aria-invalid');}
    }
    posePositionSignature=signature;q('#uxPosePositionApply').disabled=poseBusy||!point;q('#uxPosePositionApply').title=poseBusy?'The drawing is being rendered.':point?'':'Restore this joint first.';
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
  let poseOpenFor=null;
  function syncPoseEditor(){
    const active=poseActive();
    posePanel.hidden=!active;if(!active)return;
    // Each recipe opens the panel at its own default once; after that the owner's open or close stands.
    const drawn=selected.id===POSE_RECIPE||StudioPoseEditor.drawsGuide(selected);
    if(poseOpenFor!==selected.id){poseOpenFor=selected.id;q('#uxPoseDisclosure').open=drawn;}
    q('#uxPoseSummaryHint').textContent=drawn?'This recipe’s picture 1 is the drawing.':'Optional: swap the pose picture for a stick figure.';
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
  // replaces it with whatever figure the editor held (#947). Each attached guide record is considered once (a restore makes
  // a new record, so it is read again); Undo or Start from never pull the stored drawing back over the user's choice.
  // The editor "holds" a guide only while its drawing still matches the one adopted or rendered for it (poseHeld).
  const poseSeen=new WeakSet();
  function poseHeldArtifact(){return poseHeld&&posePoints&&StudioPoseEditor.holds(posePoints,poseCanvas,poseHeld)?poseHeld.id:'';}
  function loadPoseSource(){
    const guide=StudioPoseEditor.drawnGuide(referenceRecords),id=guide?.artifact_id;
    if(!guide||poseSeen.has(guide)||guide===poseLoading||poseBusy||poseDrag>=0||posePositionDirty())return;
    if(!/^[a-f0-9]{64}$/.test(id||'')||id===poseHeldArtifact()){poseSeen.add(guide);return;}
    // An edit made while the read is in flight wins over the stored drawing; the button waits for the read.
    poseLoading=guide;let loaded=null;const before={points:StudioPoseEditor.resize(posePoints,poseCanvas,poseCanvas),canvas:{...poseCanvas}};syncPoseActions();
    api('/api/pose/artifacts/'+id,{signal:AbortSignal.timeout(30000)}).then(value=>{loaded=StudioPoseEditor.fromArtifact(value,guide);}).catch(()=>{}).then(()=>{
      if(poseLoading===guide)poseLoading=null;
      // A newer guide, an inactive editor or a render in flight wins; a later sync reads this guide again.
      const attached=StudioPoseEditor.drawnGuide(referenceRecords)===guide&&poseActive();
      const idle=!poseBusy;
      const pendingPosition=posePositionDirty();
      const current=attached&&idle&&poseDrag<0&&!pendingPosition;
      const edited=!StudioPoseEditor.holds(posePoints,poseCanvas,before);
      // The same guide stayed attached and the user edited mid-read: keep even an unapplied position draft or a drag before its first move.
      if(loaded&&attached&&idle&&(edited||pendingPosition||poseDrag>=0)){poseSeen.add(guide);poseStatus('You were editing the pose while the attached guide’s drawing was loading, so your drawing was kept.');}
      else if(loaded&&current){
        const next=StudioPoseEditor.resize(loaded,guide,poseCanvas);
        poseHeld={id,points:next,canvas:{...poseCanvas}};poseSeen.add(guide);
        pushPose();poseEdit(StudioPoseEditor.adopt(posePoints,next));
        poseStatus('The attached pose guide’s drawing is back in the editor. Undo returns to the previous drawing. Nothing was submitted.');
      }else if(!loaded){poseSeen.add(guide);poseStatus('The drawing behind the attached pose guide could not be read. The picture stays attached.');}
      syncReady();
    });
  }
  function poseEdit(next,remember=true){
    posePoints=next;if(remember)poseHome=poseHome.map((point,index)=>posePoints[index]||point);
    poseSignature='';renderPoseJoints();drawPose();syncPoseActions();
    // Undo, Redo, Start from or any edit can make the editor stop (or start) holding the guide: Generate's hold follows.
    if(poseHeldArtifact()!==poseHeldShown)syncReady();
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
      const result=StudioPoseEditor.guideResponse(response,body);poseHeld={id:result.artifact_id,points:StudioPoseEditor.resize(posePoints,poseCanvas,poseCanvas),canvas:{...poseCanvas}};
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
    const RESULT_LIMIT=24,runWhen=seconds=>{const at=new Date(Number(seconds)*1000);if(!Number(seconds)||isNaN(at))return'';return at.toDateString()===new Date().toDateString()?at.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):at.toLocaleString([],{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});};
    const record=currentPair(),matches=jobs.filter(job=>StudioContinuation.sameCombinePair(record,job,catalog.presets));
    const recordOf=id=>typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id);
    const groups=StudioContinuation.combineRuns(matches,output=>recordOf(output.asset_id)?.trashed_at!=null);
    const engine=job=>StudioContinuation.combineEngineLabel(catalog.presets.find(p=>p.id===job.preset_id)||{id:job.preset_id,name:job.preset_name});
    const pictures=referenceRecords.filter(r=>r.file&&!r.missing).length+(lastUploaded?1:0);
    const total=groups.runs.reduce((sum,run)=>sum+run.outputs.length,0);let room=RESULT_LIMIT;
    const lock=combineBusy()?'disabled title="'+(!pairActionBusy&&!submitting&&!poseBusy&&posePositionDirty()?'Set or reset the typed joint position first.':'Wait for the current Combine action to finish.')+'"':'';
    const info=(job,output)=>{const asset=recordOf(output.asset_id),review=asset?.review||'unreviewed';return{asset,seed:escape(output.seed??job.controls?.seed??'unknown'),label:asset?({selected:'Kept',needs_work:'Needs work',rejected:'Not this',unreviewed:'Unreviewed'}[review]||review):asset===null?'Asset unavailable':output.asset_id?'Saved review not loaded':'No saved asset identity'};};
    const src=(job,index)=>escape(globalThis.StudioPrivacy?.mediaUrl('/api/image/'+encodeURIComponent(job.id)+'/'+index,job)||'/api/image/'+encodeURIComponent(job.id)+'/'+index);
    const tile=(job,output,index)=>{
      const {asset,seed,label}=info(job,output),id=escape(job.id),mark=pairActionBusy?'disabled':'';
      return '<article class="ux-result-tile"><img src="'+src(job,index)+'" alt="'+escape(engine(job))+' result, seed '+seed+'"><b>Seed '+seed+'</b><span>'+escape(label)+'</span><div class="ux-result-actions">'+(output.asset_id&&asset!==null?'<button type="button" data-ux-review="selected" data-asset="'+escape(output.asset_id)+'" '+mark+'>Keep</button><button type="button" data-ux-review="needs_work" data-asset="'+escape(output.asset_id)+'" '+mark+'>Needs work</button>':'')+'<button type="button" data-ux-rerun="same" data-job="'+id+'" data-index="'+index+'" '+lock+'>Prepare same seed</button><button type="button" data-ux-rerun="new" data-job="'+id+'" data-index="'+index+'" '+lock+'>Prepare new seed</button></div>'+(output.asset_id?(asset?'<div class="ux-result-checks" role="group" aria-label="Quick checks for seed '+seed+', keys 1 to 5">'+StudioReviewChecks.chipsHTML({tags:asset.tags||[],names:StudioReviewChecks.forPreset(catalog.presets.find(p=>p.id===job.preset_id)),attr:'data-ux-check',asset:output.asset_id,disabled:pairActionBusy,escape})+'</div>':'<p><button type="button" data-ux-check-load="'+escape(output.asset_id)+'" data-asset="'+escape(output.asset_id)+'" '+mark+'>'+(asset===null?'Check availability':'Load saved checks')+'</button></p>'):'')+'</article>';
    };
    const runs=groups.runs.map(({job,outputs})=>{
      if(room<=0)return'';const shown=outputs.slice(0,room);room-=shown.length;
      const facts=[Number(job.elapsed_seconds)>0?durationLabel(job.elapsed_seconds):'',outputs.length+' seed'+(outputs.length===1?'':'s'),runWhen(job.created_at),job.project_id?'from a plan':''].filter(Boolean).join(' · ');
      const checked=StudioReviewChecks.summary(outputs.map(({output})=>recordOf(output.asset_id)).filter(Boolean),StudioReviewChecks.COMBINE);
      return '<div class="ux-run-group"><div class="ux-run-head"><b>'+escape(engine(job))+'</b><small>'+escape(facts)+'</small>'+(checked?'<small class="ux-run-checks">Loaded checks: '+escape(checked)+'</small>':'')+'<button type="button" data-ux-result-recipe="'+escape(job.id)+'">Recipe</button></div><div class="ux-run-seeds">'+shown.map(({output,index})=>tile(job,output,index)).join('')+'</div></div>';
    }).join('');
    // Grid (#1204): rows are recipes, columns are seeds, every cell one size. Recipe names of runs from a plan (project_id) stay behind Reveal; ordinary runs show theirs. A cell without a picture shows its state and offers no rerun.
    const grid=resultPanel.grid===true&&groups.runs.length>0,plans=groups.runs.concat(groups.active,groups.attention).map(({job})=>job.project_id).filter(Boolean),shown=resultPanel.revealedPlans instanceof Set?resultPanel.revealedPlans:new Set(),revealed=plans.some(id=>shown.has(id)),hidden=job=>grid&&!!job.project_id&&!shown.has(job.project_id),call=job=>hidden(job)?'A planned run':engine(job);resultPanel.hiddenPlans=plans.filter(id=>!shown.has(id));// Reveal covers only the plans on screen when pressed: another pair's plan or a new plan stays blind
    const gridMarkup=()=>{
      const rows=new Map(),seeds=new Set();let left=RESULT_LIMIT;
      const cell=(job,seed)=>{const key=(job.project_id?job.project_id+'|':'')+job.preset_id,k=String(seed??'unknown');if(!rows.has(key))rows.set(key,{key,job,cells:new Map()});const row=rows.get(key);seeds.add(k);if(!row.cells.has(k))row.cells.set(k,{done:[],other:[]});return row.cells.get(k);};
      for(const {job,outputs} of groups.runs)for(const {output,index} of outputs)if(left-->0)cell(job,output.seed??job.controls?.seed).done.push({job,output,index});
      for(const {job} of groups.active.concat(groups.attention))cell(job,job.controls?.seed).other.push(job);
      const hash=text=>[...text].reduce((h,c)=>(h*31+c.charCodeAt(0))>>>0,7),list=[...rows.values()];
      // Ordinary rows first, then planned ones in a fixed order that is not the plan's own, and Reveal never reorders them.
      const ordered=list.filter(r=>!r.job.project_id).concat(list.filter(r=>r.job.project_id).sort((a,b)=>hash(a.key)-hash(b.key))),columns=[...seeds].sort((a,b)=>(isNaN(a)-isNaN(b))||(a-b)||0);
      const word=job=>{const text=String(job.status||'unknown');return text[0].toUpperCase()+text.slice(1);},held=/^(\d+):(\d+)$/.exec(resultPanel.gridFocus||''),start=held&&Number(held[1])<ordered.length&&Number(held[2])<columns.length?resultPanel.gridFocus:'0:0';let letter=0;
      const body=ordered.map((row,r)=>{
        const name=hidden(row.job)?'Candidate '+String.fromCharCode(65+letter++):engine(row.job);
        return '<div role="row" class="ux-grid-row"><span role="rowheader" class="ux-grid-name">'+escape(name)+'</span>'+columns.map((k,c)=>{
          const data=row.cells.get(k),first=data?.done[0],at=r+':'+c;let inner='<span class="ux-grid-state">No picture</span>';
          if(first){
            const {asset,seed,label}=info(first.job,first.output),extra=[data.done.length>1?'Newest of '+data.done.length+' pictures':'',data.other.length?'Also: '+data.other.map(word).join(', '):''].filter(Boolean).join(' · '),mark=pairActionBusy?'disabled':'',who=escape(name+', seed '+k);
            inner='<img src="'+src(first.job,first.index)+'" alt="'+escape(name)+' result, seed '+seed+'"><span>'+escape(label)+'</span>'+(extra?'<small>'+escape(extra)+'</small>':'')+(first.output.asset_id&&asset!==null?'<div class="ux-result-actions"><button type="button" data-ux-review="selected" data-asset="'+escape(first.output.asset_id)+'" aria-label="Keep '+who+'" '+mark+'>Keep</button><button type="button" data-ux-review="needs_work" data-asset="'+escape(first.output.asset_id)+'" aria-label="Needs work '+who+'" '+mark+'>Needs work</button></div>':'');
          }else if(data?.other.length)inner='<span class="ux-grid-state">'+escape(data.other.map(word).join(', '))+'</span><small>No picture. Nothing runs again from here.</small>';
          return '<div role="gridcell" class="ux-grid-cell" tabindex="'+(at===start?0:-1)+'" data-ux-cell="'+at+'" aria-label="'+escape(name+', seed '+k)+'">'+inner+'</div>';
        }).join('')+'</div>';
      }).join('');
      const note=letter?'<p class="ux-grid-note">Recipe names are hidden for runs from a plan. <button type="button" data-ux-reveal>Reveal recipes</button></p>':revealed&&ordered.some(r=>r.job.project_id)?'<p class="ux-grid-note">Recipe names are revealed in this view. Leaving Grid hides them again; the Review desk keeps the recorded blind review.</p>':'';
      return note+'<div class="ux-grid" role="grid" aria-label="Runs for these pictures: rows are recipes, columns are seeds" style="--cols:'+columns.length+'"><div role="row" class="ux-grid-row"><span role="columnheader" class="ux-grid-name">Recipe</span>'+columns.map(k=>'<span role="columnheader">Seed '+escape(k)+'</span>').join('')+'</div>'+body+'</div>';
    };
    const live=groups.active.map(({job})=>'<p class="ux-run-live">'+escape(engine(job))+' · '+escape(job.status)+(runWhen(job.created_at)?' since '+escape(runWhen(job.created_at)):'')+'</p>').join('');
    const count=groups.attention.length;
    const attention=count?'<details class="ux-run-attention"><summary>'+count+' run'+(count===1?'':'s')+' for these pictures need'+(count===1?'s':'')+' attention</summary>'+groups.attention.map(({job})=>'<p><b>'+escape(call(job))+' · '+escape(job.status)+'</b>'+(runWhen(job.created_at)?' · '+escape(runWhen(job.created_at)):'')+' <small>'+escape(hidden(job)?'':String(job.message||'').slice(0,160))+'</small> '+(StudioContinuation.combineInProblems(job)?'<button type="button" data-ux-problem="'+escape(job.id)+'">Open in Problems</button>':hidden(job)?'':'<button type="button" data-ux-result-recipe="'+escape(job.id)+'">Recipe</button>')+'</p>').join('')+'<p><small>Each run keeps its recipe and any prompt IDs. Nothing here runs it again.</small></p></details>':'';
    const view=groups.runs.length?'<div class="ux-grid-tools"><button type="button" data-ux-grid aria-pressed="'+grid+'" title="Rows are recipes, columns are seeds">Grid</button></div>':'';
    const markup='<h3>Runs for these pictures</h3><p>'+(grid?'Rows are recipes and columns are seeds. Arrow keys move between pictures; K keeps and W marks needs work. Nothing here runs a generation.':'Newest first. Prepare a seed to load its recipe; Generate is still your press.')+'</p>'+view+(grid?gridMarkup():live+(runs?'<div class="ux-experiment-strip">'+runs+'</div>':'<p class="ux-no-results">'+(pictures>1?'No runs for these pictures yet.':'Attach both pictures to see their runs.')+'</p>'))+(total>RESULT_LIMIT?'<p>Showing the latest '+RESULT_LIMIT+' of '+total+' outputs. All of them stay in the library.</p>':'')+attention+'<p id="uxPairActionStatus" role="status"></p>';
    if(markup!==resultMarkup){const open=!!resultPanel.querySelector('.ux-run-attention')?.open,onCell=document.activeElement?.closest?.('[data-ux-cell]')?.dataset.uxCell;resultMarkup=markup;resultPanel.innerHTML=markup;const folded=resultPanel.querySelector('.ux-run-attention');if(folded)folded.open=open;if(onCell)resultPanel.querySelector('[data-ux-cell="'+onCell+'"]')?.focus();}
  }
  resultPanel.onclick=async e=>{
    const button=e.target.closest('button');
    // Switching the view or revealing recipe names reads only what is already loaded; it never waits on an action.
    if(button&&!button.disabled&&(button.dataset.uxGrid!==undefined||button.dataset.uxReveal!==undefined)){
      const view=button.dataset.uxGrid!==undefined;if(view){resultPanel.grid=!resultPanel.grid;resultPanel.revealedPlans=new Set();}else resultPanel.revealedPlans=new Set([...(resultPanel.revealedPlans||[]),...(resultPanel.hiddenPlans||[])]);
      syncCombineResults();resultPanel.querySelector(view?'[data-ux-grid]':'[data-ux-cell][tabindex="0"]')?.focus();return;}
    if(!button||button.disabled||pairActionBusy)return;
    if(button.dataset.uxResultRecipe){try{await exportRecipe(button.dataset.uxResultRecipe);}catch(error){announce(error.message,true);}return;}
    if(button.dataset.uxProblem){
      // Reveal this run's own card: Problems shows the newest five until asked for all, so ask before looking again.
      const id=button.dataset.uxProblem,card=()=>{const box=q('#jobProblems');if(box)box.open=true;return [...(box?.querySelectorAll('[data-problem]')||[])].find(el=>el.dataset.problem===id&&!el.closest('.problemsPutAway'));};
      let found=card();if(!found){q('#jobProblems [data-problems-toggle="all"]')?.click();found=card();}
      if(!found||!focusReadinessTarget(found))announce('This run is not in the open Problems list. Its recipe stays available here.',true);
      return;}
    if(!button.dataset.uxReview&&!button.dataset.uxRerun&&!button.dataset.uxCheck&&!button.dataset.uxCheckLoad)return;
    const stamp=setupStamp(),check=button.dataset.uxCheck,load=button.dataset.uxCheckLoad,refocus=(check||load)&&button===document.activeElement;pairActionBusy=true;syncReady();let status='',current=()=>stamp===setupStamp();
    try{
      if(check||button.dataset.uxReview||load){
        const scope=typeof assetState==='object'?assetState.workspace_id:null,epoch=typeof assetWorkspaceEpoch==='number'?assetWorkspaceEpoch:0,id=load||button.dataset.asset;
        current=()=>stamp===setupStamp()&&scope===(typeof assetState==='object'?assetState.workspace_id:null)&&epoch===(typeof assetWorkspaceEpoch==='number'?assetWorkspaceEpoch:0);
        if(load){
          if(typeof resolveAssetIDs!=='function'||!await resolveAssetIDs([id])||!current())throw Error('The workbench or Workspace changed while reading saved checks. Nothing was saved.');
        }else{
          await refreshAssets();if(!current())throw Error('The workbench or Workspace changed while reading this picture. Nothing was saved.');
          if(typeof assetRecord==='function'&&!assetRecord(id)&&!await resolveAssetIDs([id]))throw Error('The Workspace changed while reading this picture. Nothing was saved.');
          if(!current())throw Error('The workbench or Workspace changed while reading this picture. Nothing was saved.');
        }
        const asset=typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id);
        if(!asset||asset.trashed_at!=null)throw Error('This picture is unavailable in the active library. Nothing was saved.');
        if(load)status='Loaded saved review and checks. Nothing was saved.';
        else if(check){
          const tags=StudioReviewChecks.cycle(asset.tags,check),now=StudioReviewChecks.answer(tags,check);
          await mutateAssets({action:'edit',ids:[asset.id],tags});status='Saved: '+check+' '+(now===null?'not checked':now?'yes':'no')+'.';
        }else{
          await mutateAssets({action:'edit',ids:[id],review:button.dataset.uxReview});
          status=button.dataset.uxReview==='selected'?'Kept.':'Needs-work decision saved.';
        }
      }else{
        const job=jobs.find(j=>j.id===button.dataset.job),index=Number(button.dataset.index),output=job?.outputs?.[index];
        if(job?.status!=='completed'||!output)throw Error('Only a completed run can prepare another seed. Inspect unresolved work in Problems.');
        const recipe=await api('/api/jobs/'+encodeURIComponent(job.id)+'/recipe'),check=await post('/api/recipe-check',recipe);
        if(stamp!==setupStamp())throw Error('The workbench changed while reading this recipe. Your current work was kept.');
        const target=catalog.presets.find(p=>p.id===recipe.preset_id);if(!target)throw Error('This recipe is no longer available.');
        const seed=output.seed??recipe.controls?.seed;if(seed==null)throw Error('This run has no recorded seed. Inspect its recipe before preparing another.');let next=seed;
        if(button.dataset.uxRerun==='new'){next=crypto.getRandomValues(new Uint32Array(1))[0];if(String(next)===String(seed))next=(next+1)%4294967296;}
        const setup={preset:target.id,look:recipe.look,continuation:recipe.continuation,controls:{...recipe.controls,seed:String(next)},batch_count:1,parent_assets:recipe.parent_assets,references:StudioContinuation.combineReferences(target,recipe.references||[])};
        selectPreset(target.id,true,true);applySaved(setup);
        recipeTemplateHash=check.template_sha256;draftDirty=true;saveDraft();updateReady();recipeChanged();
        status=(button.dataset.uxRerun==='new'?'New seed ':'Recorded seed ')+next+' prepared. Review the recipe, then Generate.';
      }
    }catch(error){status=error.message;announce(status,true);}
    finally{
      pairActionBusy=false;syncReady();const line=q('#uxPairActionStatus');if(line)line.textContent=status;
      if(refocus&&current())[...resultPanel.querySelectorAll('[data-ux-check],[data-ux-check-load]')].find(b=>(!check||b.dataset.uxCheck===check)&&b.dataset.asset===(load||button.dataset.asset))?.focus();
    }
  };
  // Number keys 1-5 press the quick checks of the seed tile holding focus.
  resultPanel.addEventListener('keydown',e=>{
    const tile=e.target.closest?.('.ux-result-tile'),index=StudioReviewChecks.keyIndex(e);if(!tile||index<0||e.defaultPrevented)return;
    const chip=tile.querySelectorAll('[data-ux-check]')[index];if(!chip)return;e.preventDefault();if(!chip.disabled){chip.focus();chip.click();}
  });
  // Grid: arrows move between cells (one tab stop, roving); K and W press the cell's Keep and Needs work, the only review writes this strip has.
  resultPanel.addEventListener('focusin',e=>{const cell=e.target.closest?.('[data-ux-cell]');if(!cell)return;resultPanel.gridFocus=cell.dataset.uxCell;for(const other of resultPanel.querySelectorAll('[data-ux-cell]'))other.tabIndex=other===cell?0:-1;});
  resultPanel.addEventListener('keydown',e=>{
    const cell=e.target.closest?.('[data-ux-cell]');if(!cell||e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey)return;
    const [row,col]=cell.dataset.uxCell.split(':').map(Number),move={ArrowUp:[-1,0],ArrowDown:[1,0],ArrowLeft:[0,-1],ArrowRight:[0,1]}[e.key],mark={k:'selected',w:'needs_work'}[e.key.toLowerCase()];
    if(move){const next=resultPanel.querySelector('[data-ux-cell="'+(row+move[0])+':'+(col+move[1])+'"]');e.preventDefault();next?.focus();}
    else if(mark){const button=cell.querySelector('[data-ux-review="'+mark+'"]');e.preventDefault();if(button&&!button.disabled)button.click();}
  });
  after('renderJobs',()=>{syncCombineEngines();syncCombineResults();});after('renderAssets',()=>{syncCombineEngines();syncCombineResults();});
  function workbenchStamp(){return JSON.stringify({privacy:draftPrivacy,backend:typeof backendActive==='undefined'?null:backendActive,switching:typeof backendSwitching!=='undefined'&&!!backendSwitching,preset:selected?.id,controls:values(),parents:parentAssets,references:attachedReferencePayload(),continuation:continuationState,batch:q('#batch').value,pending:['reference','lastReference'].map(id=>[...(q('#'+id).files||[])].map(f=>[f.name,f.size,f.lastModified]))});}
  // Slot and picker attachment preserves wording, so its guard compares attachment-relevant
  // state only: wording, lineage claims and batch must not refuse a copy that was already
  // verified against its own destination (#606 finding 3). Replace resets to the recipe
  // defaults, and handoff baselines and shared-setup adoption review the whole task, so
  // those keep the whole-workbench stamp.
  function attachStamp(){const slots=selected?.reference_slots?.length?referenceRecords.map(r=>({file:r.file||null,missing:!!r.missing,role:r.role||null})):[];return JSON.stringify({preset:selected?.id,slots,named:[uploaded||null,lastUploaded||null],pending:['reference','lastReference'].map(id=>[...(q('#'+id).files||[])].map(f=>[f.name,f.size,f.lastModified]))});}
  function syncContinuation(){
    contextPanel.hidden=!continuationState;if(!continuationState)return;
    const source=continuationSource,cap=selected?.continuation_capability;
    q('#uxContinuationImage').src='/api/assets/'+encodeURIComponent(continuationState.source_asset_id)+'/file'+(globalThis.StudioPrivacy?.creation()==='private'?'?privacy=all':'');
    q('#uxContinuationTitle').textContent=source?.title||'Saved source · '+continuationState.source_asset_id;
    const reusable=source?.prompt_origin==='submitted-output'&&source?.prompt_role==='description'&&typeof source.positive==='string';
    q('#uxContinuationOrigin').textContent=cap?.prompt_role==='none'?'This operation has no text prompt.':reusable&&q('#positive').value===source.positive?'Prompt matches this output’s submitted description.':q('#positive').value.trim()?'Using your editable wording for this pass.':'Wording needed: '+(cap?.prompt_role==='instruction'?'say what to change and what to preserve.':cap?.prompt_role==='motion'?'describe the motion and camera movement.':'describe the resulting image you want.');
    q('#positive').placeholder=cap?.prompt_role==='instruction'?'For example: Change the lighting. Keep the subject, clothing, pose and composition.':cap?.prompt_role==='motion'?'For example: A gentle breeze moves the clothing; the camera slowly moves closer.':'Describe the subject, clothing, scene and style to preserve. The recipe example is not used.';
    q('#uxContinuationGuidance').innerHTML=StudioContinuation.guidance(selected,source).map(text=>'<p>'+escape(text)+'</p>').join('');
    q('#uxContinuationPrompt').textContent=source?.positive||sourceReadError||'No submitted source wording is available.';
    q('#uxContinuationRecord').textContent=source?'Prompt '+(source.prompt_id||'unavailable')+' · source SHA-256 '+source.sha256:'Reading the retained source; no new model request.';
    const restoreWhy=submitting?'Wait for the current submission.':cap?.prompt_role!=='description'?'This recipe takes '+(cap?.prompt_role==='instruction'?'an instruction':cap?.prompt_role==='motion'?'a motion brief':'no text')+', not the source description.':!source?(sourceReadError||'Still reading the source.'):!reusable?'The source has no submitted description to restore.':'';
    q('#uxRestoreSourcePrompt').disabled=!!restoreWhy;q('#uxRestoreSourcePrompt').title=restoreWhy;q('#uxRestoreSourceReason').textContent=restoreWhy&&!submitting?'Restore source wording: '+restoreWhy:'';
    q('#uxChangeRoute').disabled=submitting;q('#uxLeaveContinuation').disabled=submitting;
    q('#generate').textContent=cap?.operation==='upscale'?'Upscale source →':cap?.operation==='restyle'?'Restyle source →':cap?.operation==='combine'?'Combine pictures →':cap?.prompt_role==='motion'?'Animate source →':'Generate source-based pass →';
  }
  async function readSource(id,captured){const owner=captured||globalThis.StudioPrivacy?.capture?.();const context=!captured&&owner?.privacy==='private'?{...owner,scope:'all'}:owner;return api('/api/assets/'+encodeURIComponent(id)+'/context',{signal:AbortSignal.timeout(30000),...privacyOptions(context)});}
  async function hydrateContinuation(){
    const claim=continuationState,stamp=JSON.stringify(claim),epoch=selectionEpoch;sourceReadError='';syncReady();if(!claim)return;
    const current=()=>epoch===selectionEpoch&&stamp===JSON.stringify(continuationState);
    try{const source=await readSource(claim.source_asset_id);if(!current())return;if(source?.asset_id!==claim.source_asset_id||source.sha256!==claim.source_sha256)throw Error('Source identity changed. Reopen the handoff.');continuationSource=source;}
    catch(error){if(current())sourceReadError='Could not verify source metadata: '+error.message;}
    finally{if(current())syncReady();}
  }
  q('#uxRestoreSourcePrompt').onclick=()=>{const source=continuationSource;if(!source||q('#uxRestoreSourcePrompt').disabled)return;if(q('#positive').value!==source.positive&&!window.confirm('Replace your current wording with this output’s submitted description?'))return;q('#positive').value=source.positive;if(selected.negative)q('#negative').value=source.negative||'';draftDirty=true;saveDraft();syncReady();};
  q('#uxChangeRoute').onclick=()=>openHandoff(continuationState.source_asset_id,selected.id);
  q('#uxLeaveContinuation').onclick=leaveContinuation;
  async function reattachSource(){
    if(!continuationState||pickerBusy||handoffBusy||submitting||restoring)return;
    const claim=continuationState,stamp=JSON.stringify(claim),epoch=selectionEpoch,captured=globalThis.StudioPrivacy?.capture?.(),busyOwner={};
    const current=()=>pickerBusyOwner===busyOwner&&epoch===selectionEpoch&&(!captured||captured.revision===globalThis.StudioPrivacy?.capture?.().revision);
    pickerBusyOwner=busyOwner;pickerBusy=true;syncReady();
    try{
      const result=await post('/api/assets/reference',{id:claim.source_asset_id},privacyOptions(captured));
      if(!current())return;
      if(stamp!==JSON.stringify(continuationState))throw Error('The task changed while the source was being put back. Nothing was attached.');
      if(result.sha256!==claim.source_sha256||result.parent_asset!==claim.source_asset_id||result.context?.sha256!==claim.source_sha256)throw Error('The library copy of the source changed. Reopen Continue with this asset.');
      // A fresh staged copy has a fresh name; the claim follows it, the identity (source hash) does not change.
      const renamed=StudioContinuation.normalize({...claim,reference_file:result.file});if(!renamed)throw Error('The staged copy could not be verified. Reopen Continue with this asset.');
      // A Vary block on this continuation follows the renamed copy: putting the source back does not apply the carried stack.
      if(varyUnapplied?.stamp===stamp)varyUnapplied={...varyUnapplied,stamp:JSON.stringify(renamed)};
      continuationState=renamed;continuationSource=result.context;secondPicture=null;secondPanel.hidden=true;
      attachContinuationSource(result,false);pendingInputs.delete(StudioContinuation.sourceInput(selected.continuation_capability)==='last_reference'?'lastReference':'reference');
      draftDirty=true;saveDraft();syncCreate();announce(StudioContinuation.sourceLabel(selected)+' holds the source again. No generation submitted.');
    }catch(error){if(current())announce(error.message,true);}
    finally{if(pickerBusyOwner===busyOwner){pickerBusyOwner=null;pickerBusy=false;syncReady();}}
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
    const epoch=selectionEpoch,captured=globalThis.StudioPrivacy?.capture?.(),busyOwner={};
    const current=()=>pickerBusyOwner===busyOwner&&epoch===selectionEpoch&&(!captured||captured.revision===globalThis.StudioPrivacy?.capture?.().revision);
    pickerBusyOwner=busyOwner;pickerBusy=true;syncReady();
    try{
      if(item.file){const transfer=new DataTransfer();transfer.items.add(item.file);selectPreset(selected.id,true,true);q('#reference').files=transfer.files;legacyReferenceChange?.call(q('#reference'),new Event('change'));}
      else{
        // Keep the reviewed draft live until a verified copy is ready. The reset and
        // existing source owner then commit synchronously, with no second request.
        // Replace resets to the recipe defaults, so wording typed while the copy runs is
        // newer work the stale confirmation must not wipe: whole-workbench guard.
        const stamp=workbenchStamp(),refs=referenceEpoch,result=await post('/api/assets/reference',{id:item.asset.id},privacyOptions(captured));
        if(!current())return;
        if(referencePending||epoch!==selectionEpoch||refs!==referenceEpoch||stamp!==workbenchStamp()||secondPicture!==item)throw Error('The workbench changed while the picture was being copied. It was not applied.');
        if(result?.parent_asset!==item.asset.id||result?.sha256!==item.asset.sha256||result?.context?.asset_id!==item.asset.id||result?.context?.sha256!==item.asset.sha256||!StudioContinuation.normalize({...continuationState,reference_file:result?.file,source_asset_id:item.asset.id,source_sha256:item.asset.sha256}))throw Error('The replacement attachment could not be verified. The current source was kept.');
        selectPreset(selected.id,true,true);attachContinuationSource(result);
      }
      dismissSecondPicture();
      draftDirty=true;saveDraft();syncCreate();announce('Continuation ended. '+secondName(item)+' is now the reference; the prompt is the recipe default.');
    }catch(error){if(current())announce(error.message,true);}
    finally{if(pickerBusyOwner===busyOwner){pickerBusyOwner=null;pickerBusy=false;syncReady();}}
  };
  // The existing slot attachment owner arbitrates late copies and preserves slot roles.
  q('#uxSecondSlots').onclick=async e=>{
    const button=e.target.closest('[data-ux-second-slot]'),item=secondPicture,index=Number(button?.dataset.uxSecondSlot);
    if(!button||pickerBusy||handoffBusy||submitting||restoring||referencePending||!item?.asset||!continuationState)return;
    if(StudioContinuation.sourceInput(selected.continuation_capability)!=='reference'||!Number.isInteger(index)||index<1||!selected.reference_slots?.[index])return;
    if(referenceRecords[index]?.file&&!referenceRecords[index]?.missing&&!window.confirm('Replace Picture '+(index+1)+' with '+secondName(item)+'? Picture 1 and your wording stay unchanged.'))return;
    const ownedFocus=secondPanel.contains(document.activeElement),epoch=selectionEpoch,captured=globalThis.StudioPrivacy?.capture?.(),busyOwner={};
    const current=()=>pickerBusyOwner===busyOwner&&epoch===selectionEpoch&&(!captured||captured.revision===globalThis.StudioPrivacy?.capture?.().revision);
    pickerBusyOwner=busyOwner;pickerBusy=true;button.disabled=true;secondPanel.setAttribute('aria-busy','true');syncReady();
    try{
      if(!await pullIntoSlot(index,item.asset.id,current)||!current())return;
      const returnFocus=ownedFocus&&view==='create'&&(secondPanel.contains(document.activeElement)||document.activeElement===document.body);
      if(secondPicture===item)dismissSecondPicture();
      announce('Picture '+(index+1)+' attached. Your source and wording were kept. Review its role before generating.');
      if(returnFocus)focusReadinessTarget(q('[data-ref-contribution="'+index+'"]')||q('[data-ref-file="'+index+'"]'));
    }finally{if(pickerBusyOwner===busyOwner){pickerBusyOwner=null;pickerBusy=false;button.disabled=false;secondPanel.setAttribute('aria-busy','false');syncReady();}}
  };
  // A modal handoff carries IDs, not paths; selecting a destination never runs it.
  const handoff=element('dialog','studio-dialog ux-handoff');handoff.id='uxHandoff';handoff.setAttribute('aria-labelledby','uxHandoffTitle');handoff.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">CONTINUE WITH THIS ASSET</span><h2 id="uxHandoffTitle">Where should it go next?</h2></div><button data-ux-close="uxHandoff" aria-label="Close handoff">✕</button></div><div class="ux-handoff-layout"><div id="uxHandoffSource"></div><div><div id="uxHandoffIntents" class="ux-handoff-intents"></div><label for="uxDestination">Destination recipe<select id="uxDestination"></select></label><div id="uxHandoffDetails"></div><div id="uxRepairMark" class="ux-repair" hidden role="group" aria-labelledby="uxRepairTitle"><h3 id="uxRepairTitle">Mark the region to repair</h3><p>Drag a box over each part to redraw, such as a broken hand. Only the boxes are repainted; the rest of the picture is protected.</p><div class="ux-repair-pick"><img alt="Drag on the picture to mark the region to repair" draggable="false"></div><label for="uxRepairType">Or type a box in picture pixels<input id="uxRepairType" autocomplete="off" placeholder="x0,y0,x1,y1; …"></label><button type="button" data-ux-repair-add>Add box</button><ul id="uxRepairList" aria-label="Marked boxes"></ul></div><details><summary>Wording prepared for this pass</summary><pre id="uxHandoffPrompt"></pre></details><details><summary>Technical recipe notes</summary><p id="uxHandoffTechnical"></p></details><p class="callout">Prepare attaches a copy and fills the settings. Nothing runs until you press Generate.</p><p id="uxHandoffStatus" role="status"></p><button id="uxPrepareHandoff" class="primary">Prepare in Create →</button><p class="disabledReason"><small id="uxPrepareReason"></small></p></div></div>';document.body.append(handoff);
  function destinationDetails(){
    const p=catalog?.presets.find(p=>p.id===q('#uxDestination').value),cap=p?.continuation_capability;
    q('#uxHandoffDetails').innerHTML=p?StudioContinuation.guidance(p,sourceContext).map(text=>'<p>'+escape(text)+'</p>').join(''):'No supported source-consuming recipe is available for this task.';
    q('#uxHandoffTechnical').textContent=p?.description||'';
    const prepared=p?StudioContinuation.promptFor(p,sourceContext):null;
    q('#uxHandoffPrompt').textContent=cap?.prompt_role==='none'?'No prompt is used.':prepared!=null?prepared:cap?.prompt_role==='description'&&sourceContext?.prompt_role==='description'&&typeof sourceContext.positive==='string'?sourceContext.positive:'No recipe example will be inserted. '+(cap?.prompt_role==='instruction'?'Write the requested change after preparing.':cap?.prompt_role==='motion'?'Write a motion brief after preparing.':'Write a description of the intended image after preparing.');
    const repair=!!cap?.requires_mask,why=repair?repairReason(repairBoxes,sourceContext):'';q('#uxRepairMark').hidden=!repair;if(repair)renderRepair();
    q('#uxPrepareHandoff').disabled=!p||!sourceContext||!!why||handoffBusy||submitting;q('#uxPrepareReason').textContent=why||'';q('#uxDestination').disabled=handoffBusy;
  }
  function handoffRecipes(preferred){q('#uxHandoffIntents').innerHTML=U.INTENTS.filter(i=>i.id!=='create').map(i=>'<button data-ux-destination="'+i.id+'" aria-pressed="'+(i.id===handoffIntent)+'">'+i.verb+'</button>').join('');const recipes=StudioContinuation.destinations(handoffIntent,catalog?.presets||[],sourceContext);q('#uxDestination').innerHTML=recipes.map(p=>'<option value="'+escape(p.id)+'">'+escape(p.name)+(p.continuation_capability.requires_mask?' · mark the region to repair':'')+'</option>').join('');if(recipes.some(p=>p.id===preferred))q('#uxDestination').value=preferred;destinationDetails();}
  function assetDetailsDirty(){return q('#assetDialog').open&&activeAsset&&(q('#assetTitle').value!==activeAsset.title||q('#assetNotes').value!==activeAsset.notes||!assetTagsEqual(q('#assetTags').value,activeAsset.tags.join(', '))||q('#assetReview').value!==activeAsset.review);}
  function warnUnsavedAsset(){let notice=q('#uxAssetUnsaved');if(!notice){notice=element('p','callout');notice.id='uxAssetUnsaved';notice.setAttribute('role','status');q('#assetHandoffs').before(notice);}notice.textContent='Save your asset details before continuing. Your changes are still here.';q('#saveAssetDetails').focus();}
  document.addEventListener('click',e=>{if(e.target.closest('.ux-scene-link,#assetRecipe')&&assetDetailsDirty()){e.preventDefault();e.stopImmediatePropagation();warnUnsavedAsset();}},true);
  function openHandoff(id,preferred,epoch,intent){
    if(epoch!=null&&epoch!==handoffEpoch)return false;const request=++handoffEpoch;
    if(assetDetailsDirty()){warnUnsavedAsset();return false;}if(!catalog){announce('Recipes are still loading.');return false;}
    const a=(typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id));if(!a||a.trashed_at||a.media_type!=='image'){announce('Choose an available image from the Asset library.',true);return false;}
    handoffId=id;handoffAsset=a;repairBoxes=[];sourceContext=null;handoffBaseline=workbenchStamp();
    handoffIntent=intent||(/wan|h3/.test(preferred||'')?'animate':/trellis|hunyuan/.test(preferred||'')?'mesh':/^combine-/.test(preferred||'')?'combine':/style-pose|restyle-/.test(preferred||'')?'restyle':/fix|refine|upscale|esrgan|repair/.test(preferred||'')?'repair':'edit');
    q('#uxHandoffSource').innerHTML=assetPreview(a,true)+'<b>'+escape(a.title)+'</b><small>Source preserved · '+escape(({selected:'Kept',needs_work:'Needs work',rejected:'Not this',unreviewed:'Unreviewed'}[a.review||'unreviewed']||a.review))+'</small>';
    q('#uxHandoffStatus').textContent='Reading this output’s exact submitted prompt…';handoffRecipes(preferred);handoff.showModal();
    readSource(id).then(source=>{if(request!==handoffEpoch||!handoff.open)return;if(source?.version!==1||source.asset_id!==id||source.sha256!==a.sha256)throw Error('Source identity changed; refresh the library.');sourceContext=source;q('#uxHandoffStatus').textContent=source.warning||'Source and output-specific wording found. Preparing remains separate from running.';const current=q('#uxDestination').value;handoffRecipes(preferred||current);}).catch(error=>{if(request===handoffEpoch&&handoff.open){q('#uxHandoffStatus').textContent='Could not read source context: '+error.message;sourceContext=null;destinationDetails();}});
    return true;
  }
  q('#uxDestination').onchange=destinationDetails;
  // #1857 Repair a marked region: a masked-repair recipe reads an RGBA picture whose transparent part is the repair region. The owner
  // drags boxes on the picture (or types x0,y0,x1,y1); Prepare composes that input on the server and attaches it like any reference.
  // The mask is the owner's, never detected. Generate stays the owner's press.
  function repairParse(text){
    const boxes=String(text||'').split(';').map(part=>part.trim()).filter(Boolean).map(part=>part.split(/[\s,]+/).filter(Boolean).map(Number));
    return boxes.length&&boxes.every(box=>box.length===4&&box.every(Number.isInteger))?boxes:null;
  }
  function repairReason(boxes,source){
    if(!source)return 'Reading the picture…';
    if(source.width%8||source.height%8)return 'Masked repair needs a width and height divisible by 8; this picture is '+source.width+' × '+source.height+'.';
    if(!boxes.length)return 'Mark the region to repair: drag a box over it on the picture, or type x0,y0,x1,y1 and press Add box.';
    if(boxes.length>16)return 'Mark at most 16 boxes.';
    const outside=boxes.find(([x0,y0,x1,y1])=>!(0<=x0&&x0<x1&&x1<=source.width&&0<=y0&&y0<y1&&y1<=source.height));
    if(outside)return 'The box '+outside.join(',')+' is not inside the '+source.width+' × '+source.height+' picture.';
    const small=boxes.find(([x0,y0,x1,y1])=>x1-x0<8||y1-y0<8);
    return small?'The box '+small.join(',')+' is too small: each side needs at least 8 px.':null;
  }
  // The picture is shown scaled; a point on it maps back to source pixels.
  function repairPoint(pick,e,source){const r=pick.getBoundingClientRect();return [Math.round(Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*source.width),Math.round(Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))*source.height)];}
  function renderRepair(){
    const pick=q('#uxRepairMark').querySelector('.ux-repair-pick'),img=pick.querySelector('img');if(handoffAsset?.url&&img.getAttribute('src')!==handoffAsset.url)img.setAttribute('src',handoffAsset.url);
    pick.querySelectorAll('.ux-parallax-box').forEach(box=>box.remove());
    if(sourceContext?.width)for(const [x0,y0,x1,y1] of repairBoxes){const box=element('span','ux-parallax-box');Object.assign(box.style,{left:100*x0/sourceContext.width+'%',top:100*y0/sourceContext.height+'%',width:100*(x1-x0)/sourceContext.width+'%',height:100*(y1-y0)/sourceContext.height+'%'});pick.append(box);}
    q('#uxRepairList').innerHTML=repairBoxes.map((box,i)=>'<li>'+escape(box.join(', '))+' <button type="button" data-ux-repair-remove="'+i+'" aria-label="Remove box '+escape(box.join(','))+'">Remove</button></li>').join('');
  }
  function repairAdd(boxes){if(!handoffBusy){repairBoxes=repairBoxes.concat(boxes);destinationDetails();}}
  document.addEventListener('pointerdown',e=>{const pick=e.target.closest?.('.ux-repair-pick');if(!pick||e.button!==0||handoffBusy||!sourceContext?.width)return;e.preventDefault();repairDrag={pick,start:repairPoint(pick,e,sourceContext)};pick.setPointerCapture?.(e.pointerId);});
  document.addEventListener('pointerup',e=>{
    if(!repairDrag)return;const {pick,start}=repairDrag;repairDrag=null;if(!sourceContext?.width)return;const end=repairPoint(pick,e,sourceContext);
    const box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
    if(box[2]-box[0]<8||box[3]-box[1]<8){q('#uxHandoffStatus').textContent='A repair box needs at least 8 px on each side; drag a larger box.';return;}
    repairAdd([box]);
  });
  const repairTyped=()=>{const boxes=repairParse(q('#uxRepairType').value);if(!boxes){q('#uxHandoffStatus').textContent='Type boxes as x0,y0,x1,y1 in picture pixels, separated by semicolons.';return;}q('#uxRepairType').value='';repairAdd(boxes);};
  document.addEventListener('click',e=>{if(e.target.closest('[data-ux-repair-add]'))repairTyped();const remove=e.target.closest('[data-ux-repair-remove]');if(remove&&!handoffBusy){repairBoxes=repairBoxes.filter((_,i)=>i!==Number(remove.dataset.uxRepairRemove));destinationDetails();}});
  q('#uxRepairType').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();repairTyped();}});
  // The prepared RGBA input becomes this recipe's picture and the source its parent, as Make seamless attaches its seam cross.
  function beginRepair(result){
    const target=catalog.presets.find(p=>p.id===result?.preset_id&&p.requires_rgba_mask),context=result.context;
    if(!target)throw Error('The masked-repair recipe is unavailable.');
    if(submitting)throw Error('Wait for the current submission before preparing a repair.');
    selectPreset(target.id,true,true);
    uploaded=result.file;setHandoffParent('reference',result.plan.source_asset_id);q('#reference').value='';
    if(context?.prompt_origin==='submitted-output'&&context.prompt_role==='description'){if(target.positive&&typeof context.positive==='string')q('#positive').value=context.positive;if(target.negative&&typeof context.negative==='string')q('#negative').value=context.negative;}
    q('#batch').value=1;
    q('#referenceHint').textContent='Repair input from '+(context?.title||'the picture')+' · '+result.width+' × '+result.height+' · '+result.plan.boxes.length+' marked box'+(result.plan.boxes.length===1?'':'es')+'. Only the marked region is repainted.';
    updateReady();
  }
  async function prepareRepair(id,preset,source,current){
    const boxes=repairBoxes.map(box=>[...box]);
    const result=await post('/api/repair/prepare',{asset_id:id,preset_id:preset,boxes});
    if(!current())return false;
    if(!handoff.open||preset!==q('#uxDestination').value||handoffBaseline!==workbenchStamp()||JSON.stringify(boxes)!==JSON.stringify(repairBoxes))throw Error('The task or the marked boxes changed while the repair input was being prepared. Nothing was applied; press Prepare again.');
    if(result?.generation_submitted!==false||result.plan?.source_asset_id!==id||result.plan.source_sha256!==source.sha256||result.file!==result.plan.mask_file||JSON.stringify(result.plan.boxes)!==JSON.stringify(boxes))throw Error('The prepared repair input could not be verified. Nothing was applied.');
    beginRepair(result);
    return true;
  }
  q('#uxPrepareHandoff').onclick=async()=>{
    if(handoffBusy||q('#uxPrepareHandoff').disabled)return;
    const id=handoffId,preset=q('#uxDestination').value,epoch=handoffEpoch,selection=selectionEpoch,source=sourceContext;
    const current=()=>epoch===handoffEpoch&&selection===selectionEpoch;
    const busyOwner={};handoffBusyOwner=busyOwner;handoffBusy=true;destinationDetails();syncReady();
    try{
      if(handoffBaseline!==workbenchStamp())throw Error('The workbench changed while this handoff was open. Reopen it to review the current task.');
      if(catalog.presets.find(p=>p.id===preset)?.requires_rgba_mask){
        const count=repairBoxes.length;if(!await prepareRepair(id,preset,source,current))return;
        q('#assetDialog').close();handoff.close();draftDirty=true;showView('create');saveDraft();syncCreate();
        announce('Repair input attached: '+count+' marked box'+(count===1?' is':'es are')+' transparent and the rest of the picture is protected. Check the prompt, then press Generate.');contextPanel.scrollIntoView({block:'center'});return;
      }
      const result=await api('/api/assets/reference',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id}),signal:AbortSignal.timeout(30000)});
      if(!current())return;
      if(!handoff.open||preset!==q('#uxDestination').value||handoffBaseline!==workbenchStamp())throw Error('The task changed during attachment. The copy was staged but not applied; reopen the handoff.');
      if(result.context?.sha256!==source.sha256||result.context?.asset_id!==id||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The source record changed during attachment. Reopen the handoff before applying it.');
      beginContinuation(result,preset,handoffIntent);sourceReadError='';const style=pendingStyle;pendingStyle=null;
      const restyle=StudioContinuation.sourceInput(selected.continuation_capability)==='last_reference';
      q(restyle?'#lastReferenceHint':'#referenceHint').textContent='Attached source · '+result.width+' × '+result.height;q('#assetDialog').close();handoff.close();draftDirty=true;showView('create');saveDraft();syncCreate();
      if(!restyle){announce(style?'Source attached. This recipe has no style board, so the second picture was not attached; the prepared wording carries the look. Check it, then press Generate.':'Source attached. Check the prompt, then press Generate.');contextPanel.scrollIntoView({block:'center'});}
      else{const label=StudioContinuation.sourceLabel(selected).toLowerCase(),op=selected.continuation_capability?.operation,board=op==='combine'?'Picture 1 (the picture whose pose you want)':selected.continuation_capability?.keeps_picture&&selected.style_weight?'the style board (off until you raise Style weight)':selected.continuation_capability?.prompt_role==='instruction'?'Picture 1 (the picture drawn the way you want)':'the style board';
        if(style?.file){announce('Source attached as the '+label+'; your picture is uploading to Picture 1.');void uploadRoleFile(0,style.file);}
        else if(style?.asset){announce('Source attached as the '+label+'; your picture goes on Picture 1.');void pullIntoSlot(0,style.asset.id);}
        else{announce('Source attached as the '+label+'. Now add '+(op==='combine'?'the picture whose pose you want to Picture 1':'a picture to Picture 1 of '+board)+', then press Generate.');focusReadinessTarget(q('[data-ref-file="0"]'));}}
    }catch(error){if(current())q('#uxHandoffStatus').textContent=error.message;}
    finally{if(handoffBusyOwner===busyOwner){handoffBusyOwner=null;handoffBusy=false;destinationDetails();syncReady();}}
  };
  handoff.addEventListener('close',()=>{if(!handoff.open){handoffEpoch++;sourceContext=null;pendingStyle=null;}});
  handoff.addEventListener('cancel',e=>{if(handoffBusy)e.preventDefault();});
  // Capture the old action before its old handler can perform an immediate transfer.
  async function openGalleryHandoff(id,preferred){const epoch=++handoffEpoch;if(!id){announce('This output has no saved asset identity. Refresh the workspace before attaching it.',true);return;}let asset=(typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id));if(!asset)try{if(!await resolveAssetIDs([id]))return;if(epoch!==handoffEpoch)return;asset=(typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id));}catch(err){if(epoch===handoffEpoch)announce('Could not refresh this output. '+err.message,true);return;}if(epoch!==handoffEpoch)return;openHandoff(id,preferred,epoch);}
  document.addEventListener('click',e=>{const button=e.target.closest('.reference-output,[data-handoff]');if(!button)return;e.preventDefault();e.stopImmediatePropagation();const output=button.dataset.job?jobs.find(j=>j.id===button.dataset.job)?.outputs?.[Number(button.dataset.index)]:null;if(button.classList.contains('reference-output')){void openGalleryHandoff(output?.asset_id,button.dataset.preset);return;}const id=activeAsset?.id;if(!id){announce('Choose an available image from the Asset library.',true);return;}openHandoff(id,button.dataset.preset||button.dataset.handoff);},true);
  after('openAsset',()=>{q('#uxAssetUnsaved')?.remove();if(!activeAsset)return;const a=activeAsset;const eligibility=U.sceneEligibility([a]);const make=(intent,label,primary)=>'<button'+(primary?' class="primary"':'')+' data-make-open="'+intent+'" data-asset="'+esc(a.id)+'">'+label+'</button>';q('#assetHandoffs').innerHTML=(!a.trashed_at&&a.media_type==='image'?(window.StudioMake?'<div class="ux-route-row" role="group" aria-label="Open in Make"><span>In Make</span>'+make('edit','Change it',true)+make('repair','Fix or upscale')+make('restyle','Restyle')+make('combine','New pose')+'</div><div class="ux-route-row" role="group" aria-label="Full editor"><span>Full editor</span>':'')+'<button'+(window.StudioMake?'':' class="primary"')+' data-ux-handoff="'+a.id+'">Continue with this →</button><button id="uxFindSourceRecipes">Find recipes for this image</button>'+(window.StudioMake?'</div>':''):'')+(!a.trashed_at&&['image','video','audio'].includes(a.media_type)?'<a class="ux-scene-link" href="/av.html?asset_ids='+encodeURIComponent(a.id)+'">'+(eligibility.ok?'Use in a scene':'Open scene source picker')+' ↗</a>':'');q('#assetRecipe').disabled=!a.job_id;q('#assetRecipe').textContent=a.job_id?'Recipe':'No recipe recorded';q('#assetRecipe').title=a.job_id?'':'This asset was not made by a Studio job, so there is no recipe to export.';});
  // #1202 Vary subtle / Vary strong: one press from a picture to a prepared round of close variations. The img2img route
  // attaches a copy through the same continuation as Continue with this (lineage = this picture) and, when it carries the
  // source's stack (WAI), copies the picture's recorded LoRA slots and sampling settings; a recipe with no route
  // reloads its own recipe with new seeds and records this picture as the parent. Generate stays the owner's press.
  let varyBusy=false;
  function varyMarkup(plan,attrs,why,recent=false){
    const reason=escape(StudioContinuation.varyHint(plan)),hint='<small id="'+why+'"'+(recent&&plan.kind==='none'?' class="run-why" title="'+reason+'"':'')+'>'+reason+'</small>';
    if(plan.kind==='none')return '<button type="button" disabled aria-describedby="'+why+'">Vary</button>'+hint;
    if(plan.kind==='reseed')return '<button type="button" data-ux-vary="reseed" '+attrs+' aria-describedby="'+why+'">Vary · new seeds, same recipe</button>'+hint;
    return '<button type="button" data-ux-vary="subtle" '+attrs+' aria-describedby="'+why+'">Vary subtle</button><button type="button" data-ux-vary="strong" '+attrs+' aria-describedby="'+why+'">Vary strong</button>'+hint;
  }
  function varyPlanFor(presetId,jobId,assetId,mediaType,status,make){
    const asset=(typeof assetRecord==='function'?assetRecord(assetId):assetState.assets.find(a=>a.id===assetId));
    // Make passes its own, fresher reading of the source run; the shared jobs list can lag it by one refresh.
    const job=jobs.find(j=>j.id===jobId),known=status||job?.status;if(known&&!['completed','partial'].includes(known))return{kind:'none',reason:'Wait for a completed source run before varying it. Inspect unresolved work in Problems.'};
    if(!assetId)return{kind:'none',reason:'This output has no saved asset identity. Refresh the workspace before varying it.'};
    const plan=StudioContinuation.varyPlan({preset_id:presetId,job_id:jobId||null,media_type:asset?asset.media_type:mediaType||'image',trashed_at:asset?.trashed_at||null},catalog?.presets||[],jobs,missingByPreset,typeof installedLoras==='undefined'?[]:installedLoras);
    if(plan.kind!=='img2img')return plan;
    if(asset?.bytes>20*1024*1024)return{kind:'none',reason:'This picture exceeds the 20 MiB reference limit. Use a smaller picture.'};
    // Make sends Vary in one press, so it rules out missing wording first; Create prepares the form and lets you describe it.
    if(!make)return plan;
    const source=typeof job?.controls?.positive==='string'?{positive:job.controls.positive,prompt_role:plan.source.continuation_capability?.prompt_role,prompt_origin:'submitted-output'}:null;
    const reason=varyProblem(plan,source);return reason?{kind:'none',reason}:plan;
  }
  function varyProblem(plan,source){
    const route=plan.route;if(StudioContinuation.sourceInput(route.continuation_capability)!=='reference')return route.name+' needs more than this picture. Use Continue with this.';
    const words=StudioContinuation.wording(route,source).positive;
    if(source&&route.positive&&!words.trim())return 'No description was kept for this picture, and '+route.name+' needs one. Use Continue with this and describe it.';
    return StudioContinuation.unfilled(route,words).length?route.name+' needs wording filled in. Use Continue with this.':'';
  }
  function syncAssetUnavailable(holder){
    if(holder?.id!=='assetNextSteps')return;
    const groups=['.ux-tile','.ux-parallax','.ux-vary'].map(selector=>holder.querySelector(selector)).filter(Boolean),focused=document.activeElement,
      // Fold only what cannot apply to this picture: a box with editable setup (or the focus) is mid-entry, not unavailable.
      blocked=groups.filter(box=>box.querySelector('button')?.disabled&&!box.contains(focused)&&!box.querySelector('input:not([disabled]),select:not([disabled]),textarea:not([disabled])'));let fold=holder.querySelector(':scope > .asset-unavailable');
    if(blocked.length&&!fold){fold=element('details','asset-unavailable','<summary></summary>');holder.append(fold);}
    let next=q('#assetFamilyActions');
    for(const box of groups.filter(box=>!blocked.includes(box)).reverse()){if(box.parentElement!==holder||box.nextElementSibling!==next)holder.insertBefore(box,next);next=box;}
    next=null;for(const box of [...blocked].reverse()){if(box.parentElement!==fold||box.nextElementSibling!==next)fold.insertBefore(box,next);next=box;}
    if(fold){if(blocked.length)fold.querySelector('summary').textContent='Not available for this picture ('+blocked.length+')';else fold.remove();}
    if(holder.contains(focused)&&document.activeElement!==focused)focused.focus({preventScroll:true});
  }
  // Rebuilt only when its words change, so polling never steals focus from a Vary button.
  function placeVary(holder,after,markup){
    let box=holder.querySelector('.ux-vary');if(box&&box.dataset.markup===markup)return;
    const next=element('div','ux-vary',markup);next.dataset.markup=markup;next.setAttribute('role','group');next.setAttribute('aria-label','Vary this picture');
    if(box)box.replaceWith(next);else after.after(next);syncAssetUnavailable(holder);
  }
  function syncGalleryVary(){
    if(!catalog)return;
    for(const card of q('#gallery').querySelectorAll('.imageCard')){
      const anchor=card.querySelector('.reference-output'),actions=card.querySelector('.card-actions');if(!anchor||!actions)continue;
      const job=jobs.find(j=>j.id===anchor.dataset.job),index=Number(anchor.dataset.index),output=job?.outputs?.[index];if(!job||!output)continue;
      const plan=varyPlanFor(job.preset_id,job.id,output.asset_id,output.media_type);
      placeVary(card,actions,varyMarkup(plan,'data-asset="'+escape(output.asset_id||'')+'" data-preset="'+escape(job.preset_id||'')+'" data-job="'+escape(job.id)+'"','uxVaryWhy-'+escape(job.id)+'-'+index,true));
    }
  }
  function syncOpenAssetVary(){
    const a=activeAsset,holder=q('#assetHandoffs')?.parentElement;if(!holder)return;
    // Vary is for pictures; a video, sound or model asset shows no Vary control at all.
    if(!a||a.media_type!=='image'){holder.querySelector('.ux-vary')?.remove();syncAssetUnavailable(holder);return;}
    const plan=varyPlanFor(a.preset_id,a.job_id,a.id,a.media_type);
    placeVary(holder,q('#assetHandoffs'),varyMarkup(plan,'data-asset="'+escape(a.id)+'" data-preset="'+escape(a.preset_id||'')+'" data-job="'+escape(a.job_id||'')+'"','uxVaryWhyAsset'));
  }
  // A backend switch reloads the LoRA inventory after these buttons were drawn. A 304 jobs poll does not redraw them.
  function refreshCarriedVary(){syncGalleryVary();syncOpenAssetVary();}
  globalThis.refreshCarriedVary=refreshCarriedVary;
  // Make (make.js) draws the same Vary buttons on its own results; the document click handler below prepares them.
  globalThis.StudioWorkbench={varyMarkup:(presetId,jobId,assetId,status)=>varyMarkup(varyPlanFor(presetId,jobId,assetId,'image',status,true),'data-asset="'+escape(assetId)+'" data-preset="'+escape(presetId||'')+'" data-job="'+escape(jobId||'')+'"','uxVaryWhyMake-'+escape(assetId))};
  after('renderJobs',syncGalleryVary);after('renderAssets',syncGalleryVary);
  after('openAsset',syncOpenAssetVary);
  async function prepareVary(button){
    const strength=button.dataset.uxVary,assetId=button.dataset.asset;
    if(varyBusy)return;
    if(sendBusy()||referencePending>0||tileBusy||parallaxBusy){announce('Wait for the current Create action to finish, then press Vary again. Nothing was prepared.',true);return;}
    if(assetDetailsDirty()){warnUnsavedAsset();return;}
    if(!catalog){announce('Recipes are still loading.');return;}
    const plan=varyPlanFor(button.dataset.preset,button.dataset.job,assetId);
    if(plan.kind==='none'){announce(plan.reason,true);return;}
    if(plan.kind==='reseed'?strength!=='reseed':!['subtle','strong'].includes(strength)){announce('This Vary button is out of date. Nothing was prepared; press Vary again.',true);syncGalleryVary();return;}
    // #1213: Vary replaces the Create setup, so ask first when it holds the owner's own wording or a staged picture (the pattern of Use this look and Start from this picture). Declining changes nothing.
    const own=key=>{const typed=String(q('#'+key)?.value||'').trim();return!!typed&&typed!==String(selected?.defaults?.[key]||'').trim();},ownWords=own('positive')||own('negative'),staged=stagedPicture();
    if((ownWords||staged)&&!window.confirm('Vary replaces the current Create setup'+(ownWords&&staged?' (your wording and the staged picture)':ownWords?' (your wording)':' (the staged picture)')+' with a prepared round of variations. Continue? Nothing will be generated.')){announce('Nothing changed. Vary was not prepared and your Create setup is kept.');return;}
    varyBusy=true;
    try{
      syncReady();
      const stamp=workbenchStamp();
      const seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
      if(plan.kind==='img2img'){
        const result=await post('/api/assets/reference',{id:assetId});
        if(stamp!==workbenchStamp())throw Error('The workbench changed while the picture was being copied. Nothing was applied; press Vary again.');
        if(result?.parent_asset!==assetId||result.context?.asset_id!==assetId||result.sha256!==result.context?.sha256)throw Error('The copied picture could not be verified. Nothing was applied.');
        beginContinuation(result,plan.route.id,'edit');sourceReadError='';varyUnapplied=null;
        // A carrying route (WAI) keeps the picture's recorded LoRA stack and sampling settings. A recorded file the
        // offline list does not offer is added as it was recorded; the server still refuses one that is not installed.
        // If one value cannot be set, Generate stays blocked on this continuation until Vary is pressed again.
        for(const [key,value] of Object.entries(plan.carry||{})){
          const input=getControl(key),text=String(value);
          if(input&&input.tagName==='SELECT'&&![...input.options].some(option=>option.value===text))input.append(new Option(text,text));
          if(input)input.value=text;
          if(!input||input.value!==text){
            const message='Vary could not keep '+key+' = '+text+' from the run of this picture, so Generate is blocked. Press Vary again or reopen Continue with this. Nothing was generated.';
            varyUnapplied={stamp:JSON.stringify(continuationState),message};updateReady();throw Error(message);
          }
        }
        if(plan.carry&&typeof updateLoraHints==='function')updateLoraHints();
        for(const [key,value] of Object.entries(plan.strengths[strength].controls)){const input=getControl(key);if(input)input.value=value;}
        q('#referenceHint').textContent='Attached source · '+result.width+' × '+result.height;
      }else{
        // The same recipe and words, new seeds. The picture is recorded as the parent; its pixels are not an input.
        const recipe=await api('/api/jobs/'+encodeURIComponent(button.dataset.job)+'/recipe');
        if(stamp!==workbenchStamp())throw Error('The workbench changed while the recipe was being read. Nothing was applied; press Vary again.');
        if(recipe?.preset_id!==plan.route.id)throw Error('This run no longer records '+plan.route.name+'. Nothing was applied.');
        const check=await post('/api/recipe-check',recipe);
        if(stamp!==workbenchStamp())throw Error('The workbench changed while the recipe was being checked. Nothing was applied; press Vary again.');
        selectPreset(plan.route.id,true,true);applySaved({preset:plan.route.id,look:recipe.look,controls:{...(recipe.controls||{})},batch_count:1,parent_assets:[assetId]});
        recipeTemplateHash=check.template_sha256;
      }
      const seedInput=getControl('seed');if(seedInput)seedInput.value=seed;
      q('#batch').value=String(plan.round.count);
      if(q('#assetDialog').open)q('#assetDialog').close();
      draftDirty=true;showView('create');saveDraft();syncCreate();updateReady();scheduleTimeEstimate();recipeChanged();
      const words=selected?.positive&&!String(q('#positive').value||'').trim()?' No submitted wording was kept for this picture: describe it before running.':'';
      announce(StudioContinuation.varyStatus(plan,strength==='reseed'?'subtle':strength,seed)+words,false,StudioContinuation.varyDefaults(plan));
    }catch(error){announce(error.message,true);}
    finally{varyBusy=false;syncReady();}
  }
  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-vary]');if(!button||button.disabled)return;e.preventDefault();void prepareVary(button);});
  // S3 one-press Polish (Fix face, Fix hands and details, Upscale) for Make: the same staged copy, claim and prepared wording as
  // Continue with this, sent as one job without touching Create's form. polishPlan only reads; polish posts /api/jobs once.
  const polishBusy=new Set();
  async function polishRoute(assetId,kind,captured){
    // A passing condition (recipes loading, a failed read) rejects, so Make asks again after its cool-down instead of caching a refusal (Muse, 19 Oct).
    if(!catalog)throw Error('Recipes are still loading.');
    let source;try{source=await readSource(assetId,captured);}catch(error){throw Error('Could not read this picture. '+error.message);}
    if(source?.asset_id!==assetId)throw Error('This picture’s record could not be verified. Refresh and try again.');
    // Make retries rejected plans; a resolved refusal would stay cached after the source finishes.
    const job=jobs.find(j=>j.id===source.job_id);if(job&&!['completed','partial'].includes(job.status))throw Error('Wait for a completed source run before polishing it. Inspect unresolved work in Problems.');
    return{...StudioContinuation.polishRoute(kind,catalog.presets,source,missingByPreset),source};
  }
  async function polishPlan(assetId,kind,captured=globalThis.StudioPrivacy?.capture?.()){
    const route=await polishRoute(assetId,kind,captured),timing=route.ok?StudioContinuation.combineTiming(jobs,route.preset.id):null;
    return{ok:!!route.ok,preset_id:route.preset?.id||null,reason:route.reason||'',...(timing?{seconds:timing.seconds}:{})};
  }
  async function polish(assetId,kind,label,captured=globalThis.StudioPrivacy?.capture?.()){
    const key=assetId+':'+kind;if(polishBusy.has(key))throw Error('This polish is already being sent. Wait for it.');
    if(sendBusy()||tileBusy||parallaxBusy)throw Error('Wait for the current action to finish before polishing this picture.');
    polishBusy.add(key);
    try{
      syncReady();
      const route=await polishRoute(assetId,kind,captured);if(!route.ok)throw Error(route.reason);
      const {preset,source}=route,result=await post('/api/assets/reference',{id:assetId},privacyOptions(captured));
      if(result?.parent_asset!==assetId||result.sha256!==source.sha256||result.context?.asset_id!==assetId||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The picture changed while it was being copied. Nothing was sent.');
      const prepared=StudioContinuation.initial(result.context,preset,'repair',result.file),controls={reference:result.file};
      if(preset.positive)controls.positive=prepared.positive;if(preset.negative)controls.negative=prepared.negative;
      if(preset.seed)controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
      return await post('/api/jobs',{preset_id:preset.id,...(captured?.privacy==='private'?{privacy:'private'}:{}),continuation:prepared.claim,controls,batch_count:1,parent_assets:[assetId],references:[],label:'Make · '+(typeof label==='string'&&label?label:StudioContinuation.POLISH[kind])},privacyOptions(captured));
    }finally{polishBusy.delete(key);syncReady();}
  }
  // #1497 Vary from Make: the round prepareVary sets up (same plan, wording, carried stack, strength and round size), sent as
  // one job without touching Create's form, so the #1213 overwrite question has nothing to protect. One press posts
  // /api/jobs once; a failed or uncertain post is reported, never sent again.
  const makeVaryBusy=new Set();
  // No HTTP answer (a dropped connection, an unreadable reply) means the job may exist: flag it so Make holds this Vary.
  const sendVary=(body,captured)=>post('/api/jobs',{...body,...(captured?.privacy==='private'?{privacy:'private'}:{})},privacyOptions(captured)).catch(error=>{if(error.status===undefined)error.uncertain=true;throw error;});
  async function vary(assetId,presetId,jobId,strength,status,captured=globalThis.StudioPrivacy?.capture?.()){
    if(makeVaryBusy.has(assetId))throw Error('Vary is already being sent for this picture. Wait for it.');
    if(sendBusy()||tileBusy||parallaxBusy)throw Error('Wait for the current action to finish before varying this picture.');
    makeVaryBusy.add(assetId);
    try{
      syncReady();
      if(!catalog)throw Error('Recipes are still loading.');
      const plan=varyPlanFor(presetId,jobId,assetId,'image',status,true);if(plan.kind==='none')throw Error(plan.reason);
      if(plan.kind==='reseed'?strength!=='reseed':!['subtle','strong'].includes(strength))throw Error('This Vary button is out of date. Nothing was sent; press Vary again.');
      const route=plan.route,seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647,base={preset_id:route.id,batch_count:plan.round.count,parent_assets:[assetId],references:[],label:'Make · '+(strength==='reseed'?'Vary':'Vary '+strength)};
      if(plan.kind==='reseed'){
        const recipe=await api('/api/jobs/'+encodeURIComponent(jobId)+'/recipe',privacyOptions(captured));
        if(recipe?.preset_id!==route.id)throw Error('This run no longer records '+route.name+'. Nothing was sent.');
        const check=await post('/api/recipe-check',{...recipe,...(captured?{privacy:captured.privacy}:{})},privacyOptions(captured));
        return await sendVary({...base,look:recipe.look,controls:{...(recipe.controls||{}),...(route.seed?{seed}:{})},expected_template_sha256:check.template_sha256},captured);
      }
      let source;try{source=await readSource(assetId,captured);}catch(error){throw Error('Could not read this picture. '+error.message);}
      if(source?.asset_id!==assetId)throw Error('This picture’s record could not be verified. Refresh and try again.');
      const reason=varyProblem(plan,source);if(reason)throw Error(reason);
      const result=await post('/api/assets/reference',{id:assetId},privacyOptions(captured));
      if(result?.parent_asset!==assetId||result.sha256!==source.sha256||result.context?.asset_id!==assetId||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The picture changed while it was being copied. Nothing was sent.');
      const prepared=StudioContinuation.initial(result.context,route,'edit',result.file);
      const controls={reference:result.file,...(StudioContinuation.canvasFor(result.context,route)||{}),...(plan.carry||{}),...plan.strengths[strength].controls};
      if(route.positive)controls.positive=prepared.positive;if(route.negative)controls.negative=prepared.negative;if(route.seed)controls.seed=seed;
      return await sendVary({...base,continuation:prepared.claim,controls},captured);
    }finally{makeVaryBusy.delete(assetId);syncReady();}
  }
  Object.assign(globalThis.StudioWorkbench,{polish,polishPlan,vary});
  // #1220 Make seamless: square, flat textures only. The server says whether this picture qualifies and a disabled button
  // carries its reason. Prepare rolls the texture and attaches its seam cross to the tile recipe; Generate stays the owner's press.
  let tileBusy=false,tileRead=0;
  function tileMarkup(status){
    const why='uxTileWhyAsset',bands=U.tileBands(status),note=!status?'Checking whether this picture can tile…':status.eligible?[status.flag,bands.note].filter(Boolean).join(' '):[status.reason,status.flag].filter(Boolean).join(' ');
    // Seam band (owner, 27 Sep 2026): wide hides a floor's repeating plank ends; narrow keeps more of the texture as generated.
    const band=bands.options.length?'<label>Seam band <select id="uxTileBand" data-ux-tile-band aria-describedby="'+why+'">'+bands.options.map(o=>'<option value="'+escape(o.value)+'"'+(o.selected?' selected':'')+(o.disabled?' disabled':'')+'>'+escape(o.label)+'</option>').join('')+'</select></label>':'';
    return band+'<button type="button" data-ux-tile="'+escape(status?.asset_id||'')+'"'+(status?.eligible?'':' disabled')+' aria-describedby="'+why+'">Make seamless</button><small id="'+why+'">'+escape(note)+'</small>';
  }
  function placeTile(holder,markup){
    let box=holder.querySelector('.ux-tile');if(box&&box.dataset.markup===markup)return;
    const chosen=box?.querySelector('[data-ux-tile-band]')?.value;
    const next=element('div','ux-tile',markup);next.dataset.markup=markup;next.setAttribute('role','group');next.setAttribute('aria-label','Make this texture tile');
    const band=next.querySelector('[data-ux-tile-band]');if(band&&chosen&&[...band.options].some(o=>o.value===chosen&&!o.disabled))band.value=chosen;
    if(box)box.replaceWith(next);else q('#assetHandoffs').after(next);syncAssetUnavailable(holder);
  }
  after('openAsset',()=>{
    const a=activeAsset,holder=q('#assetHandoffs')?.parentElement;if(!holder)return;
    if(!a||a.media_type!=='image'||a.trashed_at||!catalog?.presets?.some(p=>p.tile_route)){holder.querySelector('.ux-tile')?.remove();syncAssetUnavailable(holder);return;}
    const read=++tileRead,current=()=>read===tileRead&&activeAsset?.id===a.id;placeTile(holder,tileMarkup(null));
    api('/api/tiles/source/'+encodeURIComponent(a.id)).then(status=>{if(current())placeTile(holder,tileMarkup(status));})
      .catch(error=>{if(current())placeTile(holder,tileMarkup({asset_id:a.id,eligible:false,reason:'Could not check this picture: '+error.message+'.'}));});
  });
  async function prepareTile(button){
    const assetId=button.dataset.uxTile;if(tileBusy||!assetId)return;
    if(sendBusy()||parallaxBusy){announce('Wait for the current Create action to finish, then press Make seamless again. Nothing was prepared.',true);return;}
    if(assetDetailsDirty()){warnUnsavedAsset();return;}
    const bandPx=U.tileBandPx(button.parentElement?.querySelector('[data-ux-tile-band]')?.value);
    tileBusy=true;button.disabled=true;syncReady();
    const stamp=workbenchStamp(),detailEpoch=assetDetailEpoch;
    try{
      const result=await post('/api/tiles/prepare',{asset_id:assetId,...(bandPx==null?{}:{band_px:bandPx})});
      if(bandPx!=null&&result?.plan?.band_px!==bandPx)throw Error('The seam band came back different from the one chosen. Nothing was applied; press Make seamless again.');
      if(submitting||!assetDetailContextCurrent(assetId,detailEpoch)||stamp!==workbenchStamp())throw Error('The source picture or Create action changed while the texture was being prepared. Nothing was applied; press Make seamless again.');
      if(result?.plan?.source_asset_id!==assetId||result.file!==result.plan.rolled_file)throw Error('The prepared seam cross could not be verified. Nothing was applied.');
      beginTile(result);
      if(q('#assetDialog').open)q('#assetDialog').close();
      draftDirty=true;showView('create');saveDraft();syncCreate();updateReady();scheduleTimeEstimate();recipeChanged();
      announce('Seam cross prepared: the texture is rolled by half and only its centre cross ('+result.plan.band_px+' px seam band) will be repainted. '+(result.context?.positive?'Its own wording is kept. ':'No wording was kept for this texture: replace the bracketed description. ')+'Press Generate; the Studio then finishes the tile with its seam score and a 3×3 preview.');
    }catch(error){announce(error.message,true);}
    finally{tileBusy=false;button.disabled=false;syncReady();}
  }
  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-tile]');if(!button||button.disabled)return;e.preventDefault();void prepareTile(button);});
  // #1219 Make parallax layers: the owner names the foreground to lift out and may mark the far view (window glass, sky) as boxes,
  // typed as x0,y0,x1,y1 or dragged on the picture. The mask is the owner's, never detected. The server says whether the picture
  // qualifies; a disabled button carries its reason. Prepare attaches the picture unchanged and loads the clean-plate edit;
  // every Generate stays the owner's press.
  let parallaxBusy=false,parallaxRead=0,parallaxDrag=null;
  const generateFromCreate=q('#generate').onclick;
  q('#generate').onclick=function(...args){
    if(combineBusy()||tileBusy||parallaxBusy){announce('Wait for the current action to finish before pressing Generate. Nothing was submitted.',true);return;}
    return generateFromCreate.apply(this,args);
  };
  function parallaxBoxes(text){
    const boxes=String(text||'').split(';').map(part=>part.trim()).filter(Boolean).map(part=>part.split(/[\s,]+/).filter(Boolean).map(Number));
    return boxes.every(box=>box.length===4&&box.every(Number.isInteger))?boxes:null;
  }
  function parallaxReason(group){
    const status=group.parallaxStatus;
    if(!status)return 'Checking whether this picture can be split…';
    if(!status.eligible)return status.reason;
    if(!group.querySelector('#uxParallaxObjects').value.trim())return 'Name the foreground to lift out first, e.g. the desk, the chair and the lamp.';
    const boxes=parallaxBoxes(group.querySelector('#uxParallaxView').value);
    if(!boxes)return 'Far view boxes are x0,y0,x1,y1 in picture pixels, separated by semicolons.';
    if(boxes.length>status.max_views)return 'Mark at most '+status.max_views+' far view boxes.';
    const outside=boxes.find(([x0,y0,x1,y1])=>!(0<=x0&&x0<x1&&x1<=status.width&&0<=y0&&y0<y1&&y1<=status.height));
    return outside?'The box '+outside.join(',')+' is not inside the '+status.width+' × '+status.height+' picture.':null;
  }
  function syncParallax(group){
    const why=parallaxReason(group),button=group.querySelector('[data-ux-parallax]');if(!button)return;
    button.disabled=Boolean(why)||parallaxBusy;group.querySelector('#uxParallaxWhy').textContent=why||group.parallaxStatus.flag;syncAssetUnavailable(q('#assetNextSteps'));
    const pick=group.querySelector('.ux-parallax-pick'),status=group.parallaxStatus;if(!pick||!status?.width)return;
    pick.querySelectorAll('.ux-parallax-box').forEach(box=>box.remove());
    for(const [x0,y0,x1,y1] of parallaxBoxes(group.querySelector('#uxParallaxView').value)||[]){
      const box=element('span','ux-parallax-box');Object.assign(box.style,{left:100*x0/status.width+'%',top:100*y0/status.height+'%',width:100*(x1-x0)/status.width+'%',height:100*(y1-y0)/status.height+'%'});pick.append(box);
    }
  }
  function parallaxMarkup(status,url){
    const button='<button type="button" data-ux-parallax="'+escape(status?.asset_id||'')+'" disabled aria-describedby="uxParallaxWhy">Make parallax layers</button>';
    if(!status?.eligible)return button+'<small id="uxParallaxWhy">'+escape(status?status.reason:'Checking whether this picture can be split…')+'</small>';
    return '<label>Foreground to lift out <input id="uxParallaxObjects" maxlength="240" autocomplete="off" placeholder="e.g. the desk, the chair, the lamp and the monitor"></label>'
      +'<label>Far view boxes, optional <input id="uxParallaxView" autocomplete="off" placeholder="x0,y0,x1,y1; … in pixels, or drag on the picture below"></label>'
      +'<details class="ux-parallax-mark"><summary>Mark the far view on the picture</summary><p>Drag a box inside the window glass or the sky, not over its frame: what is inside moves as the far layer. No box: two layers.</p>'
      +'<div class="ux-parallax-pick"><img src="'+escape(url)+'" alt="Drag to mark the far view" draggable="false"></div></details>'
      +button+'<button type="button" data-ux-parallax-clear>Clear boxes</button><small id="uxParallaxWhy"></small>';
  }
  function placeParallax(holder,status,url){
    const next=element('div','ux-parallax',parallaxMarkup(status,url));next.setAttribute('role','group');next.setAttribute('aria-label','Split this picture into parallax layers');next.parallaxStatus=status;
    const box=holder.querySelector('.ux-parallax');if(box)box.replaceWith(next);else(holder.querySelector('.ux-tile')||q('#assetHandoffs')).after(next);
    if(status?.eligible)syncParallax(next);else syncAssetUnavailable(holder);
  }
  after('openAsset',()=>{
    const a=activeAsset,holder=q('#assetHandoffs')?.parentElement;if(!holder)return;
    if(!a||a.media_type!=='image'||a.trashed_at||!catalog?.presets?.some(p=>p.parallax_route)){holder.querySelector('.ux-parallax')?.remove();syncAssetUnavailable(holder);return;}
    const read=++parallaxRead,current=()=>read===parallaxRead&&activeAsset?.id===a.id;placeParallax(holder,null,a.url);
    api('/api/parallax/source/'+encodeURIComponent(a.id)).then(status=>{if(current())placeParallax(holder,status,a.url);})
      .catch(error=>{if(current())placeParallax(holder,{asset_id:a.id,eligible:false,reason:'Could not check this picture: '+error.message+'.'},a.url);});
  });
  after('openAsset',()=>{const fold=q('#assetNextSteps > .asset-unavailable');if(fold)fold.open=false;});
  document.addEventListener('input',e=>{const group=e.target.closest?.('.ux-parallax');if(group)syncParallax(group);});
  function pickPoint(pick,e){const r=pick.getBoundingClientRect(),s=pick.closest('.ux-parallax').parallaxStatus;return [Math.round(Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*s.width),Math.round(Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))*s.height)];}
  document.addEventListener('pointerdown',e=>{const pick=e.target.closest?.('.ux-parallax-pick');if(!pick||e.button!==0)return;e.preventDefault();parallaxDrag={pick,start:pickPoint(pick,e)};pick.setPointerCapture?.(e.pointerId);});
  document.addEventListener('pointerup',e=>{
    if(!parallaxDrag)return;const {pick,start}=parallaxDrag,end=pickPoint(pick,e);parallaxDrag=null;
    const box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])],group=pick.closest('.ux-parallax');
    if(box[2]-box[0]<8||box[3]-box[1]<8){announce('A far view box needs at least 8 px on each side; drag a larger box.',true);return;}
    const field=group.querySelector('#uxParallaxView');field.value=[field.value.trim(),box.join(',')].filter(Boolean).join('; ');syncParallax(group);
  });
  document.addEventListener('click',e=>{const clear=e.target.closest('[data-ux-parallax-clear]');if(!clear)return;const group=clear.closest('.ux-parallax');group.querySelector('#uxParallaxView').value='';syncParallax(group);});
  async function prepareParallax(button){
    const group=button.closest('.ux-parallax'),assetId=button.dataset.uxParallax;if(parallaxBusy||!assetId||!group)return;
    if(sendBusy()||tileBusy){announce('Wait for the current Create action to finish, then press Make parallax layers again. Nothing was prepared.',true);return;}
    if(assetDetailsDirty()){warnUnsavedAsset();return;}
    const why=parallaxReason(group);if(why){announce(why,true);return;}
    parallaxBusy=true;button.disabled=true;syncReady();
    const stamp=workbenchStamp(),detailEpoch=assetDetailEpoch,boxes=parallaxBoxes(group.querySelector('#uxParallaxView').value);
    try{
      const result=await post('/api/parallax/prepare',{asset_id:assetId,objects:group.querySelector('#uxParallaxObjects').value,...(boxes.length?{view:boxes}:{})});
      if(submitting||!assetDetailContextCurrent(assetId,detailEpoch)||stamp!==workbenchStamp())throw Error('The source picture or Create action changed while the picture was being prepared. Nothing was applied; press Make parallax layers again.');
      if(result?.plan?.source_asset_id!==assetId||result.file!==result.plan.source_file||result.stage!=='plate')throw Error('The prepared parallax plan could not be verified. Nothing was applied.');
      beginParallax(result);
      if(q('#assetDialog').open)q('#assetDialog').close();
      draftDirty=true;showView('create');saveDraft();syncCreate();updateReady();scheduleTimeEstimate();recipeChanged();
      announce('Parallax layers prepared: the picture is attached unchanged and the clean-plate edit is loaded ('+(boxes.length?boxes.length+' far view box'+(boxes.length===1?'':'es'):'no far view: two layers')+'). Press Generate; the isolate edit loads next for a second Generate, and the Studio splits the layers when both are in.');
    }catch(error){announce(error.message,true);}
    finally{parallaxBusy=false;if(group.isConnected)syncParallax(group);syncReady();}
  }
  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-parallax]');if(!button||button.disabled)return;e.preventDefault();void prepareParallax(button);});
  document.addEventListener('click',e=>{if(!e.target.closest('#uxFindSourceRecipes'))return;
    if(assetDetailsDirty()){warnUnsavedAsset();return;}const a=activeAsset;
    if(!a||a.trashed_at||a.media_type!=='image'||!window.RecipeShortlist){announce('Choose an available image after recipe guidance has loaded.',true);return;}
    // Read-only advice identity; do not reuse the source-staging or setup-apply handlers.
    const source={asset_id:a.id,sha256:a.sha256,title:a.title};q('#assetDialog').close();showView('create');
    document.dispatchEvent(new CustomEvent('studio:shortlist-source',{detail:source}));
  });
  after('renderAssets',()=>{if(assetScope==='unreviewed')q('#assetScopeTitle').textContent='Awaiting review';});
  // A selection a search or page move left unresolved is not judged from the loaded page: activation resolves it
  // through assetSelectionCanProceed (resolveAssetSelection), whose re-render judges every selected source.
  after('renderAssetSelection',()=>{const unresolved=typeof assetSelectionInfo==='function'&&assetSelectionInfo().unresolved,assets=[...assetSelection].map(id=>(typeof assetRecord==='function'?assetRecord(id):assetState.assets.find(a=>a.id===id))).filter(Boolean),eligibility=unresolved?{ok:true,reason:'Selected assets outside this page are checked before the scene opens.'}:U.sceneEligibility(assets),link=q('#createScene');link.setAttribute('aria-disabled',String(!eligibility.ok));link.title=eligibility.reason;link.classList.toggle('ux-disabled',!eligibility.ok);});
  document.addEventListener('click',e=>{const link=e.target.closest('#createScene');if(link&&link.getAttribute('aria-disabled')==='true'){e.preventDefault();e.stopImmediatePropagation();assetMessage(link.title,true);}},true);
  after('renderAssetSelection',()=>{
    let button=q('#uxFindSelectedRecipes');if(!button){button=element('button');button.id='uxFindSelectedRecipes';button.type='button';q('#createScene').before(button);}
    button.textContent='Find recipes for selected images ('+assetSelection.size+')';button.disabled=assetSelection.size===0;
    button.title='Review one to three selected library images in selection order; no attachment or generation.';
  });
  document.addEventListener('click',async e=>{if(!e.target.closest('#uxFindSelectedRecipes'))return;
    if(assetDetailsDirty()){warnUnsavedAsset();return;}
    const ids=[...assetSelection],scope=assetState.workspace_id,epoch=assetWorkspaceEpoch;
    const unavailable='Select one to three available images. Every selected image must have a saved identity; none were dropped.';
    if(!window.RecipeShortlist||ids.length<1||ids.length>3){assetMessage(unavailable,true);return;}
    try{
      if(!await resolveAssetIDs(ids)||assetState.workspace_id!==scope||assetWorkspaceEpoch!==epoch||JSON.stringify(ids)!==JSON.stringify([...assetSelection])){assetMessage('The Workspace or selection changed while reading the selected images. Choose the images again; nothing was applied.',true);return;}
      const items=ids.map(id=>assetRecord(id));
      if(items.some(a=>!a||a.trashed_at||a.media_type!=='image'||typeof a.sha256!=='string'||! /^[0-9a-f]{64}$/.test(a.sha256)))throw Error(unavailable);
      if(assetDetailsDirty()){warnUnsavedAsset();return;}
      // Preserve selection order, including selections outside the current filter. The chooser displays every image before Check.
      const sources=items.map(a=>({asset_id:a.id,sha256:a.sha256,title:a.title,role:'source'}));q('#assetDialog').close();showView('create');
      document.dispatchEvent(new CustomEvent('studio:shortlist-sources',{detail:sources}));
    }catch(error){assetMessage(error.message,true);}
  });
  // Pull any existing image into a named reference slot, without changing the recipe.
  const picker=element('dialog','studio-dialog');picker.id='uxSourcePicker';picker.setAttribute('aria-labelledby','uxPickerTitle');picker.innerHTML='<div class="dialog-heading"><h2 id="uxPickerTitle">Pull from your library</h2><button data-ux-close="uxSourcePicker" aria-label="Close source picker">✕</button></div><label for="uxSourceSlot">Use as<select id="uxSourceSlot"></select></label><label for="uxSourceSearch">Search saved images<input id="uxSourceSearch" type="search" maxlength="200" placeholder="Title, tags or recipe…"></label><p id="uxPickerStatus" role="status"></p><div id="uxSourceAssets" class="ux-picker-grid"></div><div id="uxSourcePaging"></div>';document.body.append(picker);
  // Three references cost three round trips only if the picker closes after each pick. It stays open,
  // advances to the next unfilled slot, and closes itself when every required slot holds one (#278 friction 4).
  function sourceSlotOptions(){return selected.reference_slots?.length?selected.reference_slots.map((r,i)=>'<option value="'+i+'">Picture '+(i+1)+' · '+escape(referenceRecords[i]?.role||r.role)+(referenceRecords[i]?.file&&!referenceRecords[i]?.missing?' · attached':'')+'</option>').join('')+(selected.last_reference?'<option value="lastReference">'+escape(selected.last_reference_label||'Last frame')+'</option>':''):'<option value="reference">'+escape(selected.reference_label||'Reference / first frame')+'</option>'+(selected.last_reference?'<option value="lastReference">'+escape(selected.last_reference_label||'Last frame')+'</option>':'');}
  function nextEmptySlot(){return selected.reference_slots?.length?referenceRecords.findIndex(r=>!r.file||r.missing):-1;}
  // The picker owns its reads: the Library page is one bounded slice, so saved images are searched and paged here (#1622).
  let sourcePage={assets:[],unavailable:[],next:null},sourceSeq=0,sourceSearchTimer=null;
  async function readSources(more){
    const seq=++sourceSeq,term=q('#uxSourceSearch').value.trim(),filters={visibility:'active',media_type:'image',sort:'newest',limit:100,details:true};
    if(term)filters.q=term;if(more&&sourcePage.next)filters.cursor=sourcePage.next;
    const data=await api(assetReadURL('/api/assets/page',filters));
    if(seq!==sourceSeq||!picker.open)return false;   // a newer search or a closed picker owns the list
    const unavailable=data?.unavailable_assets||[];
    if(!Array.isArray(data?.assets)||!Array.isArray(unavailable)||data.assets.length+unavailable.length>100||unavailable.some(item=>!item||typeof item.id!=='string'||typeof item.error!=='string'))throw Error('The saved-image page was not understood.');
    sourcePage={assets:more?[...sourcePage.assets,...data.assets]:data.assets,unavailable:more?[...(sourcePage.unavailable||[]),...unavailable]:unavailable,next:data.next_cursor||null};return true;
  }
  function renderSources(){
    const unavailable=sourcePage.unavailable||[];
    q('#uxSourceAssets').innerHTML=sourcePage.assets.map(a=>'<button data-ux-pull="'+a.id+'">'+assetPreview(a)+'<b>'+escape(a.title)+'</b><small>'+escape(({selected:'Kept',needs_work:'Needs work',rejected:'Not this',unreviewed:'Unreviewed'}[a.review||'unreviewed']||a.review))+'</small></button>').join('')||(unavailable.length?'<p>Saved-image details unavailable. The observed IDs and reasons are below.</p>':'<p>No matching saved images. Import an image in the Asset library first.</p>');
    q('#uxSourcePaging').innerHTML=(unavailable.length?'<p>'+sourcePage.assets.length+' available of '+(sourcePage.assets.length+unavailable.length)+' observed saved images loaded.</p>'+unavailableAssetDetails(unavailable):'')+(sourcePage.next?'<button type="button" data-ux-source-more>More saved images</button>':'');
  }
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
    sourcePage={assets:[],unavailable:[],next:null};q('#uxSourceAssets').replaceChildren();q('#uxSourcePaging').replaceChildren();q('#uxSourceAssets').setAttribute('aria-busy','true');
    const status=q('#uxPickerStatus');status.textContent='Loading saved images…';status.tabIndex=-1;
    picker.showModal();status.focus({preventScroll:true});
    try{
      const loaded=await readSources(false);
      if(request!==sourcePickerEpoch||!picker.open)return;
      if(epoch!==selectionEpoch||view!=='create'){picker.close();return;}
      if(!loaded)return;
      renderSources();status.textContent='Attach a copy. The original stays in your library.';
      q('#uxSourceSearch').disabled=false;q('#uxSourceSlot').disabled=false;
      if(document.activeElement===status)q('#uxSourceSearch').focus({preventScroll:true});
    }catch(error){if(request===sourcePickerEpoch&&picker.open)status.textContent='Could not read the library. Close and reopen to retry. '+error.message;}
    finally{if(request===sourcePickerEpoch){pickerLoading=false;q('#uxSourceAssets').setAttribute('aria-busy','false');syncSourceAvailability();}}
  }
  q('#uxPullAsset').onclick=openSourcePicker;
  picker.addEventListener('close',()=>{if(picker.open)return;sourcePickerEpoch++;sourceSeq++;clearTimeout(sourceSearchTimer);pickerLoading=false;syncSourceAvailability();});
  q('#uxSourceSearch').oninput=()=>{const request=sourcePickerEpoch;clearTimeout(sourceSearchTimer);sourceSearchTimer=setTimeout(async()=>{if(request!==sourcePickerEpoch||!picker.open)return;try{if(await readSources(false))renderSources();}catch(error){if(request===sourcePickerEpoch&&picker.open)q('#uxPickerStatus').textContent='Could not search the library. '+error.message;}},150);};
  q('#uxSourcePaging').onclick=async e=>{if(!e.target.closest('[data-ux-source-more]'))return;const request=sourcePickerEpoch;try{if(await readSources(true))renderSources();}catch(error){if(request===sourcePickerEpoch&&picker.open)q('#uxPickerStatus').textContent='Could not read more of the library. '+error.message;}};
  after('selectPreset',()=>{if(picker.open)picker.close();});
  async function pullIntoSlot(index,id,ownerCurrent=()=>true){
    const epoch=selectionEpoch,captured=globalThis.StudioPrivacy?.capture?.();
    const current=()=>ownerCurrent()&&epoch===selectionEpoch&&(!captured||captured.revision===globalThis.StudioPrivacy?.capture?.().revision);
    try{await attachReferenceAsset(index,id,current);if(!current())return false;draftDirty=true;saveDraft();syncCreate();return true;}
    catch(error){if(current())announce('The second picture was not attached. '+error.message,true);return false;}
  }
  q('#uxSourceAssets').onclick=async e=>{const button=e.target.closest('[data-ux-pull]');if(!button||pickerBusy)return;const request=sourcePickerEpoch,selection=selectionEpoch,current=()=>request===sourcePickerEpoch&&selection===selectionEpoch,busyOwner={};pickerBusyOwner=busyOwner;pickerBusy=true;button.disabled=true;syncReady();try{const id=button.dataset.uxPull,slot=q('#uxSourceSlot').value;
      if(continuationState){const input=StudioContinuation.sourceInput(selected.continuation_capability),isSource=input==='last_reference'?slot==='lastReference':slot==='reference'||slot==='0';
        if(isSource&&(!selected.reference_slots?.length||input==='reference')){picker.close();offerSecondPicture({asset:sourcePage.assets.find(a=>a.id===id)});return;}
        if(isSource)throw Error(StudioContinuation.sourceLabel(selected)+' is the picture you are continuing. Pull into another slot, or use Leave this continuation to start from this one.');}
      if(selected.reference_slots?.length&&slot!=='lastReference')await attachReferenceAsset(Number(slot),id,current);
      else{const stamp=attachStamp(),result=await post('/api/assets/reference',{id});if(!current())return;if(stamp!==attachStamp())throw Error('The workbench changed during attachment. Reopen the picker.');if(slot==='lastReference'){lastUploaded=result.file;q('#lastReference').value='';pendingInputs.delete('lastReference');}else{uploaded=result.file;q('#reference').value='';pendingInputs.delete('reference');}replaceParentAsset(slot==='lastReference'?'lastReference':'reference',null,id);}
      if(!current())return;
      draftDirty=true;saveDraft();syncCreate();
      const filled=referenceRecords.filter(r=>r.file&&!r.missing).length,boardDone=!!selected.reference_board&&filled>=(selected.reference_board.min??1);
      const remaining=boardDone?-1:nextEmptySlot();
      if(remaining<0){picker.close();announce('Saved source attached. No generation submitted.');}
      else{q('#uxSourceSlot').innerHTML=sourceSlotOptions();q('#uxSourceSlot').value=String(remaining);q('#uxPickerStatus').textContent='Attached. Picture '+(remaining+1)+' of '+referenceRecords.length+' is still empty; pick its image or close this picker.';announce('Saved source attached. No generation submitted.');}}catch(err){if(current())q('#uxPickerStatus').textContent=err.message;}finally{if(pickerBusyOwner===busyOwner){pickerBusyOwner=null;pickerBusy=false;button.disabled=false;syncReady();}}};
  picker.addEventListener('cancel',e=>{if(pickerBusy)e.preventDefault();});picker.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();if(!pickerBusy)picker.close();}});
  // Drafts are data only, scoped to the server's workspace identity. No File bytes.
  function snapshot(){if(!selected)return null;return U.normalizeDraft({version:1,updatedAt:Date.now(),recipe:{preset:selected.id,...(draftPrivacy==='private'?{privacy:'private'}:{}),...continuationPayload(),...tilePayload(),...parallaxPayload(),...(typeof StudioLooks!=='undefined'?StudioLooks.applicationPayload(selected.id):{}),controls:values(),batch:q('#batch').value,parent_assets:parentAssets,parent_by_input:{...parentByInput},references:attachedReferencePayload()},pendingInputs:['reference','lastReference'].filter(id=>pendingInputs.has(id)||(q('#'+id).files.length&&(id==='reference'?!uploaded:!lastUploaded))),templateHash:recipeTemplateHash});}
  // This remains the sole owner of Create mutation; commands persist before adoption.
  function setupStamp(){return JSON.stringify([workbenchStamp(),referenceEpoch,referencePending,selectionEpoch,recipeTemplateHash,parentByInput,typeof backendActive==='undefined'?null:backendActive]);}
  function setupBusy(){return !!referencePending||!!pickerBusy||!!restoring||!!submitting||!!handoffBusy||typeof backendSwitching!=='undefined'&&!!backendSwitching;}
  function adoptSharedSetup(value,expectedStamp,backendId){
    if(setupBusy()||expectedStamp!==setupStamp())throw Error('Create changed before loading the shared revision. Current inputs were preserved.');
    const draft=U.normalizeDraft(JSON.parse(JSON.stringify(value))),target=catalog?.presets.find(p=>p.id===draft?.recipe.preset);
    if(!draft||draft.pendingInputs.length||!target)throw Error('The shared revision cannot be represented by this editor. Export and inspect it first.');
    if(draft.recipe.tile&&!target.tile_route||draft.recipe.parallax&&!target.parallax_route)throw Error('The prepared plan does not belong to this recipe. No settings were changed.');
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
      tileState=draft.recipe.tile||null;parallaxState=draft.recipe.parallax||null;
      if(typeof StudioLooks!=='undefined')StudioLooks.restoreApplication(draft.recipe.look_application,target.id,draft.recipe.look);
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
  function draftKey(classification=draftPrivacy){return draftPrefix&&selected?draftStorageKey(draftPrefix+selected.id,classification):null;}
  function readDraft(key=draftKey()){if(!key)return null;try{const raw=draftStorage().getItem(key),value=U.normalizeDraft(JSON.parse(raw));if(value)knownDrafts.set(key,raw);return value;}catch(_){return null;}}
  function saveDraft(){if(restoring||draftPaused||!draftDirty||!draftPrefix||!selected)return;const key=draftKey(),draft=snapshot();if(!draft)return;try{const existing=draftStorage().getItem(key),current=U.normalizeDraft(JSON.parse(existing));if(current&&knownDrafts.has(key)&&knownDrafts.get(key)!==existing){draftPaused=true;renderDraftNotice();return;}if(current&&JSON.stringify({...current,updatedAt:0})===JSON.stringify({...draft,updatedAt:0}))return;const raw=JSON.stringify(draft);draftStorage().setItem(key,raw);knownDrafts.set(key,raw);q('#uxDraftStatus').textContent=(draftPrivacy==='private'?'Private draft saved for this tab · ':'Draft saved in this browser · ')+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}catch(_){q('#uxDraftStatus').textContent='Browser storage is unavailable. Export this draft or save a named setup.';}}
  function renderDraftNotice(){const draft=readDraft();q('#uxRestoreDraft').hidden=!draft;q('#uxDiscardDraft').hidden=!draft;q('#uxKeepDraft').hidden=!draftPaused;q('#uxDraftStatus').textContent=draftPaused?'Another tab changed the saved draft. Autosave is paused; export yours or keep this tab.':draft?'Saved draft from '+new Date(draft.updatedAt).toLocaleString()+'. Restore it to continue.':(draftPrivacy==='private'?'Private drafts stay in this tab. Export a draft to keep a separate copy.':'Your unsaved draft is kept in this browser. Save a setup to keep it in your workspace.');}
  async function restoreDraft(draft,{persist=false}={}){
  if(!draft)return;if(!catalog?.presets.some(p=>p.id===draft.recipe.preset)){announce('This draft needs a recipe that is not in the current catalog.',true);return;}
  restoring=true;let epoch=null,checkedInputs=[],completed=false;
  try{applySaved(draft.recipe);epoch=selectionEpoch;recipeTemplateHash=draft.templateHash;pendingInputs=new Set(draft.pendingInputs);syncReady();
    checkedInputs=[...(!selected.reference_slots?.length&&selected.reference&&uploaded?[['reference',uploaded]]:[]),...(selected.last_reference&&lastUploaded?[['lastReference',lastUploaded]]:[])];
    if(checkedInputs.length){const files=[...new Set(checkedInputs.map(([,file])=>file))],checks=await post('/api/references/check',{files});if(epoch!==selectionEpoch)return;for(const [name,file]of checkedInputs)if(!checks.some(c=>c.file===file&&c.available)){pendingInputs.add(name);if(name==='reference')uploaded=null;else lastUploaded=null;releaseInputParent(name);}}
    if(typeof tileState!=='undefined'&&tileState&&((uploaded&&uploaded!==tileState.rolled_file)||!parentAssets.includes(tileState.source_asset_id)))tileState=null;
    syncCreate();announce(draft.tileDropped||draft.recipe.tile&&typeof tileState!=='undefined'&&!tileState?'Seamless plan dropped because it no longer matches this draft. Use Make seamless again.':'Draft restored. Reattach any missing local files, then review before running.');completed=true;
  }catch(err){if(epoch===selectionEpoch){for(const [name,file]of checkedInputs){if(!file)continue;pendingInputs.add(name);if(name==='reference')uploaded=null;else lastUploaded=null;}announce('Input availability could not be checked: '+err.message,true);}}
  finally{restoring=false;if(epoch===selectionEpoch){draftDirty=!!persist&&completed;if(draftDirty)saveDraft();}syncReady();}
}
  q('#uxRestoreDraft').onclick=()=>restoreDraft(readDraft());
  q('#uxImportDraftButton').onclick=()=>q('#uxImportDraft').click();
  q('#uxImportDraft').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>131072)throw Error('Draft files must be under 128 KiB.');const draft=U.normalizeDraft(JSON.parse(await file.text()));if(!draft)throw Error('This is not a supported Studio draft.');saveDraft();await restoreDraft(draft,{persist:true});}catch(err){announce(err.message,true);}finally{e.target.value='';}};
  q('#uxDiscardDraft').onclick=()=>{try{const key=draftKey();if(key)draftStorage().removeItem(key);knownDrafts.delete(key);draftDirty=false;renderDraftNotice();}catch(_){announce('Browser storage is unavailable.',true);}};
  q('#uxKeepDraft').onclick=()=>{draftPaused=false;readDraft();saveDraft();renderDraftNotice();};
  q('#uxExportDraft').onclick=()=>{const draft=snapshot();if(!draft)return;const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(draft,null,2)],{type:'application/json'}));a.href=url;a.download='studio-draft-'+draft.recipe.preset+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  window.addEventListener('storage',e=>{if(draftPrivacy==='regular'&&e.key===draftKey()){draftPaused=true;renderDraftNotice();}});
  window.addEventListener('pagehide',saveDraft);
  for(const event of ['input','change'])q('#createView').addEventListener(event,e=>{if(e.target.closest('.editor'))draftDirty=true;syncReady();clearTimeout(draftTimer);draftTimer=setTimeout(saveDraft,350);});
  q('#createView').addEventListener('click',e=>{if(e.target.closest('[data-variant],#randomSeed,[data-ref-clear],[data-ref-up],[data-ref-down]')){pictureKept=null;renderUndo();draftDirty=true;syncReady();saveDraft();}});
  const originalLoadSetups=loadSetups;loadSetups=async function(){try{localStorage.getItem('studio-storage-probe');}catch(_){serverSetups=await api('/api/setups');renderSaved();return;}return originalLoadSetups();};
  // Explicitly apply a reviewed Prompt Lab text handoff; never infer model bindings.
  const transfer=element('section','panel ux-transfer');transfer.id='uxTransfer';transfer.hidden=true;transfer.innerHTML='<h2>Text from Prompt Lab</h2><p id="uxTransferNotice"></p><div id="uxTransferRecipes" class="ux-transfer-recipes" role="group" aria-label="Matching recipes" hidden></div><pre id="uxTransferPreview"></pre><button id="uxApplyPrompt" class="primary">Apply text to the selected recipe</button><button id="uxDismissPrompt">Dismiss</button>';createHeading.after(transfer);
  let promptHandoff=null;
  // Matching recipes are chips that only switch the selected recipe (no submit; the held wording is untouched); the button names the recipe it will fill.
  // A keyboard switch rebuilds the row; focus returns to the chosen chip so its pressed state is heard (#1743 review).
  const renderTransferChoices=()=>{const apply=q('#uxApplyPrompt'),group=q('#uxTransferRecipes'),focused=!!globalThis.document?.activeElement?.closest?.('#uxTransferRecipes');apply.textContent=selected?.name?'Apply to '+selected.name:'Apply text to the selected recipe';apply.disabled=!selected?.positive;apply.title=apply.disabled?'Choose a recipe with a text prompt first.':'';const known=(promptHandoff?.recipes||[]).map(id=>catalog?.presets.find(p=>p.id===id)).filter(Boolean);group.hidden=!known.length;const chips=known.map(p=>{const chip=element('button','');chip.type='button';chip.textContent=p.name||p.id;chip.setAttribute('aria-pressed',String(p.id===selected?.id));chip.onclick=()=>{if(p.id===selected?.id)return;try{selectPreset(p.id);}catch(e){announce(e.message,true);}};return chip;});group.replaceChildren(...chips);if(focused)chips[known.findIndex(p=>p.id===selected?.id)]?.focus?.();};
  after('selectPreset',renderTransferChoices);
  q('#uxApplyPrompt').onclick=()=>{if(!promptHandoff||!selected?.positive){announce('Choose a recipe with a text prompt first.',true);return;}saveDraft();q('#positive').value=promptHandoff.positive;if(selected.negative)q('#negative').value=promptHandoff.negative;transfer.hidden=true;draftDirty=true;saveDraft();syncReady();announce('Compiled text applied. '+(!selected.negative&&promptHandoff.negative?'This recipe has no negative-prompt field; the negative text was not applied. ':'')+'References and sampling settings were not transferred. Review before generating.');};q('#uxDismissPrompt').onclick=()=>{transfer.hidden=true;};
  async function initializeDrafts(){try{const identity=await api('/api/identity');draftPrefix='studio-draft-v1:'+identity.workspace+':';renderDraftNotice();try{const raw=sessionStorage.getItem('studio-prompt-handoff');if(raw){sessionStorage.removeItem('studio-prompt-handoff');const handoff=JSON.parse(raw);if(handoff.workspace===identity.workspace&&Date.now()-handoff.createdAt<3600000&&handoff.createdAt<=Date.now()&&typeof handoff.transfer?.positive==='string'&&handoff.transfer.positive.length<=8000){promptHandoff=U.promptTransfer({fields:handoff.transfer,profile:{id:handoff.transfer.profile},recipes:handoff.transfer.recipes});if(!promptHandoff)return;const renderNames=()=>{q('#uxTransferNotice').textContent=promptHandoff.notice;renderTransferChoices();};renderNames();/* The catalog usually lands after this notice; re-render with names once it does, bounded. */if(!catalog&&typeof setTimeout==='function'){let tries=0;const wait=()=>{if(catalog)renderNames();else if(++tries<60)setTimeout(wait,250);};setTimeout(wait,250);}q('#uxTransferPreview').textContent=promptHandoff.positive+(promptHandoff.negative?'\n\nNegative (applied only when supported):\n'+promptHandoff.negative:'');transfer.hidden=false;showView('create');}}}catch(_){/* Exported briefs remain usable when session storage is disabled. */}}catch(_){q('#uxDraftStatus').textContent='Workspace identity unavailable. Draft storage is disabled until reload.';}}
  const jobInspector=element('dialog','studio-dialog');jobInspector.id='uxJobInspector';jobInspector.setAttribute('aria-labelledby','uxJobInspectorTitle');document.body.append(jobInspector);
  function inspectJob(id){
    const job=homeData?.jobs?.find(item=>item.id===id);
    if(!job){announce('This job is no longer in the Overview snapshot. Refresh the overview to inspect its current record.',true);return;}
    const failure=U.failureDetails(job);
    jobInspector.innerHTML='<div class="dialog-heading"><h2 id="uxJobInspectorTitle">'+escape(job.preset_name||job.id)+'</h2><button type="button" data-ux-close="uxJobInspector">Close</button></div><p><b>'+escape(job.status)+'</b> · Saved record</p><p>Job ID: <code>'+escape(job.id)+'</code></p><p>'+escape(job.message||'No message recorded.')+'</p>'+(failure?'<p>'+escape(failure.summary)+'</p><p><b>Next:</b> '+escape(failure.action)+'</p><details><summary>Engine detail</summary><pre>'+escape(failure.detail)+'</pre></details>':'')+'<p>Known prompt IDs: '+escape((job.prompt_ids||[]).join(', ')||'None recorded')+'</p><details><summary>Recorded recipe and controls</summary><pre>'+escape(JSON.stringify(job.recipe||{preset:job.preset_id,controls:job.controls||{}},null,2))+'</pre></details>'+deskJobAction(job)+'<small>Overview snapshot '+escape(homeUpdated?.toLocaleString()||'time unavailable')+'. Inspecting does not retry, cancel or change your current setup.</small>';
    if(!jobInspector.open)jobInspector.showModal();
  }
  // #940: the desk can put a finished-with problem away. Only put_away_at changes (server-side
  // put_away_job); nothing is retried, cancelled or deleted, and Create → Problems brings it back.
  function deskJobAction(job){
    if(job.put_away&&job.can_bring_back)return '<p class="ux-desk-action"><button type="button" data-ux-put-away="false" data-job="'+escape(job.id)+'">Bring back</button> <small>Put away. Bring it back to your desk and Problems.</small></p>';
    if(job.can_put_away)return '<p class="ux-desk-action"><button type="button" data-ux-put-away="true" data-job="'+escape(job.id)+'">Put away</button> <small>Takes it off your desk and Problems. Nothing is retried, cancelled or deleted.</small></p>';
    if(job.status==='uncertain')return '<p class="ux-desk-action"><small>'+(job.can_stop_tracking?'To put this away, stop tracking it first in <a href="/#create">Create → Problems</a>; until then it can still be resumed.':'Resolve or abandon it in <a href="/#create">Create → Problems</a> before putting it away.')+'</small></p>';
    return '';
  }
  let deskBusy=false;
  async function putAwayFromDesk(button){
    if(deskBusy)return;deskBusy=true;button.disabled=true;const away=button.dataset.uxPutAway==='true';
    try{await post('/api/jobs/'+encodeURIComponent(button.dataset.job)+'/put-away',{put_away:away});if(jobInspector.open)jobInspector.close();announce(away?'Put away. Create → Problems → Show put away brings it back.':'Back on your desk and in Problems.');homeSignature='';await refreshHome();if(typeof refresh==='function')refresh();}
    finally{deskBusy=false;button.disabled=false;}
  }
  async function refreshHome(){if(homeBusy)return;homeBusy=true;q('#uxRefreshHome').disabled=true;try{const epoch=homeEpoch,result=await Promise.allSettled(['/api/workspace','/api/production','/api/jobs'].map(path=>api(path)));if(epoch!==homeEpoch)return;homeErrors=result.map((r,i)=>r.status==='rejected'?['Asset library','Runs','Jobs'][i]+': '+r.reason.message:null).filter(Boolean);homeData={workspace:result[0].status==='fulfilled'?result[0].value:null,plans:result[1].status==='fulfilled'?result[1].value:null,jobs:result[2].status==='fulfilled'?result[2].value:null};homeUpdated=new Date();renderHome();}finally{homeBusy=false;q('#uxRefreshHome').disabled=false;}}
  function renderHome(){if(!homeData)return;const {workspace,plans,jobs:runJobs}=homeData,all=workspace?.assets||[],assets=all.filter(a=>typeof assetIsAgentRun!=='function'||!assetIsAgentRun(a)),hidden=all.filter(a=>!a.trashed_at).length-assets.filter(a=>!a.trashed_at).length,s=U.summarize(assets,plans||[],runJobs||[]);q('#uxHomeHealth').textContent=homeErrors.length?'Some data is unavailable. '+homeErrors.join(' · '):'Saved records refreshed '+homeUpdated.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+(hidden?' · counts are your pictures; '+hidden+' agent run'+(hidden===1?' is':'s are')+' not counted':'')+' · execution, creative review and licensing remain separate.';q('#uxHomeHealth').classList.toggle('error',!!homeErrors.length);const signature=JSON.stringify(homeData);if(signature===homeSignature)return;homeSignature=signature;
    q('#uxStats').innerHTML=[['Saved assets',workspace?s.assets:'—','all'],['Awaiting review',workspace?s.unreviewed:'—','unreviewed'],['Kept',workspace?s.keepers:'—','selected'],['Needs another pass',workspace?s.needsWork:'—','needs_work']].map(([label,value,scope])=>'<button data-ux-scope="'+scope+'"><span>'+label+'</span><b>'+value+'</b><small>Open library →</small></button>').join('');
    // #940: a plan untouched for 7 days leaves the desk (Runs & review keeps it under Older). Live plans always stay;
    // a plan with no readable date cannot be shown to be old, so it stays too. planActivity is production.js's.
    const now=Date.now()/1000,stale=p=>!U.ACTIVE.includes(p.state?.status)&&typeof planActivity==='function'&&(at=>at!==null&&now-at>7*86400)(planActivity(p));
    // An owner put-away plan (#940) leaves the desk too; Runs & review → Status: All keeps it one click away.
    const allDeskPlans=[...s.reviewPlans,...s.attentionPlans,...s.activePlans,...s.prepared],putAwayPlans=(plans||[]).filter(p=>p.put_away===true).length;
    const deskPlans=allDeskPlans.filter(p=>p.put_away!==true),olderPlans=deskPlans.filter(stale).length;
    const ordered=deskPlans.filter(p=>!stale(p)).slice(0,6),seenJobs=new Set((plans||[]).flatMap(p=>(p.stages||[]).map(stage=>stage.job?.id).filter(Boolean)));
    const records=ordered.map(p=>'<a class="ux-desk-row" href="'+(p.state.status==='awaiting_review'&&p.kind==='comparison'?'/review.html?project='+encodeURIComponent(p.id):p.kind==='av'?'/av.html?project='+encodeURIComponent(p.id):p.kind==='voice'?'/voice.html':'/#production')+'" data-ux-project="'+escape(p.id)+'"><span class="ux-state-dot '+escape(p.state.status)+'" aria-hidden="true"></span><span><b>'+escape(p.name)+'</b><small>'+escape(p.state.status.replaceAll('_',' '))+' · '+escape(p.kind)+'</small></span><span aria-hidden="true">↗</span></a>');
    for(const j of [...s.attentionJobs,...s.activeJobs].filter(j=>!seenJobs.has(j.id)).slice(0,3))records.push('<button type="button" class="ux-desk-row" data-ux-inspect-job="'+escape(j.id)+'"><span class="ux-state-dot '+escape(j.status)+'" aria-hidden="true"></span><span><b>'+escape(j.preset_name)+'</b><small>'+escape(deskJobHint(j))+'</small></span><span aria-hidden="true">↗</span></button>');
    q('#uxAttention').innerHTML=(records.join('')||(plans&&runJobs?'<div class="ux-empty"><b>A clear desk.</b><p>Prepare a comparison to test one change, or start with a recipe above.</p><a href="/#create">Prepare your first pass →</a></div>':'<p>Run status is unavailable. Refresh before deciding what to start.</p>'))+(olderPlans?'<p class="ux-desk-note"><small>'+olderPlans+' plan(s) untouched for 7 days. <a href="/#production">See them under Older in Compare &amp; review</a></small></p>':'')+(s.putAwayJobs.length?'<p class="ux-desk-note"><small>'+s.putAwayJobs.length+' run(s) put away or with tracking stopped. <a href="/#create">Show put away in Create → Problems</a></small></p>':'')+(putAwayPlans?'<p class="ux-desk-note"><small>'+putAwayPlans+' plan(s) put away. <a href="/#production">Set Status to All statuses in Compare &amp; review to see them</a></small></p>':'');
    const recent=assets.filter(a=>!a.trashed_at).sort((a,b)=>b.created_at-a.created_at).slice(0,6);q('#uxRecent').innerHTML=recent.map(a=>'<button class="ux-recent-card" data-ux-open-asset="'+escape(a.id)+'">'+assetPreview(a)+'<span><b>'+escape(a.title)+'</b><small>'+escape(a.media_type)+' · '+escape(({selected:'Kept',needs_work:'Needs work',rejected:'Not this',unreviewed:'Unreviewed'}[a.review||'unreviewed']||a.review))+'</small></span></button>').join('')||'<div class="ux-empty panel"><h3>'+(workspace?'Make room for your first asset.':'Asset library is unavailable.')+'</h3><p>Import an existing image or create from a recipe. Sources stay available for the next step.</p><a href="/#assets">Open Asset library →</a></div>';
  }
  function deskJobHint(j){return j.status==='uncertain'?'outcome unknown · inspect; do not run it again':U.ACTIVE.includes(j.status)?j.status+' · in progress':j.status+' · see why, then put it away';}
  q('#uxRefreshHome').onclick=()=>refreshHome();
  document.addEventListener('click',async e=>{try{const inspect=e.target.closest('[data-ux-inspect-job]');if(inspect){inspectJob(inspect.dataset.uxInspectJob);return;}const putAway=e.target.closest('[data-ux-put-away]');if(putAway){await putAwayFromDesk(putAway);return;}const close=e.target.closest('[data-ux-close]');if(close){if((close.dataset.uxClose==='uxHandoff'&&handoffBusy)||(close.dataset.uxClose==='uxSourcePicker'&&pickerBusy))return;q('#'+close.dataset.uxClose).close();}const intent=e.target.closest('[data-ux-intent]');if(intent)chooseIntent(intent.dataset.uxIntent);const dest=e.target.closest('[data-ux-destination]');if(dest&&!handoffBusy){const next=dest.dataset.uxDestination;if(pendingStyle&&next!==handoffIntent){pendingStyle=null;announce('The extra picture was not attached because you changed the handoff task. Choose it again if the new task needs it.');}handoffIntent=next;handoffRecipes();}const hand=e.target.closest('[data-ux-handoff]');if(hand){const id=hand.dataset.uxHandoff;if(!assetState.assets.some(a=>a.id===id))await refreshAssets();openHandoff(id,undefined,undefined,hand.dataset.uxHandoffIntent);}const scope=e.target.closest('[data-ux-scope]');if(scope){assetScope=scope.dataset.uxScope;if(typeof chooseAssetSource==='function')chooseAssetSource('mine');q('#assetSearch').value='';q('#assetType').value='all';assetSelection.clear();showView('assets');renderAssets();}const open=e.target.closest('[data-ux-open-asset]');if(open){await refreshAssets();openAsset(open.dataset.uxOpenAsset);}const project=e.target.closest('[data-ux-project]');if(project){productionId=project.dataset.uxProject;if(view==='production')renderProduction();}}catch(err){announce(err.message,true);}});
  // Native file input remains the accessible fallback for drag-and-drop imports.
  const drop=element('div','ux-import-drop','<b>Bring existing work into the studio</b><span>Drop up to 32 PNG, JPG or WebP images here, or use Import images.</span>');drop.id='uxImportDrop';q('#assetsView .asset-workspace').before(drop);drop.ondragover=e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();drop.classList.add('dragover');}};drop.ondragleave=()=>drop.classList.remove('dragover');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('dragover');const files=[...e.dataTransfer.files];if(files.length>32||files.some(f=>!['image/png','image/jpeg','image/webp'].includes(f.type))){assetMessage('Import up to 32 PNG, JPEG or WebP images. No files were submitted.',true);return;}const transfer=new DataTransfer();files.forEach(f=>transfer.items.add(f));q('#importAssets').files=transfer.files;q('#importAssets').dispatchEvent(new Event('change',{bubbles:true}));};
  q('#importAssetsButton').onclick=()=>q('#importAssets').click();
  let overviewPollingAttached=false;
  function attachOverviewPolling(){
    if(overviewPollingAttached||!window.StudioReadPoller)return;
    const readHome=refreshHome;overviewPollingAttached=true;
    window.StudioReadPoller.register('overview',{interval:12000,shouldPoll:()=>view==='home',task:readHome});
    refreshHome=(...args)=>window.StudioReadPoller.refresh('overview',...args);
  }
  window.addEventListener('studio-read-poller-ready',attachOverviewPolling);attachOverviewPolling();
  // Invalidate old readers before clearing their DOM. Changing only the view never moves the creation draft.
  document.addEventListener('studio:privacy-change',event=>{
    const change=event.detail,scopeChanged=change.previousScope!==change.scope,creationChanged=change.previousCreation!==change.creation;
    if(scopeChanged||creationChanged){
      sourceSeq++;sourcePickerEpoch++;handoffEpoch++;pickerBusy=pickerLoading=handoffBusy=false;pickerBusyOwner=handoffBusyOwner=null;
      secondPanel.setAttribute('aria-busy','false');for(const button of secondPanel.querySelectorAll('[data-ux-second-slot]'))button.disabled=false;
      sourcePage={assets:[],unavailable:[],next:null};sourceContext=null;handoffId=null;handoffBaseline=null;
      for(const dialog of [picker,handoff])if(dialog.open)dialog.close();
      for(const id of ['uxSourceAssets','uxSourcePaging','uxPickerStatus','uxHandoffSource','uxHandoffDetails','uxHandoffPrompt','uxHandoffTechnical','uxHandoffStatus'])q('#'+id)?.replaceChildren();
      q('#uxSourceSearch').value='';syncReady();
    }
    if(scopeChanged){
      homeEpoch++;homeData=null;homeSignature='';tileRead++;parallaxRead++;
      if(jobInspector.open)jobInspector.close();
      for(const id of ['uxStats','uxDesk','uxRecent'])q('#'+id)?.replaceChildren();
      jobInspector.replaceChildren();q('#uxHomeHealth').textContent='Refresh to read this privacy view.';
      if(view==='home')void refreshHome();
    }
    if(change.previousCreation===change.creation)return;
    clearTimeout(draftTimer);draftTimer=null;selectionEpoch++;referenceEpoch++;
    const before=snapshot(),oldKey=draftKey(),oldFillKey=fillsKey(),ownedDraft=knownDrafts.get(oldKey),ownedFills=knownFills.get(oldFillKey),wasPaused=draftPaused;
    const fills={...JSON.parse(ownedFills||'{}'),...fillValues()};
    if(change.previousCreation==='private'&&before&&oldKey)try{draftStorage().setItem(oldKey,JSON.stringify(before));}catch(_){announce('This draft could not be saved in the browser. Export it to retain a copy.',true);}
    draftPrivacy=change.creation;draftPaused=false;knownDrafts.clear();draftDirty=false;
    if(change.previousCreation==='regular'&&change.creation==='private'){
      // Only this unsent draft moves. Unrelated saved setups and other recipes keep their own scope.
      const moved=snapshot(),key=draftKey();
      try{let retained=false;if(moved&&key){const raw=JSON.stringify(moved);sessionStorage.setItem(key,raw);knownDrafts.set(key,raw);if(oldKey){const existing=localStorage.getItem(oldKey);if(existing!==null){if(!wasPaused&&existing===ownedDraft)localStorage.removeItem(oldKey);else retained=true;}}}if(oldFillKey){const raw=JSON.stringify(fills);sessionStorage.setItem(fillsKey(),raw);knownFills.set(fillsKey(),raw);const existing=localStorage.getItem(oldFillKey);if(existing!==null){if(existing===ownedFills)localStorage.removeItem(oldFillKey);else retained=true;}}if(retained)announce('This creation is private. A regular browser draft changed in another tab, so that saved copy was kept.');}
      catch(_){announce('Private browser storage is unavailable. Export this draft before leaving; a previous regular browser copy may remain.',true);}
      draftDirty=true;renderDraftNotice();syncCreate();return;
    }
    // Leaving private creation restores a separate regular draft, never the private prompt, references or undo buffers.
    const next=readDraft();restoring=true;
    try{
      forgetWording();wordingBase=null;combineWording.clear();for(const key of Object.keys(planFills))delete planFills[key];planPrepared=null;planPair=null;planSeeded=false;
      fillsPreset=fillsSource=transferredFills=null;fillsTemplate='';fillsAssembled=null;
      sourceReadError='';varyUnapplied=null;secondPicture=pendingStyle=null;secondPanel.hidden=true;
      posePoints=poseHome=poseHeld=poseLoading=null;poseOpenFor=null;poseHeldShown='';poseTimeline=StudioPoseEditor.timeline(POSE_UNDO);
      if(selected)selectPreset(selected.id,true,true,true);
      q('#saveName').value='';pendingInputs.clear();forgetWording();
    }finally{restoring=false;}
    if(next)void restoreDraft(next);else{syncCreate();renderDraftNotice();}
  });
  showView(location.hash);initializeDrafts();
})();
