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
    const {last_refusal,...unchanged}=retained(s,slot);assert.deepEqual(unchanged,before);
    assert.equal(last_refusal?.message,'refused by a transport boundary');assert.equal(last_refusal.status,status);
    assert.equal(last_refusal.request_id,before.operation.command.request_id);assert.equal(last_refusal.workspace_id,before.workspace_id);
    const next=setup({storage:s.storage,autoOpen:slot==='detail'});
    const check=next.run(slot==='detail'?'checkAssetSave()':'performLibraryCommand(assetLibraryPending,true)');
    next.reads[0].resolve(receipt);await check;
    assert.equal(next.writes.length,0,'recovery is a GET, never a replacement POST');
    if(slot==='detail')assert.equal(next.el('#assetNotes').value,'newer local typing');
    assert.equal(retained(next,slot)?.last_refusal,undefined,'confirmation clears only current refusal ownership');
  });
for(const slot of ['detail','library'])test(slot+' missing-target refusal retains the complete exact target set',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=begin(s,slot),c=s.payload(0),body=s.writes[0].options.body;
  s.writes[0].reject(Object.assign(Error('target no longer exists'),{status:409,data:{code:'asset_revision_conflict',workspace_id:c.workspace_id,request_id:c.request_id,conflict_ids:[],missing_ids:['a'],current:[]}}));await p;
  assert.equal(retained(s,slot)?.operation?.body,body);
  assert.deepEqual(retained(s,slot).operation.command.ids,c.ids);
  assert.equal(s.run(slot==='detail'?'!!assetDetailPending':'!!assetLibraryPending'),true);
  assert.equal(retained(s,slot).last_refusal?.message,'target no longer exists');
  const next=setup({storage:s.storage,autoOpen:false});
  assert.equal(next.reads.length,0);assert.equal(next.writes.length,0);
});

