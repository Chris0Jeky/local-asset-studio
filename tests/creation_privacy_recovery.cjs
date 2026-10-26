'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto').webcrypto;
const Shelf=require('../app/static/asset-recovery-shelf.js'),Recovery=require('../app/static/asset-recovery.js'),Session=require('../app/static/asset-recovery-shelf-session.js');
const W='1'.repeat(32);
function storage(){const data=new Map();return {data,get length(){return data.size;},key:i=>[...data.keys()][i]??null,getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)};}
function draft(text){const form={title:'Synthetic review',tags:'',review:'unreviewed',notes:text};return {version:2,workspace_id:W,id:'asset-one',metadata:{id:'asset-one',workspace_id:W,metadata_revision:0,title:form.title,notes:'',tags:[],review:'unreviewed',favorite:false,trashed_at:null},baseline:{...form,notes:''},draft:form,operation:null,conflict:null};}
test('per-tab journals isolate regular, private and all without rewriting retained bytes',()=>{
  const raw=storage(),regular=Recovery.create(Recovery.scopedStorage(raw,'regular')),privateJournal=Recovery.create(Recovery.scopedStorage(raw,'private')),all=Recovery.create(Recovery.scopedStorage(raw,'all'));
  regular.write('detail',draft('ordinary wording'));privateJournal.write('detail',draft('private canary'));all.write('detail',draft('mixed canary'));
  assert.equal(regular.read('detail').draft.notes,'ordinary wording');assert.equal(privateJournal.read('detail').draft.notes,'private canary');assert.equal(all.read('detail').draft.notes,'mixed canary');
  assert.doesNotMatch(raw.getItem(Recovery.PREFIX+'detail'),/canary/);
  assert.equal(Recovery.scopedStorage(raw,'regular').length,1);
  assert.equal(Recovery.create(Recovery.scopedStorage(raw,'private')).read('detail').draft.notes,'private canary');
});
test('private checkpoints use only session storage and survive same-tab reload',async()=>{
  const raw=storage(),journal=Recovery.create(Recovery.scopedStorage(raw,'private'));
  const store=Shelf.createTab({storage:raw,privacy:'private',crypto}),session=Session.create({journal,store,privacy:'private',crypto});
  await session.enable();journal.write('detail',draft('private canary'));await session.flush();
  const records=await store.list();assert.equal(records.length,1);assert.equal(records[0].privacy,'private');
  assert.equal((await Shelf.createTab({storage:raw,privacy:'private',crypto}).list())[0].payload.draft.notes,'private canary');
  assert.equal((await Shelf.createTab({storage:raw,privacy:'all',crypto}).list()).length,0);
  const secondTab=Shelf.createTab({storage:storage(),privacy:'private',crypto});assert.deepEqual(await secondTab.list(),[]);
  assert.ok([...raw.data.keys()].every(key=>key.includes('private')));
});
test('private and mixed exports cannot be imported or restored into regular recovery',async()=>{
  for(const privacy of ['private','all']){
    const raw=storage(),journal=Recovery.create(Recovery.scopedStorage(raw,privacy)),store=Shelf.createTab({storage:raw,privacy,crypto});
    const session=Session.create({journal,store,privacy,crypto});await session.enable();journal.write('detail',draft(privacy+' canary'));await session.flush();
    const [record]=await Shelf.decode(await store.export(),crypto);assert.equal(record.privacy,privacy);
    const regular=Shelf.create({crypto,backend:{read:async()=>[],compareAndSwap:async()=>{throw Error('must not write');}},storage:{getItem:()=>null},locks:{request:(name,options,work)=>work()}});
    await assert.rejects(regular.importRecords([record]),/privacy/i);
    const regularJournal=Recovery.create(raw),regularSession=Session.create({journal:regularJournal,store:regular,crypto});
    assert.throws(()=>regularSession.restore(record,W),/privacy/i);assert.equal(regularJournal.read('detail'),null);
  }
});
test('session shelf compare-and-swap rejects stale ownership and preserves exact bytes',async()=>{
  const raw=storage(),a=Shelf.createTab({storage:raw,privacy:'private',crypto}),b=Shelf.createTab({storage:raw,privacy:'private',crypto});
  const record=await Shelf.seal('detail',draft('first'),{id:'a'.repeat(32),generation:1,created_at:1,updated_at:1,privacy:'private'},crypto);
  await a.put(record);const newer=await Shelf.seal('detail',draft('newer'),{id:record.id,generation:2,created_at:1,updated_at:2,privacy:'private'},crypto);
  await b.put(newer,record.sha256);await assert.rejects(a.put(record,record.sha256),/changed/i);
  assert.equal((await a.list())[0].payload.draft.notes,'newer');
});
test('collection journals keep private wording out of regular recovery enumeration',()=>{
  const Collection=require('../app/static/collection-recovery.js'),raw=storage();
  const regular=new Collection.Journal(raw,W),privateJournal=new Collection.Journal(raw,W,'private');
  const values=name=>({id:null,revision:null,baseline:{name:'',description:''},values:{name,description:'Synthetic text'},updated_at:1});
  regular.keep(values('Ordinary collection'));privateJournal.keep(values('Private canary'));
  assert.equal(regular.list()[0].draft.values.name,'Ordinary collection');assert.equal(privateJournal.list()[0].draft.values.name,'Private canary');
  assert.doesNotMatch(raw.getItem(regular.key),/canary/);
});
test('lifecycle observations freeze explicit privacy and retire after a scope switch',async()=>{
  const Lifecycle=require('../app/static/asset-recovery-lifecycle.js');let view='private';const requests=[],updates=[];
  const observer=Lifecycle.create({scope:()=>W,privacy:()=>view,validateReceipt(){},onUpdate:value=>updates.push(value),read:(url,options)=>new Promise(resolve=>requests.push({url,options,resolve}))});
  const pending=observer.load({slot:'detail',privacy:'private',payload:draft('Private canary')});
  assert.equal(requests.length,1);assert.equal(requests[0].options.headers['X-Studio-Privacy'],'private');
  view='regular';requests[0].resolve({});await pending;
  assert.deepEqual(updates.map(value=>value.phase),['loading']);
  await assert.rejects(observer.load({slot:'detail',privacy:'private',payload:draft('Private canary')}),/privacy/);
  assert.equal(requests.length,1);
});
