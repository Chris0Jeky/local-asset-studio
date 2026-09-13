/* A transient DOM projection. Workspace and assetSelection remain the data owners. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object' && module.exports)module.exports=api;
  else root.StudioAssetGrid=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const grids=new WeakMap();
  const selectors={check:'[data-asset-check]',favorite:'.asset-star',title:'.asset-card-title',preview:'.asset-open'};
  function mediaKey(asset){return JSON.stringify([asset.media_type,asset.url,asset.sha256]);}
  function displayKey(asset,selected){return JSON.stringify([mediaKey(asset),asset.title,asset.preset_name,asset.review,!!asset.favorite,asset.tags.slice(0,4),selected]);}
  function nextFocus(previous,current,removed){
    const available=new Set(current),index=previous.indexOf(removed);
    if(available.has(removed))return removed;
    for(let i=index+1;i<previous.length;i++)if(available.has(previous[i]))return previous[i];
    for(let i=index-1;i>=0;i--)if(available.has(previous[i]))return previous[i];
    return current[0]??null;
  }
  function releaseMedia(node){
    for(const media of node.querySelectorAll('video,audio')){
      media.pause();media.removeAttribute('src');
      for(const source of media.querySelectorAll('source'))source.removeAttribute('src');
      media.load();
    }
    for(const image of node.querySelectorAll('img'))image.removeAttribute('src');
  }
  function cardFromHTML(grid,html){
    const template=grid.ownerDocument.createElement('template');template.innerHTML=html;
    return template.content.firstElementChild;
  }
  function copyHTML(target,source){if(target.innerHTML!==source.innerHTML)target.innerHTML=source.innerHTML;}
  function update(row,asset,selected,options,grid){
    // Checkbox events update DOM directly; a matching old render key alone
    // cannot tell whether Clear selection must undo that intervening state.
    const checkbox=row.node.querySelector(selectors.check);
    if(checkbox.checked!==selected)checkbox.checked=selected;
    if(row.node.classList.contains('is-selected')!==selected)row.node.classList.toggle('is-selected',selected);
    const signature=displayKey(asset,selected);
    if(row.signature===signature)return;
    const fresh=cardFromHTML(grid,options.cardHTML(asset)),node=row.node;
    node.className=fresh.className;
    const preview=node.querySelector(selectors.preview),freshPreview=fresh.querySelector(selectors.preview);
    preview.setAttribute('aria-label',freshPreview.getAttribute('aria-label'));
    const key=mediaKey(asset);
    if(row.media!==key){releaseMedia(preview);preview.innerHTML=freshPreview.innerHTML;}
    else{
      // Labels are mutable metadata, not part of source identity.
      for(const image of preview.querySelectorAll('img'))image.alt=asset.title;
      for(const video of preview.querySelectorAll('video'))video.setAttribute('aria-label',asset.title);
    }
    for(const selector of [selectors.check,selectors.favorite]){
      const target=node.querySelector(selector),source=fresh.querySelector(selector);
      target.setAttribute('aria-label',source.getAttribute('aria-label'));
      if(selector===selectors.check)target.checked=selected;
      else {target.className=source.className;target.textContent=source.textContent;}
    }
    node.querySelector(selectors.title).textContent=asset.title;
    node.querySelector('.asset-kind').textContent=asset.media_type;
    for(const selector of ['.asset-card-meta','.asset-tags'])copyHTML(node.querySelector(selector),fresh.querySelector(selector));
    row.signature=signature;row.media=key;
  }
  function render(grid,assets,options){
    const doc=grid.ownerDocument,focused=doc.activeElement;
    let state=grids.get(grid);
    const previous=state?[...state.rows.keys()]:[],sameWorkspace=!!state && state.workspace===options.workspaceId;
    let focusId=null,focusRole=null;
    if(state && grid.contains(focused)){
      for(const [id,row] of state.rows){
        if(!row.node.contains(focused))continue;
        focusId=id;
        focusRole=Object.keys(selectors).find(role=>row.node.querySelector(selectors[role])===focused);
        break;
      }
    }
    // Only this render's current focus can be restored; no request-time focus capture.
    const ownedFocus=grid.contains(focused),nextIds=assets.map(a=>a.id),wanted=new Set(nextIds);
    if(!sameWorkspace){
      releaseMedia(grid);grid.replaceChildren();
      state={workspace:options.workspaceId,rows:new Map(),empty:null};grids.set(grid,state);
    }
    for(const [id,row] of state.rows)if(!wanted.has(id)){
      releaseMedia(row.node);row.node.remove();state.rows.delete(id);
    }
    if(!assets.length){
      if(state.empty!==options.emptyHTML){
        grid.innerHTML=options.emptyHTML;state.empty=options.emptyHTML;
      }
    }else{
      if(state.empty!==null){grid.replaceChildren();state.empty=null;}
      const ordered=new Map();let cursor=grid.firstElementChild;
      for(const asset of assets){
        const selected=options.selected.has(asset.id);let row=state.rows.get(asset.id);
        if(!row){
          const node=cardFromHTML(grid,options.cardHTML(asset));node.dataset.assetId=asset.id;
          row={node,signature:displayKey(asset,selected),media:mediaKey(asset)};
        }else update(row,asset,selected,options,grid);
        if(row.node!==cursor){
          // moveBefore preserves focus/media state in supporting browsers. The
          // standard insertion fallback is paired with narrowly scoped focus recovery.
          if(typeof grid.moveBefore==='function' && row.node.parentNode===grid)grid.moveBefore(row.node,cursor);
          else grid.insertBefore(row.node,cursor);
        }
        cursor=row.node.nextElementSibling;ordered.set(asset.id,row);
      }
      state.rows=ordered;
    }
    if(ownedFocus && (!focused.isConnected || doc.activeElement!==focused)){
      let target=null;
      if(sameWorkspace && focusRole){
        const id=nextFocus(previous,nextIds,focusId);
        target=state.rows.get(id)?.node.querySelector(selectors[focusRole]);
      }else if(sameWorkspace && focused.isConnected)target=focused;
      (target||options.focusFallback)?.focus({preventScroll:true});
    }
  }
  return {render,mediaKey,displayKey,nextFocus};
});
