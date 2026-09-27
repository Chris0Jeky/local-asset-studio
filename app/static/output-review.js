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
    const id=output?.asset_id;if(!id)return '';const review=record(id)?.review||'unreviewed';
    return '<div class="output-review" data-review-asset="'+escText(id)+'" role="group" aria-label="Review this output"><span class="output-review-state review-'+escText(review)+'">'+escText(LABEL[review]||review)+'</span>'+
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
  async function decide(id,value){
    if(busy)return false;
    if(!record(id)){say('This output is not in the loaded library yet. Refresh the Asset library, then try again.',true);return false;}
    // Buttons stay enabled so keyboard focus never drops to the page; `busy` refuses overlapping edits.
    busy=true;
    try{
      await refreshAssets(true);const current=record(id);if(!current)throw Error('This output is no longer in the library.');
      const next=current.review===value?'unreviewed':value;
      await mutateAssets({action:'edit',ids:[id],review:next});sync(id);
      say(next==='unreviewed'?'Review cleared. The output is unreviewed again.':LABEL[next]+'. Saved to the Asset library; press it again to clear.');return true;
    }catch(e){say(e.message,true);return false;}
    finally{busy=false;}
  }
  document.addEventListener('click',e=>{const b=e.target.closest?.('[data-output-review]');if(b)void decide(b.dataset.asset,b.dataset.outputReview);});
  document.addEventListener('keydown',e=>{
    if(e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey||e.shiftKey)return;const value=KEYS[(e.key||'').toLowerCase()];if(!value)return;
    const target=e.target;if(!target?.closest||['INPUT','TEXTAREA','SELECT'].includes((target.tagName||'').toUpperCase())||target.isContentEditable)return;
    const box=target.closest('#gallery .imageCard')?.querySelector('.output-review');if(!box)return;
    e.preventDefault();void decide(box.dataset.reviewAsset,value);
  });
  window.StudioOutputReview={markup,sync,decide};
})();