const refusal=(data={})=>Object.assign(Error('Synthetic <img src=x onerror="bad()"> refusal'),{status:403,data});
const panel=(s,slot)=>s.el(slot==='detail'?'#assetDetailRecovery':'#assetCommandRecovery').innerHTML;
async function refuse(s,slot,error=refusal()){
  const n=s.writes.length,p=begin(s,slot);s.writes[n].reject(error);await p;return n;
}
for(const slot of ['detail','library'])test(slot+' explanation survives typing, reopen and reload as literal retained text',async()=>{
  const s=setup({autoOpen:slot==='detail'});await refuse(s,slot);const saved=retained(s,slot),wire=s.writes[0].options.body;
  assert.equal(saved.last_refusal?.message,refusal().message);assert.match(panel(s,slot),/Synthetic &lt;img/);assert.doesNotMatch(panel(s,slot),/<img/);
  if(slot==='detail'){
    s.el('#assetNotes').value='newest local draft';s.el('#assetNotes').emit('input');s.approve(true);s.el('#closeAssetDialog').onclick();
    assert.match(s.el('#assetCommandRecovery').innerHTML,/Synthetic &lt;img/);s.run("openAsset('a')");assert.equal(s.el('#assetNotes').value,'newest local draft');
  }else{s.run("assetSelection=new Set(['b']);renderLibraryRecovery()");}
  assert.equal(retained(s,slot).operation.body,wire);assert.deepEqual(retained(s,slot).last_refusal,saved.last_refusal);
  const next=setup({storage:s.storage,autoOpen:slot==='detail'});assert.equal(next.writes.length,0);assert.equal(next.reads.length,0);assert.match(panel(next,slot),/Synthetic &lt;img/);
  assert.deepEqual(retained(next,slot).last_refusal,saved.last_refusal);if(slot==='detail')assert.equal(next.el('#assetNotes').value,'newest local draft');
  else assert.deepEqual(retained(next,slot).selection,['a','b']);
});
for(const slot of ['detail','library'])test(slot+' GET unknown or failure does not replace the last POST explanation',async()=>{
  const s=setup({autoOpen:slot==='detail'});await refuse(s,slot);const saved=retained(s,slot),command=saved.operation.command;
  let check=s.run(slot==='detail'?'checkAssetSave()':'performLibraryCommand(assetLibraryPending,true)').catch(()=>{});
  s.reads[0].resolve({workspace_id:command.workspace_id,request_id:command.request_id,status:'unknown'});await check;
  assert.deepEqual(retained(s,slot),saved);assert.match(panel(s,slot),/Synthetic &lt;img/);
  check=s.run(slot==='detail'?'checkAssetSave()':'performLibraryCommand(assetLibraryPending,true)').catch(()=>{});
  s.reads[1].reject(Object.assign(Error('GET unavailable'),{status:403,data:{}}));await check;
  assert.deepEqual(retained(s,slot),saved);assert.equal(s.writes.length,1);assert.equal(s.reads.length,2);
});
for(const slot of ['detail','library'])for(const status of [null,500])test(slot+' historical refusal remains qualified after a later '+(status||'lost-response')+' POST attempt',async()=>{
  const s=setup({autoOpen:slot==='detail'});await refuse(s,slot);
  if(slot==='detail'){s.el('#assetNotes').value='newer draft before the unresolved retry';s.el('#assetNotes').emit('input');}
  const saved=retained(s,slot),retry=s.run(slot==='detail'?'performAssetSave(assetDetailPending)':'performLibraryCommand(assetLibraryPending)').catch(e=>e);
  const error=Error('Later exact attempt outcome is unknown');if(status)error.status=status;
  s.writes[1].reject(error);const result=await retry;
  assert.deepEqual(retained(s,slot),saved);assert.equal(s.writes[1].options.body,saved.operation.body);
  assert.equal(s.writes.length,2);assert.equal(s.reads.length,0);
  assert.match(slot==='detail'?s.el('#assetDetailStatus').textContent:result.message,/not confirmed.*Later exact attempt outcome is unknown/i);
  assert.match(panel(s,slot),/Last recorded refusal/);assert.doesNotMatch(panel(s,slot),/Last attempt refused/);
  assert.match(panel(s,slot),/Synthetic &lt;img/);assert.doesNotMatch(panel(s,slot),/<img/);
  const next=setup({storage:s.storage,autoOpen:slot==='detail'});assert.match(panel(next,slot),/Last recorded refusal/);
  assert.equal(next.writes.length,0);assert.equal(next.reads.length,0);assert.deepEqual(retained(next,slot),saved);
});
for(const slot of ['detail','library'])for(const data of [{workspace_id:null},{workspace_id:'2'.repeat(32)},{request_id:''},{request_id:'replacement-request-01'},{code:'asset_workspace_conflict'}])
  test(slot+' explicit foreign refusal identity is not retained: '+JSON.stringify(data),async()=>{
    const s=setup({autoOpen:slot==='detail'});await refuse(s,slot,refusal(data));assert.equal(retained(s,slot).last_refusal,undefined);
    assert.equal(retained(s,slot).operation.body,s.writes[0].options.body);assert.doesNotMatch(panel(s,slot),/Last recorded refusal/);
  });
