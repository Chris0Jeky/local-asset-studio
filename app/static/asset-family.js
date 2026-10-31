/* Family views observe existing records; recall applies only through the existing workbench adapter. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioAssetFamily=api;
})(globalThis,function(){
  'use strict';
  const ID=/^[A-Za-z0-9_-]{1,128}$/,SCOPE=/^[0-9a-f]{32}$/,HASH=/^[0-9a-f]{64}$/;
  const need=(ok,text)=>{if(!ok)throw Error(text);};
  const identity=value=>typeof value==='string'&&ID.test(value);
  const text=(value,max)=>typeof value==='string'&&value.length<=max;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function node(value){return value&&identity(value.id)&&['active','trashed','missing'].includes(value.state)&&text(value.title,400)&&
    (value.operation===null||text(value.operation,400))&&(value.seed===null||text(value.seed,80))&&(value.strength===null||text(value.strength,80));}
  function validate(value,id,scope){
    need(value?.version===1&&value.asset_id===id&&value.workspace_id===scope&&Array.isArray(value.nodes)&&value.nodes.length<=64&&value.nodes.every(node)&&value.nodes.some(n=>n.id===id)&&
      new Set(value.nodes.map(n=>n.id)).size===value.nodes.length&&Array.isArray(value.edges)&&value.edges.length<=128&&value.edges.every(e=>e&&identity(e.parent)&&identity(e.child))&&
      Array.isArray(value.gaps)&&value.gaps.length<=64&&value.gaps.every(g=>g&&identity(g.id)&&['cycle','depth','size','invalid-lineage'].includes(g.reason))&&typeof value.truncated==='boolean'&&
      (value.children===null||Array.isArray(value.children)&&value.children.length<=20&&value.children.every(node))&&typeof value.children_truncated==='boolean'&&Number.isInteger(value.children_scanned)&&value.children_scanned>=0&&value.children_scanned<=5000&&
      value.observation_only===true&&value.generation_submitted===false&&value.media_bytes_verified===false, 'Invalid bounded family response or identity');
    return value;
  }
  function treeMarkup(report){
    return '<ol class="asset-family-strip">'+report.nodes.map(n=>{
      const label='<b>'+esc(n.title)+'</b><small>'+esc(n.operation||'Operation not recorded')+(n.seed===null?'':' · Seed '+esc(n.seed))+(n.strength===null?'':' · Strength '+esc(n.strength))+'</small>';
      const parents=report.edges.filter(e=>e.child===n.id).map(e=>e.parent);
      return '<li data-family-step="'+esc(n.id)+'">'+(n.state==='missing'?'<span class="asset-family-gap">'+label+'</span>':'<button type="button" data-family-open="'+esc(n.id)+'"'+(n.id===report.asset_id?' aria-current="step"':'')+'>'+label+(n.state==='trashed'?'<small>In Trash · original step retained</small>':'')+'</button>')+
        (parents.length>1?'<small>Sources: '+parents.map(id=>esc(report.nodes.find(n=>n.id===id)?.title||id)).join('; ')+'</small>':'')+'</li>';
    }).join('')+'</ol>'+report.gaps.map(g=>'<p class="asset-family-gap">'+esc(g.reason==='cycle'?'Circular lineage stopped at ':g.reason==='invalid-lineage'?'Unreadable lineage at ':'Earlier history folded before ')+esc(g.id)+'</p>').join('')+
      (report.truncated?'<p>History is bounded to 12 levels and 64 assets. Open an older visible step to continue exploring.</p>':'');
  }
  function newSeed(original,random=()=>crypto.getRandomValues(new Uint32Array(1))[0]){
    need(typeof original==='string'&&/^[0-9]{1,20}$/.test(original)&&BigInt(original)<=18446744073709551615n,'Invalid recorded seed');
    const value=random();need(Number.isInteger(value)&&value>=0&&value<=4294967295,'A new seed could not be prepared');
    return String(BigInt(original)===BigInt(value)?(value+1)%4294967296:value);
  }
  function directSources(report,id,scope){
    validate(report,id,scope);
    need(!report.truncated&&!report.gaps.length,'Family evidence is incomplete. Source comparison is unavailable.');
    const ids=report.edges.filter(e=>e.child===id).map(e=>e.parent);
    need(new Set(ids).size===ids.length&&ids.every(parent=>parent!==id&&report.nodes.some(n=>n.id===parent)),'Recorded sources are ambiguous or unavailable.');
    return ids.map(parent=>report.nodes.find(n=>n.id===parent));
  }
  function createComparison(options){
    let epoch=0;
    const cancel=()=>{epoch++;};
    async function choose(report,parent){
      const child=options.asset(),context=options.context(),stamp=JSON.stringify(context),serial=++epoch;
      need(child&&identity(child.id)&&HASH.test(child.sha256),'The current picture is unavailable.');
      const id=child.id,sha=child.sha256,privacy=child.privacy===undefined?'regular':child.privacy;
      const source=directSources(report,id,context.workspace).find(n=>n.id===parent);
      need(source,'Choose a recorded direct source.');
      need(source.state==='active','This recorded source is missing or in Trash.');
      const current=()=>serial===epoch&&JSON.stringify(options.context())===stamp&&options.asset()?.id===id&&options.asset()?.sha256===sha;
      try{
        const resolved=await options.resolve([id,parent]);
        if(!current())return null;
        need(resolved!==false,'The Library changed while reading the pictures. Choose the source again.');
        const image=(key)=>{
          const a=options.lookup(key),classification=a?.privacy===undefined?'regular':a.privacy;
          need(a&&a.id===key&&a.workspace_id===context.workspace&&a.media_type==='image'&&a.trashed_at==null,'A comparison picture is missing, in Trash or is not an image.');
          need(['regular','private'].includes(privacy)&&classification===privacy,'The source and current picture must have the same privacy.');
          need(HASH.test(a.sha256)&&a.url==='/api/assets/'+encodeURIComponent(key)+'/file'+(privacy==='private'?'?privacy=private':''),'Recorded image media is unavailable.');
          return {...a};
        };
        const now=image(id),original=image(parent);
        need(now.sha256===sha,'The current picture changed. Reopen it before comparing.');
        return {child:now,source:original,current};
      }catch(error){if(!current())return null;throw error;}
    }
    return {choose,cancel};
  }
  function createRecall(options){
    let epoch=0,busy=false,abort=null;
    function cancel(){epoch++;abort?.abort();abort=null;busy=false;}
    async function prepare(id,mode){
      need(identity(id)&&['new','words'].includes(mode),'Unknown asset recall identity or mode');
      need(!busy,'A recipe recall is already being checked');
      const initial=options.context(id);need(typeof initial.workspace==='string'&&SCOPE.test(initial.workspace),'Workspace identity is unavailable');
      const serial=++epoch,own=new AbortController();abort=own;busy=true;
      const current=()=>{const now=options.context(id);return serial===epoch&&now.workspace===initial.workspace&&now.stamp===initial.stamp;};
      const timer=setTimeout(()=>own.abort(),15000);
      try{
        const result=await options.read('/api/assets/recall/'+encodeURIComponent(id)+'?workspace_id='+initial.workspace,{signal:own.signal});
        need(current(),'The asset or workbench changed. Your current work was kept');
        need(result?.version===1&&result.asset_id===id&&result.workspace_id===initial.workspace&&result.observation_only===true&&result.generation_submitted===false&&result.media_bytes_verified===false&&
          result.recipe&&typeof result.recipe==='object'&&!Array.isArray(result.recipe)&&result.controls&&typeof result.controls==='object'&&!Array.isArray(result.controls), 'Recall identity or evidence is invalid');
        const seed=result.controls.seed;need(typeof seed==='string'&&/^[0-9]{1,20}$/.test(seed)&&BigInt(seed)<=18446744073709551615n,'The output has no valid recorded seed');
        const check=await options.check(result.recipe,own.signal);
        need(current(),'The asset or workbench changed. Your current work was kept');
        need(check?.matches===true&&typeof check.template_sha256==='string'&&HASH.test(check.template_sha256),'The retained recipe did not validate against the current preset');
        // A declined or auto-dismissed confirm is an answer, not a silent no-op: say what did not change.
        if(!options.confirm('Replace the Create setup with this output’s recorded recipe, '+(mode==='new'?'a new seed':'its recorded seed and editable wording')+'? This prepares one output. Nothing will be generated.')){
          options.say?.('Not prepared: the confirmation was declined. Create was not changed; nothing was generated.');return false;}
        need(current(),'The asset or workbench changed. Your current work was kept');
        const prepared={...result,controls:{...result.controls,seed:mode==='new'?newSeed(seed,options.random):seed}};
        options.apply(prepared,check,mode);return true;
      }finally{clearTimeout(timer);if(serial===epoch){busy=false;abort=null;}}
    }
    return {prepare,cancel};
  }
  function install(options){
    const d=options.document||document,q=s=>d.querySelector(s),dialog=q('#assetDialog');if(!dialog)return null;
    const panel=d.createElement('section');panel.id='assetFamily';panel.className='asset-family';q('#assetLineage').after(panel);
    const comparisonPanel=d.createElement('section');comparisonPanel.id='assetSourceComparison';comparisonPanel.className='asset-source-comparison';comparisonPanel.hidden=true;q('#assetDetailMedia').before(comparisonPanel);
    let epoch=0,controller=null,currentId=null,comparisonReport=null,comparisonScope=null;
    const button=(label,attribute,value)=>{const b=d.createElement('button');b.type='button';b.textContent=label;b.dataset[attribute]=value;return b;};
    function say(message,error=false){const line=q('#assetFamilyStatus');if(line){line.textContent=message;line.classList.toggle('error',error);}options.say(message,error);}
    // The status line and next-step buttons sit above the form, where the picture's actions are; the family strip stays below.
    const recall=createRecall({...options,context:id=>options.context(id),say});
    const comparison=createComparison({...options,context:options.comparisonContext});
    function clearComparison(focus=false){
      const current=dialog.open&&comparisonScope===JSON.stringify(options.comparisonContext());
      comparison.cancel();comparisonPanel.replaceChildren();comparisonPanel.hidden=true;dialog.classList.remove('asset-source-mode');
      if(focus&&current)q('#assetCompareSource')?.focus();
    }
    function showComparison(){
      need(comparisonReport&&comparisonScope===JSON.stringify(options.comparisonContext()),'The picture or Library changed. Reopen its details to compare.');
      const sources=directSources(comparisonReport,currentId,options.comparisonContext().workspace);
      clearComparison();comparisonPanel.hidden=false;dialog.classList.add('asset-source-mode');
      comparisonPanel.innerHTML='<div class="asset-source-heading"><h3 id="assetSourceTitle" tabindex="-1">Compare with source</h3><button type="button" data-family-compare-close>Close comparison</button></div><p>Choose a recorded direct source. Review and Save below still apply to the current version only.</p><div class="asset-source-choices" role="group" aria-label="Recorded direct sources"></div><p id="assetSourceStatus" role="status" aria-live="polite">No source chosen.</p><div id="assetSourceImages" class="asset-source-images"></div>';
      comparisonPanel.setAttribute('aria-labelledby','assetSourceTitle');
      for(const source of sources){const b=button(source.title+(source.state==='active'?'':source.state==='trashed'?' · In Trash':' · Unavailable'),'familySource',source.id);b.disabled=source.state!=='active';b.setAttribute('aria-pressed','false');q('.asset-source-choices').append(b);}
      q('#assetSourceTitle').focus();
    }
    async function chooseSource(parent){
      q('#assetSourceImages').replaceChildren();q('#assetSourceStatus').textContent='Reading the recorded pictures…';
      for(const b of comparisonPanel.querySelectorAll('[data-family-source]'))b.setAttribute('aria-pressed',String(b.dataset.familySource===parent));
      const pair=await comparison.choose(comparisonReport,parent);if(!pair)return;
      const box=q('#assetSourceImages'),line=q('#assetSourceStatus');
      const current=()=>pair.current()&&dialog.open&&!comparisonPanel.hidden&&box===q('#assetSourceImages');
      if(!current())return;
      line.textContent='Saved pictures, shown without alignment. Keep, Needs work, Not this and Save apply only to the current version.';
      const sizes=[];
      for(const [index,a,label] of [[0,pair.child,'Current version'],[1,pair.source,'Recorded source']]){
        const figure=d.createElement('figure'),image=d.createElement('img'),caption=d.createElement('figcaption'),size=d.createElement('small');
        caption.textContent=label+' · '+a.title;image.alt=label+': '+a.title;image.decoding='async';
        image.addEventListener('load',()=>{if(!current())return;sizes[index]=image.naturalWidth+' × '+image.naturalHeight;size.textContent=sizes[index]+' px';if(sizes.length===2&&sizes[0]&&sizes[1]&&sizes[0]!==sizes[1])line.textContent='Different image dimensions. Both fit the same display size; they are not pixel-aligned. Review and Save apply only to the current version.';});
        image.addEventListener('error',()=>{if(!current())return;comparison.cancel();box.replaceChildren();line.textContent='A picture could not be loaded. Nothing was changed. Choose a source again to retry.';});
        figure.append(image,caption,size);box.append(figure);image.src=a.url;
      }
    }
    function clear(){epoch++;controller?.abort();controller=null;recall.cancel();clearComparison();comparisonReport=null;comparisonScope=null;currentId=null;panel.replaceChildren();q('#assetLineage').hidden=false;
      q('#assetFamilyActions')?.replaceChildren();const line=q('#assetFamilyStatus');if(line){line.textContent='';line.classList.remove('error');}}
    function actions(id){const box=d.createElement('div');box.className='asset-family-actions';box.append(button('Same recipe, new seed','familyRecall','new'),button('Same seed, edit words','familyRecall','words'),button('Use as reference','familyReference',id));
      if(options.asset()?.media_type==='image'){const b=button('Compare with source','familyCompare',id);b.id='assetCompareSource';b.disabled=true;box.append(b);}return box;}
    async function opened(){
      const asset=options.asset();if(!dialog.open||!asset)return;
      clear();currentId=asset.id;const serial=epoch,scope=options.context(asset.id).workspace,observed=JSON.stringify(options.comparisonContext()),own=new AbortController();controller=own;
      panel.innerHTML='<h3>Family &amp; reuse</h3><div id="assetFamilyTree"></div><div id="assetFamilyChildren"></div>';
      q('#assetFamilyActions')?.replaceChildren(actions(asset.id));
      const status=q('#assetFamilyStatus');if(status)status.textContent='Reading the recorded family…';
      const children=button('Show children','familyChildren',asset.id);panel.querySelector('#assetFamilyChildren').before(children);
      const timer=setTimeout(()=>own.abort(),15000);
      try{
        const report=validate(await options.read('/api/assets/family/'+asset.id+'?workspace_id='+scope,{signal:own.signal}),asset.id,scope);
        if(serial!==epoch||!dialog.open||options.context(asset.id).workspace!==scope||observed!==JSON.stringify(options.comparisonContext()))return;
        q('#assetFamilyTree').innerHTML=treeMarkup(report);q('#assetLineage').hidden=true;
        q('#assetFamilyStatus').textContent='Recorded steps, oldest first. Missing or put-away steps stay visible. No generation submitted.';
        if(q('#assetCompareSource'))try{
          const sources=directSources(report,asset.id,scope);need(sources.length,'No recorded direct source is available for comparison.');
          comparisonReport=report;comparisonScope=observed;q('#assetCompareSource').disabled=false;
        }catch(error){q('#assetFamilyStatus').textContent+=' '+error.message;}
      }catch(e){if(serial===epoch&&dialog.open)say('Family unavailable: '+e.message,true);}
      finally{clearTimeout(timer);if(serial===epoch)controller=null;}
    }
    // The recall and reference buttons live above the form (#assetFamilyActions), outside the panel, so one handler serves both.
    const onClick=async event=>{
      const b=event.target.closest('button');if(!b||b.disabled)return;const actionEpoch=epoch;
      try{
        if(b.dataset.familyCompare){showComparison();return;}
        if(b.hasAttribute('data-family-compare-close')){clearComparison(true);return;}
        if(b.dataset.familySource){try{await chooseSource(b.dataset.familySource);}catch(error){if(actionEpoch===epoch&&!comparisonPanel.hidden){q('#assetSourceImages').replaceChildren();q('#assetSourceStatus').textContent=error.message;}}return;}
        if(b.dataset.familyOpen){options.open(b.dataset.familyOpen);return;}
        if(b.dataset.familyRecall){await recall.prepare(currentId,b.dataset.familyRecall);return;}
        if(b.dataset.familyReference){await options.reference(b.dataset.familyReference);return;}
        if(b.dataset.familyChildren){
          const id=currentId,serial=epoch,scope=options.context(id).workspace;b.disabled=true;b.setAttribute('aria-busy','true');
          try{
            const report=validate(await options.read('/api/assets/family/'+id+'?workspace_id='+scope+'&children=true',{signal:AbortSignal.timeout(15000)}),id,scope);
            if(serial!==epoch||!dialog.open||options.context(id).workspace!==scope)return;
            need(Array.isArray(report.children),'Child results are unavailable');
            const box=q('#assetFamilyChildren');box.innerHTML='<h4>Child assets</h4>'+(report.children.length?report.children.map(n=>'<button type="button" data-family-open="'+esc(n.id)+'">'+esc(n.title)+(n.state==='trashed'?' · In Trash':'')+'</button>').join(''):'<p>No child assets found.</p>')+
              (report.children_truncated?'<p>Child search is limited: at most 20 results among the newest 5,000 assets; unreadable lineage is omitted.</p>':'');
          }finally{if(b.isConnected){b.disabled=false;b.removeAttribute('aria-busy');}}
        }
      }catch(e){if(actionEpoch===epoch&&dialog.open)say(e.message,true);}
    };
    panel.addEventListener('click',onClick);comparisonPanel.addEventListener('click',onClick);q('#assetFamilyActions')?.addEventListener('click',onClick);
    dialog.addEventListener('close',()=>{if(!dialog.open)clear();});
    function decorateResults(){
      for(const card of d.querySelectorAll('#gallery .imageCard')){
        if(card.querySelector('.asset-family-result'))continue;
        const id=card.querySelector('[data-review-asset]')?.dataset.reviewAsset;if(!identity(id))continue;
        const box=d.createElement('details');box.className='asset-family-result';box.dataset.asset=id;
        const summary=d.createElement('summary');summary.textContent='Family & reuse';box.append(summary);
        const content=d.createElement('div');box.append(content);card.append(box);
        box.addEventListener('toggle',async()=>{
          if(!box.open)return;
          const scope=options.context(id).workspace;if(box.dataset.loaded&&box.dataset.scope===scope)return;
          box.dataset.scope=scope;box.dataset.loaded='loading';content.textContent='Reading the recorded family…';
          try{
            const report=validate(await options.read('/api/assets/family/'+id+'?workspace_id='+scope,{signal:AbortSignal.timeout(15000)}),id,scope);
            if(!box.isConnected)return;
            if(options.context(id).workspace!==scope){content.textContent='Workspace changed; close and reopen this family.';delete box.dataset.loaded;return;}
            content.innerHTML=treeMarkup(report);content.append(button('Open asset and recall options','familyOpen',id));box.dataset.loaded='true';
          }catch(e){if(box.isConnected){content.textContent='Family unavailable: '+e.message;delete box.dataset.loaded;}}
        });
        box.addEventListener('click',e=>{const b=e.target.closest('[data-family-open]');if(b){e.preventDefault();options.open(b.dataset.familyOpen);}});
      }
    }
    return {opened,decorateResults,clear,recall};
  }
  return {validate,treeMarkup,newSeed,directSources,createComparison,createRecall,install};
});
