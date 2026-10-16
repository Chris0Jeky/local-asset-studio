/* Make (owner ask, 15 Oct 2026): the goal-first way in. Pick what you are making, pick a look by its picture, type the
   scene, press Generate. A look is the existing Looks record (app/looks.py): recipe + adapters + wording with a {scene}
   slot, so the model dialect, quality tags and LoRA stack are the look's job, not the user's. Generate is the one press
   that submits (POST /api/looks/prepare, then POST /api/jobs); nothing runs on load. Picture goals stay in Make (16 Oct 2026):
   pick the picture, fill a short composer, press the same Generate; the request is the continuation the handoff prepares. */
(function(){
  'use strict';
  const view=document.querySelector('#makeView');if(!view)return;
  const q=s=>view.querySelector(s),escape=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const json=async(path,body)=>{const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(data.error||data.message||('Request failed ('+r.status+')'));return data;};
  // Curated, not generated: a goal lists looks by id in the order a newcomer should meet them (proven first, slow last).
  const GOALS=[
    {id:'character',name:'Anime character',hint:'A person or creature, drawn',looks:['look-wai-fantasy-portrait','look-anima-fantasy-portrait','look-animagine-fantasy-portrait','look-anima-painterly-artist-tags','look-pearly-anima-mix-v10-showcase','look-oneobsession-anima-v20-showcase','look-anifox-ringeko','look-anima-pearly-petiflow','look-krea-atelier-target-stack','look-krea-witch-nijisis']},
    {id:'scene',name:'Scene or background',hint:'A place, no main character',looks:['look-noob-fantasy-scene','look-night-shift-retro-anime','look-krea-watercolor-anime']},
    {id:'painting',name:'Painted illustration',hint:'Oil, ink, watercolour, book cover',looks:['look-krea-style-emerald-tarot','look-krea-oil-fantasy','look-krea-style-inkwork-darkbrush','look-krea-style-airy-softwatercolor']},
    {id:'photo',name:'Photo',hint:'Realistic people, places, products',looks:['look-preset-zimage-fast','look-preset-realvis','look-krea-realistic-snapshot','look-krea-lenovo-ultrareal']},
    {id:'game',name:'Game item or icon',hint:'Props, pixel art',looks:['look-preset-stylized-prop','look-preset-pixel-lora']},
    {id:'edit',name:'Change a picture',hint:'Keep it, change one thing',intent:'edit'},
    {id:'repair',name:'Fix or upscale',hint:'Faces, hands, resolution',intent:'repair'},
    {id:'restyle',name:'Restyle a picture',hint:'Same picture, another look',intent:'restyle'},
    {id:'combine',name:'Character in a new pose',hint:'Two pictures in, one out',intent:'combine'},
    {id:'animate',name:'Animate a picture',hint:'A short clip from a still',intent:'animate'},
    {id:'mesh',name:'Picture to 3D',hint:'A draft model to inspect',intent:'mesh'},
  ];
  const SHAPES={design:'As designed',portrait:'Portrait',landscape:'Landscape',square:'Square'};
  const FINAL=['completed','failed','partial','uncertain','not_submitted','cancelled','abandoned'];
  const POLISH={face:'Fix face',details:'Fix hands and details',upscale:'Upscale 2\u00d7'};
  const state={goal:'character',look:null,looks:null,examples:{},error:'',busy:false,status:'',runs:[],pictures:null,picking:false,review:{},polish:{},polishing:new Set(),tune:{},tuneOpen:false,pick:null,repicking:false,queries:{},form:{},fix:'face',styleLook:null,styleWords:false,poseMode:'picture',pose:null,posePicking:false,compare:false,compareLooks:[]};
  try{const saved=JSON.parse(localStorage.getItem('studio.make')||'{}');if(GOALS.some(g=>g.id===saved.goal))state.goal=saved.goal;if(typeof saved.look==='string')state.look=saved.look;}catch{}
  const remember=()=>{try{localStorage.setItem('studio.make',JSON.stringify({goal:state.goal,look:state.look,runs:(restoredRuns?state.runs:[...state.runs,...savedRuns.map(({id,...r})=>({...r,job:{id}}))]).slice(0,6).map(({job,look,lookId,goal,scene,tune,tuned,group,title})=>({id:job.id,look,lookId,goal,scene,tune,tuned,group,title}))}));}catch{}};
  let restoredRuns=false,savedRuns=[];try{const saved=JSON.parse(localStorage.getItem('studio.make')||'{}');if(Array.isArray(saved.runs))savedRuns=saved.runs.filter(r=>r&&typeof r.id==='string').slice(0,6);}catch{}
  const presets=()=>typeof catalog!=='undefined'&&catalog?.presets||[];
  const presetFor=look=>presets().find(p=>p.id===look?.body?.preset_id);
  const recipeOf=look=>{for(const l of look?.lineage||[]){const m=/^presets\/recipes\.json · (\S+)/.exec(l.evidence||'');if(m)return m[1];}return null;};
  // Preset-derived looks have no recipe example; their pictures are the 15 Oct 2026 proof renders (examples/make-looks-20261015).
  const PROOF_THUMBS=['look-preset-stylized-prop','look-preset-pixel-lora','look-preset-realvis','look-preset-zimage-fast'];
  const thumbOf=look=>{const r=recipeOf(look);return r&&state.examples[r]?.url||(look.anchor_asset_id?'/api/assets/'+encodeURIComponent(look.anchor_asset_id)+'/thumb':PROOF_THUMBS.includes(look.id)?'/api/examples/make-looks-20261015/'+look.id+'.jpg':null);};
  const tried=look=>{const r=recipeOf(look),list=typeof atelierRecipes!=='undefined'?atelierRecipes:[];return list.find(x=>x.id===r)?.status==='executed';};
  const goal=()=>GOALS.find(g=>g.id===state.goal);
  const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];
  // The look's active adapters: a strength above zero with a file. Style strength scales exactly these and nothing else.
  const adapters=look=>{const c=look?.body?.controls||{},p=presetFor(look),bound=k=>!!(p?.[k]||p?.bindings_extra?.[k]);
    return SLOTS.filter(k=>Number(c[k])>0&&(typeof c[k+'_name']==='string'&&c[k+'_name']||p&&!bound(k+'_name'))).map(k=>({key:k,name:c[k+'_name']||'built-in adapter',strength:Number(c[k])}));};
  const lookList=()=>{const g=goal();if(!g?.looks||!state.looks)return[];return g.looks.map(id=>state.looks.find(l=>l.id===id)).filter(l=>l&&!l.trashed_at);};
  const current=()=>state.looks?.find(l=>l.id===state.look&&!l.trashed_at)||null;
  // A family is named for what it means to the user: speed and the kind of picture, not the checkpoint.
  function speed(preset){const id=preset?.id||'';if(/krea/.test(id))return['slow','Finest detail · slow, about 10–17 min'];if(/zimage-fast|pixel|stylized|realvis/.test(id))return['fast','Fast'];return['fast','Fast · about half a minute'];}
  // The same runtime facts the full editor gates on (app.js globals); unknown (null) health does not block.
  function runtimeBlocker(){if(typeof backendSwitching!=='undefined'&&backendSwitching)return'A model environment switch is running. Wait for it to finish.';if(typeof workerAlive!=='undefined'&&workerAlive===false)return'The Studio worker has stopped. Restart the Studio before generating.';if(typeof online!=='undefined'&&online===false)return'ComfyUI is not reachable. Start it, then try again.';if(typeof online!=='undefined'&&online===true&&typeof schemaAvailable!=='undefined'&&!schemaAvailable)return'ComfyUI is still starting up. Try again in a moment.';return'';}
  function blocker(look,p=tunedPreset(look)){const runtime=runtimeBlocker();if(runtime)return runtime;if(look.usable===false)return look.unusable_reason||'This look cannot be used now.';if(!p)return'This look’s recipe is not in the library.';if(p.runtime_block)return p.runtime_block;const missing=typeof missingByPreset!=='undefined'&&missingByPreset[p.id];if(Array.isArray(missing)&&missing.length)return'Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first: open Models & setup.';return'';}
  const blockerMarkup=(look,text)=>escape(text).replace('Models &amp; setup','<a href="/#models?need='+escape(encodeURIComponent(tunedPreset(look)?.id||look.body.preset_id))+'">Models &amp; setup</a>');

  // Tune this look (owner ask, 16 Oct 2026): see and change the look's model, adapters, steps, negative and seed without the
  // full editor. Folded shut by default. Tuning only changes the controls Generate sends: the server's allow-list, adapter
  // inventory and ranges still decide, and nothing here submits. A tune belongs to its look and travels with each run.
  const NAMED=k=>k+'_name',bound=(p,k)=>!!(p?.[k]||p?.bindings_extra?.[k]),byId=id=>presets().find(p=>p.id===id);
  const kb=()=>typeof knowledge!=='undefined'&&knowledge||{},entry=name=>name&&kb().loras?.[name]||null;
  const family=p=>p?.family||p?.name||p?.id||'';
  const short=name=>entry(name)?.label||String(name||'built-in adapter').replace(/\.safetensors$/,'');
  // Same model type = same loader node and text encoders on the same backend (app/looks.py model_of): the look's wording and
  // adapters carry over, so a switch never meets a graph that cannot take them; results will still differ. A recipe whose
  // adapter file is fixed in its graph (a strength binding with no filename binding) offers no switch: that file cannot move.
  const kind=p=>p?.model?[p.model.loader,...p.model.encoders,p.backend_id||'primary'].join('|'):null;
  const textOnly=p=>(p.modality||'image')==='image'&&!!p.positive&&!p.reference&&!p.last_reference&&!p.reference_slots;
  function models(look){
    const p=presetFor(look),k=kind(p);if(!k||SLOTS.some(s=>bound(p,s)&&!bound(p,NAMED(s))))return[];const c=look.body.controls||{},seen=new Set([p.model.file]);
    const need=[...Object.keys(c),...(look.body.negative?['negative']:[]),...SLOTS.flatMap(s=>[s,NAMED(s)]).filter(s=>bound(p,s))];
    const offers=(r,key)=>!(key in c)||!r.choices?.[key]?.length||r.choices[key].includes(c[key])||!p.choices?.[key]?.includes(c[key]);
    return presets().filter(r=>r!==p&&r.family&&textOnly(r)&&kind(r)===k&&need.every(n=>bound(r,n))&&offers(r,'sampler')&&offers(r,'scheduler')&&!seen.has(r.model.file)&&seen.add(r.model.file));
  }
  const missingFor=p=>{const m=typeof missingByPreset!=='undefined'&&missingByPreset[p?.id];return Array.isArray(m)?m:[];};
  const tunedPreset=look=>byId(state.tune[look?.id]?.preset)||presetFor(look);
  function tuneOf(look){
    if(state.tune[look.id])return state.tune[look.id];const p=presetFor(look),c=look.body.controls||{};
    return state.tune[look.id]={preset:p?.id,rows:adapters(look).map(a=>({slot:a.key,name:bound(p,NAMED(a.key))?c[NAMED(a.key)]:'',strength:a.strength,on:true})),cleared:[],steps:null,sampler:'',negative:null,seed:null,reseed:true};
  }
  // Installed adapters made for this model type: the knowledge base names each file's family; a file it does not know is not offered.
  function compatible(look){
    const p=presetFor(look),k=kind(p),chosen=SLOTS.map(s=>p?.choices?.[NAMED(s)]).find(x=>x?.length),files=chosen||(typeof installedLoras!=='undefined'?installedLoras:[]);
    const kinds=new Set(presets().filter(r=>r.family&&kind(r)===k).map(r=>r.family));
    return files.filter(f=>entry(f)&&kinds.has(entry(f).family)).sort((a,b)=>(entry(b).family===p.family)-(entry(a).family===p.family)||short(a).localeCompare(short(b)));
  }
  const freeSlot=(look,t)=>SLOTS.find(s=>bound(presetFor(look),s)&&bound(presetFor(look),NAMED(s))&&!t.rows.some(r=>r.slot===s));
  const clamp=v=>Math.min(2,Math.max(0,Math.round((Number(v)||0)*20)/20));
  function tuneSummary(look,t){
    const p=presetFor(look),base=Object.fromEntries(adapters(look).map(a=>[a.key,a])),parts=[];if(!t)return'';
    if(t.preset&&t.preset!==p?.id)parts.push('model '+family(byId(t.preset)));
    for(const r of t.rows){const a=base[r.slot];if(!a||(r.name&&r.name!==a.name))parts.push('+'+short(r.name)+(r.on?' '+r.strength:' off'));else if(!r.on)parts.push(short(a.name)+' off');else if(r.strength!==a.strength)parts.push(short(a.name)+' '+r.strength);}
    for(const a of Object.values(base))if(!t.rows.some(r=>r.slot===a.key))parts.push('−'+short(a.name));
    if(t.steps!=null)parts.push(t.steps+' steps');if(t.sampler)parts.push(t.sampler);if(t.negative!=null)parts.push('own negative');if(!t.reseed&&t.seed!=null)parts.push('seed '+t.seed+' locked');
    return parts.length?'Tuned: '+parts.join(' · '):'';
  }
  // The tune applied to the prepared controls. Every bound slot of a switched model is written (off or empty is 0), so the
  // other recipe never keeps an authored adapter of its own; on the look's own model only changed slots are written.
  function applyTune(controls,look,t,scale){
    const p=presetFor(look),tp=byId(t.preset)||p,switched=tp!==p;
    for(const s of SLOTS){if(!bound(tp,s))continue;const r=t.rows.find(x=>x.slot===s);
      if(r){controls[s]=r.on?Math.min(2,Math.round(r.strength*scale*100)/100):0;if(r.name&&bound(tp,NAMED(s)))controls[NAMED(s)]=r.name;}
      else if(switched||t.cleared.includes(s))controls[s]=0;}
    if(t.steps!=null&&bound(tp,'steps'))controls.steps=t.steps;
    if(t.sampler&&bound(tp,'sampler'))controls.sampler=t.sampler;
    if(t.negative!=null&&bound(tp,'negative'))controls.negative=t.negative;
    // A trigger word is written only for an adapter you added: the look's own wording already speaks for its own adapters.
    if(typeof controls.positive==='string')for(const r of t.rows){const e=entry(r.name);if(!r.added||!r.on||!e?.trigger||controls.positive.toLowerCase().includes(e.trigger.toLowerCase()))continue;
      controls.positive=e.trigger_position==='start'?e.trigger+', '+controls.positive:controls.positive+', '+e.trigger;}
    return tp.id;
  }
  function renderTune(){
    const look=current(),box=q('#makeTuneBody');if(!look||!box)return;const t=tuneOf(look),p=presetFor(look),tp=tunedPreset(look),c=look.body.controls||{};
    const list=models(look),missing=missingFor(tp),files=compatible(look),slot=freeSlot(look,t),steps=Number(c.steps||tp?.defaults?.steps)||0;
    const draft=Math.max(1,Math.round(steps/2)),fine=Math.min(150,Math.round(steps*1.5));
    const option=(value,label,on)=>'<option value="'+escape(value)+'"'+(on?' selected':'')+'>'+escape(label)+'</option>';
    const row=r=>{const e=entry(r.name),why=e?.trigger?'Trigger: '+e.trigger+(r.added?' (added to your words)':''):r.name?'No trigger word':'Fixed in this recipe';
      return '<div class="make-tune-row" data-slot="'+r.slot+'"><label class="make-check"><input type="checkbox" data-tune-on="'+r.slot+'"'+(r.on?' checked':'')+'> <b>'+escape(short(r.name))+'</b></label>'
        +'<span class="make-tune-strength"><input type="range" min="0" max="2" step="0.05" value="'+r.strength+'" data-tune-strength="'+r.slot+'" aria-label="Strength of '+escape(short(r.name))+'"><output>'+r.strength.toFixed(2)+'</output></span>'
        +(r.name?'<button type="button" class="make-link" data-tune-remove="'+r.slot+'">Remove</button>':'')+'<small>'+escape(why)+'</small></div>';};
    box.innerHTML='<div class="make-tune-group"><h3>Model</h3>'
      +'<label>Base model<select id="makeModel" data-tune="model">'+option(p.id,'As made · '+family(p)+(missingFor(p).length?' · needs download':''),tp===p)+list.map(m=>option(m.id,family(m)+(missingFor(m).length?' · needs download':''),tp===m)).join('')+'</select></label>'
      +'<small class="muted">'+escape(tp?.model?.file||tp?.name||'')+(list.length?' · Same model type: the look’s words and adapters carry over; pictures will differ.':' · No other model in the library takes this look’s words and adapters.')+'</small>'
      +(missing.length?'<p class="make-warn" id="makeTuneWhy">Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first. <a href="/#models?need='+escape(encodeURIComponent(tp.id))+'">Open Models & setup</a></p>':'')+'</div>'
      +'<div class="make-tune-group"><h3>Adapters (LoRAs)</h3>'+(t.rows.length?t.rows.map(row).join(''):'<p class="muted">None: the model and the words carry this look.</p>')
      +(SLOTS.some(s=>bound(p,NAMED(s)))?(files.length?'<div class="make-tune-add"><label for="makeLoraSearch">Add an installed adapter</label><input id="makeLoraSearch" list="makeLoraList" placeholder="Search by name" autocomplete="off"'+(slot?'':' disabled aria-describedby="makeLoraFull"')+'><datalist id="makeLoraList">'+files.filter(f=>!t.rows.some(r=>r.name===f)).map(f=>'<option value="'+escape(f)+'">'+escape(short(f)+' · '+entry(f).family)+'</option>').join('')+'</datalist><button type="button" data-tune-add'+(slot?'':' disabled')+'>Add</button>'
        +(slot?'':'<small id="makeLoraFull">All adapter slots of this recipe are in use; remove one first.</small>')+'</div>':'<p class="muted">No installed adapter is known to fit this model type. Models & setup lists what can be installed.</p>'):'<p class="muted">This recipe has no adapter slots to fill.</p>')+'</div>'
      +((bound(tp,'steps')&&steps)||(bound(tp,'sampler')&&tp.choices?.sampler?.length)?'<div class="make-tune-group"><h3>Quality and speed</h3><div class="make-pair">'
        +(bound(tp,'steps')&&steps?'<label>Steps<select data-tune="steps">'+option('','As made · '+steps,t.steps==null)+option(draft,'Draft · '+draft+', faster',t.steps===draft)+option(fine,'Finer · '+fine+', slower',t.steps===fine)+'</select></label>':'')
        +(bound(tp,'sampler')&&tp.choices?.sampler?.length?'<label>Sampler<select data-tune="sampler">'+option('','As made'+(c.sampler?' · '+c.sampler:''),!t.sampler)+tp.choices.sampler.filter(s=>s!==c.sampler).map(s=>option(s,s,t.sampler===s)).join('')+'</select></label>':'')+'</div></div>':'')
      +(bound(tp,'negative')?'<div class="make-tune-group"><h3>Leave out</h3><textarea id="makeNegative" data-tune="negative" rows="2" maxlength="4000" aria-label="Negative prompt: things to leave out" placeholder="Things to keep out of the picture">'+escape(t.negative??look.body.negative??'')+'</textarea></div>':'')
      +(bound(tp,'seed')?'<div class="make-tune-group"><label>Seed<input type="number" id="makeSeed" data-tune="seed" min="0" max="2147483646" step="1" inputmode="numeric" value="'+escape(t.seed??c.seed??'')+'"'+(t.reseed?' disabled':'')+' aria-describedby="makeSeedHint"></label><small id="makeSeedHint" class="muted">'+(t.reseed?'Turn off “Different pictures each time” to lock this seed.':'Locked: every run starts from this seed.')+'</small></div>':'')
      +'<button type="button" class="make-link" data-tune-reset>Back to the look as made</button>';
    tuneChanged(false);
  }
  // A tune change redraws only the summary, Generate's readiness and the estimate, so the scene being typed is never disturbed.
  function tuneChanged(redraw=true){
    const look=current();if(!look)return;if(redraw){renderTune();return;}
    const sum=q('#makeTuneSum'),why=blocker(look),button=q('#makeGenerate');if(sum)sum.textContent=tuneSummary(look,state.tune[look.id])||'Model, adapters, steps, seed';
    if(button&&!state.busy){button.disabled=!!why;button.title=why;}const said=q('#makeWhy');if(said){said.innerHTML=blockerMarkup(look,why);said.hidden=!why;}estimate();
  }
  function tuneInput(target){
    const look=current();if(!look)return false;const t=tuneOf(look),row=s=>t.rows.find(r=>r.slot===s);
    if(target.dataset.tuneOn){row(target.dataset.tuneOn).on=target.checked;tuneChanged(false);return true;}
    if(target.dataset.tuneStrength){const r=row(target.dataset.tuneStrength);r.strength=clamp(target.value);target.nextElementSibling.textContent=r.strength.toFixed(2);tuneChanged(false);return true;}
    const key=target.dataset.tune;if(!key)return false;
    if(key==='model'){t.preset=target.value;const tp=tunedPreset(look);if(t.sampler&&!tp.choices?.sampler?.includes(t.sampler))t.sampler='';tuneChanged();return true;}
    if(key==='steps')t.steps=target.value?Number(target.value):null;
    if(key==='sampler')t.sampler=target.value;
    if(key==='negative')t.negative=target.value===(look.body.negative||'')?null:target.value;
    if(key==='seed')t.seed=target.value===''?null:Number(target.value);
    tuneChanged(false);return true;
  }
  function tuneClick(target){
    const look=current();if(!look)return false;
    const remove=target.closest('[data-tune-remove]');if(remove){const t=tuneOf(look),s=remove.dataset.tuneRemove;t.rows=t.rows.filter(r=>r.slot!==s);if(!t.cleared.includes(s))t.cleared.push(s);tuneChanged();q('#makeLoraSearch')?.focus();return true;}
    if(target.closest('[data-tune-add]')){const t=tuneOf(look),input=q('#makeLoraSearch'),name=input?.value.trim(),slot=freeSlot(look,t);
      if(!compatible(look).includes(name)){say(name?'Choose an adapter from the list: '+name+' is not an installed adapter for this model type.':'Type part of an adapter name, then choose it from the list.');input?.focus();return true;}
      if(!slot||t.rows.some(r=>r.name===name))return true;
      t.rows.push({slot,name,strength:clamp(entry(name)?.default??1),on:true,added:true});t.cleared=t.cleared.filter(s=>s!==slot);tuneChanged();q('[data-tune-strength="'+slot+'"]')?.focus();return true;}
    if(target.closest('[data-tune-reset]')){const reseed=state.tune[look.id]?.reseed??true;delete state.tune[look.id];tuneOf(look).reseed=reseed;tuneChanged();return true;}
    return false;
  }

  view.innerHTML='<div class="make-heading"><span class="eyebrow">MAKE</span><h1 id="makeTitle" tabindex="-1">What are you making?</h1><p>Pick a goal, pick a look by its picture, describe your idea. The look brings the right model, adapters and settings.</p></div>'
    +'<div class="make-goals" role="radiogroup" aria-labelledby="makeTitle" id="makeGoals"></div>'
    +'<p id="makeStatus" class="make-status" role="status"></p>'
    +'<div id="makeSplit" class="make-split"><div id="makeBody"></div><section class="make-runs" aria-labelledby="makeRunsTitle"><div class="section-title"><h2 id="makeRunsTitle">Your pictures</h2><a href="/#assets">Open the library ↗</a></div><div id="makeRuns" class="make-run-list" aria-live="polite" aria-relevant="additions text"></div></section></div>'
    +'<p class="make-advanced">Need every setting? <a href="/#create">Open the full editor</a> · <a href="/prompt-lab.html">Prompt Lab</a> · <a href="/#production">Compare settings side by side</a></p>';

  function renderGoals(){
    q('#makeGoals').innerHTML=GOALS.map((g,i)=>(i===5?'<span class="make-goal-break">From a picture you have</span>':'')+'<button type="button" role="radio" tabindex="'+(g.id===state.goal?'0':'-1')+'" aria-checked="'+(g.id===state.goal)+'" data-make-goal="'+g.id+'"><b>'+escape(g.name)+'</b><small>'+escape(g.hint)+'</small></button>').join('');
  }
  // Once a look is chosen the gallery folds to one line and the results sit beside the words, so Generate and its pictures share a screen.
  function layout(){const focused=!goal().intent&&!!current()&&!state.picking&&!state.compare;q('#makeSplit').classList.toggle('make-has-look',focused);view.classList.toggle('make-focused',focused);}
  function render(){renderGoals();const g=goal();if(g.intent)renderPictures(g);else renderLooks();renderRuns();layout();}
  function renderLooks(){
    const body=q('#makeBody');
    if(state.error){body.innerHTML='<p class="make-error" role="alert">'+escape(state.error)+' <button type="button" data-make-retry>Try again</button></p>';return;}
    if(!state.looks){body.innerHTML='<p class="muted">Loading looks…</p>';return;}
    const list=lookList();if(!list.some(l=>l.id===state.look))state.look=null;
    // Compare looks (#16) turns the gallery into checkboxes: two or three looks, one scene, one picture each.
    const compare=state.compare;if(compare)state.compareLooks=state.compareLooks.filter(id=>list.some(l=>l.id===id));
    const on=l=>compare?state.compareLooks.includes(l.id):l.id===state.look;
    const cards=list.map(l=>{const p=presetFor(l),[pace,label]=speed(p),thumb=thumbOf(l),why=compare?blocker(l,p):blocker(l);return '<article class="make-look'+(on(l)?' active':'')+'"><button type="button" class="make-look-select" data-make-look="'+escape(l.id)+'" role="'+(compare?'checkbox':'radio')+'" tabindex="'+(compare||l.id===(state.look||list[0]?.id)?'0':'-1')+'" aria-checked="'+on(l)+'">'
      +(thumb?'<img src="'+escape(thumb)+'" alt="" loading="lazy">':'<span class="make-look-blank" aria-hidden="true">✦</span>')
      +'<span class="make-look-text"><b>'+escape(l.name)+'</b><small class="make-pace '+pace+'">'+escape(label)+'</small>'+(tried(l)?'<small>Run on this PC before</small>':'')+'</span></button>'+(why?'<small class="make-warn make-look-text">'+blockerMarkup(l,why)+'</small>':'')+'</article>';}).join('');
    const chosen=current();
    if(chosen&&!state.picking&&!compare){const p=presetFor(chosen),thumb=thumbOf(chosen);
      body.innerHTML='<div class="make-chosen">'+(thumb?'<img src="'+escape(thumb)+'" alt="">':'<span class="make-look-blank" aria-hidden="true">✦</span>')+'<div><small>Look</small><b>'+escape(chosen.name)+'</b><small class="make-pace '+speed(p)[0]+'">'+escape(speed(p)[1])+'</small></div><button type="button" data-make-change>Change look</button></div><div id="makeComposer"></div>';}
    else body.innerHTML='<div class="make-step"><span>1</span><h2>'+(compare?'Choose two or three looks to compare':'Choose a look')+'</h2>'+(chosen&&!compare?'<button type="button" class="make-link" data-make-keep-look>Keep '+escape(chosen.name)+'</button>':'')+(list.length>1?'<button type="button" class="make-link" data-make-compare aria-pressed="'+compare+'">'+(compare?'Back to one look':'Compare looks')+'</button>':'')+'</div><div class="make-looks" role="'+(compare?'group':'radiogroup')+'" aria-label="'+(compare?'Looks to compare':'Look')+'">'+cards+'</div><div id="makeComposer"></div>';
    renderComposer();layout();
  }
  function shapeSize(preset,look,shape){
    const w=Number(look.body.controls.width||preset?.defaults?.width||1024),h=Number(look.body.controls.height||preset?.defaults?.height||1024),grid=preset?.dimension_multiple||64,round=v=>Math.max(grid,Math.round(v/grid)*grid);
    if(shape==='design')return[w,h];const area=w*h,long=Math.max(w,h),short=Math.min(w,h);
    if(shape==='square'){const s=round(Math.sqrt(area));return[s,s];}
    if(long===short){const a=round(Math.sqrt(area*1.5)),b=round(Math.sqrt(area/1.5));return shape==='portrait'?[b,a]:[a,b];}
    return shape==='portrait'?[short,long]:[long,short];
  }
  function renderComposer(){
    const box=q('#makeComposer'),look=current();if(!box)return;if(state.compare){renderCompareComposer();return;}
    if(!look){box.innerHTML='<p class="make-hint">Choose a look above. Each picture is one real run of that look on this PC; yours will differ.</p>';return;}
    // A slow look starts at one picture: four Krea pictures are about forty minutes, which nobody should get by default.
    const p=presetFor(look),why=blocker(look),example=look.body.scene_example||'',options=look.body.options||[],slow=speed(p)[0]==='slow';
    box.innerHTML='<div class="make-step"><span>2</span><h2>Describe your picture</h2></div><div class="make-composer"><div class="make-compose-main">'
      +'<label for="makeScene">'+escape(state.goal==='scene'?'Where is it, and what is there?':state.goal==='game'?'What is the item?':'Who or what, doing what, where?')+'</label>'
      +'<textarea id="makeScene" rows="3" maxlength="1000" placeholder="'+escape(example)+'"></textarea>'
      +'<div class="make-row">'+(example?'<button type="button" id="makeUseExample">Use the example</button>':'')+'<small>Plain words are fine. The look adds its own style and quality words.</small></div>'
      +options.map(o=>'<label class="make-check"><input type="checkbox" data-make-option="'+escape(o.id)+'"'+(o.default?' checked':'')+'> '+escape(o.label)+'</label>').join('')
      +'<details class="make-tune" id="makeTune"'+(state.tuneOpen?' open':'')+'><summary>Tune this look <small id="makeTuneSum"></small></summary><div id="makeTuneBody"></div></details>'
      +'</div><div class="make-compose-side">'
      +'<div class="make-pair"><label>Shape<select id="makeShape">'+Object.entries(SHAPES).map(([k,v])=>'<option value="'+k+'">'+v+(k==='design'?' · '+escape(look.body.controls.width||'')+'×'+escape(look.body.controls.height||''):'')+'</option>').join('')+'</select></label>'
      +'<label>How many<select id="makeCount"><option value="1"'+(slow?' selected':'')+'>1 picture</option><option value="2">2 pictures</option><option value="4"'+(slow?'':' selected')+'>4 to choose from</option></select></label></div>'
      +(adapters(look).length?'<label>Style strength <output id="makeStrengthOut">100%</output><input type="range" id="makeStrength" min="0" max="150" step="10" value="100" aria-describedby="makeStrengthHint"><small id="makeStrengthHint" class="muted">How strongly the look\u2019s '+adapters(look).length+' style adapter'+(adapters(look).length>1?'s apply':' applies')+'. 100% is the look as made.</small></label>':'')
      +'<label class="make-check"><input type="checkbox" id="makeNewSeed"'+(tuneOf(look).reseed?' checked':'')+'> Different pictures each time</label>'
      +'<div class="make-go"><button type="button" id="makeGenerate" class="primary"'+(why?' disabled aria-describedby="makeWhy"':'')+'>Generate</button>'
      +'<p id="makeEstimate" class="muted" aria-live="polite"></p>'
      +(why?'<p id="makeWhy" class="make-warn">'+blockerMarkup(look,why)+'</p>':'')+'</div>'
      +'<button type="button" id="makeEditor" class="make-link">Open in the full editor instead</button>'
      +'<details class="make-about"><summary>What this look uses</summary><p><b>Model:</b> '+escape(family(p)||look.body.preset_id)+(p?.model?.file?' <small class="muted">'+escape(p.model.file)+'</small>':'')+'</p>'
      +(adapters(look).length?'<p><b>Adapters:</b></p><ul>'+adapters(look).map(a=>'<li>'+escape(short(a.name==='built-in adapter'?'':a.name))+' at '+escape(a.strength)+(entry(a.name)?.trigger?' \u00b7 trigger <code>'+escape(entry(a.name).trigger)+'</code>':'')+'</li>').join('')+'</ul>':'<p>No style adapters: the model and the wording carry this look.</p>')
      +(example?'<p><b>Example:</b> '+escape(example)+'</p>':'')
      +(look.body.notes?'<details class="make-maint"><summary>Details for maintainers</summary><p class="muted">'+escape(look.body.notes)+'</p></details>':'')+'</details>'
      +'</div></div>';
    syncOperation();
    const scene=q('#makeScene');try{scene.value=sessionStorage.getItem('studio.make.scene.'+state.goal)||'';}catch{}
    scene.oninput=()=>{scene.removeAttribute('aria-invalid');scene.removeAttribute('aria-describedby');try{sessionStorage.setItem('studio.make.scene.'+state.goal,scene.value);}catch{}};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    q('#makeShape').onchange=q('#makeCount').onchange=()=>estimate();estimate();
    const strength=q('#makeStrength');if(strength)strength.oninput=()=>{q('#makeStrengthOut').textContent=strength.value+'%';};
    q('#makeNewSeed').onchange=e=>{tuneOf(look).reseed=e.target.checked;tuneChanged();};
    q('#makeTune').ontoggle=e=>{state.tuneOpen=e.target.open;};
    const kept=state.tune[look.id]?.composer;if(kept){delete state.tune[look.id].composer;
      const set=(el,v)=>{if(el&&v!=null&&[...(el.options||[{value:String(v)}])].some(o=>o.value===String(v)))el.value=String(v);};set(q('#makeShape'),kept.shape);set(q('#makeCount'),kept.count);
      if(strength&&kept.strength!=null){strength.value=kept.strength;strength.oninput();}
      for(const box of view.querySelectorAll('[data-make-option]'))if(typeof kept.options?.[box.dataset.makeOption]==='boolean')box.checked=kept.options[box.dataset.makeOption];
      say('That run\u2019s settings are back'+(tuneOf(look).reseed?'':', with its seed locked')+'. Change the words or a setting, then press Generate.');estimate();}
    renderTune();
  }
  async function prepared(look){
    // Every form value is read before the first await: a click on another look mid-request must not change this one.
    const field=q('#makeScene'),scene=field.value.trim();if(!scene){field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby','makeStatus');field.focus();throw Error('Describe your picture first, or press Use the example.');}
    const options=Object.fromEntries([...view.querySelectorAll('[data-make-option]')].map(i=>[i.dataset.makeOption,i.checked]));
    const shape=q('#makeShape').value,strength=q('#makeStrength')?.value??null,p=presetFor(look),[w,h]=shapeSize(p,look,shape),reseed=q('#makeNewSeed').checked,batch_count=Number(q('#makeCount').value),scale=Number(strength??100)/100;
    const t={...structuredClone(tuneOf(look)),reseed};if(!reseed&&t.seed!=null&&!(Number.isSafeInteger(t.seed)&&t.seed>=0))throw Error('The seed must be a whole number, 0 or more.');
    const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options}:{}),expected_revision:look.revision});
    const controls={...result.controls};
    if('width' in controls||p?.width)Object.assign(controls,{width:w,height:h});
    if(reseed&&(p?.seed||p?.bindings_extra?.seed))controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
    else if(t.seed!=null&&(p?.seed||p?.bindings_extra?.seed))controls.seed=t.seed;
    // Style strength scales the tuned adapters; two decimals, inside the server's 0-2 adapter range.
    const preset_id=applyTune(controls,look,t,scale),tuned=tuneSummary(look,t);
    // The run keeps its own settings, seed locked, so Edit and re-run changes only what you change next.
    const composer={shape,count:batch_count,strength,options};
    return{preset_id,controls,batch_count,scene,tuned,tune:{...t,reseed:controls.seed==null&&t.reseed,seed:controls.seed??t.seed,composer}};
  }
  let estimateEpoch=0;
  async function estimate(retry=false){
    const look=current(),out=q('#makeEstimate');if(!look||!out)return;const epoch=++estimateEpoch,p=presetFor(look),[w,h]=shapeSize(p,look,q('#makeShape').value),t=state.tune[look.id];
    try{const e=await json('/api/estimate',{preset_id:tunedPreset(look).id,controls:{...look.body.controls,width:w,height:h,...(t?.steps!=null?{steps:t.steps}:{})},batch_count:Number(q('#makeCount').value),reference_count:0});if(epoch!==estimateEpoch||!out.isConnected)return;
      out.classList.toggle('make-warn',e.estimate_seconds>600);out.textContent=e.estimate_seconds?'About '+duration(e.estimate_seconds)+' in total, from earlier runs on this PC.':'No timing yet: this look has not run here at this size.';}
    catch{if(epoch===estimateEpoch&&!retry)setTimeout(()=>{if(epoch===estimateEpoch)estimate(true);},1500);}
  }
  const duration=s=>s<90?Math.round(s)+' s':Math.round(s/60)+' min';
  function syncOperation(){
    q('#makeStatus').textContent=state.status;
    const g=goal(),why=g.intent?goalBlocker(g,goalRoute(g)):state.compare?compareBlocker():current()&&blocker(current());
    const generate=q('#makeGenerate'),editor=q('#makeEditor');if(generate)generate.disabled=state.busy||!!why;if(editor)editor.disabled=state.busy;
  }
  const say=text=>{state.status=text;syncOperation();};
  async function generate(){
    const look=current(),runGoal=state.goal;if(!look||state.busy)return;
    const why=blocker(look);if(why){say(why);return;}
    state.busy=true;say('Preparing\u2026');
    try{
      const request=await prepared(look);say('Sending to ComfyUI…');
      const {scene,tune,tuned,...submit}=request;const job=await json('/api/jobs',{...submit,label:'Make · '+look.name});
      state.runs.unshift({job,look:look.name,lookId:look.id,goal:runGoal,scene,tune,tuned});remember();say('Started. Your pictures appear below as they finish; you can leave this page.');
      renderRuns();poll(job.id);
      if(typeof refresh==='function')void refresh();
    }catch(error){say(error.message);}
    finally{state.busy=false;syncOperation();}
  }
  async function openInEditor(){
    const look=current();if(!look||state.busy)return;
    state.busy=true;say('Preparing…');
    try{const request=await prepared(look);applySaved({preset:request.preset_id,controls:request.controls,batch_count:request.batch_count,parent_assets:[],references:[]},{});showView('create');say('Ready in the full editor.');}
    catch(error){say(error.message);}
    finally{state.busy=false;syncOperation();}
  }
  // Keep / Not this: the library's own review field, one press, pressing again clears it.
  // Keep / Not this: the library's own review field. Saves run one after another (the library takes one command at a
  // time), and pressing the recorded decision again clears it, decided from the refreshed record, not page memory.
  let reviewQueue=Promise.resolve();
  function review(button){button.disabled=true;reviewQueue=reviewQueue.then(()=>saveReview(button));return reviewQueue;}
  async function saveReview(button){
    const id=button.dataset.asset,status=q('#makeStatus');
    try{if(await refreshAssets(true)===false){await new Promise(r=>setTimeout(r,600));await refreshAssets(true);}
      delete state.review[id];const value=reviewOf(id)===button.dataset.makeReview?'unreviewed':button.dataset.makeReview;
      await mutateAssets({action:'edit',ids:[id],review:value});state.review[id]=value;renderRuns();
      if(status)say(value==='selected'?'Kept. Your keepers are in the library under Keepers.':value==='rejected'?'Marked: not this one.':'Decision cleared.');}
    catch(error){button.disabled=false;if(status)say('Could not save that: '+error.message);}
  }
  const reviewOf=id=>state.review[id]??(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===id)?.review)??'unreviewed';
  const timers=new Map();
  const stamp=job=>job.status+'|'+(job.outputs||[]).map(o=>o.asset_id||'').join(',')+'|'+(job.message||'');
  function poll(id,misses=0){clearTimeout(timers.get(id));timers.set(id,setTimeout(async()=>{
    const run=state.runs.find(r=>r.job.id===id);if(!run){timers.delete(id);return;}
    try{const job=await json('/api/jobs/'+encodeURIComponent(id));const changed=stamp(job)!==stamp(run.job);run.job=job;
      // Redraw only when something changed, so a poll never resets an open menu or steals keyboard focus.
      if(changed){renderRuns();if(job.outputs?.length)state.pictures=null;}
      if(!FINAL.includes(job.status))poll(id);else timers.delete(id);}
    catch{if(misses<5)poll(id,misses+1);else timers.delete(id);}},2500));}
  function words(job){return({queued:'Waiting its turn',waiting:'Waiting for memory',submitting:'Sending',running:'Painting',observing:'Painting',completed:'Done',failed:'Did not finish',partial:'Some pictures did not finish',uncertain:'Outcome unknown: check Runs & review',cancelled:'Cancelled',not_submitted:'Not sent'})[job.status]||job.status;}
  const marks=a=>{const review=reviewOf(a),mark=(value,label)=>'<button type="button" data-make-review="'+value+'" data-asset="'+escape(a)+'" aria-pressed="'+(review===value)+'">'+(review===value?'✓ '+(value==='selected'?'Kept':'Marked: not this'):label)+'</button>';return mark('selected','★ Keep')+mark('rejected','Not this');};
  function actions(job,output){
    const a=output.asset_id;if(!a)return'<small class="muted">Saving to the library…</small>';
    const varyBox=document.createElement('div');varyBox.innerHTML=window.StudioWorkbench?.varyMarkup?.(job.preset_id,job.id,a)||'';
    if(varyBox.querySelector('button:disabled'))varyBox.innerHTML='';else for(const hint of varyBox.querySelectorAll('small[id]'))hint.textContent='Prepare variations in the full editor; Generate there starts them.';const vary=varyBox.innerHTML;
    // Next steps open Make's own picture goals with this picture chosen; other fixes still go through the full handoff.
    const hand=(intent,label)=>'<button type="button" data-ux-handoff="'+escape(a)+'" data-ux-handoff-intent="'+intent+'">'+label+'</button>',from=(intent,label)=>'<button type="button" data-make-from="'+intent+'" data-asset="'+escape(a)+'">'+label+'</button>';
    const polish=kind=>{const plan=state.polish[a+':'+kind],why=plan&&!plan.ok?plan.reason:'',busy=state.polishing.has(a+':'+kind);
      if(why)return'';return '<button type="button" data-make-polish="'+kind+'" data-asset="'+escape(a)+'"'+(busy?' disabled':'')+'>'+POLISH[kind]+(plan?.seconds?' <small>~'+duration(plan.seconds)+'</small>':'')+(busy?' …':'')+'</button>';};
    return '<div class="make-actions">'+marks(a)+vary+polish('face')+polish('details')+polish('upscale')+(Object.keys(POLISH).some(k=>state.polishing.has(a+':'+k))?'<small class="make-action-reason">Starting the finishing pass for this picture. Please wait.</small>':'')
      +'<details class="make-more" data-more="'+escape(a)+'"><summary>More</summary><button type="button" data-ux-open-asset="'+escape(a)+'">Open full size</button>'+hand('repair','Other fixes\u2026')+from('edit','Change one thing')+from('restyle','Restyle')+from('combine','Put in a new pose')+from('animate','Animate')+from('mesh','Make it 3D')+'</details></div>';
  }
  // Polish plans only read (studio-workbench.js polishPlan); each picture is asked once per kind.
  const planning=new Set();
  function planPolish(list){
    const api=window.StudioWorkbench;if(!api?.polishPlan)return;
    for(const {job} of list)for(const o of job.outputs||[])if(o.asset_id&&picture(o))for(const kind of Object.keys(POLISH)){
      const key=o.asset_id+':'+kind;if(planning.has(key))continue;planning.add(key);
      api.polishPlan(o.asset_id,kind).then(plan=>{state.polish[key]=plan;scheduleRuns();},error=>{state.polish[key]={ok:false,reason:error.message};planning.delete(key);setTimeout(()=>{delete state.polish[key];scheduleRuns();},15000);scheduleRuns();});}
  }
  let runsFrame=0;const scheduleRuns=()=>{if(!runsFrame)runsFrame=requestAnimationFrame(()=>{runsFrame=0;renderRuns();});};
  async function polishPicture(button){
    const id=button.dataset.asset,kind=button.dataset.makePolish,key=id+':'+kind,status=q('#makeStatus');if(state.polishing.has(key))return;
    const source=state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===id));state.polishing.add(key);renderRuns();
    try{const job=await window.StudioWorkbench.polish(id,kind);state.runs.unshift({job,look:POLISH[kind]+(source?' \u00b7 '+source.look:''),lookId:source?.lookId,goal:source?.goal,scene:null});remember();poll(job.id);
      if(status)say(POLISH[kind]+' started. The result appears at the top of your pictures.');}
    catch(error){if(status)say(error.message);}
    finally{state.polishing.delete(key);renderRuns();}
  }
  // shortcut: Comfy outputs have no auxiliary role; match filename tokens until outputs declare one (Workspace keeps source.filename).
  const picture=o=>(!o.media_type||o.media_type==='image')&&!/(?:^|[/_\\-])(mask|matte)(?:[_.-]|$)/i.test(o.source?.filename||o.filename||'');
  const pictureTitle=(scene,date)=>String(scene||'Picture').slice(0,100)+(date?' \u00b7 '+new Date(Number(date)*1000).toLocaleDateString():'');
  function renderRuns(){
    const box=q('#makeRuns');if(!box)return;
    // A compare (#16) is one card: its runs share a group and sit next to each other in state.runs. Six cards at most.
    const list=[];for(const run of state.runs){const last=list[list.length-1];if(run.group&&last?.group===run.group){last.runs.push(run);continue;}if(list.length===6)break;list.push({group:run.group||null,id:run.group||run.job.id,runs:[run]});}
    planPolish(list.flatMap(c=>c.runs));
    if(!list.length){box.innerHTML='<p class="muted">Pictures you make here show up in this space, with one-press next steps.</p>';return;}
    const img=(job,o,i,look)=>(o.asset_id?'<button type="button" class="make-open" data-ux-open-asset="'+escape(o.asset_id)+'" aria-label="Open picture '+(i+1)+' from '+escape(look)+' full size">':'')+'<img src="/api/image/'+encodeURIComponent(job.id)+'/'+i+'" alt="Picture '+(i+1)+' from '+escape(look)+'" loading="lazy">'+(o.asset_id?'</button>':'');
    // A clip or a 3D model has no picture to show here: one press opens it in the library viewer.
    const other=o=>o.asset_id&&o.media_type&&o.media_type!=='image'?'<figure class="make-media"><button type="button" data-ux-open-asset="'+escape(o.asset_id)+'">Open the '+(o.media_type==='video'?'clip':o.media_type==='audio'?'sound':'3D model')+'</button></figure>':'';
    const pending=(job,n=job.batch_count||1)=>FINAL.includes(job.status)?'':Array.from({length:Math.max(0,n-(job.outputs||[]).length)},()=>'<figure class="make-pending" aria-hidden="true"><span></span></figure>').join('');
    const markup=list.map(({group,id,runs})=>{
      if(group){const done=runs.filter(r=>FINAL.includes(r.job.status)).length,first=runs[0];
        return '<article class="make-run make-compare" data-run="'+escape(id)+'"><header><div><b>Compare looks · '+escape(pictureTitle(first.scene,first.job.created_at))+'</b><small>'+runs.length+' looks, one picture each'+(runs.every(r=>r.job.controls?.seed!=null&&r.job.controls.seed===first.job.controls?.seed)?', same seed':'')+'</small></div><span class="make-run-state '+(done===runs.length?'completed':'running')+'">'+(done===runs.length?'Done':done+' of '+runs.length+' done')+'</span></header><div class="make-compare-grid">'
          +runs.map(({job,look})=>'<figure><figcaption><b>'+escape(look)+'</b><small class="make-run-state '+escape(job.status)+'">'+escape(words(job))+'</small></figcaption>'+(job.status==='failed'&&job.message?'<p class="make-warn">'+escape(job.message)+'</p>':'')
            +(job.outputs||[]).map((o,i)=>picture(o)?img(job,o,i,look)+(o.asset_id?'<div class="make-actions">'+marks(o.asset_id)+'</div>':'<small class="muted">Saving to the library…</small>'):'').join('')+pending(job,1)+'</figure>').join('')+'</div></article>';}
      const {job,look,scene,tuned,title}=runs[0];
      return '<article class="make-run" data-run="'+escape(job.id)+'"><header><div><b>'+escape(pictureTitle(scene||title||job.controls?.positive||look,job.created_at))+'</b>'+(scene?'<small>'+escape(scene)+'</small>':look&&!scene?'<small>'+escape(look)+'</small>':'')+(tuned?'<small class="make-tuned">'+escape(tuned)+'</small>':'')+'</div><span class="make-run-state '+escape(job.status)+'">'+escape(words(job))+'</span></header>'
      +(scene?'<div class="make-run-tools"><button type="button" data-make-rerun="'+escape(job.id)+'">Edit and re-run</button><button type="button" data-make-another="'+escape(job.id)+'">Same words, another look</button></div>':'')
      +(job.status==='failed'&&job.message?'<p class="make-warn">'+escape(job.message)+'</p>':'')
      +'<div class="make-outputs">'+(job.outputs||[]).map((o,i)=>!picture(o)?other(o):'<figure>'+img(job,o,i,look)+actions(job,o)+'</figure>').join('')+pending(job)+'</div></article>';});
    const focus=document.activeElement,key=e=>(e.closest('[data-run]')?.dataset.run||'')+'|'+e.tagName+'|'+JSON.stringify({...e.dataset})+'|'+e.textContent,focusKey=box.contains(focus)?key(focus):null,open=[...box.querySelectorAll('details[open]')].map(e=>e.dataset.more);
    const next=document.createElement('div');next.innerHTML=markup.join('');
    const ids=new Set(list.map(c=>c.id));for(const old of [...box.children])if(!ids.has(old.dataset.run))old.remove();
    for(const [i,card] of [...next.children].entries()){const old=[...box.children].find(e=>e.dataset.run===card.dataset.run);if(old&&old.dataset.markup===card.outerHTML)continue;card.dataset.markup=card.outerHTML;if(old)old.replaceWith(card);else box.insertBefore(card,box.children[i]||null);}
    for(const menu of box.querySelectorAll('details'))menu.open=open.includes(menu.dataset.more);
    if(focusKey&&document.activeElement!==focus)[...box.querySelectorAll('button,summary,a')].find(e=>key(e)===focusKey)?.focus();
  }
  // Picture goals stay in Make (owner ask, 16 Oct 2026; journey audit #5-#7): pick the picture, answer a few plain fields, press
  // Make's own Generate. The request is the one the handoff prepares (studio-workbench.js polish/openHandoff): the source is
  // copied by /api/assets/reference and verified, StudioContinuation.initial writes the continuation claim, and the server checks
  // the claim, the graph hash, every file and every bracketed fill again. No route or input is added for this.
  const SC=()=>window.StudioContinuation,PE=()=>window.StudioPoseEditor,thumbUrl=a=>'/api/assets/'+encodeURIComponent(a.id)+'/thumb';
  const pictureLabel=a=>pictureTitle(a.prompt_excerpt||(!a.job_id&&a.title)||a.title,a.created_at);
  const PICK={edit:'Choose the picture to change.',repair:'Choose the picture to fix or enlarge.',restyle:'Choose the picture to redraw in another look.',combine:'Choose the character. The pose comes next.',animate:'Choose the still to bring to life.',mesh:'Choose a picture of one object or character, ideally on a plain background.'};
  const HEAD={edit:'What should change?',repair:'What should be fixed?',restyle:'Choose the new look',combine:'Choose the pose',animate:'How should it move?',mesh:'Make a 3D model'};
  // A recipe's bracketed fills become plain fields named by what they mean; a recipe example that names a person is never shown.
  const FILL={who:['Who is in the character picture','a girl with short black hair'],clothes:['What they wear, with colours','a black jacket and a red scarf'],pose:['The pose, in a few words','arms crossed, looking over one shoulder'],outfit:['The clothes in the pose picture, with colours','a long blue coat and brown boots']};
  const CLIP={'quick-diagnostic':'Short','balanced':'Longer'},CLIP_FPS=24;  // wan22-i2v writes MP4 at 24 fps (its stages)
  const ready=()=>typeof catalog!=='undefined'&&!!catalog&&!!SC();
  const runnable=p=>!!p&&!p.runtime_block&&!missingFor(p).length;
  const lookPictures=()=>(state.looks||[]).filter(l=>!l.trashed_at&&l.usable!==false&&thumbOf(l));
  const clips=p=>(p?.i2v_modes||[]).filter(m=>!m.execution_block&&m.controls);
  // The leading destination the handoff would offer for this task, the first one that can run here when there is a choice.
  function goalRoute(g){
    if(!ready()||g.intent==='repair')return null;
    const list=SC().destinations(g.intent,presets(),null).filter(p=>!p.continuation_capability.requires_mask),first=f=>{const fit=list.filter(f);return fit.find(runnable)||fit[0]||null;};
    if(g.intent==='edit')return first(p=>p.continuation_capability.operation==='instruction-edit'&&!p.reference_slots?.length);
    if(g.intent==='restyle'){const words=state.styleWords||!lookPictures().length;return first(p=>p.id===(words?'restyle-klein':'restyle-klein-picture'))||first(p=>!!p.reference_slots?.length!==words);}
    if(g.intent==='combine')return first(p=>SC().combineKind(p)===(state.poseMode==='figure'?'skeleton':'picture'));
    return first(()=>true);
  }
  function goalBlocker(g,p){
    const runtime=runtimeBlocker();if(runtime)return runtime;
    if(g.intent==='repair'){const plan=state.pick&&state.polish[state.pick.id+':'+state.fix];return plan&&!plan.ok?plan.reason:'';}
    if(!ready())return'Recipes are still loading.';if(!p)return'No recipe on this PC can do this yet.';if(p.runtime_block)return p.runtime_block;
    const m=missingFor(p);return m.length?'Needs '+m.length+' model file'+(m.length>1?'s':'')+' first: open Models & setup.':'';
  }
  const goalWhy=(p,text)=>escape(text).replace('Models &amp; setup','<a href="/#models?need='+escape(encodeURIComponent(p?.id||''))+'">Models &amp; setup</a>');
  function fillFields(g,p){return p?SC().fills(p,p.continuation_prompt).map((f,i)=>{const m=SC().fillMeaning(f.placeholder);
    if(g.intent==='restyle')return{key:'colours',label:'Colours to keep (optional)',hint:'black hair, a red robe with gold trim',placeholder:f.placeholder,optional:true};
    if(g.intent==='edit'&&!m)return{key:'change',label:'What should change?',hint:f.example||'replace her hat with a red Santa hat',placeholder:f.placeholder};
    const [label,hint]=FILL[m]||[f.label,''];return{key:m||'fill'+i,label,hint,placeholder:f.placeholder};}):[];}
  const splitLook=text=>{const i=text.indexOf(' Keep ');return i<0?[text,'']:[text.slice(0,i),text.slice(i+1)];};
  // The wording sent: the recipe's own continuation prompt with each field written into its bracket.
  function goalWords(g,p,prepared,form){
    const value=k=>String(form[k]||'').trim();
    if(g.intent==='animate')return value('motion');
    if(g.intent==='restyle'&&!p.reference_slots?.length){const [head,tail]=splitLook(prepared);return((value('look')||head).replace(/[\s.:;,]+$/,'')+'. '+tail).trim();}
    const fields=fillFields(g,p);if(!fields.length)return g.intent==='edit'&&value('change')?value('change'):prepared;
    if(g.intent==='combine')return SC().assemble(prepared,SC().combineFillValues(p,{who:value('who'),clothes:value('clothes'),pose:value('pose'),outfit:value('outfit')}));
    return SC().assemble(prepared,Object.fromEntries(fields.map(f=>[f.placeholder,value(f.key)||(f.optional?'keep them exactly as they are':'')])));
  }
  function goalMissing(g,p,form){
    const value=k=>String(form[k]||'').trim();
    if(g.intent==='combine'&&!(state.poseMode==='figure'?state.pose?.figure:state.pose?.asset))return['makePoseSlot','Choose the pose first: a picture of it, or a drawn figure.'];
    if(g.intent==='restyle'&&p?.reference_slots?.length&&!lookPictures().some(l=>l.id===state.styleLook))return['makeStyleLooks','Choose the look to redraw it in, or describe the look in words.'];
    if(g.intent==='animate'&&!value('motion'))return['makeF-motion','Say how it should move first.'];
    if(g.intent==='restyle'&&!p?.reference_slots?.length&&!value('look'))return['makeF-look','Describe the new look first.'];
    for(const f of fillFields(g,p))if(!f.optional&&!value(f.key))return['makeF-'+f.key,f.label+': fill this in first.'];
    if(g.intent==='edit'&&!fillFields(g,p).length&&!value('change'))return['makeF-change','Say what should change first.'];
    return null;
  }
  // The second picture: a look's picture (its library asset, else its example image uploaded as a reference), a pose
  // picture from the library, or a drawn stick figure rendered by /api/pose/render exactly as Create's pose editor does.
  async function goalBoard(g,p){
    if(!p.reference_slots?.length)return[];
    if(g.intent==='restyle'){const look=lookPictures().find(l=>l.id===state.styleLook);
      if(look.anchor_asset_id)return[await json('/api/assets/reference',{id:look.anchor_asset_id})];
      const r=await fetch(thumbOf(look));if(!r.ok)throw Error('Could not read the picture of '+look.name+'.');const blob=await r.blob();
      const sent=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':blob.type||'image/jpeg','X-Filename':look.id+(/png/.test(blob.type)?'.png':'.jpg')},body:blob}),data=await sent.json().catch(()=>({}));
      if(!sent.ok)throw Error(data.error||'Could not attach the look picture ('+sent.status+').');return[data];}
    if(state.poseMode!=='figure')return[await json('/api/assets/reference',{id:state.pose.asset.id})];
    const P=PE(),canvas={width:Number(p.defaults?.width)||1024,height:Number(p.defaults?.height)||1536};let points=P.fromPreset(state.pose.figure,canvas);if(state.pose.mirror)points=P.mirror(points,canvas);
    const body=P.renderRequest(P.serialize(points,canvas),P.guideRenderer(p));return[P.guideResponse(await json('/api/pose/render',body),body)];
  }
  function goalExtras(g,p,source){
    if(g.intent==='animate'){const m=clips(p).find(x=>x.id===state.form.clip)||clips(p)[0];if(!m)return{};const {positive,negative,...c}=m.controls;return{...c,mode:m.id};}
    return p?.continuation_capability?.operation==='restyle'&&source&&SC().canvasFor(source,p)||{};
  }
  let goalEpoch=0;
  async function goalEstimate(g,p){
    const out=q('#makeEstimate');if(!out||!state.pick)return;const epoch=++goalEpoch,put=(t,warn=false)=>{if(epoch===goalEpoch&&out.isConnected){out.textContent=t;out.classList.toggle('make-warn',warn);}};
    if(g.intent==='repair'){const plan=state.polish[state.pick.id+':'+state.fix];put(plan?.seconds?'About '+duration(plan.seconds)+', from earlier runs on this PC.':'');return;}
    if(!p){put('');return;}
    try{const e=await json('/api/estimate',{preset_id:p.id,controls:goalExtras(g,p,state.pick.width?state.pick:null),batch_count:1,reference_count:p.reference_slots?.length?1:0});
      put(e.estimate_seconds?'About '+duration(e.estimate_seconds)+', from earlier runs on this PC.':'No timing yet: this has not run on this PC.',e.estimate_seconds>600);}
    catch{put('');}
  }
  async function renderPictures(g){
    const body=q('#makeBody'),a=state.pick;
    if(a&&!state.repicking){body.innerHTML=(g.intent==='combine'?'':'<div class="make-chosen make-picked"><img src="'+thumbUrl(a)+'" alt=""><div><small>Your picture</small><b>'+escape(pictureLabel(a))+'</b></div><button type="button" data-make-repick>Change picture</button></div>')+'<div id="makeComposer"></div>';renderGoalComposer(g);return;}
    body.innerHTML='<div class="make-step"><span>1</span><h2>'+(g.intent==='combine'?'Pick the character picture':'Pick the picture')+'</h2>'+(a?'<button type="button" class="make-link" data-make-keep-picture>Keep '+escape(pictureLabel(a))+'</button>':'')+'</div><p class="make-hint">'+escape(PICK[g.intent])+' <a href="/#assets">Import a picture</a> first if it is not here.</p>'+pictureFinder('makePictures','data-make-pick');
    await fillPictures(g,'makePictures','data-make-pick');
  }
  const pictureFinder=(id,attr)=>'<input type="search" class="make-search" data-make-search="'+id+'" data-make-attr="'+attr+'" placeholder="Search your pictures" aria-label="Search your pictures" aria-controls="'+id+'" value="'+escape(state.queries[id]||'')+'"><div id="'+id+'" class="make-pictures"><p class="muted">Loading your pictures…</p></div>';
  async function fillPictures(g,id,attr){
    try{if(!state.pictures){const data=await json('/api/workspace');state.pictures=(data.assets||[]).filter(a=>a.media_type==='image'&&picture(a)&&!a.trashed_at).sort((a,b)=>(b.created_at||0)-(a.created_at||0));}   // the whole library is searchable; the grid shows the newest 60 matches
      if(goal()===g)renderGrid(id,attr);}
    catch(error){if(goal()===g&&q('#'+id))q('#'+id).innerHTML='<p class="make-error">'+escape(error.message)+'</p>';}
  }
  // Search reads the words people see on the card plus tags and file name; masks never reach this list.
  function renderGrid(id,attr){
    const box=q('#'+id);if(!box||!state.pictures)return;const terms=String(state.queries[id]||'').toLowerCase().split(/\s+/).filter(Boolean);
    const list=state.pictures.filter(a=>{const text=[pictureLabel(a),a.title,a.prompt_excerpt,a.filename,...(a.tags||[])].join(' ').toLowerCase();return terms.every(t=>text.includes(t));});
    const shown=list.slice(0,60),more=list.length-shown.length;
    box.innerHTML=list.length?shown.map(a=>'<button type="button" '+attr+'="'+escape(a.id)+'"><img src="'+thumbUrl(a)+'" alt="" loading="lazy"><small>'+escape(pictureLabel(a))+'</small></button>').join('')+(more?'<p class="muted">'+more+' older picture'+(more===1?'':'s')+' match too. Search to narrow the list.</p>':''):state.pictures.length?'<p class="muted">No picture matches “'+escape(state.queries[id])+'”.</p>':'<p class="muted">No pictures yet. Make one first, or import one in the library.</p>';
  }
  function figureSvg(points,mirror){const P=PE(),at=i=>points[i]&&[Math.round((mirror?1-points[i][0]:points[i][0])*100),Math.round(points[i][1]*150)];
    return '<svg viewBox="0 0 100 150" aria-hidden="true">'+P.LIMBS.map(([a,b])=>{const s=at(a),e=at(b);return s&&e?'<line x1="'+s[0]+'" y1="'+s[1]+'" x2="'+e[0]+'" y2="'+e[1]+'" stroke="'+P.COLORS[b]+'"/>':'';}).join('')+'</svg>';}
  function renderGoalComposer(g){
    const box=q('#makeComposer'),a=state.pick;if(!box||!a)return;
    const p=goalRoute(g),why=goalBlocker(g,p),f=state.form,fields=fillFields(g,p),focus=box.contains(document.activeElement)?document.activeElement.id:'';
    const field=(key,label,hint,rows=2,max=600)=>'<label class="make-field" for="makeF-'+key+'">'+escape(label)+'</label><textarea id="makeF-'+key+'" data-make-field="'+key+'" rows="'+rows+'" maxlength="'+max+'" placeholder="'+escape(hint)+'">'+escape(f[key]??'')+'</textarea>';
    const fill=x=>field(x.key,x.label,x.hint);
    let main='',side='';
    if(g.intent==='edit')main=(fields.length?fields.map(fill).join(''):field('change','What should change?','replace her hat with a red Santa hat'))+'<small class="muted">Everything else stays as it is: the character, pose, clothes, background and style.</small>';
    else if(g.intent==='repair'){planFixes(a.id);main='<fieldset class="make-options"><legend>Choose one</legend>'+Object.entries(POLISH).map(([kind,label])=>{const plan=state.polish[a.id+':'+kind],off=!!plan&&!plan.ok;
      return '<label class="make-check"><input type="radio" name="makeFix" id="makeFix-'+kind+'" data-make-fix="'+kind+'"'+(state.fix===kind?' checked':'')+(off?' aria-describedby="makeFixWhy-'+kind+'"':'')+'> '+label+(plan?.seconds?' <small>~'+duration(plan.seconds)+'</small>':'')+'</label>'+(off?'<small class="make-warn make-option-why" id="makeFixWhy-'+kind+'">'+escape(plan.reason)+'</small>':'');}).join('')+'</fieldset>';}
    else if(g.intent==='restyle'){
      if(p?.reference_slots?.length)main='<fieldset class="make-style-looks" id="makeStyleLooks" tabindex="-1"><legend>Redraw it the way this look is drawn</legend>'+lookPictures().map(l=>'<label class="make-style"><input type="radio" name="makeStyle" id="makeStyle-'+escape(l.id)+'" data-make-style="'+escape(l.id)+'"'+(state.styleLook===l.id?' checked':'')+'><img src="'+escape(thumbOf(l))+'" alt="" loading="lazy"><span>'+escape(l.name)+'</span></label>').join('')+'</fieldset>'
        +'<button type="button" class="make-link" data-make-style-words>Describe the look in words instead</button>'+fields.map(fill).join('')+'<small class="muted">Only how the look picture is drawn is copied, not what it shows. Your picture keeps its character, pose, clothes and layout.</small>';
      else{if(f.look==null&&p)f.look=splitLook(SC().promptFor(p,null)||'')[0];main=field('look','Describe the new look','a soft watercolour illustration with loose ink lines',4,2000)+(lookPictures().length?'<button type="button" class="make-link" data-make-style-pictures>Pick a look by its picture instead</button>':'')+'<small class="muted">Your words carry the look. Your picture keeps its character, pose, clothes and layout.</small>';}}
    else if(g.intent==='combine'){
      const figure=state.poseMode==='figure',pose=state.pose,figures=(PE()?.PRESETS||[]).filter(x=>x.points),mode=(value,label)=>'<label class="make-check"><input type="radio" name="makePoseMode" id="makePoseMode-'+value+'" data-make-pose-mode="'+value+'"'+(state.poseMode===value?' checked':'')+'> '+label+'</label>';
      main='<div class="make-slots"><section class="make-slot" aria-labelledby="makeSlotA"><h3 id="makeSlotA">Character picture</h3><img src="'+thumbUrl(a)+'" alt=""><small>'+escape(pictureLabel(a))+'</small><button type="button" data-make-repick>Change picture</button></section>'
        +'<section class="make-slot" id="makePoseSlot" tabindex="-1" aria-labelledby="makeSlotB"><h3 id="makeSlotB">Pose</h3><div class="make-seg" role="group" aria-label="Where the pose comes from">'+mode('picture','A picture of the pose')+mode('figure','Draw the pose')+'</div>'
        +(figure?'<div class="make-figures">'+figures.map(x=>'<label class="make-figure"><input type="radio" name="makeFigure" id="makeFigure-'+x.id+'" data-make-figure="'+x.id+'"'+(pose?.figure===x.id?' checked':'')+'>'+figureSvg(x.points,pose?.figure===x.id&&pose.mirror)+'<span>'+escape(x.label)+'</span></label>').join('')+'</div><label class="make-check"><input type="checkbox" id="makeMirror" data-make-mirror'+(pose?.mirror?' checked':'')+(pose?.figure?'':' disabled')+'> Mirror left and right</label><small class="muted">A stick figure carries the pose and nothing else. To move single joints, open the full editor.</small>'
          :pose?.asset&&!state.posePicking?'<img src="'+thumbUrl(pose.asset)+'" alt=""><small>'+escape(pictureLabel(pose.asset))+'</small><button type="button" data-make-pose-change>Change pose picture</button><small class="muted">Only the body position is taken from it, not the person, clothes or colours.</small>'
          :pictureFinder('makePosePictures','data-make-pose-pick'))+'</section></div>'+fields.map(fill).join('');}
    else if(g.intent==='animate'){main=field('motion','Motion and camera','she turns her head and smiles; the camera slowly moves closer',3)+'<small class="muted">Say what moves and how the camera moves. A description of the picture alone gives a still clip.</small>';
      const list=clips(p);if(list.length)side='<label>Length<select id="makeClip" data-make-field="clip">'+list.map(m=>'<option value="'+escape(m.id)+'"'+((f.clip||list[0].id)===m.id?' selected':'')+'>'+escape(CLIP[m.id]||m.name)+' · '+m.controls.frames+' frames, about '+(m.controls.frames/CLIP_FPS).toFixed(1)+' s</option>').join('')+'</select></label>';}
    else main='<p>One press: the background is cut away, then a textured 3D model (GLB) is built from this picture. Hidden sides are guessed, so check the model before you use it.</p>';
    box.innerHTML='<div class="make-step"><span>2</span><h2>'+escape(HEAD[g.intent])+'</h2></div><div class="make-composer"><div class="make-compose-main">'+main+'</div><div class="make-compose-side">'+side
      +'<div class="make-go"><button type="button" id="makeGenerate" class="primary"'+(why?' disabled aria-describedby="makeWhy"':'')+'>Generate</button><p id="makeEstimate" class="muted" aria-live="polite"></p>'+(why?'<p id="makeWhy" class="make-warn">'+goalWhy(p,why)+'</p>':'')+'</div>'
      +'<button type="button" class="make-link" data-ux-handoff="'+escape(a.id)+'" data-ux-handoff-intent="'+g.intent+'">Open in the full editor instead</button>'
      +(p?'<details class="make-about"><summary>What this uses</summary><p>'+escape(p.name)+'</p></details>':'')+'</div></div>';
    if(q('#makePosePictures'))void fillPictures(g,'makePosePictures','data-make-pose-pick');
    if(focus)q('#'+CSS.escape(focus))?.focus();
    syncOperation();goalEstimate(g,p);
  }
  function planFixes(id){
    const api=window.StudioWorkbench;if(!api?.polishPlan)return;
    for(const kind of Object.keys(POLISH)){const key=id+':'+kind;if(planning.has(key))continue;planning.add(key);
      api.polishPlan(id,kind).then(plan=>{state.polish[key]=plan;if(state.pick?.id===id&&goal().intent==='repair'&&!state.repicking)renderGoalComposer(goal());},error=>{state.polish[key]={ok:false,reason:error.message};planning.delete(key);});}
  }
  // The answers a picture's Combine fields were given last time (the same store Create's fields use).
  const fillsKey=id=>'studio-fills:'+id;
  function choosePicture(id){
    const a=state.pictures?.find(x=>x.id===id)||(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===id))||{id,title:''};
    if(state.pick?.id!==id){state.form={};try{const saved=JSON.parse(localStorage.getItem(fillsKey(id))||'{}');for(const k of ['who','clothes'])if(typeof saved['@'+k]==='string')state.form[k]=saved['@'+k];}catch{}}
    state.pick=a;state.repicking=false;
  }
  function rememberFills(id,form){try{const saved=JSON.parse(localStorage.getItem(fillsKey(id))||'{}');for(const k of ['who','clothes','pose'])if(String(form[k]||'').trim())saved['@'+k]=form[k].trim();localStorage.setItem(fillsKey(id),JSON.stringify(saved));}catch{}}
  async function goalGenerate(){
    const g=goal(),a=state.pick;if(!g.intent||!a||state.busy)return;
    const p=goalRoute(g),why=goalBlocker(g,p);if(why){say(why);return;}
    // Every answer is read before the first await: typing on while the copy runs does not change this request.
    const form={...state.form},missing=goalMissing(g,p,form);
    if(missing){const [id,text]=missing,el=q('#'+id);if(el){el.setAttribute('aria-invalid','true');el.setAttribute('aria-describedby','makeStatus');el.focus();}say(text);return;}
    state.busy=true;say('Preparing…');
    try{
      let job;
      if(g.intent==='repair')job=await window.StudioWorkbench.polish(a.id,state.fix);
      else{
        const source=await json('/api/assets/'+encodeURIComponent(a.id)+'/context');if(source?.version!==1||source.asset_id!==a.id)throw Error('This picture’s record could not be verified. Refresh and try again.');
        const board=await goalBoard(g,p),result=await json('/api/assets/reference',{id:a.id});
        if(result?.parent_asset!==a.id||result.sha256!==source.sha256||result.context?.asset_id!==a.id||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The picture changed while it was being copied. Nothing was sent.');
        const prepared=SC().initial(result.context,p,g.intent,result.file),controls={[SC().sourceInput(p.continuation_capability)]:result.file,...goalExtras(g,p,result.context)};
        if(p.positive)controls.positive=goalWords(g,p,prepared.positive,form);
        if(p.negative&&prepared.negative)controls.negative=prepared.negative;
        if(p.seed||p.bindings_extra?.seed)controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
        if(p.positive&&(!controls.positive.trim()||SC().unfilled(p,controls.positive).length))throw Error('Fill in every field, then press Generate again. Nothing was sent.');
        if(g.intent==='combine')rememberFills(a.id,form);
        say('Sending to ComfyUI…');
        job=await json('/api/jobs',{preset_id:p.id,continuation:prepared.claim,controls,batch_count:1,parent_assets:[...new Set([a.id,...board.map(r=>r.parent_asset).filter(Boolean)])],references:p.reference_slots?.length?SC().combineReferences(p,board):[],label:'Make · '+g.name});
      }
      state.runs.unshift({job,look:g.intent==='repair'?POLISH[state.fix]:g.name,lookId:null,goal:g.id,scene:null,title:String(form[{edit:'change',animate:'motion',combine:'who'}[g.intent]]||'').trim()||pictureLabel(a)});remember();
      say('Started. The result appears in Your pictures as it finishes; you can leave this page.');renderRuns();poll(job.id);
      if(typeof refresh==='function')void refresh();
    }catch(error){say(error.message);}
    finally{state.busy=false;syncOperation();}
  }
  // Compare looks (#16): two or three looks of this goal, one scene, one press. Each look runs once, as made (no tune), at
  // its own designed shape, all from one seed where the recipe takes a seed; the runs share a group and one card.
  const compareList=()=>state.compareLooks.map(id=>lookList().find(l=>l.id===id)).filter(Boolean);
  function compareBlocker(){const runtime=runtimeBlocker();if(runtime)return runtime;const list=compareList();if(list.length<2)return'Choose at least two looks to compare.';for(const l of list){const why=blocker(l,presetFor(l));if(why)return l.name+': '+why;}return'';}
  function renderCompareComposer(){
    const box=q('#makeComposer');if(!box)return;const list=compareList(),why=compareBlocker(),seeded=list.filter(l=>bound(presetFor(l),'seed')).length,example=list[0]?.body.scene_example||'';
    box.innerHTML='<div class="make-step"><span>2</span><h2>One scene for every look</h2></div><div class="make-composer"><div class="make-compose-main"><label for="makeScene">'+escape(state.goal==='scene'?'Where is it, and what is there?':state.goal==='game'?'What is the item?':'Who or what, doing what, where?')+'</label><textarea id="makeScene" rows="3" maxlength="1000" placeholder="'+escape(example)+'"></textarea>'
      +'<div class="make-row">'+(example?'<button type="button" id="makeUseExample">Use the example</button>':'')+'<small>Each look adds its own style and quality words and keeps its own shape.</small></div>'
      +'<p class="make-hint" id="makeCompareSum">'+(list.length?'Comparing '+list.map(l=>escape(l.name)).join(', ')+'.':'Choose two or three looks above.')+(list.length>1?' One picture per look, '+(seeded===list.length?'all from the same seed.':seeded?'the same seed for the '+seeded+' looks that take one.':'each from its own seed.'):'')+'</p></div>'
      +'<div class="make-compose-side"><div class="make-go"><button type="button" id="makeGenerate" class="primary"'+(why?' disabled aria-describedby="makeWhy"':'')+'>Generate'+(list.length>1?' '+list.length+' pictures':'')+'</button><p id="makeEstimate" class="muted" aria-live="polite"></p>'+(why?'<p id="makeWhy" class="make-warn">'+escape(why)+'</p>':'')+'</div></div></div>';
    const scene=q('#makeScene');try{scene.value=sessionStorage.getItem('studio.make.scene.'+state.goal)||'';}catch{}
    scene.oninput=()=>{scene.removeAttribute('aria-invalid');scene.removeAttribute('aria-describedby');try{sessionStorage.setItem('studio.make.scene.'+state.goal,scene.value);}catch{}};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    syncOperation();void compareEstimate();
  }
  let compareEpoch=0;
  async function compareEstimate(){
    const out=q('#makeEstimate'),list=compareList();if(!out)return;const epoch=++compareEpoch;if(list.length<2){out.textContent='';return;}
    const each=await Promise.all(list.map(l=>{const p=presetFor(l),[w,h]=shapeSize(p,l,'design');return json('/api/estimate',{preset_id:p?.id||l.body.preset_id,controls:{...l.body.controls,width:w,height:h},batch_count:1,reference_count:0}).then(e=>Number(e.estimate_seconds)||0,()=>0);}));
    if(epoch!==compareEpoch||!out.isConnected)return;const total=each.reduce((x,y)=>x+y,0),unknown=each.filter(x=>!x).length;
    out.classList.toggle('make-warn',total>600);out.textContent=list.length+' pictures, one per look'+(total?' · about '+duration(total)+' in total'+(unknown?' (no timing yet for '+unknown+')':'')+', from earlier runs on this PC.':' · no timing yet for these looks on this PC.');
  }
  async function generateCompare(){
    if(state.busy)return;const list=compareList(),why=compareBlocker();if(why){say(why);return;}
    const field=q('#makeScene'),scene=field.value.trim();if(!scene){field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby','makeStatus');field.focus();say('Describe your picture first, or press Use the example.');return;}
    state.busy=true;say('Preparing…');
    const seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647,group='compare-'+Date.now().toString(36),runGoal=state.goal;let started=0;
    try{
      for(const look of list){
        const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options:Object.fromEntries(look.body.options.map(o=>[o.id,!!o.default]))}:{}),expected_revision:look.revision});
        const p=presetFor(look),controls={...result.controls},[w,h]=shapeSize(p,look,'design');
        if('width' in controls||p?.width)Object.assign(controls,{width:w,height:h});
        if(bound(p,'seed'))controls.seed=seed;
        say('Sending '+(started+1)+' of '+list.length+' to ComfyUI…');
        const job=await json('/api/jobs',{preset_id:p?.id||look.body.preset_id,controls,batch_count:1,label:'Make · Compare · '+look.name});
        state.runs.splice(started++,0,{job,look:look.name,lookId:look.id,goal:runGoal,scene,group});remember();renderRuns();poll(job.id);
      }
      say('Started '+list.length+' pictures, one per look. They appear side by side in Your pictures.');
      if(typeof refresh==='function')void refresh();
    }catch(error){say((started?'Started '+started+' of '+list.length+'; the rest were not sent. ':'')+error.message);}
    finally{state.busy=false;syncOperation();}
  }
  async function load(){
    state.error='';
    // Speed, readiness and history read the recipe catalog that app.js loads; wait for it briefly instead of guessing.
    for(let i=0;i<40&&!presets().length;i++)await new Promise(r=>setTimeout(r,250));
    try{
      const [listing]=await Promise.all([json('/api/looks'),import('/static/bundle-showcase.js').then(m=>{state.examples=m.default.examples||{};}).catch(()=>{})]);
      state.looks=(listing.looks||listing.cards||[]).filter(l=>l.kind==='look'||l.body);
    }catch(error){state.error='Could not read the looks: '+error.message;}
    render();
    // Earlier Make runs come back from their job records; one that is gone is dropped, one still running is followed again.
    const restored=await Promise.all(savedRuns.map(async r=>{try{return{...r,job:await json('/api/jobs/'+encodeURIComponent(r.id))};}catch{return null;}}));
    state.runs=[...state.runs,...restored.filter(r=>r&&!state.runs.some(x=>x.job.id===r.id)).map(({id,...r})=>r)];
    restoredRuns=true;
    for(const r of state.runs)if(!FINAL.includes(r.job.status))poll(r.job.id);
    renderRuns();
  }
  view.addEventListener('input',e=>{const t=e.target;if(t.closest('#makeTune')){tuneInput(t);return;}
    if(t.dataset.makeField){state.form[t.dataset.makeField]=t.value;t.removeAttribute('aria-invalid');t.removeAttribute('aria-describedby');if(t.tagName==='SELECT')void goalEstimate(goal(),goalRoute(goal()));return;}
    if(t.dataset.makeSearch){state.queries[t.dataset.makeSearch]=t.value;renderGrid(t.dataset.makeSearch,t.dataset.makeAttr);}});
  // Choices that change the composer redraw it and keep the keyboard on the control just used.
  view.addEventListener('change',e=>{const t=e.target,g=goal(),redraw=sel=>{renderGoalComposer(g);q(sel)?.focus();};
    if(t.dataset.makeFix){state.fix=t.dataset.makeFix;redraw('#makeFix-'+state.fix);return;}
    if(t.dataset.makeStyle){state.styleLook=t.dataset.makeStyle;q('#makeStyleLooks')?.removeAttribute('aria-invalid');return;}
    if(t.dataset.makePoseMode){state.poseMode=t.dataset.makePoseMode;state.posePicking=false;redraw('#makePoseMode-'+state.poseMode);return;}
    // A new figure is a new pose: its words replace the pose answer (Create clears it the same way, #492); edit them freely.
    if(t.dataset.makeFigure){const fig=PE().PRESETS.find(x=>x.id===t.dataset.makeFigure);state.pose={figure:fig.id,mirror:!!state.pose?.mirror};state.form.pose=fig.label.toLowerCase();redraw('#makeFigure-'+fig.id);return;}
    if('makeMirror' in t.dataset&&state.pose?.figure){state.pose.mirror=t.checked;redraw('#makeMirror');}});
  view.addEventListener('click',e=>{
    if(e.target.closest('#makeTune')&&tuneClick(e.target))return;
    const g=e.target.closest('[data-make-goal]');if(g){state.goal=g.dataset.makeGoal;state.pictures=null;remember();render();q('[data-make-goal="'+state.goal+'"]')?.focus();return;}
    const l=e.target.closest('[data-make-look]');if(l&&state.compare){const id=l.dataset.makeLook,i=state.compareLooks.indexOf(id);
      if(i>=0)state.compareLooks.splice(i,1);else if(state.compareLooks.length>=3){say('Three looks at most: unselect one first.');return;}else state.compareLooks.push(id);
      renderLooks();q('[data-make-look="'+id+'"]')?.focus();return;}
    if(l){state.look=l.dataset.makeLook;state.picking=false;remember();renderLooks();q('#makeScene')?.focus();return;}
    if(e.target.closest('[data-make-compare]')){state.compare=!state.compare;state.compareLooks=state.compare&&lookList().some(x=>x.id===state.look)?[state.look]:[];
      say(state.compare?'Compare looks: choose two or three looks, type one scene, then press Generate once.':'');renderLooks();q('[data-make-compare]')?.focus();return;}
    const pick=e.target.closest('[data-make-pick]');if(pick){choosePicture(pick.dataset.makePick);renderPictures(goal());q('#makeComposer textarea,#makeComposer input:not([type=search])')?.focus();return;}
    if(e.target.closest('[data-make-repick]')){state.repicking=true;renderPictures(goal());q('[data-make-search="makePictures"]')?.focus();return;}
    if(e.target.closest('[data-make-keep-picture]')){state.repicking=false;renderPictures(goal());return;}
    const posePick=e.target.closest('[data-make-pose-pick]');if(posePick){const a=state.pictures?.find(x=>x.id===posePick.dataset.makePosePick);if(a){state.pose={asset:a};state.posePicking=false;renderGoalComposer(goal());q('[data-make-pose-change]')?.focus();}return;}
    if(e.target.closest('[data-make-pose-change]')){state.posePicking=true;renderGoalComposer(goal());q('[data-make-search="makePosePictures"]')?.focus();return;}
    if(e.target.closest('[data-make-style-words]')){state.styleWords=true;renderGoalComposer(goal());q('#makeF-look')?.focus();return;}
    if(e.target.closest('[data-make-style-pictures]')){state.styleWords=false;renderGoalComposer(goal());q('[data-make-style]')?.focus();return;}
    // A result's next step opens that picture goal here with the picture already chosen.
    const from=e.target.closest('[data-make-from]');if(from){const next=GOALS.find(x=>x.intent===from.dataset.makeFrom);if(!next)return;state.goal=next.id;state.compare=false;choosePicture(from.dataset.asset);remember();render();
      say(next.name+': your picture is chosen. Fill in what is asked, then press Generate.');(q('#makeComposer textarea,#makeComposer input')||q('#makeGenerate'))?.focus();return;}
    if(e.target.closest('[data-make-change]')){state.picking=true;renderLooks();q('.make-look.active [data-make-look]')?.focus();return;}
    if(e.target.closest('[data-make-keep-look]')){state.picking=false;renderLooks();q('#makeScene')?.focus();return;}
    const again=e.target.closest('[data-make-rerun],[data-make-another]');if(again){const run=state.runs.find(r=>r.job.id===(again.dataset.makeRerun||again.dataset.makeAnother));if(!run)return;
      state.goal=run.goal;state.look=run.lookId;state.picking=!!again.dataset.makeAnother;state.compare=false;
      // Edit and re-run brings the run's tune back with its look; another look starts from that look as made.
      if(!again.dataset.makeAnother){if(Array.isArray(run.tune?.rows)&&Array.isArray(run.tune.cleared)){state.tune[run.lookId]=structuredClone(run.tune);state.tuneOpen=state.tuneOpen||!!run.tuned;}else delete state.tune[run.lookId];}try{sessionStorage.setItem('studio.make.scene.'+run.goal,run.scene);}catch{}remember();render();
      const scene=q('#makeScene');if(scene&&!state.picking){scene.focus();scene.select();}else q('.make-look.active [data-make-look]')?.focus();return;}
    const verdict=e.target.closest('[data-make-review]');if(verdict){void review(verdict);return;}
    const polishing=e.target.closest('[data-make-polish]');if(polishing&&!polishing.disabled){void polishPicture(polishing);return;}
    if(e.target.closest('#makeGenerate'))void submit();
    if(e.target.closest('#makeEditor'))void openInEditor();
    if(e.target.closest('[data-make-retry]'))void load();
  });
  view.addEventListener('keydown',e=>{const radio=e.target.closest('[role="radio"]'),group=radio?.closest('[role="radiogroup"]');if(group&&['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){
    e.preventDefault();const items=[...group.querySelectorAll('[role="radio"]')],i=items.indexOf(radio),next=items[e.key==='Home'?0:e.key==='End'?items.length-1:(i+(['ArrowRight','ArrowDown'].includes(e.key)?1:items.length-1))%items.length],attr=next.hasAttribute('data-make-goal')?'data-make-goal':'data-make-look',value=next.getAttribute(attr);if(attr==='data-make-goal'){state.goal=value;state.pictures=null;remember();render();}else{state.look=value;state.picking=true;remember();renderLooks();}q('['+attr+'="'+value+'"]')?.focus();return;
  }if((e.target.id==='makeScene'||e.target.dataset.makeField)&&(e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();if(!e.repeat)void submit();}});
  // Generate is one button for every mode: a look, a compare, or a picture goal.
  const submit=()=>goal().intent?goalGenerate():state.compare?generateCompare():generate();
  let loaded=false;
  window.StudioMake={refresh(){if(!loaded){loaded=true;void load();}else render();}};
  if(!view.hidden)window.StudioMake.refresh();
})();
