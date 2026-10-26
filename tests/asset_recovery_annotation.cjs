'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const Journal=require('../app/static/asset-recovery.js'),Shelf=require('../app/static/asset-recovery-shelf.js');
const Session=require('../app/static/asset-recovery-shelf-session.js'),crypto=require('node:crypto').webcrypto;
const createShelf=require('./asset_recovery_shelf_memory.cjs');
const W='1'.repeat(32),REQUEST='refusal-request-0001',AT=1793037600000;
const clone=value=>JSON.parse(JSON.stringify(value));
function memory(){const values=new Map();return {values,getItem:key=>values.get(key)??null,setItem(key,value){if(this.failWrite)throw Error('synthetic quota');values.set(key,value);},removeItem:key=>values.delete(key)};}
function payload(slot='detail',note='newer local typing'){
  const command={ids:slot==='detail'?['a']:['a','b'],action:'edit',notes:'submitted snapshot',workspace_id:W,
    expected_revisions:slot==='detail'?{a:3}:{a:3,b:7},request_id:REQUEST};
  const operation={command,body:JSON.stringify(command,null,2)};
  if(slot==='library')return {version:2,workspace_id:W,operation,selection:['b','a']};
  const baseline={title:'Asset',tags:'kept',review:'unreviewed',notes:'baseline'},draft={...baseline,notes:note};
  return {version:2,workspace_id:W,id:'a',metadata:{id:'a',workspace_id:W,metadata_revision:3,title:'Asset',notes:'baseline',tags:['kept'],review:'unreviewed',favorite:false,trashed_at:null},
    baseline,draft,operation:{...operation,kind:'details',snapshot:{...baseline,notes:'submitted snapshot'}},conflict:null};
}
const annotation=(extra={})=>({version:1,workspace_id:W,request_id:REQUEST,status:403,code:'asset_policy_refused',message:'<img src=x> denied this attempt; earlier outcome unknown',observed_at:AT,...extra});
const refusal=(extra={})=>Object.assign(Error('<img src=x> denied this attempt; earlier outcome unknown'),{status:403,data:{code:'asset_policy_refused'},...extra});
async function seal(slot,value){return Shelf.seal(slot,value,{id:'a'.repeat(32),created_at:AT,updated_at:AT,generation:1},crypto);}

