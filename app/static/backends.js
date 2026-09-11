let backendSwitching=false, backendActive=null;
async function refreshBackends() {
  try {
    const state=await api('/api/backends');backendSwitching=state.busy;
    const select=$('#backendChoice'), keep=select.value;
    select.innerHTML=state.profiles.map(p=>'<option value="'+esc(p.id)+'" '+(!p.installed?'disabled':'')+'>'+esc(p.name)+(p.online?' · online':'')+'</option>').join('');
    select.value=state.busy?state.operation.target:(backendActive===null?state.active:(keep||state.active));
    select.disabled=state.busy;$('#switchBackend').disabled=state.busy;
    $('#backendStatus').textContent=state.operation?.message||'One model environment at a time. Switching never starts a generation.';
    if(backendActive!==null&&backendActive!==state.active){
      const id=selected?.id, controls=selected?values():{};
      catalog=await api('/api/catalog');selected=catalog.presets.find(p=>p.id===id)||catalog.presets[0];
      renderPresets();renderSelected();
      for(const [key,value] of Object.entries(controls)){const input=key==='positive'?$('#positive'):key==='negative'?$('#negative'):getControl(key);if(input)input.value=value;}
      await health();if(view==='models')await refreshLibrary();
    }
    backendActive=state.active;$('#activeBackend').textContent=state.profiles.find(p=>p.active)?.name||'';
    updateReady();
  } catch(e){$('#backendStatus').textContent=e.message;}
}
$('#switchBackend').onclick=async()=>{
  backendSwitching=true;updateReady();$('#switchBackend').disabled=true;
  try{await post('/api/backends/switch',{id:$('#backendChoice').value});await refreshBackends();}
  catch(e){backendSwitching=false;$('#switchBackend').disabled=false;$('#backendStatus').textContent=e.message;updateReady();}
};
refreshBackends();setInterval(()=>{if(backendSwitching)refreshBackends();},3000);
