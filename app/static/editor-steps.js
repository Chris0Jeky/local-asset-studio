// #1920: the Full editor's steps in order, the one you are on and what to do next, in plain words. Display only: a step
// scrolls to or opens what is already on the page; nothing here generates, saves or changes a setting.
(function(){
  const editor=document.querySelector('#createView .editor');if(!editor)return;
  const box=document.createElement('nav');box.id='editorSteps';box.className='editor-steps';box.setAttribute('aria-label','Steps in the Full editor');editor.prepend(box);
  let result=null,shown='';   // result: the newest run started in this tab that finished with a picture
  const target={recipe:'#workshopRecipeChange,#presetSearch',describe:'#positive',sources:'#uxPullAsset',generate:'#generate'};
  const NOW={recipe:'Now: choose a recipe. It sets the model and the kind of picture.',
    describe:'Now: describe the picture in a sentence or two. Use a look to add a style without writing it.',
    generate:'Now: press Generate image in the bar below. Size, seed and adapters are already set by the recipe; change them under Fine-tune the recipe only if you want to.',
    running:'Generating. The picture lands in Recent runs at the bottom; you can keep editing meanwhile.',
    next:'Your picture is in Recent runs. Keep it with K, press Continue with this on it to edit or restyle it, or change the words and generate again. Plan comparison tests settings side by side.'};
  function render(){
    const recipe=typeof selected!=='undefined'?selected:null,words=!!document.querySelector('#positive')?.value.trim(),running=typeof activeJobId!=='undefined'&&!!activeJobId;
    const takes=!!recipe?.reference||!!recipe?.reference_slots?.length,now=!recipe?'recipe':!words?'describe':running?'running':result?'next':'generate';
    const steps=[['recipe','Recipe',!!recipe],['describe','Describe',words],['sources',takes?'Your picture · optional':'Your picture · not needed',!takes],
      ['generate',running?'Generating…':'Generate',!!result&&!running],['next','Next',false]];
    const html='<ol>'+steps.map(([id,name,done],i)=>{const current=id===now||(id==='generate'&&now==='running');
      return '<li'+(current?' aria-current="step"':'')+(done?' data-done':'')+'><button type="button" data-editor-step="'+id+'">'+(done?'✓':(i+1))+' '+name+'</button></li>';}).join('')+'</ol><p role="status">'+NOW[now]+'</p>';
    if(html!==shown){box.innerHTML=html;shown=html;}
  }
  box.addEventListener('click',e=>{
    const id=e.target.closest('[data-editor-step]')?.dataset.editorStep;if(!id)return;
    if(id==='next'){if(result&&window.StudioRunOutcome?.reveal(result))return;const runs=document.querySelector('#gallery');if(runs){for(let n=runs;n;n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;runs.scrollIntoView({block:'start'});}return;}
    const el=document.querySelector(target[id]);if(!el)return;el.scrollIntoView({block:'center'});el.focus({preventScroll:true});
  });
  // Recipe choice, typing and each jobs poll repaint; a run started here that finished with a picture opens step 5.
  for(const name of ['renderSelected','settleActiveJob']){const original=window[name];if(typeof original==='function')window[name]=function(...args){const value=original.apply(this,args);render();return value;};}
  document.addEventListener('input',render);
  document.addEventListener('studio:job-settled',e=>{if(e.detail?.status==='completed'&&(e.detail.outputs||[]).length)result=e.detail;render();});
  render();
})();
