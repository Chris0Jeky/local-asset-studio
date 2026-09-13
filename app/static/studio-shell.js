/* Shared shell for independently served pages. No executor or router dependency. */
(function(){
  'use strict';
  const $=s=>document.querySelector(s),main=$('main'),isMain=!!$('#createView');
  if(!main)return;
  const links=[['home','Overview','Attention, recent work and next steps','/#home','01','Workspace'],['workflows','Guided workflows','Walkthroughs, node builder and headless recipes','/workflow-studio.html','◎','Workspace'],['create','Create','Recipes, references and generation','/#create','02','Workspace'],['assets','Asset library','Import, organize and reuse outputs','/#assets','03','Workspace'],['production','Runs & review','Comparisons, budgets and exports','/#production','04','Workspace'],['prompt','Prompt Lab','Shape a brief for a model','/prompt-lab.html','✧','Creative tools'],['scene','Scene editor','Assemble images, video and audio','/av.html','▤','Creative tools'],['voice','Voice takes','Prepare local spoken lines','/voice.html','≋','Creative tools'],['models','Models & setup','Environments, readiness and storage','/#models','◇','Studio'],['learn','Workflow guide','Understand recipes and native tools','/#learn','?','Studio']];
  document.body.classList.add('studio-shell',isMain?'studio-main':'studio-tool');
  if(!main.id)main.id='studioMain';main.tabIndex=-1;
  const sidebar=document.createElement('aside');sidebar.id='studioSidebar';sidebar.className='studio-sidebar';
  let group='';sidebar.innerHTML='<a class="studio-logo" href="/#home"><span class="studio-monogram" aria-hidden="true">a✦</span><span>ASSET STUDIO<small>LOCAL CREATIVE WORKSPACE</small></span></a><nav aria-label="Studio navigation">'+links.map(([id,label,description,href,icon,section])=>{const heading=section!==group?'<p class="nav-group">'+section+'</p>':'';group=section;return heading+'<a href="'+href+'" data-studio-route="'+id+'" title="'+description+'"><span class="nav-icon" aria-hidden="true">'+icon+'</span><span>'+label+'</span></a>';}).join('')+'</nav><div class="sidebar-bottom"><span class="local-indicator">● LOCAL BY DESIGN</span><p>Your files. Your recipes.<br>Your decision to run.</p><a href="/#models">Environment & storage →</a></div>';
  const header=document.createElement('div');header.className='studio-globalbar';header.innerHTML='<button id="studioNavToggle" aria-controls="studioSidebar" aria-expanded="false">Menu</button><div class="studio-breadcrumb"><span>Studio</span><span aria-hidden="true">/</span><strong id="studioPageTitle">Overview</strong></div><button id="studioJump" class="studio-jump">Jump to a tool <kbd>Ctrl K</kbd></button><div id="studioConnection"></div>';
  const skip=document.createElement('a');skip.className='studio-skip';skip.href='#'+main.id;skip.textContent='Skip to workspace';skip.onclick=e=>{e.preventDefault();main.focus();};
  document.body.prepend(skip,sidebar,header);
  const health=$('#health');if(health)$('#studioConnection').append(health);
  document.querySelectorAll('.topbar').forEach(el=>el.remove());
  const runtime=$('.runtime-bar');if(runtime&&$('#modelsView')){const details=document.createElement('details');details.className='environment-panel';details.open=true;details.innerHTML='<summary>Model environment <small>Switching is always explicit</small></summary>';details.append(runtime);$('#modelsView').prepend(details);}
  const dialog=document.createElement('dialog');dialog.id='studioCommandDialog';dialog.className='studio-dialog command-dialog';dialog.setAttribute('aria-labelledby','studioCommandTitle');dialog.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">GO SOMEWHERE</span><h2 id="studioCommandTitle">Find your next tool</h2></div><button data-command-close aria-label="Close tool finder">✕</button></div><label for="studioCommandSearch">Search tools and workflows</label><input id="studioCommandSearch" type="search" autocomplete="off" placeholder="Try references, review, scene, models…"><div id="studioCommandResults" class="command-results"></div><p class="muted">Navigation only. Nothing here starts generation or installs a model.</p>';document.body.append(dialog);
  const workerNotice=$('#workerFailure');if(workerNotice)workerNotice.classList.add('callout','error');
  let opener=null;
  function closeNav(){document.body.classList.remove('studio-nav-open');$('#studioNavToggle').setAttribute('aria-expanded','false');}
  function setView(id){
    // The workbench inserts Overview after shell setup; keep diagnostics outside hidden views.
    if(workerNotice&&main.firstElementChild!==workerNotice)main.prepend(workerNotice);
    const entry=links.find(x=>x[0]===id);$('#studioPageTitle').textContent=entry?.[1]||(id==='review'?'Review desk':'Overview');document.querySelectorAll('[data-studio-route]').forEach(a=>{const active=a.dataset.studioRoute===id;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});closeNav();}
  function commands(){const q=$('#studioCommandSearch').value.trim().toLowerCase();$('#studioCommandResults').innerHTML=links.filter(x=>x.slice(0,3).join(' ').toLowerCase().includes(q)).map(([id,label,description,href])=>'<a href="'+href+'"><b>'+label+'</b><small>'+description+'</small><span aria-hidden="true">↗</span></a>').join('')||'<p>No matching tool. Try create, voice or review.</p>';}
  function openCommands(){opener=document.activeElement;$('#studioCommandSearch').value='';commands();dialog.showModal();$('#studioCommandSearch').focus();}
  $('#studioJump').onclick=openCommands;$('#studioCommandSearch').oninput=commands;
  $('#studioCommandSearch').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('#studioCommandResults a')?.click();}else if(e.key==='ArrowDown'){e.preventDefault();$('#studioCommandResults a')?.focus();}};
  dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dialog.close();}});
  $('[data-command-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{if(opener?.isConnected)opener.focus();});$('#studioCommandResults').onclick=e=>{if(e.target.closest('a'))dialog.close();};
  $('#studioNavToggle').onclick=()=>{const open=document.body.classList.toggle('studio-nav-open');$('#studioNavToggle').setAttribute('aria-expanded',String(open));};
  document.addEventListener('click',e=>{if(!sidebar.contains(e.target)&&!e.target.closest('#studioNavToggle'))closeNav();const a=e.target.closest('a');if(!a||e.defaultPrevented||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||a.target||a.hasAttribute('download'))return;if(isMain){const url=new URL(a.href,location.href);if(url.origin===location.origin&&url.pathname==='/'&&url.hash&&StudioUX.VIEWS.includes(url.hash.slice(1))){e.preventDefault();document.dispatchEvent(new CustomEvent('studio:navigate',{detail:url.hash.slice(1)}));}}});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'&&!document.querySelector('dialog[open]')){e.preventDefault();openCommands();}if(e.key==='Escape'&&document.body.classList.contains('studio-nav-open')){closeNav();$('#studioNavToggle').focus();}});
  const route=location.pathname.includes('workflow-studio.html')?'workflows':location.pathname.includes('av.html')?'scene':location.pathname.includes('voice.html')?'voice':location.pathname.includes('prompt-lab.html')?'prompt':location.pathname.includes('review.html')?'review':'home';
  setView(isMain?StudioUX.normalizeView(location.hash):route);window.StudioShell={setView,openCommands};
  if(isMain){
    const css=document.createElement('link');css.rel='stylesheet';css.href='/static/bundle-explorer.css';document.head.append(css);
    const core=document.createElement('script');core.src='/static/bundle-core.js';core.onload=()=>{const ui=document.createElement('script');ui.src='/static/bundle-explorer.js';document.body.append(ui);};document.body.append(core);
  }
  if(new URLSearchParams(location.search).has('guide')){
    const css=document.createElement('link');css.rel='stylesheet';css.href='/static/studio-guide.css';document.head.append(css);
    const rules=document.createElement('script');rules.src='/static/studio-guide-state.js';rules.onload=()=>{const coach=document.createElement('script');coach.src='/static/studio-guide.js';document.body.append(coach);};document.body.append(rules);
  }
})();
