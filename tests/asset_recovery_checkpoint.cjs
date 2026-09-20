'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function hold(s){s.run(`assetRecovery.connect({changed(){},prepare:()=>new Promise((resolve,reject)=>{globalThis.finishCheckpoint=resolve;globalThis.failCheckpoint=reject;})});`);}
test('detail POST waits for the durable checkpoint and sends the old snapshot, not newer typing',async()=>{
  const s=setup();hold(s);s.el('#assetNotes').value='submitted';const pending=s.el('#saveAssetDetails').onclick();await tick();assert.equal(s.writes.length,0);
  s.el('#assetNotes').value='newer typing';s.run('finishCheckpoint()');await tick();assert.equal(s.writes.length,1);assert.equal(s.payload(0).notes,'submitted');s.accept(0);await pending;assert.equal(s.el('#assetNotes').value,'newer typing');
});
test('failed checkpoint retains draft and exact pending identity, with zero POSTs',async()=>{
  const s=setup();hold(s);s.el('#assetNotes').value='keep';const pending=s.el('#saveAssetDetails').onclick();await tick();s.run('failCheckpoint(Error("shelf quota"))');await pending;
  assert.equal(s.writes.length,0);assert.equal(s.el('#assetNotes').value,'keep');assert.match(s.el('#assetDetailStatus').textContent,/quota/);assert.equal(s.run('!!assetDetailPending'),true);
});
test('receipt inspection never depends on the optional persistent checkpoint',async()=>{
  const s=setup();s.el('#assetNotes').value='keep';const pending=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await pending;
  hold(s);const check=s.run('checkAssetSave()');await tick();assert.equal(s.reads.length,1);const c=s.payload(0);s.reads[0].resolve({workspace_id:c.workspace_id,request_id:c.request_id,status:'unknown'});await check;assert.equal(s.writes.length,1);
});
for(const change of ["assetDetailEpoch++","assetState.workspace_id='2'.repeat(32)","assetDetailPending=null"])
  test('context replacement during checkpoint refuses the old dispatch: '+change,async()=>{
    const s=setup();hold(s);s.el('#assetNotes').value='keep';const pending=s.el('#saveAssetDetails').onclick();await tick();s.run(change);s.run('finishCheckpoint()');await pending;assert.equal(s.writes.length,0);
  });
test('library POST waits for its exact retained checkpoint',async()=>{
  const s=setup({autoOpen:false});hold(s);const pending=s.run("mutateAssets({ids:['a','b'],action:'edit',favorite:true})");await tick();assert.equal(s.writes.length,0);s.run('finishCheckpoint()');await tick();assert.equal(s.writes.length,1);s.accept(0);await pending;
});
test('unavailable optional shelf does not affect disabled, synchronous journal dispatch',async()=>{
  const s=setup();assert.equal(s.run('typeof assetRecovery.connect'),'function');s.run('assetRecovery.connect(null)');s.el('#assetNotes').value='keep';const pending=s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,1);s.accept(0);await pending;
});
