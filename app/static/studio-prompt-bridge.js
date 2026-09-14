/* Explicit, workspace-scoped, text-only bridge. Does not compile or generate. */
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  if(!q('export-result'))return;
  const section=document.createElement('section');section.className='ux-prompt-transfer';section.innerHTML='<h3>Use this text in Create</h3><p>This carries the reviewed positive and negative text into Create and opens it there. References, model bindings and sampling settings are not carried: choose a matching recipe and reattach sources yourself.</p><button id="studioSendPrompt" type="button" disabled>Open Create with this prompt →</button><p id="studioPromptReason" class="pl-reason"></p><p id="studioPromptStatus" role="status"></p>';q('fields').parentElement.append(section);
  const button=q('studioSendPrompt'),reason=q('studioPromptReason');
  // Never a bare disabled control: the reason a transfer is locked is rendered next to the button.
  function sync(){const blockers=StudioUX.promptBlockers(result).filter(x=>x.blocking),transfer=StudioUX.promptTransfer(result);
    button.disabled=!!blockers.length||!transfer;
    reason.textContent=button.disabled?blockers.map(x=>x.message+' '+x.action).join(' ')||'The built prompt cannot be carried into Create yet.':'';}
  const observer=new MutationObserver(sync);observer.observe(q('export-result'),{attributes:true,attributeFilter:['disabled']});document.addEventListener('studio-prompt-state',sync);sync();
  button.onclick=async()=>{const transfer=StudioUX.promptTransfer(result);if(!transfer)return;button.disabled=true;try{const response=await fetch('/api/identity');if(!response.ok)throw Error('Workspace identity is unavailable. Export the compilation instead.');const identity=await response.json();sessionStorage.setItem('studio-prompt-handoff',JSON.stringify({workspace:identity.workspace,createdAt:Date.now(),transfer}));location.href='/#create';}catch(e){q('studioPromptStatus').textContent=e.message+' Use Export compilation when browser storage is unavailable.';sync();}};
})();
