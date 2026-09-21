'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const Core=require('../app/static/asset-recovery-shelf.js'),Journal=require('../app/static/asset-recovery.js');
const source=require('node:path').join(__dirname,'../app/static/asset-recovery-shelf-session.js');
const Session=fs.existsSync(source)?require(source):{};
const crypto=require('node:crypto').webcrypto,W='1'.repeat(32);
function value(note='draft',pending=false){const form={title:'a',tags:'',review:'unreviewed',notes:note};const command={ids:['a'],action:'edit',notes:'snapshot',workspace_id:W,expected_revisions:{a:0},request_id:'0123456789abcdef'};return {version:2,workspace_id:W,id:'a',metadata:{id:'a',workspace_id:W,metadata_revision:0,title:'a',notes:'',tags:[],review:'unreviewed',favorite:false,trashed_at:null},baseline:{...form,notes:''},draft:form,operation:pending?{command,body:JSON.stringify(command,null,2),kind:'details',snapshot:{...form,notes:'snapshot'}}:null,conflict:null};}
function storage(){const data=new Map();return {getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};}
function device(){const local=storage();let tail=Promise.resolve();return {local,locks:{request(n,o,fn){const p=tail.then(fn);tail=p.catch(()=>{});return p;}}};}
function setup({shared=device()}={}){const journal=Journal.create(storage()),store=Core.create({storage:shared.local,locks:shared.locks,crypto});assert.equal(typeof Session.create,'function','shelf session controller must exist');const messages=[],session=Session.create({journal,store,crypto,onStatus:s=>messages.push(s)});return {journal,store,session,messages};}
function libraryValue(note='lib'){const command={ids:['a'],action:'edit',notes:note,workspace_id:W,expected_revisions:{a:0},request_id:'abcdef0123456789'};return {version:2,workspace_id:W,operation:{command,body:JSON.stringify(command)},selection:['a']};}
test('disabled controller does not persist ordinary journal changes',async()=>{const s=setup();s.journal.write('detail',value());await s.session.flush();assert.equal((await s.store.list()).length,0);});
test('opt-in mirrors drafts, coalesces typing and preserves immutable command bytes',async()=>{
  const s=setup();await s.session.enable();for(let i=0;i<1000;i++)s.journal.write('detail',value('draft '+i));await s.session.flush();let records=await s.store.list();assert.equal(records.length,1);assert.equal(records[0].payload.draft.notes,'draft 999');assert.ok(records[0].generation<=2);
  s.journal.write('detail',value('snapshot',true));await s.journal.dispatch('detail',value('snapshot',true).operation,()=>{});s.journal.write('detail',value('newer',true));await s.session.flush();records=await s.store.list();assert.equal(records.length,1);assert.equal(records[0].payload.operation.body,value('',true).operation.body);assert.equal(records[0].payload.draft.notes,'newer');
});
test('a cleared or replaced command never erases the earlier unresolved identity',async()=>{
  const s=setup();await s.session.enable();s.journal.write('detail',value('snapshot',true));await s.session.flush();s.journal.clear('detail');s.journal.write('detail',value('next'));await s.session.flush();const records=await s.store.list();assert.equal(records.length,2);assert.ok(records.some(r=>r.payload.operation));
});
test('a new command after clearing a non-command snapshot retains both shelf records',async()=>{
  const s=setup();await s.session.enable();s.journal.write('detail',value('first'));await s.session.flush();const [first]=await s.store.list();
  s.journal.clear('detail');s.journal.write('detail',value('next',true));await s.session.flush();const records=await s.store.list();
  assert.equal(records.length,2);assert.ok(records.some(r=>r.id===first.id&&!r.payload.operation));assert.ok(records.some(r=>r.payload.operation));
});
test('identical snapshots in separate tabs never share shelf ownership',async()=>{
  const shared=device(),a=setup({shared}),b=setup({shared});
  await a.session.enable();await b.session.enable();a.journal.write('detail',value('same'));await a.session.flush();b.journal.write('detail',value('same'));await b.session.flush();
  let records=await a.store.list();assert.equal(records.length,2);assert.notEqual(records[0].id,records[1].id);
  a.journal.write('detail',value('tab A'));await a.session.flush();records=await b.store.list();
  assert.ok(records.some(r=>r.payload.draft.notes==='same'));assert.ok(records.some(r=>r.payload.draft.notes==='tab A'));
});
test('restore refuses foreign Workspace and occupied local viewpoints; inspection changes nothing',async()=>{
  const s=setup();s.journal.write('detail',value('saved view'));await s.session.enable();const [r]=await s.store.list();s.journal.clear('detail');
  assert.throws(()=>s.session.restore(r,'2'.repeat(32)),/Workspace/i);assert.equal(s.journal.read('detail'),null);
  s.journal.write('detail',value('newer local'));assert.throws(()=>s.session.restore(r,W),/different|viewpoint|occupied/i);assert.equal(s.journal.read('detail').draft.notes,'newer local');
});
test('export/import restores body and object identity ordering into the existing journal',async()=>{
  const s=setup();s.journal.write('detail',value('newer',true));await s.session.enable();const [r]=await Core.decode(await s.store.export(),crypto);s.journal.clear('detail');const restored=s.session.restore(r,W);assert.equal(restored.operation.body,value('',true).operation.body);assert.equal(s.journal.read('detail').operation.command.notes,'snapshot');
});
test('shelf failure blocks dispatch without losing the visible local draft',async()=>{
  const s=setup();await s.session.enable();s.store.put=async()=>{throw Error('injected quota');};s.journal.write('detail',value('keep',true));let sent=0;await assert.rejects(s.journal.dispatch('detail',value('keep',true).operation,()=>sent++),/quota/);assert.equal(sent,0);assert.equal(s.journal.read('detail').draft.notes,'keep');
});
test('disable retains existing evidence and disconnects future dependent dispatch',async()=>{
  const s=setup();await s.session.enable();s.journal.write('detail',value('keep',true));await s.session.flush();await s.session.disable();s.journal.clear('detail');assert.equal((await s.store.list()).length,1);s.journal.write('detail',value('another'));await s.session.flush();assert.equal((await s.store.list()).length,1);
});
test('capacity failure cannot block explicit discard needed to free space',async()=>{
  const s=setup();await s.session.enable();s.journal.write('detail',value('first'));await s.session.flush();const [first]=await s.store.list();
  s.store.put=async()=>{throw Error('capacity');};s.journal.write('detail',value('later'));await assert.rejects(s.session.flush(),/capacity/);
  assert.equal(typeof s.session.discard,'function');await s.session.discard(first);assert.equal((await s.store.list()).length,0);
});
test('reload with an unresolved pending command recovers the same record without a duplicate identity',async()=>{
  const shared=device(),journalStorage=storage();
  const journal1=Journal.create(journalStorage),store1=Core.create({storage:shared.local,locks:shared.locks,crypto});
  const firstSession=Session.create({journal:journal1,store:store1,crypto,onStatus:()=>{}});
  await firstSession.enable();journal1.write('detail',value('snapshot',true));await firstSession.flush();
  const before=await store1.list();assert.equal(before.length,1);const first=before[0];
  assert.ok(first.payload.operation&&first.payload.operation.command.request_id==='0123456789abcdef');
  const journal2=Journal.create(journalStorage),store2=Core.create({storage:shared.local,locks:shared.locks,crypto});
  let sends=0;const secondSession=Session.create({journal:journal2,store:store2,crypto,onStatus:()=>{}});
  await secondSession.enable();assert.equal(sends,0,'recovery itself never posts');
  const after=await store2.list();
  assert.equal(after.length,1,'reload must not mint a second record');
  assert.equal(after[0].id,first.id);assert.equal(after[0].sha256,first.sha256);
  assert.equal(after[0].generation,first.generation);assert.equal(after[0].created_at,first.created_at);
  assert.equal(after[0].workspace_id,first.workspace_id);
  assert.equal(after[0].payload.operation.command.request_id,first.payload.operation.command.request_id);
  assert.equal(after[0].payload.operation.body,first.payload.operation.body);
  await journal2.dispatch('detail',value('snapshot',true).operation,()=>{sends++;return Promise.resolve({});});
  assert.equal(sends,1,'retry still dispatches once after recovery');
  journal2.write('detail',value('newer',true));await secondSession.flush();
  const updated=await store2.list();
  assert.equal(updated.length,1);assert.equal(updated[0].id,first.id);
  assert.equal(updated[0].payload.operation.body,first.payload.operation.body);
  assert.equal(updated[0].payload.draft.notes,'newer');
});
test('cloned tabs with identical pending converge; later conflicting writes stay CAS-protected',async()=>{
  const shared=device(),a=setup({shared}),b=setup({shared});
  await a.session.enable();await b.session.enable();
  a.journal.write('detail',value('same',true));await a.session.flush();
  const [first]=await a.store.list();
  b.journal.write('detail',value('same',true));await b.session.flush();
  let records=await a.store.list();
  assert.equal(records.length,1,'identical immutable pending must not mint a duplicate identity');
  assert.equal(records[0].id,first.id);assert.equal(records[0].sha256,first.sha256);
  a.journal.write('detail',value('tab A',true));await a.session.flush();
  records=await a.store.list();assert.equal(records.length,1);assert.equal(records[0].payload.draft.notes,'tab A');
  const winner=records[0];
  b.journal.write('detail',value('tab B',true));
  await assert.rejects(b.session.flush(),/changed|conflict|inspect|viewpoint/i);
  records=await b.store.list();
  assert.equal(records.length,1);assert.equal(records[0].sha256,winner.sha256,'loser must not silently overwrite the winner');
  assert.equal(records[0].payload.draft.notes,'tab A');
  assert.equal(b.journal.read('detail').draft.notes,'tab B','losing viewpoint is retained locally');
});
test('same request identity with different pending bytes fails closed without overwrite or POST',async()=>{
  const shared=device(),a=setup({shared}),b=setup({shared});
  await a.session.enable();await b.session.enable();
  a.journal.write('detail',value('snapshot',true));await a.session.flush();
  const [first]=await a.store.list();
  const evil=value('snapshot',true);evil.operation.command.notes='changed';evil.operation.body=JSON.stringify(evil.operation.command);
  b.journal.write('detail',evil);let sends=0;
  await assert.rejects(b.session.flush(),/differs|duplicate|inspect|pending|viewpoint/i);
  const records=await b.store.list();
  assert.equal(records.length,1);assert.equal(records[0].sha256,first.sha256);
  assert.equal(records[0].payload.operation.body,first.payload.operation.body);
  assert.equal(b.journal.read('detail').operation.body,evil.operation.body,'conflicting local evidence is retained');
  assert.equal(sends,0,'conflict path never posts');
  await assert.rejects(b.journal.dispatch('detail',evil.operation,()=>{sends++;return Promise.resolve({});}),/differs|retained|inspect|changed/i);
  assert.equal(sends,0);
});
test('restore proceeds for a current record after a stale checkpoint error in another slot',async()=>{
  const s=setup();await s.session.enable();
  s.journal.write('detail',value('saved view'));await s.session.flush();
  const [record]=await s.store.list();
  const okPut=s.store.put.bind(s.store);
  s.store.put=async(rec,exp)=>{if(rec.slot==='library')throw Error('injected library quota');return okPut(rec,exp);};
  s.journal.write('library',libraryValue());await assert.rejects(s.session.flush(),/quota/);
  await assert.rejects(s.session.flush(),/quota/,'stale error remains without new work');
  s.journal.clear('detail');let sends=0;
  const restored=s.session.restore(record,W);
  assert.equal(restored.draft.notes,'saved view');assert.equal(s.journal.read('detail').draft.notes,'saved view');
  assert.equal(sends,0,'restore is a local journal operation and never posts');
  const records=await s.store.list();
  assert.ok(records.some(r=>r.id===record.id&&r.sha256===record.sha256),'selected record still current and unchanged');
});
