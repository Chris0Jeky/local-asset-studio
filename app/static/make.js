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
  const state={goal:'character',look:null,looks:null,examples:{},error:'',busy:false,runs:[],pictures:null,lookRevision:{}};
  try{const saved=JSON.parse(localStorage.getItem('studio.make')||'{}');if(GOALS.some(g=>g.id===saved.goal))state.goal=saved.goal;if(typeof saved.look==='string')state.look=saved.look;}catch{}
  const remember=()=>{try{localStorage.setItem('studio.make',JSON.stringify({goal:state.goal,look:state.look}));}catch{}};
  const presets=()=>typeof catalog!=='undefined'&&catalog?.presets||[];
  const presetFor=look=>presets().find(p=>p.id===look?.body?.preset_id);
  const recipeOf=look=>{for(const l of look?.lineage||[]){const m=/^presets\/recipes\.json · (\S+)/.exec(l.evidence||'');if(m)return m[1];}return null;};
  const thumbOf=look=>{const r=recipeOf(look);return r&&state.examples[r]?.url||(look.anchor_asset_id?'/api/assets/'+encodeURIComponent(look.anchor_asset_id)+'/thumb':null);};
  const tried=look=>{const r=recipeOf(look),list=typeof atelierRecipes!=='undefined'?atelierRecipes:[];return list.find(x=>x.id===r)?.status==='executed';};
  const goal=()=>GOALS.find(g=>g.id===state.goal);
  const lookList=()=>{const g=goal();if(!g?.looks||!state.looks)return[];return g.looks.map(id=>state.looks.find(l=>l.id===id)).filter(l=>l&&!l.trashed_at);};
  const current=()=>state.looks?.find(l=>l.id===state.look&&!l.trashed_at)||null;
  // A family is named for what it means to the user: speed and the kind of picture, not the checkpoint.
  function speed(preset){const id=preset?.id||'';if(/krea/.test(id))return['slow','Slow · finest painting (several minutes)'];if(/zimage-fast|pixel|stylized|realvis/.test(id))return['fast','Fast'];return['fast','Fast · about half a minute'];}
  function blocker(look){if(look.usable===false)return look.unusable_reason||'This look cannot be used now.';const p=presetFor(look);if(!p)return'This look’s recipe is not in the library.';if(p.runtime_block)return p.runtime_block;const missing=typeof missingByPreset!=='undefined'&&missingByPreset[p.id];if(Array.isArray(missing)&&missing.length)return'Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first: open Models & setup.';return'';}

  view.innerHTML='<div class="make-heading"><span class="eyebrow">MAKE</span><h1 id="makeTitle" tabindex="-1">What are you making?</h1><p>Pick a goal, pick a look by its picture, describe your idea. The look brings the right model, adapters and settings.</p></div>'
    +'<div class="make-goals" role="radiogroup" aria-labelledby="makeTitle" id="makeGoals"></div>'
    +'<div id="makeBody"></div><section class="make-runs" aria-labelledby="makeRunsTitle"><div class="section-title"><h2 id="makeRunsTitle">Your pictures</h2><a href="/#assets">Open the library ↗</a></div><div id="makeRuns" class="make-run-list"></div></section>'
    +'<p class="make-advanced">Need every setting? <a href="/#create">Open the full editor</a> · <a href="/prompt-lab.html">Prompt Lab</a> · <a href="/#production">Compare settings side by side</a></p>';

  function renderGoals(){
    q('#makeGoals').innerHTML=GOALS.map((g,i)=>(i===5?'<span class="make-goal-break">From a picture you have</span>':'')+'<button type="button" role="radio" aria-checked="'+(g.id===state.goal)+'" data-make-goal="'+g.id+'"><b>'+escape(g.name)+'</b><small>'+escape(g.hint)+'</small></button>').join('');
  }
  function render(){renderGoals();const g=goal();if(g.intent)renderPictures(g);else renderLooks();renderRuns();}
  function renderLooks(){
    const body=q('#makeBody');
    if(state.error){body.innerHTML='<p class="make-error" role="alert">'+escape(state.error)+' <button type="button" data-make-retry>Try again</button></p>';return;}
    if(!state.looks){body.innerHTML='<p class="muted">Loading looks…</p>';return;}
    const list=lookList();if(!list.some(l=>l.id===state.look))state.look=null;
    const cards=list.map(l=>{const p=presetFor(l),[pace,label]=speed(p),thumb=thumbOf(l),why=blocker(l);return '<button type="button" class="make-look'+(l.id===state.look?' active':'')+'" data-make-look="'+escape(l.id)+'" aria-pressed="'+(l.id===state.look)+'">'
      +(thumb?'<img src="'+escape(thumb)+'" alt="" loading="lazy">':'<span class="make-look-blank" aria-hidden="true">✦</span>')
      +'<span class="make-look-text"><b>'+escape(l.name)+'</b><small class="make-pace '+pace+'">'+escape(label)+'</small>'+(tried(l)?'<small>Run on this PC before</small>':'')+(why?'<small class="make-warn">'+escape(why)+'</small>':'')+'</span></button>';}).join('');
    body.innerHTML='<div class="make-step"><span>1</span><h2>Choose a look</h2></div><div class="make-looks">'+cards+'</div><div id="makeComposer"></div>';
    renderComposer();
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
    const p=presetFor(look),why=blocker(look),example=look.body.scene_example||'',options=look.body.options||[];
    box.innerHTML='<div class="make-step"><span>2</span><h2>Describe your picture</h2></div><div class="make-composer"><div class="make-compose-main">'
      +'<label for="makeScene">'+escape(state.goal==='scene'?'Where is it, and what is there?':state.goal==='game'?'What is the item?':'Who or what, doing what, where?')+'</label>'
      +'<textarea id="makeScene" rows="4" maxlength="1000" placeholder="'+escape(example)+'"></textarea>'
      +'<div class="make-row">'+(example?'<button type="button" id="makeUseExample">Use the example</button>':'')+'<small>Plain words are fine. The look adds its own style and quality words.</small></div>'
      +options.map(o=>'<label class="make-check"><input type="checkbox" data-make-option="'+escape(o.id)+'"'+(o.default?' checked':'')+'> '+escape(o.label)+'</label>').join('')
      +'</div><div class="make-compose-side">'
      +'<label>Shape<select id="makeShape">'+Object.entries(SHAPES).map(([k,v])=>'<option value="'+k+'">'+v+(k==='design'?' · '+escape(look.body.controls.width||'')+'×'+escape(look.body.controls.height||''):'')+'</option>').join('')+'</select></label>'
      +'<label>How many<select id="makeCount"><option value="1">1 picture</option><option value="2">2 pictures</option><option value="4" selected>4 to choose from</option></select></label>'
      +'<label class="make-check"><input type="checkbox" id="makeNewSeed" checked> Different pictures each time</label>'
      +'<p id="makeEstimate" class="muted" aria-live="polite"></p>'
      +'<button type="button" id="makeGenerate" class="primary"'+(why?' disabled aria-describedby="makeWhy"':'')+'>Generate</button>'
      +(why?'<p id="makeWhy" class="make-warn">'+escape(why)+'</p>':'')
      +'<button type="button" id="makeEditor" class="make-link">Open in the full editor instead</button>'
      +'<details class="make-about"><summary>What this look uses</summary><p>'+escape(p?.name||look.body.preset_id)+'</p><p class="muted">'+escape(look.body.notes||'')+'</p></details>'
      +'</div></div><p id="makeStatus" class="make-status" role="status"></p>';
    const scene=q('#makeScene');try{scene.value=sessionStorage.getItem('studio.make.scene.'+look.id)||'';}catch{}
    scene.oninput=()=>{try{sessionStorage.setItem('studio.make.scene.'+look.id,scene.value);}catch{}};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    q('#makeShape').onchange=q('#makeCount').onchange=()=>estimate();estimate();
  }
  async function prepared(look){
    const scene=q('#makeScene').value.trim();if(!scene)throw Error('Describe your picture first, or press Use the example.');
    const options=Object.fromEntries([...view.querySelectorAll('[data-make-option]')].map(i=>[i.dataset.makeOption,i.checked]));
    const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options}:{}),expected_revision:look.revision});
    const p=presetFor(look),[w,h]=shapeSize(p,look,q('#makeShape').value),controls={...result.controls};
    if('width' in controls||p?.width)Object.assign(controls,{width:w,height:h});
    if(q('#makeNewSeed').checked&&(p?.seed||p?.bindings_extra?.seed))controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
    return{preset_id:result.preset_id,controls,batch_count:Number(q('#makeCount').value)};
  }
  let estimateEpoch=0;
  async function estimate(retry=false){
    const look=current(),out=q('#makeEstimate');if(!look||!out)return;const epoch=++estimateEpoch,p=presetFor(look),[w,h]=shapeSize(p,look,q('#makeShape').value);
    try{const e=await json('/api/estimate',{preset_id:look.body.preset_id,controls:{...look.body.controls,width:w,height:h},batch_count:Number(q('#makeCount').value),reference_count:0});if(epoch!==estimateEpoch||!out.isConnected)return;
      out.textContent=e.estimate_seconds?'About '+duration(e.estimate_seconds)+' in total, from earlier runs on this PC.':'No timing yet: this look has not run here at this size.';}
    catch{if(epoch===estimateEpoch&&!retry)setTimeout(()=>{if(epoch===estimateEpoch)estimate(true);},1500);}
  }
  const duration=s=>s<90?Math.round(s)+' s':Math.round(s/60)+' min';
  async function generate(){
    const look=current(),status=q('#makeStatus');if(!look||state.busy)return;state.busy=true;q('#makeGenerate').disabled=true;status.textContent='Preparing…';
    try{
      const request=await prepared(look);status.textContent='Sending to ComfyUI…';
      const job=await json('/api/jobs',{...request,label:'Make · '+look.name});
      state.runs.unshift({job,look:look.name});status.textContent='Started. Your pictures appear below as they finish; you can leave this page.';
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
  const timers=new Map();
  function poll(id){clearTimeout(timers.get(id));timers.set(id,setTimeout(async()=>{try{const job=await json('/api/jobs/'+encodeURIComponent(id));const run=state.runs.find(r=>r.job.id===id);if(run)run.job=job;renderRuns();if(!FINAL.includes(job.status))poll(id);else timers.delete(id);}catch{poll(id);}},2500));}
  function words(job){return({queued:'Waiting its turn',waiting:'Waiting for memory',submitting:'Sending',running:'Painting',observing:'Painting',completed:'Done',failed:'Did not finish',partial:'Some pictures did not finish',uncertain:'Outcome unknown: check Runs & review',cancelled:'Cancelled',not_submitted:'Not sent'})[job.status]||job.status;}
  function actions(job,output){
    const a=output.asset_id;if(!a)return'<small class="muted">Saving to the library…</small>';
    const vary=window.StudioWorkbench?.varyMarkup?.(job.preset_id,job.id,a)||'';
    const hand=(intent,label)=>'<button type="button" data-ux-handoff="'+escape(a)+'" data-ux-handoff-intent="'+intent+'">'+label+'</button>';
    return '<div class="make-actions">'+vary+hand('repair','Fix details or upscale')+'<button type="button" data-ux-open-asset="'+escape(a)+'">Review and keep</button>'
      +'<details class="make-more"><summary>More</summary>'+hand('edit','Change one thing')+hand('restyle','Restyle')+hand('combine','Put in a new pose')+hand('animate','Animate')+'</details></div>';
  }
  function renderRuns(){
    const box=q('#makeRuns');if(!box)return;
    const mine=state.runs,others=(typeof jobs!=='undefined'?jobs:[]).filter(j=>!mine.some(r=>r.job.id===j.id)&&j.outputs?.length&&!j.put_away).slice(0,mine.length?0:3).map(job=>({job,look:job.label||job.preset_name}));
    const list=[...mine,...others].slice(0,6);
    if(!list.length){box.innerHTML='<p class="muted">Pictures you make here show up in this space, with one-press next steps.</p>';return;}
    box.innerHTML=list.map(({job,look})=>'<article class="make-run"><header><b>'+escape(look)+'</b><span class="make-run-state '+escape(job.status)+'">'+escape(words(job))+'</span></header>'
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
  }
  view.addEventListener('click',e=>{
    const g=e.target.closest('[data-make-goal]');if(g){state.goal=g.dataset.makeGoal;remember();render();return;}
    const l=e.target.closest('[data-make-look]');if(l){state.look=l.dataset.makeLook;remember();renderLooks();q('#makeScene')?.focus();return;}
    if(e.target.closest('#makeGenerate'))void generate();
    if(e.target.closest('#makeEditor'))void openInEditor();
    if(e.target.closest('[data-make-retry]'))void load();
  });
  view.addEventListener('keydown',e=>{if(e.target.id==='makeScene'&&(e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();void generate();}});
  let loaded=false;
  window.StudioMake={refresh(){if(!loaded){loaded=true;void load();}else render();}};
  if(!view.hidden)window.StudioMake.refresh();
})();
