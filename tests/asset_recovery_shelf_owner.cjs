'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const Shelf=require('../app/static/asset-recovery-shelf.js'),crypto=require('node:crypto').webcrypto;
const copy=value=>value===null?null:JSON.parse(JSON.stringify(value));
const digest=async raw=>raw===null?null:Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))).toString('hex');
function fixture(initial=null,legacy=null){
  let state=copy(initial),old=legacy,tail=Promise.resolve();const writes=[];
  const backend={async read(){return state===null?[]:[copy(state)];},async compareAndSwap(expected,next){
    if(this.fail)throw Error(this.fail);assert.deepEqual(state===null?[]:[state],expected,'test owner refuses a changed complete entry');
    if(this.beforeCommit)await this.beforeCommit();
    assert.deepEqual(state===null?[]:[state],expected,'test owner rechecks after a held commit');state=copy(next);writes.push(copy(next));
  }};
  const storage={getItem:()=>old,setItem(){throw Error('legacy bytes must never be written');}};
  const locks={request(_name,_options,action){const p=tail.then(action);tail=p.catch(()=>{});return p;}};
  const options={storage,locks,crypto,backend};
  return {store:Shelf.create(options),options,backend,writes,state:()=>copy(state),replace:value=>{state=copy(value);},legacy:()=>old,replaceLegacy:raw=>{old=raw;}};
}
async function record(note='initial',id='a'.repeat(32),generation=1){
  const workspace_id='1'.repeat(32),form={title:'Synthetic owner',tags:'',review:'unreviewed',notes:note};
  const metadata={id:'asset-a',workspace_id,metadata_revision:0,title:form.title,notes:'baseline',tags:[],review:'unreviewed',favorite:false,trashed_at:null};
  return Shelf.seal('detail',{version:2,workspace_id,id:'asset-a',metadata,baseline:{...form,notes:'baseline'},draft:form,operation:null,conflict:null},
    {id,created_at:1,updated_at:generation,generation},crypto);
}
const state=async records=>({version:1,raw:await Shelf.encode(records,crypto),legacy_digest:null});

