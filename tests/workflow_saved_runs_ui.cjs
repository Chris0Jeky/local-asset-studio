/* Actual panel script on a minimal DOM, independently faulting the transport. */
'use strict';
process.env.WORKFLOW_FIXTURE_ONLY='1';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {webcrypto}=require('node:crypto'), C=require('../app/static/workflow-saved-run-core.js');
const {packetFixture,Storage}=require('./workflow_saved_run_core.cjs');
function fixture(storage = new Storage()) {
  const ids=new Map(),events=new Map(),calls=[],downloads=[];let packet=packetFixture(),answer=true,reply;
  let project={id:'document-a',revision:1,dirty:false,blocked:false,conflict:false};
  class Element {
    constructor(tag){this.tag=tag;this.children=[];this.value='';this.disabled=false;this.listeners={};this.textContent='';}
    setAttribute(k,v){this[k]=v;if(k==='id')ids.set(v,this);}
    append(...items){this.children.push(...items);}
    replaceChildren(...items){this.children=items;this.value='';}
    addEventListener(k,fn){this.listeners[k]=fn;}
    remove(){}
    click(){if(this.tag==='a')downloads.push({name:this.download,url:this.href});return this.disabled?undefined:this.onclick?.();}
  }
  const body=new Element('body');ids.set('builder',new Element('section'));ids.set('presetChoice',new Element('select'));ids.get('presetChoice').value='example';
  const dispatch=(name)=>(events.get(name)||[]).forEach(f=>f());
  reply=async(url,options)=>{
    if(url=== '/api/workflow-studio/document-runs') {const v=JSON.parse(options.body);packet=packetFixture(v.request_id,v.document_id);return {};}
    if(url.endsWith('/review')) return packet;
    if(url.includes('?'))return {document_id:project.id,runs:[{request_id:packet.source.request_id,document_id:project.id,revision:1,sequence:2,preset_id:'example'}],next_before:null};
    if(url.endsWith('/observe'))return {...packet.source,observation:{state:'not_observed',job_id:packet.source.job_id,message:'This does not prove it never ran.'}};
    if(url.endsWith('/run'))return {source:packet.source,dispatch:{job:{id:packet.source.job_id,status:'queued'}}};
    throw Error('unexpected '+url);
  };
  const context={window:{WorkflowSavedRunCore:C,WorkflowProject:{snapshot:()=>({...project})},addEventListener(){}},
    document:{body,querySelector:s=>ids.get(s.slice(1)),createElement:t=>new Element(t),addEventListener:(k,f)=>events.set(k,[...(events.get(k)||[]),f])},
    localStorage:storage,crypto:webcrypto,TextEncoder,URLSearchParams,AbortController,Blob,URL:{createObjectURL:b=>{downloads.push({blob:b});return 'blob:fixture';},revokeObjectURL(){}},
    setTimeout:()=>0,clearTimeout(){},confirm:()=>answer,
    fetch:async(url,options)=>{calls.push({url,options});const value=await reply(url,options);return {ok:true,text:async()=>JSON.stringify(value)};}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/workflow-saved-runs.js'),'utf8'),context);
  return {ids,calls,storage,downloads,packet:()=>packet,click:async id=>ids.get(id).click(),consent:v=>{answer=v;},
    setReply:fn=>{reply=fn;},project:p=>{project={...project,...p};dispatch('workflow:project');},
    original:async()=>{ids.get('savedRunRequest').value=packet.source.request_id;ids.get('savedRunRequest').oninput();await ids.get('reviewSavedRun').click();}};
}
test('startup and restored references never contact the service',async()=>{
  const s=new Storage();new C.Journal(s).remember(packetFixture().source);const f=fixture(s);
  assert.equal(f.calls.length,0);assert.equal(f.ids.get('executeSavedRun').disabled,true);assert.match(f.ids.get('savedRunMessage').textContent,/nothing was sent on load/);
  await f.click('reviewSavedRun');assert.equal(f.calls.length,1);
});
test('dirty, detached, conflicting or unresolved saves block new preparation',async()=>{
  for(const p of [{dirty:true},{id:null},{conflict:true},{blocked:true}]){const f=fixture();f.project(p);await f.click('prepareSavedRun');assert.equal(f.calls.length,0);}
});
test('prepare retains request before POST, verifies review and does not run',async()=>{
  const f=fixture();let checked=false;
  f.setReply(async(url,options)=>{if(options.body){const v=JSON.parse(options.body);assert.equal(new C.Journal(f.storage).list()[0].request_id,v.request_id);checked=true;f.p=packetFixture(v.request_id);return {}; }return f.p;});
  await f.click('prepareSavedRun');assert.ok(checked);assert.equal(f.calls.length,2);assert.equal(new C.Journal(f.storage).list().length,0);
  assert.equal(f.ids.get('executeSavedRun').disabled,false);assert.equal(f.calls.filter(c=>c.url.endsWith('/run')).length,0);
});
test('lost preparation response recovers the exact original request after reload',async()=>{
  const f=fixture();let p;f.setReply(async(url,options)=>{const v=JSON.parse(options.body);p=packetFixture(v.request_id);throw Error('reply lost');});
  await f.click('prepareSavedRun');const original=f.calls[0].options.body;assert.equal(new C.Journal(f.storage).list().length,1);
  const next=fixture(f.storage);assert.equal(next.calls.length,0);next.setReply(async(url,options)=>options.body?{}:p);
  await next.click('recoverSavedPreparation');assert.equal(next.calls[0].options.body,original);assert.equal(new C.Journal(f.storage).list().length,0);
});
test('another open workflow during preparation never receives its late ticket',async()=>{
  const f=fixture();let finish,p;f.setReply(async(url,options)=>{if(options.body){p=packetFixture(JSON.parse(options.body).request_id);return new Promise(r=>{finish=r;});}return p;});
  const running=f.click('prepareSavedRun');f.project({id:'document-b'});finish({});await running;
  assert.equal(f.ids.get('executeSavedRun').disabled,true);assert.match(f.ids.get('savedRunMessage').textContent,/open workflow changed/);
});
test('history response is ignored after the open saved revision changes',async()=>{
  const f=fixture();let finish;f.setReply(async()=>new Promise(r=>{finish=r;}));const loading=f.click('loadSavedRuns');f.project({id:'document-b'});
  finish({document_id:'document-a',runs:[{request_id:'old',document_id:'document-a',revision:1,sequence:1}],next_before:null});await loading;
  assert.equal(f.ids.get('savedRunHistory').children.length,1);
});
test('review downloads exact bytes and execution sends hashes, never parsed seeds',async()=>{
  const f=fixture();await f.original();await f.click('downloadSavedTicket');assert.equal(await f.downloads[0].blob.text(),f.packet().ticket_json);
  f.consent(false);await f.click('executeSavedRun');assert.equal(f.calls.length,1);
  f.consent(true);f.project({dirty:true,revision:2});await f.click('executeSavedRun');const body=JSON.parse(f.calls[1].options.body);
  assert.deepEqual(Object.keys(body).sort(),['approved','record_sha256','ticket_sha256']);assert.equal(body.ticket_sha256,f.packet().source.ticket_sha256);
  assert.match(f.ids.get('savedRunSource').textContent,/editor differs/);
});
test('lost dispatch and malformed replies retain original identity with no automatic retry',async()=>{
  const f=fixture();await f.original();f.setReply(async()=>{throw Error('lost');});await f.click('executeSavedRun');const body=f.calls[1].options.body;
  assert.match(f.ids.get('savedRunMessage').textContent,/Outcome may be unknown/);assert.equal(f.calls.length,2);
  f.setReply(async()=>({source:f.packet().source,dispatch:{job:{id:'other',status:'completed'}}}));await f.click('executeSavedRun');
  assert.equal(f.calls[2].options.body,body);assert.match(f.ids.get('savedRunMessage').textContent,/Malformed dispatch evidence/);
});
test('retention failure stops both preparation and dispatch before network',async()=>{
  const f=fixture();f.storage.fail=true;await f.click('prepareSavedRun');assert.equal(f.calls.length,0);
  f.storage.fail=false;await f.original();f.storage.fail=true;await f.click('executeSavedRun');assert.equal(f.calls.length,1);
});
test('missing job observation is GET-only and never claims no submission',async()=>{
  const f=fixture();await f.original();await f.click('observeSavedRun');assert.equal(f.calls[1].options.body,undefined);
  assert.match(f.ids.get('savedRunMessage').textContent,/not_observed/);assert.match(f.ids.get('savedRunMessage').textContent,/No submission status was inferred/);
});
test('duplicate clicks during active preparation issue only one POST',async()=>{
  const f=fixture();let finish,p;f.setReply(async(url,options)=>{if(options.body){p=packetFixture(JSON.parse(options.body).request_id);return new Promise(r=>{finish=r;});}return p;});
  const a=f.click('prepareSavedRun');await f.click('prepareSavedRun');assert.equal(f.calls.length,1);finish({});await a;
});
