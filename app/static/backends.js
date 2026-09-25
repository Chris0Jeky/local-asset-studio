let backendSwitching=false, backendActive=null, backendReadEpoch=0, backendReadPending=null;
function renderRecovery(recovery={}) {
  $('#recoveryStatus').textContent=recovery.message || (recovery.enabled ? 'Runtime recovery is watching the selected backend.' : 'Runtime recovery is disabled.');
  $('#retryRecovery').hidden=!recovery.enabled || recovery.status!=='breaker-open';
}
// Capture at acceptance, not request start. Empty settings are authored values too.
function backendEditorSnapshot(){
  const fields=[['positive',$('#positive')],['negative',$('#negative')],...controlKeys.map(key=>[key,getControl(key)]),['mode',$('#i2vMode')]].filter(([,input])=>input);
  const active=document.activeElement,focus=fields.find(([,input])=>input===active)?.[0];
  const selection=focus&&typeof active.selectionStart==='number'?[active.selectionStart,active.selectionEnd,active.selectionDirection]:null;
  return {fields:fields.map(([key,input])=>[key,input.value]),focus,selection};
}
function restoreBackendEditor(snapshot){
  const input=key=>key==='positive'?$('#positive'):key==='negative'?$('#negative'):key==='mode'?$('#i2vMode'):getControl(key);
  const mode=snapshot.fields.find(([key])=>key==='mode')?.[1];
  if(mode&&selected.i2v_modes?.some(spec=>spec.id===mode))applyI2VMode(mode,false);
  for(const [key,value] of snapshot.fields){const target=input(key);if(target)target.value=value;}
  const focused=snapshot.focus&&input(snapshot.focus);
  if(focused){focused.focus({preventScroll:true});if(snapshot.selection)focused.setSelectionRange(...snapshot.selection);}
}
// An obsolete unresolved read must not hold the current polling guard.
async function refreshBackends() {
  const epoch=++backendReadEpoch,current=()=>epoch===backendReadEpoch;backendReadPending=epoch;
  try {
    const state=await api('/api/backends');if(!current())return;
    const switching=state?.busy===true&&state.operation?.status==='running'&&typeof state.operation?.target==='string';
    if(!Array.isArray(state?.profiles)||typeof state.active!=='string'||typeof state.busy!=='boolean'||(state.busy&&state.operation?.status==='running'&&typeof state.operation?.target!=='string'))throw Error('The backend status is incomplete. Your draft was kept.');
    const changed=backendActive!==null&&backendActive!==state.active;
    if(changed){
      const next=await api('/api/catalog');if(!current())return;
      if(!Array.isArray(next?.presets))throw Error('The refreshed recipe catalogue is unavailable. Your draft was kept.');
      const id=selected?.id,replacement=id?next.presets.find(p=>p.id===id):null;
      if(id&&!replacement)throw Error('The selected recipe is absent from the refreshed catalogue. Your draft was kept.');
      const snapshot=backendEditorSnapshot();
      catalog=next;if(replacement)selected=replacement;
      renderPresets();if(selected){renderSelected();restoreBackendEditor(snapshot);}
    }
    backendSwitching=state.busy;
    const select=$('#backendChoice'),keep=select.value;
    select.innerHTML=state.profiles.map(p=>'<option value="'+esc(p.id)+'" '+(!p.installed?'disabled':'')+'>'+esc(p.name)+(p.online?' · online':'')+'</option>').join('');
    select.value=switching?state.operation.target:(state.busy?state.active:(backendActive===null?state.active:(keep||state.active)));
    select.disabled=state.busy;$('#switchBackend').disabled=state.busy;
    const busyMessage='A local operation is running. Switching is disabled until it finishes.';
    $('#backendStatus').textContent=switching?(state.operation.message||'One model environment at a time. Switching never starts a generation.'):(state.busy?busyMessage:(state.operation?.message||'One model environment at a time. Switching never starts a generation.'));
    renderRecovery(state.recovery);
    backendActive=state.active;$('#activeBackend').textContent=state.profiles.find(p=>p.active)?.name||'';
    updateReady();
    if(changed){await health();if(current()&&view==='models')await refreshLibrary();}
  } catch(e){if(current())$('#backendStatus').textContent=e.message;}
  finally{if(backendReadPending===epoch)backendReadPending=null;}
}
$('#switchBackend').onclick=async()=>{
  backendReadEpoch++;backendSwitching=true;updateReady();$('#switchBackend').disabled=true;
  try{await post('/api/backends/switch',{id:$('#backendChoice').value});await refreshBackends();}
  catch(e){backendSwitching=false;$('#switchBackend').disabled=false;$('#backendStatus').textContent=e.message;updateReady();}
};
$('#retryRecovery').onclick=async()=>{try{await post('/api/runtime-recovery/retry',{});await refreshBackends();}catch(e){$('#recoveryStatus').textContent=e.message;}};
refreshBackends();setInterval(()=>{if(backendSwitching&&backendReadPending!==backendReadEpoch)refreshBackends();},3000);
