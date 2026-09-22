'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const Core=require('../app/static/asset-recovery-shelf.js');
const path=require('node:path').join(__dirname,'../app/static/asset-recovery-lifecycle.js');
const Lens=fs.existsSync(path)?require(path):{};
const W='1'.repeat(32),Q='request_1234567890';
function record(count=1,action='edit'){
  const ids=Array.from({length:count},(_,i)=>'asset'+i);
  const c={ids,workspace_id:W,request_id:Q,expected_revisions:Object.fromEntries(ids.map(id=>[id,0])),action,
    ...(action==='edit'?{notes:'submitted'}:action.endsWith('_collection')?{collection_id:'group'}:{})};
  const form={title:'Synthetic',tags:'',review:'unreviewed',notes:'local draft'};
  const operation={command:c,body:JSON.stringify(c,null,2)};
  const payload=count===1?{version:2,workspace_id:W,id:ids[0],metadata:{id:ids[0],workspace_id:W,metadata_revision:0,title:'Synthetic',notes:'baseline',tags:[],review:'unreviewed',favorite:false,trashed_at:null},
    baseline:{...form,notes:'baseline'},draft:form,operation:{...operation,kind:'details',snapshot:{...form,notes:'submitted'}},conflict:null}:
    {version:2,workspace_id:W,operation,selection:ids};
  return {slot:count===1?'detail':'library',payload};
}
function observation(r,states=[]){
  const c=r.payload.operation.command,withCollection=c.action.endsWith('_collection');
  return {format:'studio.asset-recovery-observation/v1',workspace_id:W,observed_at:1,generation_submitted:false,
    collection:withCollection?{id:'group',exists:false}:null,
    targets:c.ids.map((id,i)=>states[i]==='missing'?{id,state:'missing'}:{id,state:states[i]||'active',title:'Synthetic',metadata_revision:1,
      collection_count:0,collections:[],collections_limited:false,...(withCollection?{in_collection:false}:{})})};
}
function receipt(r,status='applied'){
  const c=r.payload.operation.command;
  return {workspace_id:W,request_id:Q,status,...(status==='applied'?{action:c.action,updated:c.ids,
    revisions:Object.fromEntries(c.ids.map(id=>[id,1])),applied:{notes:'submitted'},current:[]}: {})};
}
function project(...args){assert.equal(typeof Lens.project,'function','read-only lifecycle projection must exist');return Lens.project(...args);}
function observer(options){assert.equal(typeof Lens.create,'function','read-only lifecycle observer must exist');return Lens.create({scope:()=>W,validateReceipt:()=>{},...options});}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};

