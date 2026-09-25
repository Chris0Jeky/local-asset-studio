// Actual Analyze controller with bounded fake transport and storage faults.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
class Element{
 constructor(){Object.assign(this,{value:'',textContent:'',hidden:false,disabled:false,checked:false,files:[],children:[],listeners:{}});}
 addEventListener(t,f){this.listeners[t]=f;}append(...c){this.children.push(...c);}replaceChildren(...c){this.children=c;}setAttribute(){}focus(){}scrollIntoView(){}
 fire(t){return this.listeners[t]?.({target:this});}
}
async function scenario(storageFails,changedDuringRead=false,disabled=false,rejected=false){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const store=new Map(),calls=[],loads=[];let posted=null,fail=true,retired=false,brief='use that pose';
 const document={getElementById:el,createElement:()=>new Element(),hidden:false,addEventListener(){}};
 const capture=()=>({json:JSON.stringify({brief}),intent:{brief}});
 const context=vm.createContext({document,window:{addEventListener(){}},URLSearchParams,console,
  crypto:require('node:crypto').webcrypto,btoa:text=>Buffer.from(text,'binary').toString('base64'),
  setTimeout:()=>1,clearTimeout(){},sessionStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>{if(storageFails)throw Error('quota');store.set(k,v);},removeItem:k=>store.delete(k)},
  StudioPromptDraft:{capture,matches:ticket=>ticket.json===capture().json},
  StudioReferenceReview:{load:async(...args)=>loads.push(args)},
  fetch:async(url,options)=>{
   calls.push({url,options});if(url.endsWith('/capabilities'))return{ok:true,json:async()=>({...fixture.capabilities,enabled:!disabled})};
   if(url.endsWith('/create')){posted=JSON.parse(options.body);assert.ok([...store.values()].some(v=>v.includes(posted.request_id)),'Request handle must be durable BEFORE dispatch');if(rejected)return{ok:false,json:async()=>({error:'Reference bytes changed'})};if(fail)throw Error('reply lost');}
   if(url.endsWith('/retire')){retired=true;throw Error('retirement committed, reply lost');}
   if(rejected&&!retired)return{ok:false,json:async()=>({error:'Unknown analysis request; nothing was replayed'})};
   const result={...fixture.completed,request_id:posted?.request_id||fixture.completed.request_id};
   if(retired){result.result=null;result.state={status:'cancelled',resource_hold:false,inference_attempts:0,retired_without_dispatch:true,message:'Retired before dispatch'};}
   return{ok:true,json:async()=>result};
  }
 });
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/reference-analyze.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 el('ra-files').files=fixture.images.map((row,i)=>{const bytes=Buffer.from(row.media_base64,'base64');return{size:bytes.length,name:'picture-'+(i+1)+'.png',type:'image/png',arrayBuffer:async()=>{if(changedDuringRead)brief='changed while hashing';return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);}};});
 await el('ra-files').fire('change');assert.equal(calls.filter(x=>x.options?.method==='POST').length,0,'Import must never infer');
 await el('ra-start').fire('click');
 if(disabled||changedDuringRead){assert.equal(posted,null,'Disabled or stale input cannot dispatch');return;}
 if(storageFails){assert.equal(posted,null,'Storage failure must prevent inference');assert.match(el('ra-status').textContent,/saved|recover|storage/i);return;}
 assert.ok(posted);assert.equal(posted.request.brief,'use that pose');assert.equal(posted.images.length,2);
 await el('ra-start').fire('click');assert.equal(calls.filter(x=>x.url.endsWith('/create')).length,1,'Lost reply must not permit a new submit');
 if(rejected){
  await el('ra-check').fire('click');assert.equal(el('ra-new').disabled,true);assert.equal(el('ra-retire').disabled,false);
  await el('ra-retire').fire('click');assert.equal(retired,true,'Only an explicit action retires an unknown request');
  await el('ra-check').fire('click');assert.equal(el('ra-new').disabled,false,'A lost retirement reply recovers through the same identity');
  await el('ra-new').fire('click');assert.equal(el('ra-start').disabled,false);
  assert.equal(calls.filter(x=>x.url.endsWith('/create')).length,1,'Retirement/new-analysis never replays creation');return;
 }
 fail=false;await el('ra-check').fire('click');assert.equal(el('ra-use').disabled,false);
 brief='newer manual instruction';await el('ra-use').fire('click');assert.equal(brief,'newer manual instruction');assert.equal(loads.length,1,'Completion is a review handoff, never intent apply');
 assert.equal(calls.filter(x=>x.url.endsWith('/create')).length,1);
 // Reload may read the retained identity; it must never POST again.
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/reference-analyze.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));assert.equal(calls.filter(x=>x.url.endsWith('/create')).length,1);
 assert.ok([...store.values()].some(v=>v.includes(posted.request_id)));
}
async function ackResetsPerOperation(){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const store=new Map(),calls=[];let posted=null,hold=true;
 const document={getElementById:el,createElement:()=>new Element(),hidden:false,addEventListener(){}};
 const capture=()=>({json:JSON.stringify({brief:'pose'}),intent:{brief:'pose'}});
 const context=vm.createContext({document,window:{addEventListener(){}},URLSearchParams,console,
  crypto:require('node:crypto').webcrypto,btoa:text=>Buffer.from(text,'binary').toString('base64'),
  setTimeout:()=>1,clearTimeout(){},sessionStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
  StudioPromptDraft:{capture,matches:ticket=>ticket.json===capture().json},
  StudioReferenceReview:{load:async()=>{}},
  fetch:async(url,options)=>{
   calls.push({url,options});
   if(url.endsWith('/capabilities'))return{ok:true,json:async()=>({...fixture.capabilities})};
   if(url.endsWith('/create')){posted=JSON.parse(options.body);const result={...fixture.completed,request_id:posted.request_id,state:{...fixture.completed.state,status:'uncertain',resource_hold:true,response_done:false,message:'hold'}};return{ok:true,json:async()=>result};}
   if(url.endsWith('/release')){
    assert.equal(JSON.parse(options.body).acknowledge_unknown,true,'First release may use the ticked acknowledgement');
    hold=false;
    const result={...fixture.completed,request_id:posted.request_id,state:{...fixture.completed.state,status:'uncertain',resource_hold:false,response_done:true,message:'released'}};
    return{ok:true,json:async()=>result};
   }
   const result={...fixture.completed,request_id:posted.request_id,state:{...fixture.completed.state,status:'uncertain',resource_hold:hold,response_done:!hold,message:'status'}};
   return{ok:true,json:async()=>result};
  }
 });
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/reference-analyze.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 el('ra-files').files=fixture.images.map((row,i)=>{const bytes=Buffer.from(row.media_base64,'base64');return{size:bytes.length,name:'picture-'+(i+1)+'.png',type:'image/png',arrayBuffer:async()=>{return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);}};});
 await el('ra-files').fire('change');await el('ra-start').fire('click');
 el('ra-acknowledge').checked=true;await el('ra-release').fire('click');
 assert.equal(el('ra-acknowledge').checked,false,'Successful release must clear the per-operation acknowledgement');
 el('ra-acknowledge').checked=true;await el('ra-new').fire('click');
 assert.equal(el('ra-acknowledge').checked,false,'Starting a new analysis must not keep the previous acknowledgement');
 el('ra-acknowledge').checked=true;
 el('ra-recent').value=fixture.capabilities.recent?.[0]?.request_id||'recovered-request-id-0001';
 const recent=el('ra-recent');recent.value=recent.value;await el('ra-recover').fire('click');
 assert.equal(el('ra-acknowledge').checked,false,'Recovering another operation must not keep the previous acknowledgement');
}
async function invalidSelectionResetsPicker(){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const store=new Map();
 const document={getElementById:el,createElement:()=>new Element(),hidden:false,addEventListener(){}};
 const capture=()=>({json:JSON.stringify({brief:'pose'}),intent:{brief:'pose'}});
 const context=vm.createContext({document,window:{addEventListener(){}},URLSearchParams,console,
  crypto:require('node:crypto').webcrypto,btoa:text=>Buffer.from(text,'binary').toString('base64'),
  setTimeout:()=>1,clearTimeout(){},sessionStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
  StudioPromptDraft:{capture,matches:ticket=>ticket.json===capture().json},
  StudioReferenceReview:{load:async()=>{}},
  fetch:async(url)=>{if(url.endsWith('/capabilities'))return{ok:true,json:async()=>({...fixture.capabilities})};return{ok:true,json:async()=>({...fixture.completed})};}
 });
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/reference-analyze.js'),'utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 el('ra-files').files=[{size:10,name:'a.png'},{size:10,name:'b.png'},{size:10,name:'c.png'},{size:10,name:'d.png'},{size:10,name:'e.png'}];
 el('ra-files').value='C:\\fakepath\\a.png';
 await el('ra-files').fire('change');
 assert.equal(el('ra-files').value,'','Invalid selection must reset the file input so stale filenames clear');
 assert.match(el('ra-status').textContent,/one to four|8 MiB/i,'Invalid selection must show the reason and the limit');
 assert.equal(el('ra-start').disabled,true,'Start must stay disabled after an invalid selection');
 el('ra-files').files=[{size:10,name:'a.png'}];
 el('ra-files').value='C:\\fakepath\\a.png';
 await el('ra-files').fire('change');
 assert.equal(el('ra-files').value,'','A handled valid selection must also reset the input so re-choosing the same file works');
 assert.equal(el('ra-start').disabled,false,'Valid selection must enable Start');
}
(async()=>{await scenario(false);await scenario(true);await scenario(false,true);await scenario(false,false,true);await scenario(false,false,false,true);await ackResetsPerOperation();await invalidSelectionResetsPicker();console.log('Analyze: explicit dispatch, saved identity, lost reply, reload and storage refusal passed');})().catch(e=>{console.error(e);process.exitCode=1;});
