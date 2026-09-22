'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const {PREFIX}=require('../app/static/asset-recovery.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const journal=(s,slot='detail')=>s.storage.getItem(PREFIX+slot);
const begin=s=>{s.el('#assetNotes').value='sent snapshot';return s.el('#saveAssetDetails').onclick();};
const swap=s=>s.run("assetState={...assetState,workspace_id:'2'.repeat(32),assets:assetState.assets.map(a=>({...a,workspace_id:'2'.repeat(32),notes:'foreign saved'}))}");
const conflict=(s,index=0)=>Object.assign(Error('Changed'),{status:409,data:{code:'asset_revision_conflict',workspace_id:'1'.repeat(32),request_id:s.payload(index).request_id,current:s.receipt(index).current}});
for(const outcome of ['success','conflict','failure'])test('detail '+outcome+' from a previous Workspace cannot change recovery or the active editor',async()=>{
  const s=setup(),p=begin(s),receipt=s.receipt(0),bytes=journal(s);swap(s);
  if(outcome==='success')s.writes[0].resolve(receipt);else s.writes[0].reject(outcome==='conflict'?conflict(s):Error('delayed transport failure'));
  await p;
  assert.equal(s.run('activeAsset.notes'),'original');assert.equal(s.run('assetDetailConflict'),null);
  assert.equal(journal(s),bytes);assert.equal(s.run('!!assetDetailPending'),true);assert.equal(s.el('#assetNotes').value,'sent snapshot');
  assert.equal(s.run('assetState.assets[0].notes'),'foreign saved');
});
for(const outcome of ['success','failure'])test('old detail finally cannot unlock a replacement request after '+outcome,async()=>{
  const s=setup(),old=begin(s),receipt=s.receipt(0);
  s.run('assetDetailEpoch++;assetDetailBusy=false;assetDetailPending=null');s.el('#assetNotes').value='replacement';
  const current=s.el('#saveAssetDetails').onclick(),body=s.writes[1].options.body;
  if(outcome==='success')s.writes[0].resolve(receipt);else s.writes[0].reject(Error('old failure'));await old;
  try {assert.equal(s.run('assetDetailBusy'),true);assert.equal(s.el('#saveAssetDetails').disabled,true);assert.equal(s.run('assetDetailPending.body'),body);assert.equal(s.el('#assetNotes').value,'replacement');}
  finally{s.accept(1);await current;}
});
test('replacing a pending detail identity without changing the asset ID rejects its late receipt',async()=>{
  const s=setup(),p=begin(s),receipt=s.receipt(0);
  s.run("assetDetailPending={...assetDetailPending,command:{...assetDetailPending.command,request_id:'replacement_request_1'}}");
  const bytes=journal(s);s.writes[0].resolve(receipt);await p;
  assert.equal(s.run('activeAsset.notes'),'original');assert.equal(journal(s),bytes);assert.equal(s.run('assetDetailPending.command.request_id'),'replacement_request_1');
});
for(const outcome of ['success','conflict','failure'])test('library '+outcome+' from a previous Workspace cannot clear recovery or update same-ID foreign rows',async()=>{
  const s=setup({autoOpen:false});s.run("assetSelection=new Set(['a','b'])");const p=s.run("mutateAssets({ids:['a','b'],action:'edit',notes:'sent'})"),receipt=s.receipt(0),bytes=journal(s,'library');
  const settled=p.catch(()=>{});swap(s);
  if(outcome==='success')s.writes[0].resolve(receipt);else s.writes[0].reject(outcome==='conflict'?conflict(s):Error('old transport failure'));await settled;
  assert.equal(journal(s,'library'),bytes);assert.equal(s.run('!!assetLibraryPending'),true);
  assert.equal(s.run('assetState.assets[0].metadata_revision'),0);assert.equal(s.run('assetState.assets[0].notes'),'foreign saved');
});
for(const outcome of ['success','conflict','failure'])test('old library '+outcome+' cannot acknowledge or unlock a replacement command',async()=>{
  const s=setup({autoOpen:false}),old=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})").catch(()=>{}),receipt=s.receipt(0),err=conflict(s);
  s.run('assetLibraryPending=null;assetLibraryBusy=false');
  const current=s.run("mutateAssets({ids:['b'],action:'edit',notes:'replacement'})"),bytes=journal(s,'library'),body=s.writes[1].options.body;
  if(outcome==='success')s.writes[0].resolve(receipt);else s.writes[0].reject(outcome==='conflict'?err:Error('old transport failure'));await old;
  try{assert.equal(s.run('assetLibraryBusy'),true);assert.equal(s.run('assetLibraryPending.body'),body);assert.equal(journal(s,'library'),bytes);assert.equal(s.run('assetState.assets[0].metadata_revision'),0);}
  finally{s.accept(1);await current;}
});
for(const slot of ['detail','library'])test('retired '+slot+' operation cannot be invoked through a stale callback',async()=>{
  const s=setup({autoOpen:slot==='detail'});
  const p=slot==='detail'?begin(s):s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})").catch(()=>{});
  s.run('globalThis.retired='+(slot==='detail'?'assetDetailPending':'assetLibraryPending'));s.accept(0);await p;
  const retry=s.run(slot==='detail'?'performAssetSave(retired)':'performLibraryCommand(retired)').catch(()=>{});await tick();
  const sent=s.writes.length;if(sent>1)s.accept(1);await retry;assert.equal(sent,1);
});
for(const slot of ['detail','library'])test(slot+' receipt stays stale after an observed Workspace A to B to A cycle',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=slot==='detail'?begin(s):s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})").catch(()=>{}),receipt=s.receipt(0),bytes=journal(s,slot);
  const state=JSON.parse(s.run('JSON.stringify(assetState)'));
  for(const workspace_id of ['2'.repeat(32),'1'.repeat(32)]){
    const refresh=s.actualRefresh(true);s.reads.at(-1).resolve({...state,workspace_id,assets:state.assets.map(a=>({...a,workspace_id}))});await refresh;
  }
  s.writes[0].resolve(receipt);await p;
  assert.equal(journal(s,slot),bytes);assert.equal(s.run('!!'+(slot==='detail'?'assetDetailPending':'assetLibraryPending')),true);assert.equal(s.run('assetState.assets[0].metadata_revision'),0);
});
test('same-Workspace refresh does not cancel a valid current request',async()=>{
  const s=setup(),p=begin(s),receipt=s.receipt(0),state=JSON.parse(s.run('JSON.stringify(assetState)'));
  const refresh=s.actualRefresh(true);s.reads.at(-1).resolve(state);await refresh;s.writes[0].resolve(receipt);await p;
  assert.equal(s.run('activeAsset.notes'),'sent snapshot');assert.equal(journal(s),null);assert.equal(s.run('assetDetailBusy'),false);
});
for(const slot of ['detail','library'])test(slot+' callback stays stale across Workspace observations rendered by a different loader',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=slot==='detail'?begin(s):s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})").catch(()=>{}),receipt=s.receipt(0),bytes=journal(s,slot);
  const state=s.run('JSON.stringify(assetState)');
  swap(s);s.run('renderAssets()');s.run('assetState='+state+';renderAssets()');
  s.writes[0].resolve(receipt);await p;
  assert.equal(journal(s,slot),bytes);assert.equal(s.run('!!'+(slot==='detail'?'assetDetailPending':'assetLibraryPending')),true);assert.equal(s.run('assetState.assets[0].metadata_revision'),0);
});
