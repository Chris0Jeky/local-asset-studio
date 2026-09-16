// Real Prompt Lab imports with controlled file/API completion, not a fake state owner.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
 const elements=new Map();
 const el=id=>{if(!elements.has(id))elements.set(id,{value:'',children:[],listeners:{},addEventListener(k,f){this.listeners[k]=f;},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},querySelectorAll(){return[];}});return elements.get(id);};
 const profile={id:'sdxl-prose-v1',tasks:['image'],max_refs:0,min_refs:0};let releaseCompile=null,holdCompile=false;
 const ctx=vm.createContext({document:{getElementById:el,createElement:()=>el('new-'+Math.random()),createTextNode:t=>({textContent:t})},
 crypto:require('node:crypto').webcrypto,fetch:async(url,options)=>{
  if(!options)return{ok:true,json:async()=>({profiles:[profile]})};
  if(holdCompile)await new Promise(resolve=>{releaseCompile=resolve;});
  return{ok:true,json:async()=>({fields:{},state:'ready',coverage:[],intent:JSON.parse(options.body).intent,profile})};
 }});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/prompt-lab.js'),'utf8'),ctx);
 el('brief').value='Current';el('profile').value=profile.id;
 const owner=ctx.StudioPromptDraft;
 const saved=()=>({format:'studio.prompt-document/v1',name:'Saved',profile_id:profile.id,intent:{...owner.capture().intent,brief:'Opened saved words'},reference_context:null});
 return {ctx,el,owner,saved,hold:()=>holdCompile=true,release:()=>releaseCompile()};
}
(async()=>{
 for(const phase of ['file','validation']){
  const f=fixture();await tick();let releaseFile;
  const imported={...f.owner.capture().intent,brief:'Older imported words'};
  const file={size:50,text:phase==='file'?()=>new Promise(resolve=>{releaseFile=()=>resolve(JSON.stringify(imported));}):async()=>JSON.stringify(imported)};
  if(phase==='validation')f.hold();
  const running=f.el('brief-file').listeners.change({target:{files:[file]}});await tick();
  f.owner.openSaved(f.owner.capture(),f.saved());
  if(phase==='file')releaseFile();else f.release();await running;
  assert.equal(f.el('brief').value,'Opened saved words','An older '+phase+' import must not overwrite an explicitly opened saved brief');
 }
 {
  const f=fixture();await tick();let release;
  const file={size:3,name:'old.png',arrayBuffer:()=>new Promise(resolve=>{release=()=>resolve(new Uint8Array([1,2,3]).buffer);})};
  const running=f.el('ref-files').listeners.change({target:{files:[file]}});await tick();
  f.owner.openSaved(f.owner.capture(),f.saved());release();await running;
  assert.equal(f.owner.capture().intent.references.length,0,'Older hashing must not attach a picture to a different opened brief');
 }
 {
  const f=fixture();await tick();let release;
  const file={size:50,text:()=>new Promise(resolve=>{release=()=>resolve(JSON.stringify({...f.owner.capture().intent,brief:'Old'}));})};
  const running=f.el('brief-file').listeners.change({target:{files:[file]}});await tick();
  f.el('brief').value='Newer unreported typing';release();await running;
  assert.equal(f.el('brief').value,'Newer unreported typing','Form comparison must cover edits without an input event');
 }
 {
  const f=fixture();await tick();const data={...f.owner.capture().intent,brief:'Accepted import'};
  await f.el('brief-file').listeners.change({target:{files:[{size:50,text:async()=>JSON.stringify(data)}]}});
  assert.equal(f.el('brief').value,'Accepted import','An unchanged draft still accepts a valid import');
  await f.el('ref-files').listeners.change({target:{files:[{size:3,name:'valid.png',arrayBuffer:async()=>new Uint8Array([1,2,3]).buffer}]}});
  assert.equal(f.owner.capture().intent.references.length,1,'Unchanged reference imports still attach');
  await f.el('ref-files').listeners.change({target:{files:[{size:3,name:'first.png',arrayBuffer:async()=>new Uint8Array([4,5,6]).buffer},{size:3,name:'../outside.png'}]}});
  assert.equal(f.owner.capture().intent.references.length,1,'An invalid later file cannot leave a partially attached batch');
 }
 {
  const f=fixture();await tick();let release;
  const older={...f.owner.capture().intent,brief:'Older selection'},newer={...older,brief:'Newer selection'};
  const running=f.el('brief-file').listeners.change({target:{files:[{size:50,text:()=>new Promise(resolve=>{release=()=>resolve(JSON.stringify(older));})}]}});
  await f.el('brief-file').listeners.change({target:{files:[{size:50,text:async()=>JSON.stringify(newer)}]}});
  release();await running;assert.equal(f.el('brief').value,'Newer selection','Newer import selections take precedence');
 }
 console.log('Prompt imports cannot overwrite newer drafts');
})().catch(error=>{console.error(error);process.exitCode=1;});
