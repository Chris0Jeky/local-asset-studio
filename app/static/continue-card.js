/* Explicit, read-only Make recap. Library, Production and Scene editor own navigation. */
(function(){
  'use strict';
  const card=document.querySelector('#makeContinue');if(!card)return;
  const result=card.querySelector('[data-continue-result]'),refresh=card.querySelector('[data-continue-refresh]');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const context=()=>({workspace:assetState.workspace_id,epoch:assetWorkspaceEpoch,...StudioPrivacy.capture()});
  const same=c=>c.workspace===assetState.workspace_id&&c.epoch===assetWorkspaceEpoch&&c.revision===StudioPrivacy.capture().revision;
  const date=value=>typeof value==='number'&&Number.isFinite(value)&&!Number.isNaN(new Date(value*1000).getTime())?'Created '+new Date(value*1000).toLocaleString():'Created date unavailable';
  const revision=(value,max=500)=>Number.isInteger(value)&&value>=0&&value<=max;
  const status=value=>typeof value==='string'&&value.length>0&&value.length<=40;
  let serial=0,shown=null;
  function clear(){serial++;shown=null;result.textContent='Expand Continue to read existing work.';refresh.disabled=false;card.open=false;}
  async function load(){
    const request=++serial,privacy=StudioPrivacy.capture().revision;shown=null;refresh.disabled=true;result.textContent='Reading existing work…';
    try{
      if(!assetState.workspace_id)await refreshAssets();
      if(request!==serial||privacy!==StudioPrivacy.capture().revision)return;
      const captured=context();if(!/^[0-9a-f]{32}$/.test(captured.workspace||''))throw Error('Workspace unavailable');
      const data=await api('/api/workspace/continue?workspace_id='+encodeURIComponent(captured.workspace),{headers:{'X-Studio-Privacy':captured.scope}});
      if(request!==serial||!same(captured))return;
      if(data.workspace_id!==captured.workspace||data.scope!==captured.scope)throw Error('Observation belongs to another view');
      shown={data,captured,request};
      const kept=data.kept,asset=kept?.asset,native=data.native,plan=native?.plan,scene=data.scene,saved=scene?.plan;
      const assetValid=kept?.state==='ready'&&/^[A-Za-z0-9_-]{1,128}$/.test(asset?.id||'')&&StudioPrivacy.allows(asset,captured.scope);
      const planValid=native?.state==='ready'&&captured.scope!=='private'&&native.scope==='regular'&&/^[0-9a-f]{32}$/.test(plan?.id||'');
      const sceneValid=scene?.state==='ready'&&captured.scope!=='private'&&scene.scope==='regular'&&/^[0-9a-f]{32}$/.test(saved?.id||'')
        &&revision(saved.revision)&&status(saved.status)&&(saved.render===null||(revision(saved.render?.revision,saved.revision)&&status(saved.render?.status)))
        &&(saved.completed_revision===null||revision(saved.completed_revision,saved.revision));
      result.innerHTML='<div class="make-continue-grid"><section><h3>Newest kept picture</h3>'+(assetValid?'<button type="button" data-continue-asset>'+escape(asset.title||'Open picture')+'</button><p>'+escape(date(asset.created_at))+'</p>':'<p>'+(kept?.state==='empty'?'No kept pictures in this view.':'Kept picture unavailable. Refresh to try again.')+'</p>')
        +'</section><section><h3>Needs work</h3><button type="button" data-continue-needs>Open Needs work in Library</button><p>Your existing review marks in this privacy view.</p></section><section><h3>Newest native export</h3>'
        +(planValid?'<a href="/?plan='+plan.id+'#production" target="_blank" rel="noreferrer" data-continue-plan>'+escape(plan.name||'Open plan')+' ↗</a><p>'+escape(date(plan.created_at))+' · Recorded state: '+escape(plan.status)+'</p>'
          :'<p>'+(captured.scope==='private'?'Native exports are Regular-only and are not read in Private.':native?.state==='empty'?'No eligible native-export plans.':native?.state==='incomplete'?'Latest export not established within the bounded history window.':'Native-export history unavailable. A saved record or its sources could not be verified.')+'</p>')
        +(captured.scope==='all'?'<p>Exports here are Regular-only.</p>':'')+'</section><section><h3>Newest scene</h3>'
        +(sceneValid?'<a href="/av.html?project='+saved.id+'" target="_blank" rel="noreferrer" data-continue-scene>'+escape(saved.name||'Open scene')+'</a><p>Opens Scene editor in a new tab.</p><p>'+escape(date(saved.created_at))+' · Saved revision '+saved.revision+'</p><p>Recorded state: '+escape(saved.status)+'</p>'
          +'<p>'+(saved.render?'Latest recorded render: '+escape(saved.render.status)+' · revision '+saved.render.revision+'.':'No render attempt recorded.')+'</p>'
          +(saved.completed_revision!==null?'<p>Last completed render: revision '+saved.completed_revision+(saved.completed_revision<saved.revision?' (older than saved revision '+saved.revision+')':'')+'.</p>':'')
          :'<p>'+(captured.scope==='private'?'Scenes are Regular-only and are not read in Private.':scene?.state==='empty'?'No eligible saved scenes.':scene?.state==='incomplete'?'Latest scene not established within the bounded history window.':'Saved-scene history unavailable. Its retained records or sources could not be verified.')+'</p>')
        +(captured.scope==='all'?'<p>Scenes here are Regular-only.</p>':'')+'</section></div><p class="make-continue-note">Newest by creation date. Recorded states do not establish acceptance or available output files.</p>';
    }catch{if(request===serial)result.textContent='Continue is unavailable. Refresh the Library, then try again.';}
    finally{if(request===serial)refresh.disabled=false;}
  }
  card.addEventListener('toggle',()=>{if(card.open)void load();else{serial++;shown=null;result.textContent='';refresh.disabled=false;}});
  refresh.addEventListener('click',()=>void load());
  card.addEventListener('click',async event=>{
    const asset=event.target.closest('[data-continue-asset]'),needs=event.target.closest('[data-continue-needs]'),plan=event.target.closest('[data-continue-plan]'),scene=event.target.closest('[data-continue-scene]');
    if(!asset&&!needs&&!plan&&!scene)return;
    const observation=shown,owns=()=>shown===observation&&observation?.request===serial&&same(observation.captured);
    if(!owns()){event.preventDefault();clear();return;}
    if(plan||scene)return; // A separate tab preserves unsaved Make and Library drafts.
    event.preventDefault();
    if(needs){if(!assetDetailCanLeave())return;document.dispatchEvent(new CustomEvent('studio:continue-needs'));return;}
    const detailEpoch=assetDetailEpoch,draft=document.querySelector('#assetDialog').open?JSON.stringify(assetDetailValues()):null;
    try{
      await refreshAssets();
      if(!owns()||detailEpoch!==assetDetailEpoch||draft!==(document.querySelector('#assetDialog').open?JSON.stringify(assetDetailValues()):null))return;
      await openAsset(observation.data.kept.asset.id,owns);
    }catch{if(owns())result.textContent='This picture is unavailable. Refresh Continue to check it.';}
  });
  document.addEventListener('studio:privacy-change',clear);
  document.addEventListener('studio:workspace-change',event=>{if(event.detail.previous!==undefined||shown)clear();});
})();
