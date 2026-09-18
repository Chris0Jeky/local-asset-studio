/* Presentation policy only: no network, DOM, execution or persisted mutations. */
(function(root,factory){const core=factory();if(typeof module==='object'&&module.exports)module.exports=core;else root.StudioUX=core;})(globalThis,function(){
  'use strict';
  const VIEWS=['home','create','assets','production','models','learn'];
  const ACTIVE=['queued','submitting','running','waiting','observing','rendering'];
  const ATTENTION=['failed','partial','uncertain','interrupted','stopped'];
  const INTENTS=[
    {id:'create',name:'Start with an idea',verb:'Create',hint:'Words → image',description:'Find a look. Audition a small batch.',prefer:['anima-portrait','krea-anime-atelier'],accept:p=>!p.reference&&(p.modality||'image')==='image'},
    {id:'edit',name:'Change an image',verb:'Edit',hint:'Image → variation',description:'Keep a reference. Describe what changes.',prefer:['flux-edit','qwen-1ref','krea-refine'],accept:p=>!!p.reference&&(p.modality||'image')==='image'},
    {id:'repair',name:'Refine the details',verb:'Refine',hint:'Image → refinement',description:'Revisit faces, hands, finish or resolution.',prefer:['anime-detail-fix','krea-refine','anime-esrgan'],accept:p=>!!p.reference&&(p.modality||'image')==='image'&&/repair|refine|detail|esrgan|upscale/i.test(p.id+' '+p.name)},
    {id:'restyle',name:'Borrow a look',verb:'Restyle',hint:'Image (+ style picture) → image',description:'Keep this picture, or just its pose. Repaint it in another look.',prefer:['restyle-klein','restyle-klein-picture','restyle-wai','style-pose-wai','style-pose-nova','style-pose-yumeflux'],accept:p=>(!!p.reference_board&&!!p.last_reference&&p.continuation_operation!=='combine'||p.continuation_operation==='restyle'&&!!p.reference)&&(p.modality||'image')==='image'},
    {id:'combine',name:'Combine two pictures',verb:'Combine',hint:'Image + image → image',description:'Keep this character. Take the pose from another picture.',prefer:['combine-klein-9b-depth','combine-klein-9b-copypose','combine-klein-9b-replace','combine-klein-9b','combine-klein-9b-skeleton','combine-klein'],accept:p=>p.continuation_operation==='combine'&&!!p.reference_board&&!!p.last_reference&&(p.modality||'image')==='image'},
    {id:'animate',name:'Make it move',verb:'Animate',hint:'Words / image → video',description:'Build a short motion study from a still or text.',prefer:['wan22-i2v','wan22-t2v'],accept:p=>p.modality==='video'},
    {id:'mesh',name:'Explore a 3D draft',verb:'Make 3D',hint:'Image → mesh',description:'Generate a draft to inspect and finish.',prefer:['trellis-auto-cutout'],accept:p=>p.modality==='3d'},
  ];
  const normalizeView=hash=>VIEWS.includes(String(hash||'').replace(/^#/,''))?String(hash).replace(/^#/,''):'home';
  function recipesFor(id,presets,source=false){const intent=INTENTS.find(x=>x.id===id);if(!intent)return[];const rank=p=>{const i=intent.prefer.indexOf(p.id);return i<0?100:i;};return presets.filter(p=>intent.accept(p)&&(!source||!!p.reference)).sort((a,b)=>rank(a)-rank(b)||Number(!!b.verified)-Number(!!a.verified)||a.name.localeCompare(b.name));}
  function summarize(assets=[],plans=[],jobs=[]){const retained=assets.filter(a=>!a.trashed_at);return{assets:retained.length,keepers:retained.filter(a=>a.review==='selected').length,unreviewed:retained.filter(a=>!a.review||a.review==='unreviewed').length,needsWork:retained.filter(a=>a.review==='needs_work').length,activeJobs:jobs.filter(j=>ACTIVE.includes(j.status)),activePlans:plans.filter(p=>ACTIVE.includes(p.state?.status)),reviewPlans:plans.filter(p=>p.state?.status==='awaiting_review'),attentionJobs:jobs.filter(j=>ATTENTION.includes(j.status)),attentionPlans:plans.filter(p=>ATTENTION.includes(p.state?.status)),prepared:plans.filter(p=>p.state?.status==='planned')};}
  function failureDetails(job={}){
    const raw=typeof job.message==='string'?job.message:'';
    const failure=job.failure&&typeof job.failure==='object'?job.failure:null;
    if(failure||job.status==='failed'&&/ComfyUI reported an execution error|bad allocation|out of memory|not enough memory|memory allocation|alloc(?:ation)?_failed|alloc_cpu|paging file|os error 1455/i.test(raw)){
      const memory=failure?.kind==='memory_allocation'||/bad allocation|out of memory|not enough memory|memory allocation|alloc(?:ation)?_failed|alloc_cpu|paging file|os error 1455/i.test(raw);
      const detail=typeof failure?.detail==='string'&&failure.detail?failure.detail:raw||'No engine exception detail was returned.';
      return{
        kind:failure?.kind||(memory?'memory_allocation':'execution_error'),
        title:failure?.title||(memory?'Memory allocation failed':'ComfyUI execution failed'),
        summary:failure?.summary||(memory?'ComfyUI could not allocate memory while running the workflow. This usually indicates GPU/VRAM pressure or a backend allocation problem, not an invalid prompt.':'ComfyUI reported an execution error. The recipe and prompt ID were retained so the engine detail can be investigated without resubmitting it.'),
        action:failure?.action||(memory?'Release or restart ComfyUI memory, then retry with a smaller resolution, batch, or fewer active LoRAs. The original prompt was not retried automatically.':'Check the engine detail below and retry only after correcting the reported workflow or runtime issue. The original prompt was not retried automatically.'),
        detail,
        node_type:typeof failure?.node_type==='string'?failure.node_type:'',
        node_id:typeof failure?.node_id==='string'?failure.node_id:'',
        exception_type:typeof failure?.exception_type==='string'?failure.exception_type:''
      };
    }
    return null;
  }
  // The legacy boolean/text projection and actionable UI share exactly one blocker policy.
  // Action tokens are presentation destinations, never installation or execution permissions.
  function readinessItems({preset,online,schemaAvailable,workerAlive=true,missing=[],referencesReady=true,switching=false,backend=null,busy=false,unfilled=[],sourceMissing=false}){
    const items=[],add=(code,message,action=null)=>items.push({code,message,action});
    // A recipe that transforms a picture needs that picture on every route (the server refuses the authored example too).
    if(sourceMissing)add('source','Add your picture to '+(preset?.last_reference_label||preset?.reference_label||'Picture to keep (image 1)')+'; the authored example picture is never run.','source');
    // A recipe's bracketed fills left in the wording block every route (the server refuses them too), not only a continuation.
    if(Array.isArray(unfilled)&&unfilled.length)add('wording','Fill in the wording: replace '+unfilled.map(text=>'“'+text+'”').join(' and ')+' in the prompt.','fills');
    if(!preset)add('recipe','Choose a recipe.','recipes');
    if(busy)add('busy','An attachment or submission is in progress.');
    if(switching)add('switching','The model environment is switching.','models');
    if(!workerAlive)add('worker','Studio worker is unavailable. Restart Studio; no generation can be queued safely.','models');
    if(online==null)add('health','ComfyUI readiness is not yet confirmed. Check Models & setup if the health response stays unavailable.','models');
    else if(!online)add('offline','ComfyUI is offline. Start it with the Studio launcher.','models');
    else if(!schemaAvailable)add('schema','Node readiness is not available yet.','dependencies');
    if(preset?.runtime_block)add('runtime',preset.runtime_block,'dependencies');
    if(backend&&preset&&(preset.backend_id||'primary')!==backend)add('backend','Switch explicitly to '+(preset.backend_id||'primary')+' in Models & setup.','models');
    if(missing.length)add('models','Missing requirements: '+missing.join(', '),'dependencies');
    if(!referencesReady)add('references','Attach every required reference before starting.','references');
    return items;
  }
  function readiness(options){const items=readinessItems(options);return{ready:!items.length,blockers:items.map(item=>item.message)};}

  function sceneEligibility(assets){if(!assets.length)return{ok:false,reason:'Select a PNG image or MP4 video to begin.'};if(assets.some(a=>a.trashed_at||!{image:/\.png$/i,video:/\.mp4$/i,audio:/\.wav$/i}[a.media_type]?.test(a.filename||'')))return{ok:false,reason:'Scenes accept PNG, MP4 and WAV sources. Convert other formats first.'};const visuals=assets.filter(a=>['image','video'].includes(a.media_type)).length;if(!visuals)return{ok:false,reason:'Add a PNG or MP4 in the scene picker; audio needs a visual source.'};if(visuals>16||assets.filter(a=>a.media_type==='audio').length>32)return{ok:false,reason:'Use at most 16 visuals and 32 audio sources per scene.'};return{ok:true,reason:'Timing is chosen next. The Scene editor validates source bytes and WAV format.'};}
  function normalizeDraft(value){
    if(!value||value.version!==1||!Number.isFinite(value.updatedAt)||!value.recipe||typeof value.recipe.preset!=='string'||!value.recipe.preset||value.recipe.preset.length>120)return null;
    if(JSON.stringify(value).length>131072)return null;
    const input=value.recipe.controls;if(!input||typeof input!=='object'||Array.isArray(input))return null;const controls={};
    for(const [k,v]of Object.entries(input)){if(!/^[a-z][a-z0-9_]{0,63}$/.test(k)||['constructor','prototype','__proto__'].includes(k))return null;if(!(typeof v==='string'&&v.length<=20000)&&!(typeof v==='number'&&Number.isFinite(v)))return null;controls[k]=v;}
    const ids=value.recipe.parent_assets||[],refs=value.recipe.references||[],pending=value.pendingInputs||[];
    if(!Array.isArray(ids)||ids.length>32||ids.some(x=>typeof x!=='string'||x.length>160))return null;
    if(!Array.isArray(refs)||refs.length>8||refs.some(r=>!r||typeof r!=='object'||Array.isArray(r)))return null;
    for(const r of refs){if(['__proto__','constructor','prototype'].some(k=>Object.hasOwn(r,k)))return null;if(r.file!=null&&(typeof r.file!=='string'||r.file.length>255))return null;if(r.sha256!=null&&(typeof r.sha256!=='string'||!/^[a-f0-9]{64}$/i.test(r.sha256)))return null;for(const k of ['width','height','bytes'])if(r[k]!=null&&(!Number.isSafeInteger(r[k])||r[k]<0))return null;for(const k of ['role','contribution','avoid'])if(r[k]!=null&&(typeof r[k]!=='string'||r[k].length>1500))return null;if(r.missing!=null&&typeof r.missing!=='boolean')return null;}
    if(!Array.isArray(pending)||pending.some(x=>!['reference','lastReference'].includes(x)))return null;
    // Per-input lineage attribution (#108): a known input mapped to an asset this draft already declares.
    const mapped=value.recipe.parent_by_input??{};if(!mapped||typeof mapped!=='object'||Array.isArray(mapped))return null;
    // Emitted only when something was actually attributed, so a legacy draft never freezes an empty map.
    const attribution=Object.entries(mapped);
    if(attribution.length>8||attribution.some(([k,v])=>!['reference','lastReference'].includes(k)||typeof v!=='string'||!ids.includes(v)))return null;
    const batch=Number(value.recipe.batch??1);if(!Number.isInteger(batch)||batch<1||batch>4)return null;
    const continuation=value.recipe.continuation;if(continuation!=null&&(typeof StudioContinuation==='undefined'||!StudioContinuation.normalize(continuation)||continuation.preset_id!==value.recipe.preset))return null;
    return{version:1,updatedAt:value.updatedAt,recipe:{preset:value.recipe.preset,controls,batch,...(continuation?{continuation:StudioContinuation.normalize(continuation)}:{}),parent_assets:[...ids],...(attribution.length?{parent_by_input:Object.fromEntries(attribution)}:{}),references:refs.map(r=>({...r}))},pendingInputs:[...new Set(pending)],templateHash:typeof value.templateHash==='string'?value.templateHash:null};
  }
  // Named recipes are a reading aid, never a selection: bounded, catalog-shaped ids only.
  function promptRecipes(value){const out=[];for(const id of Array.isArray(value)?value:[]){if(out.length>=8)break;if(typeof id==='string'&&/^[a-z0-9-]{1,60}$/.test(id)&&!out.includes(id))out.push(id);}return out;}
  // Why a compilation cannot be used yet, in the words the person typing actually needs.
  // Pure: no DOM, no network, no mutation. Returns [{code,message,action,detail,fix,blocking}].
  // `blocking` marks the entries that stop a transfer; `fix` names a repair the page may offer in one click.
  function promptBlockers(compilation){
    if(!compilation)return[{code:'NOT_COMPILED',message:'The prompt has not been built yet.',action:'Edit any field, or press Build the prompt.',detail:'',fix:'',blocking:true}];
    const profile=compilation.profile||{},name=profile.name||'this',intent=compilation.intent||{};
    const refs=(compilation.reference_map||intent.references||[]).length,avoid=(intent.avoid||[]).join(', ');
    const plural=(n,word)=>n+' '+word+(n===1?'':'s');
    const say={
      REFERENCE_COUNT:()=>profile.max_refs===0
        ?{message:'The '+name+' profile reads no reference images, and '+plural(refs,'reference')+' '+(refs===1?'is':'are')+' attached.',action:'Remove the reference, or switch to a profile that reads reference images.',fix:'switch-profile'}
        :refs<(profile.min_refs||0)
          ?{message:name+' needs at least '+plural(profile.min_refs,'reference image')+'; '+refs+' attached.',action:'Attach a reference under "Reference images and their roles".',fix:''}
          :{message:name+' accepts at most '+plural(profile.max_refs,'reference image')+'; '+refs+' attached.',action:'Remove the extra references, or switch to a profile that accepts '+refs+'.',fix:'switch-profile'},
      REFERENCE_KIND:()=>({message:'One of your references is not a kind this profile can read.',action:'Remove it, or switch to a profile that accepts that kind.',fix:''}),
      NEGATIVE_REWRITE_REQUIRED:()=>({message:'The '+name+' profile has no negative prompt, so "Things to avoid" cannot be sent'+(avoid?' ('+avoid+')':'')+'.',action:'Keep the words as a review note, describe the opposite in positive words, or switch to a profile that has a negative prompt.',fix:'avoid-to-note'}),
      TAGS_REQUIRED:()=>({message:'This profile reads comma-separated tags and "Approved tags" is empty. Your description is never turned into tags for you.',action:'Add the tags you approve, or switch to a description-based profile.',fix:'switch-profile'}),
      MODEL_SCORE_TOKEN_CONFLICT:()=>({message:'This profile cannot use score_* tokens from another model dialect.',action:'Remove or rewrite the score_* tokens, or switch to a profile that supports them.',fix:''}),
      MODEL_TAG_ORDER_CONFLICT:()=>({message:'This profile requires quality terms at the end of the approved tag list, but other tags follow them.',action:'Move the quality terms to the final tag group, or remove them.',fix:''}),
      PROMPT_TOO_LONG:()=>({message:'The compiled text is longer than the reviewed character budget for this profile. Nothing was shortened for you.',action:'Trim the brief, subject or style, then build again.',fix:''}),
      STRUCTURAL_CONTROL_REQUIRED:()=>({message:'A hard requirement needs a mask, guide or check — prompt text alone cannot deliver it.',action:'Make it a soft review note, or plan the extra stage in Create.',fix:''}),
      VERBATIM_UNBOUND:()=>({message:'Exact words are recorded but this profile has nowhere to put them.',action:'Switch to the voice or music profile, or clear the exact words.',fix:''}),
      NEGATIVE_UNBOUND:()=>({message:'This profile has no place for "Things to avoid".',action:'Keep them as a review note, or clear the field.',fix:'avoid-to-note'}),
      TAGS_UNBOUND:()=>({message:'This profile does not read tags; yours are kept but unused.',action:'Clear the tags, or switch to a tag-based profile.',fix:''}),
      SPEECH_TEXT_REQUIRED:()=>({message:'A voice take needs the exact words to speak, separate from the performance direction.',action:'Fill "Exact words to speak".',fix:''}),
      VOICE_LANGUAGE_UNSUPPORTED:()=>({message:'That language is outside this voice profile.',action:'Choose one of the languages this profile lists.',fix:''}),
      LYRICS_CONFLICT:()=>({message:'This is marked instrumental but lyrics are present. Nothing was deleted.',action:'Clear the instrumental flag, or move the lyrics out yourself.',fix:''}),
      METER_UNSUPPORTED:()=>({message:'That time signature has no reviewed mapping yet.',action:'Use 2/4, 3/4, 4/4 or 6/8.',fix:''}),
      MOTION_UNSPECIFIED:()=>({message:'No movement is described, and none is invented for you.',action:'Say what the subject does, what the camera does and what stays fixed.',fix:''}),
      TAG_COVERAGE_REVIEW:()=>({message:'Only your approved tags are sent. Whatever the description says beyond them is not.',action:'Compare the tags against your brief before using this.',fix:''}),
      NO_TEXT_CONDITIONING:()=>({message:'This route reads an image, not a prompt. The text you wrote is not used.',action:'Approve the input image first, or pick a text-based profile.',fix:''}),
      PARAMETER_HANDOFF:()=>({message:'A parameter you set is not part of any text prompt; the recipe in Create owns it.',action:'Set it in Create after the handoff.',fix:''}),
      ACCEPTANCE_REQUIRED:()=>({message:'A hard requirement stays a thing you check by looking; no prompt can guarantee it.',action:'Keep it on your review list.',fix:''}),
    };
    const out=[];
    for(const [list,blocking] of [[compilation.errors||[],true],[compilation.diagnostics||[],false]])
      for(const entry of list){const phrase=say[entry.code]?.()||{message:entry.message||'This profile reported an unresolved requirement.',action:'Read the compiler detail below.',fix:''};out.push({code:entry.code,message:phrase.message,action:phrase.action,detail:entry.message||'',fix:phrase.fix,blocking});}
    if(compilation.state!=='blocked'&&!promptTransfer(compilation)){
      const fields=compilation.fields||{},positive=fields.positive||fields.prompt;
      out.push(typeof positive!=='string'||!positive.trim()
        ?{code:'NO_PROMPT_TEXT',message:'This profile produces no prompt text to carry into Create.',action:'Use Export compilation instead, or choose a text-based profile.',detail:'',fix:'',blocking:true}
        :{code:'TRANSFER_TOO_LONG',message:'The compiled text is longer than the 8000-character handoff limit.',action:'Shorten the brief, then build the prompt again.',detail:'',fix:'',blocking:true});
    }
    return out;
  }
  // Text-only transfer. A compiler profile is NOT proof of executor compatibility.
  function promptTransfer(compilation){if(!compilation||compilation.state==='blocked')return null;const fields=compilation.fields||{};const positive=fields.positive||fields.prompt;if(typeof positive!=='string'||!positive.trim()||positive.length>8000||typeof fields.negative==='string'&&fields.negative.length>8000)return null;return{version:1,positive,negative:typeof fields.negative==='string'?fields.negative:'',profile:String(compilation.profile?.id||compilation.profile_id||'Prompt Lab'),recipes:promptRecipes(compilation.recipes||compilation.profile?.recipes),notice:'Text only. Choose a matching recipe and reattach required references; compiler settings are not executor bindings.'};}
  return{VIEWS,ACTIVE,ATTENTION,INTENTS,normalizeView,recipesFor,summarize,failureDetails,readiness,readinessItems,sceneEligibility,normalizeDraft,promptBlockers,promptTransfer};
});