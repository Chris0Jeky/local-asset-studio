'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const conflict=(s,current)=>{const e=Error('Asset changed; nothing applied');e.status=409;e.data={workspace_id:s.run('activeAsset.workspace_id'),code:'asset_revision_conflict',current:[current],conflict_ids:['a'],missing_ids:[]};s.writes.at(-1).reject(e);};
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
    const observing=s.run('checkAssetSave()');s.reads[0].resolve({status:'unknown',workspace_id:s.payload(0).workspace_id,request_id:s.payload(0).request_id});await observing;
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
  const library=()=>{const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';
    s.run("assetState.assets.forEach((a,i)=>{a.created_at=i;a.collections=[];a.preset_name='Recipe '+a.id;});renderAssets()");return s;};
  const sample="[{id:'1',preset_name:'Anima',job_id:'j1',created_at:0},{id:'2',preset_name:'Krea',job_id:'j1',created_at:0},{id:'3',preset_name:'Anima',job_id:'j2',created_at:0}]";
  await check('Grouping is a pure projection with first-seen sections',()=>{
    const s=setup({autoOpen:false});
    const group=(mode,field='key')=>JSON.parse(s.run(`JSON.stringify(assetGroups(${sample},'${mode}').map(g=>[g.${field},g.assets.map(a=>a.id)]))`));
    assert.deepEqual(group('recipe'),[['recipe:Anima',['1','3']],['recipe:Krea',['2']]]);
    assert.deepEqual(group('run'),[['run:j1',['1','2']],['run:j2',['3']]]);
    assert.deepEqual(group('none'),[['',['1','2','3']]]);
    assert.deepEqual(group('recipe','label')[0][0],'Anima');
    // The same input twice gives the same sections; grouping never reorders or drops an asset.
    assert.deepEqual(group('recipe'),group('recipe'));
  });
  await check('Day grouping keys on the local calendar date and names missing dates',()=>{
    const s=setup({autoOpen:false});
    assert.match(s.run("assetGroupOf({created_at:1789228800},'day').key"),/^day:\d{4}-\d{2}-\d{2}$/);
    assert.equal(s.run("assetGroupOf({created_at:1789228800},'day').key"),s.run("assetGroupOf({created_at:1789228800+60},'day').key"));
    assert.deepEqual(s.run("assetGroupOf({},'day').label"),'No date recorded');
    assert.deepEqual(s.run("assetGroupOf({job_id:''},'run').label"),'No run recorded');
  });
  await check('A queue decision uses the ordinary edit save and then advances',async()=>{
    const s=library();
    assert.match(s.el('#reviewNext').textContent,/2 unreviewed/);
    s.run('startReviewQueue()');
    assert.equal(s.run('activeAsset.id'),'b');assert.match(s.el('#assetQueue').innerHTML,/1 of 2/);
    const p=s.run("assetQueueDecide('needs_work')");
    assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['b'],action:'edit',review:'needs_work'});
    s.accept(0);await p;
    assert.equal(s.run('activeAsset.id'),'a');assert.match(s.el('#assetQueue').innerHTML,/2 of 2/);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='b').review"),'needs_work');
  });
  await check('An unconfirmed queue decision never advances past its evidence',async()=>{
    const s=library();s.run('startReviewQueue()');
    const p=s.run("assetQueueDecide('selected')");s.writes[0].reject(Error('response lost'));await p;
    assert.equal(s.run('activeAsset.id'),'b');assert.match(s.el('#assetDetailStatus').textContent,/not confirmed/);
  });
  await check('The end of the queue still asks before discarding unsaved typing',()=>{
    const s=library();s.run('startReviewQueue()');
    s.run('assetQueue.index=assetQueue.ids.length-1');s.el('#assetNotes').value='unsaved thought';
    s.run('assetQueueStep(1)');
    assert.equal(s.el('#assetDialog').open,true);assert.equal(s.confirmations(),1);
    assert.equal(s.el('#assetNotes').value,'unsaved thought');assert.equal(s.writes.length,0);
  });
  await check('Reason chips toggle tags without typing and save nothing on their own',()=>{
    const s=setup();
    s.run("toggleAssetReason('hands')");
    assert.equal(s.el('#assetTags').value,'tag, hands');assert.match(s.el('#assetReviewReasons').innerHTML,/aria-pressed="true"/);
    s.run("toggleAssetReason('hands')");
    assert.equal(s.el('#assetTags').value,'tag');assert.equal(s.writes.length,0);
  });
  await check('A confirmed single review updates the loaded record without refetching the workspace',async()=>{
    const s=setup();s.run('globalThis.__refetches=0;refreshAssets=async()=>{globalThis.__refetches++;};');
    s.el('#assetReview').value='selected';const p=s.el('#saveAssetDetails').onclick();s.accept(0);await p;
    assert.equal(s.run('globalThis.__refetches'),0);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').review"),'selected');
  });
  await check('Bulk review saves each selected asset once and lists every failure',async()=>{
    const s=library();s.run("assetSelection=new Set(['a','b']);renderAssets()");
    const p=s.run("bulkReviewSelected('rejected')");
    assert.equal(s.writes.length,2);assert.deepEqual(s.payload(0).ids,['a']);assert.deepEqual(s.payload(1).ids,['b']);
    assert.equal(s.payload(0).review,'rejected');assert.deepEqual(s.payload(0).expected_revisions,{a:0});
    s.accept(0);s.writes[1].reject(Error('Workspace unavailable'));await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').review"),'rejected');
    assert.equal(s.run("assetState.assets.find(a=>a.id==='b').review"),'unreviewed');
    assert.match(s.el('#assetBulkReviewStatus').textContent,/1 of 2 marked as Rejected/);
    assert.match(s.el('#assetBulkReviewStatus').textContent,/1 failed and no retry was sent/);
    assert.match(s.el('#assetBulkReviewStatus').textContent,/not confirmed/);
  });
  console.log('Asset metadata frontend contracts passed:',count);
})().catch(e=>{console.error(e);process.exitCode=1;});
