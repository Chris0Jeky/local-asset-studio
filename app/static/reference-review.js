/* Saved reference analysis -> reviewed changes in the existing Prompt Lab draft.
 * No helper inference, model upload, generation or persistent project write. */
(() => {
  'use strict';
  const el=id=>document.getElementById(id), root=el('reference-review');
  if(!root||!globalThis.StudioPromptDraft)return;
  const owner=globalThis.StudioPromptDraft, clone=v=>JSON.parse(JSON.stringify(v));
  const roles={identity:['subject'],costume:['subject'],pose:['action','composition'],
    style:['style','palette','lighting','mood'],composition:['composition','camera','setting'],geometry:['subject']};
  const limit=8*1024*1024;
  let previewInFlight=false;
  let epoch=0, report=null, review=null, originals=null, pending=null, prepared=null, applied=null, receipt=null;
  const urls=new Set();
  const n=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  const message=text=>{el('rr-status').textContent=text;};
  function releaseUrls(){for(const url of urls)URL.revokeObjectURL(url);urls.clear();}
  function controls(){
    el('rr-originals').disabled=!report;
    el('rr-preview').disabled=!report||!originals||previewInFlight;
    el('rr-apply').disabled=!prepared;
    el('rr-undo').disabled=!applied;
    el('rr-export').disabled=!receipt;
  }
  function changed(){epoch++;prepared=null;pending=null;el('rr-diff').replaceChildren();el('rr-change-summary').textContent='';controls();}
  async function post(path,body){
    const response=await fetch('/api/prompt/reference-review/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const value=await response.json();
    if(!response.ok)throw Error(value.error||'Local validation failed. Nothing was applied.');
    if(['inference_submitted','generation_submitted','execution_authorized'].some(k=>value[k]!==false))throw Error('Unexpected reference review response.');
    return value;
  }
  function checkLabel(label,checked,onchange){
    const row=n('label');row.className='rr-check';const input=n('input');input.type='checkbox';input.checked=checked;
    input.addEventListener('change',()=>onchange(input.checked));row.append(input,document.createTextNode(label));return row;
  }
  function renderCards(){
    releaseUrls();el('rr-cards').replaceChildren();
    report.answer.images.forEach((image,index)=>{
      const ref=report.request.references[index], choice=review.selections[index];
      const card=n('article');card.className='rr-card';card.dataset.reference=ref.id;
      card.append(n('h3','Picture '+(index+1)));
      if(originals){const preview=n('img');const url=URL.createObjectURL(originals[index]);urls.add(url);preview.src=url;preview.alt='Original picture '+(index+1);preview.className='rr-picture';card.append(preview);}
      card.append(n('p',image.description));
      const label=n('label','Use this picture for');const role=n('select');role.setAttribute('aria-label','Picture '+(index+1)+' role');
      for(const key of Object.keys(roles)){const option=n('option',key);option.value=key;role.append(option);}role.value=choice.role;
      role.addEventListener('change',()=>{
        choice.role=role.value;const permitted=roles[choice.role];
        choice.facets=choice.facets.filter(k=>permitted.includes(k));
        choice.overrides=Object.fromEntries(Object.entries(choice.overrides).filter(([k])=>choice.facets.includes(k)));
        changed();renderCards();el('rr-cards').querySelector('[data-reference="'+ref.id+'"] select').focus();
        message('Role changed. Choose the traits to transfer, then preview again.');
      });label.append(role);card.append(label);
      const traits=n('details');traits.open=true;traits.append(n('summary','Traits to transfer'));
      for(const facet of roles[choice.role]){
        if(!(facet in image.facets))continue;
        const box=n('div');box.className='rr-trait';box.dataset.facet=facet;
        const uncertain=image.uncertain_facets.includes(facet);
        box.append(checkLabel('Take '+facet+(uncertain?' (uncertain — edit to confirm)':''),choice.facets.includes(facet),checked=>{
          choice.facets=checked?[...choice.facets,facet]:choice.facets.filter(k=>k!==facet);
          if(checked&&text.value!==image.facets[facet])choice.overrides[facet]=text.value;
          else delete choice.overrides[facet];changed();
        }));
        const text=n('textarea');text.rows=2;text.maxLength=240;text.value=choice.overrides[facet]??image.facets[facet];
        text.setAttribute('aria-label','Picture '+(index+1)+' '+facet+' description');
        text.addEventListener('input',()=>{
          if(!choice.facets.includes(facet)){choice.facets.push(facet);box.querySelector('input').checked=true;}
          if(text.value===image.facets[facet])delete choice.overrides[facet];else choice.overrides[facet]=text.value;
          changed();
        });box.append(text);traits.append(box);
      }
      card.append(traits);
      const extra=n('details');extra.append(n('summary','Suggested tags and unknowns'));
      for(const tag of [...new Set(image.tags)])extra.append(checkLabel(tag,choice.tags.includes(tag),checked=>{
        choice.tags=checked?[...choice.tags,tag]:choice.tags.filter(k=>k!==tag);changed();
      }));
      for(const unknown of image.unknowns)extra.append(n('p','Unknown: '+unknown));
      extra.append(n('small','Source '+ref.sha256.slice(0,12)+'… · '+ref.path));card.append(extra);el('rr-cards').append(card);
    });
  }
  function showReport(){
    el('rr-review').hidden=false;el('rr-summary').textContent=report.answer.summary;el('rr-questions').replaceChildren();
    for(const text of report.answer.assumptions)el('rr-questions').append(n('p','Assumption: '+text));
    for(const text of report.answer.questions)el('rr-questions').append(n('p','Unanswered: '+text));
    if(report.answer.questions.length)message('Analysis loaded. Review its unanswered questions and choose the exact originals.');
    else message('Analysis loaded. Choose the exact originals to review changes.');
    renderCards();controls();
  }
  // Completed worker observations enter this same review owner. Loading never applies intent.
  globalThis.StudioReferenceReview=Object.freeze({
    capture:()=>({version:epoch,context:report?{analysis:clone(report),review:clone(review)}:null}),
    restore:context=>{
      // The persistence service validated this context. Original pixels are not saved.
      changed();report=context?clone(context.analysis):null;review=context?clone(context.review):null;
      originals=null;applied=null;receipt=null;releaseUrls();el('rr-cards').replaceChildren();
      el('rr-originals').value='';el('rr-analysis').value='';el('rr-adopt').checked=false;
      el('rr-review').hidden=!report;
      if(report)showReport();
      el('rr-source-status').textContent='Reselect the exact originals before previewing another reference transfer.';
      message(report?'Saved descriptions restored; original pictures must be reselected.':'No reference review stored with this brief.');controls();
    },load:async(analysis,files=[])=>{
    if(previewInFlight)throw Error('A reference preview is still in flight; finish observing it first.');
    applied=null;receipt=null;changed();const current=epoch;
    const result=await post('inspect',{analysis});
    if(current!==epoch)throw Error('The reference review changed during loading; newer work was retained.');
    if(result.format!=='studio.reference-review/v1')throw Error('Unsupported reference review response.');
    const selected=new Map();
    for(const file of files){
      if(file.size>limit)throw Error('Reference exceeds 8 MiB.');
      const bytes=await file.arrayBuffer();
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
      selected.set(hash,file);
    }
    if(current!==epoch)throw Error('The reference review changed during image checks; newer work was retained.');
    applied=null;receipt=null;
    report=result.analysis;review=result.review;originals=null;el('rr-adopt').checked=false;
    const refs=report.request.references;
    if(refs.every(ref=>selected.has(ref.sha256))&&selected.size===files.length&&selected.size===new Set(refs.map(ref=>ref.sha256)).size)originals=refs.map(ref=>selected.get(ref.sha256));
    el('rr-originals').value='';
    el('rr-source-status').textContent=originals?refs.length+' originals matched by SHA-256.':'Reselect the exact analyzed originals to preview changes.';
    showReport();if(originals)message('Analysis and originals are ready. Review descriptions, then preview their changes.');
    return report.report_sha256;
  }});
  el('rr-analysis').addEventListener('change',async event=>{
    changed();applied=null;receipt=null;controls();const current=epoch;report=null;review=null;originals=null;releaseUrls();el('rr-cards').replaceChildren();
    el('rr-review').hidden=true;el('rr-originals').value='';el('rr-adopt').checked=false;el('rr-source-status').textContent='Open an analysis first.';controls();
    try{
      const file=event.target.files[0];if(!file||file.size>128*1024)throw Error('Choose an analysis JSON no larger than 128 KiB.');
      message('Reading saved observations…');const text=await file.text();if(current!==epoch)return;
      // Parse on the server so duplicate keys are never normalized away by JSON.parse.
      const result=await post('inspect',{analysis_json:text});if(current!==epoch)return;
      if(result.format!=='studio.reference-review/v1')throw Error('Unsupported reference review response.');
      report=result.analysis;review=result.review;el('rr-source-status').textContent='Choose '+report.request.references.length+' exact originals; order and filenames do not matter.';showReport();
    }catch(error){if(current===epoch)message(error.message);}
  });
  el('rr-originals').addEventListener('change',async event=>{
    changed();const current=epoch;originals=null;controls();renderCards();
    try{
      const files=Array.from(event.target.files), expected=report.request.references;
      if(!files.length||files.length>4||files.some(f=>!f.size||f.size>limit))throw Error('Choose one to four exact original images, each at most 8 MiB.');
      const hashes=new Map();
      for(const file of files){
        const bytes=await file.arrayBuffer();const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
        if(current!==epoch)return;
        if(hashes.has(sha)||!expected.some(r=>r.sha256===sha))throw Error('Choose each exact original once. A selected picture was changed, duplicated or not analyzed.');
        hashes.set(sha,file);
      }
      if(expected.some(r=>!hashes.has(r.sha256)))throw Error('An exact original is missing. Choose all pictures from this analysis.');
      originals=expected.map(r=>hashes.get(r.sha256));renderCards();controls();
      el('rr-source-status').textContent=expected.length+' originals matched by SHA-256.';message('Choose the traits to keep or edit their descriptions, then preview.');
    }catch(error){if(current===epoch){el('rr-source-status').textContent='Originals are not ready.';message(error.message);}}
  });
  el('rr-adopt').addEventListener('change',()=>{changed();message('Instruction choice changed. Preview before applying.');});
  async function encoded(file){
    const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
    for(let i=0;i<bytes.length;i+=4096)binary+=String.fromCharCode(...bytes.subarray(i,i+4096));return btoa(binary);
  }
  el('rr-preview').addEventListener('click',async()=>{
    if(!report||!originals||previewInFlight)return;
    changed();const current=epoch, snapshot=owner.capture(), selection=clone(review), analysis=report, files=[...originals];
    previewInFlight=true;pending=snapshot;controls();message('Checking original images and preparing a change preview…');
    try{
      const images=[];for(let i=0;i<files.length;i++){
        images.push({reference_id:analysis.request.references[i].id,media_base64:await encoded(files[i])});
        if(current!==epoch||!owner.matches(snapshot))throw Error('The brief or selection changed. Preview again.');
      }
      const result=await post('preview',{analysis,review:selection,images,intent:snapshot.intent,adopt_brief:el('rr-adopt').checked});
      if(current!==epoch)return;
      if(!owner.matches(snapshot))throw Error('The brief changed while preparing. Preview again.');
      if(result.format!=='studio.reference-transfer-preview/v1'||JSON.stringify(result.base_intent)!==snapshot.json||result.reference_draft?.source_report_sha256!==analysis.report_sha256||JSON.stringify(result.reference_draft.review)!==JSON.stringify(selection))throw Error('The preview does not match the reviewed references and brief.');
      pending=null;prepared={snapshot,result,epoch:current};el('rr-diff').replaceChildren();
      for(const change of result.changes){const item=n('details');item.append(n('summary',change.field),n('pre','Before\n'+JSON.stringify(change.before,null,2)+'\n\nAfter\n'+JSON.stringify(change.after,null,2)));el('rr-diff').append(item);}
      el('rr-change-summary').textContent=result.intent.references.length+' reference records will replace the current set; '+result.changes.length+' fields change. Nothing is applied yet.';
      message('Preview ready. Existing locks and unrelated fields are preserved. No model was called.');controls();
    }catch(error){if(current===epoch){pending=null;prepared=null;message(error.message);}}
    finally{previewInFlight=false;controls();}
  });
  el('rr-apply').addEventListener('click',()=>{
    if(!prepared)return;const chosen=prepared;
    try{
      if(chosen.epoch!==epoch)throw Error('The selection changed. Preview again.');
      // Disarm the prepared ticket before owner.apply announces its guarded
      // write, so this panel does not mistake its own synchronous event for a
      // newer external draft and erase the evidence just reviewed.
      prepared=null;pending=null;controls();
      const application=owner.apply(chosen.snapshot,chosen.result);
      applied=application;receipt={format:'studio.reference-review-receipt/v1',analysis:clone(report),preview:chosen.result,application};
      const fields=chosen.result.changes.length;
      el('rr-change-summary').textContent=chosen.result.intent.references.length+' reference records applied; '+fields+' field'+(fields===1?'':'s')+' changed. The reviewed diff is retained below.';
      controls();message('Applied to this brief. Reference files are not bound to a generator; export the receipt to retain the review.');
    }catch(error){changed();message(error.message);}
  });
  el('rr-undo').addEventListener('click',()=>{
    try{owner.undo(applied);applied=null;if(receipt)receipt.undone_in_this_tab=true;changed();message('Restored the earlier brief. The review receipt is retained.');}
    catch(error){message(error.message);}
  });
  el('rr-export').addEventListener('click',()=>{
    if(!receipt)return;const url=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}));
    const link=n('a');link.href=url;link.download='reference-review-receipt.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  document.addEventListener('studio-prompt-state',()=>{
    const snapshot=prepared?.snapshot||pending;
    if(snapshot&&!owner.matches(snapshot)){changed();message('Your brief changed. Preview again; the newer draft is untouched.');}
  });
  window.addEventListener('beforeunload',releaseUrls);
  controls();
})();
