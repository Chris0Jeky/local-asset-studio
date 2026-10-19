let backendSwitching=false, backendActive=null, backendReadEpoch=0, backendReadPending=null, backendInventoryPending=false, backendSwitchEpoch=0;
let backendResolution=null,backendResolving=false;
function updateBackendResolution(){
  $('#resolveBackendSwitch').disabled=backendResolving||!backendResolution||!$('#backendStudiosClosed').checked||!$('#backendRuntimesInspected').checked;
}
function renderBackendResolution(shared){
  const next=shared?.resolvable&&typeof shared.sha256==='string'&&/^[a-f0-9]{64}$/.test(shared.sha256)?shared.sha256:null;
  if(backendResolution!==next){$('#backendStudiosClosed').checked=false;$('#backendRuntimesInspected').checked=false;}
  backendResolution=next;
  if(!next&&[$('#backendStudiosClosed'),$('#backendRuntimesInspected'),$('#resolveBackendSwitch')].includes(document.activeElement)){
    const status=$('#backendStatus');status.tabIndex=-1;status.focus({preventScroll:true});
  }
  $('#backendResolution').hidden=!next;updateBackendResolution();
}
function renderRecovery(recovery={}) {
  $('#recoveryStatus').textContent=recovery.message || (recovery.enabled ? 'Runtime recovery is watching the selected backend.' : 'Runtime recovery is disabled.');
  const retry=$('#retryRecovery'),hide=!recovery.enabled || recovery.status!=='breaker-open';
  if(hide&&document.activeElement===retry){const status=$('#recoveryStatus');status.tabIndex=-1;status.focus({preventScroll:true});}retry.hidden=hide;
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
    const sharedBlock=state.shared_state?.blocker||state.state_issue||'';
    backendSwitching=state.busy||!!sharedBlock;
    const select=$('#backendChoice'),keep=select.value;
    select.innerHTML=state.profiles.map(p=>'<option value="'+esc(p.id)+'" '+(!p.installed?'disabled':'')+'>'+esc(p.name)+(p.online?' · online':'')+'</option>').join('');
    select.value=switching?state.operation.target:(state.busy?state.active:(backendActive===null?state.active:(keep||state.active)));
    if(backendSwitching&&[select,$('#switchBackend')].includes(document.activeElement)){const status=$('#backendStatus');status.tabIndex=-1;status.focus({preventScroll:true});}
    select.disabled=backendSwitching;$('#switchBackend').disabled=backendSwitching;
    const busyMessage='A local operation is running. Switching is disabled until it finishes.';
    $('#backendStatus').textContent=switching?(state.operation.message||'One model environment at a time. Switching never starts a generation.'):(state.busy?busyMessage:(sharedBlock||state.operation?.message||'One model environment at a time. Switching never starts a generation.'));
    renderBackendResolution(state.busy?null:state.shared_state);
    renderRecovery(state.recovery);
    backendActive=state.active;$('#activeBackend').textContent=state.profiles.find(p=>p.active)?.name||'';
    // The Models disclosure is folded by default; a running switch keeps it open so its progress and the disabled controls stay visible.
    const activeName=state.profiles.find(p=>p.active)?.name||'',panel=$('.environment-panel'),summary=$('#envSummary');if(summary)summary.textContent=switching?'Switching to '+(state.profiles.find(p=>p.id===state.operation.target)?.name||state.operation.target)+'…':activeName?'Active: '+activeName+' · switching is always explicit':'Switching is always explicit';if(backendSwitching&&panel)panel.open=true;
    updateReady();
    if(changed||backendInventoryPending){
      backendInventoryPending=true;
      if(typeof loadAtelier==='function')await loadAtelier(current,true);if(!current())return;
      backendInventoryPending=false;
      // The catalogue redraw above ran before this inventory arrived, so the adapter selects and the already-drawn Vary buttons are still the previous backend's.
      if(selected&&typeof renderLoraSlots==='function'){const snapshot=backendEditorSnapshot();renderLoraSlots();restoreBackendEditor(snapshot);}
      if(typeof refreshCarriedVary==='function')refreshCarriedVary();
      await health();if(current()&&view==='models')await refreshLibrary();
    }
  } catch(e){if(current())$('#backendStatus').textContent=e.message;}
  finally{if(backendReadPending===epoch)backendReadPending=null;}
}
$('#switchBackend').onclick=async()=>{
  const attempt=++backendSwitchEpoch;backendReadEpoch++;backendSwitching=true;updateReady();if(document.activeElement===$('#switchBackend')){const status=$('#backendStatus');status.tabIndex=-1;status.textContent='Switching model environment...';status.focus({preventScroll:true});}$('#switchBackend').disabled=true;
  try{await post('/api/backends/switch',{id:$('#backendChoice').value});await refreshBackends();}
  catch(e){if(attempt!==backendSwitchEpoch)return;const read=backendReadEpoch+1;await refreshBackends();if(attempt===backendSwitchEpoch&&read===backendReadEpoch)$('#backendStatus').textContent=e.message;}
};
$('#retryRecovery').onclick=async()=>{try{await post('/api/runtime-recovery/retry',{});await refreshBackends();}catch(e){$('#recoveryStatus').textContent=e.message;}};
$('#backendStudiosClosed').onchange=updateBackendResolution;$('#backendRuntimesInspected').onchange=updateBackendResolution;
$('#resolveBackendSwitch').onclick=async()=>{
  if(backendResolving||!backendResolution||!$('#backendStudiosClosed').checked||!$('#backendRuntimesInspected').checked)return;
  const expected=backendResolution,attempt=++backendSwitchEpoch;backendResolving=true;backendReadEpoch++;
  if(document.activeElement===$('#resolveBackendSwitch')){const status=$('#backendStatus');status.tabIndex=-1;status.textContent='Recording the inspected switch resolution…';status.focus({preventScroll:true});}
  updateBackendResolution();
  try{await post('/api/backends/resolve-switch',{expected_sha256:expected,acknowledge_studios_closed:true,acknowledge_runtimes_inspected:true});await refreshBackends();}
  catch(e){if(attempt!==backendSwitchEpoch)return;const read=backendReadEpoch+1;await refreshBackends();if(attempt===backendSwitchEpoch&&read===backendReadEpoch)$('#backendStatus').textContent=e.message;}
  finally{backendResolving=false;updateBackendResolution();}
};
refreshBackends();setInterval(()=>{if(backendSwitching&&backendReadPending!==backendReadEpoch)refreshBackends();},3000);
