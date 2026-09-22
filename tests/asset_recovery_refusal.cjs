'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const {PREFIX}=require('../app/static/asset-recovery.js');
const retained=(s,slot)=>JSON.parse(s.storage.getItem(PREFIX+slot));
function begin(s,slot){
  if(slot==='detail'){s.el('#assetNotes').value='submitted snapshot';return s.el('#saveAssetDetails').onclick();}
  s.run("assetSelection=new Set(['a','b'])");
  return s.run("mutateAssets({ids:['a','b'],action:'edit',notes:'submitted snapshot'})").catch(()=>{});
}
for(const slot of ['detail','library'])for(const status of [400,401,403,404,408,409,413,422,429])
  test(slot+' HTTP '+status+' does not erase an earlier unconfirmed command',async()=>{
    const s=setup({autoOpen:slot==='detail'}),first=begin(s,slot),receipt=s.receipt(0);
    s.writes[0].reject(Error('committed response lost'));await first;
    if(slot==='detail'){s.el('#assetNotes').value='newer local typing';s.el('#assetNotes').emit('input');}
    const retry=s.run(slot==='detail'?'performAssetSave(assetDetailPending)':'performLibraryCommand(assetLibraryPending)').catch(()=>{});
    const before=retained(s,slot),body=s.writes[0].options.body;
    assert.equal(s.writes[1].options.body,body);
    s.writes[1].reject(Object.assign(Error('refused by a transport boundary'),{status,data:{error:'refused'}}));await retry;
    assert.equal(retained(s,slot)?.operation?.body,body,'HTTP status alone cannot erase unresolved evidence');
    assert.deepEqual(retained(s,slot),before);
    const next=setup({storage:s.storage,autoOpen:slot==='detail'});
    const check=next.run(slot==='detail'?'checkAssetSave()':'performLibraryCommand(assetLibraryPending,true)');
    next.reads[0].resolve(receipt);await check;
    assert.equal(next.writes.length,0,'recovery is a GET, never a replacement POST');
    if(slot==='detail')assert.equal(next.el('#assetNotes').value,'newer local typing');
  });
for(const slot of ['detail','library'])test(slot+' missing-target refusal retains the complete exact target set',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=begin(s,slot),c=s.payload(0),body=s.writes[0].options.body;
  s.writes[0].reject(Object.assign(Error('target no longer exists'),{status:409,data:{code:'asset_revision_conflict',workspace_id:c.workspace_id,request_id:c.request_id,conflict_ids:[],missing_ids:['a'],current:[]}}));await p;
  assert.equal(retained(s,slot)?.operation?.body,body);
  assert.deepEqual(retained(s,slot).operation.command.ids,c.ids);
  assert.equal(s.run(slot==='detail'?'!!assetDetailPending':'!!assetLibraryPending'),true);
  const next=setup({storage:s.storage,autoOpen:false});
  assert.equal(next.reads.length,0);assert.equal(next.writes.length,0);
});
