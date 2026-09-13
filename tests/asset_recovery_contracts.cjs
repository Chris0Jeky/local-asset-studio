'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const {PREFIX}=require('../app/static/asset-recovery.js');
const draft=(s,text)=>{s.el('#assetNotes').value=text;s.el('#assetNotes').emit('input');};
const retained=(s,slot='detail')=>JSON.parse(s.storage.getItem(PREFIX+slot));
let count=0;
async function check(name,fn){await fn();count++;console.log('PASS',name);}
(async()=>{
  await check('In-flight reload restores exact bytes and opened revision without any request',async()=>{
    const first=setup();draft(first,'sent');void first.el('#saveAssetDetails').onclick();
    assert.equal(retained(first).operation.body,first.writes[0].options.body);
    const next=setup({storage:first.storage,autoOpen:false});
    assert.equal(next.writes.length,0);assert.equal(next.reads.length,0);assert.equal(next.el('#assetDialog').open,false);
    next.run("assetState.assets[0].metadata_revision=1;openAsset('a')");
    assert.equal(next.run('activeAsset.metadata_revision'),0);assert.equal(next.el('#assetNotes').value,'sent');
    const observing=next.run('checkAssetSave()');next.reads[0].resolve({status:'unknown',workspace_id:first.payload(0).workspace_id,request_id:first.payload(0).request_id});await observing;
    assert.equal(next.writes.length,0);const retry=next.el('#saveAssetDetails').onclick();
    assert.equal(next.writes[0].options.body,first.writes[0].options.body);next.accept(0);await retry;
    assert.equal(retained(next),null);
  });
  await check('Response-loss receipt preserves newer typing across two reloads',async()=>{
    const first=setup();draft(first,'sent');const sending=first.el('#saveAssetDetails').onclick();first.writes[0].reject(Error('lost'));await sending;draft(first,'newer');
    const next=setup({storage:first.storage});const observing=next.run('checkAssetSave()');next.reads[0].resolve(first.receipt(0));await observing;
    assert.equal(next.writes.length,0);assert.equal(next.el('#assetNotes').value,'newer');assert.equal(next.run('activeAsset.notes'),'sent');
    assert.equal(retained(next).operation,null);
    const again=setup({storage:next.storage});assert.equal(again.el('#assetNotes').value,'newer');assert.equal(again.run('activeAsset.metadata_revision'),1);
    const save=again.el('#saveAssetDetails').onclick();assert.deepEqual(again.payload(0).expected_revisions,{a:1});assert.equal(again.payload(0).notes,'newer');assert.notEqual(again.payload(0).request_id,first.payload(0).request_id);again.accept(0);await save;
  });
  await check('Unsent draft reload remains a draft bound to its original revision',async()=>{
    const first=setup();draft(first,'unsent');assert.equal(retained(first).operation,null);
    const next=setup({storage:first.storage,autoOpen:false});next.run("assetState.assets[0].metadata_revision=9;openAsset('a')");
    assert.equal(next.el('#assetNotes').value,'unsent');assert.equal(next.writes.length,0);
    const save=next.el('#saveAssetDetails').onclick();assert.deepEqual(next.payload(0).expected_revisions,{a:0});next.accept(0);await save;
  });
  await check('Conflict survives reload; rebasing only prepares a new reviewed save',async()=>{
    const first=setup();draft(first,'my edit');const save=first.el('#saveAssetDetails').onclick();
    const current={...JSON.parse(first.run('JSON.stringify(activeAsset)')),metadata_revision:3,title:'remote title'};
    const error=Object.assign(Error('changed'),{status:409,data:{workspace_id:current.workspace_id,code:'asset_revision_conflict',current:[current]}});first.writes[0].reject(error);await save;
    const next=setup({storage:first.storage});assert.match(next.el('#assetDetailConflict').innerHTML,/remote title/);assert.equal(next.el('#saveAssetDetails').disabled,true);
    next.run('resolveAssetConflict(true)');assert.equal(next.writes.length,0);assert.equal(next.el('#assetNotes').value,'my edit');assert.equal(next.el('#assetTitle').value,'remote title');
    const again=setup({storage:next.storage});const p=again.el('#saveAssetDetails').onclick();assert.deepEqual(again.payload(0).expected_revisions,{a:3});assert.equal(again.payload(0).title,undefined);assert.notEqual(again.payload(0).request_id,first.payload(0).request_id);again.accept(0);await p;
  });
  await check('Trash receipt after reload never discards typing after the lost response',async()=>{
    const first=setup();first.approve(true);draft(first,'initial draft');const p=first.el('#assetTrash').onclick();first.writes[0].reject(Error('lost'));await p;draft(first,'new draft after loss');
    const next=setup({storage:first.storage});const observe=next.run('checkAssetSave()');next.reads[0].resolve(first.receipt(0));await observe;
    assert.equal(next.writes.length,0);assert.equal(next.el('#assetDialog').open,true);assert.equal(next.el('#assetNotes').value,'new draft after loss');assert.equal(next.run('activeAsset.trashed_at'),123);
    const again=setup({storage:next.storage});assert.equal(again.el('#assetNotes').value,'new draft after loss');assert.equal(again.el('#assetTrash').textContent,'Restore');
  });
  await check('Library recovery retains selection and exact batch command without automatic replay',async()=>{
    const first=setup();first.run("assetSelection=new Set(['a','b'])");const p=first.run("mutateAssets({ids:['a','b'],action:'add_collection',collection_id:'c'})");first.writes[0].reject(Error('lost'));await assert.rejects(p);
    const next=setup({storage:first.storage,autoOpen:false});assert.equal(next.writes.length,0);assert.equal(next.run('assetSelection.size'),2);
    const retry=next.run('performLibraryCommand(assetLibraryPending)');assert.equal(next.writes[0].options.body,first.writes[0].options.body);next.accept(0);await retry;assert.equal(retained(next,'library'),null);
  });
  await check('Quota failure prevents the POST; recovery uses the same in-memory command',async()=>{
    const s=setup();draft(s,'keep');s.storage.failWrite=true;await s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,0);assert.equal(s.el('#assetNotes').value,'keep');assert.match(s.el('#assetDetailStatus').textContent,/retain/);
    const id=s.run('assetDetailPending.command.request_id');s.storage.failWrite=false;const p=s.el('#saveAssetDetails').onclick();assert.equal(s.payload(0).request_id,id);s.accept(0);await p;
  });
  await check('Unreadable journal is preserved and blocks writes instead of being replaced',async()=>{
    const first=setup();first.storage.values.set(PREFIX+'detail','{broken');const next=setup({storage:first.storage});draft(next,'visible');await next.el('#saveAssetDetails').onclick();
    assert.equal(next.writes.length,0);assert.equal(first.storage.getItem(PREFIX+'detail'),'{broken');assert.match(next.el('#assetDetailStatus').textContent,/retained save/);
    next.approve(true);next.el('#closeAssetDialog').onclick();assert.equal(first.storage.getItem(PREFIX+'detail'),'{broken');
  });
  await check('Unavailable storage on page load leaves editing visible and sends nothing',async()=>{
    const first=setup();first.storage.failRead=true;const next=setup({storage:first.storage});draft(next,'visible');await next.el('#saveAssetDetails').onclick();assert.equal(next.el('#assetNotes').value,'visible');assert.equal(next.writes.length,0);
  });
  await check('Failed journal clearing retains the confirmed command until an explicit receipt check',async()=>{
    const s=setup();draft(s,'sent');const p=s.el('#saveAssetDetails').onclick();s.storage.failClear=true;s.accept(0);await p;
    assert.equal(s.run('assetDetailPending.command.request_id'),s.payload(0).request_id);assert.equal(retained(s).operation.command.request_id,s.payload(0).request_id);
    s.storage.failClear=false;const check=s.run('checkAssetSave()');s.reads[0].resolve(s.receipt(0));await check;assert.equal(s.writes.length,1);assert.equal(retained(s),null);
  });
  await check('Close retains an unknown command and reopening a different asset cannot replace it',async()=>{
    const s=setup();draft(s,'sent');const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;s.approve(true);s.el('#closeAssetDialog').onclick();
    assert.equal(s.el('#assetDialog').open,false);const body=retained(s).operation.body;s.run("openAsset('b')");assert.equal(s.el('#assetDialog').open,false);assert.equal(retained(s).operation.body,body);s.run("openAsset('a')");assert.equal(s.el('#assetNotes').value,'sent');
  });
  await check('Ordinary draft discard still requires consent and clears only after it',async()=>{
    const s=setup();draft(s,'draft');s.el('#closeAssetDialog').onclick();assert.notEqual(retained(s),null);s.approve(true);s.el('#closeAssetDialog').onclick();assert.equal(retained(s),null);
  });
  await check('Missing asset keeps an escaped copy of the draft available without a write',async()=>{
    const first=setup();draft(first,'<private draft>');const next=setup({storage:first.storage,autoOpen:false});next.run("assetState.assets=[];openAsset('a')");
    assert.equal(next.writes.length,0);assert.equal(next.el('#assetDialog').open,false);assert.match(next.el('#assetCommandRecovery').innerHTML,/&lt;private draft&gt;/);assert.equal(retained(next).draft.notes,'<private draft>');
  });
  await check('Opening another asset after reload cannot silently discard a retained draft',async()=>{
    const first=setup();draft(first,'retained');const next=setup({storage:first.storage,autoOpen:false});next.run("openAsset('b')");assert.equal(next.el('#assetDialog').open,false);assert.equal(retained(next).draft.notes,'retained');
    next.approve(true);next.run("openAsset('b')");assert.equal(next.run('activeAsset.id'),'b');assert.equal(retained(next),null);
  });
  console.log('Asset reload recovery contracts passed:',count);
})().catch(error=>{console.error(error);process.exitCode=1;});
