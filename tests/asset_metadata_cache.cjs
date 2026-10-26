// Confirmed metadata must have one meaning across the loaded page and explicit ID reads.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const scope='1'.repeat(32),catalogue={epoch:'a'.repeat(32),revision:1};
const asset=(id,extra={})=>({id,workspace_id:scope,title:id,notes:'original',tags:[],review:'unreviewed',favorite:false,trashed_at:null,
  media_type:'image',preset_id:'hero',preset_name:'Hero',created_at:1,metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,...extra});
const page=assets=>({workspace_id:scope,catalogue,assets,next_cursor:'next'});
const collections=()=>({workspace_id:scope,catalogue,collections:[],next_cursor:null});
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const value=(s,code)=>JSON.parse(s.run('JSON.stringify('+code+')'));
async function load(s,assets,position=null){
  const n=s.reads.length,p=s.actualRefresh(true,position);await flush();
  s.reads[n].resolve(page(assets));s.reads[n+1].resolve(collections());assert.equal(await p,true);
}
async function observe(s,items){
  const n=s.writes.length,p=s.run('resolveAssetIDs('+JSON.stringify(items.map(i=>i.id))+')');
  assert.equal(s.writes[n].url,'/api/assets/selection');
  s.writes[n].resolve({workspace_id:scope,catalogue,items});assert.equal(await p,true);
}
const observed=a=>({id:a.id,state:a.trashed_at==null?'active':'trashed',asset:a});
async function ready(){
  const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='title';
  await load(s,[asset('b')]);await observe(s,[observed(asset('a')),observed(asset('off'))]);
  await load(s,[asset('b'),asset('a')],{cursor:'second',history:[null]});
  s.run("assetSelection=new Set(['a','off']);renderAssets()");return s;
}
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log('PASS',name);}catch(error){failed++;console.error('FAIL',name,'\n'+error.stack);}}
(async()=>{
  await test('An off-page resolved asset saves into the grid without changing page order or selection',async()=>{
    const s=await ready(),before=value(s,'[assetState.assets.map(a=>a.id),assetPaging.cursor,assetPaging.history,[...assetSelection]]'),reads=s.reads.length;
    s.run("openAsset('a')");s.el('#assetTitle').value='Confirmed title';s.el('#assetTags').value='confirmed';s.el('#assetReview').value='selected';
    const n=s.writes.length,p=s.el('#saveAssetDetails').onclick();s.accept(n);assert.equal(await p,true);
    assert.match(s.el('#assetGrid').innerHTML,/Confirmed title/);assert.match(s.el('#assetGrid').innerHTML,/confirmed/);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').metadata_revision"),1);
    assert.equal(s.run("assetResolved.get('a').asset.review"),'selected');
    assert.deepEqual(value(s,'[assetState.assets.map(a=>a.id),assetPaging.cursor,assetPaging.history,[...assetSelection]]'),before);
    assert.equal(s.reads.length,reads,'a confirmed in-place save needs no page read');
    assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="off"/);
  });
  await test('The next grid star toggles the confirmed favorite with the matching revision',async()=>{
    const s=await ready();s.run("openAsset('a')");
    const n=s.writes.length,p=s.el('#assetFavorite').onclick();s.accept(n);await p;
    assert.match(s.el('#assetGrid').innerHTML,/data-asset-favorite="a" aria-label="Unfavorite a"/);
    s.el('#closeAssetDialog').onclick();
    const next=s.writes.length,toggle=s.clickClosest('[data-asset-favorite]',{assetFavorite:'a'});
    assert.equal(s.payload(next).favorite,false);assert.deepEqual(s.payload(next).expected_revisions,{a:1});
    s.accept(next);await toggle;
    assert.equal(s.run("assetResolved.get('a').asset.favorite"),false);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').favorite"),false);
    assert.match(s.el('#assetGrid').innerHTML,/data-asset-favorite="a" aria-label="Favorite a"/);
  });
  await test('Bulk review reconciles both copies before repainting the loaded page',async()=>{
    const s=await ready();s.run("assetSelection=new Set(['a'])");
    const n=s.writes.length,p=s.run("bulkReviewSelected('selected')");s.accept(n);await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').review"),'selected');
    assert.equal(s.run("assetResolved.get('a').asset.metadata_revision"),1);
    assert.match(s.el('#assetGrid').innerHTML,/review-selected/);
    assert.equal(s.run("assetResolved.get('off').asset.metadata_revision"),0);
  });
  await test('A Library receipt repaints confirmed metadata without waiting for its refresh',async()=>{
    const s=await ready();s.run('refreshAssets=()=>new Promise(()=>{})');
    const n=s.writes.length,p=s.run("mutateAssets({ids:['a'],action:'edit',title:'Library title'})");s.accept(n);await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').title"),'Library title');
    assert.equal(s.run("assetResolved.get('a').asset.title"),'Library title');
    assert.match(s.el('#assetGrid').innerHTML,/Library title/);
    assert.deepEqual(value(s,'assetState.assets.map(a=>a.id)'),['b','a']);
  });
  await test('A newer page observation remains authoritative after navigating away from it',async()=>{
    const s=await ready();await load(s,[asset('a',{metadata_revision:4,title:'Newer page',favorite:true,notes:'other writer'})]);
    assert.equal(s.run("assetRecord('a').metadata_revision"),4);
    await load(s,[asset('b')]);
    assert.equal(s.run("assetRecord('a').metadata_revision"),4);assert.equal(s.run("assetRecord('a').notes"),'other writer');
    await observe(s,[observed(asset('a',{metadata_revision:2,title:'Older selected read'}))]);
    assert.equal(s.run("assetRecord('a').metadata_revision"),4,'a late older full observation cannot replace the newer one');
    assert.deepEqual(value(s,'assetState.assets.map(a=>a.id)'),['b']);
  });
  await test('Missing observations cannot expose stale page metadata or authorize a favorite',async()=>{
    const s=await ready();await observe(s,[{id:'a',state:'missing',asset:null}]);s.run('renderAssets()');
    assert.equal(s.run("assetRecord('a')"),null);assert.equal(s.run("assetRecords().some(a=>a.id==='a')"),false);
    assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="a"/);
    assert.deepEqual(value(s,'assetState.assets.map(a=>a.id)'),['b','a']);
    const n=s.writes.length;await s.clickClosest('[data-asset-favorite]',{assetFavorite:'a'});assert.equal(s.writes.length,n);
    assert.equal(s.run("assetSelection.has('a')"),true);assert.equal(s.run('assetSelectionInfo().missing'),1);
  });
  await test('A confirmed Trash receipt updates lifecycle without dropping page IDs or selection',async()=>{
    const s=await ready();s.run("openAsset('a')");s.approve(true);
    const n=s.writes.length,p=s.el('#assetTrash').onclick();s.accept(n);await p;
    assert.equal(s.run("assetResolved.get('a').state"),'trashed');
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').trashed_at"),123);
    assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="a"/);
    assert.deepEqual(value(s,'assetState.assets.map(a=>a.id)'),['b','a']);assert.equal(s.run("assetSelection.has('a')"),true);
  });
  await test('A recovered old receipt cannot overwrite a newer trashed observation or revive a missing target',async()=>{
    for(const state of ['trashed','missing']){
      const s=await ready();s.run("openAsset('a')");s.el('#assetNotes').value='historical edit';
      const n=s.writes.length,p=s.el('#saveAssetDetails').onclick(),receipt=s.receipt(n);
      const current=asset('a',{metadata_revision:4,notes:'newer metadata',trashed_at:123});
      await observe(s,[state==='missing'?{id:'a',state,asset:null}:observed(current)]);
      receipt.current=state==='missing'?[]:[current];s.writes[n].resolve(receipt);assert.equal(await p,true);
      s.run('renderAssets()');assert.equal(s.run("assetResolved.get('a').state"),state);
      assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="a"/);
      assert.equal(s.run("!!assetDetailConflict"),true);assert.equal(s.el('#assetNotes').value,'historical edit');
      if(state==='trashed')assert.equal(s.run("assetRecord('a').notes"),'newer metadata');
      else assert.equal(s.run("assetRecords().some(a=>a.id==='a')"),false);
    }
  });
  await test('Accepted historical receipts invalidate held ID observations even when no copy needs their patch',async()=>{
    const s=await ready();s.run("openAsset('a')");s.el('#assetNotes').value='historical edit';
    const n=s.writes.length,p=s.el('#saveAssetDetails').onclick(),receipt=s.receipt(n);
    await load(s,[asset('b'),asset('a',{metadata_revision:4,notes:'newer page'})]);
    await observe(s,[observed(asset('a',{metadata_revision:4,notes:'newer page'}))]);
    const readIndex=s.writes.length,reading=s.run("resolveAssetIDs(['a'])"),epoch=s.run('assetReceiptEpoch');
    receipt.current=[asset('a',{metadata_revision:4,notes:'newer page'})];s.writes[n].resolve(receipt);await p;
    assert.equal(s.run('assetReceiptEpoch'),epoch+1);
    s.writes[readIndex].resolve({workspace_id:scope,catalogue,items:[observed(asset('a'))]});
    assert.equal(await reading,false);assert.equal(s.run("assetRecord('a').metadata_revision"),4);
  });
  await test('Accepted historical receipts invalidate held pages even when no copy needs their patch',async()=>{
    const s=await ready();s.run("openAsset('a')");s.el('#assetNotes').value='historical edit';
    const n=s.writes.length,p=s.el('#saveAssetDetails').onclick(),receipt=s.receipt(n);
    await load(s,[asset('b'),asset('a',{metadata_revision:4,notes:'newer page'})]);
    await observe(s,[observed(asset('a',{metadata_revision:4,notes:'newer page'}))]);
    const r=s.reads.length,reading=s.actualRefresh(true);await flush();
    receipt.current=[asset('a',{metadata_revision:4,notes:'newer page'})];s.writes[n].resolve(receipt);await p;
    s.reads[r].resolve(page([asset('a')]));s.reads[r+1].resolve(collections());await flush();
    assert.equal(s.reads.length,r+4,'the pre-receipt page must be discarded and read again');
    assert.equal(s.run("assetRecord('a').metadata_revision"),4);
    s.reads[r+2].resolve(page([asset('b'),asset('a',{metadata_revision:4,notes:'newer page'})]));s.reads[r+3].resolve(collections());
    assert.equal(await reading,true);assert.equal(s.run("assetRecord('a').notes"),'newer page');
  });
  await test('Idempotent Trash and Restore receipts retain their unchanged revision and fields',async()=>{
    for(const [action,trashed_at] of [['trash',123],['restore',null]]){
      const s=await ready(),current=asset('a',{metadata_revision:3,trashed_at,notes:'retained note'});
      await observe(s,[observed(current)]);const before=value(s,"assetRecord('a')"),epoch=s.run('assetReceiptEpoch');
      const n=s.writes.length,p=s.run(`mutateAssets({ids:['a'],action:'${action}'})`),receipt=s.receipt(n);
      receipt.unchanged=['a'];receipt.applied={};receipt.revisions={a:3};receipt.current=[current];s.writes[n].resolve(receipt);await p;
      assert.deepEqual(value(s,"assetRecord('a')"),before);assert.equal(s.run('assetReceiptEpoch'),epoch+1);
      assert.equal(s.run("assetResolved.get('a').state"),action==='trash'?'trashed':'active');
    }
  });
  await test('Collection receipts advance only the known revision without inventing a full asset snapshot',async()=>{
    const s=await ready(),n=s.writes.length,p=s.run("mutateAssets({ids:['a'],action:'add_collection',collection_id:'collection'})");
    s.accept(n);await p;
    assert.equal(s.run("assetRecord('a').metadata_revision"),1);
    assert.equal(s.run("Object.hasOwn(assetRecord('a'),'collection_id')"),false);
    assert.deepEqual(value(s,"assetRecord('a').collections"),[],'collection membership is established by the existing explicit read');
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').metadata_revision"),1);
  });
  console.log('Asset metadata cache contracts: '+passed+' passed, '+failed+' failed');if(failed)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
