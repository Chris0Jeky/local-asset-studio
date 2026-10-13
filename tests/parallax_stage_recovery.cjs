'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync(require.resolve('../app/static/app.js'),'utf8');
const definition=source.slice(source.indexOf('function parallaxNote('),source.indexOf('function renderCompare('));
const base={id:'plate-job',status:'completed',parallax:{version:1,plan_id:'c'.repeat(64),stage:'plate',preset_id:'parallax-demo',source_asset_id:'source',source_sha256:'a'.repeat(64),source_file:'b'.repeat(32)+'_room.jpg',width:512,height:640,objects:'the desk',view_polygons:[]}};
const esc=value=>String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const s={jobs:[],esc};vm.createContext(s);vm.runInContext(definition,s);
const path=require('node:path').join(__dirname,'../app/static/parallax-stage-recovery.js');
const api=fs.existsSync(path)?require(path):null;
const render=(job,output={})=>api?api.render(job,output,s.parallaxNote(job,output),esc):s.parallaxNote(job,output);

test('completed stages retain both explicit reload actions after a split',()=>{
  const html=render({...base,parallax_finish:{job_id:'split',summary:'Measured split'}});
  for(const stage of ['plate','isolate'])assert.match(html,new RegExp('data-stage="'+stage+'"'));
  assert.match(html,/Layers split/);
});
test('unsplit cards retain existing status and do not duplicate the existing next-stage action',()=>{
  const html=render(base);
  for(const stage of ['plate','isolate'])assert.equal((html.match(new RegExp('data-stage="'+stage+'"','g'))||[]).length,1);
  assert.match(html,/no isolate edit yet/);
});
test('running jobs and finished layer outputs receive no stage reload controls',()=>{
  for(const status of ['queued','running','failed','uncertain'])assert.doesNotMatch(render({...base,status}),/parallaxStage/);
  assert.doesNotMatch(render(base,{parallax:{layer:'near',shift_px:24,summary:'Measured'}}),/parallaxStage/);
});

function fixture(){
  assert.ok(api,'stage recovery controller must be shipped');
  const f={stamp:'initial',busy:false,available:true,job:structuredClone(base),requests:[],applied:[],confirmations:[],accepted:true};
  f.result=()=>{const claim={...structuredClone(f.job.parallax),stage:'plate'};const {stage,...plan}=claim;return {plan,claim,stage,preset_id:claim.preset_id,file:claim.source_file,width:claim.width,height:claim.height,words:'Remove the desk.',generation_submitted:false};};
  f.controller=api.create({stamp:()=>f.stamp,busy:()=>f.busy,available:()=>f.available,job:id=>id===f.job.id?f.job:null,
    confirm:words=>{f.confirmations.push(words);return f.accepted;},request:async body=>{f.requests.push(body);return f.transport?f.transport():f.result();},apply:result=>f.applied.push(result)});
  return f;
}
test('reload asks before replacing Create and sends only an explicit stage request',async()=>{
  const f=fixture();assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.deepEqual(f.requests,[{job_id:'plate-job',stage:'plate'}]);assert.equal(f.applied.length,1);assert.match(f.confirmations[0],/Nothing runs/);
});
test('declined, busy, unavailable and invalid actions stage nothing',async()=>{
  const f=fixture();f.accepted=false;assert.equal(await f.controller.load('plate-job','plate'),false);
  f.accepted=true;f.busy=true;await assert.rejects(f.controller.load('plate-job','plate'),/current Create/);
  f.busy=false;f.available=false;await assert.rejects(f.controller.load('plate-job','plate'),/recipe|backend/);
  f.available=true;await assert.rejects(f.controller.load('plate-job','invented'),/stage/);
  await assert.rejects(f.controller.load('missing','plate'),/completed/);
  assert.equal(f.requests.length,0);assert.equal(f.applied.length,0);
});
test('a delayed response cannot overwrite newer draft state or a new upload',async()=>{
  for(const change of [f=>{f.stamp='newer typing';},f=>{f.busy=true;},f=>{f.available=false;},f=>{f.job.parallax.plan_id='d'.repeat(64);}]){
    const f=fixture();let release;f.transport=()=>new Promise(resolve=>{release=resolve;});
    const pending=f.controller.load('plate-job','plate');const result=f.result();change(f);release(result);
    await assert.rejects(pending,/changed|current Create|backend/);assert.equal(f.applied.length,0);
  }
});
test('duplicate clicks cannot issue competing requests and failures release the guard',async()=>{
  const f=fixture();let reject;f.transport=()=>new Promise((_,no)=>{reject=no;});
  const pending=f.controller.load('plate-job','plate');assert.equal(await f.controller.load('plate-job','isolate'),false);assert.equal(f.requests.length,1);
  reject(Error('transport refused'));await assert.rejects(pending,/transport refused/);f.transport=null;
  assert.equal(await f.controller.load('plate-job','plate'),true);assert.equal(f.applied.length,1);
});
test('mismatched response identities and geometry never reach Create',async()=>{
  for(const alter of [r=>{r.claim.stage='isolate';},r=>{r.plan.source_sha256='d'.repeat(64);},r=>{r.file='other.png';},r=>{r.width=640;},r=>{r.generation_submitted=true;},r=>{r.words='';},r=>{r.claim.view_polygons=[[[1,2],[3,4],[5,6]]];}]){
    const f=fixture();f.transport=()=>{const r=f.result();alter(r);return r;};
    await assert.rejects(f.controller.load('plate-job','plate'),/response/);assert.equal(f.applied.length,0);
  }
});