for(const slot of ['detail','library']){
  test(slot+' old payload and annotated shelf restore keep exact pending bytes',async()=>{
    const store=memory(),journal=Journal.create(store),old=payload(slot);journal.write(slot,old);assert.deepEqual(journal.read(slot),old);
    const value={...old,last_refusal:annotation()};journal.write(slot,value);
    const record=await seal(slot,journal.read(slot));assert.deepEqual(record.payload.last_refusal,annotation());
    const [imported]=await Shelf.decode(await Shelf.encode([record],crypto),crypto),target=Journal.create(memory());
    const session=Session.create({journal:target,store:null,crypto});session.restore(imported,W);
    assert.equal(target.read(slot).operation.body,old.operation.body);assert.deepEqual(target.read(slot).last_refusal,annotation());
    if(slot==='detail')assert.equal(target.read(slot).draft.notes,'newer local typing');else assert.deepEqual(target.read(slot).selection,['b','a']);
  });
  test(slot+' recording one refusal preserves the latest payload and command independently',()=>{
    const storage=memory(),journal=Journal.create(storage),value=payload(slot);journal.write(slot,value);
    const before=clone(journal.read(slot)),updated=journal.recordRefusal(slot,value.operation,refusal(),{current:()=>true,observedAt:AT});
    assert.deepEqual(updated,{...before,last_refusal:annotation()});assert.deepEqual(journal.read(slot),updated);
    assert.deepEqual(value,payload(slot),'recording must not mutate its caller snapshot');
    const copied=Journal.lastRefusal(updated,value.operation);assert.deepEqual(copied,annotation());copied.message='changed copy';assert.deepEqual(journal.read(slot).last_refusal,annotation());
  });
  test(slot+' stale body, identity or owner cannot annotate a replacement record',()=>{
    const storage=memory(),journal=Journal.create(storage),value=payload(slot);journal.write(slot,value);const raw=storage.getItem(Journal.PREFIX+slot);
    for(const change of [op=>{op.body=JSON.stringify(op.command);},op=>{op.command.request_id='another-request-0001';},op=>{op.command.workspace_id='2'.repeat(32);},op=>{op.command.expected_revisions.a=4;}]){
      const stale=clone(value.operation);change(stale);
      assert.equal(journal.recordRefusal(slot,stale,refusal(),{current:()=>true,observedAt:AT}),null);assert.equal(storage.getItem(Journal.PREFIX+slot),raw);
    }
    assert.equal(journal.recordRefusal(slot,value.operation,refusal(),{current:()=>false,observedAt:AT}),null);assert.equal(storage.getItem(Journal.PREFIX+slot),raw);
  });
  test(slot+' refused transport identity and non-refusal failures cannot replace the last explanation',()=>{
    const storage=memory(),journal=Journal.create(storage),value={...payload(slot),last_refusal:annotation()};journal.write(slot,value);const raw=storage.getItem(Journal.PREFIX+slot);
    for(const error of [refusal({status:500}),refusal({status:'403'}),refusal({data:{workspace_id:null}}),refusal({data:{workspace_id:'2'.repeat(32)}}),
      refusal({data:{request_id:''}}),refusal({data:{request_id:'another-request-0001'}}),refusal({data:{code:'asset_workspace_conflict'}})]){
      assert.equal(journal.recordRefusal(slot,value.operation,error,{current:()=>true,observedAt:AT+1}),null);assert.equal(storage.getItem(Journal.PREFIX+slot),raw);
    }
  });
  test(slot+' exact retry replaces only its bounded last explanation and carries no new command',()=>{
    const storage=memory(),journal=Journal.create(storage),value={...payload(slot),last_refusal:annotation()};journal.write(slot,value);
    const error=Object.assign(Error('😀'.repeat(1002)),{status:429,data:{code:'rate_limited',workspace_id:W,request_id:REQUEST}});
    const updated=journal.recordRefusal(slot,value.operation,error,{current:()=>true,observedAt:AT+1});
    assert.equal(updated.operation.body,value.operation.body);assert.deepEqual(updated.operation.command,value.operation.command);
    assert.equal(updated.last_refusal.status,429);assert.equal(updated.last_refusal.code,'rate_limited');assert.equal(updated.last_refusal.observed_at,AT+1);
    assert.equal([...updated.last_refusal.message].length,1000);assert.equal(updated.last_refusal.message,'😀'.repeat(999)+'…');
    assert.equal(Journal.lastRefusal(updated,null),null);assert.equal(Journal.lastRefusal(updated,{...value.operation,body:JSON.stringify(value.operation.command)}),null);
  });
  test(slot+' annotation quota failure preserves the pending recovery and its latest draft',()=>{
    const storage=memory(),journal=Journal.create(storage),value=payload(slot);journal.write(slot,value);const raw=storage.getItem(Journal.PREFIX+slot);storage.failWrite=true;
    assert.throws(()=>journal.recordRefusal(slot,value.operation,refusal(),{current:()=>true,observedAt:AT}),/retain|quota|recovery/i);assert.equal(storage.getItem(Journal.PREFIX+slot),raw);
    assert.deepEqual(journal.read(slot),value);
  });
}

