/* Explicit stage recall for completed parallax cards. Preparation only, never generation. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else{root.StudioParallaxRecovery=api;api.mount(root);}
})(globalThis,function(){
  'use strict';
  const names={plate:'clean plate',isolate:'isolate'};
  const fields=['version','plan_id','preset_id','source_asset_id','source_sha256','source_file','width','height','objects','view_polygons'];
  const activeSiblings=['queued','waiting','submitting','running','uncertain'];
  const identity=claim=>JSON.stringify(fields.map(key=>claim?.[key]));
  const need=(condition,text)=>{if(!condition)throw Error(text);};
  function siblingNote(job,list){
    const plan=job?.parallax?.plan_id;
    if(!plan||!Array.isArray(list))return '';
    const active=list.filter(entry=>entry&&entry.id!==job.id&&entry.parallax?.plan_id===plan&&activeSiblings.includes(entry.status));
    if(!active.length)return '';
    return ' '+active.map(entry=>{
      const label=names[entry.parallax?.stage]||String(entry.parallax?.stage||'edit');
      if(entry.status==='uncertain')return 'The '+label+' edit is uncertain. Inspect the original job and do not repeat it.';
      return 'The '+label+' edit is '+entry.status+'. Wait for the original job before generating.';
    }).join(' ');
  }
  function retainedSiblingNote(before){
    return ' The job list could not be refreshed. Retained observation: this is the sibling status from before the request.'+(before||'');
  }
  function render(job,output,original,escape){
    if(output?.parallax||job?.status!=='completed'||!Object.hasOwn(names,job.parallax?.stage))return original;
    const missing=Object.keys(names).filter(stage=>!original.includes('data-stage="'+stage+'"'));
    return original+missing.map(stage=>'<button type="button" class="parallaxStage" data-job="'+escape(job.id)+'" data-stage="'+stage+'" title="Load this stage for review. Nothing runs until you press Generate.">Load the '+names[stage]+' edit</button>').join('');
  }
  function create(options){
    let pending=false;
    const currentJobs=()=>typeof options.jobs==='function'?options.jobs():[];
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
        const source=ready(id,stage),expected=identity(source.parallax),stamp=options.stamp();
        const before=siblingNote(source,currentJobs());
        if(!options.confirm('Load the '+names[stage]+' edit? This replaces the current Create settings. Nothing runs until you press Generate.'+before))return false;
        need(identity(ready(id,stage).parallax)===expected&&options.stamp()===stamp,'Create or the source plan changed. Nothing was replaced.');
        const result=await options.request({job_id:id,stage});
        need(identity(ready(id,stage).parallax)===expected&&options.stamp()===stamp,'Create or the source plan changed. Nothing was replaced.');
        checkResponse(result,expected,stage);
        let fresh=true;
        if(typeof options.refresh==='function'){try{await options.refresh();}catch{fresh=false;}}
        options.apply(result,fresh?siblingNote(options.job(id),currentJobs()):retainedSiblingNote(before));
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
      jobs:()=>jobs,
      refresh:refreshJobs,
      available:job=>{const target=catalog?.presets.find(p=>p.id===job.parallax.preset_id&&p.parallax_route);return !!target&&(target.backend_id||'primary')===backendActive;},
      confirm:text=>root.confirm(text),
      request:body=>post('/api/parallax/stage',body),
      apply:(result,note)=>{beginParallax(result);showView('create');message('The '+names[result.stage]+' edit is loaded. Review its words.'+(note||' Then press Generate.'));}
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
