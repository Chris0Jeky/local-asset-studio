/* Schema discovery is read-only. This page prepares plans; Production owns explicit Start. */
(function(global){
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label=key=>key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
  function parameters(spec,values){
    const result={};
    for(const [key,rule] of Object.entries(spec)){
      const raw=String(values[key]??'').trim(),value=Number(raw);
      if(!raw||!Number.isFinite(value))throw Error(label(key)+' must be a finite number.');
      if(rule.type==='int'&&!Number.isInteger(value))throw Error(label(key)+' must be an integer.');
      if(value<rule.min||value>rule.max)throw Error(label(key)+' must be between '+rule.min+' and '+rule.max+'.');
      result[key]=value;
    }
    return result;
  }
  global.StudioProcedural={parameters};
  if(typeof document==='undefined')return;
  const $=selector=>document.querySelector(selector),drafts={};
  let catalog=null,current=null,busy=false;
  const message=(text,error=false)=>{$('#proceduralStatus').textContent=text;$('#proceduralStatus').classList.toggle('error',error);};
  function sync(){
    $('#proceduralFields').disabled=busy||!catalog;$('#proceduralRefresh').disabled=busy;
    const ready=catalog?.runtime.ready===true;
    $('#proceduralPrepare').disabled=busy||!ready;
    $('#proceduralPrepare').title=ready?'Saves a plan; start its build separately.':'Configure Blender 5.4, Node and the pinned validator first.';
    $('#proceduralGodot').disabled=!catalog?.runtime.godot_available;
  }
  function values(){return Object.fromEntries(Object.keys(catalog.generators[current].params).map(key=>[key,$('#proceduralParam-'+key).value]));}
  function renderGenerator(){
    if(current)drafts[current]=values();
    current=$('#proceduralGenerator').value;const spec=catalog.generators[current];
    $('#proceduralDescription').textContent=spec.description;$('#proceduralUnits').textContent=catalog.units;
    $('#proceduralParams').innerHTML=Object.entries(spec.params).map(([key,rule])=>'<div><label for="proceduralParam-'+esc(key)+'">'+esc(label(key))+'</label><input id="proceduralParam-'+esc(key)+'" type="number" required min="'+rule.min+'" max="'+rule.max+'" step="'+(rule.type==='int'?'1':'any')+'" aria-describedby="proceduralHelp-'+esc(key)+'"><small id="proceduralHelp-'+esc(key)+'">'+esc(rule.min+'–'+rule.max+(rule.type==='int'?' · whole number':'')+(rule.doc?' · '+rule.doc:''))+'</small></div>').join('');
    for(const [key,rule] of Object.entries(spec.params))$('#proceduralParam-'+key).value=drafts[current]?.[key]??String(rule.default);
    $('#proceduralConstraints').hidden=!spec.constraints.length;
    $('#proceduralRules').innerHTML=spec.constraints.map(rule=>'<li>'+esc(rule.doc)+'</li>').join('');
  }
  async function request(path,body){
    let response,data;
    try{response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
    catch(_){throw Error('Studio did not return a response.');}
    if(!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type')||''))throw Error('Studio returned an unreadable response.');
    try{data=await response.json();}catch(_){throw Error('Studio returned an unreadable response.');}
    if(!response.ok){const error=Error(typeof data?.error==='string'?data.error:'The request was refused.');error.refused=response.status>=400&&response.status<500;throw error;}
    return data;
  }
  async function refresh(){
    if(busy)return;
    if(current&&catalog)drafts[current]=values();
    busy=true;sync();
    try{
      const data=await request('/api/procedural');
      if(!data||typeof data.generators!=='object'||!Object.keys(data.generators).length||typeof data.runtime?.ready!=='boolean'||!Array.isArray(data.runtime.missing))throw Error('Procedural catalog unavailable.');
      const selected=current;current=null;catalog=data;
      $('#proceduralGenerator').innerHTML=Object.entries(catalog.generators).map(([key,spec])=>'<option value="'+esc(key)+'">'+esc(spec.label||label(key))+'</option>').join('');
      $('#proceduralGenerator').value=selected&&catalog.generators[selected]?selected:Object.keys(catalog.generators)[0];renderGenerator();
      $('#proceduralRuntime').innerHTML='<p class="'+(catalog.runtime.ready?'procedural-runtime-ready':'')+'"><strong>'+(catalog.runtime.ready?'Configured files found':'Setup needed before preparation')+'</strong></p>'+(catalog.runtime.missing.length?'<ul>'+catalog.runtime.missing.map(item=>'<li>'+esc(item)+'</li>').join('')+'</ul>':'')+'<p class="muted">'+esc(catalog.runtime.note)+'</p>';
      if(!catalog.runtime.godot_available)$('#proceduralGodot').checked=false;
      $('#proceduralGodotHelp').textContent=(catalog.runtime.godot_available?'':'Configure Godot to enable this option. ')+'Without this check, engine verification stays incomplete.';
      message('Choose a generator and check its settings. Nothing has been built.');
    }catch(error){catalog=null;$('#proceduralRuntime').textContent='Setup could not be checked. Choose Check setup when Studio is available.';message(error.message,true);}
    finally{busy=false;sync();}
  }
  function intent(){return {name:$('#proceduralName').value.trim(),generator:current,params:parameters(catalog.generators[current].params,values()),render:$('#proceduralRender').checked,verify_engine:$('#proceduralGodot').checked};}
  async function submit(prepare){
    if(busy||!catalog)return;
    if(prepare&&!catalog.runtime.ready){message('Configure the required tools, then choose Check setup. No plan was prepared.',true);return;}
    if(!$('#proceduralForm').reportValidity())return;
    let payload;
    try{payload=intent();}catch(error){message(error.message,true);return;}
    busy=true;sync();message(prepare?'Preparing the pinned plan…':'Checking dimensions and constraints…');
    try{
      const result=await request(prepare?'/api/procedural':'/api/procedural/validate',payload);
      if(prepare){
        if(!/^[a-f0-9]{32}$/.test(result?.id)||result.kind!=='procedural'||result.state?.status!=='planned')throw Error('Studio returned an unreadable preparation result.');
        $('#proceduralPrepared').innerHTML='<p><strong>'+esc(result.name)+'</strong> is prepared.</p><a class="primary" href="/?plan='+result.id+'#production">Open build plan →</a><p>Choose <strong>Start build</strong> there when ready. This plan keeps the settings you just prepared.</p>';
        message('Plan prepared. Open its build plan to start explicitly.');
      }else{if(result?.generation_submitted!==false||!result.intent)throw Error('Studio returned an unreadable validation result.');message('Settings are valid. Geometry and engine checks run only after Start build.');}
    }catch(error){message(prepare&&!error.refused?'Preparation outcome is not confirmed. Check Comparisons before preparing again. '+error.message:error.message,true);}
    finally{busy=false;sync();}
  }
  $('#proceduralGenerator').onchange=()=>{renderGenerator();message('Settings changed. Check them before preparing a new plan.');};
  $('#proceduralForm').onsubmit=event=>{event.preventDefault();return submit(true);};
  $('#proceduralCheck').onclick=()=>submit(false);$('#proceduralRefresh').onclick=refresh;
  refresh();
})(globalThis);
