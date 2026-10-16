/* Make (owner ask, 15 Oct 2026): the goal-first way in. Pick what you are making, pick a look by its picture, type the
   scene, press Generate. A look is the existing Looks record (app/looks.py): recipe + adapters + wording with a {scene}
   slot, so the model dialect, quality tags and LoRA stack are the look's job, not the user's. Generate is the one press
   that submits (POST /api/looks/prepare, then POST /api/jobs); nothing runs on load. Picture goals hand a chosen picture
   to the existing continuation handoff (studio-workbench.js), which still ends on Create's own Generate. */
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
  const state={goal:'character',look:null,looks:null,examples:{},error:'',busy:false,runs:[],pictures:null,picking:false,review:{},polish:{},polishing:new Set(),tune:{},tuneOpen:false};
  try{const saved=JSON.parse(localStorage.getItem('studio.make')||'{}');if(GOALS.some(g=>g.id===saved.goal))state.goal=saved.goal;if(typeof saved.look==='string')state.look=saved.look;}catch{}
  const remember=()=>{try{localStorage.setItem('studio.make',JSON.stringify({goal:state.goal,look:state.look,runs:(restoredRuns?state.runs:[...state.runs,...savedRuns.map(({id,...r})=>({...r,job:{id}}))]).slice(0,6).map(({job,look,lookId,goal,scene,tune,tuned})=>({id:job.id,look,lookId,goal,scene,tune,tuned}))}));}catch{}};
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
  function blocker(look){const runtime=runtimeBlocker();if(runtime)return runtime;if(look.usable===false)return look.unusable_reason||'This look cannot be used now.';const p=tunedPreset(look);if(!p)return'This look’s recipe is not in the library.';if(p.runtime_block)return p.runtime_block;const missing=typeof missingByPreset!=='undefined'&&missingByPreset[p.id];if(Array.isArray(missing)&&missing.length)return'Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first: open Models & setup.';return'';}
  const blockerMarkup=(look,text)=>escape(text).replace('Models &amp; setup','<a href="/#models?need='+escape(encodeURIComponent(tunedPreset(look)?.id||look.body.preset_id))+'">Models &amp; setup</a>');

  // Tune this look (owner ask, 16 Oct 2026): see and change the look's model, adapters, steps, negative and seed without the
  // full editor. Folded shut by default. Tuning only changes the controls Generate sends: the server's allow-list, adapter
  // inventory and ranges still decide, and nothing here submits. A tune belongs to its look and travels with each run.
  const NAMED=k=>k+'_name',bound=(p,k)=>!!(p?.[k]||p?.bindings_extra?.[k]),byId=id=>presets().find(p=>p.id===id);
  const kb=()=>typeof knowledge!=='undefined'&&knowledge||{},entry=name=>name&&kb().loras?.[name]||null;
  const family=p=>p?.family||p?.name||p?.id||'';
  const short=name=>entry(name)?.label||String(name||'built-in adapter').replace(/\.safetensors$/,'');
  // Same model type = same loader node and text encoders on the same backend (app/looks.py model_of): the look's wording and
  // adapters carry over, so a switch never meets a graph that cannot take them; results will still differ.
  const kind=p=>p?.model?[p.model.loader,...p.model.encoders,p.backend_id||'primary'].join('|'):null;
  const textOnly=p=>(p.modality||'image')==='image'&&!!p.positive&&!p.reference&&!p.last_reference&&!p.reference_slots;
  function models(look){
    const p=presetFor(look),k=kind(p);if(!k)return[];const c=look.body.controls||{},seen=new Set([p.model.file]);
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
    if(target.closest('[data-tune-add]')){const t=tuneOf(look),input=q('#makeLoraSearch'),name=input?.value.trim(),slot=freeSlot(look,t),status=q('#makeStatus');
      if(!compatible(look).includes(name)){if(status)status.textContent=name?'Choose an adapter from the list: '+name+' is not an installed adapter for this model type.':'Type part of an adapter name, then choose it from the list.';input?.focus();return true;}
      if(!slot||t.rows.some(r=>r.name===name))return true;
      t.rows.push({slot,name,strength:clamp(entry(name)?.default??1),on:true,added:true});t.cleared=t.cleared.filter(s=>s!==slot);tuneChanged();q('[data-tune-strength="'+slot+'"]')?.focus();return true;}
    if(target.closest('[data-tune-reset]')){const reseed=state.tune[look.id]?.reseed??true;delete state.tune[look.id];tuneOf(look).reseed=reseed;tuneChanged();return true;}
    return false;
  }

  view.innerHTML='<div class="make-heading"><span class="eyebrow">MAKE</span><h1 id="makeTitle" tabindex="-1">What are you making?</h1><p>Pick a goal, pick a look by its picture, describe your idea. The look brings the right model, adapters and settings.</p></div>'
    +'<div class="make-goals" role="radiogroup" aria-labelledby="makeTitle" id="makeGoals"></div>'
    +'<div id="makeSplit" class="make-split"><div id="makeBody"></div><section class="make-runs" aria-labelledby="makeRunsTitle"><div class="section-title"><h2 id="makeRunsTitle">Your pictures</h2><a href="/#assets">Open the library ↗</a></div><div id="makeRuns" class="make-run-list"></div></section></div>'
    +'<p class="make-advanced">Need every setting? <a href="/#create">Open the full editor</a> · <a href="/prompt-lab.html">Prompt Lab</a> · <a href="/#production">Compare settings side by side</a></p>';

  function renderGoals(){
    q('#makeGoals').innerHTML=GOALS.map((g,i)=>(i===5?'<span class="make-goal-break">From a picture you have</span>':'')+'<button type="button" role="radio" aria-checked="'+(g.id===state.goal)+'" data-make-goal="'+g.id+'"><b>'+escape(g.name)+'</b><small>'+escape(g.hint)+'</small></button>').join('');
  }
  // Once a look is chosen the gallery folds to one line and the results sit beside the words, so Generate and its pictures share a screen.
  function layout(){const focused=!goal().intent&&!!current()&&!state.picking;q('#makeSplit').classList.toggle('make-has-look',focused);view.classList.toggle('make-focused',focused);}
  function render(){renderGoals();const g=goal();if(g.intent)renderPictures(g);else renderLooks();renderRuns();layout();}
  function renderLooks(){
    const body=q('#makeBody');
    if(state.error){body.innerHTML='<p class="make-error" role="alert">'+escape(state.error)+' <button type="button" data-make-retry>Try again</button></p>';return;}
    if(!state.looks){body.innerHTML='<p class="muted">Loading looks…</p>';return;}
    const list=lookList();if(!list.some(l=>l.id===state.look))state.look=null;
    const cards=list.map(l=>{const p=presetFor(l),[pace,label]=speed(p),thumb=thumbOf(l),why=blocker(l);return '<article class="make-look'+(l.id===state.look?' active':'')+'"><button type="button" class="make-look-select" data-make-look="'+escape(l.id)+'" aria-pressed="'+(l.id===state.look)+'">'
      +(thumb?'<img src="'+escape(thumb)+'" alt="" loading="lazy">':'<span class="make-look-blank" aria-hidden="true">✦</span>')
      +'<span class="make-look-text"><b>'+escape(l.name)+'</b><small class="make-pace '+pace+'">'+escape(label)+'</small>'+(tried(l)?'<small>Run on this PC before</small>':'')+'</span></button>'+(why?'<small class="make-warn make-look-text">'+blockerMarkup(l,why)+'</small>':'')+'</article>';}).join('');
    const chosen=current();
    if(chosen&&!state.picking){const p=presetFor(chosen),thumb=thumbOf(chosen);
      body.innerHTML='<div class="make-chosen">'+(thumb?'<img src="'+escape(thumb)+'" alt="">':'<span class="make-look-blank" aria-hidden="true">✦</span>')+'<div><small>Look</small><b>'+escape(chosen.name)+'</b><small class="make-pace '+speed(p)[0]+'">'+escape(speed(p)[1])+'</small></div><button type="button" data-make-change>Change look</button></div><div id="makeComposer"></div>';}
    else body.innerHTML='<div class="make-step"><span>1</span><h2>Choose a look</h2>'+(chosen?'<button type="button" class="make-link" data-make-keep-look>Keep '+escape(chosen.name)+'</button>':'')+'</div><div class="make-looks">'+cards+'</div><div id="makeComposer"></div>';
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
    const box=q('#makeComposer'),look=current();if(!box)return;
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
      +'</div></div><p id="makeStatus" class="make-status" role="status"></p>';
    const scene=q('#makeScene');try{scene.value=sessionStorage.getItem('studio.make.scene.'+state.goal)||'';}catch{}
    scene.oninput=()=>{try{sessionStorage.setItem('studio.make.scene.'+state.goal,scene.value);}catch{}};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    q('#makeShape').onchange=q('#makeCount').onchange=()=>estimate();estimate();
    const strength=q('#makeStrength');if(strength)strength.oninput=()=>{q('#makeStrengthOut').textContent=strength.value+'%';};
    q('#makeNewSeed').onchange=e=>{tuneOf(look).reseed=e.target.checked;tuneChanged();};
    q('#makeTune').ontoggle=e=>{state.tuneOpen=e.target.open;};
    const kept=state.tune[look.id]?.composer;if(kept){delete state.tune[look.id].composer;
      const set=(el,v)=>{if(el&&v!=null&&[...(el.options||[{value:String(v)}])].some(o=>o.value===String(v)))el.value=String(v);};set(q('#makeShape'),kept.shape);set(q('#makeCount'),kept.count);
      if(strength&&kept.strength!=null){strength.value=kept.strength;strength.oninput();}
      for(const box of view.querySelectorAll('[data-make-option]'))if(typeof kept.options?.[box.dataset.makeOption]==='boolean')box.checked=kept.options[box.dataset.makeOption];
      q('#makeStatus').textContent='That run\u2019s settings are back'+(tuneOf(look).reseed?'':', with its seed locked')+'. Change the words or a setting, then press Generate.';estimate();}
    renderTune();
  }
  async function prepared(look){
    // Every form value is read before the first await: a click on another look mid-request must not change this one.
    const scene=q('#makeScene').value.trim();if(!scene)throw Error('Describe your picture first, or press Use the example.');
    const options=Object.fromEntries([...view.querySelectorAll('[data-make-option]')].map(i=>[i.dataset.makeOption,i.checked]));
    const p=presetFor(look),[w,h]=shapeSize(p,look,q('#makeShape').value),reseed=q('#makeNewSeed').checked,batch_count=Number(q('#makeCount').value),scale=Number(q('#makeStrength')?.value??100)/100;
    const t={...structuredClone(tuneOf(look)),reseed};if(!reseed&&t.seed!=null&&!(Number.isSafeInteger(t.seed)&&t.seed>=0))throw Error('The seed must be a whole number, 0 or more.');
    const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options}:{}),expected_revision:look.revision});
    const controls={...result.controls};
    if('width' in controls||p?.width)Object.assign(controls,{width:w,height:h});
    if(reseed&&(p?.seed||p?.bindings_extra?.seed))controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
    else if(t.seed!=null&&(p?.seed||p?.bindings_extra?.seed))controls.seed=t.seed;
    // Style strength scales the tuned adapters; two decimals, inside the server's 0-2 adapter range.
    const preset_id=applyTune(controls,look,t,scale),tuned=tuneSummary(look,t);
    // The run keeps its own settings, seed locked, so Edit and re-run changes only what you change next.
    const composer={shape:q('#makeShape').value,count:batch_count,strength:q('#makeStrength')?.value??null,options};
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
  async function generate(){
    const look=current(),status=q('#makeStatus');if(!look||state.busy)return;
    const why=blocker(look);if(why){status.textContent=why;return;}
    state.busy=true;q('#makeGenerate').disabled=true;status.textContent='Preparing…';
    try{
      const request=await prepared(look);status.textContent='Sending to ComfyUI…';
      const {scene,tune,tuned,...submit}=request;const job=await json('/api/jobs',{...submit,label:'Make · '+look.name});
      state.runs.unshift({job,look:look.name,lookId:look.id,goal:state.goal,scene,tune,tuned});remember();status.textContent='Started. Your pictures appear below as they finish; you can leave this page.';
      renderRuns();poll(job.id);
      if(typeof refresh==='function')void refresh();
    }catch(error){status.textContent=error.message;status.classList.add('make-warn');setTimeout(()=>status.classList.remove('make-warn'),4000);}
    finally{state.busy=false;const button=q('#makeGenerate');if(button)button.disabled=!!blocker(look);}
  }
  async function openInEditor(){
    const look=current(),status=q('#makeStatus');if(!look)return;
    try{const request=await prepared(look);applySaved({preset:request.preset_id,controls:request.controls,batch_count:request.batch_count,parent_assets:[],references:[]},{});showView('create');}
    catch(error){status.textContent=error.message;}
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
      if(status)status.textContent=value==='selected'?'Kept. Your keepers are in the library under Keepers.':value==='rejected'?'Marked: not this one.':'Decision cleared.';}
    catch(error){button.disabled=false;if(status)status.textContent='Could not save that: '+error.message;}
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
  function actions(job,output){
    const a=output.asset_id;if(!a)return'<small class="muted">Saving to the library…</small>';
    const vary=window.StudioWorkbench?.varyMarkup?.(job.preset_id,job.id,a)||'';
    const hand=(intent,label)=>'<button type="button" data-ux-handoff="'+escape(a)+'" data-ux-handoff-intent="'+intent+'">'+label+'</button>';
    const review=reviewOf(a),mark=(value,label)=>'<button type="button" data-make-review="'+value+'" data-asset="'+escape(a)+'" aria-pressed="'+(review===value)+'">'+label+'</button>';
    const polish=kind=>{const plan=state.polish[a+':'+kind],why=plan&&!plan.ok?plan.reason:'',busy=state.polishing.has(a+':'+kind);
      return '<button type="button" data-make-polish="'+kind+'" data-asset="'+escape(a)+'"'+(why||busy?' disabled':'')+(why?' title="'+escape(why)+'"':'')+'>'+POLISH[kind]+(plan?.seconds?' <small>~'+duration(plan.seconds)+'</small>':'')+(busy?' …':'')+'</button>';};
    return '<div class="make-actions">'+mark('selected','\u2605 Keep')+mark('rejected','Not this')+vary+polish('face')+polish('details')+polish('upscale')
      +'<details class="make-more"><summary>More</summary><button type="button" data-ux-open-asset="'+escape(a)+'">Open full size</button>'+hand('repair','Other fixes\u2026')+hand('edit','Change one thing')+hand('restyle','Restyle')+hand('combine','Put in a new pose')+hand('animate','Animate')+'</details></div>';
  }
  // Polish plans only read (studio-workbench.js polishPlan); each picture is asked once per kind.
  const planning=new Set();
  function planPolish(list){
    const api=window.StudioWorkbench;if(!api?.polishPlan)return;
    for(const {job} of list)for(const o of job.outputs||[])if(o.asset_id&&(!o.media_type||o.media_type==='image'))for(const kind of Object.keys(POLISH)){
      const key=o.asset_id+':'+kind;if(planning.has(key))continue;planning.add(key);
      api.polishPlan(o.asset_id,kind).then(plan=>{state.polish[key]=plan;scheduleRuns();},error=>{state.polish[key]={ok:false,reason:error.message};planning.delete(key);setTimeout(()=>{delete state.polish[key];scheduleRuns();},15000);scheduleRuns();});}
  }
  let runsFrame=0;const scheduleRuns=()=>{if(!runsFrame)runsFrame=requestAnimationFrame(()=>{runsFrame=0;renderRuns();});};
  async function polishPicture(button){
    const id=button.dataset.asset,kind=button.dataset.makePolish,key=id+':'+kind,status=q('#makeStatus');if(state.polishing.has(key))return;
    const source=state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===id));state.polishing.add(key);renderRuns();
    try{const job=await window.StudioWorkbench.polish(id,kind);state.runs.unshift({job,look:POLISH[kind]+(source?' \u00b7 '+source.look:''),lookId:source?.lookId,goal:source?.goal,scene:null});remember();poll(job.id);
      if(status)status.textContent=POLISH[kind]+' started. The result appears at the top of your pictures.';}
    catch(error){if(status)status.textContent=error.message;}
    finally{state.polishing.delete(key);renderRuns();}
  }
  function renderRuns(){
    const box=q('#makeRuns');if(!box)return;
    const mine=state.runs,others=(typeof jobs!=='undefined'?jobs:[]).filter(j=>!mine.some(r=>r.job.id===j.id)&&j.outputs?.length&&!j.put_away).slice(0,mine.length?0:3).map(job=>({job,look:job.label||job.preset_name}));
    const list=[...mine,...others].slice(0,6);planPolish(list);
    if(!list.length){box.innerHTML='<p class="muted">Pictures you make here show up in this space, with one-press next steps.</p>';return;}
    box.innerHTML=list.map(({job,look,scene,tuned})=>'<article class="make-run"><header><div><b>'+escape(look)+'</b>'+(scene?'<small>'+escape(scene)+'</small>':'')+(tuned?'<small class="make-tuned">'+escape(tuned)+'</small>':'')+'</div><span class="make-run-state '+escape(job.status)+'">'+escape(words(job))+'</span></header>'
      +(scene?'<div class="make-run-tools"><button type="button" data-make-rerun="'+escape(job.id)+'">Edit and re-run</button><button type="button" data-make-another="'+escape(job.id)+'">Same words, another look</button></div>':'')
      +(job.status==='failed'&&job.message?'<p class="make-warn">'+escape(job.message)+'</p>':'')
      +'<div class="make-outputs">'+(job.outputs||[]).map((o,i)=>(o.media_type&&o.media_type!=='image')?'':'<figure>'+(o.asset_id?'<button type="button" class="make-open" data-ux-open-asset="'+escape(o.asset_id)+'" aria-label="Open picture '+(i+1)+' full size">':'')+'<img src="/api/image/'+encodeURIComponent(job.id)+'/'+i+'" alt="Picture '+(i+1)+' from '+escape(look)+'" loading="lazy">'+(o.asset_id?'</button>':'')+actions(job,o)+'</figure>').join('')
      +(FINAL.includes(job.status)?'':Array.from({length:Math.max(0,(job.batch_count||1)-(job.outputs||[]).length)},()=>'<figure class="make-pending" aria-hidden="true"><span></span></figure>').join(''))+'</div></article>').join('');
  }
  async function renderPictures(g){
    const body=q('#makeBody');
    body.innerHTML='<div class="make-step"><span>1</span><h2>Pick the picture</h2></div><p class="make-hint">'+escape(g.name)+': choose one of your pictures. The next screen suggests the best recipe for it and keeps your picture as the source. <a href="/#assets">Import a picture</a> first if it is not here.</p><div id="makePictures" class="make-pictures"><p class="muted">Loading your pictures…</p></div>';
    try{if(!state.pictures){const data=await json('/api/workspace');state.pictures=(data.assets||[]).filter(a=>a.media_type==='image'&&!a.trashed_at).sort((a,b)=>(b.created_at||0)-(a.created_at||0)).slice(0,24);}
      if(goal()!==g)return;const box=q('#makePictures');
      box.innerHTML=state.pictures.length?state.pictures.map(a=>'<button type="button" data-ux-handoff="'+escape(a.id)+'" data-ux-handoff-intent="'+g.intent+'"><img src="/api/assets/'+encodeURIComponent(a.id)+'/thumb" alt="" loading="lazy"><small>'+escape(a.title||'Picture')+'</small></button>').join(''):'<p class="muted">No pictures yet. Make one first, or import one in the library.</p>';}
    catch(error){if(goal()===g)q('#makePictures').innerHTML='<p class="make-error">'+escape(error.message)+'</p>';}
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
    // With no Make runs yet, recent pictures come from the job list app.js loads; wait for it briefly.
    for(let i=0;i<40&&!state.runs.length&&!(typeof jobs!=='undefined'&&jobs.length);i++)await new Promise(r=>setTimeout(r,250));
    renderRuns();
  }
  view.addEventListener('input',e=>{if(e.target.closest('#makeTune'))tuneInput(e.target);});
  view.addEventListener('click',e=>{
    if(e.target.closest('#makeTune')&&tuneClick(e.target))return;
    const g=e.target.closest('[data-make-goal]');if(g){state.goal=g.dataset.makeGoal;state.pictures=null;remember();render();return;}
    const l=e.target.closest('[data-make-look]');if(l){state.look=l.dataset.makeLook;state.picking=false;remember();renderLooks();q('#makeScene')?.focus();return;}
    if(e.target.closest('[data-make-change]')){state.picking=true;renderLooks();q('.make-look.active [data-make-look]')?.focus();return;}
    if(e.target.closest('[data-make-keep-look]')){state.picking=false;renderLooks();q('#makeScene')?.focus();return;}
    const again=e.target.closest('[data-make-rerun],[data-make-another]');if(again){const run=state.runs.find(r=>r.job.id===(again.dataset.makeRerun||again.dataset.makeAnother));if(!run)return;
      state.goal=run.goal;state.look=run.lookId;state.picking=!!again.dataset.makeAnother;
      // Edit and re-run brings the run's tune back with its look; another look starts from that look as made.
      if(!again.dataset.makeAnother){if(Array.isArray(run.tune?.rows)&&Array.isArray(run.tune.cleared)){state.tune[run.lookId]=structuredClone(run.tune);state.tuneOpen=state.tuneOpen||!!run.tuned;}else delete state.tune[run.lookId];}try{sessionStorage.setItem('studio.make.scene.'+run.goal,run.scene);}catch{}remember();render();
      const scene=q('#makeScene');if(scene&&!state.picking){scene.focus();scene.select();}else q('.make-look.active [data-make-look]')?.focus();return;}
    const verdict=e.target.closest('[data-make-review]');if(verdict){void review(verdict);return;}
    const polishing=e.target.closest('[data-make-polish]');if(polishing&&!polishing.disabled){void polishPicture(polishing);return;}
    if(e.target.closest('#makeGenerate'))void generate();
    if(e.target.closest('#makeEditor'))void openInEditor();
    if(e.target.closest('[data-make-retry]'))void load();
  });
  view.addEventListener('keydown',e=>{if(e.target.id==='makeScene'&&(e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();if(!e.repeat)void generate();}});
  let loaded=false;
  window.StudioMake={refresh(){if(!loaded){loaded=true;void load();}else render();}};
  if(!view.hidden)window.StudioMake.refresh();
})();
