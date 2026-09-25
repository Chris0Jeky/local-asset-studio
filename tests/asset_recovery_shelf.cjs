'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const path=require('node:path').join(__dirname,'../app/static/asset-recovery-shelf.js');
const S=fs.existsSync(path)?require(path):{};
const crypto=require('node:crypto').webcrypto,W='1'.repeat(32);
function envelope(note='draft',pending=false){
  const form={title:'Synthetic review',tags:'tag',review:'unreviewed',notes:note};
  const metadata={id:'asset-a',workspace_id:W,metadata_revision:0,title:form.title,notes:'baseline',tags:['tag'],review:'unreviewed',favorite:false,trashed_at:null};
  const command={ids:['asset-a'],action:'edit',notes:'submitted',workspace_id:W,expected_revisions:{'asset-a':0},request_id:'request_1234567890'};
  return {version:2,workspace_id:W,id:'asset-a',metadata,baseline:{...form,notes:'baseline'},draft:form,operation:pending?{command,body:JSON.stringify(command),kind:'details',snapshot:{...form,notes:'submitted'}}:null,conflict:null};
}
function memory(){let raw=null,tail=Promise.resolve();const m={storage:{getItem(){return raw;},setItem(k,v){raw=v;}},locks:{request(name,opts,fn){const p=tail.then(fn);tail=p.catch(()=>{});return p;}},crypto,raw:()=>raw,replace:v=>raw=v};return m;}
let serial=0;
async function record(value=envelope(),options={}){assert.equal(typeof S.seal,'function','shelf codec must exist');return S.seal('detail',value,{id:(++serial).toString(16).padStart(32,'0'),created_at:100,updated_at:100,generation:1,...options},crypto);}
test('shelf codec exists and preserves exact submitted bytes separately from newer typing',async()=>{
  const e=envelope('newer typing',true);e.operation.body=JSON.stringify(e.operation.command,null,2);
  const r=await record(e),text=await S.encode([r],crypto),decoded=await S.decode(text,crypto);
  assert.equal(decoded[0].payload.operation.body,e.operation.body);assert.equal(decoded[0].payload.draft.notes,'newer typing');
  assert.equal(decoded[0].payload.operation.command.notes,'submitted');
});
test('metadata projection omits media/path details without altering user text',async()=>{
  const e=envelope('<script>literal review text</script>');e.metadata.path='/private/owner/picture.png';e.metadata.source={private:'data'};
  e.conflict={code:'asset_revision_conflict',workspace_id:W,current:[{...e.metadata}]};
  const r=await record(e);assert.equal(r.payload.metadata.path,undefined);assert.equal(r.payload.conflict.current[0].source,undefined);assert.equal(r.payload.draft.notes,e.draft.notes);
});
test('strict parser rejects duplicate escaped keys, future versions and corrupt hashes',async()=>{
  const r=await record(),raw=await S.encode([r],crypto);
  await assert.rejects(S.decode(raw.replace('"version":1','"version":1,"\\u0076ersion":1'),crypto),/duplicate/i);
  await assert.rejects(S.decode(raw.replace('"version":1','"version":99'),crypto),/version/i);
  await assert.rejects(S.decode(raw.replace('"notes":"draft"','"notes":"altered"'),crypto),/digest/i);
  for(const text of ['{"a":NaN}','{"a":1e999}','{"x":'+ '['.repeat(18)+'0'+']'.repeat(18)+'}'])assert.throws(()=>S.parse(text),/JSON|finite|depth/i);
});
test('record/aggregate byte, field, target and key bounds refuse without truncation',async()=>{
  await assert.rejects(record(envelope('x'.repeat(65537))),/limit|large|bound/i);
  assert.throws(()=>S.parse(' '.repeat(S.LIMITS.total+1)),/large|limit|bound/i);
  assert.throws(()=>S.parse('{'+Array.from({length:20001},(_,i)=>`"k${i}":0`).join(',')+'}'),/keys|bound/i);
  const e=envelope();e.metadata.id=e.id='a'.repeat(129);await assert.rejects(record(e),/identity|ID|bound/i);
});
test('locked writes survive fresh store instances and stale writers preserve both viewpoints',async()=>{
  const m=memory(),store=S.create(m),r=await record();await store.put(r,null);
  assert.deepEqual(await S.create(m).list(),[r]);
  const newer=await record(envelope('newer'),{id:r.id,generation:2,created_at:r.created_at,updated_at:101});
  await store.put(newer,r.sha256);
  await assert.rejects(store.put(await record(envelope('stale'),{id:r.id,generation:2,created_at:r.created_at,updated_at:101}),r.sha256),/changed|conflict/i);
  assert.equal((await store.list())[0].payload.draft.notes,'newer');
});
test('unresolved command cannot be changed or removed by an update',async()=>{
  const m=memory(),store=S.create(m),r=await record(envelope('draft',true));await store.put(r,null);
  const cleared=await record(envelope('next'),{id:r.id,generation:2,created_at:100,updated_at:101});
  await assert.rejects(store.put(cleared,r.sha256),/pending|immutable/i);
  const e=envelope('newer',true);e.operation.command.notes='changed';e.operation.body=JSON.stringify(e.operation.command);
  await assert.rejects(store.put(await record(e,{id:r.id,generation:2,created_at:100,updated_at:101}),r.sha256),/pending|immutable/i);
  assert.deepEqual(await store.list(),[r]);
});
test('storage refusal or changed readback reports failure; unavailable locks never write',async()=>{
  const r=await record(),m=memory();let writes=0;
  await assert.rejects(S.create({...m,locks:null}).put(r,null),/lock|unavailable/i);assert.equal(m.raw(),null);
  await assert.rejects(S.create({...m,storage:{getItem:()=>null,setItem(){writes++;throw Error('quota');}}}).put(r,null),/quota|storage|retain/i);assert.equal(writes,1);
  await assert.rejects(S.create({...m,storage:{getItem:()=>null,setItem(){}}}).put(r,null),/readback|verify|retain/i);
});
test('capacity and duplicate request pressure never evict existing records',async()=>{
  const m=memory(),store=S.create(m),first=await record(envelope('pending',true));await store.put(first,null);
  await assert.rejects(store.put(await record(envelope('another view',true)),null),/duplicate|request/i);
  for(let i=1;i<S.LIMITS.records;i++)await store.put(await record(),null);
  const before=m.raw();await assert.rejects(store.put(await record(),null),/capacity|limit|full/i);assert.equal(m.raw(),before);
  assert.equal((await store.list())[0].payload.operation.command.request_id,'request_1234567890');
});
test('import is inspected before persistence; malformed/duplicate batches are all-or-nothing',async()=>{
  const m=memory(),store=S.create(m),a=await record(),b=await record();const text=await S.encode([a,b],crypto);
  const inspected=await S.decode(text,crypto);assert.equal(m.raw(),null);await store.importRecords(inspected);assert.equal((await store.list()).length,2);
  const before=m.raw();await assert.rejects(store.importRecords([await record(),a]),/duplicate|exists/i);assert.equal(m.raw(),before);
  await assert.rejects(S.encode([a,a],crypto),/duplicate/i);
});
test('explicit digest-guarded discard clears only its chosen local record',async()=>{
  const m=memory(),store=S.create(m),a=await record(envelope('pending',true)),b=await record();await store.importRecords([a,b]);
  await assert.rejects(store.remove(a.id,'0'.repeat(64)),/changed|conflict/i);await store.remove(a.id,a.sha256);assert.deepEqual(await store.list(),[b]);
});
test('concurrent tab capacity checks serialize under the shared origin lock',async()=>{
  const m=memory(),a=S.create(m),b=S.create(m);for(let i=0;i<S.LIMITS.records-1;i++)await a.put(await record(),null);
  const r1=await record(),r2=await record();const results=await Promise.allSettled([a.put(r1,null),b.put(r2,null)]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal((await a.list()).length,S.LIMITS.records);
});
test('a library source mark (#939) seals with a run label or null, and an oversized label is refused',async()=>{
  const seal=(run_label,n)=>{const command={ids:['asset-a','asset-b'],action:'edit',run_label,workspace_id:W,expected_revisions:{'asset-a':0,'asset-b':3},request_id:'request_1234567890'};
    return S.seal('library',{version:2,workspace_id:W,operation:{command,body:JSON.stringify(command)},selection:['asset-a','asset-b']},{id:n.repeat(32),generation:1,created_at:1,updated_at:1},crypto);};
  for(const [label,n] of [['Agent lab','a'],[null,'b'],['界'.repeat(80),'c']]){
    const [decoded]=await S.decode(await S.encode([await seal(label,n)],crypto),crypto);
    assert.equal(decoded.payload.operation.command.run_label,label);
  }
  for(const [label,n] of [['x'.repeat(81),'d'],['','e'],[7,'f']])await assert.rejects(seal(label,n),/library|bound|invalid/i);
});
module.exports={envelope,memory};
test('non-ASCII fields are bounded by UTF-8 bytes, and imported library extras are refused',async()=>{
  await assert.rejects(record(envelope('😀'.repeat(17000))),/bound|limit/i);
  const e=envelope('x',true),payload={version:2,workspace_id:W,operation:{command:e.operation.command,body:e.operation.body},selection:['asset-a']};
  const r=await S.seal('library',payload,{id:'e'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);
  r.payload.operation.snapshot={private_path:'/not-an-admitted-field'};
  const {sha256,...content}=r;r.sha256=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(S.canonical(content)))).toString('hex');
  await assert.rejects(S.encode([r],crypto),/library|field/i);
});
test('a held lock times out without writing or silently falling back to unlocked storage',async()=>{
  const m=memory(),r=await record(),locks={request(n,o){return new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>reject(Error('lock wait aborted')),{once:true}));}};
  await assert.rejects(S.create({...m,locks,lockTimeoutMs:10}).put(r,null),/abort|lock/i);assert.equal(m.raw(),null);
});
test('server-valid Unicode titles keep code-point limits separate from UTF-8 storage budgets',async()=>{
  for(const title of ['界'.repeat(200),'😀'.repeat(200)]){
    const e=envelope('draft',true);
    for(const v of [e.metadata,e.baseline,e.draft,e.operation.snapshot,e.operation.command])v.title=title;
    e.operation.body=JSON.stringify(e.operation.command,null,2);
    const r=await record(e),[decoded]=await S.decode(await S.encode([r],crypto),crypto);
    assert.equal(decoded.payload.metadata.title,title);assert.equal(decoded.payload.operation.body,e.operation.body);
  }
  const e=envelope();e.draft.title='😀'.repeat(201);await assert.rejects(record(e),/bound|limit|invalid/i);
});
