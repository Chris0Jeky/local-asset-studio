'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup}=require('./asset_detail_contracts.cjs');
const {setup:collections,memoryStorage}=require('./collection_editor_fixture.cjs');
const Recovery=require('../app/static/asset-recovery.js');
const W='1'.repeat(32),asset={id:'private-one',workspace_id:W,privacy:'private',title:'Private canary',notes:'',tags:[],review:'unreviewed',favorite:false,trashed_at:null,media_type:'image',job_id:'private-job',metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,url:'/api/assets/private-one/file?privacy=private'};
const change=(s,scope,previousScope='regular')=>s.dispatch('studio:privacy-change',{detail:{scope,previousScope}});
function setPrivate(s){s.run('assetState.assets='+JSON.stringify([asset])+';openAsset("private-one");');}
test('privacy switching retains independent drafts, clears all visible text and never shares search or collection preferences',async()=>{
  const local=memoryStorage(),s=setup({localStorage:local});s.el('#assetNotes').value='Ordinary draft';s.run('retainAssetDraft()');
  await change(s,'private');setPrivate(s);s.el('#assetNotes').value='Private draft canary';s.el('#assetSearch').value='Private search canary';s.run('assetScope="collection:private-canary";retainAssetDraft();rememberAssetView();assetSelection.add("private-one");');
  assert.match(s.run('assetThumbUrl(activeAsset)'),/&privacy=private/);assert.match(s.el('#assetDownload').href,/privacy=private&download/);
  for(const id of ['assetDetailConflict','assetDetailRecovery'])s.el('#'+id).innerHTML='Private stale detail canary';
  await change(s,'regular','private');
  assert.equal(s.el('#assetDialog').open,false);assert.equal(s.el('#assetNotes').value,'');assert.equal(s.run('assetSelection.size'),0);assert.equal(s.run('activeAsset'),null);
  assert.equal(s.run('assetRetainedDetail.draft.notes'),'Ordinary draft');assert.doesNotMatch(JSON.stringify([...local.data.values()]),/Private|private-canary/);
  assert.doesNotMatch(s.storage.getItem(Recovery.PREFIX+'detail'),/Private/);assert.equal(s.el('#assetSearch').value,'');
  for(const id of ['assetDetailConflict','assetDetailRecovery'])assert.doesNotMatch(s.el('#'+id).innerHTML,/Private stale/);
  await change(s,'private');assert.equal(s.run('assetRetainedDetail.draft.notes'),'Private draft canary');assert.equal(s.el('#assetSearch').value,'Private search canary');
});
test('scope switching preserves a bounded private draft in memory when browser storage refuses writes',async()=>{
  const s=setup({autoOpen:false});await change(s,'private');setPrivate(s);
  s.el('#assetNotes').value='Unstored private draft canary';s.storage.failWrite=true;
  await change(s,'regular','private');assert.equal(s.el('#assetNotes').value,'');assert.equal(s.run('assetRetainedDetail'),null);
  assert.doesNotMatch(JSON.stringify([...s.storage.values.values()]),/Unstored private/);
  await change(s,'private');assert.equal(s.run('assetRetainedDetail.draft.notes'),'Unstored private draft canary');assert.match(s.run('assetRecoveryError'),/memory/);
  setPrivate(s);assert.equal(s.el('#assetNotes').value,'Unstored private draft canary');assert.equal(s.writes.length,0);
  s.storage.failWrite=false;s.run('retainAssetDraft()');assert.equal(s.run('assetUnstoredDetails.size'),0);
  assert.match(s.storage.getItem('studio.privacy.private.'+Recovery.PREFIX+'detail'),/Unstored private draft/);
});
test('a private mutation reply after switching cannot repopulate regular status or retire private recovery',async()=>{
  const s=setup({autoOpen:false});await change(s,'private');setPrivate(s);s.el('#assetNotes').value='Private submitted canary';
  const request=s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,1);assert.equal(s.writes[0].options.headers['X-Studio-Privacy'],'private');
  await change(s,'regular','private');s.el('#assetDetailStatus').textContent='Regular status';
  s.writes[0].reject(Object.assign(Error('Private error canary'),{status:400}));await request;
  assert.equal(s.el('#assetDetailStatus').textContent,'Regular status');assert.equal(s.run('assetRetainedDetail'),null);
  const retained=JSON.parse(s.storage.getItem('studio.privacy.private.'+Recovery.PREFIX+'detail'));
  assert.equal(retained.operation.command.notes,'Private submitted canary');assert.equal(retained.last_refusal,undefined);
});
test('an old private bulk reply cannot release a new regular bulk owner',async()=>{
  const s=setup({autoOpen:false});await change(s,'private');setPrivate(s);s.run('assetSelection=new Set(["private-one"]);');
  const old=s.run('bulkReviewSelected("selected")');assert.equal(s.writes.length,1);assert.equal(s.writes[0].options.headers['X-Studio-Privacy'],'private');
  await change(s,'regular','private');assert.equal(s.run('assetBulkReviewBusy'),false);
  const regular={...asset,id:'regular-one',privacy:'regular',title:'Ordinary'};s.run('assetState.assets='+JSON.stringify([regular])+';assetSelection=new Set(["regular-one"]);');
  const current=s.run('bulkReviewSelected("selected")');assert.equal(s.writes.length,2);assert.equal(s.writes[1].options.headers['X-Studio-Privacy'],'regular');
  s.writes[0].reject(Error('Private late bulk canary'));await old;
  assert.equal(s.run('assetBulkReviewBusy'),true);assert.doesNotMatch(s.el('#assetBulkReviewStatus').textContent,/Private late/);
  s.writes[1].reject(Error('Regular unconfirmed'));await current;assert.equal(s.run('assetBulkReviewBusy'),false);
});
test('page privacy is part of query identity and old reads are aborted before accepting a new scope',async()=>{
  const s=setup({autoOpen:false});await change(s,'private');
  const query=s.run('assetPageQuery()');assert.match(query,/"privacy":"private"/);
  const pending=s.actualRefresh(true);assert.equal(s.reads.length,1);assert.match(s.reads[0].url,/privacy=private/);assert.equal(s.reads[0].options.headers['X-Studio-Privacy'],'private');
  await change(s,'regular','private');assert.equal(await pending,false);assert.equal(s.reads[0].options.signal.aborted,true);
  assert.notEqual(s.run('assetPageQuery()'),query);assert.equal(s.run('assetState.assets.length'),0);assert.equal(s.run('assetRefreshing'),false);
});
test('private collection edits in All retain and send their target classification',async()=>{
  const s=collections();s.run('window.StudioPrivacy={scope:()=>"all",creation:()=>"regular"};');
  s.run(fs.readFileSync(path.join(__dirname,'../app/static/collection-editor.js'),'utf8'));
  s.run('assetState.collections=[{id:"private-collection",privacy:"private",name:"Private shelf",description:"",revision:1}];openCollection("private-collection");');
  s.el('#collectionDescription').value='Private collection canary';s.el('#collectionDescription').emit('input');
  const pending=s.run('saveCollectionChange("save")');assert.equal(s.writes.length,1);
  assert.equal(s.writes[0].options.headers['X-Studio-Privacy'],'private');
  const regularKey='studio.collection-recovery/v1/'+W;assert.equal(s.storage.getItem(regularKey),null);
  assert.match(s.storage.getItem('studio.collection-recovery/v1/private/'+W),/Private collection canary/);
  s.writes[0].reject(Error('Synthetic response loss'));await pending;
});
test('a private collection draft survives a scope switch with unavailable session storage',()=>{
  const s=collections();s.run('window.view="private";window.StudioPrivacy={scope:()=>window.view,creation:()=>"private"};document.addEventListener=(name,fn)=>{if(name==="studio:privacy-change")globalThis.switchPrivacy=fn;};');
  s.run(fs.readFileSync(path.join(__dirname,'../app/static/collection-editor.js'),'utf8'));s.run('openCollection()');
  s.el('#collectionName').value='Unstored private collection';s.el('#collectionDescription').value='Private description canary';
  const write=s.storage.setItem;s.storage.setItem=()=>{throw Error('Synthetic quota');};
  s.el('#collectionDescription').emit('input');s.run('window.view="regular";switchPrivacy({detail:{previousScope:"private",scope:"regular"}});');
  assert.equal(s.el('#collectionDialog').open,false);assert.equal(s.el('#collectionDescription').value,'');assert.equal(s.storage.data.size,0);
  s.run('window.view="private";switchPrivacy({detail:{previousScope:"regular",scope:"private"}});');s.el('#recoverCollections').onclick();
  assert.equal(s.el('#collectionDialog').open,true);s.el('#restoreCollectionDraft').onclick();assert.equal(s.el('#collectionDescription').value,'Private description canary');assert.equal(s.writes.length,0);
  s.storage.setItem=write;s.el('#collectionDescription').emit('input');assert.equal(s.run('collectionUnstored.size'),0);
  assert.match(s.storage.getItem('studio.collection-recovery/v1/private/'+W),/Private description canary/);
});
