const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{
 constructor(tag='div'){Object.assign(this,{tag,value:'',textContent:'',hidden:false,disabled:false,checked:false,children:[],listeners:{},dataset:{}});}
 addEventListener(k,f){this.listeners[k]=f;}append(...v){this.children.push(...v);}replaceChildren(...v){this.children=v;}
 get firstChild(){return this.children[0];}setAttribute(k,v){this[k]=v;}querySelectorAll(){return [];}fire(k){return this.listeners[k]?.({target:this});}
}
const scope='a'.repeat(32),id='b'.repeat(32),store=new Map();let rejectStorage=false,drop=false,held=null,release,posts=[],rows=[],lastCommand;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function create(){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const events={};const doc={getElementById:el,createElement:t=>new Element(t),createTextNode:()=>new Element(),body:new Element(),
   addEventListener:(k,f)=>{(events[k]??=[]).push(f);},dispatchEvent:e=>{for(const f of events[e.type]||[])f(e);}};
 const sessionStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>{if(rejectStorage)throw Error('quota');store.set(k,v);},removeItem:k=>store.delete(k)};
 const zero={generation_submitted:false,inference_submitted:false,execution_authorized:false};
 const row=(document,revision=1)=>({format:'studio.prompt-project/v1',workspace_id:scope,id,revision,head_revision:revision,source_bytes_verified:false,document,...zero});
 const response=value=>({ok:true,body:new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(JSON.stringify(value)));c.close();}}),json:async()=>value});
 const context=vm.createContext({document:doc,window:{addEventListener(){}},CustomEvent:class{constructor(type){this.type=type;}},
   crypto:require('node:crypto').webcrypto,TextEncoder,TextDecoder,AbortController,URLSearchParams,setTimeout:()=>1,clearTimeout(){},sessionStorage,
   URL:{revokeObjectURL(){}},fetch:async(url,options)=>{
    if(url==='/api/prompt/profiles')return response({profiles:[]});
    if(url.endsWith('/capabilities'))return response({format:'studio.prompt-projects/v1',workspace_id:scope,...zero});
    if(url.includes('/list?'))return response({workspace_id:scope,projects:rows.map(r=>({id:r.id,name:r.document.name,revision:r.revision})),...zero});
    if(url.includes('/status?'))return response(lastCommand);
    if(url.includes('/read?'))return response(rows[0]);
    const value=JSON.parse(options.body),action=url.split('/').pop();
    assert.equal(store.size,1,'Exact request must be retained before POST');
    assert.equal(JSON.parse([...store.values()][0]).body,options.body,'Dispatch must use the exact retained body');
    posts.push({url,body:options.body});const current=row(value.document,(value.expected_revision||0)+1);rows=[current];
    lastCommand={format:'studio.prompt-command/v1',workspace_id:scope,request_id:value.request_id,action,request:value,project:current,...zero};
    if(held)await new Promise(resolve=>{release=resolve;});
    if(drop){drop=false;throw Error('reply lost');}
    return response(lastCommand);
   }});
 for(const name of ['prompt-lab.js','reference-review.js','prompt-projects.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
 vm.runInContext("registry=[{id:'sdxl-prose-v1',tasks:['image'],max_refs:0,min_refs:0}];",context);
 el('profile').value='sdxl-prose-v1';el('brief').value='Original';el('pp-name').value='Keeper';
 return {context,el};
}
(async()=>{
 let {context,el}=create();await tick();assert.equal(posts.length,0,'Page load never writes');
 held=true;const saving=el('pp-create').fire('click');await tick();assert.equal(posts.length,1);
 el('brief').value='Newer while saving';await el('brief').fire('input');release();await saving;held=null;
 assert.equal(el('brief').value,'Newer while saving');assert.match(el('pp-current').textContent,/unsaved/);assert.equal(store.size,0);
 // Inject unknown reply: recreation of page must read the retained handle, not send again.
 drop=true;await el('pp-save').fire('click');assert.equal(store.size,1);assert.match(el('pp-status').textContent,/Check save status/);
 const count=posts.length;({context,el}=create());await tick();assert.equal(posts.length,count);assert.equal(el('pp-recovery').hidden,false);
 el('brief').value='Newer after reload';await el('pp-check').fire('click');assert.equal(posts.length,count);assert.equal(store.size,0);
 assert.equal(el('brief').value,'Newer after reload');assert.equal(el('pp-open').disabled,false);
 el('brief').value='Unreported late input';await el('pp-open').fire('click');assert.equal(el('brief').value,'Unreported late input');assert.match(el('pp-status').textContent,/changed/);
 vm.runInContext("registry=[{id:'sdxl-prose-v1',tasks:['image'],max_refs:0,min_refs:0}];",context);el('pp-list').value=id;await el('pp-preview').fire('click');await el('pp-open').fire('click');
 assert.equal(el('brief').value,'Newer while saving');assert.match(el('pp-current').textContent,/revision 2/);
 rejectStorage=true;await el('pp-save').fire('click');assert.equal(posts.length,count);assert.match(el('pp-status').textContent,/retained/);rejectStorage=false;
 console.log('Saved brief panel recovery guards passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