test('browser storage without a transactional owner fails closed instead of falling back to localStorage',async()=>{
  let writes=0;const store=Shelf.create({storage:{getItem:()=>null,setItem(){writes++;}},locks:{request:async(_n,_o,fn)=>fn()},crypto});
  await assert.rejects(store.put(await record(),null),/IndexedDB|transactional|unavailable/i);assert.equal(writes,0);
});
test('legacy inspection is read-only and first mutation migrates through the atomic owner without changing old bytes',async()=>{
  const original=await record(),raw=await Shelf.encode([original],crypto),f=fixture(null,raw);
  assert.deepEqual(await f.store.list(),[original]);assert.equal(f.state(),null);assert.equal(f.writes.length,0);
  const newer=await record('newer',original.id,2);await f.store.put(newer,original.sha256);
  assert.equal(f.legacy(),raw);assert.equal(f.state().legacy_digest,await digest(raw));assert.equal(f.writes.length,1);
  assert.deepEqual(await f.store.list(),[newer]);assert.equal(await f.store.raw(),f.state().raw);assert.equal(await f.store.legacyRaw(),raw);
});
test('initialization refuses a legacy value that changes after the inspected bytes were captured',async()=>{
  const original=await record(),raw=await Shelf.encode([original],crypto),replacement=await Shelf.encode([await record('new older')],crypto),f=fixture(null,raw);let reads=0;
  f.options.storage.getItem=()=>++reads===1?raw:replacement;
  await assert.rejects(f.store.put(await record('new current',original.id,2),original.sha256),/changed|refresh/i);
  assert.equal(f.state(),null);assert.equal(f.writes.length,0);
});
test('empty initialized shelf stays authoritative and never resurrects preserved legacy records',async()=>{
  const original=await record(),raw=await Shelf.encode([original],crypto),f=fixture(null,raw);
  await f.store.remove(original.id,original.sha256);assert.deepEqual(await f.store.list(),[]);
  assert.ok(f.state());assert.equal(f.state().raw,await Shelf.encode([],crypto));assert.equal(f.legacy(),raw);
  assert.deepEqual(await Shelf.create(f.options).list(),[]);
});
test('legacy divergence quarantines mutations while both exact raw exports remain available',async()=>{
  const initial=await state([await record()]),f=fixture(initial),older=await Shelf.encode([await record('older-tab')],crypto);f.replaceLegacy(older);
  let failure;try{await f.store.list();}catch(error){failure=error;}
  assert.equal(failure?.code,'asset_recovery_legacy_changed');assert.ok(failure.review);
  assert.equal(await f.store.raw(),initial.raw);assert.equal(await f.store.legacyRaw(),older);
  await assert.rejects(f.store.put(await record('attempt','b'.repeat(32)),null),error=>error.code==='asset_recovery_legacy_changed');
  assert.deepEqual(f.state(),initial);assert.equal(f.writes.length,0);assert.equal(f.legacy(),older);
});
test('explicit acknowledgement changes only compatibility metadata and a later old-tab write quarantines again',async()=>{
  const initial=await state([await record()]),f=fixture(initial),old=await Shelf.encode([await record('older')],crypto);f.replaceLegacy(old);
  let token;try{await f.store.list();}catch(error){token=error.review;}
  await f.store.acceptLegacy(token);assert.equal(f.state().raw,initial.raw);assert.equal(f.legacy(),old);assert.equal(f.state().legacy_digest,await digest(old));
  assert.equal((await f.store.list())[0].payload.draft.notes,'initial');
  f.replaceLegacy(await Shelf.encode([await record('new older write')],crypto));
  await assert.rejects(f.store.list(),error=>error.code==='asset_recovery_legacy_changed');
});
for(const replacement of ['current','legacy','foreign-token'])test('acknowledgement refuses an uninspected '+replacement+' replacement',async()=>{
  const initial=await state([await record()]),f=fixture(initial);f.replaceLegacy(await Shelf.encode([await record('older')],crypto));
  let token;try{await f.store.list();}catch(error){token=error.review;}
  if(replacement==='current')f.replace(await state([await record('new current')]));
  if(replacement==='legacy')f.replaceLegacy(await Shelf.encode([await record('new older')],crypto));
  if(replacement==='foreign-token')token={};
  const before=f.state(),old=f.legacy();await assert.rejects(f.store.acceptLegacy(token),/changed|refresh|review/i);
  assert.deepEqual(f.state(),before);assert.equal(f.legacy(),old);assert.equal(f.writes.length,0);
});
for(const kind of ['future','extra','corrupt-bundle'])test(kind+' owner state refuses use while preserving bounded raw export',async()=>{
  const initial=await state([await record()]);if(kind==='future')initial.version=99;if(kind==='extra')initial.extra=true;if(kind==='corrupt-bundle')initial.raw='{invalid';
  const f=fixture(initial);await assert.rejects(f.store.list(),/version|state|fields|JSON|invalid/i);
  assert.deepEqual(f.state(),initial);assert.equal(await f.store.raw(),initial.raw);assert.equal(f.writes.length,0);
});
test('corrupt current bytes cannot issue a usable legacy acknowledgement token',async()=>{
  const initial={version:1,raw:'{invalid',legacy_digest:null},f=fixture(initial,await Shelf.encode([await record('older')],crypto));let failure;
  try{await f.store.list();}catch(error){failure=error;}
  assert.ok(failure);assert.notEqual(failure.code,'asset_recovery_legacy_changed');assert.equal(failure.review,undefined);
  assert.equal(await f.store.raw(),initial.raw);assert.deepEqual(f.state(),initial);assert.equal(f.writes.length,0);
});
for(const value of [null,undefined])test('a present '+String(value)+' owner entry is corrupt evidence, not absence',async()=>{
  const f=fixture();f.backend.read=async()=>[value];
  await assert.rejects(f.store.list(),/owner state|version|fields/i);await assert.rejects(f.store.importRecords([]),/owner state|version|fields/i);
  assert.equal(await f.store.raw(),String(value));assert.equal(f.writes.length,0);
});
for(const initializing of [true,false])test((initializing?'initialization':'replacement')+' owner failure leaves both evidence copies intact',async()=>{
  const r=await record(),raw=await Shelf.encode([r],crypto),initial=initializing?null:await state([r]),f=fixture(initial,initializing?raw:null);
  f.backend.fail='Synthetic transaction aborted or quota refused';const next=await record('new',r.id,2);
  await assert.rejects(f.store.put(next,r.sha256),/abort|quota/i);assert.deepEqual(f.state(),initial);assert.equal(f.legacy(),initializing?raw:null);assert.equal(f.writes.length,0);
});
test('a successful put waits for the atomic owner completion',async()=>{
  const f=fixture(),r=await record();let release,entered;const started=new Promise(resolve=>{entered=resolve;});
  f.backend.beforeCommit=()=>{entered();return new Promise(resolve=>{release=resolve;});};
  let settled=false;const pending=f.store.put(r,null).then(()=>{settled=true;});await started;await Promise.resolve();
  assert.equal(settled,false);assert.equal(f.state(),null);release();await pending;assert.equal(settled,true);assert.equal((await f.store.list())[0].sha256,r.sha256);
});
