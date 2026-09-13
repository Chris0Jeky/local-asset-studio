/* Deterministic continuation policy. Suggestions are data, never execution authority. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioContinuation=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const fields=['intent','preset_id','reference_file','source_asset_id','source_sha256','template_sha256','version'];
  function normalize(value){
    if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join()!==fields.join()||value.version!==1)return null;
    for(const key of fields.filter(k=>k!=='version'))if(typeof value[key]!=='string'||!value[key]||value[key].length>255)return null;
    if(!['edit','repair','animate','mesh'].includes(value.intent)||!['source_sha256','template_sha256'].every(k=>/^[a-f0-9]{64}$/.test(value[k]))||!/^[a-f0-9]{32}_[A-Za-z0-9._-]+\.(png|jpg|webp)$/.test(value.reference_file))return null;
    return Object.fromEntries(fields.map(k=>[k,value[k]]));
  }
  const routes={edit:['image-to-image','instruction-edit','localized-detail','upscale'],repair:['image-to-image','localized-detail','upscale','masked-repair'],animate:['image-to-video'],mesh:['image-to-3d']};
  function destinations(intent,presets,source){
    const family=presets.find(p=>p.id===source?.preset_id)?.family;
    const prefer={edit:['qwen-1ref','krea-refine'],repair:['anime-detail-fix','krea-refine','anime-esrgan-2x'],animate:['wan22-i2v'],mesh:['trellis-auto-cutout']}[intent]||[];
    const score=p=>(p.runtime_block?1000:0)+(p.continuation_capability.requires_mask?500:0)+(family&&p.family===family?-100:0)+(prefer.includes(p.id)?prefer.indexOf(p.id):100);
    return presets.filter(p=>p.continuation_capability?.consumes_source&&routes[intent]?.includes(p.continuation_capability.operation)).sort((a,b)=>score(a)-score(b)||a.name.localeCompare(b.name));
  }
  function initial(source,preset,intent,file){
    const cap=preset?.continuation_capability;
    if(!source||source.version!==1||!cap?.consumes_source)throw Error('Source context or the source-consuming graph is unavailable. Refresh before continuing.');
    if(!routes[intent]?.includes(cap.operation))throw Error('The destination does not support this operation.');
    if(cap.requires_mask)throw Error('Prepare an RGBA repair mask first. A plain source copy is not a repair mask.');
    const claim=normalize({version:1,intent,preset_id:preset.id,reference_file:file,source_asset_id:source.asset_id,source_sha256:source.sha256,template_sha256:cap.template_sha256});
    if(!claim)throw Error('The source attachment could not be verified. Reopen the handoff.');
    const copy=cap.prompt_role==='description'&&source.prompt_role==='description'&&source.prompt_origin==='submitted-output';
    return{claim,positive:copy&&typeof source.positive==='string'?source.positive:'',negative:copy&&typeof source.negative==='string'?source.negative:''};
  }
  function settings(preset,overrides,current){
    const protectedKeys=new Set(['positive','negative','reference','last_reference']);
    const out={...current};
    for(const [key,value]of Object.entries(preset.defaults||{}))if(!protectedKeys.has(key)&&!['width','height','seed'].includes(key))out[key]=value;
    for(const [key,value]of Object.entries(overrides||{}))if(!protectedKeys.has(key))out[key]=value;
    return out;
  }
  function blockers(claim,preset,controls,parents,refs=[]){
    if(!claim)return[];
    if(!normalize(claim))return['Continuation context is invalid. Reopen Continue with this asset.'];
    const cap=preset?.continuation_capability,reasons=[];
    if(preset?.id!==claim.preset_id||!cap?.consumes_source)reasons.push('This route cannot consume the selected source. Choose a source-based route or leave continuation explicitly.');
    if(cap&&(!routes[claim.intent]?.includes(cap.operation)||cap.template_sha256!==claim.template_sha256))reasons.push('The destination operation or graph changed. Reopen the handoff before running.');
    if(cap?.requires_mask)reasons.push('Prepare the RGBA repair mask in the dedicated repair workflow first.');
    const files=preset?.reference_slots?.length?refs.map(item=>item?.file):[controls.reference,...(preset?.last_reference?[controls.last_reference]:[])];
    if(files[0]!==claim.reference_file||!parents?.includes(claim.source_asset_id))reasons.push('The source attachment changed or is missing. Reopen Continue with the intended image. No example fallback is allowed.');
    if(files.length!==(cap?.reference_count||0)||files.some(file=>typeof file!=='string'||!file))reasons.push('Attach every source input explicitly. An authored example cannot supply a missing continuation frame.');
    if(preset?.positive&&!String(controls.positive||'').trim())reasons.push(cap?.prompt_role==='motion'?'Describe the motion and camera movement before running.':cap?.prompt_role==='instruction'?'Say what to change and what to keep before running.':'Describe the desired image before running. No source description was available to copy.');
    return reasons;
  }
  function guidance(preset,source){
    const cap=preset?.continuation_capability;
    if(!cap?.consumes_source)return['This recipe does not have a verified source-to-output connection.'];
    const text=[{'image-to-image':'Resamples the attached image, rather than starting with an empty image. Identity, style and background can still drift.','localized-detail':'Detects and repaints local regions. Detection can miss a face or hand; inspect the output before accepting it.','instruction-edit':'Uses the source as visual context. Write the change you want and what should stay the same.','upscale':'Enlarges the source without a text prompt. This does not repair pose or guarantee identical fine detail.','masked-repair':'Needs a prepared RGBA PNG: transparent alpha identifies the repair region. A plain source copy is not enough.','image-to-video':'Uses the source as a visual input. Describe motion, timing and camera movement; an image caption alone is not a motion brief.','image-to-3d':'Uses the source for reconstruction. Hidden surfaces are inferred; inspect the mesh and materials.'}[cap.operation]||cap.scope];
    if(cap.prompt_role==='description')text.push(source?.prompt_role==='description'&&source?.positive?'Copies this output’s actual submitted description. You may refine the description without changing the source.':'No reusable image description is available. Write one; recipe example text will stay out of the prompt.');
    if(source?.preset_id&&source.preset_id!==preset.id&&cap.prompt_role!=='none')text.push('Different source recipe: '+(source.preset_name||source.preset_id)+'. Source sampling settings, seed and adapters are not copied. Check destination style triggers; low denoise does not guarantee the same look.');
    if(cap.reference_count>1)text.push('This attaches Picture 1 only. Add '+(cap.reference_count-1)+' more required reference(s).');
    if(preset.runtime_block)text.push(preset.runtime_block);
    return text.filter(Boolean);
  }
  function variantHelp(preset,variant){
    const values=settings(preset,variant.controls,{}),parts=[];
    if(values.denoise!=null){const n=Number(values.denoise);parts.push('Denoise '+values.denoise+': '+(n<=0.3?'less resampling noise; generally closer to the source':n<1?'more repainting freedom; identity and scenery may change':'full-noise resampling; not a preservation pass')+'.');}
    if(values.steps!=null)parts.push(values.steps+' sampling steps.');
    for(let i=1;i<=6;i++){const slot='lora'+(i===1?'':i),name=preset.defaults?.[slot+'_name'];if(name&&Number(values[slot])===0&&Number(preset.defaults?.[slot])!==0)parts.push('Switches off adapter '+i+' ('+name+').');}
    return parts.join(' ')||'Applies the listed settings; inspect parameters before running.';
  }
  return{normalize,initial,settings,blockers,guidance,variantHelp,destinations};
});