for(const slot of ['detail','library'])test(slot+' annotation storage failure leaves original refusal visible and exact pending evidence intact',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=begin(s,slot),raw=s.storage.getItem(PREFIX+slot);s.storage.failWrite=true;
  s.writes[0].reject(refusal());await p;assert.equal(s.storage.getItem(PREFIX+slot),raw);assert.equal(s.writes.length,1);
  if(slot==='detail')assert.match(s.el('#assetDetailStatus').textContent,/Synthetic.*refusal.*explanation could not be retained/i);
  else{
    s.storage.failWrite=false;const retry=s.run('performLibraryCommand(assetLibraryPending)').catch(e=>e);s.storage.failWrite=true;s.writes[1].reject(refusal());
    assert.match((await retry).message,/Synthetic.*refusal.*explanation could not be retained/i);
  }
});
for(const slot of ['detail','library'])test(slot+' annotation readback failure keeps exact pending bytes and reports the refused attempt truthfully',async()=>{
  const s=setup({autoOpen:slot==='detail'}),p=slot==='detail'?begin(s,slot):s.run("mutateAssets({ids:['a','b'],action:'edit',notes:'submitted snapshot'})").catch(e=>e);
  const before=retained(s,slot),get=s.storage.getItem.bind(s.storage),set=s.storage.setItem.bind(s.storage);let refuseReadback=false;
  s.storage.setItem=(key,raw)=>{set(key,raw);if(JSON.parse(raw).last_refusal)refuseReadback=true;};
  s.storage.getItem=key=>{if(refuseReadback){refuseReadback=false;throw Error('synthetic annotation readback failure');}return get(key);};
  s.writes[0].reject(refusal());const result=await p,after=retained(s,slot);
  assert.equal(after.operation.body,before.operation.body);assert.deepEqual(after.operation,before.operation);assert.equal(s.writes.length,1);
  assert.match(slot==='detail'?s.el('#assetDetailStatus').textContent:result.message,/Synthetic.*refusal.*explanation could not be retained/i);
  assert.equal(s.run(slot==='detail'?'!!assetDetailPending':'!!assetLibraryPending'),true);
});
test('an unverified missing-target conflict keeps its literal explanation visible when annotation storage fails',async()=>{
  const s=setup(),p=begin(s,'detail'),command=s.payload(0),raw=s.storage.getItem(PREFIX+'detail');s.storage.failWrite=true;
  const message='The target was removed <img src=x onerror="bad()">; check its lifecycle';
  s.writes[0].reject(Object.assign(Error(message),{status:409,data:{code:'asset_revision_conflict',workspace_id:command.workspace_id,request_id:command.request_id,conflict_ids:[],missing_ids:['a'],current:[]}}));await p;
  assert.equal(s.storage.getItem(PREFIX+'detail'),raw);assert.equal(s.writes.length,1);assert.equal(s.reads.length,0);
  assert.equal(s.run('!!assetDetailPending'),true);assert.equal(s.run('assetDetailConflict'),null);
  assert.ok(s.el('#assetDetailStatus').textContent.includes(message),'the displayed status retains the original literal reason after finally persistence fails');
  assert.match(s.el('#assetDetailStatus').textContent,/Conflict reply could not be verified.*explanation could not be retained/i);
  assert.equal(retained(s,'detail').last_refusal,undefined);
});
test('a verified detail revision conflict drops an earlier attempt annotation when it releases the pending command',async()=>{
  const s=setup();await refuse(s,'detail');const retry=s.run('performAssetSave(assetDetailPending)'),c=s.payload(1);
  const current={...s.receipt(1).current[0],metadata_revision:2,trashed_at:null};
  s.writes[1].reject(Object.assign(Error('changed'),{status:409,data:{code:'asset_revision_conflict',workspace_id:c.workspace_id,request_id:c.request_id,conflict_ids:['a'],missing_ids:[],current:[current]}}));await retry;
  assert.equal(s.run('assetDetailPending'),null);assert.equal(retained(s,'detail').last_refusal,undefined);assert.equal(s.run('!!assetDetailConflict'),true);
});
for(const slot of ['detail','library'])test(slot+' explicit local discard removes current annotation and cannot transfer it to a new command',async()=>{
  const s=setup({autoOpen:slot==='detail'});await refuse(s,slot);const old=retained(s,slot).last_refusal;assert.ok(old);
  s.approve(true);if(slot==='detail')s.el('#closeAssetDialog').onclick();await s.clickClosest('[data-asset-recovery-discard]',{assetRecoveryDiscard:slot});
  assert.equal(retained(s,slot),null);assert.doesNotMatch(s.el('#assetCommandRecovery').innerHTML,/Synthetic &lt;img/);
  if(slot==='detail')s.run("openAsset('a')");const next=begin(s,slot);assert.equal(retained(s,slot).last_refusal,undefined);assert.notEqual(retained(s,slot).operation.command.request_id,old.request_id);
  s.writes[1].reject(Error('new outcome unknown'));await next;assert.equal(retained(s,slot).last_refusal,undefined);
});
