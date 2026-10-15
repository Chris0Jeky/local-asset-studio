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
  const f={stamp:'initial',busy:false,available:true,job:structuredClone(base),requests:[],applied:[],notes:[],confirmations:[],accepted:true,all:[]};
  f.all=[f.job];
  f.result=()=>{const claim={...structuredClone(f.job.parallax),stage:'plate'};const {stage,...plan}=claim;return {plan,claim,stage,preset_id:claim.preset_id,file:claim.source_file,width:claim.width,height:claim.height,words:'Remove the desk.',generation_submitted:false};};
  f.controller=api.create({stamp:()=>f.stamp,busy:()=>f.busy,available:()=>f.available,job:id=>f.all.find(entry=>entry.id===id)||null,jobs:()=>f.all,
    confirm:words=>{f.confirmations.push(words);return f.accepted;},request:async body=>{f.requests.push(body);return f.transport?f.transport():f.result();},apply:(result,note)=>{f.applied.push(result);f.notes.push(note||'');}});
  return f;
}
function sibling(status){
  const job=structuredClone(base);
  job.id='isolate-job';
  job.status=status;
  job.parallax.stage='isolate';
  job.outputs=[];
  return job;
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
test('live same-plan activity stays visible in the recall confirmation and success',async()=>{
  const f=fixture();f.all.push(sibling('running'));
  assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.deepEqual(f.requests,[{job_id:'plate-job',stage:'plate'}]);
  assert.equal(f.applied.length,1);
  assert.equal(f.applied[0].generation_submitted,false);
  assert.equal(f.applied[0].plan.plan_id,base.parallax.plan_id);
  assert.match(f.confirmations[0],/Nothing runs/);
  assert.match(f.confirmations[0],/running/);
  assert.match(f.confirmations[0],/Wait for the original job/);
  assert.match(f.notes[0],/running/);
  assert.match(f.notes[0],/Wait for the original job/);
});
test('uncertain same-plan activity forbids repetition in the recall confirmation and success',async()=>{
  const f=fixture();f.all.push(sibling('uncertain'));
  assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.deepEqual(f.requests,[{job_id:'plate-job',stage:'plate'}]);
  assert.equal(f.applied.length,1);
  assert.equal(f.applied[0].generation_submitted,false);
  assert.equal(f.applied[0].plan.plan_id,base.parallax.plan_id);
  assert.match(f.confirmations[0],/Nothing runs/);
  assert.match(f.confirmations[0],/uncertain/);
  assert.match(f.confirmations[0],/Inspect the original job/);
  assert.match(f.confirmations[0],/do not repeat/i);
  assert.match(f.notes[0],/uncertain/);
  assert.match(f.notes[0],/Inspect the original job/);
  assert.match(f.notes[0],/do not repeat/i);
});
test('success shows the current sibling context after the response, not stale data',async()=>{
  const f=fixture();const live=sibling('running');f.all.push(live);
  let release;f.transport=()=>new Promise(resolve=>{release=resolve;});
  const pending=f.controller.load('plate-job','plate');
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(f.confirmations[0],/running/);
  live.status='uncertain';
  release(f.result());
  assert.equal(await pending,true);
  assert.match(f.notes[0],/uncertain/);
  assert.match(f.notes[0],/Inspect the original job/);
});
test('success refreshes sibling status after the checked stage response and keeps a failed refresh as the pre-request observation',async()=>{
  const f=fixture(),plate=f.job,running=Object.freeze(sibling('running'));
  let list=Object.freeze([plate,running]);
  const seen={refresh:0,submitted:false,words:false};
  const arm=()=>{seen.submitted=false;seen.words=false;};
  f.controller=api.create({
    stamp:()=>f.stamp,busy:()=>f.busy,available:()=>f.available,
    job:id=>list.find(entry=>entry.id===id)||null,jobs:()=>list,
    confirm:words=>{f.confirmations.push(words);return f.accepted;},
    request:async body=>{
      const mark=seen.refresh;seen.submitted=false;seen.words=false;f.requests.push(body);
      const result=f.transport?await f.transport():f.result();
      assert.equal(seen.refresh,mark);
      return result&&typeof result==='object'?new Proxy(result,{get(target,prop,receiver){
        if(prop==='generation_submitted')seen.submitted=true;if(prop==='words')seen.words=true;
        return Reflect.get(target,prop,receiver);
      }}):result;
    },
    refresh:async()=>{
      assert.ok(seen.submitted&&seen.words,'refresh runs only after the stage response passed checkResponse');
      assert.equal(f.applied.length,0);assert.equal(f.requests.length,1);
      assert.equal(list[1].status,'running');assert.ok(Object.isFrozen(list)&&Object.isFrozen(list[1]));
      seen.refresh++;list=Object.freeze([plate,Object.freeze(sibling('uncertain'))]);
      if(f.refreshError)throw f.refreshError;
    },
    apply:(result,note)=>{f.applied.push(result);f.notes.push(note||'');}
  });
  arm();assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.equal(seen.refresh,1);assert.deepEqual(f.requests,[{job_id:'plate-job',stage:'plate'}]);
  assert.equal(f.applied.length,1);assert.equal(f.applied[0].generation_submitted,false);
  assert.match(f.confirmations[0],/running/);assert.match(f.confirmations[0],/Wait for the original job/);
  assert.doesNotMatch(f.confirmations[0],/uncertain/);
  assert.match(f.notes[0],/uncertain/);assert.match(f.notes[0],/Inspect the original job/);
  assert.doesNotMatch(f.notes[0],/Wait for the original job/);assert.doesNotMatch(f.notes[0],/\brunning\b/);
  list=Object.freeze([plate,running]);seen.refresh=0;f.refreshError=Error('jobs unread');
  f.notes.length=0;f.applied.length=0;f.requests.length=0;f.confirmations.length=0;arm();
  assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.equal(seen.refresh,1);assert.deepEqual(f.requests,[{job_id:'plate-job',stage:'plate'}]);
  assert.equal(f.applied.length,1);assert.equal(f.applied[0].generation_submitted,false);
  assert.equal(list[1].status,'uncertain');
  assert.match(f.notes[0],/retained observation/i);assert.match(f.notes[0],/from before the request/);
  assert.match(f.notes[0],/running/);assert.match(f.notes[0],/Wait for the original job/);
  assert.doesNotMatch(f.notes[0],/uncertain/);assert.doesNotMatch(f.notes[0],/current/);
  f.refreshError=null;
  const quiet=async(run,pattern,requestDelta)=>{
    const refreshBefore=seen.refresh,appliedBefore=f.applied.length,requestsBefore=f.requests.length;
    arm();
    if(pattern)await assert.rejects(run(),pattern);else assert.equal(await run(),false);
    assert.equal(seen.refresh,refreshBefore);assert.equal(f.applied.length,appliedBefore);
    assert.equal(f.requests.length,requestsBefore+(requestDelta||0));
  };
  f.accepted=false;await quiet(()=>f.controller.load('plate-job','plate'));f.accepted=true;
  f.busy=true;await quiet(()=>f.controller.load('plate-job','plate'),/current Create/);f.busy=false;
  f.available=false;await quiet(()=>f.controller.load('plate-job','plate'),/recipe|backend/);f.available=true;
  f.transport=()=>{const result=f.result();result.claim.plan_id='d'.repeat(64);return result;};
  await quiet(()=>f.controller.load('plate-job','plate'),/response/,1);f.transport=null;
  f.transport=()=>{throw Error('transport refused');};
  await quiet(()=>f.controller.load('plate-job','plate'),/transport refused/,1);f.transport=null;
  const valid=f.result();let release;f.transport=()=>new Promise(resolve=>{release=resolve;});
  const refreshBefore=seen.refresh,appliedBefore=f.applied.length,requestsBefore=f.requests.length;
  arm();const pending=f.controller.load('plate-job','plate');
  await new Promise(resolve=>setImmediate(resolve));
  const saved=plate.parallax.plan_id;plate.parallax.plan_id='e'.repeat(64);release(valid);
  await assert.rejects(pending,/changed/);plate.parallax.plan_id=saved;
  assert.equal(seen.refresh,refreshBefore);assert.equal(f.applied.length,appliedBefore);
  assert.equal(f.requests.length,requestsBefore+1);
});
test('a refreshed source keeps the pre-request plan when the replacement record changes identity',async()=>{
  const f=fixture(),plate=f.job;
  let list=[plate,sibling('running')];
  f.controller=api.create({
    stamp:()=>f.stamp,busy:()=>f.busy,available:()=>f.available,
    job:id=>list.find(entry=>entry.id===id)||null,jobs:()=>list,
    confirm:words=>{f.confirmations.push(words);return true;},
    request:async body=>{f.requests.push(body);return f.result();},
    refresh:async()=>{const replaced=structuredClone(plate);replaced.parallax.plan_id='f'.repeat(64);list=[replaced,sibling('uncertain')];},
    apply:(result,note)=>{f.applied.push(result);f.notes.push(note||'');}
  });
  assert.equal(await f.controller.load('plate-job','plate'),true);
  assert.equal(f.applied.length,1);assert.equal(f.applied[0].generation_submitted,false);
  assert.equal(list[0].parallax.plan_id,'f'.repeat(64));
  assert.match(f.notes[0],/uncertain/);assert.match(f.notes[0],/Inspect the original job/);
  assert.doesNotMatch(f.notes[0],/retained observation/i);assert.doesNotMatch(f.notes[0],/Wait for the original job/);
});
test('readJobList keeps a 304, accepts a job array, and refuses a failed or non-array body',async()=>{
  const etag='"jobs"',headers={get:name=>name==='ETag'?etag:null};
  assert.deepEqual(await api.readJobList(async()=>({status:304,ok:false,headers})),{unchanged:true});
  const jobs=[{id:'plate-job'}];
  assert.deepEqual(await api.readJobList(async()=>({status:200,ok:true,json:async()=>jobs,headers})),{unchanged:false,jobs,etag});
  await assert.rejects(api.readJobList(async()=>({status:500,ok:false,headers})),/could not be refreshed/);
  await assert.rejects(api.readJobList(async()=>({status:200,ok:true,json:async()=>({error:'no'}),headers})),/could not be refreshed/);
});
test('mount refreshes through readJobList, redraws a changed list, and does not poll or estimate',()=>{
  const body=fs.readFileSync(path,'utf8');
  const refresh=body.slice(body.indexOf('refresh:'),body.indexOf('available:'));
  assert.match(refresh,/readJobList/);assert.match(refresh,/\/api\/jobs/);assert.match(refresh,/renderJobs\(signature\)/);
  assert.doesNotMatch(refresh,/refreshJobs|scheduleTimeEstimate/);
});
