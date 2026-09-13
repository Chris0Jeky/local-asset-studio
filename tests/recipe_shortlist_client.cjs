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
const sourceQuery={goal:'edit-image',reference_count:1,limit:6,offset:0,source_asset_id:'asset-0',source_sha256:'b'.repeat(64),source_role:'pose'};
const sourceReport=()=>({...report(),goal:'edit-image',reference_count:1,source:{asset_id:'asset-0',sha256:'b'.repeat(64),role:'pose',title:'My image',width:32,height:48,bytes_verified:true,staged:false}});
test('binds an exact primary source without treating it as attached',()=>{assert.deepEqual(C.validate(sourceReport(),sourceQuery),sourceReport())});
test('refuses missing substituted or staged source observations',()=>{
 for(const source of [undefined,null,{...sourceReport().source,asset_id:'other'},{...sourceReport().source,sha256:'c'.repeat(64)},{...sourceReport().source,role:'identity'},{...sourceReport().source,bytes_verified:false},{...sourceReport().source,staged:true},{...sourceReport().source,width:0}])assert.throws(()=>C.validate({...sourceReport(),source},sourceQuery));
 assert.throws(()=>C.validate({...report(),source:sourceReport().source},query));
});
test('changing advice source discards a delayed source-bound reply',async()=>{
 const pending=deferred(),events=[];const s=new C.Session(()=>pending.promise,e=>events.push(e));const work=s.load(sourceQuery);
 s.invalidate('Source changed');pending.resolve(sourceReport());await work;
 assert.equal(events.filter(e=>e.report).length,0);
});
const orderedQuery={goal:'edit-image',reference_count:2,limit:6,offset:0,sources:[
  {asset_id:'asset-0',sha256:'b'.repeat(64),role:'identity'},
  {asset_id:'asset-1',sha256:'c'.repeat(64),role:'pose'}]};
const orderedReport=()=>({...report(),goal:'edit-image',reference_count:2,source:null,
  sources:orderedQuery.sources.map((x,i)=>({...x,slot:i+1,title:'Picture '+(i+1),width:32,height:48,bytes_verified:true,staged:false})),
  total:1,counts:{observed:0,unknown:1,needs_setup:0},candidates:[{preset_id:'roles',name:'Roles',description:'Fixture',backend_id:'primary',operation:'instruction-edit',prompt_role:'instruction',reference_count:2,template_sha256:'d'.repeat(64),status:'unknown',checks:[],requirements:[],
  source_assignments:orderedQuery.sources.map((x,i)=>({...x,slot:i+1,binding:[String(i+1),'image'],role_mode:'prompt-guidance'}))}]});
test('ordered observations bind every image, proposed role and exact position',()=>{assert.equal(C.validate(orderedReport(),orderedQuery).sources.length,2)});
test('ordered report cannot omit swap stage or substitute a source',()=>{
 const edits=[r=>delete r.sources,r=>r.sources.reverse(),r=>r.sources[1].role='identity',r=>r.sources[1].staged=true,r=>r.sources[1].bytes_verified=false,r=>r.sources[0].slot=true,r=>r.source=r.sources[0]];
 for(const edit of edits){const r=orderedReport();edit(r);assert.throws(()=>C.validate(r,orderedQuery));}
 assert.throws(()=>C.validate({...report(),sources:orderedReport().sources},query));
});
test('ordered candidate assignments cannot be omitted compressed reordered or misbound',()=>{
 const edits=[r=>delete r.candidates[0].source_assignments,r=>r.candidates[0].source_assignments.pop(),r=>r.candidates[0].source_assignments.reverse(),r=>r.candidates[0].source_assignments[1].asset_id='other',r=>r.candidates[0].source_assignments[1].binding=['2','mask']];
 for(const edit of edits){const r=orderedReport();edit(r);assert.throws(()=>C.validate(r,orderedQuery));}
});
test('in-flight request keeps a value snapshot of nested source intent',async()=>{
 const q=structuredClone(orderedQuery),gate=deferred(),events=[];let sent;
 const s=new C.Session(x=>{sent=x;return gate.promise},e=>events.push(e));const work=s.load(q);
 q.sources[1].role='style';q.sources.reverse();assert.deepEqual(sent.sources,orderedQuery.sources);
 gate.resolve(orderedReport());await work;assert.equal(events.filter(e=>e.report).length,1);
});
