/* Looks (#1221): pick a saved look in Create, type only the scene, and the Studio writes the wording and the look's recipe
   settings. A look is Workspace data (/api/looks, app/looks.py), not browser storage. Preparing never generates (K8). */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioLooks=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const SLOT='{scene}',PICTURE_KEYS=['reference','last_reference','reference_slots'],NOT_CONTROLS=['positive','negative','reference','last_reference','mode'];
  const slotCount=text=>String(text||'').split(SLOT).length-1;
  // Mirrors app/looks.py recipe_problem: a look is words on one text-to-image recipe.
  function recipeProblem(preset){
    if(!preset)return 'Choose a recipe first.';
    if((preset.modality||'image')!=='image')return 'A look needs an image recipe.';
    if(!preset.positive)return 'This recipe takes no wording.';
    if(PICTURE_KEYS.some(k=>Array.isArray(preset[k])?preset[k].length:preset[k]))return 'Looks use text-to-image recipes; this one takes a picture.';
    return '';
  }
  function groups(looks){const all=Array.isArray(looks)?looks:[];return{active:all.filter(l=>!l.trashed_at),away:all.filter(l=>l.trashed_at)};}
  function optionLabel(look,presetId){return look.name+(!look.usable&&!look.trashed_at?' · unavailable':look.body?.preset_id!==presetId&&look.preset_name?' · on '+look.preset_name:'');}
  function prepareBlocker({look,scene,busy}){
    if(busy)return 'Wait for the current look action to finish.';
    if(!look)return 'Choose a look.';
    if(!look.usable)return look.unusable_reason||'This look cannot be used.';
    if(!String(scene||'').trim())return 'Type the scene in a few words.';
    return '';
  }
  function saveBlocker({preset,positive,name,busy}){
    if(busy)return 'Wait for the current look action to finish.';
    const problem=recipeProblem(preset);if(problem)return problem;
    const slots=slotCount(positive);
    if(slots!==1)return slots?'Write '+SLOT+' only once in the wording.':'Write '+SLOT+' in the wording above where a new scene goes.';
    if(!String(name||'').trim())return 'Name the look.';
    return '';
  }
  // The look records the recipe's settings as they stand; wording and pictures are not settings.
  function saveControls(values){return Object.fromEntries(Object.entries(values||{}).filter(([k,v])=>!NOT_CONTROLS.includes(k)&&v!==''&&v!=null).map(([k,v])=>[k,typeof v==='string'&&v.trim()!==''&&Number.isFinite(Number(v))?Number(v):v]));}
  function summary(look){
    if(!look)return '';
    const anchor=(look.lineage||[]).find(e=>e.role==='anchor');
    return [look.preset_name||look.body?.preset_id,anchor?'anchor '+(anchor.key||String(anchor.sha256||'').slice(0,12))+(look.anchor_asset_id?' (in your Workspace)':' (not in this Workspace)'):'no anchor picture',look.origin==='seed'?(look.revision>0?'edited shipped look':'shipped look'):'your look'].filter(Boolean).join(' · ');
  }
  // Optional lines (owner, 27 Sep 2026): layout sentences a look offers but does not force, e.g. Night Shift's quiet wall for UI
  // backgrounds. One checkbox per line, set to the line's default; every line's choice is sent so the server never guesses.
  const lines=look=>Array.isArray(look?.body?.options)?look.body.options:[];
  function optionRows(look){return lines(look).map(o=>({id:o.id,label:o.label,checked:!!o.default}));}
  function optionsPayload(look,checked){const all=lines(look);return all.length?Object.fromEntries(all.map(o=>[o.id,typeof checked?.[o.id]==='boolean'?checked[o.id]:!!o.default])):null;}
  function readyMessage(result,switched,look){
    const c=result.controls||{},size=c.width&&c.height?', '+c.width+'x'+c.height:'',seed=c.seed!=null?', seed '+c.seed:'';
    const on=lines(look).filter(o=>result.look?.options?.[o.id]).map(o=>o.label),withLines=on.length?', with: '+on.join('; '):'';
    return result.look.name+' prepared on '+(result.preset_name||result.preset_id)+(switched?' (recipe switched)':'')+seed+size+withLines+'. Your scene is in the wording. Nothing was generated; press Generate when it reads right.';
  }
  // Probe detached controls first: an unsupported select value becomes empty, and numeric
  // controls can reject a value. Never publish only the settings that happened to stick.
  function applyControls(controls,resolve){
    const writes=[],problems=[];
    for(const [key,value] of Object.entries(controls||{})){
      const input=resolve(key);
      if(!input){problems.push(key);continue;}
      const probe=input.cloneNode(true);probe.value=value;
      const same=probe.type==='number' ? probe.value!==''&&Number.isFinite(Number(value))&&Number(probe.value)===Number(value) : String(probe.value)===String(value);
      if(!same||!probe.checkValidity()){problems.push(key);continue;}
      writes.push([input,value]);
    }
    if(!problems.length)for(const [input,value] of writes)input.value=value;
    return problems;
  }
  let application=null,preparation=null;
  // Admission is global while preparing, even if the owner changes the selected recipe.
  // Tokens prevent an obsolete completion from releasing a newer request's hold.
  function beginPreparation(){return preparation={};}
  function finishPreparation(token){if(preparation!==token)return false;preparation=null;return true;}
  function normalizeApplication(value,presetId){
    if(!value||value.version!==1||value.preset_id!==presetId||!Array.isArray(value.controls)||!value.controls.length||value.controls.length>32||value.controls.some(k=>typeof k!=='string'||!/^[a-z][a-z0-9_]{0,63}$/.test(k)))return null;
    return {version:1,preset_id:presetId,controls:[...new Set(value.controls)]};
  }
  function clearApplication(){application=null;}
  function restoreApplication(value,presetId){
    application=value==null?null:normalizeApplication(value,presetId);
    if(value!=null&&!application)throw Error('Invalid saved Look application state.');
  }
  function applicationPayload(presetId){return application?.preset_id===presetId?{look_application:normalizeApplication(application,presetId)}:{};}
  function applicationBlocker(presetId){if(preparation)return 'A Look is being prepared. Wait for it to finish before generating or saving a setup.';return application?.preset_id===presetId?'This Look could not be applied: '+application.controls.join(', ')+'. Recipe defaults are shown; no Look settings were applied. Reprepare with supported settings or reset the recipe without the look. Nothing was generated.':'';}
  return{SLOT,slotCount,recipeProblem,groups,optionLabel,prepareBlocker,saveBlocker,saveControls,summary,optionRows,optionsPayload,readyMessage,applyControls,normalizeApplication,clearApplication,restoreApplication,applicationPayload,applicationBlocker,beginPreparation,finishPreparation};
});

