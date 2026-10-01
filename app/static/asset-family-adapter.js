/* Read-only family controls reuse the public Create draft owner and the existing source picker. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioFamilyAdapter=api;
})(globalThis,function(){
  'use strict';
  const need=(condition,message)=>{if(!condition)throw Error(message);};
  function create(options){
    function context(){
      const state=options.state();
      return {workspace:state.workspace,stamp:JSON.stringify([options.owner.stamp(),state.assetId,state.assetEpoch,
        state.workspaceEpoch,state.fields,state.pending,state.conflict,state.metadataBusy,state.specialized])};
    }
    function idle(){
      const state=options.state();
      need(!state.dirty&&!state.pending&&!state.conflict&&!state.metadataBusy,
        'Finish the current edit or pending asset save first. Your work was kept.');
      need(!options.owner.busy(),'Wait for the current Create action to finish. Your work was kept.');
      need(!state.specialized,'Leave the current continuation or specialized workflow before recalling a recipe. Your work was kept.');
      return state;
    }
    function apply(result,check,mode){
      const state=idle(),recipe=result.recipe,target=options.presets().find(p=>p.id===recipe.preset_id);
      need(result.workspace_id===state.workspace&&result.asset_id===state.assetId,'The asset or Workspace changed. Your work was kept.');
      need(target&&target.seed,'This recorded recipe or its seed control is unavailable. Open its original workflow instead.');
      need((target.backend_id||'primary')===options.backend(),'Switch to the recorded recipe’s backend explicitly before recalling it.');
      const draft={version:1,updatedAt:Date.now(),pendingInputs:[],templateHash:check.template_sha256,recipe:{
        preset:target.id,controls:{...result.controls},batch:1,parent_assets:recipe.parent_assets||[],
        references:recipe.references||[],...(recipe.continuation?{continuation:recipe.continuation}:{})}};
      // The owner validates every control, reference slot and graph identity before adopting.
      // No direct selectPreset/applySaved interception, server command, copy or generation here.
      options.owner.adopt(draft,options.owner.stamp(),options.backend());
      options.finish(mode,target,result.controls.seed);
    }
    async function reference(id){
      const state=options.state();
      need(!state.dirty&&!state.pending&&!state.conflict&&!state.metadataBusy,
        'Save or resolve the asset editor first. Your draft is kept.');
      need(!options.owner.busy(),'Wait for the current Create action to finish. Your work was kept.');
      const asset=options.asset(id);
      need(asset&&asset.trashed_at==null&&asset.media_type==='image','Choose an active image as a reference.');
      const stamp=options.owner.stamp(),scope=state.workspace;
      await options.picker(asset,()=>options.owner.stamp()===stamp&&options.state().workspace===scope);
    }
    return {context,apply,reference};
  }
  return {create};
});

(function(){
  'use strict';
  if(typeof document==='undefined'||typeof module==='object')return;
  function boot(){
    const F=globalThis.StudioAssetFamily,owner=globalThis.StudioSetupDraft,q=s=>document.querySelector(s);
    if(!F||!owner||!q('#assetDialog')||q('#assetFamily'))return;
    const state=()=>({workspace:assetState.workspace_id,workspaceEpoch:assetWorkspaceEpoch,
      assetId:q('#assetDialog').open?activeAsset?.id:null,assetEpoch:assetDetailEpoch,fields:assetDetailValues(),
      dirty:assetDetailDirty(),pending:!!assetDetailPending,conflict:!!assetDetailConflict,metadataBusy:assetDetailBusy,
      specialized:!!continuationState||!!tileState||!!parallaxState||q('#uxPoseEditor')?.hidden===false});
    const adapter=StudioFamilyAdapter.create({owner,state,presets:()=>catalog?.presets||[],backend:()=>backendActive,
      asset:id=>assetState.assets.find(a=>a.id===id),
      finish:(mode,target,seed)=>{
        q('#assetDialog').close();showView('create');
        const focus=mode==='words'&&target.positive?q('#positive'):getControl('seed');
        if(focus){for(let el=focus.parentElement;el;el=el.parentElement)if(el.tagName==='DETAILS')el.open=true;
          focus.focus({preventScroll:true});focus.scrollIntoView({block:'center'});}
        message((mode==='new'?'New seed ':'Recorded seed ')+seed+' prepared as one output. Review the settings; Generate remains a separate press.');
      },
      picker:async(asset,current)=>{
        const entry=q('#uxPullAsset');
        if(!entry||entry.disabled||typeof entry.onclick!=='function')throw Error('Choose a recipe with an available reference slot in Create first. Nothing was changed.');
        q('#assetDialog').close();showView('create');
        // Invoke the existing button's handler, including its own single-flight and stale-read checks.
        await entry.onclick.call(entry);
        const search=q('#uxSourceSearch');
        if(!current()||!q('#uxSourcePicker')?.open||!search||search.disabled)return;
        search.value=asset.title;search.dispatchEvent(new Event('input',{bubbles:true}));
        const choice=[...document.querySelectorAll('#uxSourceAssets [data-ux-pull]')].find(b=>b.dataset.uxPull===asset.id);
        (choice||search).focus({preventScroll:true});
      }});
    const family=F.install({...adapter,read:api,say:message,asset:()=>activeAsset,
      confirm:globalThis.confirm.bind(globalThis),
      check:(recipe,signal)=>api('/api/recipe-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recipe),signal}),
      open:id=>{if(!openAsset(id))message('The asset could not be opened. Your current editor was kept.',true);}});
    let last=null;
    function observeDetail(){
      const now=state(),key=q('#assetDialog').open?JSON.stringify([now.workspace,now.assetId,now.assetEpoch]):null;
      if(key===last)return;last=key;
      if(key)void family.opened();else family.clear();
    }
    // Presentation observers watch only the existing dialog's session projection and gallery.
    // They neither intercept legacy functions nor add a polling loop or authoritative state.
    const details=new MutationObserver(observeDetail);
    details.observe(q('#assetDialog'),{attributes:true,attributeFilter:['open']});
    details.observe(q('#assetDetailMedia'),{childList:true});
    const results=new MutationObserver(()=>family.decorateResults());
    results.observe(q('#gallery'),{childList:true,subtree:true});
    globalThis.addEventListener('pagehide',()=>family.clear());
    globalThis.addEventListener('pageshow',event=>{if(event.persisted){last=null;observeDetail();family.decorateResults();}});
    observeDetail();family.decorateResults();
  }
  if(globalThis.StudioSetupDraft)boot();else document.addEventListener('studio:setup-draft-ready',boot,{once:true});
})();
