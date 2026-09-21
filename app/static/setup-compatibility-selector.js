/* Native selector presentation for reviewed setup compatibility reports. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.StudioSetupCompatibilitySelector=api;
})(globalThis,function(){
  'use strict';

  const OUTER='studio.setup-context-compatibility-report/v1';
  const INNER='studio.setup-compatibility-report/v1';
  const INPUT='studio.setup-compatibility-input/v1';
  const STATUSES=new Set(['recommended','possible','needs_review','incompatible']);
  const AUTHORITY=[
    'provider_accessed','file_hashed','model_downloaded',
    'installation_authorized','backend_switched','selection_changed',
    'generation_submitted',
  ];
  const MOUNTS=new WeakMap();
  let sequence=0;
  const object=value=>!!value&&typeof value==='object'&&!Array.isArray(value);
  const need=(condition,message)=>{if(!condition)throw new TypeError(message);};
  const text=value=>typeof value==='string'&&value.length>0;
  const findings=(value,label)=>{
    need(Array.isArray(value),`Invalid compatibility ${label}`);
    value.forEach(item=>need(object(item)&&text(item.code)&&text(item.message),`Invalid compatibility ${label}`));
  };
  const zeroAuthority=(value,label)=>AUTHORITY.forEach(key=>need(value[key]===false,`Invalid compatibility ${label} authority`));

  function validate(report){
    need(object(report)&&report.format===OUTER,'Invalid compatibility report format');
    need(/^[0-9a-f]{64}$/.test(report.context_sha256||''),'Invalid compatibility context fingerprint');
    zeroAuthority(report,'report');
    need(object(report.precondition)&&text(report.precondition.backend_id)&&text(report.precondition.runtime),'Invalid compatibility precondition');
    need(typeof report.precondition.switching==='boolean','Invalid compatibility precondition');
    need(object(report.compatibility_input)&&report.compatibility_input.format===INPUT,'Invalid compatibility input');
    need(Array.isArray(report.compatibility_input.candidates),'Invalid compatibility input candidates');
    need(object(report.compatibility)&&report.compatibility.format===INNER,'Invalid compatibility decision report');
    zeroAuthority(report.compatibility,'decision');
    need(Array.isArray(report.compatibility.candidates),'Invalid compatibility candidates');

    const inputs=new Map();
    for(const candidate of report.compatibility_input.candidates){
      need(object(candidate)&&text(candidate.id)&&text(candidate.name)&&text(candidate.identity),'Invalid compatibility input candidate');
      need(!inputs.has(candidate.id),'Duplicate compatibility input candidate');
      inputs.set(candidate.id,candidate);
    }
    const rows=new Set(),ranks=new Set();
    for(const row of report.compatibility.candidates){
      need(object(row)&&text(row.id)&&text(row.name)&&text(row.identity),'Invalid compatibility candidate');
      need(!rows.has(row.id),'Duplicate compatibility candidate');rows.add(row.id);
      const source=inputs.get(row.id);
      need(source&&source.name===row.name&&source.identity===row.identity,'Compatibility candidate does not match input');
      need(STATUSES.has(row.status),'Invalid compatibility status');
      const normally=row.status==='recommended'||row.status==='possible';
      need(row.selectable===normally,'Invalid compatibility selectable state');
      need(row.expert_override_required===(row.status==='needs_review'),'Invalid compatibility expert override state');
      if(row.status==='recommended'){
        need(Number.isSafeInteger(row.recommendation_rank)&&row.recommendation_rank>0,'Invalid compatibility recommendation rank');
        need(!ranks.has(row.recommendation_rank),'Duplicate compatibility recommendation rank');ranks.add(row.recommendation_rank);
      }else need(row.recommendation_rank===null,'Invalid compatibility recommendation rank');
      findings(row.hard_conflicts,'hard conflicts');
      findings(row.unknowns,'unknowns');
      findings(row.limitations,'limitations');
      need(object(row.evidence_summary),'Invalid compatibility evidence summary');
    }
    need(rows.size===inputs.size,'Compatibility candidate set does not match input');
    return report;
  }

  function reason(row){
    const records=row.status==='incompatible'?row.hard_conflicts:row.status==='needs_review'?row.unknowns:row.status==='possible'?row.limitations:[];
    const messages=records.map(item=>item.message).filter(Boolean);
    if(messages.length)return messages.join(' ');
    if(row.status==='recommended')return 'Exact hard requirements passed and the retained evidence supports this recommendation.';
    if(row.status==='possible')return 'Known hard requirements pass, but the evidence does not justify a recommendation.';
    if(row.status==='needs_review')return 'A required compatibility fact is unknown and needs explicit expert review.';
    return 'A known hard compatibility conflict prevents normal selection.';
  }

  function project(report){
    validate(report);
    return report.compatibility.candidates.map(row=>{
      const prefix=row.status==='recommended'?`Recommended #${row.recommendation_rank}`:row.status==='possible'?'Possible':row.status==='needs_review'?'Needs review':'Incompatible';
      return Object.freeze({
        id:row.id,
        name:row.name,
        identity:row.identity,
        status:row.status,
        label:`${prefix} · ${row.name}`,
        reason:reason(row),
        normalSelectable:row.status==='recommended'||row.status==='possible',
        expertSelectable:row.status!=='incompatible',
        recommendationRank:row.recommendation_rank,
      });
    });
  }

  function describedBy(select){
    return String(select.getAttribute?.('aria-describedby')||select.attributes?.['aria-describedby']||'');
  }

  function decorate(select,report,{status=null,expert=false}={}){
    need(select&&select.options,'A native selector is required');
    const rows=project(report),byId=new Map(rows.map(row=>[row.id,row]));
    const options=Array.from(select.options);
    for(const option of options){
      const base=option.dataset?.compatibilityLabel||String(option.textContent??option.value??'');
      if(option.dataset&&!option.dataset.compatibilityLabel)option.dataset.compatibilityLabel=base;
      const row=byId.get(String(option.value));
      if(row){
        option.textContent=row.label;
        option.disabled=expert?!row.expertSelectable:!row.normalSelectable;
        if(option.dataset)option.dataset.compatibilityStatus=row.status;
      }else{
        option.textContent=`Needs review · ${base}`;
        option.disabled=true;
        if(option.dataset)option.dataset.compatibilityStatus='unreported';
      }
    }
    const selectedOption=options.find(option=>String(option.value)===String(select.value))||options.find(option=>option.selected);
    const selected=selectedOption?byId.get(String(selectedOption.value))||null:null;
    const selectable=selected?expert?selected.expertSelectable:selected.normalSelectable:false;
    if(selectable)select.removeAttribute?.('aria-invalid');
    else select.setAttribute?.('aria-invalid','true');
    if(status){
      status.hidden=false;
      if(selected){
        const hold=selected.status==='needs_review'&&!expert?' Enable explicit expert review to make this choice available.':'';
        status.textContent=`${selected.label}. ${selected.reason}${hold}`;
      }else if(selectedOption){
        status.textContent='Needs review. The selected value was not included in this exact compatibility report.';
      }else status.textContent='Choose a reviewed option to see its compatibility explanation.';
      if(status.id){
        const ids=new Set(describedBy(select).split(/\s+/).filter(Boolean));
        ids.add(status.id);select.setAttribute?.('aria-describedby',[...ids].join(' '));
      }
    }
    if(select.dataset)select.dataset.compatibilityContext=report.context_sha256;
    return Object.freeze({rows:Object.freeze(rows),selected,expert:Boolean(expert),contextSha256:report.context_sha256});
  }

  function restoreAttribute(element,name,value){
    if(value===null||value===undefined)element.removeAttribute(name);
    else element.setAttribute(name,value);
  }

  function mount(select,report,{container=null,label='Compatibility review'}={}){
    validate(report);
    need(select?.ownerDocument&&select.options,'Mount requires a native select element');
    MOUNTS.get(select)?.destroy();
    const document=select.ownerDocument;
    const host=container||document.createElement('div');
    if(!container){
      need(select.parentNode,'Mount requires an attached selector or a container');
      select.insertAdjacentElement('afterend',host);
    }
    const wrapper=document.createElement('section');
    wrapper.className='setup-compatibility-selector';
    wrapper.dataset.setupCompatibility='';
    wrapper.setAttribute('aria-label',String(label));
    const heading=document.createElement('strong');heading.textContent=String(label);
    const status=document.createElement('p');
    status.id=`setupCompatibilityStatus${++sequence}`;
    status.dataset.compatibilityStatus='';
    status.setAttribute('role','status');
    status.setAttribute('aria-live','polite');
    const expertLabel=document.createElement('label');
    expertLabel.className='setup-compatibility-expert';
    const expert=document.createElement('input');
    expert.type='checkbox';
    const expertText=document.createElement('span');
    expertText.textContent='Show Needs review choices for expert review';
    expertLabel.append(expert,expertText);
    const boundary=document.createElement('small');
    boundary.textContent='Incompatible and unreported choices remain unavailable. This review does not change the current selection.';
    wrapper.append(heading,status,expertLabel,boundary);
    host.append(wrapper);

    const selectSnapshot={
      describedBy:select.getAttribute('aria-describedby'),
      invalid:select.getAttribute('aria-invalid'),
      context:select.dataset.compatibilityContext,
      hadContext:Object.hasOwn(select.dataset,'compatibilityContext'),
      hadClass:select.classList.contains('setup-compatibility-select'),
    };
    const optionSnapshots=Array.from(select.options).map(option=>({
      option,
      text:option.textContent,
      disabled:option.disabled,
      label:option.dataset.compatibilityLabel,
      hadLabel:Object.hasOwn(option.dataset,'compatibilityLabel'),
      status:option.dataset.compatibilityStatus,
      hadStatus:Object.hasOwn(option.dataset,'compatibilityStatus'),
    }));
    select.classList.add('setup-compatibility-select');
    expertLabel.hidden=!report.compatibility.candidates.some(row=>row.status==='needs_review');
    let destroyed=false,current=null;
    const render=()=>{if(!destroyed)current=decorate(select,report,{status,expert:expert.checked});};
    const onSelect=()=>render();
    const onExpert=()=>render();
    select.addEventListener('change',onSelect);
    expert.addEventListener('change',onExpert);
    render();

    const controller={
      get current(){return current;},
      destroy(){
        if(destroyed)return;
        destroyed=true;
        select.removeEventListener('change',onSelect);
        expert.removeEventListener('change',onExpert);
        for(const snapshot of optionSnapshots){
          snapshot.option.textContent=snapshot.text;
          snapshot.option.disabled=snapshot.disabled;
          if(snapshot.hadLabel)snapshot.option.dataset.compatibilityLabel=snapshot.label;
          else delete snapshot.option.dataset.compatibilityLabel;
          if(snapshot.hadStatus)snapshot.option.dataset.compatibilityStatus=snapshot.status;
          else delete snapshot.option.dataset.compatibilityStatus;
        }
        restoreAttribute(select,'aria-describedby',selectSnapshot.describedBy);
        restoreAttribute(select,'aria-invalid',selectSnapshot.invalid);
        if(selectSnapshot.hadContext)select.dataset.compatibilityContext=selectSnapshot.context;
        else delete select.dataset.compatibilityContext;
        if(!selectSnapshot.hadClass)select.classList.remove('setup-compatibility-select');
        wrapper.remove();
        if(!container&&!host.childNodes.length)host.remove();
        if(MOUNTS.get(select)===controller)MOUNTS.delete(select);
      },
    };
    Object.freeze(controller);
    MOUNTS.set(select,controller);
    return controller;
  }

  return Object.freeze({validate,project,decorate,mount});
});
