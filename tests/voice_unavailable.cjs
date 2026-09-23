'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/static/voice.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
const ready=()=>json({capabilities:{configured:true},projects:[]});
function page(){
  const elements=new Map(),requests=[];
  const $=id=>{if(!elements.has(id))elements.set(id,{textContent:'',innerHTML:'',value:'',disabled:false,classList:{toggle(){}}});return elements.get(id);};
  const context=vm.createContext({document:{querySelector:$},setTimeout(){return 1;},clearTimeout(){},
    fetch:(url,options={})=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))});
  vm.runInContext(source,context);
  return {$,requests,refresh:()=>$('#voiceRefresh').onclick(),prepare:()=>$('#voiceForm').onsubmit({preventDefault(){}})};
}
for(const [name,response] of [
  ['HTML error',()=>new Response('<!DOCTYPE html><h1>Not found</h1>',{status:404,headers:{'Content-Type':'text/html'}})],
  ['malformed JSON',()=>new Response('{oops',{headers:{'Content-Type':'application/json'}})],
  ['network failure',null],
  ['malformed capabilities',()=>json({projects:[]})]
])test(`Voice ${name} keeps Prepare unavailable and permits explicit recovery`,async()=>{
  const h=page();
  if(response)h.requests[0].resolve(response());else h.requests[0].reject(Error('Failed to fetch'));
  await flush();
  assert.equal(h.$('#voicePrepare').disabled,true);
  assert.match(h.$('#voiceStatus').textContent,/unavailable/i);
  assert.doesNotMatch(h.$('#voiceStatus').textContent,/Unexpected token|JSON|Cannot read/);
  assert.match(h.$('#voiceTakes').innerHTML,/unavailable|No takes prepared/i);
  const count=h.requests.length,attempt=h.prepare();
  // Complete a regression's incorrectly sent request so RED cannot hang.
  if(h.requests.length>count){h.requests.at(-1).reject(Error('Unexpected write'));}
  await attempt;assert.equal(h.requests.length,count,'An unconfirmed capability cannot prepare even via direct form dispatch');
  const refresh=h.refresh();h.requests.at(-1).resolve(ready());await refresh;
  assert.equal(h.$('#voicePrepare').disabled,false);
  assert.match(h.$('#voiceTakes').innerHTML,/No takes prepared/);
});
test('a failed post-prepare refresh cannot rearm Prepare in finally',async()=>{
  const h=page();h.requests[0].resolve(ready());await flush();
  h.$('#voiceLines').value='Synthetic line';const submit=h.prepare();
  assert.equal(h.requests.at(-1).options.method,'POST');h.requests.at(-1).resolve(json({}));await flush();
  h.requests.at(-1).reject(Error('Offline'));await submit;
  assert.equal(h.$('#voicePrepare').disabled,true);
  assert.equal(h.requests.filter(r=>r.options.method==='POST').length,1);
});
test('configured false does not enable Prepare',async()=>{
  const h=page();h.requests[0].resolve(json({capabilities:{configured:false},projects:[]}));await flush();
  assert.equal(h.$('#voicePrepare').disabled,true);
});
test('a stale successful refresh cannot replace a newer unavailable observation',async()=>{
  const h=page(),later=h.refresh();h.requests[1].reject(Error('Offline'));await later;
  h.requests[0].resolve(ready());await flush();assert.equal(h.$('#voicePrepare').disabled,true);
});
