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
