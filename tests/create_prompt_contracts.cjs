'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
const continuation=require('../app/static/continuation-core.js');
function page(){
  const elements=new Map(),listeners={},writes=[];
  const element=id=>{if(!elements.has(id))elements.set(id,{value:'',files:[],textContent:'',innerHTML:'',disabled:false,hidden:false,
    classList:{toggle(){}},addEventListener(){},setAttribute(){},focus(){this.focused=true;},closest:()=>true});return elements.get(id);};
  const context=vm.createContext({console,URL,Blob,AbortController,StudioContinuation:continuation,location:{hash:''},
    setInterval(){},setTimeout(){return 1;},clearTimeout(){},
    document:{querySelector:element,querySelectorAll:()=>[],addEventListener:(name,fn)=>(listeners[name]||=[]).push(fn)},
    fetch:(url,options={})=>{if(options.method==='POST'){writes.push({url,body:JSON.parse(options.body)});return Promise.resolve({ok:true,json:async()=>({id:'synthetic-job',message:'Synthetic only'})});}return new Promise(()=>{});}});
  vm.runInContext(source,context);
  const run=js=>vm.runInContext(js,context);
  run("selected={id:'text',positive:{node:'1',input:'text'}};online=true;schemaAvailable=true;workerAlive=true;attachedReferencePayload=()=>[]");
  run("uploadInput=async()=>null;refresh=async()=>{}");
  return {run,element,writes,input(value,event='input'){element('#positive').value=value;for(const fn of listeners[event]||[])fn({target:element('#positive')});}};
}
for(const prompt of ['', '   ', '\n\t', '\u00a0'])test(`ordinary text recipe blocks trimmed-empty prompt ${JSON.stringify(prompt)}`,async()=>{
  const h=page();h.element('#positive').value=prompt;h.run('updateReady()');
  assert.equal(h.element('#generate').disabled,true);
  const items=JSON.parse(h.run('JSON.stringify(continuationBlockerItems())'));
  assert.deepEqual(items,[{code:'wording',message:'Add a prompt to generate.'}]);
  await h.element('#generate').onclick();
  assert.equal(h.writes.length,0);assert.match(h.element('#status').textContent,/Add a prompt/);
  assert.equal(h.element('#positive').focused,true);
});
for(const event of ['input','change'])test(`native ${event} notification recomputes shared readiness when prompt clears and recovers`,()=>{
  const h=page();h.input('A synthetic lantern',event);assert.equal(h.element('#generate').disabled,false);
  h.input(' ',event);assert.equal(h.element('#generate').disabled,true);
  h.input('Another lantern',event);assert.equal(h.element('#generate').disabled,false);assert.equal(h.writes.length,0);
});
test('a valid prompt reaches the original explicit submission handler unchanged',async()=>{
  const h=page();h.input('  A synthetic lantern  ');await h.element('#generate').onclick();
  assert.equal(h.writes.length,1);assert.equal(h.writes[0].url,'/api/jobs');
  assert.equal(h.writes[0].body.controls.positive,'  A synthetic lantern  ');
});
test('image-only recipes without a positive binding remain usable with empty hidden text',async()=>{
  const h=page();h.run("selected={id:'image-only'}");h.input('');
  assert.equal(h.element('#generate').disabled,false);await h.element('#generate').onclick();assert.equal(h.writes.length,1);
});
test('correcting wording cannot bypass backend, model, worker or submission blockers',()=>{
  for(const state of ['online=false','schemaAvailable=false','workerAlive=false','submitting=true',"missingByPreset={text:['model']}"]){
    const h=page();h.run(state);h.input('A valid description');assert.equal(h.element('#generate').disabled,true,state);
  }
});
test('continuation-specific refusal remains authoritative instead of being replaced by a generic prompt rule',()=>{
  const h=page();h.run('continuationState={invalid:true}');
  const items=JSON.parse(h.run('JSON.stringify(continuationBlockerItems())'));
  assert.equal(items[0].code,'invalid');assert.match(items[0].message,/Reopen Continue/);
});
