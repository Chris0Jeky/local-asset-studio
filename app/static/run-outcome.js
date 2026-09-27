// One next step when the run you started settles (#278, #772). app.js announces the settled record once
// ('studio:job-settled'); this says what happened in plain words and offers the one useful move:
// a finished run shows its result card, anything else opens its Problems entry. Nothing here submits,
// retries or changes a job: every action only opens, scrolls or focuses what is already on the page.
(function(){
  const plural=(n,word)=>n+' '+word+(n===1?'':'s');
  const took=job=>Number(job.elapsed_seconds)>0&&typeof durationLabel==='function'?' in '+durationLabel(job.elapsed_seconds):'';
  function summary(job){
    const made=(job.outputs||[]).length;
    if(job.status==='completed')return {text:'Done'+took(job)+' · '+plural(made,'output')+'. Review it while it is fresh.',action:'Show result',error:false};
    if(job.status==='partial')return {text:'Partly done: '+plural(made,'output')+' saved. The rest will not be run again automatically.',action:'See what happened',error:true};
    if(job.status==='not_submitted')return {text:'Not started: '+(String(job.message||'').split(/(?<=\.)\s/)[0]||'the queue could not be checked.')+' Nothing was submitted.',action:'See why',error:true};
    if(job.status==='cancelled')return {text:made?'Cancelled: '+plural(made,'finished output')+' kept. Nothing was retried.':String(job.message||'Cancelled by you.'),action:made?'Show result':'See the record',error:false};
    if(job.status==='uncertain')return {text:'Outcome unknown. It will not be run again; inspect it before starting new work.',action:'Inspect',error:true};
    const why=job.failure?.title||String(job.message||'').split(/(?<=\.)\s/)[0]||'No reason was recorded.';
    return {text:'Failed: '+why,action:'See why',error:true};
  }
  function box(){
    let el=document.getElementById('runOutcome');if(el)return el;
    const status=document.getElementById('status');if(!status)return null;
    el=document.createElement('div');el.id='runOutcome';el.className='run-outcome';el.hidden=true;status.after(el);return el;
  }
  function open(node){for(let n=node;n;n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;}
  function reveal(job){
    // Any shown output of the run will do: output 0 may be in Trash, and a playing clip holds the list back.
    const target=job.status==='completed'?document.querySelector('#gallery [data-output^="'+CSS.escape(job.id)+':"]'):document.querySelector('[data-problem="'+CSS.escape(job.id)+'"]');
    if(!target){if(typeof message==='function')message('That run is not shown here yet (a playing clip holds the list until it stops) or its outputs are in Trash. Asset library has every saved output.',true);return false;}
    if(job.status!=='completed'){const details=document.getElementById('jobProblems');if(details)details.open=true;}
    open(target);target.scrollIntoView({block:'center'});
    // A result focuses its first action (so K/W/X review it); a problem focuses its record, reason first.
    const first=job.status==='completed'?target.querySelector('button,a,summary'):null;if(!first&&!target.hasAttribute('tabindex'))target.tabIndex=-1;(first||target).focus({preventScroll:true});return true;
  }
  let shown=null;
  function render(job){
    const el=box();if(!el)return;const s=summary(job);shown=job;
    if(typeof message==='function')message(s.text,s.error);
    el.innerHTML='';const go=document.createElement('button');go.type='button';go.dataset.runOutcome='show';go.textContent=s.action+' →';
    const close=document.createElement('button');close.type='button';close.dataset.runOutcome='dismiss';close.textContent='Dismiss';close.setAttribute('aria-label','Dismiss this run summary');
    el.append(go,close);el.hidden=false;
  }
  function clear(){shown=null;const el=document.getElementById('runOutcome');if(el){el.hidden=true;el.innerHTML='';}}
  document.addEventListener('studio:job-settled',e=>{if(e.detail?.id)render(e.detail);});
  document.addEventListener('click',e=>{
    const b=e.target.closest?.('[data-run-outcome]');
    if(b){if(b.dataset.runOutcome==='dismiss'){const said=shown&&summary(shown).text;clear();if(typeof message==='function'&&document.getElementById('status')?.textContent===said)message('');}else if(shown){const job=(typeof jobs!=='undefined'&&jobs.find(j=>j.id===shown.id))||shown;reveal(job);}return;}
    if(e.target.closest?.('#generate'))clear();
  },true);
  window.StudioRunOutcome={summary,render,clear,reveal};
})();
