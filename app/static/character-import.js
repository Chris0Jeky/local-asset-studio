// A local preview and an explicit caller of the existing primary-case import.
// Production remains the plan/reference/preflight/budget authority.
(()=>{
  const MAX_JSON=1024*1024,MAX_IMAGE=20*1024*1024,hex=/^[0-9a-f]{64}$/;
  let loaded=null,busy=false,attempted=false,abortRequested=false,uploadController=null;
  const status=(message,error=false)=>{const target=$('#characterImportStatus');target.textContent=message;target.classList.toggle('error',error);};
  const require=(condition,message)=>{if(!condition)throw Error(message);};
  const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');
  const lock=value=>{busy=value;$('#characterImportInputs').disabled=value;$('#cancelCharacterImport').disabled=false;};
  const cancelMessage=(done,total)=>done>0?'Import cancelled after '+done+' of '+total+' pictures. Nothing was imported; pictures already uploaded stay ready for another try.':'Import cancelled after 0 of '+total+' pictures. Nothing was imported.';
  const requestAbort=()=>{abortRequested=true;try{uploadController?.abort();}catch(e){}};
  function clear(){loaded=null;attempted=false;$('#characterCaseFields').hidden=true;$('#importCharacterCase').disabled=true;$('#characterReferenceFiles').innerHTML='';$('#importCharacterCase').textContent='Import planned case';}
  async function readFile(selector,label){
    const file=$(selector).files[0];require(file,label+' is required.');
    require(file.size>0&&file.size<=MAX_JSON,label+' must be a JSON file under 1 MiB.');
    try{const raw=(await file.text()).replace(/^\uFEFF/,'');return {value:JSON.parse(raw),raw};}catch(e){throw Error(label+' is not readable JSON.');}
  }
  function check(plan,handoff){
    require(plan?.kind==='character_study_plan'&&plan.submits_generation===false&&hex.test(plan.plan_sha256),'Choose a saved character study plan.');
    require(handoff?.kind==='character_study_handoff'&&handoff.submits_generation===false&&handoff.submission_payload===null&&hex.test(handoff.handoff_sha256),'Choose an unarmed character study handoff.');
    require(handoff.plan_sha256===plan.plan_sha256&&handoff.schema_version===plan.schema_version,'The handoff belongs to a different study plan.');
    require(plan.canon?.approval?.state==='approved'&&plan.canon.approval.reviewer_kind==='human','Record the owner’s canon approval before importing this study.');
    const cases=Array.isArray(plan.cases)?plan.cases.filter(c=>c.id===handoff.case_id):[];
    require(cases.length===1,'The handoff must name exactly one case in this plan.');
    const item=cases[0],refs=handoff.upload_requirements,canonRefs=plan.canon.references,allowance=plan.request?.budget?.max_generation_attempts;
    require(Number.isSafeInteger(item.seed)&&item.seed===handoff.proposed_controls?.seed&&item.preset_id===handoff.preset_id,'The handoff recipe or seed differs from this case, or its seed cannot be represented exactly here.');
    require(Number.isSafeInteger(allowance)&&allowance>=1,'The study must declare a finite generation allowance.');
    require(Array.isArray(refs)&&refs.length>0&&refs.length<=32&&Array.isArray(canonRefs)&&Array.isArray(item.reference_ids)&&refs.length===item.reference_ids.length,'Every case reference must have a handoff slot.');
    const seen=new Set();
    refs.forEach((ref,i)=>{
      const original=canonRefs.filter(r=>r.id===ref.id);
      require(typeof ref.id==='string'&&/^[a-z][a-z0-9-]{0,79}$/.test(ref.id)&&!seen.has(ref.id)&&ref.id===item.reference_ids[i]&&ref.slot_index===i,'Reference IDs and slot order must match the case.');
      require(original.length===1&&hex.test(ref.sha256)&&ref.sha256===original[0].sha256&&ref.role===original[0].role&&ref.path===original[0].path,'A handoff reference differs from the approved canon.');
      seen.add(ref.id);
    });
    return {plan,handoff,item,refs,allowance,uploads:new Map()};
  }
  function payload(names){return {character_plan:loaded.plan,character_handoff:loaded.handoff,uploads:names,name:$('#characterImportName').value.trim(),max_seconds:Number($('#characterImportMinutes').value)*60};}
  function serialize(value){
    // Python's contract digests distinguish 1.0 from 1. Preserve both original
    // JSON values instead of round-tripping them through JavaScript numbers.
    return '{"character_plan":'+loaded.planText+',"character_handoff":'+loaded.handoffText+',"uploads":'+JSON.stringify(value.uploads)+',"name":'+JSON.stringify(value.name)+',"max_seconds":'+value.max_seconds+'}';
  }
  function validatePayload(value){
    require(value.name.length>0&&value.name.length<=120,'Give this case a name of 1–120 characters.');
    require(Number.isInteger(value.max_seconds)&&value.max_seconds>=60&&value.max_seconds<=14400,'Choose 1–240 whole minutes.');
    require(new TextEncoder().encode(serialize(value)).length<=MAX_JSON,'The complete plan and handoff exceed Studio’s 1 MiB import limit. Keep the original files; this case cannot be imported here.');
  }
  function checkedProject(project){
    require(project?.id===loaded.projectId&&project.root_id==='character-study:'+loaded.plan.plan_sha256,'The saved project does not match this study case.');
    if(project.plan){const source=project.plan.character_source;require(source?.kind==='character_primary_import'&&source.case_id===loaded.item.id&&source.study_plan?.plan_sha256===loaded.plan.plan_sha256&&source.handoff?.handoff_sha256===loaded.handoff.handoff_sha256,'This case already exists with a different handoff. Inspect its saved plan in Runs & review.');}
    return project;
  }
  async function existing(){
    const projects=await api('/api/production');require(Array.isArray(projects),'Studio did not return its saved plans.');
    if(!projects.some(p=>p.id===loaded.projectId))return null;
    return checkedProject(await api('/api/production/'+loaded.projectId));
  }
  async function show(project,alreadySaved=false){
    checkedProject(project);productionId=project.id;$('#characterImportDialog').close();showView('production');
    await refreshProduction(true);
    productionMessage((alreadySaved?'Opened the existing case.':'Imported the planned case.')+' Nothing was started. Use its separate Start action when ready.');
  }
  $('#importCharacterStudy').onclick=()=>{if(busy)return;clear();$('#characterPlanFile').value='';$('#characterHandoffFile').value='';$('#characterImportMinutes').value='30';status('Choose the approved study plan and the handoff for one case.');$('#characterImportDialog').showModal();};
  $('#cancelCharacterImport').onclick=()=>{if(busy)requestAbort();else $('#characterImportDialog').close();};
  $('#characterImportDialog').oncancel=e=>{if(busy){e.preventDefault();requestAbort();}};
  for(const selector of ['#characterPlanFile','#characterHandoffFile'])$(selector).onchange=()=>{if(!busy){clear();status('Read the selected files to preview this case.');}};
  $('#readCharacterCase').onclick=async()=>{
    if(busy)return;clear();lock(true);
    try{
      const planFile=await readFile('#characterPlanFile','Study plan'),handoffFile=await readFile('#characterHandoffFile','Case handoff'),plan=planFile.value,handoff=handoffFile.value;
      loaded=check(plan,handoff);loaded.planText=planFile.raw;loaded.handoffText=handoffFile.raw;
      loaded.projectId=(await digest(new TextEncoder().encode('character-primary:'+plan.plan_sha256+':'+handoff.case_id))).slice(0,32);
      $('#characterImportName').value=(plan.request.study_id+' · '+loaded.item.task_id+' · '+loaded.item.route_id).slice(0,120);
      validatePayload(payload(loaded.refs.map(ref=>({reference_id:ref.id,file:'x'.repeat(200)}))));
      $('#characterCaseSummary').textContent=loaded.item.task_id+' · '+loaded.item.route_id+' · seed '+loaded.item.seed+'. Declared study limit: '+loaded.allowance+' attempts shared across cases. See the saved case for its current balance.';
      $('#characterCasePrompt').textContent=handoff.proposed_controls.positive;
      $('#characterReferenceFiles').innerHTML=loaded.refs.map((ref,i)=>'<label>Reference '+(i+1)+' · '+esc(ref.id)+' ('+esc(ref.role)+')<small>'+esc(ref.path)+'</small><input id="characterReference'+i+'" type="file" accept="image/png,image/jpeg,image/webp" required></label>').join('');
      $('#characterCaseFields').hidden=false;$('#importCharacterCase').disabled=false;
      status('Choose each original reference. Import checks the current recipe and live model readiness, then saves a planned case.');
    }catch(e){clear();status(e.message,true);}finally{lock(false);}
  };
  $('#characterImportForm').onsubmit=async e=>{
    e.preventDefault();if(busy||!loaded)return;lock(true);abortRequested=false;uploadController=null;
    try{
      if(attempted){const saved=await existing();if(saved)await show(saved,true);else status('The case is not visible yet. No import was repeated. Inspect Runs & review and the reported failure before loading corrected files.',true);return;}
      const files=[];
      validatePayload(payload(loaded.refs.map(ref=>({reference_id:ref.id,file:'x'.repeat(200)}))));
      // Check all bytes before uploading any file; hash one bounded image at a time.
      for(let i=0;i<loaded.refs.length;i++){
        if(abortRequested)throw Error(cancelMessage(0,loaded.refs.length));
        const ref=loaded.refs[i],file=$('#characterReference'+i).files[0];
        require(file,'Choose the original image for '+ref.id+'.');
        require(file.size>0&&file.size<=MAX_IMAGE,'Reference '+ref.id+' must be under 20 MiB.');
        require(['image/png','image/jpeg','image/webp'].includes(file.type),'Reference '+ref.id+' must be a PNG, JPEG or WebP.');
        require(await digest(await file.arrayBuffer())===ref.sha256,'Reference '+ref.id+' has different bytes from the approved handoff. Choose the original file.');
        files.push(file);
      }
      const saved=await existing();if(saved){await show(saved,true);return;}
      const uploads=[];
      for(let i=0;i<files.length;i++){
        if(abortRequested)throw Error(cancelMessage(uploads.length,files.length));
        const ref=loaded.refs[i],file=files[i],known=loaded.uploads.get(i);let name=known?.source===file?known.name:null;
        if(!name){status('Uploading reference '+(i+1)+' of '+files.length+'…');
          uploadController=new AbortController();
          try{
            const uploaded=await api('/api/upload',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':ref.id},body:file,signal:uploadController.signal});
            require(typeof uploaded?.file==='string'&&/^[0-9a-f]{32}_[A-Za-z0-9._-]{1,110}$/.test(uploaded.file),'Studio did not confirm the uploaded reference name.');
            name=uploaded.file;loaded.uploads.set(i,{source:file,name});
          }catch(uploadError){if(abortRequested)throw Error(cancelMessage(uploads.length,files.length));throw uploadError;}
          finally{uploadController=null;}
        }
        uploads.push({reference_id:ref.id,file:name});
      }
      if(abortRequested)throw Error(cancelMessage(uploads.length,files.length));
      const value=payload(uploads);validatePayload(value);attempted=true;$('#importCharacterCase').textContent='Check saved case';status('Checking and importing this case…');
      await show(await api('/api/production',{method:'POST',headers:{'Content-Type':'application/json'},body:serialize(value)}));
    }catch(error){
      status(error.message+(attempted?' Import was not confirmed here. Check the saved case; this button will only read its status.':''),true);
      if(attempted){try{const saved=await existing();if(saved)await show(saved,true);}catch(checkError){status(error.message+' The saved case could not be checked: '+checkError.message+'. No import was repeated.',true);}}
    }finally{lock(false);}
  };
})();
