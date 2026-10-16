/* Shared shell for independently served pages. No executor or router dependency. */
(function(){
  'use strict';
  const $=s=>document.querySelector(s),main=$('main'),isMain=!!$('#createView');
  if(!main)return;
  if(!$('#studioNavigationStyles')){const css=document.createElement('link');css.id='studioNavigationStyles';css.rel='stylesheet';css.href='/static/studio-navigation.css';document.head.append(css);}
  const links=[['make','Make','Pick a goal and a look, describe it, generate','/#make','✦','Workspace'],['assets','Library','Import, organize and reuse outputs','/#assets','03','Workspace'],['models','Models & setup','Environments, readiness and storage','/#models','◇','Workspace'],['create','Full editor','Every recipe, reference and setting','/#create','02','Advanced'],['production','Compare & review','Comparisons, budgets and exports','/#production','04','Advanced'],['workflows','Workflow builder','Walkthroughs, node builder and headless recipes','/workflow-studio.html#builder','◎','Advanced'],['prompt','Prompt Lab','Shape a brief for a model','/prompt-lab.html','✧','More tools'],['scene','Scene editor','Assemble images, video and audio','/av.html','▤','More tools'],['voice','Voice takes','Prepare local spoken lines','/voice.html','≋','More tools'],['learn','Workflow guide','Understand recipes and native tools','/#learn','?','More tools'],['home','Overview','Attention, recent work and next steps','/#home','01','Workspace',true]];
  // Make keeps this list private; studio_ux.cjs pins names, hints and look membership to its GOALS.
  const makeGoals=[
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
  const synonyms={repair:'upscale fix face fix hands',combine:'pose',mesh:'3d',animate:'animate video',restyle:'restyle style'};
  const keywords={models:'download install',assets:'library pictures keepers',production:'compare',create:'full editor recipe seed'};
  const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let looks=[];
  document.body.classList.add('studio-shell',isMain?'studio-main':'studio-tool');
  if(!main.id)main.id='studioMain';main.tabIndex=-1;
  const sidebar=document.createElement('aside');sidebar.id='studioSidebar';sidebar.className='studio-sidebar';
  sidebar.innerHTML='<a class="studio-logo" href="/#make"><span class="studio-monogram" aria-hidden="true">a✦</span><span>ASSET STUDIO<small>LOCAL CREATIVE WORKSPACE</small></span></a><nav aria-label="Studio navigation">'+['Workspace','Advanced','More tools'].map(section=>{const items=links.filter(x=>x[5]===section&&!x[6]).map(([id,label,description,href,icon])=>'<a href="'+href+'" data-studio-route="'+id+'" title="'+description+'"><span class="nav-icon" aria-hidden="true">'+icon+'</span><span>'+label+'</span></a>').join('');return section==='Workspace'?'<p class="nav-group">'+section+'</p>'+items:'<details class="studio-nav-group" data-nav-group="'+section+'"><summary class="nav-group">'+section+'</summary>'+items+'</details>';}).join('')+'</nav><div class="sidebar-bottom"><span class="local-indicator">● LOCAL BY DESIGN</span><p>Your files. Your recipes.<br>Your decision to run.</p><a href="/#models">Environment & storage →</a></div>';
  const header=document.createElement('div');header.className='studio-globalbar';header.innerHTML='<button id="studioNavToggle" aria-controls="studioSidebar" aria-expanded="false">Menu</button><div class="studio-breadcrumb"><span>Studio</span><span aria-hidden="true">/</span><strong id="studioPageTitle">Overview</strong></div><a id="studioQuickCreate" class="studio-quick-create" href="/#make" hidden>Make</a><button id="studioJump" class="studio-jump">Jump to a tool <kbd>Ctrl K</kbd></button><div id="studioConnection"></div>';
  const skip=document.createElement('a');skip.className='studio-skip';skip.href='#'+main.id;skip.textContent='Skip to workspace';skip.onclick=e=>{e.preventDefault();main.focus();};
  document.body.prepend(skip,sidebar,header);
  sidebar.querySelectorAll('[data-nav-group]').forEach(details=>{const key='studio.nav.'+details.dataset.navGroup;try{details.open=localStorage.getItem(key)==='true';}catch{}details.addEventListener('toggle',()=>{try{localStorage.setItem(key,String(details.open));}catch{}});});
  const health=$('#health');if(health)$('#studioConnection').append(health);
  document.querySelectorAll('.topbar').forEach(el=>el.remove());
  const runtime=$('.runtime-bar');if(runtime&&$('#modelsView')){const details=document.createElement('details');details.className='environment-panel';details.open=true;details.innerHTML='<summary>Model environment <small>Switching is always explicit</small></summary>';details.append(runtime);$('#modelsView').prepend(details);}
  const dialog=document.createElement('dialog');dialog.id='studioCommandDialog';dialog.className='studio-dialog command-dialog';dialog.setAttribute('aria-labelledby','studioCommandTitle');dialog.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">GO SOMEWHERE</span><h2 id="studioCommandTitle">Find your next tool</h2></div><button data-command-close aria-label="Close tool finder">✕</button></div><label for="studioCommandSearch">Search tools, goals and looks</label><input id="studioCommandSearch" type="search" autocomplete="off" placeholder="Try references, review, scene, models…"><div id="studioCommandResults" class="command-results"></div><p class="muted">Navigation only. Nothing here starts generation or installs a model.</p>';document.body.append(dialog);
  const workerNotice=$('#workerFailure');if(workerNotice)workerNotice.classList.add('callout','error');
  let opener=null;
  function syncNavigation(){
    const compact=getComputedStyle($('#studioNavToggle')).display!=='none';
    if(!compact)document.body.classList.remove('studio-nav-open');
    const open=compact&&document.body.classList.contains('studio-nav-open');
    $('#studioNavToggle').setAttribute('aria-expanded',String(open));
    $('#studioQuickCreate').hidden=!compact;
    sidebar.inert=compact&&!open;sidebar.setAttribute('aria-hidden',String(sidebar.inert));
    if(sidebar.inert&&sidebar.contains(document.activeElement))main.focus({preventScroll:true});
  }
  function closeNav(){document.body.classList.remove('studio-nav-open');syncNavigation();}
  window.addEventListener('resize',syncNavigation);
  // Observe the settled destination, including departure from the toggle. A blur
  // microtask can run while activeElement is body, before native Tab sets focus.
  document.addEventListener('focusin',event=>{
    if(document.body.classList.contains('studio-nav-open')&&!sidebar.contains(event.target)&&event.target!==$('#studioNavToggle'))closeNav();
  });
  function setView(id){
    // The workbench inserts Overview after shell setup; keep diagnostics outside hidden views.
    if(workerNotice&&main.firstElementChild!==workerNotice)main.prepend(workerNotice);
    const quick=$('#studioQuickCreate');quick.classList.toggle('active',id==='make');if(id==='make')quick.setAttribute('aria-current','page');else quick.removeAttribute('aria-current');
    const entry=links.find(x=>x[0]===id);$('#studioPageTitle').textContent=entry?.[1]||(id==='review'?'Review desk':'Overview');document.querySelectorAll('[data-studio-route]').forEach(a=>{const active=a.dataset.studioRoute===id;a.classList.toggle('active',active);if(active){a.setAttribute('aria-current','page');const group=a.closest('details');if(group)group.open=true;}else a.removeAttribute('aria-current');});closeNav();}
  function commands(){
    const q=$('#studioCommandSearch').value.trim().toLowerCase();
    const entries=[...makeGoals.map(g=>({label:g.name,description:g.hint,href:'/#make',goal:g.id,search:synonyms[g.id]||''})),...looks.map(l=>{const g=makeGoals.find(g=>g.looks?.includes(l.id));return{label:l.name,description:g?'Look - Make':'Look - open Make to choose a look',href:'/#make',look:g?l.id:null,goal:g?.id,search:l.id==='look-preset-pixel-lora'?'pixel':''};}),...links.map(([id,label,description,href])=>({label,description,href,search:id+' '+(keywords[id]||'')}))];
    $('#studioCommandResults').innerHTML=entries.filter(x=>(x.label+' '+x.description+' '+x.search).toLowerCase().includes(q)).sort((a,b)=>Number(!!q&&(' '+b.search+' ').includes(' '+q+' '))-Number(!!q&&(' '+a.search+' ').includes(' '+q+' '))).map(x=>'<a href="'+escape(x.href)+'"'+(x.goal?' data-make-goal="'+escape(x.goal)+'"':'')+(x.look?' data-make-look="'+escape(x.look)+'"':'')+'><b>'+escape(x.label)+'</b><small>'+escape(x.description)+'</small><span aria-hidden="true">&#8599;</span></a>').join('')||'<p>No match. Try anime, upscale, pose, pixel, compare or download.</p>';
  }
  async function loadLooks(){try{const r=await fetch('/api/looks');if(!r.ok)return;const data=await r.json();looks=(data.looks||data.cards||[]).filter(l=>!l.trashed_at&&(l.kind==='look'||l.body)&&typeof l.id==='string'&&typeof l.name==='string');if(dialog.open&&!$('#studioCommandResults').contains(document.activeElement))commands();}catch{}}
  function openCommands(){opener=document.activeElement;$('#studioCommandSearch').value='';commands();dialog.showModal();loadLooks();$('#studioCommandSearch').focus();}
  $('#studioJump').onclick=openCommands;$('#studioCommandSearch').oninput=commands;
  $('#studioCommandSearch').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('#studioCommandResults a')?.click();}};
  dialog.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){const items=[...$('#studioCommandResults').querySelectorAll('a')],index=items.indexOf(document.activeElement);e.preventDefault();if(e.key==='ArrowUp'&&index<=0)$('#studioCommandSearch').focus();else items[Math.min(items.length-1,index+(e.key==='ArrowDown'?1:-1))]?.focus();}if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dialog.close();}});
  $('[data-command-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{if(opener?.isConnected)opener.focus();});$('#studioCommandResults').onclick=e=>{const a=e.target.closest('a');if(!a)return;dialog.close();if(!a.dataset.makeGoal&&!a.dataset.makeLook)return;e.preventDefault();e.stopPropagation();try{const saved=JSON.parse(localStorage.getItem('studio.make')||'{}');localStorage.setItem('studio.make',JSON.stringify({...saved,...(a.dataset.makeGoal?{goal:a.dataset.makeGoal}:{}),look:a.dataset.makeLook||null}));}catch{}location.href='/#make';if(isMain)location.reload();};
  $('#studioNavToggle').onclick=()=>{const open=document.body.classList.toggle('studio-nav-open');syncNavigation();if(open){const target=sidebar.querySelector('[aria-current=page]')||sidebar.querySelector('nav a'),group=target?.closest('details');if(group)group.open=true;target?.focus({preventScroll:true});}};
  document.addEventListener('click',e=>{if(!sidebar.contains(e.target)&&!e.target.closest('#studioNavToggle'))closeNav();const a=e.target.closest('a');if(!a||e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||a.target||a.hasAttribute('download'))return;if(isMain){const url=new URL(a.href,location.href);if(url.origin===location.origin&&url.pathname==='/'&&url.hash&&StudioUX.VIEWS.includes(url.hash.slice(1))){e.preventDefault();document.dispatchEvent(new CustomEvent('studio:navigate',{detail:url.hash.slice(1)}));}}});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'&&!document.querySelector('dialog[open]')){e.preventDefault();openCommands();}if(e.key==='Escape'&&document.body.classList.contains('studio-nav-open')){closeNav();$('#studioNavToggle').focus();}});
  const route=location.pathname.includes('workflow-studio.html')?'workflows':location.pathname.includes('av.html')?'scene':location.pathname.includes('voice.html')?'voice':location.pathname.includes('prompt-lab.html')?'prompt':location.pathname.includes('review.html')?'review':'home';
  setView(isMain?StudioUX.normalizeView(location.hash):route);window.StudioShell={setView,openCommands};
  if(isMain){
    // #907 spike: the compiled Vue guidance island loads only behind the explicit ?ui=island flag, after the workshop owns Create.
    const loadIsland=()=>{if(new URLSearchParams(location.search).get('ui')!=='island'||$('#uiIslandScript'))return;const style=document.createElement('link');style.rel='stylesheet';style.href='/static/ui-dist/island.css';document.head.append(style);const island=document.createElement('script');island.id='uiIslandScript';island.type='module';island.src='/static/ui-dist/island.js';document.body.append(island);};
    const loadWorkshop=()=>{const workshop=document.createElement('script');workshop.src='/static/workshop.js';workshop.onload=()=>{const ambienceView=document.createElement('script');ambienceView.src='/static/workshop-ambience.js';document.body.append(ambienceView);loadIsland();};document.body.append(workshop);};
    const context=document.createElement('script');context.src='/static/presentation-context.js';context.onload=()=>{const ambience=document.createElement('script');ambience.src='/static/workshop-ambience-policy.js';ambience.onload=loadWorkshop;ambience.onerror=loadWorkshop;document.body.append(ambience);};document.body.append(context);
    const disclosureStyle=document.createElement('link');disclosureStyle.rel='stylesheet';disclosureStyle.href='/static/create-progressive-disclosure.css';document.head.append(disclosureStyle);
    const disclosure=document.createElement('script');disclosure.src='/static/create-progressive-disclosure.js';document.body.append(disclosure);
    const parallaxRecovery=document.createElement('script');parallaxRecovery.src='/static/parallax-stage-recovery.js';document.body.append(parallaxRecovery);
    const proposalStyle=document.createElement('link');proposalStyle.rel='stylesheet';proposalStyle.href='/static/setup-proposal.css';document.head.append(proposalStyle);
    const proposal=document.createElement('script');proposal.src='/static/setup-proposal.js';proposal.onload=()=>{const apply=document.createElement('script');apply.src='/static/setup-apply.js';apply.onload=()=>{window.StudioSetupApply.mount(window);window.StudioSetupProposal.mount(window);};document.body.append(apply);};document.body.append(proposal);
    const css=document.createElement('link');css.rel='stylesheet';css.href='/static/bundle-explorer.css';document.head.append(css);
    const core=document.createElement('script');core.src='/static/bundle-core.js';core.onload=()=>{const ui=document.createElement('script');ui.src='/static/bundle-explorer.js';document.body.append(ui);};document.body.append(core);
  }
  if(new URLSearchParams(location.search).has('guide')){
    const css=document.createElement('link');css.rel='stylesheet';css.href='/static/studio-guide.css';document.head.append(css);
    const rules=document.createElement('script');rules.src='/static/studio-guide-state.js';rules.onload=()=>{const coach=document.createElement('script');coach.src='/static/studio-guide.js';document.body.append(coach);};document.body.append(rules);
  }
  if(isMain||route==='workflows'){
    const style=document.createElement('link');style.rel='stylesheet';style.href='/static/recipe-shortlist.css';document.head.append(style);
    const script=document.createElement('script');script.src='/static/recipe-shortlist.js';script.defer=true;document.body.append(script);
  }
})();
