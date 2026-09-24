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
  function place(parent,node,before){
    if(node===before)return;
    // Attach new containers first so retained cards can move between connected parents.
    if(typeof parent.moveBefore==='function' && node.parentNode && node.isConnected===parent.isConnected)parent.moveBefore(node,before);
    else parent.insertBefore(node,before);
  }
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
    let focusId=null,focusRole=null,focusGroup=null,focusAction=null;
    if(state && grid.contains(focused))for(const [key,section] of state.groups)if(section.actions.contains(focused)){focusGroup=key;focusAction=focused.dataset?.groupReview??null;break;}
    if(state && grid.contains(focused) && focusGroup===null){
      for(const [id,row] of state.rows){
        if(!row.node.contains(focused))continue;
        focusId=id;
        focusRole=Object.keys(selectors).find(role=>row.node.querySelector(selectors[role])===focused);
        break;
      }
    }
    // Only this render's current focus can be restored; no request-time focus capture.
    const groups=options.groups?.[0]?.key?options.groups:[{key:'',assets}],grouped=!!groups[0].key;
    const ownedFocus=grid.contains(focused),nextIds=groups.flatMap(group=>group.assets.map(a=>a.id)),wanted=new Set(nextIds);
    if(!sameWorkspace){
      releaseMedia(grid);grid.replaceChildren();
      state={workspace:options.workspaceId,rows:new Map(),groups:new Map(),empty:null};grids.set(grid,state);
    }
    for(const [id,row] of state.rows)if(!wanted.has(id)){
      releaseMedia(row.node);row.node.remove();state.rows.delete(id);
    }
    if(!assets.length){
      state.groups.clear();
      if(state.empty!==options.emptyHTML){
        grid.innerHTML=options.emptyHTML;state.empty=options.emptyHTML;
      }
    }else{
      if(state.empty!==null){grid.replaceChildren();state.empty=null;}
      const ordered=new Map(),sections=new Map();let cursor=grid.firstElementChild;
      // Finish section ordering before moving any cards: a former flat card may be the cursor.
      if(grouped)for(const group of groups){
        let section=state.groups.get(group.key);
        if(!section){
          const node=doc.createElement('section'),heading=doc.createElement('h4'),label=doc.createTextNode(''),count=doc.createElement('small'),actions=doc.createElement('div'),items=doc.createElement('div');
          node.className='asset-group';items.className='asset-group-items';actions.className='asset-group-actions';actions.hidden=true;
          // The heading is a programmatic focus target for when a group's own actions disappear.
          heading.tabIndex=-1;heading.append(label,count);node.append(heading,actions,items);section={node,heading,label,count,actions,actionsHTML:'',items};
        }
        // Group actions are caller-escaped markup, replaced only when it changes so a focused control survives.
        const actionsHTML=options.groupActionsHTML?.(group)||'';
        if(section.actionsHTML!==actionsHTML){section.actions.innerHTML=actionsHTML;section.actionsHTML=actionsHTML;section.actions.hidden=!actionsHTML;}
        if(section.label.nodeValue!==group.label)section.label.nodeValue=group.label;
        if(section.count.textContent!==String(group.assets.length))section.count.textContent=group.assets.length;
        place(grid,section.node,cursor);cursor=section.node.nextElementSibling;sections.set(group.key,section);
      }
      for(const group of groups){
        const parent=grouped?sections.get(group.key).items:grid;let rowCursor=parent.firstElementChild;
        for(const asset of group.assets){
          const selected=options.selected.has(asset.id);let row=state.rows.get(asset.id);
          if(!row){
            const node=cardFromHTML(grid,options.cardHTML(asset));node.dataset.assetId=asset.id;
            row={node,signature:displayKey(asset,selected),media:mediaKey(asset)};
          }else update(row,asset,selected,options,grid);
          place(parent,row.node,rowCursor);rowCursor=row.node.nextElementSibling;ordered.set(asset.id,row);
        }
      }
      // Retained cards have left obsolete containers; removing them now cannot discard those cards.
      for(const [key,section] of state.groups)if(!sections.has(key))section.node.remove();
      state.rows=ordered;state.groups=sections;
    }
    if(ownedFocus && (!focused.isConnected || doc.activeElement!==focused)){
      let target=null;
      if(sameWorkspace && focusGroup!==null){
        const section=state.groups.get(focusGroup);
        target=section?[...section.actions.querySelectorAll('[data-group-review]')].find(b=>b.dataset.groupReview===focusAction)||section.heading:null;
      }else if(sameWorkspace && focusRole){
        const id=nextFocus(previous,nextIds,focusId);
        target=state.rows.get(id)?.node.querySelector(selectors[focusRole]);
      }else if(sameWorkspace && focused.isConnected)target=focused;
      (target||options.focusFallback)?.focus({preventScroll:true});
    }
  }
  return {render,mediaKey,displayKey,nextFocus};
});

// The editor is a separate browser module; Node projection tests stay side-effect free.
if(typeof document!=='undefined'){
  const load=()=>{
    if(document.querySelector('script[data-addressable-figures]'))return;
    const script=document.createElement('script');script.src='/static/addressable-figures.js';script.async=false;script.dataset.addressableFigures='';
    (document.head||document.documentElement).append(script);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
}
