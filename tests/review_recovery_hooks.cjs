'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
(async()=>{
  const s=setup();s.run('assetReviewRecovery={blocked:()=>false,beforeSend:()=>false,changed:()=>{},closed:()=>{},opened:()=>{},refreshed:()=>{}}');
  s.el('#assetNotes').value='A draft';const held=s.el('#saveAssetDetails').onclick();
  assert.equal(s.writes.length,0,'A refused recovery checkpoint must prevent metadata dispatch');await held;
  assert.equal(s.run('assetDetailPending'),null,'Unsent command does not become an unconfirmed submission');
  const good=setup();good.run('let checkpoints=[];assetReviewRecovery={blocked:()=>false,beforeSend:operation=>{checkpoints.push(JSON.parse(JSON.stringify({body:operation.body,snapshot:operation.snapshot})));return true;},changed:()=>{},closed:()=>{},opened:()=>{},refreshed:()=>{}}');
  good.el('#assetNotes').value='At click';const sent=good.el('#saveAssetDetails').onclick();
  assert.equal(good.run('checkpoints.length'),1);assert.equal(good.run('checkpoints[0].body'),good.writes[0].options.body);
  good.el('#assetNotes').value='Later';assert.equal(good.run('checkpoints[0].snapshot.notes'),'At click');good.accept(0);await sent;
  const blocked=setup();blocked.run('assetReviewRecovery={blocked:()=>true,beforeSend:()=>{throw Error("must not dispatch")},changed:()=>{},closed:()=>{},opened:()=>{},refreshed:()=>{}}');blocked.el('#assetNotes').value='Local';await blocked.el('#saveAssetDetails').onclick();assert.equal(blocked.writes.length,0);
  console.log('Review recovery integration hooks passed: 3');
})().catch(e=>{console.error(e);process.exitCode=1;});
