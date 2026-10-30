/* Review commands share Production's API; this page has no generation path. */
(function () {
  'use strict';
  const CHECKS = {constraints:'Stated constraints',identity:'Identity / costume',pose_contact:'Pose / contact',composition:'Composition',detail:'Detail / cleanup'};
  const verdictLabel=v=>({keep:'Keep',needs_work:'Needs work',reject:'Not this',unreviewed:'Not reviewed'}[v]||String(v).replaceAll('_',' '));
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
  const drawn={left:null,right:null};   // the alias each preview canvas actually shows; K/W/X wait for it (#1760 review)
  let state=null,busy=false,serial=0,drawSerial=0,viewDraft=null,summaryDraft=null,selectionDraft=null,characterDecisionDraft=null;
  let presentation=new URLSearchParams(location.search).get('view')==='grid'?'grid':'pair';
  let primarySide='left',heldSide=null;
  const drafts=new Map(),images=new Map();
  const cropIds=['cropLeft','cropTop','cropRight','cropBottom'];
  const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
  function message(text,error=false){$('#message').textContent=text;$('#message').classList.toggle('error',error);}
  function dirty(){return drafts.size>0||viewDraft!==null||summaryDraft!==null||selectionDraft!==null||characterDecisionDraft!==null;}
  // #1752: the one-click winner path. The click itself is the human declaration that the stated constraints hold; nothing else sets that check.
  const winnerTarget=()=>state?.candidates?.find(c=>c.alias===$('#selected').value)||null;
  function winnerBlock(candidate){
    if(!state?.revealed)return 'Reveal the settings first.';
    if(drafts.size||viewDraft)return 'Save candidate assessments and the shared crop first.';
    if(!candidate)return 'Choose a kept candidate under Selected result first.';
    if(state.candidates.some(c=>c.assessment.verdict==='unreviewed'))return 'Record a verdict for every candidate, including rejected results.';
    if(candidate.assessment.verdict!=='keep')return 'Candidate '+candidate.alias+' is not kept; only a kept candidate can be the winner.';
    if(state.evidence?.stages?.[candidate.source?.stage]?.status!=='completed')return 'An incomplete execution may be reviewed but cannot become the selected result.';
    return '';
  }
  function controls(){
    for(const node of document.querySelectorAll('button,input,select,textarea'))node.disabled=busy;
    $('#desk').setAttribute('aria-busy',busy?'true':'false');
    $('#export').disabled=busy||!state?.finalized||dirty();
    const exportReason=busy?'':dirty()?'Save your unsaved changes first':!state?.finalized?'Finalize the review first':'';
    $('#export').title=exportReason;$('#exportHint').textContent=exportReason;
    $('#reveal').disabled=busy||!!state?.revealed;
    $('#presentationGrid').disabled=busy||!state?.grid;
    $('#restore').disabled=busy||!$('#restoreRevision').value;
    $('#saveDraft').hidden=!dirty();$('#open').disabled=busy||!project||!/^[a-f0-9]{32}$/.test(project);
    $('#viewStatus').textContent=viewDraft?'Unsaved crop':'Saved crop';
    $('#assessmentStatus').textContent=drafts.has($('#candidate').value)?'Unsaved assessment':'Saved';
    const target=winnerTarget(),block=winnerBlock(target);
    $('#chooseWinner').textContent=(target?'Candidate '+target.alias+' meets':'Meets')+' the stated constraints — choose as winner';
    $('#chooseWinner').disabled=busy||!!block;$('#chooseWinner').title=block;$('#chooseWinnerHint').textContent=busy?'':block;
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
    if(busy)return;const focusedAlias=document.activeElement?.dataset?.gridCandidate;
    releaseCompare();
    busy=true;message(action==='export'?'Exporting…':['inspect','open'].includes(action)?'Loading…':'Saving…');controls();const ticket=++serial;
    try{
      const value=await request(action,extra);if(ticket!==serial)return;
      after(value);if(action==='export')state.export=value;else state=value;
      render();message(action==='inspect'?'Saved review loaded. No generation performed.':action==='export'?'Review evidence published with original sources and checksums.':'Saved. No generation performed.');return '';
    }catch(error){message(error.message+' Your unsaved notes are retained; reload explicitly after resolving any conflict.',true);return error.message;}
    finally{if(ticket===serial){busy=false;controls();if(focusedAlias)gridButtons().find(b=>b.dataset.gridCandidate===focusedAlias)?.focus({preventScroll:true});}}
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
    releaseCompare();
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
    syncGridSelection();controls();
  }
  const runLabel=status=>({completed:'Completed',failed:'Failed',cancelled:'Cancelled',not_started:'Not started',stopped:'Stopped',interrupted:'Interrupted',unavailable:'Execution unavailable'}[status]||'Execution unavailable');
  function gridButtons(){return [...$('#gridTable').querySelectorAll('[data-grid-candidate]')];}
  function syncGridSelection(){
    for(const button of gridButtons()){
      const alias=button.dataset.gridCandidate,candidate=state?.candidates.find(c=>c.alias===alias);if(!candidate)continue;
      const selected=alias===$('#candidate').value;button.setAttribute('aria-pressed',String(selected));button.classList.toggle('is-current',selected);
      button.querySelector('small').textContent=verdictLabel((drafts.get(alias)||candidate.assessment).verdict)+(drafts.has(alias)?' · unsaved':'');
    }
  }
  function applyPresentation(){
    if(!state?.grid)presentation='pair';const grid=presentation==='grid';
    $('#gridPanel').hidden=!grid;$('#comparisonLayout').classList.toggle('with-grid',grid);
    $('#presentationPair').setAttribute('aria-pressed',String(!grid));$('#presentationGrid').setAttribute('aria-pressed',String(grid));
    $('#gridHint').textContent=!state?.grid?'Grid needs unambiguous saved settings and seeds. Pair is available for this review.':state.revealed?'Rows show the saved comparisons; columns show their seeds. Every retained image remains selectable.':'Rows group comparisons; columns group seeds. Their identities stay hidden until Reveal.';
    const destination=$(grid?'#gridAssessment':'#assessmentHome');
    if($('#assessment').parentElement!==destination)destination.append($('#assessment'));
    $('#assessmentHome').hidden=grid;$('#assessmentHome').parentElement?.classList.toggle('grid-decision',grid);
  }
  function setPresentation(value){
    if(busy||value==='grid'&&!state?.grid)return;releaseCompare();presentation=value;applyPresentation();
    const url=new URL(location.href);url.searchParams.set('view',presentation);history.replaceState(null,'',url);
    draw().catch(error=>message(error.message,true));controls();
  }
  function selectGridCandidate(alias){
    if(busy||!state?.candidates.some(c=>c.alias===alias))return;
    const previous=$('#left').value;$('#candidate').value=alias;$('#left').value=alias;
    if($('#right').value===alias&&previous!==alias)$('#right').value=previous;
    $('#mode').value='pair';fillAssessment();draw().catch(error=>message(error.message,true));
    message('Candidate '+alias+' selected. Its matched crop and assessment are open.');
  }
  function renderGrid(){
    const table=$('#gridTable');table.replaceChildren();if(!state?.grid)return;
    const grid=state.grid,caption=el('caption','Comparison grid'),head=el('thead'),header=el('tr'),corner=el('th','');
    table.classList.toggle('has-settings',state.revealed&&grid.rows.some(row=>row.settings));
    header.append(corner);
    for(const column of grid.columns){const th=el('th',state.revealed?'Seed '+column.seed:column.alias);th.scope='col';header.append(th);}
    head.append(header);const body=el('tbody');
    for(const row of grid.rows){
      const tr=el('tr'),th=el('th',state.revealed?(row.label??row.engine):row.alias);th.scope='row';tr.append(th);
      if(state.revealed&&row.settings){
        const details=el('details'),names={positive:'Wording',negative:'Negative text',seed:'Seed',cfg:'Guidance',steps:'Steps',denoise:'Denoise',lora:'LoRA strength'};
        details.className='grid-settings';details.append(el('summary','Settings'));
        for(const [key,value] of Object.entries(row.settings))details.append(el('p',(names[key]||key)+': '+value));
        th.append(details);
      }
      for(const column of grid.columns){
        const cell=grid.cells.find(c=>c.row===row.alias&&c.column===column.alias),td=el('td'),content=el('div');content.className='grid-cell';
        const runs=cell?.runs||[],many=runs.length>1,aliases=cell?.candidates||[],claimed=new Set(runs.flatMap(run=>run.candidates||[]));
        const status=el('p',many?runs.length+' runs':runs.length?runLabel(runs[0].status):'Not planned');status.className='grid-outcome';content.append(status);
        // Run labels are ordinal and status-only: repeated coordinates share engine and seed, so Run N reveals nothing hidden.
        const groups=many?runs.map((run,i)=>({label:`Run ${i+1} · ${runLabel(run.status)}`,aliases:(run.candidates||[]).filter(a=>aliases.includes(a))})):[{aliases}];
        const extra=aliases.filter(a=>!claimed.has(a));if(many&&extra.length)groups.push({label:'Other retained images',aliases:extra});
        for(const group of groups){
          const outputs=el('div');outputs.className='grid-outputs';let box=outputs;
          if(many){box=el('div');box.className='grid-run';box.setAttribute('role','group');box.setAttribute('aria-label',group.label);const label=el('p',group.label);label.className='grid-run-label';box.append(label,outputs);}
          for(const alias of group.aliases){
            const button=el('button');button.type='button';button.className='grid-candidate';
            button.dataset.gridCandidate=alias;button.dataset.gridRow=row.alias;button.dataset.gridColumn=column.alias;
            if(many)button.dataset.gridRun=group.label;
            const canvas=el('canvas');canvas.width=384;canvas.height=384;canvas.setAttribute('aria-hidden','true');
            button.append(canvas,el('span','Candidate '+alias),el('small','Not reviewed'));
            button.onclick=()=>selectGridCandidate(alias);outputs.append(button);
          }
          if(many&&!group.aliases.length)box.append(el('p','No retained image'));
          content.append(box);
        }
        content.append(el('p',aliases.length?`${aliases.length} retained image${aliases.length===1?'':'s'}`:'No retained images'));
        td.append(content);tr.append(td);
      }
      body.append(tr);
    }
    table.append(caption,head,body);syncGridSelection();
  }
  function gridKey(event){
    const button=event.target.closest?.('[data-grid-candidate]');
    if(!button||busy||event.altKey||event.ctrlKey||event.metaKey||event.repeat)return;
    const buttons=gridButtons(),index=buttons.indexOf(button),key=event.key.toLowerCase();
    if(['arrowleft','arrowright','arrowup','arrowdown'].includes(key)){
      event.preventDefault();let next;
      if(key==='arrowleft'||key==='arrowright')next=buttons[index+(key==='arrowleft'?-1:1)];
      else{
        const column=buttons.filter(b=>b.dataset.gridColumn===button.dataset.gridColumn),position=column.indexOf(button),direction=key==='arrowup'?-1:1;
        for(let i=position+direction;i>=0&&i<column.length;i+=direction)if(column[i].dataset.gridRow!==button.dataset.gridRow){next=column[i];break;}
      }
      next?.focus();return;
    }
    const verdict={k:'keep',w:'needs_work',x:'reject'}[key];if(!verdict)return;
    event.preventDefault();selectGridCandidate(button.dataset.gridCandidate);$('#verdict').value=verdict;
    drafts.set($('#candidate').value,assessmentDraft());syncGridSelection();
    $('#assessmentForm').onsubmit({preventDefault(){}});
  }
  function render(){
    if(!state?.exists){$('#start').hidden=false;$('#desk').hidden=true;return;}
    $('#start').hidden=true;$('#desk').hidden=false;$('#phase').textContent=state.finalized?'Decision recorded':state.revealed?'Settings revealed':'Blind review';
    $('#revision').textContent=`Revision ${state.revision} · ${state.candidates.length} candidates`;
    const options=state.candidates.map(c=>[c.alias,'Candidate '+c.alias]);
    selectOptions($('#left'),options,options[0][0]);selectOptions($('#right'),options,options[Math.min(1,options.length-1)][0]);selectOptions($('#candidate'),options,options[0][0]);
    const view=viewDraft||state;cropIds.forEach((id,i)=>{$('#'+id).value=view.crop[i]/100;});$('#background').value=view.background;
    renderGrid();applyPresentation();fillAssessment();$('#progress').replaceChildren(...state.candidates.map(c=>{const row=el('div');row.className='progress-row';row.append(el('b','Candidate '+c.alias),el('span',verdictLabel(c.assessment.verdict)));return row;}));
    $('#decision').hidden=!state.revealed;$('#provenance').hidden=!state.revealed;$('#evidence').textContent=state.revealed?(state.evidence_json??JSON.stringify(state.evidence,null,2)):'';
    selectOptions($('#selected'),[['','None should progress'],...options],state.selected||'');$('#selected').value=selectionDraft??state.selected??'';$('#summary').value=summaryDraft??state.notes;
    $('#characterDecision').value=characterDecisionDraft??state.character_review?.review?.decision??'selected';
    $('#characterDecisionStatus').hidden=!state.character_context;
    $('#characterDecisionStatus').textContent=state.character_review?`${state.character_review.review.decision==='accepted'?'Accepted':'Selected'} for this case by ${state.character_review.review.reviewer} at review revision ${state.character_review.review_revision}. Rights and engine acceptance remain separate.`:'Character acceptance has not been recorded. Every character requirement must pass before selection or acceptance.';
    $('#history').replaceChildren(...state.history.slice(0,40).map(e=>el('li',`r${e.revision} · ${e.action}${e.alias?' · '+e.alias:''} · ${e.reviewer}`)));
    selectOptions($('#restoreRevision'),[['','Choose an earlier assessment'],...state.history.filter(e=>e.action==='rate').map(e=>[String(e.revision),`r${e.revision} · ${e.alias} · ${verdictLabel(e.assessment.verdict)}`])],'');
    $('#downloads').replaceChildren();
    for(const a of state.export?.artifacts||[]){const link=el('a',a.path.endsWith('.zip')?'Download review evidence pack':a.path.endsWith('.png')?'Download matched contact sheet':'Download structured review');link.href=artifactPath(a.url,project)+'?download';link.download='';$('#downloads').append(link);}
    draw().catch(error=>message(error.message,true));controls();
  }
  async function imageFor(url){
    artifactPath(url,project);
    if(!images.has(url)){const image=new Image();image.src=url;images.set(url,image.decode().then(()=>image).catch(error=>{images.delete(url);throw error;}));}
    return images.get(url);
  }
  function holdCompare(){
    if(busy||!state?.exists||heldSide)return false;
    heldSide=$('#mode').value==='pair'?primarySide:$('#mode').value;$('#holdCompare').setAttribute('aria-pressed','true');
    draw().catch(error=>message(error.message,true));return true;
  }
  function releaseCompare(){
    if(!heldSide)return;heldSide=null;$('#holdCompare').setAttribute('aria-pressed','false');draw().catch(error=>message(error.message,true));
  }
  const editing=target=>target?.isContentEditable||!!target?.closest?.('input,textarea,select,[contenteditable]');
  // Space keeps activating a focused control (#1744 review); only the canvases, the page and the hold button itself swap.
  const activates=target=>{const control=target?.closest?.('button,a[href],summary,[role=button]');return !!control&&control.id!=='holdCompare';};
  document.addEventListener('keydown',event=>{
    if(event.key!==' '||event.repeat||event.isComposing||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey||editing(event.target)||activates(event.target))return;
    if(holdCompare())event.preventDefault();
  });
  document.addEventListener('keyup',event=>{if(event.key===' ')releaseCompare();});
  // K/W/X in Pair presentation save the candidate on show through the Grid's own save path (#1752); the Grid's keys stay on its tiles.
  document.addEventListener('keydown',event=>{
    const verdict={k:'keep',w:'needs_work',x:'reject'}[String(event.key).toLowerCase()];
    if(!verdict||presentation!=='pair'||busy||!state?.exists||event.repeat||event.isComposing||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey||editing(event.target))return;
    event.preventDefault();
    if(heldSide){message('Release Space first: the preview shows the other candidate.',true);return;}
    // A rating after the decision would reopen it and clear the winner (review_desk.rate); a shortcut never does that silently (#1760 review).
    if(state.finalized){message('The decision is recorded. Change an assessment with its form and Save to reopen it.',true);return;}
    const mode=$('#mode').value,side=mode==='pair'?primarySide:mode,alias=$('#'+side).value;
    if(drawn[side]!==alias){message('Wait for Candidate '+alias+' to appear before rating it.',true);return;}
    $('#candidate').value=alias;fillAssessment();$('#verdict').value=verdict;
    drafts.set(alias,assessmentDraft());syncGridSelection();
    $('#assessmentForm').onsubmit({preventDefault(){}});
  });
  document.addEventListener('focusin',event=>{if(editing(event.target))releaseCompare();});
  document.addEventListener('visibilitychange',releaseCompare);window.addEventListener('blur',releaseCompare);
  $('#holdCompare').onpointerdown=event=>{if(event.button!==0||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;event.preventDefault();$('#holdCompare').focus({preventScroll:true});holdCompare();};
  for(const type of ['pointerup','pointercancel','pointerleave'])$('#holdCompare').addEventListener(type,releaseCompare);
  window.addEventListener('pointerup',releaseCompare);window.addEventListener('pointercancel',releaseCompare);
  for(const side of ['left','right']){$('#'+side+'Canvas').onfocus=()=>{primarySide=side;};$('#'+side+'Canvas').onpointerdown=()=>{primarySide=side;};}
  async function draw(){
    if(!state?.exists)return;const ticket=++drawSerial;
    const crop=cropFromPercent(cropIds.map(id=>$('#'+id).value)),background=$('#background').value,mode=$('#mode').value;
    $('#leftFigure').hidden=mode==='right';$('#rightFigure').hidden=mode==='left';$('#canvases').classList.toggle('single',mode!=='pair');
    const previews=['left','right'].map(async side=>{
      const candidate=state.candidates.find(c=>c.alias===$('#'+side).value),preview=heldSide===side?state.candidates.find(c=>c.alias===$('#'+(side==='left'?'right':'left')).value):candidate,image=await imageFor(preview.preview_url);if(ticket!==drawSerial)return;
      const canvas=$('#'+side+'Canvas'),ctx=canvas.getContext('2d'),[l,t,r,b]=cropPixels(crop,image.naturalWidth,image.naturalHeight),scale=Math.min(canvas.width/(r-l),canvas.height/(b-t));
      ctx.fillStyle=background==='dark'?'#20232b':'#f1f2f5';ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.drawImage(image,l,t,r-l,b-t,(canvas.width-(r-l)*scale)/2,(canvas.height-(b-t)*scale)/2,(r-l)*scale,(b-t)*scale);
      canvas.setAttribute('aria-label','Candidate '+preview.alias+' · shared cropped preview');
      drawn[side]=preview.alias;
      $('#'+side+'Caption').textContent='Candidate '+candidate.alias+(candidate.source?' · '+candidate.source.filename:' · settings hidden');
    });
    if(presentation==='grid')for(const button of gridButtons())previews.push((async()=>{
      const candidate=state.candidates.find(c=>c.alias===button.dataset.gridCandidate),canvas=button.querySelector('canvas'),ctx=canvas.getContext('2d');
      ctx.fillStyle=background==='dark'?'#20232b':'#f1f2f5';ctx.fillRect(0,0,canvas.width,canvas.height);
      try{
        const image=await imageFor(candidate.preview_url);if(ticket!==drawSerial)return;
        const [l,t,r,b]=cropPixels(crop,image.naturalWidth,image.naturalHeight),scale=Math.min(canvas.width/(r-l),canvas.height/(b-t));
        ctx.drawImage(image,l,t,r-l,b-t,(canvas.width-(r-l)*scale)/2,(canvas.height-(b-t)*scale)/2,(r-l)*scale,(b-t)*scale);
      }catch(error){if(ticket===drawSerial){button.querySelector('small').textContent='Preview unavailable';message('Candidate '+candidate.alias+' preview is unavailable. Check its retained file, then reload.',true);}}
    })());
    await Promise.all(previews);
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
  $('#assessmentForm').oninput=event=>{if(event.target.id==='candidate')return;drafts.set($('#candidate').value,assessmentDraft());syncGridSelection();controls();};
  $('#presentationPair').onclick=()=>setPresentation('pair');$('#presentationGrid').onclick=()=>setPresentation('grid');$('#gridTable').addEventListener('keydown',gridKey);
  $('#assessmentForm').onsubmit=event=>{event.preventDefault();try{const alias=$('#candidate').value,extra=state.character_context?{character_checks:characterValues()}:{};operation('rate',{alias,assessment:assessmentValues(),...extra},()=>drafts.delete(alias));}catch(error){message(error.message,true);}};
  $('#cropForm').oninput=()=>{try{viewDraft={crop:cropFromPercent(cropIds.map(id=>$('#'+id).value)),background:$('#background').value};draw().catch(error=>message(error.message,true));}catch(error){viewDraft={crop:state.crop,background:$('#background').value};message(error.message,true);}controls();};
  $('#cropForm').onsubmit=event=>{event.preventDefault();try{operation('view',{crop:cropFromPercent(cropIds.map(id=>$('#'+id).value)),background:$('#background').value},()=>{viewDraft=null;});}catch(error){message(error.message,true);}};
  for(const button of document.querySelectorAll('[data-crop]'))button.onclick=()=>{const crop={whole:[0,0,10000,10000],centre:[2500,2500,7500,7500],upper:[0,0,10000,5000]}[button.dataset.crop];cropIds.forEach((id,i)=>{$('#'+id).value=crop[i]/100;});$('#cropForm').oninput();};
  for(const side of ['left','right','mode'])$('#'+side).onchange=()=>{releaseCompare();draw().catch(error=>message(error.message,true));};
  $('#swap').onclick=()=>{releaseCompare();const left=$('#left').value;$('#left').value=$('#right').value;$('#right').value=left;draw().catch(error=>message(error.message,true));};
  $('#reveal').onclick=()=>{if(confirm('Reveal recipe settings and source identities? This is recorded and cannot be undone as a blind review.'))operation('reveal');};
  $('#summary').oninput=()=>{summaryDraft=$('#summary').value;controls();};$('#selected').onchange=()=>{selectionDraft=$('#selected').value;controls();};
  $('#characterDecision').onchange=()=>{characterDecisionDraft=$('#characterDecision').value;controls();};
  const decide=selected=>{const extra=state.character_context&&selected?{character_decision:$('#characterDecision').value,reviewer:'local-user'}:{};return operation('finalize',{selected,notes:$('#summary').value,...extra},()=>{summaryDraft=selectionDraft=characterDecisionDraft=null;});};
  $('#decisionForm').onsubmit=event=>{event.preventDefault();if(drafts.size||viewDraft){message('Save candidate assessments and the shared crop before recording the decision.',true);return;}decide($('#selected').value||null);};
  $('#chooseWinner').onclick=async()=>{
    const candidate=winnerTarget(),block=winnerBlock(candidate);if(busy||block){message(block||'Wait for the save to finish.',true);return;}
    const alias=candidate.alias,seen=candidate.assessment;let marked=false;
    if(seen.observations.constraints!=='pass'){   // the rate keeps every other field of the saved assessment and character check as it was
      const failure=await operation('rate',{alias,assessment:{...seen,observations:{...seen.observations,constraints:'pass'}},...(state.character_context?{character_checks:candidate.character_checks}:{})});
      if(failure!=='')return;marked=true;
    }
    const failure=await decide(alias);
    if(failure==='')message('Candidate '+alias+(marked?': stated constraints marked Pass and ':' ')+'recorded as the winner. No generation performed.');
    else message((marked?'Candidate '+alias+' stated constraints were saved as Pass, but the decision was not recorded. ':'The decision was not recorded. ')+(failure||'Try again.'),true);
  };
  $('#export').onclick=()=>operation('export');$('#restoreRevision').onchange=controls;
  $('#restore').onclick=()=>{if(dirty()){message('Save or download your local drafts before restoring an earlier assessment.',true);return;}operation('restore',{source_revision:Number($('#restoreRevision').value)});};
  $('#saveDraft').onclick=()=>{
    const blob=new Blob([JSON.stringify({kind:'unsaved-review-notes',project_id:project,base_revision:state?.revision,assessments:Object.fromEntries(drafts),view:viewDraft,notes:summaryDraft,selected:selectionDraft,character_decision:characterDecisionDraft},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=el('a');link.href=url;link.download='unsaved-review-notes.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
  controls();
  if(!project||!/^[0-9a-f]{32}$/.test(project)){$('#message').classList.toggle('error',true);$('#reload').disabled=true;}
  else operation('inspect');
}());
