'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/static/backends.js'),'utf8').replace('refreshBackends();setInterval(', 'setInterval(');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};}
function fixture(){
  const nodes=new Map(),pending=[],writes=[],state={renders:0,health:0},a={id:'a',name:'A',positive:true,negative:true,defaults:{positive:'old default',seed:42}},b={...a,id:'b',name:'B'};
  const document={activeElement:null};
  function node(id){if(!nodes.has(id))nodes.set(id,{id,value:'',textContent:'',hidden:false,disabled:false,innerHTML:'',focus(){document.activeElement=this;},setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}});return nodes.get(id);}
  const context={document,console,selected:a,catalog:{presets:[a,b]},controlKeys:['seed','steps'],view:'create',setInterval(callback){state.poll=callback;},esc:String,$:node,getControl:key=>node('[data-key="'+key+'"]'),
    values:()=>({positive:node('#positive').value,negative:node('#negative').value,...Object.fromEntries(['seed','steps'].filter(k=>node('[data-key="'+k+'"]').value!=='').map(k=>[k,node('[data-key="'+k+'"]').value]))}),
    api:url=>{const d=deferred();pending.push({url,...d});return d.promise;},post:async(...args)=>{writes.push(args);return{};},renderPresets(){},renderSelected(){state.renders++;node('#positive').value=context.selected.defaults.positive;for(const key of ['seed','steps']){const id='[data-key="'+key+'"]';if(document.activeElement===nodes.get(id))document.activeElement=null;nodes.delete(id);node(id).value=String(context.selected.defaults[key]??'');}},health:async()=>{state.health++;},refreshLibrary:async()=>{},updateReady(){}};
  vm.createContext(context);vm.runInContext(source,context);vm.runInContext("backendActive='old'",context);
  const backend=(id='new')=>({active:id,busy:false,profiles:[{id,name:id,active:true,installed:true}],operation:null});
  return{context,node,pending,writes,state,a,b,backend,run:()=>context.refreshBackends(),tick:()=>new Promise(resolve=>setImmediate(resolve))};
}
// Do not await an async helper that adopts the still-pending refresh promise.
async function begin(f){const work=f.run();f.pending[0].resolve(f.backend());await f.tick();return{work};}
test('late catalogue preserves latest wording, cleared settings and focused numeric field',async()=>{
 const f=fixture();f.node('#positive').value='old typing';f.node('[data-key="seed"]').value='42';const {work}=await begin(f);
 f.node('#positive').value='latest typing';f.node('[data-key="seed"]').value='';f.node('[data-key="steps"]').value='11';f.node('[data-key="steps"]').focus();
 f.pending[1].resolve({presets:[f.a,f.b]});await work;
 assert.equal(f.node('#positive').value,'latest typing');assert.equal(f.node('[data-key="seed"]').value,'');assert.equal(f.node('[data-key="steps"]').value,'11');assert.equal(f.context.document.activeElement,f.node('[data-key="steps"]'));assert.equal(f.writes.length,0);
});
test('recipe chosen during catalogue read remains the selected recipe',async()=>{
 const f=fixture();const {work}=await begin(f);f.context.selected=f.b;f.node('#positive').value='B wording';f.pending[1].resolve({presets:[f.a,f.b]});await work;assert.equal(f.context.selected.id,'b');assert.equal(f.node('#positive').value,'B wording');
});
for(const result of ['missing','malformed','failed'])test(result+' catalogue retains the live editor without falling back',async()=>{
 const f=fixture();const original=f.context.catalog;const {work}=await begin(f);f.node('#positive').value='live';
 if(result==='failed')f.pending[1].reject(Error('catalogue unavailable'));else f.pending[1].resolve(result==='missing'?{presets:[f.b]}:{});
 await work;assert.equal(f.context.catalog,original);assert.equal(f.context.selected,f.a);assert.equal(f.node('#positive').value,'live');assert.equal(f.state.renders,0);assert.ok(f.node('#backendStatus').textContent);
});
for(const result of ['success','failure'])test('superseded backend '+result+' cannot overwrite newer chrome',async()=>{
 const f=fixture();const older=f.run(),newer=f.run();f.pending[1].resolve(f.backend('old'));await newer;const status=f.node('#backendStatus').textContent;
 if(result==='failure')f.pending[0].reject(Error('old failure'));else f.pending[0].resolve(f.backend('stale'));
 await f.tick();assert.equal(f.pending.length,2,'stale state must not begin another catalogue read');await older;assert.equal(f.node('#activeBackend').textContent,'old');assert.equal(f.node('#backendStatus').textContent,status);
});
for(const result of ['success','failure'])test('superseded catalogue '+result+' cannot replace newer editor',async()=>{
 const f=fixture();const {work:older}=await begin(f);const newer=f.run();f.pending[2].resolve(f.backend('old'));await newer;
 if(result==='failure')f.pending[1].reject(Error('old catalogue failure'));else f.pending[1].resolve({presets:[f.a,f.b]});
 await older;assert.equal(f.state.renders,0);assert.equal(f.node('#activeBackend').textContent,'old');assert.ok(!f.node('#backendStatus').textContent.includes('failure'));
});

test('automatic polling does not supersede its own slow catalogue read',async()=>{
 const f=fixture();vm.runInContext('backendSwitching=true',f.context);const {work}=await begin(f);f.state.poll();f.state.poll();assert.equal(f.pending.length,2);f.pending[1].resolve({presets:[f.a,f.b]});await work;assert.equal(f.state.renders,1);
});
