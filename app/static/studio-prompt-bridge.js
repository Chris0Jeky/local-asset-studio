/* Explicit, workspace-scoped, text-only bridge. Does not compile or generate. */
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  if(!q('export-result'))return;
  const section=document.createElement('section');section.className='ux-prompt-transfer';section.innerHTML='<h3>Use this text in Create</h3><p>Transfer the reviewed positive and negative text. References, model bindings and sampling settings are not transferred. Choose a matching recipe in Create.</p><button id="studioSendPrompt" type="button" disabled>Review text in Create →</button><p id="studioPromptStatus" role="status"></p>';q('fields').parentElement.append(section);
  const button=q('studioSendPrompt');
  function sync(){button.disabled=q('export-result').disabled||!StudioUX.promptTransfer(result);}
  const observer=new MutationObserver(sync);observer.observe(q('export-result'),{attributes:true,attributeFilter:['disabled']});sync();
  button.onclick=async()=>{const transfer=StudioUX.promptTransfer(result);if(!transfer)return;button.disabled=true;try{const response=await fetch('/api/identity');if(!response.ok)throw Error('Workspace identity is unavailable. Export the compilation instead.');const identity=await response.json();sessionStorage.setItem('studio-prompt-handoff',JSON.stringify({workspace:identity.workspace,createdAt:Date.now(),transfer}));location.href='/#create';}catch(e){q('studioPromptStatus').textContent=e.message+' Use Export compilation when browser storage is unavailable.';sync();}};
})();
