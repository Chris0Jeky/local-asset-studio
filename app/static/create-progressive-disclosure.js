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
  function wildcards(document){
    const host=document.querySelector('#wildcardChips'),prompt=document.querySelector('#positive'),label=document.querySelector('#positiveWrap');
    if(!host||!prompt||!label)return null;
    const existing=document.querySelector('#promptWildcards');if(existing)return existing;
    const details=document.createElement('details');details.id='promptWildcards';details.className='create-context-help';
    const summary=document.createElement('summary');summary.textContent='Optional prompt wildcards';
    details.append(summary);label.after(details);details.append(host);
    // Preserve app.js's host, insertion handler and caret. This owns presentation only.
    function refresh(){
      const focused=details.contains(document.activeElement),available=!host.hidden&&!!host.querySelector('[data-wildcard]');
      details.open=false;details.hidden=!available;
      if(focused)(available?summary:prompt).focus();
    }
    const Observer=(document.defaultView&&document.defaultView.MutationObserver)||root.MutationObserver;
    if(typeof Observer==='function'){
      const observer=new Observer(refresh);
      observer.observe(host,{childList:true,attributes:true,attributeFilter:['hidden']});
      details.__createContextObserver=observer;
    }
    // Same-preset authored variants change wording without repainting the host.
    document.addEventListener('studio:recipe',refresh);
    details.addEventListener('keydown',event=>{
      if(event.key!=='Escape'||!details.open)return;
      event.preventDefault();event.stopPropagation();details.open=false;summary.focus();
    });
    details.addEventListener('toggle',()=>{
      if(!details.open&&host.contains(document.activeElement))(details.hidden?prompt:summary).focus();
    });
    refresh();return details;
  }
  function mount(document){
    return {recipe:wrap(document,'recipeNotes','recipeNotesHelp','Recipe details, provenance and sources'),
            references:wrap(document,'referenceBoardNote','referenceBoardHelp','How are these references used?'),wildcards:wildcards(document)};
  }
  return{mount,observe,sync,wrap};
});
