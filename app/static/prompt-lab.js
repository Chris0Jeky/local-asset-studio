'use strict';
const $=id=>document.getElementById(id);let registry=[],result=null,proposed=null,draftVersion=0,buildTimer=null;
let intent={schema_version:1,id:'creative-brief',task:'image',brief:$('brief').value,facets:{},tags:[],avoid:[],constraints:[],references:[],verbatim:{},parameters:{},locked:['verbatim']};
const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
async function api(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');return data;}
// The page rebuilds itself on every edit. Compiling is a pure projection: it never submits a job.
function announce(){if(typeof CustomEvent==='function'&&typeof document.dispatchEvent==='function')document.dispatchEvent(new CustomEvent('studio-prompt-state'));}
function schedule(){if(typeof setTimeout!=='function')return;clearTimeout(buildTimer);buildTimer=setTimeout(()=>{buildTimer=null;build();},400);}
function resetBuild(){draftVersion++;result=null;$('export-result').disabled=true;$('export-reason').textContent='Build the prompt first.';$('state').textContent='Rebuilding…';announce();}
function invalidate(){resetBuild();schedule();}
// An explicit repair rebuilds once and keeps its own explanation; no debounced rebuild follows to wipe it.
function rebuild(note){resetBuild();build(note);}
function collect(){intent.brief=$('brief').value;for(const k of ['subject','style','motion']){if($(k).value.trim())intent.facets[k]=$(k).value;else delete intent.facets[k];}for(const k of ['tags','avoid'])if($(k).value!==intent[k].join(', '))intent[k]=$(k).value.split(',').map(x=>x.trim()).filter(Boolean);if(intent.task==='voice')intent.verbatim.text=$('words').value;if(intent.task==='music')intent.verbatim.lyrics=$('words').value;}
function show(){ $('brief').value=intent.brief;for(const k of ['subject','style','motion'])$(k).value=intent.facets[k]||'';$('tags').value=intent.tags.join(', ');$('avoid').value=intent.avoid.join(', ');words();references();notes();}
function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
for(const k of ['brief','subject','style','motion','tags','avoid','words'])$(k).addEventListener('input',invalidate);
$('profile').addEventListener('change',()=>{const p=registry.find(x=>x.id===$('profile').value);collect();intent.task=p.tasks[0];words();summary();invalidate();});
$('compile').addEventListener('click',()=>build());
async function build(note){if(typeof clearTimeout==='function')clearTimeout(buildTimer);buildTimer=null;if(!registry.length)return;const ticket=draftVersion;try{collect();const compiled=await api('/api/prompt/compile',{intent,profile_id:$('profile').value});if(ticket!==draftVersion)$('status').textContent='Draft changed while building. Stale preview discarded.';else{result=compiled;render();$('status').textContent=note||'No generation submitted.';}}catch(e){$('status').textContent=e.message;}announce();}
function render(){$('fields').textContent=Object.entries(result.fields).map(([key,value])=>key.toUpperCase()+'\n'+(typeof value==='string'?value:JSON.stringify(value))).join('\n\n');$('state').textContent=result.state==='blocked'?'Not usable yet. Each reason and what to do about it is listed below.':'Built. Read it before you use it; nothing was generated.';issues();coverage();$('trace').textContent=JSON.stringify({coverage:result.coverage,intent:result.intent,intent_sha256:result.intent_sha256,profile_sha256:result.profile_sha256},null,2);$('export-result').disabled=false;$('export-reason').textContent='Includes the unresolved items above, so a blocked build is still a usable record.';}
// Every unresolved item in plain words, with the action next to it and the code kept for agents.
function issues(){const list=StudioUX.promptBlockers(result);$('diagnostics').replaceChildren();
  if(!list.length){const done=node('p','Nothing is unresolved. Read the text above before you use it.');done.className='muted';$('diagnostics').append(done);return;}
  for(const item of list){const box=document.createElement('div');box.className=item.blocking?'pl-issue pl-blocking':'pl-issue';
    box.append(node('p',(item.blocking?'Blocked: ':'Worth knowing: ')+item.message));
    const action=node('p',item.action);action.className='pl-action';box.append(action);
    const target=item.fix==='switch-profile'?alternative(item.code):null;
    if(target){const swap=node('button','Switch to '+target.name);swap.addEventListener('click',()=>choose(target.id));box.append(swap);}
    if(item.fix==='avoid-to-note'&&intent.avoid.length){const keep=node('button','Keep as review note');keep.addEventListener('click',park);box.append(keep);}
    box.append(node('small',item.code+(item.detail?' · '+item.detail:'')));
    $('diagnostics').append(box);}}
// A profile swap is offered only when it actually fits the references already attached.
function alternative(code){const count=intent.references.length,current=registry.find(p=>p.id===$('profile').value),fits=match=>registry.find(p=>p.id!==$('profile').value&&p.min_refs<=count&&count<=p.max_refs&&match(p));
  if(code==='REFERENCE_COUNT')return current&&current.min_refs<=count&&count<=current.max_refs?null:fits(p=>p.dialect==='edit')||fits(p=>['prose','motion'].includes(p.dialect))||null;
  if(code==='TAGS_REQUIRED')return fits(p=>p.dialect==='prose')||null;
  return null;}
function choose(id){const p=registry.find(x=>x.id===id);if(!p)return;$('profile').value=id;collect();intent.task=p.tasks[0];words();summary();rebuild('Switched to '+p.name+'. Nothing you typed was changed.');}
// Moves the avoid terms into soft review notes. The words are kept verbatim, split across as many
// bounded notes as they need rather than truncated, and every note can be moved back in one click.
const noteText=terms=>'Avoid: '+terms.join(', ');
function park(){collect();if(!intent.avoid.length)return;const terms=intent.avoid.join(', '),groups=[];let current=[];
  for(const term of intent.avoid){const next=[...current,term];if(noteText(next).length>500&&current.length){groups.push(current);current=[term];}else current=next;}
  if(current.length)groups.push(current);
  if(groups.some(g=>noteText(g).length>500)){$('status').textContent='One avoidance term is too long to keep as a review note. Nothing was moved or deleted; shorten that term first.';return;}
  if(intent.constraints.length+groups.length>24){$('status').textContent='These terms need '+groups.length+' review notes and only '+(24-intent.constraints.length)+' fit. Nothing was moved or deleted; remove a note first.';return;}
  let n=1;
  for(const group of groups){while(intent.constraints.some(c=>c.id==='avoid-note-'+n))n++;intent.constraints.push({id:'avoid-note-'+n,text:noteText(group),mechanism:'verify',priority:'soft'});}
  intent.avoid=[];$('avoid').value='';notes();
  rebuild('Moved “'+terms+'” out of Things to avoid and into '+(groups.length===1?'a review note':groups.length+' review notes')+'. Every word is kept in the brief; this profile simply has nowhere to send them.');}
function unpark(note){intent.constraints=intent.constraints.filter(x=>x.id!==note.id);
  const terms=note.text.replace(/^Avoid: /,'').split(',').map(x=>x.trim()).filter(Boolean);
  intent.avoid=[...new Set([...intent.avoid,...terms])];$('avoid').value=intent.avoid.join(', ');notes();rebuild('Returned “'+terms.join(', ')+'” to Things to avoid.');}
function notes(){$('notes-list').replaceChildren();$('notes-section').hidden=!intent.constraints.length;
  for(const c of intent.constraints){const row=document.createElement('div');row.className='pl-note';row.append(node('span',c.text+' ('+c.priority+' · checked by '+c.mechanism+')'));
    const back=node('button',c.id.startsWith('avoid-note-')?'Return to Things to avoid':'Remove note');
    back.addEventListener('click',()=>c.id.startsWith('avoid-note-')?unpark(c):(intent.constraints=intent.constraints.filter(x=>x.id!==c.id),notes(),rebuild('Removed the review note. Nothing else changed.')));
    row.append(back);$('notes-list').append(row);}}
function summary(){const p=registry.find(x=>x.id===$('profile').value);$('profile-summary').textContent=!p?'':[p.summary||'',p.max_refs?'Reads '+p.min_refs+' to '+p.max_refs+' reference images.':'Reads no reference images.',p.negative?'':'No negative prompt.'].filter(Boolean).join(' ');}
// The trace as sentences: what you wrote, and where this profile actually put it.
const SOURCES={brief:'Your brief',tags:'Tags',avoid:'Things to avoid'};
const DESTINATIONS={positive:'positive prompt',negative:'negative prompt',reference_map:'reference map (roles only; no upload happens here)','text: byte-preserving':'the spoken words, byte for byte','lyrics: byte-preserving':'the lyrics, byte for byte','review: positive rewrite':'nowhere yet — it needs a positive rewrite you approve',timesignature:'time signature',keyscale:'key','workflow parameter handoff':'a recipe setting in Create, not the prompt','preserved / unbound':'kept in the brief, with no output channel','description + acceptance':'positive prompt, and a thing you check by looking','required_stage + acceptance':'an extra stage (mask, guide or check), not the prompt'};
// `description` is one ledger word for three different fields; name the one this dialect fills.
function destination(value){if(value!=='description')return DESTINATIONS[value]||value.replaceAll('_',' ');
  const dialect=result.profile&&result.profile.dialect;
  return dialect==='voice'?'performance direction (the instruct field, never the spoken words)':dialect==='music'?'caption':'positive prompt';}
function readable(source){const b=result.intent;if(SOURCES[source])return SOURCES[source];
  let m=/^facets\.(.+)$/.exec(source);if(m)return m[1][0].toUpperCase()+m[1].slice(1);
  m=/^references\[(\d+)\]$/.exec(source);if(m){const r=b.references[+m[1]];return 'Reference '+(+m[1]+1)+(r?' ('+r.role+')':'');}
  m=/^constraints\[(\d+)\]$/.exec(source);if(m){const c=b.constraints[+m[1]];return c?'Review note “'+c.text+'”':'Review note';}
  m=/^parameters\.(.+)$/.exec(source);if(m)return 'Parameter '+m[1].replaceAll('_',' ');
  m=/^verbatim\.(.+)$/.exec(source);if(m)return m[1]==='text'?'Exact words':'Exact lyrics';
  return source;}
function coverage(){$('coverage').replaceChildren();
  $('identity').textContent='This exact brief is fingerprinted '+String(result.intent_sha256||'').slice(0,12)+'… Change any word and the fingerprint changes. The profile record is '+String(result.profile_sha256||'').slice(0,12)+'…';
  for(const row of result.coverage||[]){const line=document.createElement('p');line.className='pl-coverage';
    line.append(node('b',readable(row.source)),node('span',' → '),node('span',destination(row.destination)));$('coverage').append(line);}
  if(!(result.coverage||[]).length)$('coverage').append(node('p','This profile recorded no field mapping.'));}
$('export-brief').addEventListener('click',()=>{collect();download(intent,'creative-brief.json');});$('export-result').addEventListener('click',()=>{if(result)download(result,'compiled-intent.json');});
$('brief-file').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file||file.size>65536)throw Error('Choose a brief smaller than 64 KiB');const data=JSON.parse(await file.text());const compatible=registry.find(p=>p.tasks.includes(data.task));if(!compatible)throw Error('Unsupported task');await api('/api/prompt/compile',{intent:data,profile_id:compatible.id});intent=data;$('profile').value=compatible.id;show();summary();invalidate();$('status').textContent='Imported the full brief. Nothing generated.';}catch(err){$('status').textContent=err.message;}});
$('proposal-file').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file||file.size>65536)throw Error('Choose a small proposal JSON');const data=JSON.parse(await file.text());proposed=data.proposal||data;collect();await api('/api/prompt/apply',{intent,proposal:proposed,accepted_fields:[]});$('proposal-list').replaceChildren();for(const c of proposed.changes){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=c.field;input.disabled=intent.locked.some(x=>c.field===x||c.field.startsWith(x+'.'));label.append(input,document.createTextNode(c.field+': '+JSON.stringify(c.value)+' â€” '+c.reason));$('proposal-list').append(label);}$('accept').disabled=false;$('status').textContent='Suggestions loaded; none applied.';}catch(err){$('accept').disabled=true;$('status').textContent=err.message;}});
$('accept').addEventListener('click',async()=>{try{collect();const ticket=draftVersion;const accepted_fields=Array.from($('proposal-list').querySelectorAll('input:checked')).map(x=>x.value);const revision=await api('/api/prompt/apply',{intent,proposal:proposed,accepted_fields});if(ticket!==draftVersion){$('status').textContent='Draft changed while applying. Stale result discarded.';return;}intent=revision.intent;show();invalidate();$('accept').disabled=true;$('status').textContent='Selected suggestions applied to a new draft. Original proposal remains separate.';}catch(e){$('status').textContent=e.message;}});
let metadataRequest=0;
$('png-file').addEventListener('change',async e=>{
  const request=++metadataRequest;
  try{
    const file=e.target.files[0];
    if(!file||file.size>650000)throw Error('Metadata inspector accepts PNG/JPEG/WebP/recipe-sidecar JSON up to 650 KB; use the CLI for larger media or an attached sidecar.');
    $('metadata').textContent='Inspecting '+file.name+'… No workflow will run.';
    const bytes=new Uint8Array(await file.arrayBuffer());
    let binary='';
    for(let i=0;i<bytes.length;i+=4096)binary+=String.fromCharCode(...bytes.subarray(i,i+4096));
    const data=await api('/api/prompt/metadata',{media_base64:btoa(binary)});
    if(request===metadataRequest)$('metadata').textContent=JSON.stringify(data,null,2);
  }catch(err){
    if(request===metadataRequest)$('metadata').textContent=err.message;
  }
});
fetch('/api/prompt/profiles').then(async response=>{const data=await response.json();if(!response.ok)throw Error(data.error||'Prompt Lab is unavailable');return data;}).then(data=>{registry=data.profiles;for(const p of registry){const o=node('option',p.name);o.value=p.id;$('profile').append(o);}if(registry.length)$('profile').value=registry[0].id;summary();build();}).catch(e=>{$('status').textContent='Start Asset Studio normally, then reopen this page: '+e.message;});

