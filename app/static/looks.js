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
    return [look.preset_name||look.body?.preset_id,anchor?'anchor '+(anchor.key||String(anchor.sha256||'').slice(0,12))+(look.anchor_asset_id?' (in your Workspace)':' (not in this Workspace)'):'no anchor picture',look.origin==='seed'?'shipped look':'your look'].filter(Boolean).join(' · ');
  }
  function readyMessage(result,switched){
    const c=result.controls||{},size=c.width&&c.height?', '+c.width+'x'+c.height:'',seed=c.seed!=null?', seed '+c.seed:'';
    return result.look.name+' prepared on '+(result.preset_name||result.preset_id)+(switched?' (recipe switched)':'')+seed+size+'. Your scene is in the wording. Nothing was generated; press Generate when it reads right.';
  }
  return{SLOT,slotCount,recipeProblem,groups,optionLabel,prepareBlocker,saveBlocker,saveControls,summary,readyMessage};
});

(function(){
  'use strict';
  if(typeof document==='undefined'||!document.querySelector('#createView')||typeof module==='object')return;
  const L=StudioLooks,q=s=>document.querySelector(s);
  let looks=[],busy=false,composed=null;
  const block=document.createElement('section');block.id='lookBlock';block.className='ux-looks';block.setAttribute('aria-labelledby','lookTitle');
  block.innerHTML='<h4 id="lookTitle">Use a saved look</h4><div class="ux-looks-row"><label>Look<select id="lookSelect"></select></label><label>Scene<input id="lookScene" maxlength="1000" autocomplete="off" aria-describedby="lookReason"></label></div>'
    +'<p id="lookSummary" class="muted"></p><div class="ux-looks-row"><button type="button" id="lookPrepare" aria-describedby="lookReason">Prepare with this look</button><button type="button" id="lookTrash" aria-describedby="lookReason">Put away</button></div><p class="disabledReason"><small id="lookReason"></small></p>'
    +'<details id="lookSave"><summary>Save this wording as a look</summary><p class="muted">Write '+L.SLOT+' in the wording where a new scene goes. The recipe and its settings are saved with it.</p><label>Look name<input id="lookName" maxlength="120" autocomplete="off" aria-describedby="lookSaveReason"></label><p id="lookAnchor" class="muted"></p><button type="button" id="lookSaveButton" aria-describedby="lookSaveReason">Save look</button><p class="disabledReason"><small id="lookSaveReason"></small></p></details>'
    +'<p id="lookStatus" role="status" aria-live="polite"></p>';
  (q('#uxFills')||q('#positiveWrap')).before(block);
  const current=()=>looks.find(l=>l.id===q('#lookSelect').value)||null;
  const status=(text,error=false)=>{q('#lookStatus').textContent=text;q('#lookStatus').classList.toggle('error',error);};
  const anchorAsset=()=>typeof parentAssets!=='undefined'&&parentAssets.length===1?parentAssets[0]:null;
  function sync(){
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
    if(switched)selectPreset(result.preset_id);
    for(const [key,value] of Object.entries(result.controls)){const input=key==='positive'?q('#positive'):key==='negative'?q('#negative'):getControl(key);if(input)input.value=value;}
    composed=result.controls.positive;q('#positive').dispatchEvent(new Event('input',{bubbles:true}));
    updateLoraHints();updateReady();scheduleTimeEstimate();recipeChanged();
    const text=L.readyMessage(result,switched);message(text);status(text);
  }
  q('#lookSelect').addEventListener('change',sync);q('#lookScene').addEventListener('input',sync);q('#lookName').addEventListener('input',sync);
  q('#positive').addEventListener('input',sync);document.addEventListener('studio:recipe',()=>render(q('#lookSelect').value));
  q('#lookScene').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.ctrlKey&&!e.metaKey){e.preventDefault();if(!q('#lookPrepare').disabled)q('#lookPrepare').click();}});
  q('#lookPrepare').onclick=()=>act(async()=>{const look=current();apply(await post('/api/looks/prepare',{id:look.id,scene:q('#lookScene').value,expected_revision:look.revision}));});
  q('#lookTrash').onclick=()=>act(async()=>{const look=current();const saved=await post('/api/looks',{action:look.trashed_at?'restore':'trash',id:look.id,expected_revision:look.revision});await load(saved.id);status(saved.name+(saved.trashed_at?' put away. Restore brings it back.':' restored.'));});
  q('#lookSaveButton').onclick=()=>act(async()=>{
    const body={preset_id:selected.id,template:q('#positive').value,controls:L.saveControls(values())};if(selected.negative)body.negative=q('#negative').value;
    const anchor=anchorAsset(),saved=await post('/api/looks',{action:'create',kind:'look',name:q('#lookName').value.trim(),body,...(anchor?{anchor_asset_id:anchor}:{})});
    q('#lookName').value='';await load(saved.id);status(saved.name+' saved in your Workspace. Type a scene and prepare to use it.');
  });
  load();
})();
