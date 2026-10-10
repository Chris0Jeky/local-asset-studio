/* Explicit stage recall for completed parallax cards. Preparation only, never generation. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{root.StudioParallaxRecovery=api;api.mount(root);}
})(globalThis,function(){
  'use strict';
  const names={plate:'clean plate',isolate:'isolate'};
  const fields=['version','plan_id','preset_id','source_asset_id','source_sha256','source_file','width','height','objects','view_polygons'];
  const identity=claim=>JSON.stringify(fields.map(key=>claim?.[key]));
  const need=(condition,text)=>{if(!condition)throw Error(text);};
  function render(job,output,original,escape){
    if(output?.parallax||job?.status!=='completed'||!Object.hasOwn(names,job.parallax?.stage))return original;
    const missing=Object.keys(names).filter(stage=>!original.includes('data-stage="'+stage+'"'));
    return original+missing.map(stage=>'<button type="button" class="parallaxStage" data-job="'+escape(job.id)+'" data-stage="'+stage+'" title="Load this stage for review. Nothing runs until you press Generate.">Load the '+names[stage]+' edit</button>').join('');
  }
  function create(options){
    let pending=false;
    function ready(id,stage){
      need(Object.hasOwn(names,stage),'Choose the clean plate or isolate stage.');
      const job=options.job(id);
      need(job?.status==='completed'&&Object.hasOwn(names,job.parallax?.stage),'Choose a completed parallax stage.');
      need(!options.busy(),'Finish the current Create action first. Your work was kept.');
      need(options.available(job),'The parallax recipe or backend changed. Your work was kept.');
      return job;
    }
    function checkResponse(result,expected,stage){
      need(result&&result.generation_submitted===false&&result.stage===stage&&result.claim?.stage===stage
        &&identity(result.claim)===expected&&identity(result.plan)===expected
        &&result.preset_id===result.claim.preset_id&&result.file===result.claim.source_file
        &&result.width===result.claim.width&&result.height===result.claim.height
        &&typeof result.words==='string'&&result.words.trim()&&result.words.length<=8000,
        'The stage response no longer matches the requested plan. Nothing was replaced.');
    }
    return {async load(id,stage){
      if(pending)return false;
      pending=true;
      try{
        const expected=identity(ready(id,stage).parallax),stamp=options.stamp();
        if(!options.confirm('Load the '+names[stage]+' edit? This replaces the current Create settings. Nothing runs until you press Generate.'))return false;
        need(identity(ready(id,stage).parallax)===expected&&options.stamp()===stamp,'Create or the source plan changed. Nothing was replaced.');
        const result=await options.request({job_id:id,stage});
        need(identity(ready(id,stage).parallax)===expected&&options.stamp()===stamp,'Create or the source plan changed. Nothing was replaced.');
        checkResponse(result,expected,stage);
        options.apply(result);
        return true;
      }finally{pending=false;}
    }};
  }
  function mount(root){
    const gallery=root.document?.querySelector('#gallery');
    if(!gallery||gallery.dataset.parallaxRecovery==='mounted')return;
    if(!root.StudioSetupDraft||typeof root.parallaxNote!=='function'){
      if(root.document.readyState==='loading')root.document.addEventListener('DOMContentLoaded',()=>mount(root),{once:true});
      return;
    }
    const owner=root.StudioSetupDraft;
    const controller=create({
      stamp:()=>JSON.stringify([owner.stamp(),parallaxState,tileState]),
      busy:()=>owner.busy()||!!continuationState||!!root.document.querySelector('dialog[open]'),
      job:id=>jobs.find(job=>job.id===id),
      available:job=>{const target=catalog?.presets.find(p=>p.id===job.parallax.preset_id&&p.parallax_route);return !!target&&(target.backend_id||'primary')===backendActive;},
      confirm:text=>root.confirm(text),
      request:body=>post('/api/parallax/stage',body),
      apply:result=>{beginParallax(result);showView('create');message('The '+names[result.stage]+' edit is loaded. Review its words, then press Generate.');}
    });
    const previous=root.parallaxNote;
    root.parallaxNote=(job,output)=>render(job,output,previous(job,output),esc);
    // Capture only stage buttons, including the legacy next-stage button. A single
    // owner prevents the old bubble handler from issuing a second unguarded request.
    gallery.addEventListener('click',async event=>{
      const button=event.target.closest?.('.parallaxStage');
      if(!button||!gallery.contains(button))return;
      event.preventDefault();event.stopImmediatePropagation();
      if(button.disabled)return;
      button.disabled=true;
      try{await controller.load(button.dataset.job,button.dataset.stage);}
      catch(error){message(error.message,true);}
      finally{button.disabled=false;}
    },true);
    gallery.dataset.parallaxRecovery='mounted';
    // Existing cards may precede this asynchronously loaded feature. The renderer's
    // normal focus/media preservation applies; no polling or mutation observer.
    jobsSignature='';renderJobs();
  }
  return {create,render,mount};
});
