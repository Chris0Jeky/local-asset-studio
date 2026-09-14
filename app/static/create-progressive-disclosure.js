/* Move standing explanations behind optional, accessible disclosures. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.CreateProgressiveDisclosure=api;
  if(root.document)api.mount(root.document);
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function wrap(document,targetId,detailsId,summaryText){
    const existing=document.querySelector('#'+detailsId);if(existing)return existing;
    const target=document.querySelector('#'+targetId);if(!target||!target.parentNode)return null;
    const details=document.createElement('details');details.id=detailsId;details.className='create-context-help';
    const summary=document.createElement('summary');summary.textContent=summaryText;
    target.parentNode.insertBefore(details,target);details.append(summary,target);return details;
  }
  function mount(document){
    return {recipe:wrap(document,'recipeNotes','recipeNotesHelp','Why this recipe?'),
            references:wrap(document,'referenceBoardNote','referenceBoardHelp','How are these references used?')};
  }
  return{mount,wrap};
});