for(const [name,change] of [
  ['future version',r=>r.version=2],['unknown field',r=>r.extra='unadmitted'],['foreign Workspace',r=>r.workspace_id='2'.repeat(32)],
  ['foreign request',r=>r.request_id='another-request-0001'],['empty message',r=>r.message=''],['oversized Unicode message',r=>r.message='😀'.repeat(1001)],
  ['non-text message',r=>r.message=42],['oversized code',r=>r.code='x'.repeat(65)],['non-text code',r=>r.code=42],['markup code',r=>r.code='<script>'],
  ['string status',r=>r.status='403'],['server error status',r=>r.status=500],['fractional status',r=>r.status=403.1],['negative time',r=>r.observed_at=-1],
  ['fractional time',r=>r.observed_at=.5],['out-of-range date',r=>r.observed_at=8640000000000001],['string time',r=>r.observed_at=String(AT)]
])test('invalid annotation '+name+' refuses journal and shelf without replacing evidence',async()=>{
  const storage=memory(),journal=Journal.create(storage),old=payload();journal.write('detail',old);const raw=storage.getItem(Journal.PREFIX+'detail'),bad={...payload(),last_refusal:annotation()};change(bad.last_refusal);
  assert.throws(()=>journal.write('detail',bad),/retain|safe/i);assert.equal(storage.getItem(Journal.PREFIX+'detail'),raw);
  const malformed=JSON.stringify(bad);storage.values.set(Journal.PREFIX+'detail',malformed);assert.throws(()=>journal.read('detail'),/retained|safely/i);assert.equal(storage.getItem(Journal.PREFIX+'detail'),malformed);
  assert.throws(()=>journal.recordRefusal('detail',old.operation,refusal(),{observedAt:AT}),/retained|safely/i);assert.equal(storage.getItem(Journal.PREFIX+'detail'),malformed);
  await assert.rejects(seal('detail',bad),/refusal|annotation|invalid|bound|version/i);
});

test('maximum Unicode text, code and date boundaries remain usable without truncation',async()=>{
  const value={...payload(),last_refusal:annotation({message:'😀'.repeat(1000),code:'a'.repeat(64),observed_at:8640000000000000})};
  const journal=Journal.create(memory());journal.write('detail',value);const record=await seal('detail',value);
  assert.deepEqual(record.payload.last_refusal,value.last_refusal);assert.equal(Buffer.byteLength(record.payload.last_refusal.message,'utf8'),4000);
});
test('generic refusal keeps its literal explanation without inventing a server code',()=>{
  const journal=Journal.create(memory()),value=payload();journal.write('detail',value);
  const updated=journal.recordRefusal('detail',value.operation,refusal({data:{error:'refused'}}),{observedAt:AT});
  assert.equal(updated.last_refusal.message,annotation().message);assert.equal(Object.hasOwn(updated.last_refusal,'code'),false);
});
test('annotation without a verified pending scope is refused',async()=>{
  for(const change of [v=>v.operation=null,v=>{v.version=1;delete v.workspace_id;delete v.metadata.workspace_id;delete v.operation.command.workspace_id;v.operation.body=JSON.stringify(v.operation.command);}]){
    const value={...payload(),last_refusal:annotation()};change(value);assert.throws(()=>Journal.create(memory()).write('detail',value),/safe|retain/i);await assert.rejects(seal('detail',value),/refusal|annotation|invalid|scope/i);
  }
});
test('annotation digest tampering refuses the imported bundle',async()=>{
  const record=await seal('detail',{...payload(),last_refusal:annotation()});
  const raw=await Shelf.encode([record],crypto);await assert.rejects(Shelf.decode(raw.replace('denied this attempt','fabricated success'),crypto),/digest/i);
});
test('annotation checkpoints update the same shelf record without mutating its immutable operation',async()=>{
  const local=memory(),tab=memory(),journal=Journal.create(tab);let tail=Promise.resolve();const locks={request(name,options,fn){const next=tail.then(fn);tail=next.catch(()=>{});return next;}};
  const store=createShelf({storage:local,locks,crypto}),session=Session.create({journal,store,crypto});const value=payload();journal.write('detail',value);await session.enable();const [before]=await store.list();
  journal.recordRefusal('detail',value.operation,refusal(),{current:()=>true,observedAt:AT});await session.flush();const records=await store.list();
  assert.equal(records.length,1);assert.equal(records[0].id,before.id);assert.equal(records[0].generation,before.generation+1);assert.deepEqual(records[0].payload.operation,before.payload.operation);assert.deepEqual(records[0].payload.last_refusal,annotation());
  journal.clear('detail');await session.flush();assert.equal(journal.read('detail'),null);assert.deepEqual(await store.list(),records,'clearing current recovery must not erase historical shelf evidence');
});
