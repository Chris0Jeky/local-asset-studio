// Review where you generate (#278 slice 4, #940): Keep / Needs work / Reject on each Recent runs output.
// A decision is the same asset edit the Asset library saves (mutateAssets, revision-checked); pressing the
// current decision again returns the output to unreviewed. Nothing is generated, moved or deleted.
// K / W / X decide for the output whose card holds keyboard focus, never while typing in a field.
(function(){
  const LABEL={selected:'Kept',needs_work:'Needs work',rejected:'Rejected',unreviewed:'Unreviewed'};
  const KEYS={k:'selected',w:'needs_work',x:'rejected'};
  const CHOICES=[['selected','Keep','K'],['needs_work','Needs work','W'],['rejected','Reject','X']];
  let busy=false;
  const record=id=>typeof assetState!=='undefined'?assetState.assets.find(a=>a.id===id):null;
  const escText=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // The card owns the markup so renderJobs keeps focus on a decision button across a poll re-render.
  function markup(output){
    const id=output?.asset_id;if(!id)return '';const review=record(id)?.review||'unreviewed',saving=pendingFor(id);
    return '<div class="output-review" data-review-asset="'+escText(id)+'" role="group" aria-label="Review this output"'+(saving?' aria-busy="true"':'')+'><span class="output-review-state review-'+escText(review)+'">'+(saving?'Saving…':escText(LABEL[review]||review))+'</span>'+
      CHOICES.map(([value,label,key])=>'<button type="button" class="outputReview" data-output-review="'+value+'" data-asset="'+escText(id)+'" aria-pressed="'+(review===value)+'" aria-keyshortcuts="'+key+'" title="'+label+' ('+key+' on a focused card)'+(review===value?'. Press again to clear.':'')+'">'+label+'</button>').join('')+'</div>';
  }
  // Update every copy in place: the jobs signature does not change when only a review does.
  function sync(id){
    const review=record(id)?.review||'unreviewed';
    for(const box of document.querySelectorAll('.output-review[data-review-asset="'+CSS.escape(id)+'"]')){
      const state=box.querySelector('.output-review-state');state.className='output-review-state review-'+review;state.textContent=LABEL[review]||review;
      for(const b of box.querySelectorAll('[data-output-review]')){const on=b.dataset.outputReview===review,[,label,key]=CHOICES.find(c=>c[0]===b.dataset.outputReview);b.setAttribute('aria-pressed',String(on));b.title=label+' ('+key+' on a focused card)'+(on?'. Press again to clear.':'');}
    }
  }
  const say=(text,error=false)=>typeof message==='function'?message(text,error):null;
  // The library takes one edit at a time, so decisions queue in press order and none is dropped: a press on any
  // card while a save is in flight is saved right after it, and its row says "Saving…" until then. Buttons stay
  // enabled so keyboard focus never drops to the page. A long queue is refused out loud, never silently.
  const queue=[],QUEUE_MAX=24;
  function pendingFor(id){return queue.some(q=>q.id===id)||busy===id;}
  function mark(id){for(const box of document.querySelectorAll('.output-review[data-review-asset="'+CSS.escape(id)+'"]')){const on=pendingFor(id);box.toggleAttribute('aria-busy',on);if(on)box.querySelector('.output-review-state').textContent='Saving…';}}
  async function readLibrary(){
    let fresh=await refreshAssets(true);
    // false means another library read is in flight (or failed): wait for it briefly, then read once more.
    for(let i=0;!fresh&&typeof assetRefreshing!=='undefined'&&assetRefreshing&&i<50;i++)await new Promise(r=>setTimeout(r,100));
    if(!fresh)fresh=await refreshAssets(true);
    if(!fresh)throw Error('Could not read the library, so nothing was saved. Try again.');
  }
  async function apply(id,value){
    try{
      // Create does not poll the library, so a new output's asset arrives only with this read.
      await readLibrary();const current=record(id);if(!current)throw Error('This output is not in the library yet. Try again in a moment, or open Asset library.');
      const next=current.review===value?'unreviewed':value;
      await mutateAssets({action:'edit',ids:[id],review:next});
      say(next==='unreviewed'?'Review cleared. The output is unreviewed again.':LABEL[next]+'. Saved to the Asset library; press it again to clear.');return true;
    }catch(e){
      // After a refused edit the library holds it for recovery, so later queued decisions cannot save: say so.
      const dropped=queue.splice(0);for(const d of dropped){sync(d.id);mark(d.id);}
      say(e.message+(typeof assetLibraryPending!=='undefined'&&assetLibraryPending?' Open Asset library to check or retry the earlier update.':'')+(dropped.length?' '+plural(dropped.length)+' after it were not saved.':''),true);return false;
    }
  }
  const plural=n=>n+(n===1?' later decision':' later decisions');
  async function decide(id,value){
    if(queue.length>=QUEUE_MAX){say('Too many decisions are waiting to save. Wait a moment, then continue.',true);return false;}
    queue.push({id,value});mark(id);
    if(busy){say('Saving the previous decision; this one follows.');return true;}
    let ok=true;
    while(queue.length){const job=queue.shift();busy=job.id;try{ok=await apply(job.id,job.value);}finally{busy=false;sync(job.id);mark(job.id);}}
    return ok;
  }
  document.addEventListener('click',e=>{const b=e.target.closest?.('[data-output-review]');if(b)void decide(b.dataset.asset,b.dataset.outputReview);});
  document.addEventListener('keydown',e=>{
    // A held key repeats; a repeat must never toggle the decision it just saved back off.
    if(e.repeat||e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey||e.shiftKey)return;const value=KEYS[(e.key||'').toLowerCase()];if(!value)return;
    const target=e.target;if(!target?.closest||['INPUT','TEXTAREA','SELECT'].includes((target.tagName||'').toUpperCase())||target.isContentEditable)return;
    const box=target.closest('#gallery .imageCard')?.querySelector('.output-review');if(!box)return;
    e.preventDefault();void decide(box.dataset.reviewAsset,value);
  });
  window.StudioOutputReview={markup,sync,decide};
})();