function words(){const show=['voice','music'].includes(intent.task);$('words-section').hidden=!show;if(show){const key=intent.task==='voice'?'text':'lyrics';$('words-label').textContent=intent.task==='voice'?'Exact words to speak (never rewritten)':'Exact lyrics (never rewritten)';$('words').value=intent.verbatim[key]||'';}}
function references(){$('reference-list').replaceChildren();for(const r of intent.references){const card=document.createElement('div');card.append(node('p',r.id+' / '+r.path));const label=node('label','Reference role');const select=document.createElement('select');for(const role of ['identity','pose','style','costume','composition','motion','voice','geometry','mask']){const opt=node('option',role);opt.value=role;select.append(opt);}select.value=r.role;select.addEventListener('change',()=>{r.role=select.value;invalidate();});label.append(select);card.append(label);for(const key of ['take','ignore']){const l=node('label',key==='take'?'Take from this image':'Do not transfer');const input=document.createElement('input');input.value=r[key].join('; ');input.addEventListener('change',()=>{r[key]=input.value.split(';').map(x=>x.trim()).filter(Boolean);invalidate();});l.append(input);card.append(l);}const remove=node('button','Remove reference');remove.addEventListener('click',()=>{intent.references=intent.references.filter(x=>x.id!==r.id);references();invalidate();});card.append(remove);$('reference-list').append(card);}}
$('ref-files').addEventListener('change',async e=>{try{for(const f of e.target.files){if(intent.references.length>=12)throw Error('Twelve reference records maximum');if(f.size>8*1024*1024||/[\\/:]/.test(f.name))throw Error('Use small images with portable filenames');const bytes=await f.arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');intent.references.push({id:'ref-'+crypto.randomUUID().slice(0,8),role:'identity',kind:'image',path:f.name,sha256:hash,take:[],ignore:[]});}references();invalidate();$('status').textContent='References recorded by hash. Set each role below; the prompt rebuilds itself.';}catch(err){references();$('status').textContent=err.message;}});

// Reference review is a client of this draft owner, never a second intent store.
// These guards cover this open editor; they are not shared Workspace revisions.
globalThis.StudioPromptDraft=(()=>{
  const clone=value=>JSON.parse(JSON.stringify(value));
  function capture(){collect();const json=JSON.stringify(intent);return {version:draftVersion,profile:$('profile').value,json,intent:JSON.parse(json)};}
  function matches(ticket){const now=capture();return !!ticket&&ticket.version===now.version&&ticket.profile===now.profile&&ticket.json===now.json&&JSON.stringify(ticket.intent)===ticket.json;}
  function apply(ticket,preview){
    if(!matches(ticket))throw Error('The brief changed. Preview the reference changes again.');
    if(!preview||preview.format!=='studio.reference-transfer-preview/v1'||['generation_submitted','inference_submitted','execution_authorized'].some(k=>preview[k]!==false)||!preview.intent)throw Error('Expected a non-executing reference preview.');
    if(JSON.stringify(preview.base_intent)!==ticket.json)throw Error('The preview does not match this brief.');
    const before=capture();intent=clone(preview.intent);show();invalidate();
    return {before,after:capture()};
  }
  function undo(receipt){
    if(!receipt||!matches(receipt.after))throw Error('The brief changed after applying. Undo would overwrite newer work; export the receipt to recover earlier values.');
    intent=JSON.parse(receipt.before.json);$('profile').value=receipt.before.profile;show();summary();invalidate();return capture();
  }
  return Object.freeze({capture,matches,apply,undo});
})();
