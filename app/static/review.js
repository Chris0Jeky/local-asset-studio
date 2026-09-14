/* Review commands share Production's API; this page has no generation path. */
(function () {
  'use strict';
  const CHECKS = {constraints:'Stated constraints',identity:'Identity / costume',pose_contact:'Pose / contact',composition:'Composition',detail:'Detail / cleanup'};
  function cropFromPercent(values) {
    if(values.length!==4||values.some(v=>!['string','number'].includes(typeof v)||String(v).trim()===''||!Number.isFinite(Number(v))||Number(v)<0||Number(v)>100))throw Error('Enter four crop percentages.');
    const crop=values.map(v=>Math.round(Number(v)*100));
    if(!(0<=crop[0]&&crop[0]<crop[2]&&crop[2]<=10000&&0<=crop[1]&&crop[1]<crop[3]&&crop[3]<=10000))throw Error('Crop edges must form a rectangle within 0–100%.');
    return crop;
  }
  function optionalInteger(value,low,high) {
    if(!['string','number'].includes(typeof value))throw Error('Use a number, or leave the field blank.');
    if(String(value).trim()==='')return null;
    const n=Number(value);if(!Number.isInteger(n)||n<low||n>high)throw Error(`Use an integer from ${low} to ${high}, or leave it blank.`);return n;
  }
  function cropPixels(crop,width,height){return [Math.floor(crop[0]*width/10000),Math.floor(crop[1]*height/10000),Math.ceil(crop[2]*width/10000),Math.ceil(crop[3]*height/10000)];}
  function artifactPath(value,project) {
    if(typeof value!=='string'||!value.startsWith(`/api/production/${project}/files/reviews/`)||!/^\/api\/production\/[a-f0-9]{32}\/files\/reviews\/[a-f0-9]{32}\/[a-zA-Z0-9_./-]+$/.test(value)||value.split('/').slice(1).some(v=>v===''||v==='..'||v==='.'))throw Error('Invalid local review artifact URL.');
    return value;
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={cropFromPercent,cropPixels,optionalInteger,artifactPath};
  if(typeof document==='undefined')return;
  const $=s=>document.querySelector(s), project=new URLSearchParams(location.search).get('project');
  let state=null,busy=false,serial=0,drawSerial=0,viewDraft=null,summaryDraft=null,selectionDraft=null,characterDecisionDraft=null;
  const drafts=new Map(),images=new Map();
  const cropIds=['cropLeft','cropTop','cropRight','cropBottom'];
  const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  function message(text,error=false){$('#message').textContent=text;$('#message').classList.toggle('error',error);}
  function dirty(){return drafts.size>0||viewDraft!==null||summaryDraft!==null||selectionDraft!==null||characterDecisionDraft!==null;}
  function controls(){
    for(const node of document.querySelectorAll('button,input,select,textarea'))node.disabled=busy;
    $('#export').disabled=busy||!state?.finalized||dirty();
    $('#reveal').disabled=busy||!!state?.revealed;
    $('#restore').disabled=busy||!$('#restoreRevision').value;
    $('#saveDraft').hidden=!dirty();$('#open').disabled=busy||!project||!/^[a-f0-9]{32}$/.test(project);
    $('#viewStatus').textContent=viewDraft?'Unsaved crop':'Saved crop';
    $('#assessmentStatus').textContent=drafts.has($('#candidate').value)?'Unsaved assessment':'Saved';
    const characterSelected=!!state?.character_context&&!!$('#selected').value;
    $('#characterDecisionLabel').hidden=!characterSelected;$('#summary').required=characterSelected;
  }
  async function request(action,extra={}) {
    const payload={action,...extra};
    if(!['inspect','open'].includes(action))payload.expected_revision=state.revision;
    const response=await fetch(`/api/production/${project}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const value=await response.json();if(!response.ok)throw Error(value.error||'Review request failed.');return value;
  }
  async function operation(action,extra={},after=()=>{}){
    if(busy)return;busy=true;controls();const ticket=++serial;
    try{
      const value=await request(action,extra);if(ticket!==serial)return;
      after(value);if(action==='export')state.export=value;else state=value;
      render();message(action==='inspect'?'Saved review loaded. No generation performed.':action==='export'?'Review evidence published with original sources and checksums.':'Saved. No generation performed.');
    }catch(error){message(error.message+' Your unsaved notes are retained; reload explicitly after resolving any conflict.',true);}
    finally{if(ticket===serial){busy=false;controls();}}
  }
  function selectOptions(node,options,fallback){
    const current=node.value;node.replaceChildren(...options.map(([value,label])=>{const option=el('option',label);option.value=value;return option;}));
    node.value=options.some(([value])=>value===current)?current:fallback;
  }
  function assessmentValues(){
    return {verdict:$('#verdict').value,observations:Object.fromEntries(Object.keys(CHECKS).map(key=>[key,$('#check-'+key).value])),
            notes:$('#notes').value,cleanup_seconds:optionalInteger($('#cleanup').value,0,86400),preference:optionalInteger($('#preference').value,1,5)};
  }
  function characterValues(){return Object.fromEntries(Object.keys(state?.character_context?.required_checks||{}).map(key=>[key,$('#character-check-'+key).value]));}
  function assessmentDraft(){
    // Keep even temporarily invalid numeric input as a draft; validate only on Save.
    return {verdict:$('#verdict').value,observations:Object.fromEntries(Object.keys(CHECKS).map(key=>[key,$('#check-'+key).value])),
            notes:$('#notes').value,cleanup_seconds:$('#cleanup').value,preference:$('#preference').value,character_checks:characterValues()};
  }
  function fillAssessment(){
    const candidate=state?.candidates.find(c=>c.alias===$('#candidate').value);if(!candidate)return;
    const value=drafts.get(candidate.alias)||candidate.assessment;
    $('#verdict').value=value.verdict;$('#notes').value=value.notes;$('#cleanup').value=value.cleanup_seconds??'';$('#preference').value=value.preference??'';
    for(const key of Object.keys(CHECKS))$('#check-'+key).value=value.observations[key];
    const scope=state.character_context;$('#characterAssessment').hidden=!scope;
    $('#characterChecks').replaceChildren(...Object.entries(scope?.required_checks||{}).map(([key,description])=>{
      const label=el('label',description),select=el('select');select.id='character-check-'+key;
      for(const [value,title] of [['uncertain','Uncertain'],['not_visible','Not visible'],['pass','Pass'],['fail','Fail']]){const option=el('option',title);option.value=value;select.append(option);}
      select.value=(value.character_checks||candidate.character_checks||{})[key]||'uncertain';label.append(select);return label;
    }));
    $('#candidateSource').hidden=!state.revealed;
    $('#candidateSource').textContent=candidate.source?`${candidate.source.filename} · stage ${candidate.source.stage+1} · ${candidate.source.transform.oriented_size.join(' × ')} · SHA-256 ${candidate.source.sha256}`:'';
    controls();
  }
  function render(){
    if(!state?.exists){$('#start').hidden=false;$('#desk').hidden=true;return;}
    $('#start').hidden=true;$('#desk').hidden=false;$('#phase').textContent=state.finalized?'Decision recorded':state.revealed?'Settings revealed':'Blind review';
    $('#revision').textContent=`Revision ${state.revision} · ${state.candidates.length} candidates`;
    const options=state.candidates.map(c=>[c.alias,'Candidate '+c.alias]);
    selectOptions($('#left'),options,options[0][0]);selectOptions($('#right'),options,options[Math.min(1,options.length-1)][0]);selectOptions($('#candidate'),options,options[0][0]);
    const view=viewDraft||state;cropIds.forEach((id,i)=>{$('#'+id).value=view.crop[i]/100;});$('#background').value=view.background;
    fillAssessment();$('#progress').replaceChildren(...state.candidates.map(c=>{const row=el('div');row.className='progress-row';row.append(el('b','Candidate '+c.alias),el('span',c.assessment.verdict.replaceAll('_',' ')));return row;}));
    $('#decision').hidden=!state.revealed;$('#provenance').hidden=!state.revealed;$('#evidence').textContent=state.revealed?JSON.stringify(state.evidence,null,2):'';
    selectOptions($('#selected'),[['','None should progress'],...options],state.selected||'');$('#selected').value=selectionDraft??state.selected??'';$('#summary').value=summaryDraft??state.notes;
    $('#characterDecision').value=characterDecisionDraft??state.character_review?.review?.decision??'selected';
    $('#characterDecisionStatus').hidden=!state.character_context;
    $('#characterDecisionStatus').textContent=state.character_review?`${state.character_review.review.decision==='accepted'?'Accepted':'Selected'} for this case by ${state.character_review.review.reviewer} at review revision ${state.character_review.review_revision}. Rights and engine acceptance remain separate.`:'Character acceptance has not been recorded. Every character requirement must pass before selection or acceptance.';
    $('#history').replaceChildren(...state.history.slice(0,40).map(e=>el('li',`r${e.revision} · ${e.action}${e.alias?' · '+e.alias:''} · ${e.reviewer}`)));
    selectOptions($('#restoreRevision'),[['','Choose an earlier assessment'],...state.history.filter(e=>e.action==='rate').map(e=>[String(e.revision),`r${e.revision} · ${e.alias} · ${e.assessment.verdict}`])],'');
    $('#downloads').replaceChildren();
    for(const a of state.export?.artifacts||[]){const link=el('a',a.path.endsWith('.zip')?'Download review evidence pack':a.path.endsWith('.png')?'Download matched contact sheet':'Download structured review');link.href=artifactPath(a.url,project)+'?download';link.download='';$('#downloads').append(link);}
    draw().catch(error=>message(error.message,true));controls();
  }
  async function imageFor(url){
    artifactPath(url,project);
    if(!images.has(url)){const image=new Image();image.src=url;images.set(url,image.decode().then(()=>image).catch(error=>{images.delete(url);throw error;}));}
    return images.get(url);
  }
  async function draw(){
    if(!state?.exists)return;const ticket=++drawSerial;
    const crop=cropFromPercent(cropIds.map(id=>$('#'+id).value)),background=$('#background').value,mode=$('#mode').value;
    $('#leftFigure').hidden=mode==='right';$('#rightFigure').hidden=mode==='left';$('#canvases').classList.toggle('single',mode!=='pair');
    await Promise.all(['left','right'].map(async side=>{
      const candidate=state.candidates.find(c=>c.alias===$('#'+side).value),image=await imageFor(candidate.preview_url);if(ticket!==drawSerial)return;
      const canvas=$('#'+side+'Canvas'),ctx=canvas.getContext('2d'),[l,t,r,b]=cropPixels(crop,image.naturalWidth,image.naturalHeight),scale=Math.min(canvas.width/(r-l),canvas.height/(b-t));
      ctx.fillStyle=background==='dark'?'#20232b':'#f1f2f5';ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.drawImage(image,l,t,r-l,b-t,(canvas.width-(r-l)*scale)/2,(canvas.height-(b-t)*scale)/2,(r-l)*scale,(b-t)*scale);
      canvas.setAttribute('aria-label','Candidate '+candidate.alias+' · shared cropped preview');
      $('#'+side+'Caption').textContent='Candidate '+candidate.alias+(candidate.source?' · '+candidate.source.filename:' · settings hidden');
    }));
  }
  for(const [key,label] of Object.entries(CHECKS)){
    const wrap=el('label',label),select=el('select');select.id='check-'+key;
    for(const [value,label] of [['not_assessed','Not assessed'],['pass','Pass'],['fail','Fail']]){const o=el('option',label);o.value=value;select.append(o);}wrap.append(select);$('#observations').append(wrap);
  }
  $('#open').onclick=()=>operation('open');
  $('#reload').onclick=()=>{
    if(dirty()&&!confirm('Discard unsaved local notes and reload the saved revision? Download the unsaved notes first to keep a copy.'))return;
    operation('inspect',{},()=>{drafts.clear();viewDraft=summaryDraft=selectionDraft=characterDecisionDraft=null;});
  };
  $('#candidate').onchange=fillAssessment;
  $('#assessmentForm').oninput=event=>{if(event.target.id==='candidate')return;drafts.set($('#candidate').value,assessmentDraft());controls();};
  $('#assessmentForm').onsubmit=event=>{event.preventDefault();try{const alias=$('#candidate').value,extra=state.character_context?{character_checks:characterValues()}:{};operation('rate',{alias,assessment:assessmentValues(),...extra},()=>drafts.delete(alias));}catch(error){message(error.message,true);}};
  $('#cropForm').oninput=()=>{try{viewDraft={crop:cropFromPercent(cropIds.map(id=>$('#'+id).value)),background:$('#background').value};draw().catch(error=>message(error.message,true));}catch(error){viewDraft={crop:state.crop,background:$('#background').value};message(error.message,true);}controls();};
  $('#cropForm').onsubmit=event=>{event.preventDefault();try{operation('view',{crop:cropFromPercent(cropIds.map(id=>$('#'+id).value)),background:$('#background').value},()=>{viewDraft=null;});}catch(error){message(error.message,true);}};
  for(const button of document.querySelectorAll('[data-crop]'))button.onclick=()=>{const crop={whole:[0,0,10000,10000],centre:[2500,2500,7500,7500],upper:[0,0,10000,5000]}[button.dataset.crop];cropIds.forEach((id,i)=>{$('#'+id).value=crop[i]/100;});$('#cropForm').oninput();};
  for(const side of ['left','right','mode'])$('#'+side).onchange=()=>draw().catch(error=>message(error.message,true));
  $('#swap').onclick=()=>{const left=$('#left').value;$('#left').value=$('#right').value;$('#right').value=left;draw().catch(error=>message(error.message,true));};
  $('#reveal').onclick=()=>{if(confirm('Reveal recipe settings and source identities? This is recorded and cannot be undone as a blind review.'))operation('reveal');};
  $('#summary').oninput=()=>{summaryDraft=$('#summary').value;controls();};$('#selected').onchange=()=>{selectionDraft=$('#selected').value;controls();};
  $('#characterDecision').onchange=()=>{characterDecisionDraft=$('#characterDecision').value;controls();};
  $('#decisionForm').onsubmit=event=>{event.preventDefault();if(drafts.size||viewDraft){message('Save candidate assessments and the shared crop before recording the decision.',true);return;}const selected=$('#selected').value||null,extra=state.character_context&&selected?{character_decision:$('#characterDecision').value,reviewer:'local-user'}:{};operation('finalize',{selected,notes:$('#summary').value,...extra},()=>{summaryDraft=selectionDraft=characterDecisionDraft=null;});};
  $('#export').onclick=()=>operation('export');$('#restoreRevision').onchange=controls;
  $('#restore').onclick=()=>{if(dirty()){message('Save or download your local drafts before restoring an earlier assessment.',true);return;}operation('restore',{source_revision:Number($('#restoreRevision').value)});};
  $('#saveDraft').onclick=()=>{
    const blob=new Blob([JSON.stringify({kind:'unsaved-review-notes',project_id:project,base_revision:state?.revision,assessments:Object.fromEntries(drafts),view:viewDraft,notes:summaryDraft,selected:selectionDraft,character_decision:characterDecisionDraft},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=el('a');link.href=url;link.download='unsaved-review-notes.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
  controls();
  if(!project||!/^[0-9a-f]{32}$/.test(project)){message('Open Review desk from an image comparison in Studio’s Experiments view.',true);$('#reload').disabled=true;}
  else operation('inspect');
}());
