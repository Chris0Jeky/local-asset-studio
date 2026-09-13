const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../app/static/recipe-shortlist.js');
const query={goal:'new-image',reference_count:0,limit:6,offset:0};
const report=()=>({format:'studio.recipe-shortlist/v1',goal:'new-image',reference_count:0,snapshot_sha256:'a'.repeat(64),
  candidates:[],total:0,offset:0,next_offset:null,counts:{observed:0,unknown:0,needs_setup:0},diagnostics:[],checked_at:123,
  generation_submitted:false,execution_authorized:false,scope:'Default graph only'});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{resolve,reject,promise}};
test('does not request on construction or field invalidation',()=>{let calls=0;const s=new C.Session(()=>{calls++},()=>{});s.invalidate();assert.equal(calls,0)});
test('accepts matching bounded read-only reports',()=>{assert.deepEqual(C.validate(report(),query),report())});
test('rejects wrong context, authority, shape and page metadata',()=>{
 for(const patch of [{goal:'edit-image'},{reference_count:1},{generation_submitted:true},{execution_authorized:true},{candidates:Array(13).fill({})},{next_offset:0},{snapshot_sha256:'bad'},{offset:3},{total:-1}])assert.throws(()=>C.validate({...report(),...patch},query));
});
test('single flight and explicit invalidation discard a late response',async()=>{
 let calls=0,signal;const gate=deferred(),events=[];const s=new C.Session((q,sg)=>{calls++;signal=sg;return gate.promise},e=>events.push(e));
 const pending=s.load(query);await s.load(query);assert.equal(calls,1);s.invalidate();assert.equal(signal.aborted,true);
 gate.resolve(report());await pending;assert.equal(events.filter(e=>e.report).length,0);
});
test('A to B to A cannot revive the original reply',async()=>{
 const first=deferred(),second=deferred(),events=[];let count=0;
 const s=new C.Session(()=>++count===1?first.promise:second.promise,e=>events.push(e));
 const a=s.load(query);s.invalidate();const b=s.load(query);second.resolve(report());await b;first.resolve({...report(),snapshot_sha256:'b'.repeat(64)});await a;
 assert.deepEqual(events.filter(e=>e.report).map(e=>e.report.snapshot_sha256),['a'.repeat(64)]);
});
test('transport failure does not retry or leave a busy session',async()=>{
 let calls=0;const events=[];const s=new C.Session(async()=>{calls++;throw Error('offline')},e=>events.push(e));await s.load(query);
 assert.equal(calls,1);assert.equal(s.busy,false);assert.match(events.at(-1).message,/offline/);
});
test('deadline aborts the actual read and does not turn later success into evidence',async()=>{
 let fire,cleared=0,signal;const events=[],gate=deferred();
 const s=new C.Session((q,sg)=>{signal=sg;return gate.promise},e=>events.push(e),{set:fn=>{fire=fn;return 1},clear:()=>cleared++});
 const pending=s.load(query);fire();assert.equal(signal.aborted,true);assert.equal(s.busy,false);gate.resolve(report());await pending;
 assert.equal(events.filter(e=>e.report).length,0);assert.match(events.at(-1).message,/timed out/);assert.ok(cleared);
});
test('invalid responses preserve no actionable stale report',async()=>{
 const events=[];const s=new C.Session(async()=>({...report(),goal:'edit-image'}),e=>events.push(e));await s.load(query);
 assert.equal(events.filter(e=>e.report).length,0);assert.match(events.at(-1).message,/context/);
});
