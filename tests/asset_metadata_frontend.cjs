'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const conflict=(s,current)=>{const e=Error('Asset changed; nothing applied');e.status=409;e.data={code:'asset_revision_conflict',current:[current],conflict_ids:['a'],missing_ids:[]};s.writes.at(-1).reject(e);};
const saved=(s,fields={})=>({...JSON.parse(s.run('JSON.stringify(activeAsset)')),metadata_revision:1,...fields});
let count=0;
async function check(name,fn){await fn();count++;console.log('PASS',name);}
(async()=>{
  await check('Save binds the opened snapshot, not refreshed library metadata',async()=>{
    const s=setup();s.el('#assetNotes').value='edit';s.run('assetState.assets=assetState.assets.map(a=>({...a,metadata_revision:2}))');
    const p=s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,1);
    assert.deepEqual(s.payload(0).expected_revisions,{a:0});assert.equal(typeof s.payload(0).request_id,'string');
    s.accept(0);await p;assert.equal(s.run('activeAsset.metadata_revision'),1);
  });
  await check('Conflict retains edits, offers comparison and never auto-writes',async()=>{
    const s=setup();s.el('#assetTitle').value='My title';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,saved(s,{notes:'Their notes'}));await p;
    assert.equal(s.el('#assetTitle').value,'My title');assert.equal(s.el('#saveAssetDetails').disabled,true);
    assert.match(s.el('#assetDetailConflict').innerHTML,/Their notes/);assert.equal(s.writes.length,1);
    s.run('resolveAssetConflict(true)');assert.equal(s.el('#assetTitle').value,'My title');assert.equal(s.el('#assetNotes').value,'Their notes');
    assert.equal(s.run('activeAsset.metadata_revision'),1);assert.equal(s.writes.length,1);
    const next=s.el('#saveAssetDetails').onclick();assert.deepEqual(s.payload(1).expected_revisions,{a:1});assert.equal(s.payload(1).notes,undefined);
    s.accept(1);await next;assert.equal(s.el('#assetNotes').value,'Their notes');
  });
  await check('Same-field conflict preserves both versions and escapes markup',async()=>{
    const s=setup();s.el('#assetNotes').value='My correction';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,saved(s,{notes:'<img src=x onerror=evil()>Their correction'}));await p;
    assert.match(s.el('#assetDetailConflict').innerHTML,/Both changed/);assert.doesNotMatch(s.el('#assetDetailConflict').innerHTML,/<img/);
    s.run('resolveAssetConflict(false)');assert.equal(s.el('#assetNotes').value,'<img src=x onerror=evil()>Their correction');assert.equal(s.run('assetDetailDirty()'),false);assert.equal(s.writes.length,1);
  });
  await check('Unknown save retry keeps the same immutable body while newer typing survives',async()=>{
    const s=setup();s.el('#assetNotes').value='earlier';let p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('response lost'));await p;
    s.el('#assetNotes').value='newer';p=s.el('#saveAssetDetails').onclick();assert.equal(s.writes[1].options.body,s.writes[0].options.body);
    s.accept(1);await p;assert.equal(s.el('#assetNotes').value,'newer');assert.equal(s.run('assetDetailDirty()'),true);assert.equal(s.run('activeAsset.notes'),'earlier');
  });
  await check('Receipt lookup confirms without a second POST',async()=>{
    const s=setup();s.el('#assetNotes').value='earlier';const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const observing=s.run('checkAssetSave()');assert.equal(s.reads.length,1);assert.match(s.reads[0].url,/\/api\/assets\/commands\//);
    s.reads[0].resolve(s.receipt(0));await observing;assert.equal(s.writes.length,1);assert.equal(s.run('assetDetailDirty()'),false);
  });
  await check('Missing receipt stays unknown; malformed success is never accepted',async()=>{
    const s=setup();s.el('#assetNotes').value='keep';const p=s.el('#saveAssetDetails').onclick();s.writes[0].resolve({});await p;
    assert.equal(s.run('assetDetailDirty()'),true);assert.match(s.el('#assetDetailStatus').textContent,/not confirmed/);
    const observing=s.run('checkAssetSave()');s.reads[0].resolve({status:'unknown',request_id:s.payload(0).request_id});await observing;
    assert.equal(s.writes.length,1);assert.equal(s.run('assetDetailDirty()'),true);assert.equal(s.el('#assetFavorite').disabled,true);
  });
  await check('Missing revision blocks writes rather than guessing zero',async()=>{
    const s=setup();s.run('delete activeAsset.metadata_revision');s.el('#assetNotes').value='keep';await s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,0);assert.match(s.el('#assetDetailStatus').textContent,/Reload/);
  });
  await check('A recovered Trash command cannot discard typing after its lost reply',async()=>{
    const s=setup();s.approve(true);s.el('#assetNotes').value='First draft';
    const p=s.el('#assetTrash').onclick();s.writes[0].reject(Error('lost Trash reply'));await p;
    s.el('#assetNotes').value='New notes after loss';const observing=s.run('checkAssetSave()');
    const receipt=s.receipt(0);receipt.applied={trashed_at:123};s.reads[0].resolve(receipt);await observing;
    assert.equal(s.el('#assetDialog').open,true);assert.equal(s.el('#assetNotes').value,'New notes after loss');
    assert.equal(s.run('activeAsset.trashed_at'),123);assert.equal(s.run('assetDetailDirty()'),true);
  });
  await check('Malformed conflict snapshots never replace the draft',async()=>{
    const s=setup();s.el('#assetNotes').value='Keep';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,{id:'a',metadata_revision:1,tags:'not an array'});await p;
    assert.doesNotThrow(()=>s.run('resolveAssetConflict(false)'));assert.equal(s.el('#assetNotes').value,'Keep');
    assert.match(s.el('#assetDetailConflict').innerHTML,/unavailable/);
  });
  await check('A library receipt does not wait for a stalled refresh',async()=>{
    const s=setup();s.run('refreshAssets=()=>new Promise(()=>{})');
    const p=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})");s.accept(0);
    const winner=await Promise.race([p.then(()=>true),new Promise(resolve=>setTimeout(()=>resolve(false),50))]);
    assert.equal(winner,true);assert.equal(s.run('assetState.assets[0].favorite'),true);
  });
  console.log('Asset metadata frontend contracts passed:',count);
})().catch(e=>{console.error(e);process.exitCode=1;});