test('historical receipt cannot make a missing target active or change exact command bytes',()=>{
  const r=record(),before=Core.canonical(r),p=project(r,observation(r,['missing']),receipt(r));
  assert.equal(p.targets[0].state,'missing');assert.equal(p.targets[0].receipt_revision,1);assert.equal(p.targets[0].metadata_revision,undefined);
  assert.equal(Core.canonical(r),before);
});
test('mixed selection retains all twelve IDs in order beyond the receipt current-preview cap',()=>{
  const r=record(12),o=observation(r,['active','trashed','missing']);const p=project(r,o,receipt(r));
  assert.deepEqual(p.targets.map(t=>t.id),r.payload.selection);assert.equal(p.targets[1].state,'trashed');assert.equal(p.targets[2].state,'missing');assert.equal(p.targets.length,12);
});
test('restoration is inferred only from a retained Trash state and a newer active revision',()=>{
  const r=record(1,'trash'),o=observation(r);o.targets[0].metadata_revision=2;
  assert.equal(project(r,o,receipt(r)).targets[0].restored_since_retained,true);
  const unrelated=record();assert.equal(project(unrelated,o,receipt(unrelated)).targets[0].restored_since_retained,false);
  o.targets[0].metadata_revision=0;assert.equal(project(r,o,receipt(r)).targets[0].restored_since_retained,false);
});
test('deleted collection is an observation and never recreates historical membership',()=>{
  const r=record(2,'add_collection'),p=project(r,observation(r),receipt(r));
  assert.equal(p.collection.exists,false);assert.ok(p.targets.every(t=>t.in_collection===false));
});
test('truncated, reordered, foreign and malformed current observations refuse as a whole',()=>{
  const r=record(12);
  for(const edit of [o=>o.targets.pop(),o=>o.targets.reverse(),o=>o.workspace_id='2'.repeat(32),o=>o.targets[0].metadata_revision=NaN,
    o=>o.targets[0].collections_limited=true,o=>o.targets[0].title='😀'.repeat(201),o=>o.generation_submitted=true]){
    const o=observation(r);edit(o);assert.throws(()=>project(r,o,receipt(r)));
  }
});
test('changed historical target set or revision is never accepted as confirmation',()=>{
  const r=record(2);for(const edit of [p=>p.updated.pop(),p=>p.revisions.asset0=99,p=>p.request_id='different_request_id',p=>p.workspace_id='2'.repeat(32)]){
    const p=receipt(r);p.updated=[...p.updated];edit(p);assert.throws(()=>project(r,observation(r),p));
  }
});
test('unavailable current read keeps all target IDs with an explicitly unavailable state',()=>{
  const r=record(12),p=project(r,null,receipt(r));assert.equal(p.targets.length,12);assert.ok(p.targets.every(t=>t.state==='unavailable'));
});
test('status and lifecycle read use only GET and do not mutate retained records',async()=>{
  const r=record(2),before=Core.canonical(r),requests=[],updates=[];let verified=0;
  const lens=observer({read:async(url,options)=>{requests.push({url,options});return url.includes('/commands/')?receipt(r):observation(r);},validateReceipt:()=>verified++,onUpdate:v=>updates.push(v)});
  assert.equal(requests.length,0);await lens.load(r);
  assert.equal(requests.length,2);assert.ok(requests.every(q=>q.options.method==='GET'&&!q.options.body));
  assert.equal(verified,1);assert.equal(updates.at(-1).phase,'ready');assert.equal(Core.canonical(r),before);
});
test('unknown stays unknown and never starts another request automatically',async()=>{
  const r=record(),updates=[];let requests=0;
  const lens=observer({read:async url=>{requests++;return url.includes('/commands/')?receipt(r,'unknown'):observation(r);},onUpdate:v=>updates.push(v)});
  await lens.load(r);assert.equal(updates.at(-1).receipt.status,'unknown');assert.equal(requests,2);
});
test('foreign and unscoped recovery dispatch zero reads',async()=>{
  let calls=0;const lens=observer({read:()=>{calls++;},onUpdate:()=>{}});
  const foreign=record();foreign.payload.workspace_id='2'.repeat(32);
  await assert.rejects(lens.load(foreign));
  const legacy=record();legacy.payload.version=1;delete legacy.payload.workspace_id;
  await assert.rejects(lens.load(legacy));assert.equal(calls,0);
});
test('late replies cannot populate a superseding inspection',async()=>{
  const old=record(),fresh=record(2),held=[],updates=[];
  const lens=observer({read:(url,options)=>{const d=deferred();held.push({...d,url,options});return d.promise;},onUpdate:v=>updates.push(v)});
  const a=lens.load(old),b=lens.load(fresh);assert.ok(held[0].options.signal.aborted);
  held[2].resolve(receipt(fresh));held[3].resolve(observation(fresh));await b;
  held[0].resolve(receipt(old));held[1].resolve(observation(old));await a;
  assert.equal(updates.filter(u=>u.phase==='ready').length,1);assert.equal(updates.at(-1).report.targets.length,2);
});
test('dialog cancellation and Workspace changes suppress stale receipt disclosure',async()=>{
  for(const change of ['cancel','workspace']){
    const r=record(),held=[],updates=[];let scope=W;
    const lens=observer({scope:()=>scope,read:()=>{const d=deferred();held.push(d);return d.promise;},onUpdate:v=>updates.push(v)});
    const p=lens.load(r);if(change==='cancel')lens.cancel();else scope='2'.repeat(32);
    held[0].resolve(receipt(r));held[1].resolve(observation(r));await p;
    assert.equal(updates.filter(u=>u.phase==='ready').length,0);
  }
});
test('current read failure retains independently verified historical receipt',async()=>{
  const r=record(),updates=[];
  const lens=observer({read:async url=>{if(url.includes('/commands/'))return receipt(r);throw Error('storage unavailable');},onUpdate:v=>updates.push(v)});
  await lens.load(r);assert.equal(updates.at(-1).receipt.status,'applied');assert.match(updates.at(-1).observation_error,/storage unavailable/);
  assert.equal(updates.at(-1).report.targets[0].state,'unavailable');
});
test('a draft without a command reads lifecycle only and never fabricates a receipt',async()=>{
  const r=record(),o=observation(r),updates=[];r.payload.operation=null;let calls=0;
  const lens=observer({read:async url=>{calls++;assert.ok(url.includes('/recovery-observation?'));return o;},onUpdate:v=>updates.push(v)});
  await lens.load(r);assert.equal(calls,1);assert.equal(updates.at(-1).receipt,null);
});
module.exports={record,observation,receipt};
