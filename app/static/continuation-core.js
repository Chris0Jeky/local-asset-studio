/* Deterministic continuation policy. Suggestions are data, never execution authority. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioContinuation=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const fields=['intent','preset_id','reference_file','source_asset_id','source_sha256','template_sha256','version'];
  const INTENTS=['edit','repair','restyle','combine','animate','mesh'];
  function normalize(value){
    if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join()!==fields.join()||value.version!==1)return null;
    for(const key of fields.filter(k=>k!=='version'))if(typeof value[key]!=='string'||!value[key]||value[key].length>255)return null;
    if(!INTENTS.includes(value.intent)||!['source_sha256','template_sha256'].every(k=>/^[a-f0-9]{64}$/.test(value[k]))||!/^[a-f0-9]{32}_[A-Za-z0-9._-]+\.(png|jpg|webp)$/.test(value.reference_file))return null;
    return Object.fromEntries(fields.map(k=>[k,value[k]]));
  }
  const routes={edit:['image-to-image','instruction-edit','localized-detail','upscale'],repair:['image-to-image','localized-detail','upscale','masked-repair'],restyle:['restyle'],combine:['combine'],animate:['image-to-video'],mesh:['image-to-3d']};
  function placeholders(preset){const value=preset?.continuation_placeholder;return(Array.isArray(value)?value:[value]).filter(text=>typeof text==='string'&&text);}
  // The recipe's bracketed fills still present in the wording; the server refuses to run with any left, on every route.
  function unfilled(preset,text){const value=typeof text==='string'?text:'';return placeholders(preset).filter(item=>value.includes(item));}
  // Which declared input receives the continuation source. A style board keeps its pose picture on last_reference.
  function sourceInput(cap){return cap?.source_input==='last_reference'?'last_reference':'reference';}
  // A board recipe says which image number its board is in its label ("Pose picture (image 1)"); the 9B Combine keeps the pose picture as image 1 and swaps the character in as image 2.
  function boardImage(preset){const m=/\((image \d)\)/.exec(preset?.reference_board_label||'');return m?' ('+m[1]+')':'';}
  function sourceLabel(preset){const cap=preset?.continuation_capability;return sourceInput(cap)==='last_reference'?preset.last_reference_label||'Pose picture':preset?.reference_slots?.length?'Picture 1':preset?.reference_label||'Reference';}
  function destinations(intent,presets,source){
    const family=presets.find(p=>p.id===source?.preset_id)?.family;
    // Edit leads with the 20-second Klein edit; the 11-minute Qwen edit stays available but no longer greets the user.
    const prefer={edit:['flux-edit','qwen-1ref','krea-refine'],repair:['anime-detail-fix','krea-refine','anime-esrgan-2x'],restyle:['restyle-klein','restyle-klein-picture','restyle-wai','style-pose-wai','style-pose-nova','style-pose-yumeflux'],combine:['combine-klein-9b-depth','combine-klein-9b','combine-klein'],animate:['wan22-i2v'],mesh:['trellis-auto-cutout']}[intent]||[];
    // For Restyle, a recipe that keeps the picture (img2img) outranks the source's own Style + Pose family.
    const score=p=>(p.runtime_block?1000:0)+(p.continuation_capability.requires_mask?500:0)+(intent==='restyle'&&p.continuation_capability.keeps_picture?-300:0)+(family&&p.family===family?-100:0)+(prefer.includes(p.id)?prefer.indexOf(p.id):100);
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
    const prepared=promptFor(preset,source);
    return{claim,positive:prepared!=null?prepared:copy&&typeof source.positive==='string'?source.positive:'',negative:copy&&typeof source.negative==='string'?source.negative:''};
  }
  // A recipe may author the wording of a continuation: its `continuation_prompt` is used verbatim, with `{source}`
  // standing for the source's own submitted description (or nothing when no exact description is retained).
  // An instruction ("Redraw this image as…", "Change one thing…") is not a description: appending it would compound
  // the previous pass's orders into this one, so only a description-role prompt is carried over.
  function promptFor(preset,source){
    const template=preset?.continuation_prompt;
    if(typeof template!=='string'||!template.trim())return null;
    const described=source?.prompt_origin==='submitted-output'&&source.prompt_role==='description'&&typeof source.positive==='string'&&source.positive.trim();
    const lead=preset.continuation_capability?.board_min>0?' Image 1 shows: ':' The picture shows: ';
    // A function replacement keeps `$&`-style patterns in a description literal; a description that would push the
    // wording past the server's 8000-character prompt limit is left out rather than blocking Generate later.
    const text=template.replace('{source}',()=>described?lead+source.positive.trim().replace(/[\s.]+$/,'')+'.':'');
    return text.length>8000?template.replace('{source}',''):text;
  }
  // A restyle that keeps the picture draws it at the source's own aspect ratio (~1.5 megapixels, multiples of the recipe grid).
  function canvasFor(source,preset){
    const cap=preset?.continuation_capability;
    if(cap?.operation!=='restyle'||!cap.keeps_picture||!preset.width||!preset.height||!(source?.width>0&&source?.height>0))return null;
    const grid=preset.dimension_multiple||16,limit=preset.dimension_limits?.[1]||1536,aspect=source.width/source.height,pixels=1.5*1024*1024;
    // Scale both axes together when the long edge would pass the recipe limit, so the aspect ratio survives the clamp.
    let width=Math.sqrt(pixels*aspect),height=Math.sqrt(pixels/aspect);const scale=Math.min(1,limit/Math.max(width,height));width*=scale;height*=scale;
    const fit=v=>Math.min(limit,Math.max(grid*4,Math.round(v/grid)*grid));
    return{width:fit(width),height:fit(height)};
  }
  function settings(preset,overrides,current){
    const protectedKeys=new Set(['positive','negative','reference','last_reference']);
    const out={...current};
    for(const [key,value]of Object.entries(preset.defaults||{}))if(!protectedKeys.has(key)&&!['width','height','seed'].includes(key))out[key]=value;
    for(const [key,value]of Object.entries(overrides||{}))if(!protectedKeys.has(key))out[key]=value;
    return out;
  }
  // Each blocker names the control it is about, in the words on screen. `code` lets the page offer the matching repair.
  function blockerItems(claim,preset,controls,parents,refs=[]){
    if(!claim)return[];
    if(!normalize(claim))return[{code:'invalid',message:'This continuation record is unreadable. Reopen Continue with this asset.'}];
    const cap=preset?.continuation_capability,items=[],add=(code,message)=>items.push({code,message});
    if(preset?.id!==claim.preset_id||!cap?.consumes_source)add('route','This recipe cannot read the source picture. Pick a source-based recipe, or leave this continuation.');
    if(cap&&(!routes[claim.intent]?.includes(cap.operation)||cap.template_sha256!==claim.template_sha256))add('graph','The recipe graph changed since the handoff. Reopen Continue with this asset.');
    if(cap?.requires_mask)add('mask','This recipe needs a repair mask, not the plain source. Prepare the RGBA mask first.');
    const filled=file=>typeof file==='string'&&!!file,missing=[];let sourceFile;
    if(sourceInput(cap)==='last_reference'){
      sourceFile=controls.last_reference;
      const pictures=refs.filter(r=>filled(r?.file)&&!r.missing).length,minimum=cap?.board_min||1;
      if(refs.some(r=>r?.missing))missing.push('A board picture is missing');
      else if(pictures<minimum)add('board',cap.operation==='combine'?'Add the picture whose pose you want to Picture 1'+boardImage(preset)+'.':'Add at least '+minimum+' picture'+(minimum===1?'':'s')+' whose look you want to the style board (Picture 1).');
    }else if(preset?.reference_slots?.length){
      sourceFile=refs[0]?.file;
      refs.forEach((r,i)=>{if(i&&(!filled(r?.file)||r.missing))missing.push('Picture '+(i+1)+' is empty');});
      if(preset.last_reference&&!filled(controls.last_reference))missing.push((preset.last_reference_label||'Last frame')+' is empty');
    }else{
      sourceFile=controls.reference;
      if(preset?.last_reference&&!filled(controls.last_reference))missing.push((preset.last_reference_label||'Last frame')+' is empty');
    }
    if(sourceFile!==claim.reference_file||!parents?.includes(claim.source_asset_id))add('source',sourceLabel(preset)+' no longer holds the picture you chose to continue. Put it back, or leave this continuation to start from another picture.');
    if(missing.length)add('inputs',missing.join('; ')+'. Attach a picture there; the recipe example cannot stand in while continuing.');
    if(preset?.positive&&!String(controls.positive||'').trim())add('wording',cap?.prompt_role==='motion'?'Describe the motion and camera movement before running.':cap?.prompt_role==='instruction'?'Say what to change and what to keep before running.':'Describe the result before running. No source description was available to copy.');
    else if(preset?.positive){
      // Prepared wording may carry bracketed placeholders (one string or a list); each one left in place is named.
      const left=unfilled(preset,controls.positive);
      if(left.length)add('wording','Fill in the wording: replace '+left.map(text=>'“'+text+'”').join(' and ')+' in the prompt.');
    }
    return items;
  }
  function blockers(claim,preset,controls,parents,refs=[]){return blockerItems(claim,preset,controls,parents,refs).map(item=>item.message);}
  function guidance(preset,source){
    const cap=preset?.continuation_capability;
    if(!cap?.consumes_source)return['This recipe does not have a verified source-to-output connection.'];
    const text=[{'image-to-image':'Resamples the attached image, rather than starting with an empty image. Identity, style and background can still drift.','localized-detail':'Detects and repaints local regions. Detection can miss a face or hand; inspect the output before accepting it.','instruction-edit':'Uses the source as visual context. Write the change you want and what should stay the same.','upscale':'Enlarges the source without a text prompt. This does not repair pose or guarantee identical fine detail.','masked-repair':'Needs a prepared RGBA PNG: transparent alpha identifies the repair region. A plain source copy is not enough.','restyle':cap.keeps_picture&&!cap.board_min?'Keeps this picture (layout, pose, costume, colours) and redraws it in the look the wording describes: the picture is the model’s own reference and there is no style board, so your words carry the look. Edit the first sentence to try another look; keep the “Keep …” sentence.':cap.keeps_picture&&cap.prompt_role==='instruction'?'Keeps this picture (layout, pose, costume) and redraws it the way the picture on the board is drawn: the wording tells the model to copy how image 2 is drawn, not what it shows. Colours can drift towards image 2; name the ones to keep.':cap.keeps_picture?'Keeps this picture (layout, pose, costume, colours; Denoise says how much may change) and repaints it in the recipe’s finish. The style board’s pictures add their palette only as far as Style weight says (0 = off). The prompt says who the character is.':'Keeps this picture’s pose and paints a new image in the look of the pictures you put on the style board. Its colours, costume and background are not copied; the prompt says who the character is.','combine':/depth map/i.test(preset.reference_board_label||'')?'Keeps this character (face, hair, outfit, colours, rendering style) and draws it in the body position of the picture you put on the board, read as a depth map: only the silhouette reaches the model, so that picture’s person, clothing, colours and background do not. A heel or a skirt in the silhouette can still shape the figure; audition three seeds.':'Keeps this character (face, hair, outfit, colours, rendering style) and draws it in the pose of the picture you put on the board. The pose is taken from that picture, not its person or colours, though a shoe or stocking from it can ghost in. The background follows the pose picture unless the wording says otherwise.','image-to-video':'Uses the source as a visual input. Describe motion, timing and camera movement; an image caption alone is not a motion brief.','image-to-3d':'Uses the source for reconstruction. Hidden surfaces are inferred; inspect the mesh and materials.'}[cap.operation]||cap.scope];
    if(cap.prompt_role==='description')text.push(source?.prompt_role==='description'&&source?.positive?'Copies this output’s actual submitted description. You may refine the description without changing the source.':'No reusable image description is available. Write one; recipe example text will stay out of the prompt.');
    if(source?.preset_id&&source.preset_id!==preset.id&&cap.prompt_role!=='none')text.push('Different source recipe: '+(source.preset_name||source.preset_id)+'. Source sampling settings, seed and adapters are not copied. Check destination style triggers; low denoise does not guarantee the same look.');
    // The owner's report (14 Sep 2026): restyling a restyle with the same wording and seed gave "the same exact image".
    else if(source?.preset_id&&source.preset_id===preset.id&&cap.prompt_role!=='none')text.push('This picture already came from this recipe. The same wording and seed give the same picture again: change the wording, or the seed, before running.');
    if(cap.operation==='combine')text.push('Your picture goes on '+sourceLabel(preset)+' and stays who it is: face, hair, outfit, colours and rendering style. After preparing, add the picture whose pose you want to Picture 1'+boardImage(preset)+'. The wording is prepared for you'+((preset?.reference_slots?.length||0)>1?'; a third picture leaks its costume unless you say exactly what to take from image 3.':'; name your character\'s clothes and colours in it or the pose picture\'s outfit leaks.'));
    else if(cap.operation==='restyle'&&!cap.board_min)text.push('Your picture goes on '+sourceLabel(preset)+'. The wording is prepared for you: the finish to draw, what to keep, and this output’s submitted description when one exists. There is no style board to fill.');
    else if(cap.operation==='restyle'&&cap.prompt_role==='instruction')text.push('Your picture goes on '+sourceLabel(preset)+' and keeps its pose, costume and layout. After preparing, add the picture drawn the way you want to Picture 1 (image 2): the wording tells the model to copy how it is drawn, not what it shows. Colours drift towards that picture; name the colours to keep in the wording.');
    else if(cap.operation==='restyle')text.push('Your picture becomes the '+(preset.last_reference_label||'pose picture').toLowerCase()+'. After preparing, add one to three pictures whose look you want to the style board.'+(cap.keeps_picture?' The finish terms and the light-novel LoRA are added to your prompt for you; eyes and lashes get a face pass with the same styled model.':' To keep the costume and background as well, choose a Restyle a picture recipe.'));
    else if(cap.reference_count>1)text.push('This attaches Picture 1 only. Add '+(cap.reference_count-1)+' more required reference(s).');
    if(preset.runtime_block)text.push(preset.runtime_block);
    return text.filter(Boolean);
  }
  function variantLabel(key){
    return({cfg:'Guidance (CFG)',seed:'Seed',width:'Canvas width',height:'Canvas height',frames:'Frames',fps:'FPS',style_weight:'Style weight',pose_strength:'Pose strength'})[key]||key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
  }
  function variantHelp(preset,variant){
    const authored=variant?.controls&&typeof variant.controls==='object'&&!Array.isArray(variant.controls)?variant.controls:{};
    const values=settings(preset,authored,{}),parts=[];
    if(values.denoise!=null){const n=Number(values.denoise);parts.push('Denoise '+values.denoise+': '+(n<=0.3?'less resampling noise; generally closer to the source':n<1?'more repainting freedom; identity and scenery may change':'full-noise resampling; not a preservation pass')+'.');}
    if(values.steps!=null)parts.push(values.steps+' sampling steps.');
    for(const [key,value]of Object.entries(authored)){
      if(['denoise','steps'].includes(key)||typeof value!=='number'||!Number.isFinite(value))continue;
      const index=['lora','lora2','lora3','lora4','lora5','lora6'].indexOf(key);
      if(index>=0){
        const name=preset.defaults?.[key+'_name'],prior=Number(preset.defaults?.[key]);
        if(value===0&&Number.isFinite(prior)&&prior!==0)parts.push('Switches off adapter '+(index+1)+(name?' ('+name+')':'')+'.');
        else parts.push('Adapter '+(index+1)+' strength '+value+(name?' ('+name+')':'')+'.');
      }else parts.push(variantLabel(key)+' '+value+'.');
    }
    return parts.join(' ')||'Applies the listed settings; inspect parameters before running.';
  }
  return{normalize,initial,settings,blockers,blockerItems,guidance,variantHelp,destinations,sourceInput,sourceLabel,promptFor,canvasFor,unfilled};
});
