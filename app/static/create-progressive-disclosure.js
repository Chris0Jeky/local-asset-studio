/* Move standing explanations behind optional, accessible disclosures. */
(function(root,factory){
  const api=factory(root);
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.CreateProgressiveDisclosure=api;
  if(root.document)api.mount(root.document);
})(typeof globalThis!=='undefined'?globalThis:this,function(root){
  'use strict';
  function sync(details,target){
    if(!details||!target)return null;
    details.hidden=!String(target.textContent||'').trim();return details;
  }
  function observe(document,details,target){
    sync(details,target);
    if(details.__createContextObserver)return details.__createContextObserver;
    const Observer=(document.defaultView&&document.defaultView.MutationObserver)||root.MutationObserver;
    if(typeof Observer!=='function')return null;
    const observer=new Observer(function(){sync(details,target);});
    observer.observe(target,{childList:true,subtree:true,characterData:true});
    details.__createContextObserver=observer;return observer;
  }
  function wrap(document,targetId,detailsId,summaryText){
    const target=document.querySelector('#'+targetId);if(!target||!target.parentNode)return null;
    const existing=document.querySelector('#'+detailsId);if(existing){observe(document,existing,target);return existing;}
    const details=document.createElement('details');details.id=detailsId;details.className='create-context-help';
    const summary=document.createElement('summary');summary.textContent=summaryText;
    target.parentNode.insertBefore(details,target);details.append(summary,target);observe(document,details,target);return details;
  }
  function mount(document){
    return {recipe:wrap(document,'recipeNotes','recipeNotesHelp','Why this recipe?'),
            references:wrap(document,'referenceBoardNote','referenceBoardHelp','How are these references used?')};
  }
  return{mount,observe,sync,wrap};
});
