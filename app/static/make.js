/* Make (owner ask, 15 Oct 2026): the goal-first way in. Pick what you are making, pick a look by its picture, type the
   scene, press Generate. A look is the existing Looks record (app/looks.py): recipe + adapters + wording with a {scene}
   slot, so the model dialect, quality tags and LoRA stack are the look's job, not the user's. Generate is the one press
   that submits (POST /api/looks/prepare, then POST /api/jobs); nothing runs on load. Picture goals stay in Make (16 Oct 2026):
   pick the picture, fill a short composer, press the same Generate; the request is the continuation the handoff prepares. */
(function(){
  'use strict';
  const view=document.querySelector('#makeView');if(!view)return;
  const q=s=>view.querySelector(s),escape=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const creationPrivacy=()=>window.StudioPrivacy?.creation?.()==='private'?'private':'regular',readScope=()=>window.StudioPrivacy?.scope?.()||'regular';
  const privateKey=(key,privacy=creationPrivacy())=>privacy==='private'?key+'.private':key,storedIn=privacy=>privacy==='private'?sessionStorage:localStorage;
  // Private wording, tunes, redo and remembered fills never enter shared persistent browser storage.
  const makeStorage={getItem:key=>storedIn(creationPrivacy()).getItem(privateKey(key)),setItem:(key,value)=>storedIn(creationPrivacy()).setItem(privateKey(key),value),removeItem:key=>storedIn(creationPrivacy()).removeItem(privateKey(key)),
    get length(){return storedIn(creationPrivacy()).length;},key:index=>{const key=storedIn(creationPrivacy()).key(index);return creationPrivacy()==='private'?(key?.endsWith('.private')?key.slice(0,-8):null):key;}};
  const requestPrivacy=(scope=readScope(),privacy=creationPrivacy())=>({...window.StudioPrivacy?.capture?.(),scope,privacy});
  const privacyFetch=(path,options={},captured=requestPrivacy())=>{const headers={...options.headers,'X-Studio-Privacy':captured.scope};if((options.method||'GET')!=='GET')headers['X-Studio-Creation-Privacy']=captured.privacy;
    return (window.StudioPrivacy?.fetch?.bind(window.StudioPrivacy)||fetch)(path,{...options,headers});};
  const json=async(path,body,captured=requestPrivacy())=>{const r=await privacyFetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},captured);const data=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(Error(data.error||data.message||('Request failed ('+r.status+')')),{status:r.status,code:data.code});return data;};
  const classified=value=>value?.privacy==='private'?'private':'regular',runPrivacy=run=>classified(run.job?.privacy?run.job:run),inScope=value=>readScope()==='all'||classified(value)===readScope();
  const privateMedia=(url,privacy)=>privacy==='private'?url+(url.includes('?')?'&':'?')+'privacy=private':url;
  const usePrivacy=value=>{if(classified(value)==='private'&&creationPrivacy()!=='private'){say('This picture is private. Choose Private for this creation before continuing.');return false;}return true;};
  let privacyEpoch=0,draftRevision=0,draftReady=false,draftProblem='';
  // Curated, not generated: a goal lists looks by id in the order a newcomer should meet them (proven first, slow last).
  const GOALS=[
    {id:'character',name:'Anime character',hint:'A person or creature, drawn',looks:['look-oneobsession-anima-v20-showcase','look-pearly-anima-mix-v10-showcase','look-anima-pearly-petiflow','look-anifox-ringeko','look-wai-fantasy-portrait','look-anima-fantasy-portrait','look-animagine-fantasy-portrait']},
    {id:'scene',name:'Scene or background',hint:'A place, no main character',looks:['look-night-shift-retro-anime','look-noob-fantasy-scene','look-krea-watercolor-anime']},
    {id:'painting',name:'Painted illustration',hint:'Oil, ink, watercolour, book cover',looks:['look-anima-painterly-artist-tags','look-krea-style-emerald-tarot','look-krea-style-inkwork-darkbrush','look-krea-style-airy-softwatercolor','look-krea-oil-fantasy','look-krea-atelier-target-stack','look-krea-witch-nijisis']},
    {id:'photo',name:'Photo',hint:'Realistic people, places, products',looks:['look-preset-zimage-fast','look-preset-realvis','look-krea-realistic-snapshot','look-krea-lenovo-ultrareal']},
    {id:'game',name:'Game item or icon',hint:'Props, pixel art',looks:['look-zimage-game-icon','look-preset-stylized-prop','look-preset-pixel-lora']},
    {id:'edit',name:'Change a picture',hint:'Keep it, change one thing',intent:'edit'},
    {id:'repair',name:'Fix or upscale',hint:'Faces, hands, resolution',intent:'repair'},
    {id:'restyle',name:'Restyle a picture',hint:'Same picture, another look',intent:'restyle'},
    {id:'combine',name:'Character in a new pose',hint:'Two pictures in, one out',intent:'combine'},
    {id:'animate',name:'Animate a picture',hint:'A short clip from a still',intent:'animate'},
    {id:'mesh',name:'Picture to 3D',hint:'A draft model to inspect',intent:'mesh'},
  ];
  const SHAPES={design:'As designed',portrait:'Portrait',landscape:'Landscape',square:'Square'};
  // Audit #21: a goal's usual picture shape, preselected when the look can be reshaped; other goals follow the look's own design.
  const SHAPE_FOR={character:'portrait',scene:'landscape',game:'square'};
  // Lab evidence (docs/looks/LOOK-LAB-2026-10-16.md on branch lab/look-qualification-20261016): looks whose two lab runs were both
  // judged keep, with the median score. Agent judgement on this PC, not art acceptance; update this map from the lab doc, not by hand.
  // Round 7 (docs/looks/LOOK-LAB-2026-10-19.md, PR #1563): the One Obsession and Pearly Anima mixes kept 12 of 12 each (3 scenes x 4 seeds, adult
  // characters), so they lead the Anime character goal; Petiflow (Anima base) follows, as Anima-base close-up faces read youthful in that lab.
  // Kept in at least 3 of 4 test pictures, or 2 of 2 where only two were made (docs/looks/LOOK-LAB-2026-10-16.md, rounds 1-2; the game icon is round 4, PR #1488: potion and sword, one seed each).
  const TESTED={'look-oneobsession-anima-v20-showcase':'12 of 12 (19 Oct, round 7)','look-pearly-anima-mix-v10-showcase':'12 of 12 (19 Oct, round 7)','look-anima-pearly-petiflow':'4 of 4','look-anima-painterly-artist-tags':'2 of 2','look-night-shift-retro-anime':'3 of 4','look-krea-watercolor-anime':'2 of 2','look-krea-oil-fantasy':'2 of 2','look-krea-style-inkwork-darkbrush':'2 of 2','look-krea-realistic-snapshot':'2 of 2','look-krea-lenovo-ultrareal':'2 of 2'};
  const tested=l=>TESTED[l.id]?'<small class="make-tested" title="'+escape(TESTED[l.id]+' test pictures on this PC were kept (16 Oct 2026 unless dated; judged by an agent, not art approval).')+'">Tested well</small>':'';
  // Best for (lab rounds 1-2, docs/looks/LOOK-LAB-2026-10-16.md "Ranked best look per goal" and R3): what each tested look carried.
  // Kept here, not in presets/looks.json, because a look body takes only the fields app/looks.py allows.
  const BEST_FOR={'look-oneobsession-anima-v20-showcase':'Adult characters in costume; leans to revealing cuts, so name what is covered','look-pearly-anima-mix-v10-showcase':'Adult characters in costume, props held as written','look-anima-pearly-petiflow':'Close-ups and upper-body portraits holding one thing','look-anifox-ringeko':'A character holding an animal, readable faces; avoid books and lettering','look-night-shift-retro-anime':'Quiet, empty interiors with a few named props','look-anima-painterly-artist-tags':'A painted travel scene with one figure, quickly','look-krea-watercolor-anime':'Airy painted scenes','look-krea-style-inkwork-darkbrush':'Black-and-white buildings and interiors','look-krea-oil-fantasy':'Dark, colourful fantasy places','look-krea-style-airy-softwatercolor':'Pale flowery rooms; avoid written labels','look-krea-lenovo-ultrareal':'Natural phone-photo people and rooms','look-zimage-game-icon':'One item on white; check shape details'};
  const bestFor=l=>BEST_FOR[l.id]?'<small class="make-best">Best for: '+escape(BEST_FOR[l.id])+'</small>':'';
  // Recorded, never inferred: only a recipe whose own commercial_note names non-commercial terms (presets/catalog.json) is tagged.
  const nonCommercial=p=>/non-?commercial|prohibit commerciali/i.test(p?.commercial_note||'');
  const licence=p=>nonCommercial(p)?'<small class="make-licence" title="'+escape(p.commercial_note)+'">Non-commercial</small>':'';
  const FINAL=['completed','failed','partial','uncertain','not_submitted','cancelled','abandoned'];
  const POLISH={face:'Fix face',details:'Fix hands and details',refine:'Refine 1.5\u00d7',upscale:'Upscale 2\u00d7'};
  const state={selected:{},goal:'character',look:null,looks:null,examples:{},error:'',busy:false,status:'',missing:'',runs:[],pictures:null,picking:false,review:{},polish:{},polishing:new Set(),varying:new Set(),varyHeld:new Set(),tune:{},tuneOpen:false,pick:null,repicking:false,queries:{},form:{},fix:'face',styleLook:null,styleWords:false,poseMode:'picture',poseRoute:'copy',pose:null,posePicking:false,compare:false,compareLooks:[],sweeps:{},characters:[],character:null,allPictures:false,charSave:null,charEdit:null,charMigrate:null,charStale:false,charForm:{},openers:new Set(),noteGone:false};
  // Round 5 (#1492): Anima pictures send Fix face and Fix hands to one WAI face-then-hand repaint, so they are one button, and say what that costs.
  const MERGED='Fix face and hands',FIX_HINT='Repaints with a WAI model and can change this look’s face finish — keep the original and compare.',UP_HINT='Smooths fine texture; upscale the version you chose.',REFINE_HINT='Refine redraws lightly at 1.5\u00d7: on the 19 Oct lab picture it kept the face and added eye and lash detail. Compare with the original; upscale last.';
  const merged=id=>{const f=state.polish[id+':face'],d=state.polish[id+':details'];return !!(f?.ok&&d?.ok&&f.preset_id&&f.preset_id===d.preset_id);};
  const polishName=(id,kind)=>kind==='face'&&merged(id)?MERGED:POLISH[kind];
  const polishKinds=id=>Object.keys(POLISH).filter(k=>!(k==='details'&&merged(id)));
  try{const saved=JSON.parse(makeStorage.getItem('studio.make')||'{}');if(GOALS.some(g=>g.id===saved.goal))state.goal=saved.goal;if(typeof saved.look==='string')state.look=saved.look;}catch{}
  const observing=run=>run.lost||!FINAL.includes(run.job.status)||run.job.status==='uncertain'&&run.job.tracking_disposition?.status!=='stopped';
  // Keep the newest six cards, plus every card still being observed; a Compare stays whole, including in storage.
  const runCards=runs=>{const cards=[],groups=new Map();for(const run of runs){let card=run.group&&groups.get(run.group);
    if(!card){card={group:run.group||null,id:run.group||run.job.id,runs:[]};cards.push(card);if(run.group)groups.set(run.group,card);}card.runs.push(run);}
    // Unfinished cards stay past the six, but at most 20 of them, so a run stuck 'uncertain' cannot grow history without bound.
    let extra=0;return cards.filter((c,i)=>i<6||c.runs.some(observing)&&extra++<20);};
  const remember=()=>{try{const runs=restoredRuns?state.runs:[...state.runs,...savedRuns.map(({id,status,tracking_disposition,...r})=>({...r,job:{id,status,tracking_disposition}}))];
    for(const privacy of ['regular','private']){if(privacy!==creationPrivacy()&&!runs.some(r=>runPrivacy(r)===privacy))continue;const storage=storedIn(privacy),key=privateKey('studio.make',privacy),saved=JSON.parse(storage.getItem(key)||'{}'),observed=runs.filter(r=>runPrivacy(r)===privacy);
      // A scope filter is not a deletion: retain stored cards this observation did not request.
      const retained=readScope()==='all'||readScope()===privacy?[]:(saved.runs||[]).filter(r=>!observed.some(x=>x.job.id===r.id)).map(({id,status,tracking_disposition,...r})=>({...r,job:{id,status,tracking_disposition,privacy}}));
      storage.setItem(key,JSON.stringify({goal:privacy===creationPrivacy()?state.goal:saved.goal,look:privacy===creationPrivacy()?state.look:saved.look,
        runs:runCards([...observed,...retained]).flatMap(c=>c.runs).map(({job,look,lookId,goal,scene,tune,tuned,group,axis,value,title,fills,redo,lost})=>({id:job.id,status:job.status,tracking_disposition:job.tracking_disposition,privacy,look,lookId,goal,scene,tune,tuned,group,axis,value,title,fills,redo,lost}))}));}}catch{}rememberDraft();};
  const readSavedRuns=()=>{const runs=[];for(const privacy of (readScope()==='all'?['regular','private']:[readScope()]))try{const saved=JSON.parse(storedIn(privacy).getItem(privateKey('studio.make',privacy))||'{}');if(Array.isArray(saved.runs))runs.push(...saved.runs.filter(r=>r&&typeof r.id==='string'&&classified(r)===privacy));}catch{}return runs;};
  let restoredRuns=false,savedRuns=readSavedRuns();
  const presets=()=>typeof catalog!=='undefined'&&catalog?.presets||[];
  const presetFor=look=>presets().find(p=>p.id===look?.body?.preset_id);
  const recipeOf=look=>{for(const l of look?.lineage||[]){const m=/^presets\/recipes\.json · (\S+)/.exec(l.evidence||'');if(m)return m[1];}return null;};
  // Preset-derived looks have no recipe example; their pictures are the 15 Oct 2026 proof renders (examples/make-looks-20261015).
  const PROOF_THUMBS=['look-preset-stylized-prop','look-preset-pixel-lora','look-preset-realvis','look-preset-zimage-fast'];
  const thumbOf=look=>{const r=recipeOf(look);return r&&state.examples[r]?.url||(look.anchor_asset_id?privateMedia('/api/assets/'+encodeURIComponent(look.anchor_asset_id)+'/thumb',classified(look)):PROOF_THUMBS.includes(look.id)?'/api/examples/make-looks-20261015/'+look.id+'.jpg':null);};
  const tried=look=>{const r=recipeOf(look),list=typeof atelierRecipes!=='undefined'?atelierRecipes:[];return list.find(x=>x.id===r)?.status==='executed';};
  // The owner's own Keep / Not this marks on pictures made with a look (#1699, GET /api/looks/record); the slot lets a fresh mark redraw only this line.
  const recordLine=l=>{const r=state.record?.[l?.id],kept=r?.kept||0,no=r?.not_this||0,parts=[kept&&kept+' kept',no&&no+' not this'].filter(Boolean);return parts.length?'<small class="make-record" title="Your Keep and Not this marks on pictures made with this look in this Studio">Your marks: '+parts.join(' · ')+'</small>':'';};
  const recordSlot=l=>'<span data-make-record="'+escape(l.id)+'">'+recordLine(l)+'</span>';
  const refreshRecord=async()=>{const epoch=privacyEpoch;try{const r=await json('/api/looks/record');if(epoch!==privacyEpoch)return;state.record=r.looks||{};for(const el of view.querySelectorAll('[data-make-record]'))el.innerHTML=recordLine({id:el.dataset.makeRecord});}catch{if(epoch===privacyEpoch)state.record={};}};
  const goal=()=>GOALS.find(g=>g.id===state.goal);
  const SLOTS=['lora','lora2','lora3','lora4','lora5','lora6'];
  // The look's active adapters: a strength above zero with a file. Style strength scales exactly these and nothing else.
  const adapters=look=>{const c=look?.body?.controls||{},p=presetFor(look),bound=k=>!!(p?.[k]||p?.bindings_extra?.[k]);
    return SLOTS.filter(k=>Number(c[k])>0&&(typeof c[k+'_name']==='string'&&c[k+'_name']||p&&!bound(k+'_name'))).map(k=>({key:k,name:c[k+'_name']||'the recipe’s own LoRA',strength:Number(c[k])}));};
  const lookList=()=>{const g=goal();if(!g?.looks||!state.looks)return[];return g.looks.map(id=>state.looks.find(l=>l.id===id)).filter(l=>l&&!l.trashed_at);};
  const current=()=>state.looks?.find(l=>l.id===state.look&&!l.trashed_at)||null;
  // Honest speed (#1448): median seconds per picture measured in the 16 Oct look lab (docs/looks/LOOK-LAB-2026-10-16.md, R1 table,
  // "Median s/image": load, encode, sample and decode on this PC; two pictures each, cold and warm mixed). Update from the doc, not by hand.
  const LAB_SECONDS={'look-night-shift-retro-anime':163.2,'look-krea-atelier-target-stack':1757,'look-krea-witch-nijisis':812.2,'look-anima-painterly-artist-tags':31.7,'look-anima-fantasy-portrait':37.1,'look-wai-fantasy-portrait':25.4,'look-animagine-fantasy-portrait':41.5,'look-pearly-anima-mix-v10-showcase':29.8,'look-oneobsession-anima-v20-showcase':30.8,'look-anima-pearly-petiflow':30.6,'look-anifox-ringeko':44.9,'look-noob-fantasy-scene':36.7,'look-krea-watercolor-anime':375,'look-krea-oil-fantasy':643.1,'look-krea-style-emerald-tarot':466.8,'look-krea-style-inkwork-darkbrush':434,'look-krea-style-airy-softwatercolor':430,'look-krea-realistic-snapshot':342.7,'look-krea-lenovo-ultrareal':357.2,'look-preset-stylized-prop':43.3,'look-preset-pixel-lora':47.9,'look-preset-realvis':86.7,'look-preset-zimage-fast':102.4};
  // This PC's finished Make runs of the look as made (its recipe and steps; drafts and model switches left out) come first, then the lab.
  // ponytail: picture size is not matched; a reshaped run counts like a designed one.
  function lookTiming(look){
    const seen=new Map(),names=['Make · '+look.name,'Make · Compare · '+look.name],steps=look.body.controls?.steps;
    for(const j of [...(typeof jobs!=='undefined'&&Array.isArray(jobs)?jobs:[]),...state.runs.map(r=>r.job)])if(j?.id&&names.includes(j.label)&&(steps==null||Number(j.controls?.steps)===Number(steps)))seen.set(j.id,j);
    const mine=window.StudioContinuation?.combineTiming?.([...seen.values()],look.body.preset_id);
    return mine?{seconds:mine.seconds,source:'Median of '+mine.count+' finished run'+(mine.count>1?'s':'')+' of this look on this PC.'}:LAB_SECONDS[look.id]?{seconds:LAB_SECONDS[look.id],source:'Median of two test pictures in the 16 Oct look lab on this PC.'}:null;
  }
  // Fast under 45 s, Medium under 3 min, Slow otherwise. A look never measured says so; only a Krea recipe is known slow without a number.
  function speed(look){const t=look&&lookTiming(look),s=t&&Math.round(t.seconds);
    if(!t)return /krea/.test(look?.body?.preset_id||'')?['slow','Slow · several minutes','Krea 2 recipes took 6 to 37 minutes per picture in the 16 Oct look lab.']:['unknown','Speed not measured yet','No timing for this look on this PC yet.'];
    return s<45?['fast','Fast · ~'+s+' s',t.source]:s<180?['medium','Medium · ~'+s+' s',t.source]:['slow','Slow · ~'+Math.round(s/60)+' min',t.source];}
  const pace=look=>{const [kind,label,source]=speed(look);return '<small class="make-pace '+kind+'" title="'+escape(source)+'">'+escape(label)+'</small>';};
  // The same runtime facts the full editor gates on (app.js globals); unknown (null) health does not block.
  function runtimeBlocker(){if(typeof backendWorkBlocker!=='undefined'&&backendWorkBlocker)return backendWorkBlocker;if(typeof backendSwitching!=='undefined'&&backendSwitching)return'A model environment switch is running. Wait for it to finish.';if(typeof workerAlive!=='undefined'&&workerAlive===false)return'The Studio worker has stopped. Restart the Studio before generating.';if(typeof online!=='undefined'&&online===false)return'ComfyUI is not reachable. Start it, then try again.';if(typeof online!=='undefined'&&online===true&&typeof schemaAvailable!=='undefined'&&!schemaAvailable)return'ComfyUI is still starting up. Try again in a moment.';return'';}
  function blocker(look,p=tunedPreset(look)){const runtime=runtimeBlocker();if(runtime)return runtime;if(look.usable===false)return look.unusable_reason||'This look cannot be used now.';if(!p)return'This look’s recipe is not in the library.';if(p.runtime_block)return p.runtime_block;const missing=typeof missingByPreset!=='undefined'&&missingByPreset[p.id];if(Array.isArray(missing)&&missing.length)return'Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first: open Models & setup.';return'';}
  const blockerMarkup=(look,text,id=tunedPreset(look)?.id||look.body.preset_id)=>escape(text).replace('Models &amp; setup','<a href="/#models?need='+escape(encodeURIComponent(id))+'">Models &amp; setup</a>');

  // Tune this look (owner ask, 16 Oct 2026): see and change the look's model, adapters, steps, negative and seed without the
  // full editor. Folded shut by default. Tuning only changes the controls Generate sends: the server's allow-list, adapter
  // inventory and ranges still decide, and nothing here submits. A tune belongs to its look and travels with each run.
  const NAMED=k=>k+'_name',bound=(p,k)=>!!(p?.[k]||p?.bindings_extra?.[k]),byId=id=>presets().find(p=>p.id===id);
  const kb=()=>typeof knowledge!=='undefined'&&knowledge||{},entry=name=>name&&kb().loras?.[name]||null;
  const family=p=>p?.family||p?.name||p?.id||'';
  const short=name=>entry(name)?.label||String(name||'the recipe’s own LoRA').replace(/\.safetensors$/,'');
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
  // A tune survives a reload (audit N7): one record per look revision, the 12 most recent, checked against the catalog before use.
  const TUNES='studio.make.tune';let savedTunes={};try{const s=JSON.parse(makeStorage.getItem(TUNES)||'{}');if(s&&typeof s==='object'&&!Array.isArray(s))savedTunes=s;}catch{}
  function validTune(look,t){
    const p=presetFor(look),num=(v,lo,hi)=>typeof v==='number'&&Number.isFinite(v)&&v>=lo&&v<=hi;
    if(!t||typeof t!=='object'||t.rev!==look.revision||!Array.isArray(t.rows)||!Array.isArray(t.cleared))return null;
    const tp=t.preset===p?.id?p:models(look).find(m=>m.id===t.preset);if(!tp)return null;
    const rows=t.rows.filter(r=>r&&SLOTS.includes(r.slot)&&bound(tp,r.slot)&&typeof r.name==='string'&&r.name.length<300&&num(r.strength,0,2)&&typeof r.on==='boolean');
    if(rows.length!==t.rows.length||new Set(rows.map(r=>r.slot)).size!==rows.length||!t.cleared.every(s=>SLOTS.includes(s)))return null;
    if(!(t.steps==null||Number.isSafeInteger(t.steps)&&t.steps>0&&t.steps<=150)||!(t.negative==null||typeof t.negative==='string'&&t.negative.length<=4000)||!(t.seed==null||Number.isSafeInteger(t.seed)&&t.seed>=0)||!(t.scale==null||num(t.scale,0,150)))return null;
    return{preset:tp.id,rows:rows.map(r=>({slot:r.slot,name:r.name,strength:r.strength,on:r.on,...(r.added?{added:true}:{})})),cleared:[...t.cleared],steps:t.steps??null,sampler:tp.choices?.sampler?.includes(t.sampler)?t.sampler:'',negative:t.negative??null,seed:t.seed??null,reseed:t.reseed!==false,scale:t.scale??100,...(t.turbo===true?{turbo:true}:{})};
  }
  function keepTune(look){
    const t=state.tune[look.id];delete savedTunes[look.id];
    if(t&&(tuneSummary(look,t)||!t.reseed)){const {composer,...rest}=t;savedTunes[look.id]={...rest,rev:look.revision};}
    const ids=Object.keys(savedTunes);for(const id of ids.slice(0,Math.max(0,ids.length-12)))delete savedTunes[id];
    writeTunes(savedTunes,creationPrivacy());
  }
  function tuneOf(look){
    if(state.tune[look.id])return state.tune[look.id];const saved=validTune(look,savedTunes[look.id]);if(saved)return state.tune[look.id]=saved;const p=presetFor(look),c=look.body.controls||{};
    return state.tune[look.id]={preset:p?.id,rows:adapters(look).map(a=>({slot:a.key,name:bound(p,NAMED(a.key))?c[NAMED(a.key)]:'',strength:a.strength,on:true})),cleared:[],steps:null,sampler:'',negative:null,seed:null,reseed:true,scale:100};
  }
  // Installed adapters made for this model type: the knowledge base names each file's family; a file it does not know is not offered.
  // Files whose family is the look's (or the switched model's) come first as made for it; the rest share only the loader (audit N5).
  // A merge of a base model counts as that base for its LoRAs: the knowledge base's family_aliases (One Obsession and Pearly are recorded
  // Anima-family merges in presets/catalog.json), the same aliases the full editor's guidance reads (bundle-core.js).
  const base=p=>kb().family_aliases?.[p?.family]||p?.family;
  const fits=(look,f)=>[base(presetFor(look)),base(tunedPreset(look))].includes(entry(f)?.family);
  function compatible(look){
    const p=presetFor(look),k=kind(p),chosen=SLOTS.map(s=>p?.choices?.[NAMED(s)]).find(x=>x?.length),files=chosen||(typeof installedLoras!=='undefined'?installedLoras:[]);
    const kinds=new Set(presets().filter(r=>r.family&&kind(r)===k).map(r=>r.family));
    return files.filter(f=>entry(f)&&kinds.has(entry(f).family)).sort((a,b)=>fits(look,b)-fits(look,a)||short(a).localeCompare(short(b)));
  }
  // Measured pairings (lab round 3, PR #1481, docs/looks/LOOK-LAB-2026-10-16.md "Petiflow Tune pairings"): Petiflow as made, one fern
  // scene, one seed. Notes only: added adapters start at their knowledge-base default (owner decision, 16 Oct 2026).
  const LAB={'look-anima-pearly-petiflow':{'anima-xilmo-000020.safetensors':'Lab with Petiflow: at 0.35 kept the scene; at 0.7 changed the plant.',
    'anima-ke-ta_style_v1.safetensors':'Lab with Petiflow: 0.35 and 0.7 both kept the scene, with no gain over Petiflow alone.',
    'anima-newanimastyle-v1.safetensors':'Lab with Petiflow: at 0.5 kept the scene; at 1.0 changed the plant and the face.',
    'anima-kieed_v9_step6000.safetensors':'Lab with Petiflow: at 0.25 and 0.5 it changed the plant and flattened the face.'}};
  const labOf=(look,name)=>tunedPreset(look)===presetFor(look)&&LAB[look?.id]?.[name]||null;
  // Style strength multiplies every tuned adapter; what is sent is shown beside each strength (audit N3).
  const scaleOf=t=>t?.scale??100,eff=(r,t)=>r.on?Math.min(2,Math.round(r.strength*scaleOf(t))/100):0;
  const rowOut=(r,t)=>r.strength.toFixed(2)+(scaleOf(t)!==100&&r.on?' → '+eff(r,t).toFixed(2):'');
  function paintScale(t){const v=scaleOf(t);for(const el of view.querySelectorAll('#makeStrength,#makeTuneScale'))el.value=v;for(const el of view.querySelectorAll('#makeStrengthOut,#makeTuneScaleOut'))el.textContent=v+'%';
    for(const r of t.rows){const out=q('[data-tune-strength="'+r.slot+'"]')?.nextElementSibling;if(out)out.textContent=rowOut(r,t);}}
  // Two models of one family (two "Anima" files) are told apart by their file.
  const modelLabel=(m,all)=>family(m)+(all.filter(x=>family(x)===family(m)).length>1?' · '+String(m.model?.file||m.id).replace(/^.*[\\/]/,'').replace(/\.(safetensors|gguf|ckpt|pt)$/i,''):'');
  // A word already in the prompt as a whole token is not added again (audit N11: "masterpiece" three times).
  const hasToken=(text,word)=>new RegExp('(^|[^\\p{L}\\p{N}_])'+word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'($|[^\\p{L}\\p{N}_])','iu').test(text);
  const freeSlot=(look,t)=>SLOTS.find(s=>bound(presetFor(look),s)&&bound(presetFor(look),NAMED(s))&&!t.rows.some(r=>r.slot===s));
  // Draft first (audit #12): Tune's own Draft step count (half the look's steps), offered where the recipe binds steps and the draft
  // saves real time: ten steps or more, or a slow look. A fast few-step model (Night Shift's 8) spends its time outside sampling.
  const halve=n=>Math.max(1,Math.round(n/2)),fullSteps=(look,tp)=>Number(look.body.controls?.steps||tp?.defaults?.steps)||0;
  const draftOf=(look,tp=tunedPreset(look))=>{const n=fullSteps(look,tp);return bound(tp,'steps')&&n>=2?halve(n):0;};
  // Round 7 look lab (gpu-lab, 19 Oct; agent verdicts, not art acceptance): on Anima models the official turbo LoRA at 8 steps, cfg 1, euler/simple
  // (13 s warm) was a near-tie with 30 steps, and 20/30/40 steps looked alike. So an Anima look's Draft is the turbo pass, and it offers no Fine.
  // Keyed by file, so it applies wherever the knowledge base says that file fits (compatible()); update from the lab doc, not by hand.
  const TURBO={file:'anima-turbo-lora-v0.2.safetensors',steps:8,cfg:1,sampler:'euler',scheduler:'simple'};
  const turboFits=(look,t=tuneOf(look),tp=tunedPreset(look))=>compatible(look).includes(TURBO.file)&&['steps','cfg'].every(k=>bound(tp,k))&&(t.rows.some(r=>r.name===TURBO.file)||!!freeSlot(look,t));
  function draftMarkup(look){const tp=tunedPreset(look),full=fullSteps(look,tp),turbo=turboFits(look),n=turbo?TURBO.steps:full>=10||speed(look)[0]==='slow'?draftOf(look,tp):0,t=state.tune[look.id];if(!n)return'';
    // Quality is one visible choice (owner, 19 Oct): Draft, As made or Fine are Tune's own step counts, so the estimate follows the choice.
    const fine=Math.min(150,Math.round(full*1.5)),radio=(id,value,label,on)=>'<label class="make-check"><input type="radio" name="makeQuality" id="'+id+'" value="'+value+'"'+(on?' checked':'')+(id==='makeDraft'?' aria-describedby="makeDraftHint"':'')+'> '+label+'</label>';
    if(turbo)return '<fieldset class="make-quality"><legend>Quality</legend>'+radio('makeDraft','turbo','Draft · turbo LoRA, 8 steps, quickest',!!t?.turbo)+radio('makeStandard','','As made · '+full+' steps',!t?.turbo&&t?.steps==null)
      +'<small id="makeDraftHint" class="muted">On Anima models the turbo Draft takes about half the time; on one 19 Oct lab picture it came close to a full run, and 20, 30 and 40 steps looked alike, so there is no Fine. Compare with As made on your own picture. A draft card offers “Make the final” at the full '+full+' steps.</small></fieldset>';
    return '<fieldset class="make-quality"><legend>Quality</legend>'+radio('makeDraft',n,'Draft · '+n+' steps, rougher but quicker',t?.steps===n)+radio('makeStandard','','As made · '+full+' steps',t?.steps==null&&!t?.turbo)+(fine>full?radio('makeFine',fine,'Fine · '+fine+' steps, slower',t?.steps===fine):'')
      +'<small id="makeDraftHint" class="muted">A draft card offers “Make the final”: the same words and seed at the full '+full+' steps.</small></fieldset>';}
  const draftRun=run=>{const look=state.looks?.find(l=>l.id===run.lookId);return!!look&&run.scene&&FINAL.includes(run.job.status)&&(run.job.outputs||[]).length>0&&(!!run.tune?.turbo||run.tune?.steps!=null&&run.tune.steps===draftOf(look,byId(run.tune.preset)||presetFor(look)));};
  const clamp=v=>Math.min(2,Math.max(0,Math.round((Number(v)||0)*20)/20));
  function tuneSummary(look,t){
    const p=presetFor(look),base=Object.fromEntries(adapters(look).map(a=>[a.key,a])),parts=[];if(!t)return'';
    if(t.preset&&t.preset!==p?.id)parts.push('model '+family(byId(t.preset)));
    for(const r of t.rows){const a=base[r.slot];if(!a||(r.name&&r.name!==a.name))parts.push('+'+short(r.name)+(r.on?' '+r.strength:' off'));else if(!r.on)parts.push(short(a.name)+' off');else if(r.strength!==a.strength)parts.push(short(a.name)+' '+r.strength);}
    for(const a of Object.values(base))if(!t.rows.some(r=>r.slot===a.key))parts.push('−'+short(a.name));
    if(scaleOf(t)!==100&&t.rows.some(r=>r.on))parts.push('all LoRAs ×'+scaleOf(t)+'%');
    if(t.turbo)parts.push('draft · turbo LoRA, 8 steps');else if(t.steps!=null)parts.push((t.steps===draftOf(look,byId(t.preset)||p)?'draft ':'')+t.steps+' steps');if(t.sampler)parts.push(t.sampler);if(t.negative!=null)parts.push('own negative');if(!t.reseed&&t.seed!=null)parts.push('seed '+t.seed+' locked');
    return parts.length?'Tuned: '+parts.join(' · '):'';
  }
  // Untuned, the summary still names what will run (owner, 19 Oct: the model and LoRAs are the choice, so they stay in view while Tune is shut).
  function asMade(look){const p=presetFor(look),steps=fullSteps(look,p);if(!p)return'Model, LoRAs, steps, seed';
    return 'As made: '+[modelLabel(p,presets()),...adapters(look).map(a=>short(a.name)+' '+a.strength.toFixed(2)),...(bound(p,'steps')&&steps?[steps+' steps']:[])].join(' · ');}
  // The tune applied to the prepared controls. Every bound slot of a switched model is written (off or empty is 0), so the
  // other recipe never keeps an authored adapter of its own; on the look's own model only changed slots are written.
  function applyTune(controls,look,t){
    const p=presetFor(look),tp=byId(t.preset)||p,switched=tp!==p;
    for(const s of SLOTS){if(!bound(tp,s))continue;const r=t.rows.find(x=>x.slot===s);
      if(r){controls[s]=eff(r,t);if(r.name&&bound(tp,NAMED(s)))controls[NAMED(s)]=r.name;}
      else if(switched||t.cleared.includes(s))controls[s]=0;}
    if(t.steps!=null&&bound(tp,'steps'))controls.steps=t.steps;
    if(t.sampler&&bound(tp,'sampler'))controls.sampler=t.sampler;
    if(t.negative!=null&&bound(tp,'negative'))controls.negative=t.negative;
    // The turbo draft, after the sampler: it needs its own steps, cfg, sampler and scheduler, whatever Tune says (Muse HIGH on #1559).
    if(t.turbo&&compatible(look).includes(TURBO.file)){const own=t.rows.find(r=>r.name===TURBO.file),slot=own?.slot||SLOTS.find(x=>bound(tp,x)&&bound(tp,NAMED(x))&&!t.rows.some(r=>r.slot===x));
      if(slot){controls[slot]=1;controls[NAMED(slot)]=TURBO.file;controls.steps=TURBO.steps;controls.cfg=TURBO.cfg;if(tp.choices?.sampler?.includes(TURBO.sampler))controls.sampler=TURBO.sampler;if(tp.choices?.scheduler?.includes(TURBO.scheduler))controls.scheduler=TURBO.scheduler;}}
    // A trigger word is written only for an adapter you added: the look's own wording already speaks for its own adapters.
    if(typeof controls.positive==='string')for(const r of t.rows){const e=entry(r.name);if(!r.added||!r.on||!e?.trigger)continue;
      const add=e.trigger.split(',').map(w=>w.trim()).filter(w=>w&&!hasToken(controls.positive,w)).join(', ');if(!add)continue;
      controls.positive=e.trigger_position==='start'?add+', '+controls.positive:controls.positive+', '+add;}
    return tp.id;
  }
  function renderTune(){
    const look=current(),box=q('#makeTuneBody');if(!look||!box)return;
    if(!presetFor(look)){box.innerHTML='<p class="muted">This look\u2019s recipe is not in the library, so it cannot be tuned here.</p>';tuneChanged(false);return;}
    const t=tuneOf(look),p=presetFor(look),tp=tunedPreset(look),c=look.body.controls||{};
    const list=models(look),missing=missingFor(tp),files=compatible(look),slot=freeSlot(look,t),steps=Number(c.steps||tp?.defaults?.steps)||0;
    const draft=halve(steps),fine=Math.min(150,Math.round(steps*1.5));
    const option=(value,label,on)=>'<option value="'+escape(value)+'"'+(on?' selected':'')+'>'+escape(label)+'</option>';
    const row=r=>{const e=entry(r.name),why=e?.trigger?'Trigger: '+e.trigger+(r.added?' (added to your words)':''):r.name?'No trigger word':'Fixed in this recipe';
      return '<div class="make-tune-row" data-slot="'+r.slot+'"><label class="make-check"><input type="checkbox" data-tune-on="'+r.slot+'"'+(r.on?' checked':'')+'> <b>'+escape(short(r.name))+'</b></label>'
        +'<span class="make-tune-strength"><input type="range" min="0" max="2" step="0.05" value="'+r.strength+'" data-tune-strength="'+r.slot+'" aria-label="Strength of '+escape(short(r.name))+'"><output>'+rowOut(r,t)+'</output></span>'
        +(r.name?'<button type="button" class="make-link" data-tune-remove="'+r.slot+'">Remove</button>':'')+'<small>'+escape(why)+'</small>'+(labOf(look,r.name)?'<small class="make-lab">'+escape(labOf(look,r.name))+'</small>':'')+'</div>';};
    const all=[p,...list],made=files.filter(f=>fits(look,f)).length,other=files.length-made;
    box.innerHTML='<div class="make-tune-group"><h3>Model</h3>'
      +'<label>Base model<select id="makeModel" data-tune="model">'+option(p.id,'As made · '+modelLabel(p,all)+(nonCommercial(p)?' · non-commercial':'')+(missingFor(p).length?' · needs download':''),tp===p)+list.map(m=>option(m.id,modelLabel(m,all)+(nonCommercial(m)?' · non-commercial':'')+(missingFor(m).length?' · needs download':''),tp===m)).join('')+'</select></label>'
      +'<small class="muted">'+escape(tp?.model?.file||tp?.name||'')+(nonCommercial(tp)?' · '+escape(tp.commercial_note):'')+(list.length?' · Same model type: the look’s words and LoRAs carry over; pictures will differ.':' · No other model in the library takes this look’s words and LoRAs.')+'</small>'
      +(missing.length?'<p class="make-warn" id="makeTuneWhy">Needs '+missing.length+' model file'+(missing.length>1?'s':'')+' first. <a href="/#models?need='+escape(encodeURIComponent(tp.id))+'">Open Models & setup</a></p>':'')+'</div>'
      +'<div class="make-tune-group"><h3>LoRAs</h3>'
      +(t.rows.length?'<label class="make-tune-scale">All LoRAs × <output id="makeTuneScaleOut">'+scaleOf(t)+'%</output><input type="range" id="makeTuneScale" data-tune="scale" min="0" max="150" step="10" value="'+scaleOf(t)+'" aria-describedby="makeTuneScaleHint"></label><small id="makeTuneScaleHint" class="muted">Multiplies every strength below; the arrow shows what is sent. 100% sends them as set.</small>'+t.rows.map(row).join(''):'<p class="muted">None: the model and the words carry this look.</p>')
      +(SLOTS.some(s=>bound(p,NAMED(s)))?(files.length?'<div class="make-tune-add"><label for="makeLoraSearch">Add a LoRA <small>installed, fits this model</small></label><input id="makeLoraSearch" type="search" list="makeLoraList" placeholder="Filter by name, style or trigger word" autocomplete="off" aria-describedby="makeLoraFit'+(slot?'':' makeLoraFull')+'"'+(slot?'':' disabled')+'><datalist id="makeLoraList">'+files.filter(f=>!t.rows.some(r=>r.name===f)).map(f=>{const e=entry(f);return '<option value="'+escape(f)+'">'+escape(short(f)+(e.role?' · '+e.role:'')+' · '+(fits(look,f)?'made for this model':e.family+', may not suit'))+'</option>';}).join('')+'</datalist><button type="button" data-tune-add'+(slot?'':' disabled')+'>Add</button>'
        +'<small id="makeLoraFit">'+(made?made+' made for '+escape(base(p))+(base(p)!==family(p)?' (this model’s base)':'')+' come first.':'None is made for '+escape(family(p))+' itself.')+(other?' '+other+' from other families of this model type may not suit it.':'')+'</small>'
        +(slot?'':'<small id="makeLoraFull">All LoRA slots of this recipe are in use; remove one first.</small>')+'<div id="makeLoraChoices" class="make-lora-list" role="group" aria-label="Installed LoRAs for this model">'+loraCards(look,'')+'</div></div>':'<p class="muted">No installed LoRA is known to fit this model type. Models & setup lists what can be installed.</p>'):'<p class="muted">This recipe has no LoRA slots to fill.</p>')+'</div>'
      +((bound(tp,'steps')&&steps)||(bound(tp,'sampler')&&tp.choices?.sampler?.length)?'<div class="make-tune-group"><h3>Quality and speed</h3><div class="make-pair">'
        +(bound(tp,'steps')&&steps?'<label>Steps<select data-tune="steps">'+option('','As made · '+steps,t.steps==null)+option(draft,'Draft · '+draft+', faster',t.steps===draft)+option(fine,'Fine · '+fine+', slower',t.steps===fine)+'</select></label>':'')
        +(bound(tp,'sampler')&&tp.choices?.sampler?.length?'<label>Sampler<select data-tune="sampler">'+option('','As made'+(c.sampler?' · '+c.sampler:''),!t.sampler)+tp.choices.sampler.filter(s=>s!==c.sampler).map(s=>option(s,s,t.sampler===s)).join('')+'</select></label>':'')+'</div></div>':'')
      +(bound(tp,'negative')?'<div class="make-tune-group"><h3>Leave out</h3><textarea id="makeNegative" data-tune="negative" rows="2" maxlength="4000" aria-label="Negative prompt: things to leave out" placeholder="Things to keep out of the picture">'+escape(t.negative??look.body.negative??'')+'</textarea></div>':'')
      +(bound(tp,'seed')?'<div class="make-tune-group"><label class="make-check"><input type="checkbox" id="makeNewSeed" data-tune="reseed"'+(t.reseed?' checked':'')+'> Different pictures each time</label><label>Seed<input type="number" id="makeSeed" data-tune="seed" min="0" max="2147483646" step="1" inputmode="numeric" value="'+escape(t.seed??c.seed??'')+'"'+(t.reseed?' disabled':'')+' aria-describedby="makeSeedHint"></label><small id="makeSeedHint" class="muted">'+(t.reseed?'Turn off “Different pictures each time” to lock this seed.':'Locked: every run starts from this seed.')+'</small></div>':'')
      +'<button type="button" class="make-link" data-tune-reset>Back to the look as made</button>';
    tuneChanged(false);
  }
  // A tune change redraws only the summary, Generate's readiness and the estimate, so the scene being typed is never disturbed.
  function tuneChanged(redraw=true){
    const look=current();if(!look)return;if(redraw){renderTune();renderSweep();return;}
    keepTune(look);sweepPaint();const sum=q('#makeTuneSum'),why=lookWhy(look),button=q('#makeGenerate');if(sum)sum.textContent=tuneSummary(look,state.tune[look.id])||asMade(look);
    const draftBox=q('#makeDraftBox');if(draftBox)draftBox.innerHTML=draftMarkup(look);
    if(button&&!state.busy){button.disabled=!!why;button.title=why;}const said=q('#makeWhy');if(said){said.innerHTML=why?blockerMarkup(look,why,whyPreset(look)):'';said.dataset.why=why;}estimate();
  }
  function tuneInput(target){
    const look=current();if(!look)return false;const t=tuneOf(look),row=s=>t.rows.find(r=>r.slot===s);
    if(target.dataset.tuneOn){row(target.dataset.tuneOn).on=target.checked;paintScale(t);tuneChanged(false);return true;}
    if(target.dataset.tuneStrength){const r=row(target.dataset.tuneStrength);r.strength=clamp(target.value);target.nextElementSibling.textContent=rowOut(r,t);tuneChanged(false);return true;}
    const key=target.dataset.tune;if(!key)return false;
    if(key==='scale'){t.scale=Math.min(150,Math.max(0,Number(target.value)||0));paintScale(t);tuneChanged(false);return true;}
    if(key==='reseed'){if(target.checked===t.reseed)return true;t.reseed=target.checked;tuneChanged();q('#makeNewSeed')?.focus();return true;}
    if(key==='model'){t.preset=target.value;const tp=tunedPreset(look);if(t.sampler&&!tp.choices?.sampler?.includes(t.sampler))t.sampler='';tuneChanged();return true;}
    if(key==='steps'){t.steps=target.value?Number(target.value):null;delete t.turbo;}
    if(key==='sampler')t.sampler=target.value;
    if(key==='negative')t.negative=target.value===(look.body.negative||'')?null:target.value;
    if(key==='seed')t.seed=target.value===''?null:Number(target.value);
    tuneChanged(false);return true;
  }
  // Matches on the file name or the knowledge base's label, ignoring case: an exact name wins, else every typed word must appear.
  function adapterMatches(look,text){const s=text.toLowerCase(),files=compatible(look),names=f=>[f,f.replace(/\.safetensors$/i,''),short(f)].map(x=>x.toLowerCase());
    const exact=files.filter(f=>names(f).includes(s));if(exact.length)return exact;const words=s.split(/\s+/).filter(Boolean);return files.filter(f=>words.every(w=>loraText(f).includes(w)));}
  function addAdapter(look,name){const t=tuneOf(look),slot=freeSlot(look,t);if(!slot||!compatible(look).includes(name)||t.rows.some(r=>r.name===name))return;
    t.rows.push({slot,name,strength:startOf(name),on:true,added:true});t.cleared=t.cleared.filter(s=>s!==slot);const turboOff=typeof TURBO!=='undefined'&&t.turbo&&!turboFits(look,t);if(turboOff)delete t.turbo;tuneChanged();q('[data-tune-strength="'+slot+'"]')?.focus();
    say((fits(look,name)?'Added '+short(name)+'.':'Added '+short(name)+'. It was made for '+entry(name).family+', so it may not suit this model; check the first picture.')+(turboOff?' That took the last free slot, so Quality is back to As made (the turbo Draft needs one).':''));}
  // An added LoRA starts at its recommended strength. A recorded 0 means "off in recipes", not advice, so it starts at 1 kept inside its
  // recorded range, as the full editor's recommendedStrength does (an added LoRA at 0 did nothing).
  const startOf=name=>{const e=entry(name),d=Number(e?.default),r=Array.isArray(e?.strength)?e.strength.filter(Number.isFinite):[];return clamp(d>0?d:r.length?Math.max(Math.min(...r),Math.min(1,Math.max(...r))):1);};
  // The LoRA list (owner, 19 Oct: choosing LoRAs must be browsable, not a name to guess): every installed LoRA for this model type as a
  // card with its role, fit, trigger word and the strength its maker recommends; Add puts it in at that strength. Typing narrows the list.
  // A new model family needs no code here: fit and order come from the knowledge base's family names (compatible(), fits()).
  // One search text for the list and for Enter / Add (Codex P2 on #1537): file, label, role, family and trigger word.
  const loraText=f=>{const e=entry(f)||{};return [f,f.replace(/\.safetensors$/i,''),short(f),e.role,e.family,e.trigger].join(' ').toLowerCase();};
  function loraCards(look,text){
    const t=tuneOf(look),slot=freeSlot(look,t),words=String(text||'').toLowerCase().split(/\s+/).filter(Boolean);
    const files=compatible(look).filter(f=>!t.rows.some(r=>r.name===f)&&words.every(w=>loraText(f).includes(w)));
    const card=f=>{const e=entry(f)||{},range=Array.isArray(e.strength)&&e.strength.length===2&&e.strength[0]!==e.strength[1]?' (works '+e.strength[0]+'–'+e.strength[1]+')':'';
      return '<div class="make-lora-card'+(fits(look,f)?'':' make-lora-foreign')+'"><div><b>'+escape(short(f))+'</b><small>'+escape([e.role,fits(look,f)?'made for this model':e.family+', may not suit'].filter(Boolean).join(' · '))+'</small>'
        +'<small>'+(e.trigger?'Trigger '+escape(e.trigger)+', added to your words':'No trigger word')+' · starts at '+escape(startOf(f).toFixed(2))+escape(range)+'</small>'+(typeof TURBO!=='undefined'&&f===TURBO.file?'<small>Easier: Quality → Draft uses it with the 8 steps and cfg 1 it needs.</small>':'')+'</div>'
        +'<button type="button" data-tune-pick="'+escape(f)+'" aria-label="Add '+escape(short(f))+'"'+(slot?'':' disabled aria-describedby="makeLoraFull"')+'>Add</button></div>';};
    if(!files.length)return '<small>'+(words.length?'No installed LoRA for this model matches “'+escape(text)+'”.':'Every installed LoRA for this model is already added.')+'</small>';
    const made=files.filter(f=>fits(look,f)),other=files.filter(f=>!fits(look,f));
    // Filtered, every match shows flat; unfiltered, LoRAs from other families wait in a fold, as they may not suit.
    return words.length||!made.length?files.map(card).join(''):made.map(card).join('')+(other.length?'<details class="make-lora-more"><summary>'+other.length+' from other families of this model type (may not suit)</summary>'+other.map(card).join('')+'</details>':'');
  }
  function tuneClick(target){
    const look=current();if(!look)return false;
    const remove=target.closest('[data-tune-remove]');if(remove){const t=tuneOf(look),s=remove.dataset.tuneRemove;t.rows=t.rows.filter(r=>r.slot!==s);if(!t.cleared.includes(s))t.cleared.push(s);tuneChanged();q('#makeLoraSearch')?.focus();return true;}
    const pick=target.closest('[data-tune-pick]');if(pick){addAdapter(look,pick.dataset.tunePick);return true;}
    if(target.closest('[data-tune-add]')){const input=q('#makeLoraSearch'),text=input?.value.trim()||'',t=tuneOf(look),choices=q('#makeLoraChoices');
      if(!text){say('Type part of a LoRA name, then press Add.');input?.focus();return true;}
      // A part of the name is enough (audit v3 N2): one match is added, several are offered as choices, none says why.
      const found=adapterMatches(look,text),open=found.filter(f=>!t.rows.some(r=>r.name===f));
      if(!found.length){say(text+' is not an installed LoRA for this model type. Type part of its name, or choose one from the list.');input?.focus();return true;}
      if(!open.length){say(short(found[0])+(found.length>1?' and the other matches are':' is')+' already added.');input?.focus();return true;}
      if(open.length===1){addAdapter(look,open[0]);return true;}
      if(choices){choices.innerHTML=loraCards(look,text);choices.querySelector('[data-tune-pick]')?.focus();}
      say(open.length+' LoRAs match. Choose one.');return true;}
    if(target.closest('[data-tune-reset]')){const reseed=state.tune[look.id]?.reseed??true;delete state.tune[look.id];delete savedTunes[look.id];tuneOf(look).reseed=reseed;tuneChanged();return true;}
    return false;
  }

  // Compare one setting (#1496): one look with its Tune, one setting varied over two or three values, the words and seed held.
  // One press sends one job per value into one card, as Compare looks does: a light group in this browser, not a planned
  // comparison (Blind until Reveal belongs to planned comparisons only, owner 27 Sep), so every picture is labelled with its value.
  const sweepOf=look=>state.sweeps[look.id]??={open:false,axis:'',values:[]};
  function sweepAxes(look){
    const t=tuneOf(look),tp=tunedPreset(look);
    return[{id:'steps',label:'Steps',why:t.turbo?'Quality is the turbo Draft, which fixes 8 steps; choose As made first':!bound(tp,'steps')?'this recipe takes no step count':fullSteps(look,tp)<1?'this look’s step count is not known here':''},
      ...(t.rows.length?t.rows.map(r=>({id:'adapter:'+r.slot,label:short(r.name)+' strength',slot:r.slot,why:''})):[{id:'adapter',label:'LoRA strength',why:'this look has no LoRA; add one under Model, LoRAs and settings first'}]),
      {id:'model',label:'Model',why:models(look).length?'':'no other model in the library takes this look'}];
  }
  function sweepDefaults(look,axis){const t=tuneOf(look),tp=tunedPreset(look),p=presetFor(look);
    if(axis.id==='steps'){const n=t.steps??fullSteps(look,tp);return[String(n),String(n>1?halve(n):n+1)];}
    if(axis.id==='model')return[tp.id,(tp===p?models(look)[0]:p).id];
    const r=t.rows.find(x=>x.slot===axis.slot),now=r.on?r.strength:0;return[String(now),String(now?0:startOf(r.name))];}
  // The runs one press would send, or why it cannot: null while Compare one setting is folded shut.
  function sweepPlan(look,base=tuneOf(look)){
    const s=sweepOf(look);if(!s.open)return null;const fail=why=>({why:'Compare one setting: '+why.replace(/\.?$/,'.')});
    const p=presetFor(look),axis=sweepAxes(look).find(a=>a.id===s.axis);if(!axis)return fail('choose the setting to vary');if(axis.why)return fail(axis.why);
    const all=[p,...models(look)],runs=[];
    for(const raw of s.values.map(v=>String(v??'').trim()).filter(Boolean)){const t=structuredClone(base);let label;
      if(axis.id==='steps'){const n=Number(raw);if(!Number.isSafeInteger(n)||n<1||n>150)return fail('steps are whole numbers from 1 to 150');t.steps=n;label=n+' steps';}
      else if(axis.id==='model'){const m=all.find(x=>x?.id===raw);if(!m)return fail('that model is not offered for this look');const why=blocker(look,m);if(why)return{...fail(family(m)+': '+why),preset:m.id};
        t.preset=m.id;if(t.sampler&&!m.choices?.sampler?.includes(t.sampler))t.sampler='';label=(m===p?'As made · ':'')+modelLabel(m,all);}
      else{const n=Number(raw),r=t.rows.find(x=>x.slot===axis.slot);if(!Number.isFinite(n)||n<0||n>2)return fail('strengths go from 0 (off) to 2');r.on=clamp(n)>0;if(r.on)r.strength=clamp(n);label=short(r.name)+(r.on?' '+rowOut(r,t):' off');
        // Told apart by what applyTune sends: 0.01 rounds to off, and All adapters at 0% sends 0 for every value.
        if(runs.some(x=>eff(x.tune.rows.find(y=>y.slot===axis.slot),x.tune)===eff(r,t)))return fail('two values send the same strength'+(scaleOf(t)!==100?' (All LoRAs is at '+scaleOf(t)+'%)':''));}
      if(runs.some(x=>x.label===label))return fail('give different values');runs.push({label,tune:t});}
    return runs.length<2?fail('give two or three values'):{axis,runs,why:''};
  }
  const turboWhy=look=>{const t=state.tune[look.id];return t?.turbo&&!turboFits(look,t)?'The turbo Draft needs a free LoRA slot: remove a LoRA or choose Quality As made.':'';};
  const lookWhy=look=>blocker(look)||turboWhy(look)||sweepPlan(look)?.why||'';
  // The recipe a refusal's Models & setup link opens: a blocked compare value, else the tuned recipe.
  const whyPreset=look=>!blocker(look)&&sweepPlan(look)?.preset||tunedPreset(look)?.id||look.body.preset_id;
  // An added adapter's trigger word goes in only where it is on (applyTune), so sweeping it changes the words too.
  function sweepHint(look,axis){const r=axis?.slot&&tuneOf(look).rows.find(x=>x.slot===axis.slot),trigger=r?.added&&entry(r.name)?.trigger;
    return trigger?'The same look, seed and other settings for every picture; only this LoRA’s strength changes, and its trigger word “'+trigger+'” is added only to the pictures where it is on.':'The same look, words and seed for every picture; only this setting changes. One picture per value, side by side on one card.';}
  function renderSweep(){
    const look=current(),box=q('#makeSweepBody');if(!look||!box)return;const s=sweepOf(look),axes=sweepAxes(look),axis=axes.find(a=>a.id===s.axis&&!a.why),p=presetFor(look),all=[p,...models(look)];
    const option=(value,label,on,off)=>'<option value="'+escape(value)+'"'+(on?' selected':'')+(off?' disabled':'')+'>'+escape(label)+'</option>';
    const field=i=>{const v=s.values[i]??'',name='Value '+(i+1)+(i===2?' (optional)':'');
      if(axis.id==='model')return '<label>'+name+'<select data-sweep-value="'+i+'">'+(i===2?option('','None',!v):'')+all.map(m=>option(m.id,(m===p?'As made · ':'')+modelLabel(m,all)+(missingFor(m).length?' · needs download':''),v===m.id)).join('')+'</select></label>';
      return '<label>'+name+'<input type="number" data-sweep-value="'+i+'" value="'+escape(v)+'" '+(axis.id==='steps'?'min="1" max="150" step="1"':'min="0" max="2" step="0.05"')+(i===2?' placeholder="optional"':'')+'></label>';};
    box.innerHTML='<p class="make-hint">'+escape(sweepHint(look,axis))+'</p>'
      +'<label class="make-sweep-axis">Setting to vary<select id="makeSweepAxis" data-sweep="axis">'+option('','Choose a setting',!axis)+axes.map(a=>option(a.id,a.label+(a.why?' · unavailable: '+a.why:''),axis===a,!!a.why)).join('')+'</select></label>'
      +(axis?'<div class="make-sweep-values">'+[0,1,2].map(field).join('')+'</div>'+(axis.slot?'<small class="muted">0 turns the LoRA off.</small>':''):'')
      +'<small id="makeSweepOne" class="muted">While this is open, How many is one picture per value. Fold it shut to make pictures as usual.</small>';
    sweepPaint();
  }
  // Summary, How many and the Generate label follow the plan; readiness and the estimate are the caller's (tuneChanged, sweepInput).
  function sweepPaint(){
    const look=current();if(!look)return;const s=sweepOf(look),plan=sweepPlan(look),ok=plan&&!plan.why,sum=q('#makeSweepSum'),count=q('#makeCount'),button=q('#makeGenerate');
    if(sum)sum.textContent=ok?plan.runs.map(r=>r.label).join(' vs '):'Same words and seed, one setting changed';
    if(count){count.disabled=s.open;if(s.open)count.setAttribute('aria-describedby','makeSweepOne');else count.removeAttribute('aria-describedby');}
    if(button)button.textContent=ok?'Generate '+plan.runs.length+' pictures':'Generate';
  }
  function sweepInput(target){const look=current();if(!look)return;const s=sweepOf(look);
    if(target.dataset.sweep==='axis'){s.axis=target.value;const a=sweepAxes(look).find(x=>x.id===s.axis&&!x.why);s.values=a?sweepDefaults(look,a):[];renderSweep();q('#makeSweepAxis')?.focus();}
    else if(target.dataset.sweepValue!=null)s.values[Number(target.dataset.sweepValue)]=target.value;
    sweepPaint();syncOperation();estimate();}

  view.innerHTML='<div class="make-heading"><span class="eyebrow">MAKE</span><h1 id="makeTitle" tabindex="-1">What are you making?</h1><p>Pick a goal, pick a look by its picture, describe your idea. The look brings the right model, LoRAs and settings.</p></div>'
    +'<div class="make-goals" role="radiogroup" aria-labelledby="makeTitle" id="makeGoals"></div>'
    +'<div id="makeStatusSlot"></div><p id="makeDraftWarning" class="make-warn" role="status" hidden></p>'
    +'<div id="makeSplit" class="make-split"><div id="makeBody"></div><section class="make-runs" aria-labelledby="makeRunsTitle"><div class="section-title"><h2 id="makeRunsTitle">Your pictures</h2><a href="/#assets">Open the library ↗</a></div><div id="makeRuns" class="make-run-list" aria-live="polite" aria-relevant="additions text"></div></section></div>'
    +'<p class="make-advanced">Need every setting? <a href="/#create">Open the full editor</a> · <a href="/prompt-lab.html">Prompt Lab</a> · <a href="/#production">Compare settings side by side</a></p>';

  // One live status line (audit N2): it sits under Generate in the Generate bar, so progress and refusals show where the press
  // was; with no composer on screen it waits under the goals. The node moves, it is never redrawn, so it keeps its text.
  const statusEl=document.createElement('p');statusEl.id='makeStatus';statusEl.className='make-status';statusEl.setAttribute('role','status');
  function placeStatus(){const button=q('.make-go #makeGenerate'),slot=button?null:q('#makeStatusSlot');if(button&&statusEl.previousElementSibling!==button)button.after(statusEl);else if(slot&&statusEl.parentElement!==slot)slot.append(statusEl);}
  placeStatus();
  // A look picture that is missing on this PC (local-only examples) shows the blank mark, not a broken image. Only look pictures:
  // a chosen picture of yours (.make-picked) keeps its <img>, so a slow or failed thumbnail never removes it.
  view.addEventListener('error',e=>{if(e.target.matches?.('.make-look img,.make-chosen:not(.make-picked)>img')){const blank=document.createElement('span');blank.className='make-look-blank';blank.setAttribute('aria-hidden','true');blank.textContent='✦';e.target.replaceWith(blank);}},true);
  function renderGoals(){
    q('#makeGoals').innerHTML=GOALS.map((g,i)=>(i===5?'<div class="make-goal-group" role="group" aria-labelledby="makePictureGoals"><span class="make-goal-break" id="makePictureGoals">From a picture you have</span>':'')+'<button type="button" role="radio" tabindex="'+(g.id===state.goal?'0':'-1')+'" aria-checked="'+(g.id===state.goal)+'" data-make-goal="'+g.id+'"><b>'+escape(g.name)+'</b><small>'+escape(g.hint)+'</small></button>').join('')+'</div>';
  }
  // Once a look is chosen the gallery folds to one line and the results sit beside the words, so Generate and its pictures share a screen.
  // The pictures column opens beside the words only once there are pictures; before that the composer takes the full width.
  function layout(){const focused=!goal().intent&&!!current()&&!state.picking&&!state.compare;q('#makeSplit').classList.toggle('make-has-look',focused&&state.runs.length>0);view.classList.toggle('make-focused',focused);}
  function render(){renderGoals();const g=goal();if(g.intent)renderPictures(g);else renderLooks();renderRuns();layout();placeStatus();draftWarning();}
  function renderLooks(){
    const body=q('#makeBody');
    if(state.error){body.innerHTML='<p class="make-error" role="alert">'+escape(state.error)+' <button type="button" data-make-retry>Try again</button></p>';placeStatus();return;}
    if(!state.looks){body.innerHTML='<p class="muted">Loading looks…</p>';placeStatus();return;}
    const list=lookList();if(!list.some(l=>l.id===state.look))state.look=null;
    // Compare looks (#16) turns the gallery into checkboxes: two or three looks, one scene, one picture each.
    const compare=state.compare;if(compare)state.compareLooks=state.compareLooks.filter(id=>list.some(l=>l.id===id));
    const on=l=>compare?state.compareLooks.includes(l.id):l.id===state.look;
    const cards=list.map(l=>{const p=presetFor(l),thumb=thumbOf(l),why=compare?blocker(l,p):blocker(l);return '<article class="make-look'+(on(l)?' active':'')+'"><button type="button" class="make-look-select" data-make-look="'+escape(l.id)+'" role="'+(compare?'checkbox':'radio')+'" tabindex="'+(compare||l.id===(state.look||list[0]?.id)?'0':'-1')+'" aria-checked="'+on(l)+'">'
      +(thumb?'<img src="'+escape(thumb)+'" alt="" loading="lazy">':'<span class="make-look-blank" aria-hidden="true">✦</span>')
      +'<span class="make-look-text"><b>'+escape(l.name)+'</b>'+recipeLine(l)+pace(l)+tested(l)+recordSlot(l)+licence(p)+bestFor(l)+(tried(l)?'<small>Run on this PC before</small>':'')+'</span></button>'+(why?'<small class="make-warn make-look-text">'+blockerMarkup(l,why)+'</small>':'')+'</article>';}).join('');
    const chosen=current();
    if(chosen&&!state.picking&&!compare){const p=presetFor(chosen),thumb=thumbOf(chosen);
      body.innerHTML='<div class="make-chosen">'+(thumb?'<img src="'+escape(thumb)+'" alt="">':'<span class="make-look-blank" aria-hidden="true">✦</span>')+'<div><small>Look</small><b>'+escape(chosen.name)+'</b>'+recipeLine(chosen)+pace(chosen)+tested(chosen)+recordSlot(chosen)+licence(p)+bestFor(chosen)+'</div><button type="button" data-make-change>Change look</button></div><div id="makeComposer"></div>';}
    else body.innerHTML='<div class="make-step"><span>1</span><h2>'+(compare?'Choose two or three looks to compare':'Choose a look')+'</h2>'+(chosen&&!compare?'<button type="button" class="make-link" data-make-keep-look>Stay with '+escape(chosen.name)+'</button>':'')+(list.length>1?'<button type="button" class="make-link" data-make-compare aria-pressed="'+compare+'">'+(compare?'Back to one look':'Compare looks')+'</button>':'')+'</div><div class="make-looks" role="'+(compare?'group':'radiogroup')+'" aria-label="'+(compare?'Looks to compare':'Look')+'">'+cards+'</div><div id="makeComposer"></div>';
    renderComposer();layout();
  }
  // A look names its model and LoRA count on its card (owner, 19 Oct: someone choosing a model should see which look uses which).
  const recipeLine=l=>{const p=presetFor(l),n=adapters(l).length;return p?'<small class="make-recipe">'+escape(family(p))+' model'+(n?' · '+n+' LoRA'+(n>1?'s':''):'')+'</small>':'';};
  function shapeSize(preset,look,shape){
    const w=Number(look.body.controls.width||preset?.defaults?.width||1024),h=Number(look.body.controls.height||preset?.defaults?.height||1024),grid=preset?.dimension_multiple||64,round=v=>Math.max(grid,Math.round(v/grid)*grid);
    if(shape==='design')return[w,h];const area=w*h,long=Math.max(w,h),short=Math.min(w,h);
    if(shape==='square'){const s=round(Math.sqrt(area));return[s,s];}
    if(long===short){const a=round(Math.sqrt(area*1.5)),b=round(Math.sqrt(area/1.5));return shape==='portrait'?[b,a]:[a,b];}
    return shape==='portrait'?[short,long]:[long,short];
  }
  const shapeDefault=look=>('width' in look.body.controls||presetFor(look)?.width)&&SHAPE_FOR[state.goal]||'design';
  function renderComposer(){
    const box=q('#makeComposer'),look=current();if(!box)return;if(state.compare){renderCompareComposer();return;}
    if(!look){box.innerHTML='<p class="make-hint">Choose a look above. Each picture is one real run of that look on this PC; yours will differ.</p>';placeStatus();return;}
    // A slow look starts at one picture: four Krea pictures are about forty minutes, which nobody should get by default.
    const p=presetFor(look),why=blocker(look),example=look.body.scene_example||'',options=look.body.options||[],slow=speed(look)[0]==='slow';
    box.innerHTML='<div class="make-step"><span>2</span><h2>Describe your picture</h2></div><div class="make-composer"><div class="make-compose-main">'
      +'<label for="makeScene">'+escape(state.goal==='scene'?'Where is it, and what is there?':state.goal==='game'?'What is the item?':'Who or what, doing what, where?')+'</label>'
      +'<textarea id="makeScene" rows="3" maxlength="1000" placeholder="'+escape(example)+'"></textarea>'
      +'<div class="make-row">'+(example?'<button type="button" id="makeUseExample">Use the example</button>':'')+'<small>Plain words are fine. The look adds its own style and quality words.</small></div>'
      +options.map(o=>'<label class="make-check"><input type="checkbox" data-make-option="'+escape(o.id)+'"'+(o.default?' checked':'')+'> '+escape(o.label)+'</label>').join('')
      +'<details class="make-tune" id="makeTune"'+(state.tuneOpen?' open':'')+'><summary>Model, LoRAs and settings <small id="makeTuneSum"></small></summary><div id="makeTuneBody"></div></details>'
      +'<details class="make-tune" id="makeSweep"'+(sweepOf(look).open?' open':'')+'><summary>Compare one setting <small id="makeSweepSum"></small></summary><div id="makeSweepBody"></div></details>'
      +'</div><div class="make-compose-side">'
      +'<div class="make-pair"><label>Shape<select id="makeShape">'+Object.entries(SHAPES).map(([k,v])=>'<option value="'+k+'"'+(k===shapeDefault(look)?' selected':'')+'>'+v+(k==='design'?' · '+escape(look.body.controls.width||'')+'×'+escape(look.body.controls.height||''):'')+'</option>').join('')+'</select></label>'
      +'<label>How many<select id="makeCount"><option value="1"'+(slow?' selected':'')+'>1 picture</option><option value="2">2 pictures</option><option value="4"'+(slow?'':' selected')+'>4 to choose from</option></select></label></div>'
      // With Tune open the same multiplier sits above the adapters it scales, so this copy hides (make.css).
      +(adapters(look).length?'<label class="make-strength">Style strength <output id="makeStrengthOut">'+scaleOf(tuneOf(look))+'%</output><input type="range" id="makeStrength" min="0" max="150" step="10" value="'+scaleOf(tuneOf(look))+'" aria-describedby="makeStrengthHint"><small id="makeStrengthHint" class="muted">How strongly the look\u2019s '+adapters(look).length+' style LoRA'+(adapters(look).length>1?'s apply':' applies')+'. 100% is the look as made.</small></label>':'')
      +'<div id="makeDraftBox"></div>'
      +'<button type="button" id="makeEditor" class="make-link">Open in the full editor instead</button>'
      +'<details class="make-about"><summary>What this look uses</summary><p><b>Model:</b> '+escape(family(p)||look.body.preset_id)+(p?.model?.file?' <small class="muted">'+escape(p.model.file)+'</small>':'')+'</p>'
      +(adapters(look).length?'<p><b>LoRAs:</b></p><ul>'+adapters(look).map(a=>'<li>'+escape(short(a.name==='the recipe’s own LoRA'?'':a.name))+' at '+escape(a.strength)+(entry(a.name)?.trigger?' \u00b7 trigger <code>'+escape(entry(a.name).trigger)+'</code>':'')+'</li>').join('')+'</ul>':'<p>No LoRAs: the model and the wording carry this look.</p>')
      +(example?'<p><b>Example:</b> '+escape(example)+'</p>':'')
      +(look.body.notes?'<details class="make-maint"><summary>Details for maintainers</summary><p class="muted">'+escape(look.body.notes)+'</p></details>':'')+'</details>'
      +'</div>'+goBar(why?blockerMarkup(look,why):'')+'</div>';
    syncOperation();
    const scene=q('#makeScene');try{scene.value=sceneDraftValue();}catch{}
    scene.oninput=()=>{scene.removeAttribute('aria-invalid');scene.removeAttribute('aria-describedby');writeScene(scene.value);settleMissing();};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    q('#makeShape').onchange=q('#makeCount').onchange=()=>estimate();estimate();
    const strength=q('#makeStrength');if(strength)strength.oninput=()=>{const t=tuneOf(look);t.scale=Math.min(150,Math.max(0,Number(strength.value)||0));paintScale(t);tuneChanged(false);};
    q('#makeTune').ontoggle=e=>{state.tuneOpen=e.target.open;};
    q('#makeSweep').ontoggle=e=>{if(sweepOf(look).open===e.target.open)return;sweepOf(look).open=e.target.open;sweepPaint();syncOperation();estimate();};
    const kept=state.tune[look.id]?.composer;if(kept){delete state.tune[look.id].composer;
      const set=(el,v)=>{if(el&&v!=null&&[...(el.options||[{value:String(v)}])].some(o=>o.value===String(v)))el.value=String(v);};set(q('#makeShape'),kept.shape);set(q('#makeCount'),kept.count);
      // A run saved before Style strength joined the tune kept it with the composer.
      if(state.tune[look.id].scale==null&&kept.strength!=null&&strength){strength.value=kept.strength;strength.oninput();}
      for(const box of view.querySelectorAll('[data-make-option]'))if(typeof kept.options?.[box.dataset.makeOption]==='boolean')box.checked=kept.options[box.dataset.makeOption];
      say('That run\u2019s settings are back'+(tuneOf(look).reseed?'':', with its seed locked')+'. Change the words or a setting, then press Generate.');estimate();}
    renderTune();renderSweep();
  }
  const goBar=(why,label='Generate')=>'<div class="make-go"><button type="button" id="makeGenerate" class="primary"'+(why?' disabled aria-describedby="makeWhy"':'')+'>'+label+'</button><p id="makeEstimate" class="muted" aria-live="polite"></p><p id="makeWhy" class="make-warn" role="status">'+why+'</p></div>';
  const SCENE_FIRST='Describe your picture first, or press Use the example.';
  async function prepared(look,sweep=false,captured){
    // Every form value is read before the first await: a click on another look mid-request must not change this one.
    const field=q('#makeScene'),scene=field.value.trim();if(!scene){field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby','makeStatus');field.focus();throw Error(SCENE_FIRST);}
    const options=Object.fromEntries([...view.querySelectorAll('[data-make-option]')].map(i=>[i.dataset.makeOption,i.checked]));
    const shape=q('#makeShape').value,p=presetFor(look),[w,h]=shapeSize(p,look,shape),batch_count=Number(q('#makeCount').value);
    // An adapter added in an earlier session may have been uninstalled since: leave it out and say so, never send an unknown file.
    const inv=typeof installedLoras!=='undefined'&&installedLoras.length?new Set(installedLoras):null,gone=inv?(tuneOf(look).rows||[]).filter(r=>r.added&&!inv.has(r.name)):[];
    if(gone.length){const live=tuneOf(look);live.rows=live.rows.filter(r=>!gone.includes(r));tuneChanged(false);say('Left out '+gone.map(r=>r.name.replace(/\.safetensors$/,'')).join(', ')+': no longer installed.');}
    const t=structuredClone(tuneOf(look)),reseed=t.reseed;if(!reseed&&t.seed!=null&&!(Number.isSafeInteger(t.seed)&&t.seed>=0))throw Error('The seed must be a whole number, 0 or more.');
    const plan=sweep?sweepPlan(look,t):null;if(plan?.why)throw Error(plan.why);
    const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options}:{}),expected_revision:look.revision},captured);
    const base={...result.controls};
    if('width' in base||p?.width)Object.assign(base,{width:w,height:h});
    // One seed for every run of this press. It follows the recipe that runs: a switched model may bind one the look's own recipe does not (#1438).
    const seed=reseed?crypto.getRandomValues(new Uint32Array(1))[0]%2147483647:t.seed;
    // The run keeps its own settings, seed locked, so Edit and re-run changes only what you change next.
    const composer={shape,count:batch_count,options};
    const build=v=>{const controls=structuredClone(base);if(seed!=null&&bound(byId(v.preset)||p,'seed'))controls.seed=seed;
      // Style strength (v.scale) scales the tuned adapters; two decimals, inside the server's 0-2 adapter range.
      const preset_id=applyTune(controls,look,v),tp=byId(v.preset)||p,notes=[];
      // A switched model may not offer the look's sampler or scheduler: use its default and say so (#1506 follow-up).
      for(const key of ['sampler','scheduler']){const choices=tp.choices?.[key],value=controls[key],fallback=tp.defaults?.[key];
        if(key in controls&&choices?.length&&!choices.includes(value)&&choices.includes(fallback)){controls[key]=fallback;notes.push("This look's "+key+' '+value+' is not offered by '+(tp.name||tp.id)+'; using its default '+fallback+'.');}}
      return{preset_id,controls,look:result.look,notes,tuned:tuneSummary(look,v),tune:{...v,reseed:controls.seed==null&&v.reseed,seed:controls.seed??v.seed,composer}};};
    // A compare reports a variant's swap only once that variant is sent (generateSweep); the base run is not sent then.
    const {notes,...first}=build(t),variants=plan?plan.runs.map(r=>({...build(r.tune),label:r.label})):null;
    return{...first,batch_count,scene,notice:[...new Set([...(result.notices||[]),...(plan?[]:notes)])].join(' '),...(plan?{axis:plan.axis.label,variants}:{})};
  }
  let estimateEpoch=0;
  async function estimate(retry=false){
    const look=current(),out=q('#makeEstimate');if(!look||!out)return;const epoch=++estimateEpoch,p=presetFor(look),[w,h]=shapeSize(p,look,q('#makeShape').value),t=state.tune[look.id],plan=sweepPlan(look);
    if(plan&&!plan.why){let guessed=false;const each=await Promise.all(plan.runs.map(r=>json('/api/estimate',{preset_id:(byId(r.tune.preset)||p).id,controls:{...look.body.controls,width:w,height:h,...(r.tune.steps!=null?{steps:r.tune.steps}:{})},batch_count:1,reference_count:0}).then(e=>(guessed||=rough(e),Number(e.estimate_seconds)||0),()=>0)));
      if(epoch!==estimateEpoch||!out.isConnected)return;const total=each.reduce((x,y)=>x+y,0),unknown=each.filter(x=>!x).length;
      out.classList.toggle('make-warn',total>600);out.textContent=plan.runs.length+' pictures, one per value'+(total?' · about '+duration(total)+' in total'+(unknown?' (no timing yet for '+unknown+')':'')+basis({confidence:guessed?'none':''}):' · no timing yet for these settings on this PC.');return;}
    try{const e=await json('/api/estimate',{preset_id:tunedPreset(look).id,controls:{...look.body.controls,width:w,height:h,...(t?.turbo&&turboFits(look,t)?{steps:TURBO.steps}:t?.steps!=null?{steps:t.steps}:{})},batch_count:Number(q('#makeCount').value),reference_count:0});if(epoch!==estimateEpoch||!out.isConnected)return;
      const n=Number(q('#makeCount').value)||1,lab=rough(e)&&labTimed(look,t,w,h)&&lookTiming(look),total=lab?lab.seconds*n:e.estimate_seconds;
      out.classList.toggle('make-warn',total>600);out.textContent=lab?'About '+duration(total)+(n>1?' for '+n+' pictures, ~'+Math.round(lab.seconds)+' s each':'')+'. '+lab.source:total?'About '+duration(total)+' in total'+basis(e):'No timing yet: this look has not run here at this size.';}
    catch{if(epoch===estimateEpoch&&!retry)setTimeout(()=>{if(epoch===estimateEpoch)estimate(true);},1500);}
  }
  const duration=s=>s<90?Math.round(s)+' s':Math.round(s/60)+' min';
  // /api/estimate answers even with no comparable run here (confidence none: a generic guess with a wide range), so the words say which it is.
  // The lab median holds only for the look as timed: its model, steps (turbo Draft has its own), sampler and LoRA files, at about its designed pixel count
  // (strengths, words, negative and seed do not change the time). Anything else falls back to the server's guess, worded as one.
  const labTimed=(look,t,w,h)=>{const p=presetFor(look),[dw,dh]=shapeSize(p,look,'design'),own=adapters(look);
    return(!t||(!t.preset||t.preset===p?.id)&&t.steps==null&&!t.turbo&&!t.sampler&&(t.rows||[]).every(r=>own.some(a=>a.key===r.slot&&(!r.name||r.name===a.name))))&&Math.abs(w*h-dw*dh)<=0.05*dw*dh;};
  const rough=e=>e?.confidence==='none',basis=e=>rough(e)?', a rough guess: nothing like it has run on this PC yet.':', from earlier runs on this PC.';
  function syncOperation(){
    placeStatus();statusEl.textContent=state.status;
    const g=goal(),why=g.intent?goalBlocker(g,goalRoute(g)):state.compare?compareBlocker():current()&&lookWhy(current());
    const generate=q('#makeGenerate'),editor=q('#makeEditor');if(generate)generate.disabled=state.busy||!!why;if(editor)editor.disabled=state.busy;
    // The blocker line stays in the page as a status region; it is rewritten only when the reason changes, so it is announced once.
    if(generate){if(why)generate.setAttribute('aria-describedby','makeWhy');else generate.removeAttribute('aria-describedby');}
    const said=q('#makeWhy');if(said&&said.dataset.why!==(why||'')){said.dataset.why=why||'';said.innerHTML=!why?'':g.intent?goalWhy(goalRoute(g),why):state.compare?escape(why):blockerMarkup(current(),why,whyPreset(current()));}
  }
  const say=text=>{state.status=text;state.missing='';syncOperation();};
  // A refusal that names a missing answer clears itself once the answer is given (audit N10: a stale "Choose the pose first").
  function sayMissing(text){say(text);state.missing=text;}
  function settleMissing(){if(!state.missing||state.status!==state.missing)return;const g=goal(),m=g.intent?goalMissing(g,goalRoute(g),state.form):q('#makeScene')?.value.trim()?null:[0,SCENE_FIRST];if(m?.[1]!==state.missing)say('');}
  // After a press the new card comes into view: on a phone it sits below the Generate bar (audit N2).
  const showRun=id=>q('[data-run="'+CSS.escape(id)+'"]')?.scrollIntoView({block:'nearest'});
  async function generate(){
    const look=current(),runGoal=state.goal,captured=requestPrivacy(),epoch=privacyEpoch;if(!look||state.busy)return;
    const why=lookWhy(look);if(why){say(why);return;}if(sweepPlan(look))return generateSweep(look);
    state.busy=true;say('Preparing\u2026');
    try{
      const request=await prepared(look,false,captured);if(epoch===privacyEpoch)say('Sending to ComfyUI…');
      const {scene,tune,tuned,notice,...submit}=request;const job=await json('/api/jobs',{...submit,label:'Make · '+look.name},captured);job.privacy=job.privacy||captured.privacy;
      state.runs.unshift({job,look:look.name,lookId:look.id,goal:runGoal,scene,tune,tuned});remember();if(epoch===privacyEpoch)say('Started. Your pictures appear in Your pictures as they finish; you can leave this page.'+(notice?' '+notice:''));
      renderRuns();if(epoch===privacyEpoch)showRun(job.id);poll(job.id);if(epoch===privacyEpoch)window.StudioPrivacy?.submitted?.(captured);
      if(typeof refresh==='function')void refresh();
    }catch(error){if(epoch===privacyEpoch){if(error.message===SCENE_FIRST)sayMissing(error.message);else say(error.message);}}
    finally{state.busy=false;syncOperation();}
  }
  async function openInEditor(){
    const look=current(),captured=requestPrivacy(),epoch=privacyEpoch;if(!look||state.busy)return;
    state.busy=true;say('Preparing…');
    try{const request=await prepared(look,false,captured);if(epoch!==privacyEpoch)throw Error('The creation privacy changed. Your draft is kept; open it in the full editor again.');applySaved({preset:request.preset_id,look:request.look,controls:request.controls,batch_count:request.batch_count,parent_assets:[],references:[],privacy:captured.privacy},{});showView('create');say('Ready in the full editor.'+(request.notice?' '+request.notice:''));}
    catch(error){if(epoch===privacyEpoch)say(error.message);}
    finally{state.busy=false;syncOperation();}
  }
  // Keep / Not this: the library's own review field, one press, pressing again clears it.
  // Keep / Not this: the library's own review field. Saves run one after another (the library takes one command at a
  // time), and pressing the recorded decision again clears it, decided from the refreshed record, not page memory.
  let reviewQueue=Promise.resolve();
  // One write per target at a time (Muse lens, 19 Oct): a redraw can bring back an enabled button mid-save, so a second press of Keep,
  // Resume, Save character or Put away is dropped while the first is in flight, instead of applying twice or undoing itself.
  const inflight=new Set(),once=async(key,fn)=>{if(inflight.has(key))return;inflight.add(key);try{return await fn();}finally{inflight.delete(key);}};
  function review(button){const key='review:'+button.dataset.asset;if(inflight.has(key))return reviewQueue;inflight.add(key);button.disabled=true;reviewQueue=reviewQueue.then(()=>saveReview(button)).finally(()=>inflight.delete(key));return reviewQueue;}
  async function saveReview(button){
    const id=button.dataset.asset,epoch=privacyEpoch;
    try{if(await refreshAssets(true)===false){await new Promise(r=>setTimeout(r,600));await refreshAssets(true);}
      if(epoch!==privacyEpoch)return;
      delete state.review[id];const value=reviewOf(id)===button.dataset.makeReview?'unreviewed':button.dataset.makeReview;
      await mutateAssets({action:'edit',ids:[id],review:value});if(epoch!==privacyEpoch)return;state.review[id]=value;renderRuns();void refreshRecord();
      say(value==='selected'?'Kept. Kept pictures are in the library under Kept.':value==='rejected'?'Marked: not this one.':'Decision cleared.');}
    catch(error){if(epoch!==privacyEpoch)return;button.disabled=false;say('Could not save that: '+error.message);}
  }
  const reviewOf=id=>state.review[id]??(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===id)?.review)??'unreviewed';
  const timers=new Map();
  const stamp=job=>job.status+'|'+(job.outputs||[]).map(o=>o.asset_id||'').join(',')+'|'+(job.message||'')+'|'+(job.tracking_disposition?.status||'')+'|'+(job.queue_ahead??'');
  // A failed read is not the end of a run (#1438): it keeps checking, backing off to 30 s, and says so on its card.
  const POLL=2500,POLL_MAX=30000;
  function poll(id,misses=0){clearTimeout(timers.get(id));timers.set(id,setTimeout(async()=>{
    const run=state.runs.find(r=>r.job.id===id),epoch=privacyEpoch;if(!run){timers.delete(id);return;}
    try{const job=await json('/api/jobs/'+encodeURIComponent(id),undefined,requestPrivacy(runPrivacy(run)));if(epoch!==privacyEpoch||!state.runs.includes(run))return;const changed=stamp(job)!==stamp(run.job)||run.lost;run.job={...job,privacy:job.privacy||runPrivacy(run)};run.lost=false;
      // Redraw only when something changed, so a poll never resets an open menu or steals keyboard focus.
      if(changed){renderRuns();remember();if(job.outputs?.some(o=>o.asset_id)){state.pictures=null;refreshPickers();}}
      if(observing(run))poll(id,run.job.status==='uncertain'?4:0);else timers.delete(id);}
    catch{if(!state.runs.includes(run)){timers.delete(id);return;}if(!run.lost){run.lost=true;renderRuns();}poll(id,misses+1);}},Math.min(POLL_MAX,POLL*2**Math.min(misses,4))));}
  // A finished run's pictures join an open picture grid at once, so the next goal can start from them.
  function refreshPickers(){const g=goal();if(!g.intent)return;for(const [id,attr] of [['makePictures','data-make-pick'],['makePosePictures','data-make-pose-pick']])if(q('#'+id))void fillPictures(g,id,attr);}
  // A painting card says how long it has run and, from /api/estimate, about how long such a run takes on this PC; the tab title
  // counts unfinished runs and shows a tick when one finished unseen. Text only: no notification, sound or extra press. The clock is
  // aria-hidden inside the live #makeRuns region so it never announces every second; the estimate reads the run's own privacy history.
  const PAINTING=['submitting','running','observing'],clock=s=>{s=Math.max(0,Math.round(s));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');};
  function runClock(job,e,now){if(!PAINTING.includes(job.status)||!job.started_at)return '';const spent=now-Number(job.started_at),t=rough(e)?0:Number(e?.estimate_seconds)||0;
    return clock(spent)+(t?(spent>t*1.5?', longer than the usual '+duration(t):' of about '+duration(t)):'');}
  // ComfyUI's slow state on this PC (Klein 9B at 53-63 s/step instead of 6.5) survives idle and /free; only a restart cures it (#1702).
  // Said once, only against a well-measured usual time, and only as advice: nothing is cancelled, restarted or sent again.
  const SLOW='Much slower than usual on this PC. If the next run is slow too, restart ComfyUI between runs.';
  const slowRun=(job,e,now)=>PAINTING.includes(job.status)&&!!job.started_at&&e?.confidence==='high'&&(t=>t>0&&now-job.started_at>Math.max(3*t,t+120))(Number(e.estimate_seconds)||0);
  const estimates=new Map(),baseTitle=document.title;let clockTimer=0,wasBusy=0,doneUnseen=false;
  function runTitle(){const busy=state.runs.filter(r=>!FINAL.includes(r.job.status)).length;if(busy<wasBusy&&document.hidden)doneUnseen=true;wasBusy=busy;
    const next=(busy?'('+busy+') ':doneUnseen?'✓ ':'')+baseTitle;if(document.title!==next)document.title=next;}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&doneUnseen){doneUnseen=false;runTitle();}});
  function tick(){const now=Date.now()/1000;let live=false;clearTimeout(clockTimer);
    for(const el of document.querySelectorAll('[data-make-clock]')){const run=state.runs.find(r=>r.job.id===el.dataset.makeClock),job=run?.job;if(!job)continue;const rp=runPrivacy(run);
      if(PAINTING.includes(job.status)&&job.started_at&&!estimates.has(job.id)){estimates.set(job.id,null);json('/api/estimate',{preset_id:job.preset_id,controls:job.controls||{},batch_count:job.batch_count||1,reference_count:(job.references||[]).length},requestPrivacy(rp,rp)).then(e=>estimates.set(job.id,e),()=>{});}
      const text=runClock(job,estimates.get(job.id),now),shown=text?' · '+text:'';live||=!!text;if(el.textContent!==shown)el.textContent=shown;
      const slow=el.closest?.('[data-run]')?.querySelector('[data-make-slow]');if(slow){const on=slowRun(job,estimates.get(job.id),now);if(slow.hidden===on){slow.hidden=!on;slow.textContent=on?SLOW:'';}}}
    runTitle();clockTimer=live?setTimeout(tick,1000):0;}
  function words(job){return({queued:'Waiting its turn'+(job.queue_ahead>0?' · '+job.queue_ahead+' ahead':''),waiting:'Waiting for memory',submitting:'Sending',running:'Painting',observing:'Painting',completed:'Done',failed:'Did not finish',partial:'Some pictures did not finish',uncertain:'Outcome unknown: nothing was sent again',cancelled:'Cancelled',not_submitted:'Not sent'})[job.status]||job.status;}
  // An uncertain or partial run offers what the full editor's Problems list offers, on its own card: Resume observation reads
  // ComfyUI again for the retained prompt IDs, Stop tracking records a reason. Neither ever sends the picture again.
  function recovery(job){
    const stopped=job.tracking_disposition?.status==='stopped',resume=stopped?job.can_resume_tracking:!job.has_pending_submission&&['uncertain','partial'].includes(job.status)&&job.prompt_ids?.length,id=escape(job.id);
    if(!resume&&!job.can_stop_tracking)return'';
    return '<div class="make-recover"><p class="muted">'+(job.status==='partial'?'ComfyUI may still hold the missing pictures.':'ComfyUI may still have finished it.')+' Resume checks again; nothing is sent again.</p>'+(resume?'<button type="button" data-make-resume="'+id+'">Resume observation</button>':'')
      +(job.can_stop_tracking?'<details class="make-more" data-more="stop:'+id+'"><summary>Stop tracking\u2026</summary><label>Reason for stopping<input data-make-stop-reason="'+id+'" maxlength="1000"></label><button type="button" data-make-stop="'+id+'">Stop tracking</button><small class="muted">ComfyUI keeps a finished prompt only in memory: after a ComfyUI restart Resume cannot collect it. Resume first if you may want it.</small></details>':'')+'</div>';
  }
  async function recover(button){
    const action=button.dataset.makeResume?'resume':'stop-tracking',id=button.dataset.makeResume||button.dataset.makeStop,run=state.runs.find(r=>r.job.id===id),epoch=privacyEpoch;if(!run)return;const captured=requestPrivacy(runPrivacy(run));
    let body={};if(action==='stop-tracking'){const field=q('[data-make-stop-reason="'+CSS.escape(id)+'"]'),reason=field?.value.trim();if(!reason){field?.setAttribute('aria-invalid','true');field?.setAttribute('aria-describedby','makeStatus');field?.focus();say('Give a reason before stopping tracking.');return;}body={reason};}
    button.disabled=true;
    try{const job=await json('/api/jobs/'+encodeURIComponent(id)+'/'+action,body,captured);if(epoch!==privacyEpoch)return;run.job={...run.job,...job};run.lost=false;renderRuns();remember();if(observing(run))poll(id);else{clearTimeout(timers.get(id));timers.delete(id);}
      say(action==='resume'?'Checking ComfyUI again for this run. Nothing is sent again.':'Tracking stopped. Its record and any pictures stay in the library.');}
    catch(error){if(epoch!==privacyEpoch)return;button.disabled=false;say(error.message);}
  }
  const marks=a=>{const review=reviewOf(a),mark=(value,label,key=value==='selected'?'K':'X')=>'<button type="button" data-make-review="'+value+'" data-asset="'+escape(a)+'" aria-pressed="'+(review===value)+'" aria-keyshortcuts="'+key+'" title="'+key+' on a focused picture">'+(review===value?'✓ '+(value==='selected'?'Kept':'Marked: not this'):label)+'</button>';return mark('selected','★ Keep')+mark('rejected','Not this');};
  function actions(job,output){
    const a=output.asset_id;if(!a)return'<small class="muted">Saving to the library…</small>';
    const varyBox=document.createElement('div');varyBox.innerHTML=window.StudioWorkbench?.varyMarkup?.(job.preset_id,job.id,a,job.status)||'';
    // Vary keeps its disabled button and linked reason, as Fix and Upscale do.
    if(varyBox.querySelector('button:disabled'))for(const hint of varyBox.querySelectorAll('small[id]'))hint.textContent=inMake(hint.textContent);
    else{const busy=state.varying.has(a),held=state.varyHeld.has(a);for(const b of varyBox.querySelectorAll('[data-ux-vary]')){b.dataset.makeVary=b.dataset.uxVary;b.removeAttribute('data-ux-vary');b.disabled=busy||held;}
      if(busy||held)for(const hint of varyBox.querySelectorAll('small[id]'))hint.textContent=held?VARY_HELD:'Starting the variations for this picture. Please wait.';}const vary=varyBox.innerHTML;
    // Next steps open Make's own picture goals with this picture chosen; other fixes still go through the full handoff. Change one thing
    // (outfit, colour), New pose and Restyle sit beside Vary and the fixes: they are the tweaks people name (owner, 19 Oct); the rest wait under More.
    const hand=(intent,label)=>'<button type="button" data-ux-handoff="'+escape(a)+'" data-ux-handoff-intent="'+intent+'">'+label+'</button>',from=(intent,label)=>'<button type="button" data-make-from="'+intent+'" data-asset="'+escape(a)+'">'+label+'</button>';
    // A fix that cannot run stays on screen, disabled, with its reason beside it (one line per distinct reason), as the Fix or upscale goal does.
    const reasons=[...new Set(Object.keys(POLISH).map(k=>state.polish[a+':'+k]).filter(x=>x&&!x.ok).map(x=>inMake(x.reason)))],whyId=r=>'makePolishWhy-'+escape(a)+'-'+reasons.indexOf(r);
    const polish=kind=>{const plan=state.polish[a+':'+kind],why=plan&&!plan.ok?inMake(plan.reason):'',busy=state.polishing.has(a+':'+kind);
      return '<button type="button" data-make-polish="'+kind+'" data-asset="'+escape(a)+'"'+(busy||why?' disabled':'')+(why?' aria-describedby="'+whyId(why)+'"':'')+'>'+polishName(a,kind)+(plan?.seconds?' <small>~'+duration(plan.seconds)+'</small>':'')+(busy?' …':'')+'</button>';};
    return '<div class="make-actions">'+marks(a)+'<button type="button" class="make-next-open" data-make-select="'+escape(a)+'" data-run-id="'+escape(job.id)+'">Next steps…</button><div class="make-next" role="group" aria-label="Next steps for this picture">'+characterMarkup(job,a)+vary+polishKinds(a).map(polish).join('')+from('edit','Change one thing')+from('combine','New pose')+from('restyle','Restyle')+(Object.keys(POLISH).some(k=>state.polishing.has(a+':'+k))?'<small class="make-action-reason">Starting the finishing pass for this picture. Please wait.</small>':'')+reasons.map(r=>'<small class="make-warn make-polish-why" id="'+whyId(r)+'">'+escape(r)+'</small>').join('')+(merged(a)?'<small class="muted make-polish-hint">'+FIX_HINT+'</small>':'')+(state.polish[a+':refine']?.ok?'<small class="muted make-polish-hint">'+REFINE_HINT+'</small>':'')+(state.polish[a+':upscale']?.ok?'<small class="muted make-polish-hint">'+UP_HINT+'</small>':'')
      +'<details class="make-more" data-more="'+escape(a)+'"><summary>More</summary><button type="button" data-ux-open-asset="'+escape(a)+'">Open full size</button>'+hand('repair','Other fixes\u2026')+from('animate','Animate')+from('mesh','Make it 3D')+'</details></div></div>';
  }
  // One picture of a card shows its next steps at a time (owner, 19 Oct: four pictures each with eleven buttons is a wall). Keep and Not this
  // stay on every picture; "Next steps…" moves the steps to another. The first saved picture starts selected; the others' steps stay in the
  // page, hidden, so nothing about them changes but where they show.
  const selectedOf=job=>{const ids=(job.outputs||[]).filter(o=>o.asset_id&&picture(o)).map(o=>o.asset_id);return ids.includes(state.selected[job.id])?state.selected[job.id]:ids[0];};
  // My character (#1205): any finished picture can become a character's canon (owner, 16 Oct), with its words. Saving writes one Workspace card and
  // never submits. The form keeps its answers in state, so a redraw of the runs list does not lose what was typed.
  // v2: Edit and Put away / Restore (revision-checked: a 409 means the card changed elsewhere, so it is reloaded), a read-only
  // Line-up per character, and a once-offered note that saves the old per-picture answers as a character. None of it submits.
  const usableCharacters=()=>(state.characters||[]).filter(c=>c.usable&&c.canon_asset_id);
  const awayCharacters=()=>(state.characters||[]).filter(c=>c.trashed_at);
  const charField=(key,label,max,area)=>{const v=escape(state.charForm[key]);return '<label>'+label+(area?'<textarea data-make-char="'+key+'" rows="2" maxlength="'+max+'">'+v+'</textarea>':'<input data-make-char="'+key+'" maxlength="'+max+'" value="'+v+'">')+'</label>';};
  // mode "create" is named by the canon picture, "edit" by the card. Only Edit shows the avoid words: they are stored and used
  // when a goal's request has a negative field (goalGenerate), nowhere else.
  const characterForm=(id,mode,note)=>'<form class="make-character-form" data-make-character-form="'+escape(id)+'" data-mode="'+mode+'">'+charField('name','Name',120)+charField('who','Who they are',600,true)+charField('clothes','Clothes and colours',600,true)+(mode==='edit'?charField('avoid','Words to keep out of their pictures',600,true):'')
    +'<div class="make-row"><button type="submit">Save character</button><button type="button" class="make-link" data-make-character-cancel>Cancel</button></div><small class="muted">'+note+'</small></form>';
  const CANON_NOTE='This picture becomes the character’s canon. Saving makes no picture.';
  const clearCharForms=()=>{state.charSave=state.charEdit=state.charMigrate=null;state.charForm={};};
  // Redraw the picker only where it is showing (a chosen picture shows the composer instead).
  const refreshCharacters=()=>{const g=goal();if(CHARACTER_GOALS.includes(g.intent)&&(!state.pick||state.repicking))void renderPictures(g);};
  function characterMarkup(job,a){
    if(!a)return'';
    // A put-away picture cannot be a canon (the server refuses a trashed asset): say so instead of offering a form that fails.
    if(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===a)?.trashed_at)return'<small class="muted">Put away in the library. Restore it to make it a character.</small>';
    const owner=usableCharacters().find(c=>c.canon_asset_id===a);if(owner)return'<small class="make-canon">Canon of '+escape(owner.name)+'</small>';
    return state.charSave!==a?'<button type="button" data-make-character-save="'+escape(a)+'">Make this my character…</button>':characterForm(a,'create',CANON_NOTE);
  }
  // Prefilled from the run where it is plain: a pose run's answers, else the scene as typed. A look run names its look.
  function openCharacterForm(a,runId){const run=state.runs.find(r=>r.job.id===runId)||state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===a));
    if(!usePrivacy({privacy:runPrivacy(run||{})}))return;
    clearCharForms();state.charSave=a;state.charForm={name:'',who:String(run?.fills?.who||run?.scene||'').slice(0,600),clothes:String(run?.fills?.clothes||'').slice(0,600),look:run?.lookId||null};renderRuns();refreshCharacters();q('[data-make-char="name"]')?.focus();}
  function openCharacterEdit(id){const c=(state.characters||[]).find(x=>x.id===id);if(!c)return;clearCharForms();state.charEdit=id;
    state.charForm={name:c.name,who:c.body.who||'',clothes:c.body.clothes||'',avoid:c.body.avoid||''};renderRuns();refreshCharacters();q('[data-make-char="name"]')?.focus();}
  async function saveCharacter(form){
    const mode=form.dataset.mode,id=form.dataset.makeCharacterForm,f={...state.charForm},name=String(f.name||'').trim(),who=String(f.who||'').trim(),captured=requestPrivacy(),epoch=privacyEpoch;
    const missing=!name?'name':!who?'who':null;if(missing){const el=q('[data-make-char="'+missing+'"]');if(el)markMissing(el);sayMissing(missing==='name'?'Name the character first.':'Say who they are first.');return;}
    const button=form.querySelector('[type=submit]');if(button)button.disabled=true;const clothes=String(f.clothes||'').trim(),avoid=String(f.avoid||'').trim();
    try{
      if(mode==='edit'){const c=(state.characters||[]).find(x=>x.id===id);if(!c)throw Error('That character is no longer here.');
        await json('/api/characters',{action:'edit',id,expected_revision:c.revision,name,body:{who,...(clothes?{clothes}:{}),...(avoid?{avoid}:{}),...(c.body.look_id?{look_id:c.body.look_id}:{})}},{...captured,scope:classified(c)});
        if(epoch!==privacyEpoch)return;clearCharForms();await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();q('[data-make-character-edit="'+CSS.escape(id)+'"]')?.focus();sayChars('Saved the changes to “'+name+'”.');return;}
      await json('/api/characters',{action:'create',kind:'character',name,canon_asset_id:id,body:{who,...(clothes?{clothes}:{}),...(f.look?{look_id:f.look}:{})}},captured);
      if(epoch!==privacyEpoch)return;clearCharForms();await loadCharacters();if(epoch!==privacyEpoch)return;renderRuns();refreshCharacters();sayChars('Saved “'+name+'”. Choose it under Your characters in Character in a new pose.');}
    catch(error){if(epoch!==privacyEpoch)return;if(button)button.disabled=false;
      if(error.status===409&&mode==='edit'){clearCharForms();await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();sayChars('“'+name+'” changed somewhere else, so it was reloaded. Your edit was not saved; edit again if you still want it.');return;}
      say('Could not save the character: '+error.message);}
  }
  // Put away and Restore name the revision they read. A 409 reloads the list and changes nothing.
  async function characterCommand(id,action){const c=(state.characters||[]).find(x=>x.id===id),captured=requestPrivacy(),epoch=privacyEpoch;if(!c)return;
    try{await json('/api/characters',{action,id,expected_revision:c.revision},{...captured,scope:classified(c)});if(epoch!==privacyEpoch)return;if(state.character===id&&action==='trash')state.character=null;if(state.charEdit===id)clearCharForms();await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();
      if(action==='trash'){q('.make-away summary')?.focus();sayChars('Put “'+c.name+'” away. It waits under Put away if you want it back.');}
      else{q('[data-make-character="'+CSS.escape(id)+'"]')?.focus();sayChars('Restored “'+c.name+'”.');}}
    catch(error){if(epoch!==privacyEpoch)return;if(error.status===409){await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();sayChars('“'+c.name+'” changed somewhere else, so it was reloaded. Nothing was changed.');return;}say('Could not '+(action==='trash'?'put it away':'restore it')+': '+error.message);}
  }
  // Use as canon: one edit with only canon_asset_id and the revision read; the words are untouched. The server refuses a put-away picture; a 409 reloads and changes nothing.
  async function swapCanon(id,asset){const c=usableCharacters().find(x=>x.id===id),captured=requestPrivacy(),epoch=privacyEpoch;if(!c||asset===c.canon_asset_id)return;
    try{await json('/api/characters',{action:'edit',id,expected_revision:c.revision,canon_asset_id:asset},{...captured,scope:classified(c)});if(epoch!==privacyEpoch)return;
      await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();q('[data-make-character="'+CSS.escape(id)+'"]')?.focus();sayChars('“'+c.name+'” now uses that picture as its canon. Choose the character again to use it.');}
    catch(error){if(epoch!==privacyEpoch)return;if(error.status===409){await loadCharacters();if(epoch!==privacyEpoch)return;refreshCharacters();sayChars('“'+c.name+'” changed somewhere else, so it was reloaded. The canon was not changed.');return;}sayChars('Could not change the canon: '+error.message);}
  }
  // A failed read keeps the list already shown and says so; the saying that follows a command appends it, so it is not overwritten.
  const STALE=' Your characters could not be refreshed, so the list shown may be out of date.';
  // A chosen character whose words changed (edited here or elsewhere) refreshes the form's who and clothes, which were copied when it was chosen.
  async function loadCharacters(){const was=(state.characters||[]).find(c=>c.id===state.character),epoch=privacyEpoch;
    try{const data=await json('/api/characters');if(epoch!==privacyEpoch)return;state.characters=(data.characters||[]).filter(inScope);state.charStale=false;}catch{if(epoch!==privacyEpoch)return;state.charStale=true;say(STALE.trim());return;}
    const now=state.characters.find(c=>c.id===state.character);if(was&&now&&(was.body.who!==now.body.who||was.body.clothes!==now.body.clothes)){state.form.who=now.body.who||'';state.form.clothes=now.body.clothes||'';}}
  const sayChars=text=>say(text+(state.charStale?STALE:''));
  // Picture goals that take a character list the saved ones first. Choosing one picks its canon as it is and fills its words.
  const CHARACTER_GOALS=['edit','repair','restyle','combine'];
  function characterChooser(g){const list=usableCharacters(),away=awayCharacters();if(!CHARACTER_GOALS.includes(g.intent)||!list.length&&!away.length)return'';
    const open=k=>state.openers.has(k)?' open':'',editing=list.find(c=>c.id===state.charEdit),id=c=>escape(c.id);
    return '<section class="make-characters" aria-labelledby="makeCharactersTitle"><h3 id="makeCharactersTitle" tabindex="-1">Your characters</h3>'
      +(list.length?'<div class="make-pictures">'+list.map(c=>'<div class="make-char"><button type="button" data-make-character="'+id(c)+'"><img src="'+thumbUrl({id:c.canon_asset_id,privacy:classified(c)})+'" alt="" loading="lazy"><small>'+escape(c.name)+'</small></button>'
        +'<div class="make-char-links"><button type="button" class="make-link" data-make-character-edit="'+id(c)+'" aria-label="Edit '+escape(c.name)+'">Edit</button><button type="button" class="make-link" data-make-character-away="'+id(c)+'" aria-label="Put away '+escape(c.name)+'">Put away</button></div></div>').join('')+'</div>':'<p class="muted">All your characters are put away.</p>')
      +(editing?characterForm(editing.id,'edit','Saving changes the words only; the canon picture stays. Saving makes no picture.'):'')
      +list.map(c=>'<details class="make-lineup" data-open-key="lineup:'+id(c)+'"'+open('lineup:'+c.id)+'><summary>Line-up: '+escape(c.name)+'</summary><div data-make-lineup="'+id(c)+'"><p class="muted">Reading your pictures…</p></div></details>').join('')
      +(away.length?'<details class="make-away" data-open-key="away"'+open('away')+'><summary>Put away ('+away.length+')</summary>'+away.map(c=>'<div class="make-away-row"><span>'+escape(c.name)+'</span><button type="button" class="make-link" data-make-character-restore="'+id(c)+'" aria-label="Restore '+escape(c.name)+'">Restore</button></div>').join('')+'</details>':'')+'</section>';}
  // The line-up (drift check): the canon pinned first, then kept pictures whose lineage reaches the canon, newest first, all at one
  // height. It reads the Workspace list Make already loaded (each picture's lineage names its parent pictures): no new route, no
  // generation. A parent that is put away or not a picture breaks the chain there. Direct children only would miss edits of edits.
  const LINEUP_MAX=24;
  function lineupMarkup(c){
    const pics=state.pictures||[],canon=pics.find(a=>a.id===c.canon_asset_id)||{id:c.canon_asset_id,privacy:classified(c)},family=new Set([c.canon_asset_id]),rec=(c.lineage||[]).find(l=>l?.role==='canon');
    // Seeded from the recorded canon identity too: when the recorded asset is put away and a live copy of its bytes stands in (characters.py
    // canon_asset), kept pictures still descend from the recorded asset or from any picture with the recorded sha256.
    if(rec?.asset_id)family.add(rec.asset_id);if(rec?.sha256)for(const a of pics)if(a.sha256===rec.sha256)family.add(a.id);
    for(let grew=true;grew;){grew=false;for(const a of pics)if(!family.has(a.id)&&(a.lineage||[]).some(p=>family.has(p?.asset_id??p))){family.add(a.id);grew=true;}}
    const kept=pics.filter(a=>a.id!==c.canon_asset_id&&family.has(a.id)&&(state.review[a.id]??a.review)==='selected'),shown=kept.slice(0,LINEUP_MAX);
    const item=(a,canonTag)=>'<button type="button" class="make-lineup-item'+(canonTag?' make-lineup-canon':'')+'" data-ux-open-asset="'+escape(a.id)+'"><img src="'+thumbUrl(a)+'" alt="'+escape(canonTag?'Canon picture of '+c.name:pictureLabel(a))+'" loading="lazy">'+(canonTag?'<small class="make-lineup-tag">Canon</small>':'')+'</button>';
    // Each kept picture can become the canon: the owner's own press, never inferred (#1205, owner 27 Sep). Saving makes no picture.
    const cell=a=>'<div class="make-lineup-cell">'+item(a)+'<button type="button" class="make-link" data-make-canon="'+escape(a.id)+'" data-make-canon-of="'+escape(c.id)+'" aria-label="Use this picture as the canon of '+escape(c.name)+'">Use as canon</button></div>';
    return '<div class="make-lineup-strip">'+item(canon,true)+shown.map(cell).join('')+'</div>'+(kept.length?'':'<p class="muted">No kept picture comes from the canon yet. Keep one made from it and it appears here.</p>')
      +(kept.length>shown.length?'<p class="muted">'+(kept.length-shown.length)+' older kept picture'+(kept.length-shown.length===1?'':'s')+' not shown. The line-up holds the newest '+LINEUP_MAX+'.</p>':'');
  }
  async function fillLineups(){const boxes=[...view.querySelectorAll('[data-make-lineup]')].filter(b=>b.closest('details').open),epoch=privacyEpoch;if(!boxes.length)return;
    try{await loadPictures();if(epoch!==privacyEpoch)return;}catch(error){if(epoch!==privacyEpoch)return;for(const b of boxes)b.innerHTML='<p class="make-error">'+escape(error.message)+'</p>';return;}
    for(const b of boxes){const c=usableCharacters().find(x=>x.id===b.dataset.makeLineup);if(c&&b.isConnected)b.innerHTML=lineupMarkup(c);}}
  // One-time migration: Combine used to remember who / clothes per picture in this browser only (studio-fills:<picture>). When no
  // character exists yet, kept pictures that still carry those answers can be saved as one. Offered, never automatic; "No thanks"
  // is remembered here (a failing store just means it stays quiet for this visit).
  const NOTE_KEY='studio.make.character-note';
  const noteQuiet=()=>{if(state.noteGone)return true;try{return makeStorage.getItem(NOTE_KEY)==='dismissed';}catch{return true;}};
  function rememberedAnswers(){const found={};try{for(let i=0;i<makeStorage.length;i++){const key=makeStorage.key(i);if(!key||!key.startsWith('studio-fills:'))continue;
    try{const v=JSON.parse(makeStorage.getItem(key)||'{}'),who=typeof v['@who']==='string'?v['@who'].trim():'';if(who)found[key.slice(13)]={who:who.slice(0,600),clothes:typeof v['@clothes']==='string'?v['@clothes'].trim().slice(0,600):''};}catch{}}}catch{}return found;}
  function characterNote(g){const box=q('#makeCharNote');if(!box)return;box.innerHTML='';
    if(!CHARACTER_GOALS.includes(g.intent)||(state.characters||[]).length||!state.pictures||noteQuiet())return;
    const saved=rememberedAnswers(),list=state.pictures.filter(a=>saved[a.id]&&(state.review[a.id]??a.review)==='selected').slice(0,6);if(!list.length)return;
    box.innerHTML='<section class="make-note" aria-labelledby="makeNoteTitle"><h3 id="makeNoteTitle">Save your answers as a character?</h3><p>This browser remembers the who and clothes you typed for these kept pictures. A character keeps them with your pictures, on any browser.</p>'
      +(state.charMigrate?characterForm(state.charMigrate,'create',CANON_NOTE):'<div class="make-pictures">'+list.map(a=>'<button type="button" data-make-migrate="'+escape(a.id)+'"><img src="'+thumbUrl(a)+'" alt="" loading="lazy"><small>'+escape(saved[a.id].who)+'</small></button>').join('')+'</div>')
      +'<div class="make-row"><button type="button" class="make-link" data-make-note-dismiss>No thanks</button></div></section>';}
  function openMigration(id){const saved=rememberedAnswers()[id];if(!saved)return;clearCharForms();state.charMigrate=id;state.charForm={name:'',who:saved.who,clothes:saved.clothes};characterNote(goal());q('#makeCharNote [data-make-char="name"]')?.focus();}
  function dismissNote(){state.noteGone=true;try{makeStorage.setItem(NOTE_KEY,'dismissed');}catch{}clearCharForms();characterNote(goal());q('.make-step h2')?.focus();say('Okay, you will not be asked again.');}
  function chooseCharacter(id){const c=usableCharacters().find(x=>x.id===id);if(!c||!usePrivacy(c)||choosePicture(c.canon_asset_id)===false)return false;
    state.character=c.id;state.form.who=c.body.who||'';state.form.clothes=c.body.clothes||'';
    if(goal().intent==='restyle'&&c.body.look_id){const list=lookPictures();state.styleLook=(!c.look_note&&list.find(l=>l.id===c.body.look_id)||list.find(l=>l.id===state.styleLook)||list[0])?.id||null;state.styleWords=!list.length;}
    return goal().intent==='restyle'&&c.body.look_id?c.look_note:null;}
  const chosenCharacter=()=>{const c=usableCharacters().find(x=>x.id===state.character);return c&&c.canon_asset_id===state.pick?.id?c:null;};
  // Polish plans only read (studio-workbench.js polishPlan); each picture is asked once per kind.
  // A plan that could not be read is asked again only after a 15 s cool-down, never once per redraw (#1438).
  const planning=new Set(),PLAN_RETRY=15000;
  function askPlan(id,kind,then){
    const api=window.StudioWorkbench,key=id+':'+kind,epoch=privacyEpoch;if(!api?.polishPlan||planning.has(key))return;planning.add(key);
    const source=state.pick?.id===id?state.pick:state.pictures?.find(a=>a.id===id)||state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===id))?.job;
    api.polishPlan(id,kind,requestPrivacy(classified(source))).then(plan=>{if(epoch!==privacyEpoch)return;state.polish[key]=plan;then();},error=>{if(epoch!==privacyEpoch)return;state.polish[key]={ok:false,reason:error.message};then();setTimeout(()=>{if(epoch!==privacyEpoch)return;planning.delete(key);delete state.polish[key];then();},PLAN_RETRY);});
  }
  function planPolish(list){
    for(const {job} of list)for(const o of job.outputs||[])if(o.asset_id&&picture(o))for(const kind of Object.keys(POLISH))askPlan(o.asset_id,kind,scheduleRuns);
  }
  let runsFrame=0;const scheduleRuns=()=>{if(!runsFrame)runsFrame=requestAnimationFrame(()=>{runsFrame=0;renderRuns();});};
  async function polishPicture(button){
    const id=button.dataset.asset,kind=button.dataset.makePolish,key=id+':'+kind,captured=requestPrivacy(),epoch=privacyEpoch;if(state.polishing.has(key))return;
    const source=state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===id));if(!usePrivacy({privacy:runPrivacy(source||{})}))return;state.polishing.add(key);renderRuns();
    try{const job=await window.StudioWorkbench.polish(id,kind,polishName(id,kind),{...captured,scope:runPrivacy(source||{})});job.privacy=job.privacy||captured.privacy;state.runs.unshift({job,look:polishName(id,kind)+(source?' \u00b7 '+source.look:''),lookId:source?.lookId,goal:source?.goal,scene:null});remember();poll(job.id);
      if(epoch===privacyEpoch){say(polishName(id,kind)+' started. The result appears at the top of your pictures.');window.StudioPrivacy?.submitted?.(captured);}}
    catch(error){if(epoch===privacyEpoch)say(error.message);}
    finally{state.polishing.delete(key);renderRuns();}
  }
  // A Vary whose /api/jobs answer never came back may have started: never offer it again in this page (no resubmission).
  const VARY_HELD='The last Vary for this picture got no answer, so it may have started. Check Your pictures and the library; reload the page to press Vary again.';
  async function varyPicture(button){
    const {asset:id,preset,job:jobId,makeVary:strength}=button.dataset,name=strength==='reseed'?'Vary':'Vary '+strength,captured=requestPrivacy(),epoch=privacyEpoch;if(state.varying.has(id)||state.varyHeld.has(id))return;
    const source=state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===id));if(!usePrivacy({privacy:runPrivacy(source||{})}))return;state.varying.add(id);renderRuns();
    try{const job=await window.StudioWorkbench.vary(id,preset,jobId,strength,source?.job.status,{...captured,scope:runPrivacy(source||{})});job.privacy=job.privacy||captured.privacy;state.runs.unshift({job,look:name+(source?' · '+source.look:''),lookId:source?.lookId,goal:source?.goal,scene:null});remember();poll(job.id);
      if(epoch===privacyEpoch){say(name+' started. The new pictures appear at the top of your pictures.');window.StudioPrivacy?.submitted?.(captured);}}
    catch(error){if(error.uncertain)state.varyHeld.add(id);if(epoch===privacyEpoch)say(error.uncertain?VARY_HELD:error.message);}
    finally{state.varying.delete(id);renderRuns();}
  }
  // shortcut: Comfy outputs have no auxiliary role; match filename tokens until outputs declare one (Workspace keeps source.filename).
  const picture=o=>(!o.media_type||o.media_type==='image')&&!/(?:^|[/_\\-])(mask|matte)(?:[_.-]|$)/i.test(o.source?.filename||o.filename||'');
  const pictureTitle=(scene,date)=>String(scene||'Picture').slice(0,100)+(date?' \u00b7 '+new Date(Number(date)*1000).toLocaleDateString():'');
  function renderRuns(){
    runTitle();const box=q('#makeRuns');if(!box)return;
    const visible=state.runs.filter(r=>readScope()==='all'||runPrivacy(r)===readScope()),list=runCards(visible);
    const shown=new Set(list.flatMap(c=>c.runs));if(shown.size<visible.length){for(const r of visible)if(!shown.has(r)){clearTimeout(timers.get(r.job.id));timers.delete(r.job.id);}state.runs=state.runs.filter(r=>!visible.includes(r)||shown.has(r));remember();}
    planPolish(list.flatMap(c=>c.runs));
    layout();
    if(!list.length){box.innerHTML='<p class="muted">Pictures you make here show up in this space, with one-press next steps.</p>';return;}
    const img=(job,o,i,look)=>(o.asset_id?'<button type="button" class="make-open" data-ux-open-asset="'+escape(o.asset_id)+'" aria-label="Open picture '+(i+1)+' from '+escape(look)+' full size">':'')+'<img src="'+privateMedia('/api/image/'+encodeURIComponent(job.id)+'/'+i,classified(job))+'" alt="Picture '+(i+1)+' from '+escape(look)+'" loading="lazy">'+(o.asset_id?'</button>':'')+lookNote(job,o);
    // A clip or a 3D model has no picture to show here: one press opens it in the library viewer.
    const other=o=>o.asset_id&&o.media_type&&o.media_type!=='image'?'<figure class="make-media"><button type="button" data-ux-open-asset="'+escape(o.asset_id)+'">Open the '+(o.media_type==='video'?'clip':o.media_type==='audio'?'sound':'3D model')+'</button></figure>':'';
    const pending=(job,n=job.batch_count||1)=>FINAL.includes(job.status)?'':Array.from({length:Math.max(0,n-(job.outputs||[]).length)},()=>'<figure class="make-pending" aria-hidden="true"><span></span></figure>').join('');
    const markup=list.map(({group,id,runs})=>{
      if(group){const done=runs.filter(r=>!observing(r)).length,first=runs[0];
        return '<article class="make-run make-compare" data-run="'+escape(id)+'"><header><div><b>'+(first.axis?'Compare a setting · ':'Compare looks · ')+escape(pictureTitle(first.scene,first.job.created_at))+'</b><small>'+(first.axis?escape(first.look)+' · '+runs.length+' values of '+escape(first.axis)+', one picture each':runs.length+' looks, one picture each')+(runs.every(r=>r.job.controls?.seed!=null&&r.job.controls.seed===first.job.controls?.seed)?', same seed':'')+'</small></div><span class="make-run-state '+(done===runs.length?'completed':'running')+'">'+(done===runs.length?'Done':done+' of '+runs.length+' done')+'</span></header><div class="make-compare-grid">'
          +runs.map(({job,look,value,lost})=>(look=value||look,'<figure><figcaption><b>'+escape(look)+'</b><small class="make-run-state '+escape(lost?'uncertain':job.status)+'">'+escape(lost?'Lost contact; still checking':words(job))+(lost?'':'<span data-make-clock="'+escape(job.id)+'" aria-hidden="true"></span>')+'</small></figcaption>'+(job.status==='failed'&&job.message?'<p class="make-warn">'+escape(job.message)+'</p>':'')+(lost?'':recovery(job))
            +(job.outputs||[]).map((o,i)=>picture(o)?img(job,o,i,look)+(o.asset_id?'<div class="make-actions">'+marks(o.asset_id)+characterMarkup(job,o.asset_id)+'</div>':'<small class="muted">Saving to the library…</small>'):'').join('')+pending(job,1)+'</figure>')).join('')+'</div></article>';}
      const {job,look,scene,tuned,title,lost}=runs[0];
      return '<article class="make-run" data-run="'+escape(job.id)+'"><header><div><b>'+escape(pictureTitle(scene||title||job.controls?.positive||look,job.created_at))+'</b>'+(scene?'<small>'+escape(scene)+'</small>':look&&!scene?'<small>'+escape(look)+'</small>':'')+(tuned?'<small class="make-tuned">'+escape(tuned)+'</small>':'')+'</div><span class="make-run-state '+escape(lost?'uncertain':job.status)+'">'+escape(lost?'Lost contact with this run; still checking':words(job))+(lost?'':'<span data-make-clock="'+escape(job.id)+'" aria-hidden="true"></span>')+'</span></header>'+(lost?'':'<p class="make-warn" data-make-slow hidden></p>')
      +(scene?'<div class="make-run-tools">'+(draftRun(runs[0])?'<button type="button" data-make-final="'+escape(job.id)+'">Make the final</button>':'')+'<button type="button" data-make-rerun="'+escape(job.id)+'">Edit and re-run</button><button type="button" data-make-another="'+escape(job.id)+'">Same words, another look</button></div>':runs[0].redo?'<div class="make-run-tools"><button type="button" data-make-redo="'+escape(job.id)+'">Edit and re-run</button></div>':'')
      +(job.status==='failed'&&job.message?'<p class="make-warn">'+escape(job.message)+'</p>':'')+(lost?'':recovery(job))
      +'<div class="make-outputs">'+(job.outputs||[]).map((o,i)=>!picture(o)?other(o):'<figure'+(o.asset_id&&o.asset_id===selectedOf(job)?' class="make-selected"':'')+'>'+img(job,o,i,look)+actions(job,o)+'</figure>').join('')+pending(job)+'</div></article>';});
    const focus=document.activeElement,key=e=>(e.closest('[data-run]')?.dataset.run||'')+'|'+e.tagName+'|'+JSON.stringify({...e.dataset})+'|'+e.textContent,focusKey=box.contains(focus)?key(focus):null,open=[...box.querySelectorAll('details[open]')].map(e=>e.dataset.more);
    const next=document.createElement('div');next.innerHTML=markup.join('');
    const ids=new Set(list.map(c=>c.id));for(const old of [...box.children])if(!ids.has(old.dataset.run))old.remove();
    for(const [i,card] of [...next.children].entries()){const old=[...box.children].find(e=>e.dataset.run===card.dataset.run);if(old&&old.dataset.markup===card.outerHTML)continue;card.dataset.markup=card.outerHTML;if(old)old.replaceWith(card);else box.insertBefore(card,box.children[i]||null);}
    for(const menu of box.querySelectorAll('details'))menu.open=open.includes(menu.dataset.more);
    if(focusKey&&document.activeElement!==focus)[...box.querySelectorAll('button,summary,a')].find(e=>key(e)===focusKey)?.focus();
    tick();
  }
  // Picture goals stay in Make (owner ask, 16 Oct 2026; journey audit #5-#7): pick the picture, answer a few plain fields, press
  // Make's own Generate. The request is the one the handoff prepares (studio-workbench.js polish/openHandoff): the source is
  // copied by /api/assets/reference and verified, StudioContinuation.initial writes the continuation claim, and the server checks
  // the claim, the graph hash, every file and every bracketed fill again. No route or input is added for this.
  const SC=()=>window.StudioContinuation,PE=()=>window.StudioPoseEditor,thumbUrl=a=>privateMedia('/api/assets/'+encodeURIComponent(a.id)+'/thumb',classified(a));
  const pictureLabel=a=>pictureTitle(a.prompt_excerpt||(!a.job_id&&a.title)||a.title,a.created_at);
  // Cards that share a prompt are told apart by a second line (audit v3 N5): the look or recipe, how long ago, the seed.
  const ago=t=>{const s=Math.max(0,Date.now()/1000-Number(t||0));return !t?'':s<90?'just now':s<5400?Math.round(s/60)+' min ago':s<129600?Math.round(s/3600)+' h ago':Math.round(s/86400)+' days ago';};
  // An imported picture's "recipe" is its file name, already in its title: it is not repeated (19 Oct walkthrough).
  const pictureMeta=a=>[String(a.run_label||'').startsWith('Make · ')?a.run_label.slice(7):a.preset_name&&String(a.title||'').includes(a.preset_name)?'':a.preset_name,ago(a.created_at),a.source?.seed!=null?'seed '+a.source.seed:''].filter(Boolean).join(' · ');
  // The pickers show your pictures, as the Library's Mine does (workspace.js assetIsAgentRun: Make runs are yours, #1421).
  const agentRun=a=>typeof assetIsAgentRun==='function'&&assetIsAgentRun(a);
  const PICK={edit:'Choose the picture to change.',repair:'Choose the picture to fix or enlarge.',restyle:'Choose the picture to redraw in another look.',combine:'Choose the character. The pose comes next.',animate:'Choose the still to bring to life.',mesh:'Choose a picture of one object or character, ideally on a plain background.'};
  const HEAD={edit:'What should change?',repair:'What should be fixed?',restyle:'Choose the new look',combine:'Choose the pose',animate:'How should it move?',mesh:'Make a 3D model'};
  // A recipe's bracketed fills become plain fields named by what they mean; a recipe example that names a person is never shown.
  // The pose example is the wording lab round 3 tested on Copy Pose (PR #1481): hands, prop and camera in a few words.
  const FILL={who:['Who is in the character picture','a girl with short black hair'],clothes:['What they wear, with colours','a black jacket and a red scarf'],pose:['The pose, in a few words','holding one bamboo flute with both hands at chest height, front view, medium shot'],outfit:['The clothes in the pose picture, with colours','a long blue coat and brown boots']};
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
    if(g.intent==='combine'){if(state.poseMode==='figure')return first(p=>SC().combineKind(p)==='skeleton');
      const chosen=state.poseRoute!=='copy'&&list.find(p=>p.id===POSE_ROUTE[state.poseRoute]);if(chosen)return chosen;
      const copy=list.find(p=>p.id===POSE_ROUTE.copy);return runnable(copy)?copy:list.find(p=>runnable(p)&&SC().combineKind(p)==='picture'&&!POSE_OFF.includes(p.id)&&p.id!==POSE_ROUTE.scene)||copy||null;}
    return first(()=>true);
  }
  // Character in a new pose from a picture (lab round 3, PR #1481, docs/looks/LOOK-LAB-2026-10-16.md "Pose measurements"): Copy Pose
  // kept pose, face and finish 2/2; Replace character put the face into the pose picture's scene 2/2 as designed. Depth lost identity,
  // so it is an explicit choice with a warning (owner, 16 Oct); plain 9B stays hidden. Neither is an automatic Copy Pose fallback.
  const POSE_ROUTE={copy:'combine-klein-9b-copypose',scene:'combine-klein-9b-replace',depth:'combine-klein-9b-depth'},POSE_OFF=['combine-klein-9b-depth','combine-klein-9b'];
  const notReady=p=>!p?'is not in the recipe library':p.runtime_block?'cannot run here ('+p.runtime_block.replace(/[\s.]+$/,'')+')':'needs '+missingFor(p).length+' model file'+(missingFor(p).length>1?'s':'')+' first (open Models & setup)';
  function goalBlocker(g,p){
    if(draftProblem)return draftProblem;
    const runtime=runtimeBlocker();if(runtime)return runtime;
    if(g.intent==='repair'){const plan=state.pick&&state.polish[state.pick.id+':'+state.fix];return plan&&!plan.ok?inMake(plan.reason):'';}
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
  // sel is the snapshot goalGenerate took before its first await: a pick made while the request runs never mixes into it.
  async function goalBoard(g,p,sel,captured=requestPrivacy()){
    if(!p.reference_slots?.length)return[];
    if(g.intent==='restyle'){const look=sel.style||lookPictures().find(l=>l.id===sel.styleLook);if(!look)throw Error('Choose the new look first.');
      if(look.anchor_asset_id)return[await json('/api/assets/reference',{id:look.anchor_asset_id},{...captured,scope:classified(look)})];
      const r=await privacyFetch(thumbOf(look),{},captured);if(!r.ok)throw Error('Could not read the picture of '+look.name+'.');const blob=await r.blob();
      const sent=await privacyFetch('/api/upload',{method:'POST',headers:{'Content-Type':blob.type||'image/jpeg','X-Filename':look.id+(/png/.test(blob.type)?'.png':'.jpg')},body:blob},captured),data=await sent.json().catch(()=>({}));
      if(!sent.ok)throw Error(data.error||'Could not attach the look picture ('+sent.status+').');return[data];}
    if(sel.poseMode!=='figure')return[await json('/api/assets/reference',{id:sel.pose.asset.id},{...captured,scope:classified(sel.pose.asset)})];
    const P=PE(),canvas={width:Number(p.defaults?.width)||1024,height:Number(p.defaults?.height)||1536};let points=P.fromPreset(sel.pose.figure,canvas);if(sel.pose.mirror)points=P.mirror(points,canvas);
    const body=P.renderRequest(P.serialize(points,canvas),P.guideRenderer(p));return[P.guideResponse(await json('/api/pose/render',body,captured),body)];
  }
  function goalExtras(g,p,source,clip=state.form.clip){
    if(g.intent==='animate'){const m=clips(p).find(x=>x.id===clip)||clips(p)[0];if(!m)return{};const {positive,negative,...c}=m.controls;return{...c,mode:m.id};}
    return p?.continuation_capability?.operation==='restyle'&&source&&SC().canvasFor(source,p)||{};
  }
  let goalEpoch=0;
  async function goalEstimate(g,p){
    const out=q('#makeEstimate');if(!out||!state.pick)return;const epoch=++goalEpoch,put=(t,warn=false)=>{if(epoch===goalEpoch&&out.isConnected){out.textContent=t;out.classList.toggle('make-warn',warn);}};
    if(g.intent==='repair'){const plan=state.polish[state.pick.id+':'+state.fix];put(plan?.seconds?'About '+duration(plan.seconds)+', from earlier runs on this PC.':'');return;}
    if(!p){put('');return;}
    try{const e=await json('/api/estimate',{preset_id:p.id,controls:goalExtras(g,p,state.pick.width?state.pick:null),batch_count:1,reference_count:p.reference_slots?.length?1:0});
      put(e.estimate_seconds?'About '+duration(e.estimate_seconds)+basis(e):'No timing yet: this has not run on this PC.',e.estimate_seconds>600);}
    catch{put('');}
  }
  async function renderPictures(g){
    const body=q('#makeBody'),a=state.pick,epoch=privacyEpoch;
    if(a&&!state.repicking){body.innerHTML=(g.intent==='combine'?'':'<div class="make-chosen make-picked"><img src="'+thumbUrl(a)+'" alt=""><div><small>'+(chosenCharacter()?'Your character':'Your picture')+'</small><b>'+escape(chosenCharacter()?.name||pictureLabel(a))+'</b></div><button type="button" data-make-repick>Change picture</button></div>')+'<div id="makeComposer"></div>';renderGoalComposer(g);return;}
    body.innerHTML='<div class="make-step"><span>1</span><h2 tabindex="-1">'+(g.intent==='combine'?'Pick the character picture':'Pick the picture')+'</h2>'+(a?'<button type="button" class="make-link" data-make-keep-picture>Stay with '+escape(pictureLabel(a))+'</button>':'')+'</div><div id="makeCharNote"></div>'+characterChooser(g)+'<p class="make-hint">'+escape(PICK[g.intent])+'</p>'+pictureFinder('makePictures','data-make-pick');
    await fillPictures(g,'makePictures','data-make-pick');
    if(epoch===privacyEpoch&&goal()===g){characterNote(g);void fillLineups();}
  }
  // Import here (pass 2): a picture that is not in the library yet is one file choice away, and it becomes the chosen picture; Make is never left.
  const pictureFinder=(id,attr)=>'<div class="make-finder"><input type="search" class="make-search" data-make-search="'+id+'" data-make-attr="'+attr+'" placeholder="Search your pictures" aria-label="Search your pictures" aria-controls="'+id+'" value="'+escape(state.queries[id]||'')+'"><button type="button" data-make-import="'+id+'">Import a picture…</button><input type="file" accept="image/png,image/jpeg,image/webp" hidden data-make-import-file="'+id+'" aria-label="Import a picture"><button type="button" class="make-link" data-make-all="'+id+'" aria-controls="'+id+'" aria-pressed="false" hidden></button></div><div id="'+id+'" class="make-pictures"><p class="muted">Loading your pictures…</p></div>';
  async function loadPictures(){if(!state.pictures){const epoch=privacyEpoch,data=await json('/api/workspace');if(epoch!==privacyEpoch)throw Error('Picture view changed while loading.');state.pictures=(data.assets||[]).filter(a=>inScope(a)&&a.media_type==='image'&&picture(a)&&!a.trashed_at).sort((a,b)=>(b.created_at||0)-(a.created_at||0));}return state.pictures;}   // your pictures by default, the whole library with Show all; the grid shows the newest 60 matches
  async function fillPictures(g,id,attr){
    const epoch=privacyEpoch;try{await loadPictures();
      if(epoch===privacyEpoch&&goal()===g)renderGrid(id,attr);}
    catch(error){if(epoch===privacyEpoch&&goal()===g&&q('#'+id))q('#'+id).innerHTML='<p class="make-error">'+escape(error.message)+'</p>';}
  }
  // Search reads the words people see on the card plus tags and file name; masks never reach this list.
  function renderGrid(id,attr){
    const box=q('#'+id);if(!box||!state.pictures)return;const terms=String(state.queries[id]||'').toLowerCase().split(/\s+/).filter(Boolean);
    const match=a=>{const text=[pictureLabel(a),pictureMeta(a),a.title,a.prompt_excerpt,a.filename,...(a.tags||[])].join(' ').toLowerCase();return terms.every(t=>text.includes(t));};
    // The pose grid never offers the character picture as its own pose.
    const others=id==='makePosePictures'?state.pictures.filter(a=>a.id!==state.pick?.id):state.pictures;
    const agents=others.filter(agentRun).length,pool=state.allPictures||!agents?others:others.filter(a=>!agentRun(a)),list=pool.filter(match);
    const shown=list.slice(0,60),more=list.length-shown.length,hidden=!state.allPictures&&agents&&terms.length?others.filter(a=>agentRun(a)&&match(a)).length:0;
    const card=a=>{const label=pictureLabel(a),meta=pictureMeta(a);return '<button type="button" '+attr+'="'+escape(a.id)+'" title="'+escape(String(a.prompt_excerpt||a.title||label)+(meta?' · '+meta:''))+'"><img src="'+thumbUrl(a)+'" alt="'+escape(label)+'" loading="lazy"><small aria-hidden="true">'+escape(label)+'</small>'+(meta?'<small class="make-pic-meta">'+escape(meta)+'</small>':'')+'</button>';};
    box.innerHTML=list.length?shown.map(card).join('')+(more?'<p class="muted">'+more+' older picture'+(more===1?'':'s')+' match too. Search to narrow the list.</p>':''):pool.length?'<p class="muted">No picture matches “'+escape(state.queries[id])+'”'+(hidden?'; '+hidden+' from agent runs do'+(hidden===1?'es':'')+'.':'.')+'</p>':others.length?'<p class="muted">None of your own pictures yet: everything here is from agent runs.</p>':state.pictures.length?'<p class="muted">The character is your only picture. Import a pose picture, or choose Draw the pose.</p>':'<p class="muted">No pictures yet. Import one, or make one first.</p>';
    const all=q('[data-make-all="'+id+'"]');if(all){all.hidden=!agents;all.setAttribute('aria-pressed',String(!!state.allPictures));all.textContent=state.allPictures?'Show only my pictures':'Show all pictures ('+agents+' more from agent runs)';}
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
    else if(g.intent==='repair'){planFixes(a.id);preselectFix(a.id);main='<fieldset class="make-options"><legend>Choose one</legend>'+polishKinds(a.id).map(kind=>{const label=polishName(a.id,kind);const plan=state.polish[a.id+':'+kind],off=!!plan&&!plan.ok;
      return '<label class="make-check"><input type="radio" name="makeFix" id="makeFix-'+kind+'" data-make-fix="'+kind+'"'+(state.fix===kind?' checked':'')+(off?' disabled aria-describedby="makeFixWhy-'+kind+'"':'')+'> '+label+(plan?.seconds?' <small>~'+duration(plan.seconds)+'</small>':'')+'</label>'+(off?'<small class="make-warn make-option-why" id="makeFixWhy-'+kind+'">'+escape(inMake(plan.reason))+'</small>':'')+(kind==='face'&&merged(a.id)?'<small class="muted make-option-why">'+FIX_HINT+'</small>':'')+(kind==='refine'&&plan?.ok?'<small class="muted make-option-why">'+REFINE_HINT+'</small>':'')+(kind==='upscale'&&plan?.ok?'<small class="muted make-option-why">'+UP_HINT+'</small>':'');}).join('')+'</fieldset>';}
    else if(g.intent==='restyle'){
      if(p?.reference_slots?.length)main='<fieldset class="make-style-looks" id="makeStyleLooks" tabindex="-1"><legend>Redraw it the way this look is drawn</legend>'+lookPictures().map(l=>'<label class="make-style"><input type="radio" name="makeStyle" id="makeStyle-'+escape(l.id)+'" data-make-style="'+escape(l.id)+'"'+(state.styleLook===l.id?' checked':'')+'><img src="'+escape(thumbOf(l))+'" alt="" loading="lazy"><span>'+escape(l.name)+'</span></label>').join('')+'</fieldset>'
        +'<button type="button" class="make-link" data-make-style-words>Describe the look in words instead</button>'+fields.map(fill).join('')+'<small class="muted">Only how the look picture is drawn is copied, not what it shows. Your picture keeps its character, pose, clothes and layout.</small>';
      else{if(f.look==null&&p)f.look=splitLook(SC().promptFor(p,null)||'')[0];main=field('look','Describe the new look','a soft watercolour illustration with loose ink lines',4,2000)+(lookPictures().length?'<button type="button" class="make-link" data-make-style-pictures>Pick a look by its picture instead</button>':'')+'<small class="muted">Your words carry the look. Your picture keeps its character, pose, clothes and layout.</small>';}}
    else if(g.intent==='combine'){
      const figure=state.poseMode==='figure',pose=state.pose,figures=(PE()?.PRESETS||[]).filter(x=>x.points),mode=(value,label)=>'<label class="make-check"><input type="radio" name="makePoseMode" id="makePoseMode-'+value+'" data-make-pose-mode="'+value+'"'+(state.poseMode===value?' checked':'')+'> '+label+'</label>';
      // Copy Pose by default; Replace character and depth are explicit choices. A fallback says why.
      const all=ready()?SC().destinations('combine',presets(),null):[],copy=all.find(x=>x.id===POSE_ROUTE.copy),route=Object.keys(POSE_ROUTE).find(k=>p?.id===POSE_ROUTE[k])||'copy',scene=route==='scene',depth=route==='depth';
      const opt=(v,label,says)=>'<label class="make-check"><input type="radio" name="makePoseRoute" id="makePoseRoute-'+v+'" data-make-pose-route="'+v+'"'+(route===v?' checked':'')+' aria-describedby="makePoseRouteHint-'+v+'"> '+label+'</label><small class="muted" id="makePoseRouteHint-'+v+'">'+says+'</small>';
      const routes=(all.some(x=>x.id===POSE_ROUTE.scene||x.id===POSE_ROUTE.depth)?'<fieldset class="make-options make-pose-routes"><legend>What to keep</legend>'+opt('copy','Keep my character as it is','Your character keeps its face, clothes, background and finish; only the body position comes from the pose picture.')+(all.some(x=>x.id===POSE_ROUTE.scene)?opt('scene','Put my character into this picture’s scene','The pose picture keeps its outfit, setting and finish; only your character’s face and hair go in.'):'')+(all.some(x=>x.id===POSE_ROUTE.depth)?opt('depth','Follow the pose picture’s outline (depth)','Follows the outline closely; in lab round 3 it simplified the face and curls, and one result had a blank grey face.'):'')+'</fieldset>':'')
        +(route==='copy'&&p&&p.id!==POSE_ROUTE.copy?'<small class="make-warn" id="makePoseFallback">'+goalWhy(copy||p,'Copy Pose '+notReady(copy)+', so this uses '+SC().combineEngineLabel(p)+' instead; it may keep the face less well.')+'</small>':'');
      main='<div class="make-slots"><section class="make-slot" aria-labelledby="makeSlotA"><h3 id="makeSlotA">Character picture</h3><img src="'+thumbUrl(a)+'" alt=""><small>'+escape(chosenCharacter()?'Your character '+chosenCharacter().name+' \u00b7 canon picture':pictureLabel(a))+'</small><button type="button" data-make-repick>Change picture</button></section>'
        +'<section class="make-slot" id="makePoseSlot" tabindex="-1" aria-labelledby="makeSlotB"><h3 id="makeSlotB">Pose</h3><div class="make-seg" role="group" aria-label="Where the pose comes from">'+mode('picture','A picture of the pose')+mode('figure','Draw the pose')+'</div>'
        +(figure?'<div class="make-figures">'+figures.map(x=>'<label class="make-figure"><input type="radio" name="makeFigure" id="makeFigure-'+x.id+'" data-make-figure="'+x.id+'"'+(pose?.figure===x.id?' checked':'')+'>'+figureSvg(x.points,pose?.figure===x.id&&pose.mirror)+'<span>'+escape(x.label)+'</span></label>').join('')+'</div><label class="make-check"><input type="checkbox" id="makeMirror" data-make-mirror'+(pose?.mirror?' checked':'')+(pose?.figure?'':' disabled')+'> Mirror left and right</label><small class="muted">A stick figure carries the pose and nothing else. To move single joints, open the full editor.</small><small class="muted" id="makeFigureHint">Hands and gaze follow the words only weakly. Describe the pose simply, and leave out words the figure contradicts, such as crossed legs on the bent figure.</small>'
          :routes+(pose?.asset&&!state.posePicking?'<img src="'+thumbUrl(pose.asset)+'" alt=""><small>'+escape(pictureLabel(pose.asset))+'</small><button type="button" data-make-pose-change>Change pose picture</button><small class="muted">'+(scene?'Its pose, camera, clothes and background stay; only the person changes.':depth?'Its outline guides the pose; clothing shapes can carry over and your character may change.':'Only the body position is taken from it, not the person, clothes or colours.')+'</small>'
          :pictureFinder('makePosePictures','data-make-pose-pick')))+'</section></div>'+fields.map(fill).join('');}
    else if(g.intent==='animate'){main=field('motion','Motion and camera','she turns her head and smiles; the camera slowly moves closer',3)+'<small class="muted">Say what moves and how the camera moves. A description of the picture alone gives a still clip.</small>';
      const list=clips(p);if(list.length)side='<label>Length<select id="makeClip" data-make-field="clip">'+list.map(m=>'<option value="'+escape(m.id)+'"'+((f.clip||list[0].id)===m.id?' selected':'')+'>'+escape(CLIP[m.id]||m.name)+' · '+m.controls.frames+' frames, about '+(m.controls.frames/CLIP_FPS).toFixed(1)+' s</option>').join('')+'</select></label>';}
    else main='<p>One press: the background is cut away, then a textured 3D model (GLB) is built from this picture. Hidden sides are guessed, so check the model before you use it.</p>';
    box.innerHTML='<div class="make-step"><span>2</span><h2 tabindex="-1">'+escape(HEAD[g.intent])+'</h2></div><div class="make-composer"><div class="make-compose-main">'+main+'</div><div class="make-compose-side">'+side
      +'<button type="button" class="make-link" data-ux-handoff="'+escape(a.id)+'" data-ux-handoff-intent="'+g.intent+'">Open in the full editor instead</button>'
      +(p?'<details class="make-about"><summary>What this uses</summary><p>'+escape(p.name)+'</p></details>':'')+'</div>'+goBar(why?goalWhy(p,why):'')+'</div>';
    if(q('#makePosePictures'))void fillPictures(g,'makePosePictures','data-make-pose-pick');
    if(focus)q('#'+CSS.escape(focus))?.focus();
    syncOperation();settleMissing();goalEstimate(g,p);
  }
  // A fix that cannot run here is never the preselected one (audit N9); refusals name Make's own goals, not the full editor's dialog.
  function preselectFix(id){const plan=k=>state.polish[id+':'+k];if(state.fix==='details'&&merged(id))state.fix='face';if(plan(state.fix)&&!plan(state.fix).ok){const first=Object.keys(POLISH).find(k=>plan(k)?.ok)||Object.keys(POLISH).find(k=>!plan(k));if(first)state.fix=first;}}
  const inMake=text=>String(text||'').replace(/ Use Continue with this( and describe it)?\.?$/,' Choose another fix, or use “Change a picture”.');
  function planFixes(id){
    for(const kind of Object.keys(POLISH))askPlan(id,kind,()=>{if(state.pick?.id===id&&goal().intent==='repair'&&!state.repicking)renderGoalComposer(goal());});
  }
  // The answers a picture's Combine fields were given last time (the same store Create's fields use).
  const fillsKey=id=>'studio-fills:'+id;
  function choosePicture(id){
    const a=state.pictures?.find(x=>x.id===id)||(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===id))||{id,title:''};
    if(!usePrivacy(a))return false;
    if(state.pick?.id!==id){state.form={};try{const saved=JSON.parse(makeStorage.getItem(fillsKey(id))||'{}');for(const k of ['who','clothes'])if(typeof saved['@'+k]==='string')state.form[k]=saved['@'+k];}catch{}}
    // A new character that is the chosen pose picture leaves the pose empty, so one picture is never both.
    if(state.pose?.asset?.id===id)state.pose=null;
    state.pick=a;state.repicking=false;draftProblem='';
  }
  function rememberFills(id,form,privacy=creationPrivacy()){try{const storage=storedIn(privacy),key=privateKey(fillsKey(id),privacy),saved=JSON.parse(storage.getItem(key)||'{}');for(const k of ['who','clothes','pose'])if(String(form[k]||'').trim())saved['@'+k]=form[k].trim();storage.setItem(key,JSON.stringify(saved));}catch{}}
  // aria-invalid belongs on inputs, not on a fieldset or section: a group of choices marks each choice (WCAG 4.1.2).
  function markMissing(el){const radios=el.matches('input,textarea,select')?[el]:[...el.querySelectorAll('input[type=radio]')],list=radios.length?radios:[...el.querySelectorAll('input')].slice(0,1);
    for(const f of list){f.setAttribute('aria-invalid','true');f.setAttribute('aria-describedby','makeStatus');}(list[0]||el).focus();}
  // A picture goal's run keeps what it was made from (wave 6 ask): the picture, the answers, the pose and its route (Copy Pose or
  // Replace), the look picture or the fix. Edit and re-run puts them back on screen; it never submits. Read back from this browser's
  // storage, so every field is checked before use.
  const redoOf=(a,form,sel)=>({pick:a.id,form:Object.fromEntries(Object.entries(form).filter(([,v])=>typeof v==='string')),styleLook:sel.styleLook,styleWords:!!sel.styleWords,poseMode:sel.poseMode,poseRoute:sel.poseRoute,
    pose:sel.pose?.asset?{asset:sel.pose.asset.id}:sel.pose?.figure?{figure:sel.pose.figure,mirror:!!sel.pose.mirror}:null,fix:sel.fix});
  function redoRun(run){const r=run.redo,g=GOALS.find(x=>x.id===run.goal);if(!g?.intent||!r||typeof r.pick!=='string'||!usePrivacy({privacy:runPrivacy(run)}))return false;
    state.goal=g.id;state.compare=false;state.character=null;if(choosePicture(r.pick)===false)return false;
    state.form=Object.fromEntries(Object.entries(r.form&&typeof r.form==='object'?r.form:{}).filter(([,v])=>typeof v==='string'&&v.length<=2000));
    if(['picture','figure'].includes(r.poseMode))state.poseMode=r.poseMode;if(['copy','scene','depth'].includes(r.poseRoute))state.poseRoute=r.poseRoute;
    const find=id=>state.pictures?.find(x=>x.id===id)||(typeof assetState!=='undefined'&&assetState?.assets?.find(x=>x.id===id))||{id,title:''};
    state.pose=typeof r.pose?.asset==='string'?{asset:find(r.pose.asset)}:PE()?.PRESETS?.some(x=>x.id===r.pose?.figure)?{figure:r.pose.figure,mirror:!!r.pose.mirror}:null;state.posePicking=false;
    if(typeof r.styleLook==='string')state.styleLook=r.styleLook;state.styleWords=!!r.styleWords;if(POLISH[r.fix])state.fix=r.fix;
    remember();render();return true;}
  async function goalGenerate(){
    const g=goal(),a=state.pick,captured=requestPrivacy(),epoch=privacyEpoch;if(!g.intent||!a||state.busy)return;
    const p=goalRoute(g),why=goalBlocker(g,p);if(why){say(why);return;}
    // Every answer is read before the first await: typing on while the copy runs does not change this request.
    const form={...state.form},avoid=String(chosenCharacter()?.body.avoid||'').trim(),missing=goalMissing(g,p,form),sel={styleLook:state.styleLook,style:state.looks?.find(l=>l.id===state.styleLook),styleWords:state.styleWords,poseMode:state.poseMode,poseRoute:state.poseRoute,pose:state.pose&&{...state.pose},fix:state.fix};
    if(missing){const el=q('#'+missing[0]);if(el)markMissing(el);sayMissing(missing[1]);return;}
    state.busy=true;say('Preparing…');
    try{
      let job;
      if(g.intent==='repair')job=await window.StudioWorkbench.polish(a.id,sel.fix,polishName(a.id,sel.fix),{...captured,scope:classified(a)});
      else{
        const sourcePrivacy={...captured,scope:classified(a)},source=await json('/api/assets/'+encodeURIComponent(a.id)+'/context',undefined,sourcePrivacy);if(source?.version!==1||source.asset_id!==a.id)throw Error('This picture’s record could not be verified. Refresh and try again.');
        const board=await goalBoard(g,p,sel,captured),result=await json('/api/assets/reference',{id:a.id},sourcePrivacy);
        if(result?.parent_asset!==a.id||result.sha256!==source.sha256||result.context?.asset_id!==a.id||JSON.stringify(result.context)!==JSON.stringify(source))throw Error('The picture changed while it was being copied. Nothing was sent.');
        const prepared=SC().initial(result.context,p,g.intent,result.file),controls={[SC().sourceInput(p.continuation_capability)]:result.file,...goalExtras(g,p,result.context,form.clip)};
        if(p.positive)controls.positive=goalWords(g,p,prepared.positive,form);
        if(p.negative&&prepared.negative)controls.negative=avoid?prepared.negative+', '+avoid:prepared.negative;   // a chosen character's avoid words ride only where the request already has a negative
        if(p.seed||p.bindings_extra?.seed)controls.seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;
        if(p.positive&&(!controls.positive.trim()||SC().unfilled(p,controls.positive).length))throw Error('Fill in every field, then press Generate again. Nothing was sent.');
        if(g.intent==='combine')rememberFills(a.id,form,captured.privacy);
        if(epoch===privacyEpoch)say('Sending to ComfyUI…');
        job=await json('/api/jobs',{preset_id:p.id,continuation:prepared.claim,controls,batch_count:1,parent_assets:[...new Set([a.id,...board.map(r=>r.parent_asset).filter(Boolean)])],references:p.reference_slots?.length?SC().combineReferences(p,board):[],label:'Make · '+g.name},captured);
      }
      job.privacy=job.privacy||captured.privacy;
      state.runs.unshift({job,look:g.intent==='repair'?polishName(a.id,sel.fix):g.name,lookId:null,goal:g.id,scene:null,title:String(form[{edit:'change',animate:'motion',combine:'who'}[g.intent]]||'').trim()||pictureLabel(a),...(g.intent==='combine'?{fills:{who:String(form.who||'').trim(),clothes:String(form.clothes||'').trim()}}:{}),redo:redoOf(a,form,sel)});remember();
      if(epoch===privacyEpoch)say('Started. The result appears in Your pictures as it finishes; you can leave this page.');renderRuns();poll(job.id);if(epoch===privacyEpoch)window.StudioPrivacy?.submitted?.(captured);
      if(typeof refresh==='function')void refresh();
    }catch(error){if(epoch===privacyEpoch)say(error.message);}
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
      +goBar(why?escape(why):'','Generate'+(list.length>1?' '+list.length+' pictures':''))+'</div>';
    const scene=q('#makeScene');try{scene.value=sceneDraftValue();}catch{}
    scene.oninput=()=>{scene.removeAttribute('aria-invalid');scene.removeAttribute('aria-describedby');writeScene(scene.value);settleMissing();};
    if(q('#makeUseExample'))q('#makeUseExample').onclick=()=>{scene.value=example;scene.oninput();scene.focus();};
    syncOperation();void compareEstimate();
  }
  let compareEpoch=0;
  async function compareEstimate(){
    const out=q('#makeEstimate'),list=compareList();if(!out)return;const epoch=++compareEpoch;let guessed=false,usedLab=false,usedRuns=false;if(list.length<2){out.textContent='';return;}
    const each=await Promise.all(list.map(l=>{const p=presetFor(l),[w,h]=shapeSize(p,l,'design');return json('/api/estimate',{preset_id:p?.id||l.body.preset_id,controls:{...l.body.controls,width:w,height:h},batch_count:1,reference_count:0}).then(e=>{const lab=rough(e)&&lookTiming(l);if(rough(e)&&!lab)guessed=true;if(lab)usedLab=true;else if(!rough(e)&&e.estimate_seconds)usedRuns=true;return lab?lab.seconds:Number(e.estimate_seconds)||0;},()=>0);}));
    if(epoch!==compareEpoch||!out.isConnected)return;const total=each.reduce((x,y)=>x+y,0),unknown=each.filter(x=>!x).length;
    out.classList.toggle('make-warn',total>600);out.textContent=list.length+' pictures, one per look'+(total?' · about '+duration(total)+' in total'+(unknown?' (no timing yet for '+unknown+')':'')+(guessed?basis({confidence:'none'}):!usedLab?basis({}):usedRuns?', from earlier runs and the look lab on this PC.':', from the 16 Oct look lab on this PC.'):' · no timing yet for these looks on this PC.');
  }
  // A compare sends its jobs one by one; leaving Make (even briefly) stops the ones not yet sent (#1514).
  function leaveWatch(){let left=false;const o=new MutationObserver(records=>{if(view.hidden||records.some(r=>r.oldValue!==null))left=true;});
    o.observe(view,{attributes:true,attributeFilter:['hidden'],attributeOldValue:true});return{stopped:()=>left||view.hidden||!view.isConnected,stop:()=>o.disconnect()};}
  async function generateSweep(look){
    const captured=requestPrivacy(),epoch=privacyEpoch,report=text=>{if(epoch===privacyEpoch)say(text);};
    const runGoal=state.goal,group='compare-'+Date.now().toString(36),watch=leaveWatch(),swaps=new Set();let started=0,n=0,sending=false;state.busy=true;report('Preparing\u2026');
    try{
      const request=await prepared(look,true,captured),runs=request.variants;n=runs.length;
      for(const v of runs){
        if(watch.stopped())break;
        report('Sending '+(started+1)+' of '+n+' to ComfyUI\u2026');
        sending=true;const job=await json('/api/jobs',{preset_id:v.preset_id,controls:v.controls,look:v.look,batch_count:1,label:'Make · Compare · '+look.name},captured);job.privacy=job.privacy||captured.privacy;sending=false;for(const n of v.notes||[])swaps.add(n);
        state.runs.splice(started++,0,{job,look:look.name,lookId:look.id,goal:runGoal,scene:request.scene,tune:v.tune,tuned:v.tuned,group,axis:request.axis,value:v.label});remember();renderRuns();poll(job.id);
      }
      report((started<n?'Started '+started+' of '+n+'; the rest were not sent because you left Make.':'Started '+n+' pictures, one per value of '+request.axis+'. They appear side by side in Your pictures.')+[request.notice,...swaps].filter(Boolean).map(x=>' '+x).join(''));
      if(started&&epoch===privacyEpoch)showRun(group);if(typeof refresh==='function')void refresh();
    }catch(error){if(error.message===SCENE_FIRST)epoch===privacyEpoch&&sayMissing(error.message);else report((sending&&error.status===undefined?'Started '+started+' of '+n+'; the last one may have started and is not shown here; check the library and Problems before trying again. ':started?'Started '+started+' of '+n+'; the rest were not sent. ':'')+error.message+[...swaps].map(n=>' '+n).join(''));}
    finally{watch.stop();state.busy=false;syncOperation();if(started&&epoch===privacyEpoch)window.StudioPrivacy?.submitted?.(captured);}
  }
  async function generateCompare(){
    const captured=requestPrivacy(),epoch=privacyEpoch,report=text=>{if(epoch===privacyEpoch)say(text);};
    if(state.busy)return;const list=compareList(),why=compareBlocker();if(why){report(why);return;}
    const field=q('#makeScene'),scene=field.value.trim();if(!scene){field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby','makeStatus');field.focus();sayMissing(SCENE_FIRST);return;}
    state.busy=true;report('Preparing…');
    const seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647,group='compare-'+Date.now().toString(36),runGoal=state.goal,watch=leaveWatch(),stopped=watch.stopped;let started=0,sending=false;const notes=[];
    try{
      for(const look of list){
        if(stopped())break;
        const result=await json('/api/looks/prepare',{id:look.id,scene,...(look.body.options?.length?{options:Object.fromEntries(look.body.options.map(o=>[o.id,!!o.default]))}:{}),expected_revision:look.revision},captured);
        const swaps=result.notices||[];const p=presetFor(look),controls={...result.controls},[w,h]=shapeSize(p,look,'design');
        if('width' in controls||p?.width)Object.assign(controls,{width:w,height:h});
        if(bound(p,'seed'))controls.seed=seed;
        if(stopped())break;
        report('Sending '+(started+1)+' of '+list.length+' to ComfyUI…');
        sending=true;const job=await json('/api/jobs',{preset_id:p?.id||look.body.preset_id,controls,look:result.look,batch_count:1,label:'Make · Compare · '+look.name},captured);job.privacy=job.privacy||captured.privacy;sending=false;
        state.runs.splice(started++,0,{job,look:look.name,lookId:look.id,goal:runGoal,scene,group});notes.push(...swaps);remember();renderRuns();poll(job.id);
      }
      const noted=notes.map(n=>' '+n).join('');
      report((started<list.length?'Started '+started+' of '+list.length+'; the rest were not sent because you left Make.':'Started '+list.length+' pictures, one per look. They appear side by side in Your pictures.')+noted);
      if(typeof refresh==='function')void refresh();
    }catch(error){report((sending&&error.status===undefined?'Started '+started+' of '+list.length+'; the last one may have started and is not shown here; check the library and Problems before trying again. ':started?'Started '+started+' of '+list.length+'; the rest were not sent. ':'')+error.message+notes.map(n=>' '+n).join(''));}
    finally{watch.stop();state.busy=false;syncOperation();if(started&&epoch===privacyEpoch)window.StudioPrivacy?.submitted?.(captured);}
  }
  // Your pictures lives in this browser; a new browser starts it from the library's Make pictures (audit v3 N6): the newest six
  // Make runs by their "Make · " label, read back from their job records. Their words are not stored, so Edit and re-run is not offered.
  async function seedRuns(){
    try{const seen=new Set(),firsts=[];for(const a of await loadPictures()){if(!String(a.run_label||'').startsWith('Make · ')||typeof a.job_id!=='string'||seen.has(a.job_id))continue;seen.add(a.job_id);firsts.push(a);if(firsts.length===6)break;}
      const runs=await Promise.all(firsts.map(async a=>{try{const job=await json('/api/jobs/'+encodeURIComponent(a.job_id)),name=a.run_label.replace(/^Make · (Compare · )?/,''),look=state.looks?.find(l=>l.name===name);
        return{job,look:name,lookId:look?.id||null,goal:GOALS.find(g=>g.looks?.includes(look?.id))?.id||null,scene:null,title:a.prompt_excerpt||null};}catch{return null;}}));
      return runs.filter(Boolean);}catch{return[];}
  }
  async function load(){
    const epoch=privacyEpoch,revision=draftRevision,pendingDraft=readDraft();state.error='';
    // Speed, readiness and history read the recipe catalog that app.js loads; wait for it briefly instead of guessing.
    for(let i=0;i<40&&!presets().length;i++)await new Promise(r=>setTimeout(r,250));
    try{
      const [listing]=await Promise.all([json('/api/looks'),refreshRecord(),loadCharacters(),import('/static/bundle-showcase.js').then(m=>{state.examples=m.default.examples||{};}).catch(()=>{})]);
      if(epoch!==privacyEpoch)return;state.looks=(listing.looks||listing.cards||[]).filter(l=>l.kind==='look'||l.body);
    }catch(error){if(epoch!==privacyEpoch)return;state.error='Could not read the looks: '+error.message;}
    if(epoch!==privacyEpoch)return;await restoreDraft(pendingDraft,epoch,revision);if(epoch!==privacyEpoch)return;draftReady=true;view.dataset.draftState='ready';
    const navigation=pendingNavigation||takeNavigation();pendingNavigation=null;if(navigation)chooseNavigation(navigation);
    render();
    // Earlier Make runs come back from their job records; one the Studio says is gone (404) is dropped, one still running is followed
    // again, and one whose read fails is kept and checked again with back-off (#1438), never taken for deleted.
    const restored=await Promise.all(savedRuns.map(async r=>{try{const job=await json('/api/jobs/'+encodeURIComponent(r.id),undefined,requestPrivacy(classified(r)));return inScope(job)?{...r,privacy:classified(job),job,lost:false}:null;}catch(error){return error.status===404?null:{...r,job:{id:r.id,status:'',outputs:[],privacy:classified(r)},lost:true};}}));
    if(epoch!==privacyEpoch)return;
    state.runs=[...state.runs,...restored.filter(r=>r&&!state.runs.some(x=>x.job.id===r.id)).map(({id,...r})=>r)];
    if(!state.runs.length&&!savedRuns.length){const seeded=await seedRuns();if(epoch!==privacyEpoch)return;if(!state.runs.length)state.runs=seeded;}
    restoredRuns=true;remember();
    for(const r of state.runs)if(observing(r))poll(r.job.id,r.lost?1:0);
    renderRuns();
  }
  // The gallery folds away under the pointer: bring "Describe your picture" out from under the fixed bar (audit N8, make.css scroll-margin).
  function focusScene(){q('#makeComposer .make-step')?.scrollIntoView({block:'nearest'});q('#makeScene')?.focus({preventScroll:true});}
  view.addEventListener('input',e=>{const t=e.target;if(t.id==='makeLoraSearch'){const box=q('#makeLoraChoices'),look=current();if(box&&look)box.innerHTML=loraCards(look,t.value);return;}if(t.closest('#makeTune')){tuneInput(t);return;}if(t.closest('#makeSweep')){sweepInput(t);return;}
    if(t.dataset.makeField){state.form[t.dataset.makeField]=t.value;t.removeAttribute('aria-invalid');t.removeAttribute('aria-describedby');settleMissing();if(t.tagName==='SELECT')void goalEstimate(goal(),goalRoute(goal()));return;}
    if(t.dataset.makeChar){state.charForm[t.dataset.makeChar]=t.value;t.removeAttribute('aria-invalid');t.removeAttribute('aria-describedby');settleMissing();return;}
    if(t.dataset.makeSearch){state.queries[t.dataset.makeSearch]=t.value;renderGrid(t.dataset.makeSearch,t.dataset.makeAttr);}});
  // Choices that change the composer redraw it and keep the keyboard on the control just used.
  view.addEventListener('change',e=>{if(e.target.matches('[data-make-import-file]'))void importPicture(e.target);});
  // The library's own import (POST /api/assets/import); the new picture is chosen for the slot whose button was pressed.
  async function importPicture(input){
    const file=input.files?.[0],id=input.dataset.makeImportFile,g=goal(),box=q('#'+id),button=q('[data-make-import="'+id+'"]'),captured=requestPrivacy(),epoch=privacyEpoch;if(!file)return;
    const fail=text=>{if(box)box.insertAdjacentHTML('afterbegin','<p class="make-error" role="alert">'+escape(text)+' Nothing was imported.</p>');};
    if(!['image/png','image/jpeg','image/webp'].includes(file.type))return fail('Choose a PNG, JPEG or WebP picture.');
    if(file.size>20*1024*1024)return fail(file.name+' is over 20 MiB.');
    if(button){button.disabled=true;button.textContent='Importing…';}
    try{const r=await privacyFetch('/api/assets/import',{method:'POST',headers:{'Content-Type':file.type,'X-Filename':file.name},body:file},captured),data=await r.json().catch(()=>({}));
      if(!r.ok||!data.asset?.id)throw Error(data.error||'The import was refused ('+r.status+').');
      if(epoch!==privacyEpoch)return;
      // From here the asset exists (Codex P2 on #1576): it is chosen whatever happens next, and the list refresh is best effort.
      let a=data.asset,listed=true;state.pictures=null;try{await loadPictures();a=state.pictures.find(x=>x.id===a.id)||(state.pictures.unshift(a),a);}catch{if(epoch!==privacyEpoch)return;listed=false;state.pictures=[a];}if(epoch!==privacyEpoch)return;
      if(goal()===g){if(id==='makePosePictures'){state.pose={asset:a};state.posePicking=false;renderGoalComposer(g);q('[data-make-pose-change]')?.focus();}
        else{state.character=null;choosePicture(a.id);await renderPictures(g);if(epoch!==privacyEpoch)return;q('#makeComposer textarea,#makeComposer input:not([type=search])')?.focus();}}
      if(!listed)state.pictures=null;   // the next picker reads the library again
      say('Imported '+file.name+'. It is chosen'+(listed?'.':'; the picture list could not refresh, so it will reload next time.'));rememberDraft();return;}
    catch(error){if(epoch!==privacyEpoch)return;if(button){button.disabled=false;button.textContent='Import a picture…';}fail(error.message);}
    finally{input.value='';}
  }
  view.addEventListener('change',e=>{const t=e.target,g=goal(),redraw=sel=>{renderGoalComposer(g);q(sel)?.focus();};
    if(t.name==='makeQuality'){const look=current(),id=t.id;if(look){const tune=tuneOf(look);tune.turbo=t.value==='turbo';tune.steps=t.value&&t.value!=='turbo'?Number(t.value):null;tuneChanged();q('#'+id)?.focus();}return;}
    if(t.dataset.makeFix){state.fix=t.dataset.makeFix;redraw('#makeFix-'+state.fix);return;}
    if(t.dataset.makeStyle){state.styleLook=t.dataset.makeStyle;for(const r of view.querySelectorAll('[data-make-style]')){r.removeAttribute('aria-invalid');r.removeAttribute('aria-describedby');}settleMissing();return;}
    if(t.dataset.makePoseRoute){state.poseRoute=t.dataset.makePoseRoute;redraw('#makePoseRoute-'+state.poseRoute);return;}
    if(t.dataset.makePoseMode){state.poseMode=t.dataset.makePoseMode;state.posePicking=false;redraw('#makePoseMode-'+state.poseMode);return;}
    // A new figure is a new pose: its words replace the pose answer (Create clears it the same way, #492); edit them freely.
    if(t.dataset.makeFigure){const fig=PE().PRESETS.find(x=>x.id===t.dataset.makeFigure);state.pose={figure:fig.id,mirror:!!state.pose?.mirror};state.form.pose=fig.label.toLowerCase();redraw('#makeFigure-'+fig.id);return;}
    if('makeMirror' in t.dataset&&state.pose?.figure){state.pose.mirror=t.checked;redraw('#makeMirror');}});
  view.addEventListener('click',e=>{
    if(e.target.closest('#makeTune')&&tuneClick(e.target))return;
    const g=e.target.closest('[data-make-goal]');if(g){state.goal=g.dataset.makeGoal;state.pictures=null;remember();render();q('[data-make-goal="'+state.goal+'"]')?.focus();return;}
    const l=e.target.closest('[data-make-look]');if(l&&state.compare){const id=l.dataset.makeLook,i=state.compareLooks.indexOf(id);
      if(i>=0)state.compareLooks.splice(i,1);else if(state.compareLooks.length>=3){say('Three looks at most: unselect one first.');return;}else state.compareLooks.push(id);
      renderLooks();
      // The scene box sits below the cards (audit v3 N4): from the second look on, bring it into view and put the keyboard there.
      if(i<0&&state.compareLooks.length>=2){const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;q('#makeComposer .make-step')?.scrollIntoView({block:'start',behavior:reduce?'auto':'smooth'});q('#makeScene')?.focus({preventScroll:true});
        say(state.compareLooks.length<3?'Two looks chosen. Type the scene, or scroll up to add a third look.':'Three looks chosen. Type the scene, then press Generate.');return;}
      q('[data-make-look="'+id+'"]')?.focus();return;}
    if(l){state.look=l.dataset.makeLook;state.picking=false;remember();renderLooks();focusScene();return;}
    if(e.target.closest('[data-make-compare]')){state.compare=!state.compare;state.compareLooks=state.compare&&lookList().some(x=>x.id===state.look)?[state.look]:[];
      say(state.compare?'Compare looks: choose two or three looks, type one scene, then press Generate once.':'');renderLooks();q('[data-make-compare]')?.focus();return;}
    const character=e.target.closest('[data-make-character]');if(character){const note=chooseCharacter(character.dataset.makeCharacter);if(note===false)return;renderPictures(goal());
      say('Your character is chosen: its canon picture as it is'+(goal().intent==='combine'?', with its words.':'.')+(note?' '+note:''));q('#makeComposer textarea,#makeComposer input:not([type=search])')?.focus();return;}
    const saveChar=e.target.closest('[data-make-character-save]');if(saveChar){openCharacterForm(saveChar.dataset.makeCharacterSave,saveChar.closest('[data-run]')?.dataset.run);return;}
    if(e.target.closest('[data-make-character-cancel]')){const a=state.charSave,edit=state.charEdit,move=state.charMigrate;clearCharForms();renderRuns();refreshCharacters();q(edit?'[data-make-character-edit="'+CSS.escape(edit)+'"]':move?'[data-make-migrate="'+CSS.escape(move)+'"]':'[data-make-character-save="'+CSS.escape(a||'')+'"]')?.focus();return;}
    const canon=e.target.closest('[data-make-canon]');if(canon){void once('character:'+canon.dataset.makeCanonOf,()=>swapCanon(canon.dataset.makeCanonOf,canon.dataset.makeCanon));return;}
    const editChar=e.target.closest('[data-make-character-edit]');if(editChar){openCharacterEdit(editChar.dataset.makeCharacterEdit);return;}
    const awayChar=e.target.closest('[data-make-character-away]');if(awayChar){void once('character:'+awayChar.dataset.makeCharacterAway,()=>characterCommand(awayChar.dataset.makeCharacterAway,'trash'));return;}
    const restoreChar=e.target.closest('[data-make-character-restore]');if(restoreChar){void once('character:'+restoreChar.dataset.makeCharacterRestore,()=>characterCommand(restoreChar.dataset.makeCharacterRestore,'restore'));return;}
    const migrate=e.target.closest('[data-make-migrate]');if(migrate){openMigration(migrate.dataset.makeMigrate);return;}
    if(e.target.closest('[data-make-note-dismiss]')){dismissNote();return;}
    const pick=e.target.closest('[data-make-pick]');if(pick){if(choosePicture(pick.dataset.makePick)===false)return;state.character=null;renderPictures(goal());q('#makeComposer textarea,#makeComposer input:not([type=search])')?.focus();return;}
    const imp=e.target.closest('[data-make-import]');if(imp){q('[data-make-import-file="'+imp.dataset.makeImport+'"]')?.click();return;}
    const all=e.target.closest('[data-make-all]');if(all){state.allPictures=!state.allPictures;for(const [id,attr] of [['makePictures','data-make-pick'],['makePosePictures','data-make-pose-pick']])renderGrid(id,attr);q('[data-make-all="'+all.dataset.makeAll+'"]')?.focus();return;}
    if(e.target.closest('[data-make-repick]')){state.repicking=true;renderPictures(goal());q('[data-make-search="makePictures"]')?.focus();return;}
    if(e.target.closest('[data-make-keep-picture]')){state.repicking=false;renderPictures(goal());q('#makeComposer .make-step h2')?.focus();return;}
    const posePick=e.target.closest('[data-make-pose-pick]');if(posePick){const a=state.pictures?.find(x=>x.id===posePick.dataset.makePosePick);if(a&&usePrivacy(a)){state.pose={asset:a};state.posePicking=false;renderGoalComposer(goal());q('[data-make-pose-change]')?.focus();}return;}
    if(e.target.closest('[data-make-pose-change]')){state.posePicking=true;renderGoalComposer(goal());q('[data-make-search="makePosePictures"]')?.focus();return;}
    if(e.target.closest('[data-make-style-words]')){state.styleWords=true;renderGoalComposer(goal());q('#makeF-look')?.focus();return;}
    if(e.target.closest('[data-make-style-pictures]')){state.styleWords=false;renderGoalComposer(goal());q('[data-make-style]')?.focus();return;}
    // A result's next step opens that picture goal here with the picture already chosen.
    const pickNext=e.target.closest('[data-make-select]');if(pickNext){state.selected[pickNext.dataset.runId]=pickNext.dataset.makeSelect;renderRuns();q('.make-selected [data-make-select="'+CSS.escape(pickNext.dataset.makeSelect)+'"]')?.closest('figure')?.querySelector('.make-next button:not(:disabled),.make-next summary')?.focus();return;}
    const from=e.target.closest('[data-make-from]');if(from){const next=GOALS.find(x=>x.intent===from.dataset.makeFrom),run=state.runs.find(r=>(r.job.outputs||[]).some(o=>o.asset_id===from.dataset.asset));if(!next||!usePrivacy({privacy:runPrivacy(run||{})})||choosePicture(from.dataset.asset)===false)return;state.goal=next.id;state.compare=false;state.character=null;remember();render();
      say(next.name+': your picture is chosen. Fill in what is asked, then press Generate.');(q('#makeComposer textarea,#makeComposer input')||q('#makeGenerate'))?.focus();return;}
    if(e.target.closest('[data-make-change]')){state.picking=true;renderLooks();q('.make-look.active [data-make-look]')?.focus();return;}
    if(e.target.closest('[data-make-keep-look]')){state.picking=false;renderLooks();focusScene();return;}
    const again=e.target.closest('[data-make-rerun],[data-make-another],[data-make-final]');if(again){const run=state.runs.find(r=>r.job.id===(again.dataset.makeRerun||again.dataset.makeAnother||again.dataset.makeFinal)),final=!!again.dataset.makeFinal;if(!run||!usePrivacy({privacy:runPrivacy(run)}))return;
      state.goal=run.goal;state.look=run.lookId;state.picking=!!again.dataset.makeAnother;state.compare=false;for(const s of Object.values(state.sweeps))s.open=false;
      // Edit and re-run brings the run's tune back with its look; another look starts from that look as made.
      if(!again.dataset.makeAnother){if(Array.isArray(run.tune?.rows)&&Array.isArray(run.tune.cleared)){state.tune[run.lookId]=structuredClone(run.tune);state.tuneOpen=state.tuneOpen||(!!run.tuned&&!final);}else{delete state.tune[run.lookId];delete savedTunes[run.lookId];}}
      // Make the final is Edit and re-run with the draft's steps put back to the look's own: the same words and seed, staged, never sent.
      if(final&&state.tune[run.lookId]){state.tune[run.lookId].steps=null;delete state.tune[run.lookId].turbo;}writeScene(run.scene,run.goal);remember();render();
      if(final){say('The final is set up: the same words and seed at full detail. Press Generate to make it.');q('#makeGenerate')?.focus();return;}
      const scene=q('#makeScene');if(scene&&!state.picking){scene.focus();scene.select();}else q('.make-look.active [data-make-look]')?.focus();return;}
    const redo=e.target.closest('[data-make-redo]');if(redo){const run=state.runs.find(r=>r.job.id===redo.dataset.makeRedo);
      if(run&&redoRun(run)){say('That run’s picture and answers are back. Change what you like, then press Generate.');(q('#makeComposer textarea,#makeComposer input:not([type=search])')||q('#makeGenerate'))?.focus();}return;}
    const recovering=e.target.closest('[data-make-resume],[data-make-stop]');if(recovering&&!recovering.disabled){void once('recover:'+(recovering.dataset.makeResume||recovering.dataset.makeStop),()=>recover(recovering));return;}
    const verdict=e.target.closest('[data-make-review]');if(verdict){void review(verdict);return;}
    const polishing=e.target.closest('[data-make-polish]');if(polishing&&!polishing.disabled){void polishPicture(polishing);return;}
    const varying=e.target.closest('[data-make-vary]');if(varying&&!varying.disabled){void varyPicture(varying);return;}
    if(e.target.closest('#makeGenerate'))void submit();
    if(e.target.closest('#makeEditor'))void openInEditor();
    if(e.target.closest('[data-make-retry]'))void load();
  });
  // Which disclosures are open survives a redraw; opening a line-up reads the pictures (details fire toggle without bubbling).
  view.addEventListener('toggle',e=>{const k=e.target.dataset?.openKey;if(!k)return;if(e.target.open){state.openers.add(k);if(k.startsWith('lineup:'))void fillLineups();}else state.openers.delete(k);},true);
  view.addEventListener('submit',e=>{const form=e.target.closest('[data-make-character-form]');if(form){e.preventDefault();void once('character-save:'+form.dataset.mode+':'+form.dataset.makeCharacterForm,()=>saveCharacter(form));}});
  // One key map across the Studio (pass 2): K keeps and X marks "not this" on the focused picture, as in the Library and the Full editor.
  view.addEventListener('keydown',e=>{const k=e.key?.toLowerCase();if((k==='k'||k==='x')&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.target.matches('input,textarea,select,[contenteditable]')){
    const b=e.target.closest('.make-outputs figure,.make-compare-grid figure')?.querySelector('[data-make-review="'+(k==='k'?'selected':'rejected')+'"]');if(b&&!b.disabled){e.preventDefault();void review(b);return;}}});
  view.addEventListener('keydown',e=>{const radio=e.target.closest('[role="radio"]'),group=radio?.closest('[role="radiogroup"]');if(group&&['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){
    e.preventDefault();const items=[...group.querySelectorAll('[role="radio"]')],i=items.indexOf(radio),next=items[e.key==='Home'?0:e.key==='End'?items.length-1:(i+(['ArrowRight','ArrowDown'].includes(e.key)?1:items.length-1))%items.length],attr=next.hasAttribute('data-make-goal')?'data-make-goal':'data-make-look',value=next.getAttribute(attr);if(attr==='data-make-goal'){state.goal=value;state.pictures=null;remember();render();}else{state.look=value;state.picking=true;remember();renderLooks();}q('['+attr+'="'+value+'"]')?.focus();return;
  }if(e.target.id==='makeLoraSearch'&&e.key==='Enter'&&!e.isComposing){e.preventDefault();if(!e.repeat)q('[data-tune-add]')?.click();return;}
  if((e.target.id==='makeScene'||e.target.dataset.makeField)&&(e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();if(!e.repeat)void submit();}});
  // Generate is one button for every mode: a look, a compare, or a picture goal.
  const submit=()=>goal().intent?goalGenerate():state.compare?generateCompare():generate();
  // The Library's picture dialog opens Make's picture goals with that picture chosen (audit v3 N3); Continue with this stays beside
  // them for the full editor. Leaving follows the dialog's own unsaved-changes rule; nothing is submitted.
  document.addEventListener('click',e=>{const b=e.target.closest('#assetDialog [data-make-open]');if(!b)return;const next=GOALS.find(x=>x.intent===b.dataset.makeOpen);
    if(!next||typeof assetDetailCanLeave==='function'&&!assetDetailCanLeave())return;
    if(choosePicture(b.dataset.asset)===false)return;state.goal=next.id;state.compare=false;state.character=null;state.pictures=null;remember();state.status=next.name+': your picture is chosen. Fill in what is asked, then press Generate.';state.missing='';
    document.querySelector('#assetDialog')?.close();if(typeof showView==='function')showView('make');else window.StudioMake.refresh();
    (q('#makeComposer textarea,#makeComposer input:not([type=search])')||q('#makeGenerate'))?.focus();});
  let loaded=false;
  // Models & setup lists the looks that are ready; a ready look in a Make goal offers "Use in Make" (owner, 19 Oct: browse models, then make).
  // It chooses the goal and the look and opens Make; nothing is sent.
  document.addEventListener('click',e=>{const b=e.target.closest('#modelLooks [data-make-use-look]');if(!b)return;const g=GOALS.find(x=>x.looks?.includes(b.dataset.makeUseLook));if(!g)return;
    state.goal=g.id;state.look=b.dataset.makeUseLook;state.compare=false;state.picking=false;remember();const name=b.closest('li')?.querySelector('b')?.textContent||'';state.status=(name?name+' is chosen. ':'')+'Describe your picture, then press Generate.';state.missing='';if(typeof showView==='function')showView('make');else window.StudioMake.refresh();});
  // Only the unsent draft lives in this tab. Restoring observes at most the two selected asset identities; it never stages media or runs a job.
  const DRAFT_KEY='studio.make.picture-draft',DRAFT_LIMIT=32768,DRAFT_FIELDS=['change','who','clothes','pose','outfit','colours','look','motion','clip'];
  const safeId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)?value:null;
  const draftAsset=a=>a&&safeId(a.id)?{id:a.id,privacy:classified(a),workspace_id:typeof a.workspace_id==='string'?a.workspace_id:null,title:String(a.title||'Saved picture').slice(0,300),media_type:'image'}:null;
  function draftSnapshot(privacy=creationPrivacy()){
    const pose=state.pose?.asset?{asset:draftAsset(state.pose.asset)}:state.pose?.figure?{figure:state.pose.figure,mirror:!!state.pose.mirror}:null;
    const scene=q('#makeScene')?.value||'';
    return{version:1,privacy,goal:state.goal,look:state.look,source:draftAsset(state.pick),form:Object.fromEntries(DRAFT_FIELDS.filter(k=>typeof state.form[k]==='string').map(k=>[k,state.form[k].slice(0,2000)])),
      pose,poseMode:state.poseMode,poseRoute:state.poseRoute,styleLook:state.styleLook,styleWords:!!state.styleWords,fix:state.fix,scene:scene.slice(0,1000)};
  }
  const hasDraft=d=>!!(d?.source||d?.scene||Object.values(d?.form||{}).some(v=>v.trim()));
  const pageDrafts=new Map(),pageScenes=new Map(),pageTunes=new Map();
  function readTunes(privacy){
    if(pageTunes.has(privacy))return pageTunes.get(privacy);
    try{const value=JSON.parse(storedIn(privacy).getItem(privateKey(TUNES,privacy))||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch{return{};}
  }
  function writeTunes(value,privacy){
    pageTunes.set(privacy,structuredClone(value));
    try{const storage=storedIn(privacy),key=privateKey(TUNES,privacy),raw=JSON.stringify(value);storage.setItem(key,raw);
      if(storage.getItem(key)!==raw)throw Error('Tune write was not retained');pageTunes.delete(privacy);draftWarning();return true;
    }catch{draftWarning();return false;}
  }
  function writeScene(value,g=state.goal,privacy=creationPrivacy()){
    const key=privateKey('studio.make.scene.'+g,privacy);pageScenes.set(key,value);
    try{sessionStorage.setItem(key,value);}catch{}
  }
  function draftWarning(){const warning=q('#makeDraftWarning');if(!warning)return;
    warning.hidden=!pageDrafts.has(creationPrivacy())&&!pageTunes.has(creationPrivacy());warning.textContent=warning.hidden?'':'Browser storage could not retain this draft. Keep this page open and copy your wording before reloading. Earlier recovery copies have not been removed.';}
  function writeDraft(d,privacy){
    const value={...d,privacy};pageDrafts.set(privacy,value);
    try{const raw=JSON.stringify(value),key=privateKey(DRAFT_KEY,privacy);if(raw.length>DRAFT_LIMIT)throw Error('Draft exceeds storage limit');
      sessionStorage.setItem(key,raw);if(sessionStorage.getItem(key)!==raw)throw Error('Draft write was not retained');
      pageDrafts.delete(privacy);draftWarning();return true;
    }catch{draftWarning();return false;}
  }
  function sceneDraftValue(){const pending=pageDrafts.get(creationPrivacy());
    if(pending?.goal===state.goal)return pending.scene||'';
    const key=privateKey('studio.make.scene.'+state.goal);return pageScenes.has(key)?pageScenes.get(key):sessionStorage.getItem(key)||'';
  }
  function rememberDraft(){if(draftReady)writeDraft(draftSnapshot(),creationPrivacy());}
  function readDraft(privacy=creationPrivacy()){
    try{const raw=pageDrafts.has(privacy)?JSON.stringify(pageDrafts.get(privacy)):sessionStorage.getItem(privateKey(DRAFT_KEY,privacy));if(!raw||raw.length>DRAFT_LIMIT)return null;const d=JSON.parse(raw);
      if(d?.version!==1||d.privacy!==privacy||!GOALS.some(g=>g.id===d.goal)||!d.form||typeof d.form!=='object'||Array.isArray(d.form))return null;
      if(d.source&&!safeId(d.source.id)||d.pose?.asset&&!safeId(d.pose.asset.id))return null;
      if(privacy==='regular'&&[d.source,d.pose?.asset].some(a=>a&&classified(a)==='private'))return null;
      d.form=Object.fromEntries(DRAFT_FIELDS.filter(k=>typeof d.form[k]==='string'&&d.form[k].length<=2000).map(k=>[k,d.form[k]]));
      return d;
    }catch{return null;}
  }
  function applyDraft(d){
    state.goal=d.goal;state.look=safeId(d.look);state.pick=draftAsset(d.source);state.form={...d.form};state.character=null;state.repicking=false;state.posePicking=false;
    state.poseMode=d.poseMode==='figure'?'figure':'picture';state.poseRoute=['copy','scene','depth'].includes(d.poseRoute)?d.poseRoute:'copy';
    state.pose=d.pose?.asset?{asset:draftAsset(d.pose.asset)}:PE()?.PRESETS?.some(p=>p.id===d.pose?.figure)?{figure:d.pose.figure,mirror:!!d.pose.mirror}:null;
    state.styleLook=safeId(d.styleLook);state.styleWords=!!d.styleWords;state.fix=POLISH[d.fix]?d.fix:'face';
    if(typeof d.scene==='string')writeScene(d.scene.slice(0,1000),d.goal,d.privacy);
  }
  async function restoreDraft(d,epoch=privacyEpoch,revision=draftRevision){
    if(!d)return;const resolved=[];
    try{for(const saved of [d.source,d.pose?.asset].filter(Boolean)){
        if(!/^[0-9a-f]{32}$/.test(saved.workspace_id||''))throw Error('This draft has no verified library identity. Choose its pictures again; your wording is kept.');
        const result=await json('/api/assets/selection',{ids:[saved.id],workspace_id:saved.workspace_id,details:true},requestPrivacy(classified(saved),d.privacy));
        if(epoch!==privacyEpoch||revision!==draftRevision)return;
        const item=result.items?.find(x=>x.id===saved.id);
        if(saved.workspace_id&&result.workspace_id!==saved.workspace_id)throw Error('This draft belongs to another library. Choose its pictures again.');
        if(item?.state!=='active'||!item.asset||item.asset.media_type!=='image')throw Error('A picture in this draft is unavailable. Choose another picture; your wording is kept.');
        resolved.push({...item.asset,privacy:classified(item.asset)});
      }
      if(epoch!==privacyEpoch||revision!==draftRevision)return;applyDraft(d);if(d.source)state.pick=resolved[0];if(d.pose?.asset)state.pose={asset:resolved[resolved.length-1]};draftProblem='';
    }catch(error){if(epoch!==privacyEpoch||revision!==draftRevision)return;applyDraft(d);draftProblem=error.code==='asset_workspace_conflict'?'This draft belongs to another library. Choose its pictures again.':error.message;}
  }
  // These listeners run after the existing handlers, so they record the actual edited values without another execution owner.
  for(const name of ['input','change','click','keydown'])view.addEventListener(name,e=>{if(name==='keydown'&&!['Enter',' ','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;draftRevision++;rememberDraft();});
  document.addEventListener('studio:privacy-change',event=>{
    const {previousCreation='regular',creation=creationPrivacy()}=event.detail||{},before=draftSnapshot(previousCreation),migrate=previousCreation==='regular'&&creation==='private'&&hasDraft(before);
    if(draftReady&&hasDraft(before))writeDraft(before,previousCreation);
    if(migrate){const retained=writeDraft(before,'private');let tuneRetained=true;
      // Copy and verify the active tune before retiring either regular recovery record.
      // A failed write keeps a page-local private copy; another tab's newer tune is never erased.
      if(!GOALS.find(g=>g.id===before.goal)?.intent&&savedTunes[before.look]){
        const own=structuredClone(savedTunes[before.look]),privateTunes={...readTunes('private'),[before.look]:own};
        tuneRetained=writeTunes(privateTunes,'private');
        if(retained&&tuneRetained)try{const regular=JSON.parse(localStorage.getItem(TUNES)||'{}');
          if(JSON.stringify(regular[before.look])===JSON.stringify(own)){delete regular[before.look];localStorage.setItem(TUNES,JSON.stringify(regular));}}
        catch{}
      }
      if(retained&&tuneRetained)try{sessionStorage.removeItem(privateKey(DRAFT_KEY,'regular'));sessionStorage.removeItem(privateKey('studio.make.scene.'+before.goal,'regular'));pageDrafts.delete('regular');pageScenes.delete(privateKey('studio.make.scene.'+before.goal,'regular'));}catch{}
    }
    privacyEpoch++;draftRevision++;draftReady=false;draftProblem='';view.dataset.draftState='restoring';
    for(const timer of timers.values())clearTimeout(timer);timers.clear();planning.clear();
    state.runs=[];state.pictures=null;state.characters=[];state.charStale=false;state.review={};state.record={};state.polish={};state.queries={};state.allPictures=false;state.openers.clear();clearCharForms();
    state.status='';state.missing='';state.error='';state.compare=false;state.compareLooks=[];state.sweeps={};
    if(previousCreation!==creation){state.pick=null;state.pose=null;state.form={};state.character=null;state.styleLook=null;state.styleWords=false;state.repicking=false;state.posePicking=false;state.tune={};
      savedTunes=readTunes(creation);
      const next=readDraft();if(next)applyDraft(next);
    }
    restoredRuns=false;savedRuns=readSavedRuns();render();void load();
  });
  // The finder passes intent to this owner; old recovery cannot override an explicit choice.
  let pendingNavigation=null;
  function navigationValue(value){
    const g=value&&GOALS.find(g=>g.id===value.goal);if(!g)return null;
    const look=value.look??null;if(look!==null&&!g.looks?.includes(look))return null;
    return{goal:g.id,look};
  }
  function takeNavigation(){try{const key='studio.make.navigation',raw=sessionStorage.getItem(key);if(!raw)return null;
    sessionStorage.removeItem(key);if(sessionStorage.getItem(key)!==null)return null;
    return raw.length<=512?navigationValue(JSON.parse(raw)):null;
  }catch{return null;}}
  function chooseNavigation(value){const next=navigationValue(value);if(!next)return false;
    if(!draftReady){pendingNavigation=next;return true;}
    draftRevision++;state.goal=next.goal;state.look=next.look;state.compare=false;state.compareLooks=[];state.picking=false;state.pictures=null;
    remember();render();return true;
  }
  window.StudioMake={goalOf:id=>GOALS.find(x=>x.looks?.includes(id))?.id||null,choose:selection=>chooseNavigation(selection),refreshReadiness:syncOperation,refresh(){if(!loaded){loaded=true;void load();}else render();}};
  if(!view.hidden)window.StudioMake.refresh();
})();
