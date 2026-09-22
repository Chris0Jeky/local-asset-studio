/* Bundle discovery is a workbench client, not another recipe store or executor. */
(function(){
  'use strict';
  function mount(){
    if(!document.querySelector('#createView')||document.querySelector('#bundleLauncher'))return;
    const B=StudioBundles,q=s=>document.querySelector(s),escape=esc;
    let opener=null,items=[],active=null,preset=null,baseline={},overrides={},inspection=null,epoch=0,openEpoch=0,context='',sourceIdentity='',showcase={},showcaseMessage='',inspectionMessage='',tuning=null,pendingProposal=null;
    const button=document.createElement('button');button.id='bundleLauncher';button.type='button';button.className='bundle-launcher';button.innerHTML='<b>Explore creative bundles</b><span>See the look, ingredients and settings together →</span>';
    const styling=document.createElement('link');styling.rel='stylesheet';styling.href='/static/bundle-tuning.css';document.head.append(styling);
    const anchor=q('#presetSearch');if(!anchor)return;(anchor.closest('label')||anchor).before(button);
    button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','bundleExplorer');
    const dialog=document.createElement('dialog');dialog.id='bundleExplorer';dialog.className='bundle-explorer';dialog.setAttribute('aria-labelledby','bundleTitle');
    dialog.innerHTML='<header class="bundle-header"><div><span class="eyebrow">CREATIVE BUNDLES</span><h2 id="bundleTitle">Start with a look. Understand the recipe.</h2><p>Browse without changing your work. Apply only after reviewing the differences.</p></div><button id="bundleClose" type="button" aria-label="Close bundle explorer">Close</button></header><div class="bundle-layout"><aside class="bundle-browser"><label for="bundleSearch">Find a look or resource<input id="bundleSearch" type="search" placeholder="Painterly, ink, Anima…"></label><label for="bundleFamily">Model family<select id="bundleFamily"><option value="">All families</option></select></label><p id="bundleCount" role="status"></p><div id="bundleCards"></div></aside><section class="bundle-detail" aria-label="Selected bundle"><p id="bundleStatus" role="status"></p><div id="bundleBody"><p>Choose a bundle to inspect its ingredients and examples.</p></div></section></div>';
    document.body.append(dialog);
    function status(message){q('#bundleStatus').textContent=message;}
    function snapshot(){return B.canonical({preset:selected?.id,controls:selected?values():{},batch:q('#batch')?.value,parents:typeof parentAssets==='undefined'?[]:parentAssets,references:typeof referenceRecords==='undefined'?[]:referenceRecords});}
    function source(){return B.canonical({preset,recipe:active,knowledge:knowledge||null});}
    function sources(urls){return B.links(urls).map(u=>'<a href="'+escape(u)+'" target="_blank" rel="noreferrer">'+escape(new URL(u).hostname)+' ↗</a>').join(' · ');}
    function record(id){return B.sample(showcase.examples?.[id]);}
    function card(item){const p=catalog.presets.find(p=>p.id===item.preset_id);let count='Needs review';try{count=B.adapters(p,B.resolve(p,item),knowledge).filter(a=>a.active).length+' active adapter(s)';}catch{}const s=record(item.id);return '<button type="button" class="bundle-card" data-bundle="'+escape(item.id)+'" aria-pressed="'+(item.id===active?.id)+'">'+(s?'<img loading="lazy" src="'+escape(s.url)+'" alt="'+escape(s.caption)+'">':'<span class="bundle-no-preview">No documented preview</span>')+'<b>'+escape(item.name)+'</b><span>'+escape(item.family||p?.family||'Family not recorded')+'</span><small>'+escape(count)+' · '+B.evidence(item).label+'</small></button>';}
    function images(){dialog.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{const note=document.createElement('span');note.className='bundle-no-preview';note.textContent='Preview file unavailable; recipe retained. Local example media rebuilds with: python scripts/lab-media.py restore';img.replaceWith(note);},{once:true}));}
    function cards(){const search=q('#bundleSearch').value.toLowerCase(),family=q('#bundleFamily').value;const filtered=items.filter(r=>(!family||r.family===family)&&[r.name,r.family,...(r.tags||[]),...Object.values(r.controls||{})].join(' ').toLowerCase().includes(search));q('#bundleCount').textContent=filtered.length+' bundles · authored control sets';q('#bundleCards').innerHTML=filtered.map(card).join('')||'<p>No matching bundles. Try another family or clear the search.</p>';images();}
    function ingredientHtml(controls){const rows=B.resources(preset,controls,inspection?.graph);return '<p class="bundle-caveat">'+escape(inspectionMessage||'Authored graph resources, with this draft’s bound settings. Create checks runtime prerequisites separately. This view does not verify installed hashes.')+'</p>'+(rows.length?'<dl class="bundle-ingredients">'+rows.map(r=>'<div><dt>'+escape(r.role)+(r.active?'':' · off')+'</dt><dd>'+escape(r.file)+'<small>Node '+escape(r.node)+' · '+escape(r.field)+'</small></dd></div>').join('')+'</dl>':'<p>No resource graph available yet. This does not mean no models are required.</p>');}
    function guideHtml(){const g=B.guidance(knowledge,preset);if(!g.entry)return '<p>No stored family guidance. Keep the authored settings, or compare a deliberate change in Runs & review.</p>';return '<p class="bundle-caveat">Stored family guidance · '+escape(g.family)+' · '+escape(g.updated||'date unknown')+'. Suggestions are not proof that this exact stack was tested. Read the conditions before changing a value.</p>'+(g.entry.prompt?.style?'<h4>Prompt approach</h4><p>'+escape(g.entry.prompt.style)+'</p>':'')+(g.entry.axes||[]).filter(a=>B.bound(preset,a.control)&&!B.SLOTS.includes(a.control)).map(a=>'<details><summary>'+escape(a.id)+' <small>'+escape((a.values||[]).join(' / '))+'</small></summary><p>'+escape(a.rationale)+'</p><p>'+sources(a.sources)+'</p>'+(a.observed?.length?'<p><b>Recorded observations, not a controlled benchmark</b></p><ul>'+a.observed.map(o=>'<li>'+escape(o)+'</li>').join('')+'</ul>':'<p>No local observations attached to this suggestion.</p>')+'</details>').join('');}
    function field(key,v){const range=B.limits(preset,key),help=({positive:'Describe the subject and composition. Review the adapter trigger notes.',negative:'Only present when this graph exposes negative conditioning.',seed:'Keep fixed to compare a change; runtime and model versions still matter.',steps:'Sampling iterations, not a quality score. Accelerated recipes need their matching schedule.',cfg:'Graph-specific conditioning strength. Do not transfer this value between model families.',width:'Canvas pixels; changing size can alter composition, time and memory.',height:'Canvas pixels; the workflow’s required multiple is enforced.'})[key]||'This slot’s strength, not a universal style slider. Zero disables it in supported Studio graphs.';return '<label>'+escape(B.controlLabel(key))+' '+(range?'<input data-bundle-control="'+key+'" type="number" min="'+range[0]+'" max="'+range[1]+'" step="'+range[2]+'" value="'+escape(v)+'">':'<textarea data-bundle-control="'+key+'" rows="4">'+escape(v)+'</textarea>')+'<small>'+escape(help)+'</small></label>';}
    function tuningHtml(){
      const alternatives=items.filter(r=>r.preset_id===preset.id);
      return '<section class="bundle-review" id="bundleTuning"><h4>Try a related setup</h4><p>Bring over a complete authored stack and sampling setup. Keep the parts of your idea you choose; review everything before changing the draft.</p><label>Authored alternative<select id="bundleAlternative">'+alternatives.map(r=>'<option value="'+escape(r.id)+'">'+escape(r.name)+'</option>').join('')+'</select></label><div class="bundle-preserve"><label><input type="checkbox" id="bundleKeepIdea" checked> Keep my prompt and negative prompt</label><label><input type="checkbox" id="bundleKeepSeed" checked> Keep my seed</label><label><input type="checkbox" id="bundleKeepCanvas" checked> Keep my canvas size</label></div><button id="bundlePropose" type="button">Review setup change</button><div id="bundleProposal" aria-live="polite"></div><div class="bundle-history"><button id="bundleUndo" type="button">Undo draft change</button><button id="bundleRedo" type="button">Redo draft change</button><small>Draft only. Nothing is saved or generated here.</small></div></section>';
    }
    function bindTuning(){
      const choice=q('#bundleAlternative');if(!choice)return;
      choice.value=items.find(r=>r.preset_id===preset.id&&r.id!==tuning.present.origin)?.id||tuning.present.origin;
      q('#bundleUndo').disabled=!tuning.past.length;q('#bundleRedo').disabled=!tuning.future.length;
      for(const id of ['bundleAlternative','bundleKeepIdea','bundleKeepSeed','bundleKeepCanvas'])q('#'+id).onchange=()=>{pendingProposal=null;q('#bundleProposal').textContent='Choices changed. Review the proposal again.';};
      q('#bundlePropose').onclick=()=>{
        try{
          // Invalid typed text must not be replaced with the last valid snapshot.
          B.resolve(preset,active,overrides);
          const target=atelierRecipes.find(r=>r.id===choice.value);
          pendingProposal=B.proposeTuning(preset,active,tuning,target,knowledge,{keepIdea:q('#bundleKeepIdea').checked,keepSeed:q('#bundleKeepSeed').checked,keepCanvas:q('#bundleKeepCanvas').checked});
          const p=pendingProposal;
          q('#bundleProposal').innerHTML='<h4>'+escape(p.targetName)+'</h4><p>'+escape(p.notice)+'</p><p>'+escape(p.evidence.label)+' for the source recipe. '+escape(p.evidence.detail)+'</p><p>'+escape(p.notes)+'</p><p>'+sources(p.sources)+'</p>'+['Adapter stack','Sampling','Composition','Idea'].map(group=>{const rows=p.changes.filter(c=>c.group===group);return rows.length?'<details open><summary>'+group+' · '+rows.length+' change(s)</summary><dl>'+rows.map(c=>'<dt>'+escape(B.controlLabel(c.key))+'</dt><dd><del>'+escape(c.before??'(unset)')+'</del> → <ins>'+escape(c.after??'(unset)')+'</ins></dd>').join('')+'</dl></details>':'';}).join('')+(p.changes.length?'':'<p>No effective changes.</p>')+'<details><summary>Guidance for this stack</summary>'+p.claims.filter(a=>a.active).map(a=>'<article class="bundle-adapter"><h4>'+escape(a.label)+'</h4><p>'+escape(a.role)+' · '+escape(a.scope)+' · '+escape(a.knowledgeDate||'date unknown')+'</p><p>'+escape(a.range?'Stored source range: '+a.range.join('–'):'No source range recorded.')+'</p><p>'+escape(a.trigger?'Trigger: '+a.trigger+' · '+a.position:'No trigger recorded.')+'</p><p>'+escape(a.note)+'</p><p>'+sources(a.sources)+'</p><p class="bundle-caveat">'+escape(a.verification)+'</p></article>').join('')+'</details><p>Resource availability, timing and memory are not measured by this preview. Sampling settings and the full adapter stack are transferred together.</p>'+p.warnings.map(w=>'<p class="bundle-warning">'+escape(w)+'</p>').join('')+'<label class="bundle-consent"><input type="checkbox" id="bundleProposalConsent"> I reviewed the changes and source conditions.</label><button type="button" id="bundleStage" disabled>Use changes in draft</button>';
          q('#bundleProposalConsent').onchange=()=>q('#bundleStage').disabled=!q('#bundleProposalConsent').checked||!p.changes.length;
          q('#bundleStage').onclick=()=>{
            try{
              if(!pendingProposal||!q('#bundleProposalConsent').checked)return;
              const latest=catalog.presets.find(r=>r.id===preset.id),source=atelierRecipes.find(r=>r.id===active.id),target=atelierRecipes.find(r=>r.id===pendingProposal.targetId);
              tuning=B.acceptTuning(latest,source,tuning,target,knowledge,pendingProposal);
              overrides={...tuning.present.controls};pendingProposal=null;detail();q('#bundleAlternative').focus({preventScroll:true});q('#bundleTuning').scrollIntoView({block:'nearest'});
              status('Setup changed in the draft. Review its settings; Apply to Create is still separate.');
            }catch(error){q('#bundleProposal').textContent=error.message;pendingProposal=null;}
          };
        }catch(error){q('#bundleProposal').textContent=error.message;pendingProposal=null;}
      };
      for(const [id,direction]of [['bundleUndo','undo'],['bundleRedo','redo']])q('#'+id).onclick=()=>{tuning=B.travelTuning(tuning,direction);overrides={...tuning.present.controls};pendingProposal=null;detail();q('#'+id).focus();};
    }
    let workflowModules=null;
    function attachReusableWorkflow(){
      const host=document.createElement('section');host.className='bundle-reusable-host';q('#bundleBody').append(host);
      if(!workflowModules){
        const css=document.createElement('link');css.rel='stylesheet';css.href='/static/bundle-workflow.css';document.head.append(css);
        workflowModules=Promise.all([import('/static/workflow-project-state.js'),import('/static/bundle-workflow-core.js')]).then(()=>import('/static/bundle-workflow.js'));
      }
      const capture=()=>{
        if(!host.isConnected||!inspection?.graph)throw Error('Re-select the bundle and complete resource inspection first.');
        const latest=catalog.presets.find(p=>p.id===preset.id),recipe=atelierRecipes.find(r=>r.id===active.id);
        if(B.canonical({preset:latest,recipe,knowledge:knowledge||null})!==sourceIdentity)throw Error('The catalog changed. Re-select the bundle before saving a workflow.');
        const origin=atelierRecipes.find(r=>r.id===tuning.present.origin);
        if(!origin||B.canonical(origin)!==tuning.present.originSnapshot)throw Error('The staged source recipe changed. Review it again.');
        return JSON.parse(JSON.stringify({preset:latest,recipe:origin,controls:B.resolve(latest,recipe,overrides),graph:inspection.graph}));
      };
      workflowModules.then(()=>{if(host.isConnected)BundleWorkflow.mount(host,capture);}).catch(()=>{if(host.isConnected)host.textContent='Reusable-workflow controls could not load. Reload Studio; the current bundle is unchanged.';});
    }
    const guidanceModule=import('/static/bundle-guidance.js');
    guidanceModule.catch(()=>{});
    let guidancePanel=null;
    function attachGuidance(){
      const host=document.createElement('section');host.id='bundleScopedGuidance';q('#bundleTuning').before(host);
      const capture=()=>{
        if(!inspection?.graph)throw Error('Resource inspection is not available yet.');
        return {preset,controls:B.resolve(preset,active,overrides),graph:inspection.graph};
      };
      guidanceModule.then(module=>{if(host.isConnected&&dialog.open)guidancePanel=module.mount(host,capture);}).catch(()=>{if(host.isConnected)host.textContent='Scoped guidance could not load. Your settings are unchanged.';});
    }
    function detail(){
      guidancePanel?.destroy();guidancePanel=null;
      const effective=B.resolve(preset,active,overrides),e=B.evidence(active),s=record(active.id),adapters=B.adapters(preset,effective,knowledge),canApply=(preset.modality||'image')==='image'&&!preset.reference&&!preset.last_reference&&!preset.reference_slots?.length;
      q('#bundleBody').innerHTML='<div class="bundle-feature"><div><span class="bundle-chip">'+escape(preset.family||active.family||'Recipe')+'</span><h3 tabindex="-1" id="bundleSelectedTitle">'+escape(active.name)+'</h3><p>'+escape(active.notes||preset.description||'')+'</p><p><b>'+e.label+'</b></p><p class="bundle-caveat">'+escape(e.detail||'No execution receipt is attached to this recipe.')+'</p><p>'+sources(active.sources)+'</p></div>'+(s?'<figure><img src="'+escape(s.url)+'" alt="'+escape(s.caption)+'"><figcaption><b>'+s.label+'</b> · '+escape(s.caption)+'<p>'+escape(s.notice)+'</p><p>'+escape(s.review||s.coverage||'')+'</p><small>Prompt '+escape(s.prompt_id)+' · '+escape(s.receipt)+'</small></figcaption></figure>':'<div class="bundle-empty"><b>No documented example yet</b><p>The settings are available; this card does not claim what they will produce.</p></div>')+'</div><p class="bundle-caveat">'+escape(showcaseMessage||'Examples remain historical when you edit. Generated, artistically accepted and licensed are separate states.')+'</p><div class="bundle-facts">'+['steps','cfg','width','height','sampler','scheduler'].filter(k=>effective[k]!=null).map(k=>'<span><small>'+escape(k)+'</small><b>'+escape(effective[k])+'</b></span>').join('')+'</div><details open><summary>What is in this bundle?</summary><div id="bundleIngredients">'+ingredientHtml(effective)+'</div></details><details><summary>What do the adapters do?</summary>'+(adapters.length?adapters.map(a=>'<article class="bundle-adapter"><h4>'+escape(a.label||a.file)+' <small>'+escape(a.role)+'</small></h4><code>'+escape(a.file)+'</code><p>Authored slot '+escape(a.key)+' · '+(a.active?'strength '+escape(a.strength):'off')+'</p><p>'+escape(a.trigger?'Recorded trigger: '+a.trigger+(a.position?' · '+a.position:''):'No trigger recorded; this is not proof that none is needed.')+'</p><p>'+escape(a.note||'Purpose or interactions are not described in the stored entry. Compare one change before stacking more.')+'</p>'+(a.range.length?'<p>Stored source range: '+escape(a.range.join('–'))+' · '+escape(a.family||'family not recorded')+'</p>':'')+(a.sha256?'<details><summary>Recorded file identity</summary><code>'+escape(a.sha256)+'</code><p>Stored SHA-256, not a fresh hash of the installed file.</p></details>':'')+sources(a.sources)+'</article>').join(''):'<p>No editable filename-based adapter slots in this recipe.</p>')+'<p>To replace a checkpoint or adapter file, choose another complete bundle, or use the existing workbench controls. File names and family labels alone do not establish compatibility.</p></details><details><summary>General family notes · not checked against this stack</summary>'+guideHtml()+'</details>'+tuningHtml()+'<details open><summary>Adapt this bundle</summary><p>Keep the recipe intact, or make a deliberate variation. Sampling and accelerator settings may depend on each other; there is no universal quality slider.</p><div class="bundle-edit-fields">'+Object.entries(effective).filter(([k])=>B.editable(preset,k)&&!(k==='lora'&&typeof effective[k]==='string')).map(([k,v])=>field(k,v)).join('')+'</div><button type="button" id="bundleReset">Reset to this bundle</button></details><section class="bundle-review"><h4>Review changes before applying</h4><p id="bundleVariantNotice"></p><div id="bundleDiff"></div><p>Apply replaces the workbench recipe, resets references and sets the batch to <b>one output</b>. The existing draft-recovery mechanism is used. No generation, download or environment switch occurs.</p>'+(!canApply?'<p>This reference or non-image route is inspect-only here. Prepare it in the existing workbench so its inputs and lineage stay explicit.</p>':'')+'<label class="bundle-consent"><input id="bundleConsent" type="checkbox"> Replace the current workbench settings and clear its references.</label><p id="bundleApplyStatus" role="status"></p><button type="button" id="bundleApply" class="primary" '+(!canApply?'disabled':'')+'>Apply to Create →</button></section>';
      q('#bundleApply').dataset.allowed=String(canApply);q('#bundleReset').onclick=()=>{tuning=B.recordTuning(preset,active,tuning,baseline,active.id,tuning.revision,B.canonical(active));overrides={};pendingProposal=null;detail();};q('#bundleApply').onclick=apply;
      q('#bundleBody').querySelectorAll('[data-bundle-control]').forEach(el=>el.addEventListener('input',()=>{overrides[el.dataset.bundleControl]=el.value;pendingProposal=null;q('#bundleProposal').textContent='Draft edited. Review a new setup proposal before staging.';try{tuning=B.recordTuning(preset,active,tuning,B.resolve(preset,active,overrides),tuning.present.origin,tuning.revision);}catch{}q('#bundleConsent').checked=false;review();q('#bundleUndo').disabled=!tuning.past.length;q('#bundleRedo').disabled=!tuning.future.length;}));
      q('#bundleConsent').onchange=review;bindTuning();review();images();if(canApply){attachReusableWorkflow();attachGuidance();}
    }
    function review(){
      guidancePanel?.update();
      try{const controls=B.resolve(preset,active,overrides),changes=B.diff(baseline,controls),current=selected?values():{};
        q('#bundleVariantNotice').textContent=changes.length?'Modified variation · '+changes.length+' change(s) from the bundle. The example is not a preview of these edits.':'Authored controls unchanged. Any historical example still has its own model/runtime provenance.';
        const rows=B.diff(current,controls);q('#bundleDiff').innerHTML='<p>'+escape(selected?.name||'No current recipe')+' → '+escape(active.name)+'</p><details><summary>'+rows.length+' workbench control change(s)</summary><dl>'+rows.map(r=>'<dt>'+escape(B.controlLabel(r.key))+'</dt><dd><del>'+escape(r.before??'(not set)')+'</del><br><ins>'+escape(r.after??'(removed)')+'</ins></dd>').join('')+'</dl></details>';
        q('#bundleIngredients').innerHTML=ingredientHtml(controls);q('#bundleApplyStatus').textContent='';q('#bundleApply').disabled=q('#bundleApply').dataset.allowed!=='true'||!q('#bundleConsent').checked;
      }catch(err){q('#bundleApplyStatus').textContent=err.message;q('#bundleApply').disabled=true;}
    }
    async function choose(id){
      const ticket=++epoch;active=items.find(r=>r.id===id);preset=catalog.presets.find(p=>p.id===active?.preset_id);overrides={};inspection=null;inspectionMessage='Inspecting authored resources…';context=snapshot();sourceIdentity=source();
      try{baseline=B.resolve(preset,active);tuning=B.tuningSession(preset,active);pendingProposal=null;detail();cards();status('');q('#bundleSelectedTitle').focus({preventScroll:true});}catch(err){q('#bundleBody').textContent=err.message;status('This recipe needs a binding review before it can be applied.');return;}
      try{const data=await api('/api/inspect/'+encodeURIComponent(preset.id));if(ticket!==epoch||!dialog.open)return;inspection=data;inspectionMessage='';review();}catch(err){if(ticket!==epoch||!dialog.open)return;inspectionMessage='Resource inspection unavailable: '+err.message;review();}
    }
    function apply(){
      try{
        if(q('#bundleApply').disabled||!q('#bundleConsent').checked)return;
        if(submitting)throw Error('A submission is in progress. Finish it before replacing this workbench.');
        if(snapshot()!==context)throw Error('The workbench changed while this preview was open. Select the bundle again to review a fresh comparison.');
        const latest=catalog.presets.find(p=>p.id===preset.id),recipe=atelierRecipes.find(r=>r.id===active.id);
        if(B.canonical({preset:latest,recipe,knowledge:knowledge||null})!==sourceIdentity)throw Error('The catalog changed. Reopen the explorer before applying.');
        const controls=B.resolve(latest,recipe,overrides);
        // Existing service path, complete defaults, explicit reset. Never call post/create_job/generate.
        const issues=B.transferProblems(latest,controls,typeof installedLoras==='undefined'?[]:installedLoras);if(issues.length)throw Error(issues.join(' '));
        const origin=atelierRecipes.find(r=>r.id===tuning.present.origin);if(!origin||B.canonical(origin)!==tuning.present.originSnapshot)throw Error('The staged source recipe changed. Reopen and review it again.');
        selectPreset(latest.id);applyRecipe(B.tuningHandoff(latest,origin,controls));
        q('#positive').dispatchEvent(new Event('input',{bubbles:true}));
        showView('create');opener=preset.positive?q('#positive'):q('#presetSearch');dialog.close();q('#createView').__workshop?.finishRecipeSelection(opener);opener.focus();message('Bundle applied as an editable setup. Review readiness; Generate is still a separate action.');
      }catch(err){q('#bundleApplyStatus').textContent=err.message;q('#bundleApply').disabled=true;}
    }
    const openBundles=async()=>{
      const opened=++openEpoch;opener=document.activeElement;dialog.showModal();q('#bundleSearch').focus();status('');
      active=null;preset=null;overrides={};inspection=null;showcase={};q('#bundleBody').innerHTML='<p>Choose a bundle to inspect its ingredients and examples.</p>';q('#bundleCards').replaceChildren();
      if(typeof catalog==='undefined'||!catalog?.presets||typeof atelierRecipes==='undefined'||!atelierRecipes.length){status('The recipe catalog is not available yet. Close and reopen after Studio finishes loading.');return;}
      items=atelierRecipes.filter(r=>r&&typeof r.id==='string'&&catalog.presets.some(p=>p.id===r.preset_id));
      q('#bundleFamily').innerHTML='<option value="">All families</option>'+[...new Set(items.map(r=>r.family).filter(Boolean))].sort().map(f=>'<option>'+escape(f)+'</option>').join('');q('#bundleSearch').value='';cards();
      try{const data=(await import('/static/bundle-showcase.js')).default;if(opened!==openEpoch||!dialog.open)return;showcase=data;showcaseMessage='';cards();if(active){const preview=q('#bundleBody .bundle-feature figure, #bundleBody .bundle-empty');const sample=record(active.id);if(preview&&sample){const figure=document.createElement('figure');figure.innerHTML='<img src="'+escape(sample.url)+'" alt="'+escape(sample.caption)+'"><figcaption>'+escape(sample.label+' · '+sample.caption+' '+sample.notice)+'</figcaption>';preview.replaceWith(figure);images();}}}catch{if(opened!==openEpoch||!dialog.open)return;showcaseMessage='Example index unavailable. Recipes remain browsable without previews.';status(showcaseMessage);}
    };
    button.onclick=openBundles;
    function mountHomeLauncher(){
      if(q('#bundleHomeLauncher'))return;
      const heading=q('#homeView .ux-home-heading');if(!heading)return;
      const homeButton=button.cloneNode(true);homeButton.id='bundleHomeLauncher';homeButton.onclick=openBundles;heading.after(homeButton);
    }
    mountHomeLauncher();
    if(!q('#bundleHomeLauncher'))document.addEventListener('studio:setup-draft-ready',mountHomeLauncher,{once:true});
    q('#bundleCards').onclick=e=>{const card=e.target.closest('[data-bundle]');if(card)choose(card.dataset.bundle);};q('#bundleSearch').oninput=cards;q('#bundleFamily').onchange=cards;q('#bundleClose').onclick=()=>dialog.close();
    dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dialog.close();}else if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();e.stopPropagation();}});
    dialog.addEventListener('close',()=>{guidancePanel?.destroy();guidancePanel=null;epoch++;openEpoch++;if(opener?.isConnected)opener.focus();});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
