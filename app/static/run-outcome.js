// One next step when the run you started settles (#278, #772). app.js announces the settled record once
// ('studio:job-settled'); this says what happened in plain words and offers the one useful move:
// a finished run shows its result card, anything else reveals its record: a Problems entry, or the Recent runs card of a run that
// never started (not_submitted, #1120) or was cancelled before it made anything. Nothing here submits,
// retries or changes a job: every action only opens, scrolls or focuses what is already on the page.
(function(){
  const plural=(n,word)=>n+' '+word+(n===1?'':'s');
  const took=job=>Number(job.elapsed_seconds)>0&&typeof durationLabel==='function'?' in '+durationLabel(job.elapsed_seconds):'';
  // #302: the server samples Windows commit every 0.5 s while each prompt runs (host_commit_windows). Only a run that came
  // close says so: the qwen-2ref job that died on a host allocation had about 9 GB left (12 Sep 2026). Silence otherwise.
  const TIGHT_BYTES=16*2**30;
  const tight=job=>{let low=null,pct=null;for(const w of job.host_commit_windows||[]){const n=v=>typeof v==='number'&&Number.isFinite(v)?v:NaN,left=n(w?.min_available_bytes),peak=n(w?.peak_committed_bytes),limit=n(w?.limit_bytes);
    if(Number.isFinite(left)&&left>=0&&(low===null||left<low))low=left;if(peak>0&&limit>0)pct=Math.max(pct??0,peak/limit);}
    return low!==null&&low<TIGHT_BYTES?' Memory was tight: Windows commit headroom fell to '+(low/2**30).toFixed(1)+' GiB'+(pct?' ('+Math.round(pct*100)+' % used)':'')+'; close memory-heavy programs before the next large job.':'';};
  function summary(job){
    const made=(job.outputs||[]).length;
    if(job.status==='completed')return {text:'Done'+took(job)+' · '+plural(made,'output')+'. Review it while it is fresh.'+tight(job),action:'Show result',error:false};
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
    // A cancelled run that kept finished outputs has results too (#1160 review); its record is the fallback.
    const results=job.status==='completed'||(job.status==='cancelled'&&(job.outputs||[]).length>0);
    const output=results?document.querySelector('#gallery [data-output^="'+CSS.escape(job.id)+':"]'):null;
    const target=job.status==='completed'?output:output||document.querySelector('[data-problem="'+CSS.escape(job.id)+'"]');
    if(!target){if(typeof message==='function')message('That run is not shown here yet (a playing clip holds the list until it stops) or its outputs are in Trash. Asset library has every saved output.',true);return false;}
    // open() unfolds whichever holds the record: Problems for a problem, Recent runs for a gallery card (#1120), never both.
    open(target);target.scrollIntoView({block:'center'});
    // A result focuses its first action (so K/W/X review it); a problem focuses its record, reason first.
    const first=output?target.querySelector('button,a,summary'):null;if(!first&&!target.hasAttribute('tabindex'))target.tabIndex=-1;(first||target).focus({preventScroll:true});return true;
  }
  let shown=null;const pending=[];
  function waiting(){const el=document.getElementById('runOutcomeWaiting');if(el){el.textContent=pending.length?plural(pending.length,'more run')+' settled. Dismiss to see the next.':'';el.hidden=!pending.length;}}
  function display(job){
    const el=box();if(!el)return;const s=summary(job);shown=job;
    el.innerHTML='';const text=document.createElement('p');text.className='run-outcome-summary'+(s.error?' error':'');text.textContent=s.text;text.setAttribute('role','status');
    const more=document.createElement('small');more.id='runOutcomeWaiting';more.setAttribute('role','status');
    const go=document.createElement('button');go.type='button';go.dataset.runOutcome='show';go.textContent=s.action+' →';
    const close=document.createElement('button');close.type='button';close.dataset.runOutcome='dismiss';close.textContent='Dismiss';close.setAttribute('aria-label','Dismiss this run summary');
    el.append(text,more,go,close);el.hidden=false;waiting();
  }
  // A single poll can settle several started runs. Keep the current controls/focus until Dismiss,
  // and own the summary text so a poll error or a newer Generate cannot erase the notice (#1250).
  function render(job){if(shown){pending.push(job);waiting();}else display(job);}
  function clear(){shown=null;pending.length=0;const el=document.getElementById('runOutcome');if(el){el.hidden=true;el.innerHTML='';}}
  function returnFocus(){
    const generate=document.getElementById('generate');generate?.focus();if(generate&&document.activeElement===generate)return;
    const status=document.getElementById('status');
    for(const target of [status,status?.closest('.wk-run-dock'),status?.closest('.editor')])if(target){if(!target.hasAttribute('tabindex'))target.tabIndex=-1;target.focus({preventScroll:true});if(document.activeElement===target)return;}
  }
  document.addEventListener('studio:job-settled',e=>{if(e.detail?.id)render(e.detail);});
  document.addEventListener('click',e=>{
    const b=e.target.closest?.('[data-run-outcome]');
    if(b){if(b.dataset.runOutcome==='dismiss'){const focused=document.activeElement===b,next=pending.shift();if(next){display(next);if(focused)document.querySelector('#runOutcome [data-run-outcome="dismiss"]')?.focus();}else{clear();if(focused)returnFocus();}}else if(shown){const job=(typeof jobs!=='undefined'&&jobs.find(j=>j.id===shown.id))||shown;reveal(job);}return;}
  },true);
  window.StudioRunOutcome={summary,render,clear,reveal,tight};
})();
