'use strict';
const $=s=>document.querySelector(s),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let voiceBusy=false,voiceTimer=null,voiceReady=false,voiceEpoch=0;
const message=(text,error=false)=>{$('#voiceStatus').textContent=text;$('#voiceStatus').classList.toggle('error',error);};
const unavailable=()=>Error('Voice API unavailable. Check that Studio is running, then choose Refresh.');
async function request(path,body){
  let response,data;
  try{response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});}catch(_){throw unavailable();}
  const type=response.headers?.get('Content-Type');
  if(type&&!/^application\/json(?:\s*;|$)/i.test(type))throw unavailable();
  try{data=await response.json();}catch(_){throw unavailable();}
  if(!response.ok)throw Error(typeof data?.error==='string'?data.error:'Voice operation refused. Inspect saved takes before trying again.');
  return data;
}
async function refresh(){
  const epoch=++voiceEpoch;voiceReady=false;$('#voicePrepare').disabled=true;
  if(voiceTimer)clearTimeout(voiceTimer);voiceTimer=null;
  try{
    const data=await request('/api/voice-baseline');if(epoch!==voiceEpoch)return;
    if(typeof data?.capabilities?.configured!=='boolean'||!Array.isArray(data.projects)||data.projects.some(p=>!p||typeof p.id!=='string'||!p.state||typeof p.state.status!=='string'))throw unavailable();
    voiceReady=data.capabilities.configured;
    $('#voiceCapability').textContent=voiceReady?'Isolated voice bundle configured. Prepare checks the exact model and runtime.':'Install and configure the isolated voice bundle to prepare a take.';
  $('#voiceTakes').innerHTML=data.projects.map(p=>{const active=['queued','running'].includes(p.state.status),resumable=p.voice_resume?.eligible===true;return '<article class="panel voice-take"><h3>'+esc(p.name)+'</h3><p>'+esc(p.state.status)+' · '+esc(p.state.message)+'</p><div class="voice-actions">'+(p.state.status==='planned'?'<button class="primary" data-start="'+p.id+'">Generate CPU take</button>':'')+(active?'<button data-stop="'+p.id+'">Cancel owned take</button>':'')+(resumable?'<button data-resume="'+p.id+'">Resume unstarted take</button>':'')+'<a href="/api/production/'+p.id+'/files/plan.json?download">Saved recipe</a><a href="/#assets">Open Workspace</a></div>'+(p.state.artifacts||[]).filter(a=>a.role==='audio').map(a=>'<div class="voice-audio"><b>'+esc(a.path.split('/').pop())+'</b><audio controls preload="none" src="'+esc(a.url)+'"></audio><a href="'+esc(a.url)+'?download">Download WAV</a></div>').join('')+'</article>';}).join('')||'<p class="muted">No takes prepared. Nothing is generated on page load.</p>';
  voiceTimer=data.projects.some(p=>['queued','running'].includes(p.state.status))?setTimeout(()=>refresh().catch(e=>message(e.message,true)),1000):null;
    if(!voiceBusy)message('Saved takes refreshed. Refresh does not start generation.');
  }catch(error){
    if(epoch!==voiceEpoch)return;
    voiceReady=false;$('#voiceCapability').textContent='Voice API unavailable. Refresh to check capabilities and saved takes.';
    if(!$('#voiceTakes').innerHTML)$('#voiceTakes').innerHTML='<p class="muted">Saved takes unavailable. Nothing is generated on page load.</p>';
    throw error;
  }finally{if(epoch===voiceEpoch)$('#voicePrepare').disabled=!voiceReady||voiceBusy;}
}
$('#voiceForm').onsubmit=async event=>{event.preventDefault();if(voiceBusy)return;if(!voiceReady){message('Voice preparation unavailable. Refresh to confirm the configured bundle. No request was sent.',true);return;}voiceBusy=true;$('#voicePrepare').disabled=true;try{const lines=$('#voiceLines').value.split(/\n+/).map(t=>t.trim()).filter(Boolean).map((text,i)=>({id:'line-'+(i+1),text}));await request('/api/voice-baseline',{name:$('#voiceName').value,speaker_id:$('#voiceSpeaker').value,lines});message('Take prepared. Choose Generate CPU take when ready.');await refresh();}catch(e){message(e.message+' Inspect saved takes before repeating an uncertain request.',true);}finally{voiceBusy=false;$('#voicePrepare').disabled=!voiceReady;}};
$('#voiceTakes').onclick=async event=>{const button=event.target.closest('[data-start],[data-stop],[data-resume]');if(!button||voiceBusy)return;const action=button.dataset.start?'start':button.dataset.stop?'stop':'resume',identifier=button.dataset.start||button.dataset.stop||button.dataset.resume;voiceBusy=true;button.disabled=true;try{await request('/api/production/'+identifier+'/'+action,{});await refresh();}catch(e){message(e.message+' Inspect the existing take before trying again.',true);}finally{voiceBusy=false;$('#voicePrepare').disabled=!voiceReady;}};
$('#voiceRefresh').onclick=()=>refresh().catch(e=>message(e.message,true));refresh().catch(e=>message(e.message,true));