(function(){
  'use strict';
  if(typeof document==='undefined'||!document.querySelector('#createView')||typeof module==='object')return;
  const L=StudioLooks,q=s=>document.querySelector(s);
  let looks=[],busy=false,composed=null,preparationEpoch=0;
  // Events catch edit-then-undo; the stamp also catches changes made without input events.
  for(const type of ['input','change'])document.addEventListener(type,event=>{
    if(event.target?.closest?.('#createView'))preparationEpoch++;
  },true);
  document.addEventListener('studio:recipe',()=>{preparationEpoch++;});
  // Folded by default: Create's first screen keeps the wording and Generate in view (workshop height budget).
  const block=document.createElement('details');block.id='lookBlock';block.className='ux-looks';
  block.innerHTML='<summary>Use a saved look <small>type only the scene</small></summary><div class="ux-looks-row"><label>Look<select id="lookSelect"></select></label><label>Scene<input id="lookScene" maxlength="1000" autocomplete="off" aria-describedby="lookReason"></label></div><div id="lookOptions" class="ux-looks-row" role="group" aria-label="Optional lines of this look" hidden></div>'
    +'<p id="lookSummary" class="muted"></p><div class="ux-looks-row"><button type="button" id="lookPrepare" aria-describedby="lookReason">Prepare with this look</button><button type="button" id="lookTrash" aria-describedby="lookReason">Put away</button></div><p class="disabledReason"><small id="lookReason"></small></p>'
    +'<details id="lookSave"><summary>Save this wording as a look</summary><p class="muted">Write '+L.SLOT+' in the wording where a new scene goes. The recipe and its settings are saved with it.</p><label>Look name<input id="lookName" maxlength="120" autocomplete="off" aria-describedby="lookSaveReason"></label><p id="lookAnchor" class="muted"></p><button type="button" id="lookSaveButton" aria-describedby="lookSaveReason">Save look</button><p class="disabledReason"><small id="lookSaveReason"></small></p></details>'
    +'<p id="lookStatus" role="status" aria-live="polite"></p><button type="button" id="lookReset" hidden>Reset recipe without the look</button>';
  (q('#uxFills')||q('#positiveWrap')).before(block);
  const current=()=>looks.find(l=>l.id===q('#lookSelect').value)||null;
  const status=(text,error=false)=>{q('#lookStatus').textContent=text;q('#lookStatus').classList.toggle('error',error);};
  const anchorAsset=()=>typeof parentAssets!=='undefined'&&parentAssets.length===1?parentAssets[0]:null;
  // Rebuilt only when the chosen look changes, so a ticked line survives typing the scene.
  let linesFor=null;
  function renderLines(){
    const look=current(),key=look?look.id+':'+look.revision:null;if(key===linesFor)return;linesFor=key;
    const rows=L.optionRows(look),box=q('#lookOptions');box.hidden=!rows.length;
    box.innerHTML=rows.map(r=>'<label><input type="checkbox" data-look-option="'+esc(r.id)+'"'+(r.checked?' checked':'')+'> '+esc(r.label)+'</label>').join('');
  }
  const checkedLines=()=>Object.fromEntries([...document.querySelectorAll('#lookOptions [data-look-option]')].map(i=>[i.dataset.lookOption,i.checked]));
  function sync(){
    renderLines();
    q('#lookReset').hidden=!L.applicationBlocker(typeof selected!=='undefined'?selected?.id:null);q('#lookReset').disabled=busy;
    const look=current(),reason=L.prepareBlocker({look,scene:q('#lookScene').value,busy});
    q('#lookPrepare').disabled=!!reason;q('#lookReason').textContent=reason;
    q('#lookTrash').hidden=!look;q('#lookTrash').disabled=busy;q('#lookTrash').textContent=look?.trashed_at?'Restore':'Put away';
    q('#lookScene').placeholder=look?.body?.scene_example?'e.g. '+look.body.scene_example:'the place and its props';
    q('#lookSummary').textContent=L.summary(look);
    const saving=L.saveBlocker({preset:typeof selected!=='undefined'?selected:null,positive:q('#positive')?.value,name:q('#lookName').value,busy});
    q('#lookSaveButton').disabled=!!saving;q('#lookSaveReason').textContent=saving;
    const anchor=anchorAsset();q('#lookAnchor').textContent=anchor?'Anchor picture: '+anchor+' (the picture this run came from).':'No anchor picture: prepare from a kept picture first to record one.';
  }
  function render(keep){
    const presetId=typeof selected!=='undefined'?selected?.id:null,{active,away}=L.groups(looks),opt=l=>'<option value="'+esc(l.id)+'">'+esc(L.optionLabel(l,presetId))+'</option>';
    q('#lookSelect').innerHTML='<option value="">'+(looks.length?'Choose a look…':'No saved looks yet')+'</option>'+active.map(opt).join('')+(away.length?'<optgroup label="Put away">'+away.map(opt).join('')+'</optgroup>':'');
    q('#lookSelect').value=looks.some(l=>l.id===keep)?keep:'';sync();
  }
  async function load(keep){
    try{const data=await api('/api/looks');looks=data.looks||[];render(keep??q('#lookSelect').value);if(data.seed_errors?.length)status('Some shipped looks were not loaded: '+data.seed_errors.join('; '),true);}
    catch(e){status('Looks are unavailable: '+e.message+'. Reload the page to try again.',true);}
  }
  async function act(work){if(busy)return;busy=true;sync();try{await work();}catch(e){status(e.message,true);if(e.status===409)await load();}finally{busy=false;sync();}}
  function apply(result){
    const typed=q('#positive').value.trim(),switched=selected?.id!==result.preset_id;
    if(typed&&typed!==String(selected?.defaults?.positive||'').trim()&&typed!==composed&&!confirm('This look replaces the wording in Create. Continue?')){status('Nothing changed.');return;}
    // Reload the recipe even when it is open: a setting the look does not store, or a parent picture, must not linger.
    const batch=q('#batch').value;selectPreset(result.preset_id);q('#batch').value=batch;
    const problems=L.applyControls(result.controls,key=>key==='positive'?q('#positive'):key==='negative'?q('#negative'):getControl(key));
    if(problems.length){
      L.restoreApplication({version:1,preset_id:result.preset_id,controls:problems},result.preset_id);
      q('#positive').dispatchEvent(new Event('input',{bubbles:true}));updateReady();recipeChanged();
      const text=L.applicationBlocker(result.preset_id);message(text,true);status(text,true);return;
    }
    composed=result.controls.positive;q('#positive').dispatchEvent(new Event('input',{bubbles:true}));
    updateLoraHints();updateReady();scheduleTimeEstimate();recipeChanged();
    const text=L.readyMessage(result,switched,looks.find(l=>l.id===result.look.id));message(text);status(text);
  }
  q('#lookSelect').addEventListener('change',sync);q('#lookScene').addEventListener('input',sync);q('#lookName').addEventListener('input',sync);
  q('#positive').addEventListener('input',sync);document.addEventListener('studio:recipe',()=>render(q('#lookSelect').value));
  q('#lookScene').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.ctrlKey&&!e.metaKey){e.preventDefault();if(!q('#lookPrepare').disabled)q('#lookPrepare').click();}});
  function preparationStamp(){
    const look=current();
    return JSON.stringify([look?.id,look?.revision,q('#lookScene').value,checkedLines(),
      typeof StudioSetupDraft!=='undefined'?StudioSetupDraft.stamp():[selected?.id,values(),q('#batch').value]]);
  }
  q('#lookPrepare').onclick=()=>act(async()=>{
    const look=current(),scene=q('#lookScene').value,reason=L.prepareBlocker({look,scene});
    if(reason)throw Error(reason);
    const options=L.optionsPayload(look,checkedLines()),stamp=preparationStamp(),epoch=preparationEpoch;
    const token=L.beginPreparation();
    const currentRequest=()=>{try{return epoch===preparationEpoch&&stamp===preparationStamp();}catch{return false;}};
    const stale=()=>status('Create or the selected Look changed while preparing. The result was not applied. Review the current inputs and prepare again.');
    try{
      updateReady();let result;
      try{result=await post('/api/looks/prepare',{id:look.id,scene,expected_revision:look.revision,...(options?{options}:{})});}
      catch(error){if(!currentRequest()){stale();return;}throw error;}
      if(!currentRequest()){stale();return;}
      // Application is synchronous; release before it renders an actual recovery hold.
      L.finishPreparation(token);apply(result);
    }finally{L.finishPreparation(token);updateReady();}
  });
  q('#lookReset').onclick=()=>{if(busy)return;selectPreset(selected.id);status('Recipe reset without the look. Review its defaults before generating.');};
  q('#lookTrash').onclick=()=>act(async()=>{const look=current();const saved=await post('/api/looks',{action:look.trashed_at?'restore':'trash',id:look.id,expected_revision:look.revision});await load(saved.id);status(saved.name+(saved.trashed_at?' put away. Restore brings it back.':' restored.'));});
  q('#lookSaveButton').onclick=()=>act(async()=>{
    const body={preset_id:selected.id,template:q('#positive').value,controls:L.saveControls(values())};if(selected.negative)body.negative=q('#negative').value;
    const anchor=anchorAsset(),saved=await post('/api/looks',{action:'create',kind:'look',name:q('#lookName').value.trim(),body,...(anchor?{anchor_asset_id:anchor}:{})});
    q('#lookName').value='';await load(saved.id);status(saved.name+' saved in your Workspace. Type a scene and prepare to use it.');
  });
  load();
})();
