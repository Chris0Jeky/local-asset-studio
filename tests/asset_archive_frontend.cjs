'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs');
const {setup}=require('./asset_detail_contracts.cjs');
const Shelf=require('../app/static/asset-recovery-shelf.js');
function configured(options={}){const s=setup(options);s.el('#assetType').value='all';s.el('#assetSort').value='newest';s.el('#assetArchiveFilter').value='active';return s;}
function receipt(s,n,{noop=false,newer=null}={}){
  const c=s.payload(n),row=JSON.parse(s.run(`JSON.stringify(assetRecord(${JSON.stringify(c.ids[0])}))`));
  const applied=noop?{}:{archived_at:c.action==='archive'?0:null};
  return {status:'applied',workspace_id:c.workspace_id,request_id:c.request_id,updated:c.ids,action:c.action,
    revisions:Object.fromEntries(c.ids.map(id=>[id,c.expected_revisions[id]+(noop?0:1)])),applied,
    ...(noop?{unchanged:c.ids}:{}),current:[newer||{...row,...applied,metadata_revision:c.expected_revisions[row.id]+(noop?0:1)}]};
}
test('Archive view is independent of Trash, source and privacy, and retains off-page selection',()=>{
  const s=configured({autoOpen:false});s.run("assetState.assets[0].archived_at=0;assetSelection=new Set(['a','b']);");
  assert.equal(s.run('visibleAssets().map(a=>a.id).join()'),'b');
  s.el('#assetArchiveFilter').value='archived';s.el('#assetArchiveFilter').onchange();
  assert.equal(s.run('visibleAssets().map(a=>a.id).join()'),'a');
  assert.equal(s.run('assetPageFilters().archive'),'archived');
  assert.equal(s.run('[...assetSelection].join()'),'a,b');
  s.run("assetScope='trash';assetState.assets[0].trashed_at=123;assetActivePrivacy='private';");
  const f=JSON.parse(s.run('JSON.stringify(assetPageFilters())'));
  assert.equal(f.archive,'archived');assert.equal(f.visibility,'trash');assert.equal(f.privacy,'private');
  s.el('#assetArchiveFilter').value='all';assert.equal(s.run('assetPageFilters().archive'),'all');
  s.el('#assetArchiveFilter').value='active';assert.equal(s.run("Object.hasOwn(assetPageFilters(),'archive')"),false);
});
test('Ordinary detail opens initialize Archive labels from the current asset, not the previous button',async()=>{
  for(const archived of [0,77]){
    const s=configured({autoOpen:false});s.el('#assetArchive').textContent='Archive';
    s.run(`assetState.assets[0].archived_at=${archived};`);
    assert.equal(s.run('assetRetainedDetail'),null);
    for(const [id,label] of [['a','Return to active'],['b','Archive'],['a','Return to active']]){
      assert.equal(s.run(`openAsset('${id}')`),true);
      assert.equal(s.el('#assetArchive').textContent,label);
      assert.equal(s.run('assetRetainedDetail'),null,'opening alone must not create a draft');
      assert.equal(s.writes.length,0,'opening and switching must not mutate either asset');
      s.el('#closeAssetDialog').onclick();
    }
    s.run("openAsset('a')");const unarchive=s.el('#assetArchive').onclick();
    assert.equal(s.payload(0).action,'unarchive');s.writes[0].resolve(receipt(s,0));await unarchive;
    s.el('#closeAssetDialog').onclick();s.run("openAsset('b')");
    assert.equal(s.el('#assetArchive').textContent,'Archive');
    const archive=s.el('#assetArchive').onclick();assert.equal(s.payload(1).action,'archive');
    s.writes[1].resolve(receipt(s,1));await archive;
  }
});
test('Archiving preserves the open dirty draft, collection state and original request identity',async()=>{
  const s=configured();s.el('#assetNotes').value='unsaved before archive';s.el('#assetNotes').emit('input');
  const done=s.el('#assetArchive').onclick();assert.equal(s.writes.length,1);
  assert.equal(s.payload(0).action,'archive');assert.equal(s.payload(0).notes,undefined);
  assert.equal(s.el('#assetNotes').disabled,false);s.el('#assetNotes').value='newer while archiving';
  assert.equal(s.run("assetRecovery.read('detail').operation.kind"),'archive');
  assert.equal(s.run("assetRecovery.read('detail').operation.body"),s.writes[0].options.body);
  s.writes[0].resolve(receipt(s,0));await done;
  assert.equal(s.run('activeAsset.archived_at'),0);assert.equal(s.el('#assetDialog').open,true);
  assert.equal(s.run('assetDetailDirty()'),true);assert.equal(s.el('#assetNotes').value,'newer while archiving');
  assert.equal(s.run('visibleAssets().map(a=>a.id).join()'),'b');assert.match(s.el('#assetDetailStatus').textContent,/Archived.*unsaved/);
  assert.equal(s.el('#assetArchive').textContent,'Return to active');assert.equal(s.confirmations(),0);
  const restored=s.el('#assetArchive').onclick();assert.equal(s.payload(1).action,'unarchive');
  s.writes[1].resolve(receipt(s,1));await restored;
  assert.equal(s.run('activeAsset.archived_at'),null);assert.equal(s.run('assetDetailDirty()'),true);
  assert.equal(s.el('#assetArchive').textContent,'Archive');
});
test('Lost acknowledgement persists exact Archive bytes across reload and checks without replay',async()=>{
  const s=configured();s.el('#assetNotes').value='keep draft';const done=s.el('#assetArchive').onclick();
  assert.equal(s.writes.length,1);s.writes[0].reject(Error('response lost'));await done;
  const retained=s.run("JSON.stringify(assetRecovery.read('detail'))"),body=s.writes[0].options.body;
  assert.equal(JSON.parse(retained).operation.command.action,'archive');
  const t=configured({storage:s.storage});assert.equal(t.writes.length,0);assert.equal(t.el('#assetNotes').value,'keep draft');
  assert.equal(t.run('assetDetailPending.body'),body);assert.equal(t.el('#assetArchive').disabled,true);
  const check=t.run('checkAssetSave()');assert.equal(t.reads.length,1);
  t.reads[0].resolve(receipt(s,0));assert.equal(await check,true);assert.equal(t.writes.length,0);
  assert.equal(t.run('activeAsset.archived_at'),0);assert.equal(t.el('#assetNotes').value,'keep draft');
});
test('Archive no-ops retain revisions and mismatched timestamps do not clear recovery',async()=>{
  const s=configured();const done=s.run("writeAssetDetails({action:'unarchive'},'archive')");
  assert.equal(s.writes.length,1,'Archive action must be retainable before dispatch');s.writes[0].resolve(receipt(s,0,{noop:true}));assert.equal(await done,true);assert.equal(s.run('activeAsset.metadata_revision'),0);
  const attempt=s.el('#assetArchive').onclick(),bad=receipt(s,1);bad.applied.archived_at='0';s.writes[1].resolve(bad);await attempt;
  assert.equal(s.run('assetDetailPending.command.request_id'),s.payload(1).request_id);
  assert.equal(s.run('activeAsset.metadata_revision'),0);
});
test('A newer archive observation wins after conflict, without discarding local wording',async()=>{
  const s=configured();s.el('#assetNotes').value='local';const done=s.el('#assetFavorite').onclick();
  const newer={...s.receipt(0).current[0],metadata_revision:2,archived_at:77};
  s.writes[0].resolve({...s.receipt(0),current:[newer]});await done;
  assert.equal(s.run('!!assetDetailConflict'),true);s.run('resolveAssetConflict(true)');
  assert.equal(s.run('activeAsset.archived_at'),77);assert.equal(s.el('#assetArchive').textContent,'Return to active');
  const next=s.el('#assetArchive').onclick();assert.equal(s.payload(1).action,'unarchive');
  assert.equal(s.payload(1).expected_revisions.a,2);s.writes[1].resolve(receipt(s,1));await next;
  assert.equal(s.el('#assetNotes').value,'local');
});
test('Archive view preferences respect private storage ownership and untrusted restored options',()=>{
  const local={values:new Map(),getItem(k){return this.values.get(k)||null;},setItem(k,v){this.values.set(k,v);}},s=configured({localStorage:local});
  s.el('#assetArchiveFilter').value='archived';s.run('rememberAssetView()');assert.equal(local.getItem('studio.assets.archive'),'archived');
  s.run("assetActivePrivacy='private';assetViewRemembered='';");s.el('#assetArchiveFilter').value='all';s.run('rememberAssetView()');
  assert.equal(local.getItem('studio.assets.archive'),'archived');
  assert.equal(s.storage.values.get('studio.privacy.private.studio.assets.archive'),'all');
  s.el('#assetArchiveFilter').value='active';s.run('restoreAssetView()');assert.equal(s.el('#assetArchiveFilter').value,'all');
  s.storage.values.set('studio.privacy.private.studio.assets.archive','invalid');s.el('#assetArchiveFilter').value='active';s.run('restoreAssetView()');assert.equal(s.el('#assetArchiveFilter').value,'active');
});
test('Same-run inspection explicitly includes archived siblings',async()=>{
  const s=configured();s.run("assetPaging={catalogue:{},history:[]};assetSiblingPage={id:'a',items:[],next:null};");
  const done=s.run("loadAssetSiblings('load')");
  // Initial inspection uses the native owner; its URL must not inherit the default active-only filter.
  assert.equal(s.reads.length,1);assert.match(s.reads[0].url,/archive=all/);
  s.reads[0].reject(Error('synthetic bounded read failure'));await done;
});
test('Markup has distinct archive filter, detail and bulk controls, with no Trash conflation',()=>{
  const html=fs.readFileSync('app/static/index.html','utf8');
  assert.match(html,/<select[^>]*id="assetArchiveFilter"[^>]*aria-label="Archive state"/);
  assert.match(html,/id="assetArchive"[^>]*>Archive<\/button>/);
  assert.match(html,/data-bulk="archive"/);assert.match(html,/data-bulk="unarchive"/);
});
test('Archive checkpoint round-trips through the strict recovery shelf and lifecycle inspector',async()=>{
  const s=configured();s.el('#assetNotes').value='retained local wording';const done=s.el('#assetArchive').onclick();
  s.writes[0].reject(Error('response lost'));await done;
  const payload=JSON.parse(s.run("JSON.stringify(assetRecovery.read('detail'))"));
  assert.deepEqual(Shelf.project('detail',payload),payload);
  const Lens=require('../app/static/asset-recovery-lifecycle.js'),record={slot:'detail',payload};
  const value={format:'studio.asset-recovery-observation/v1',workspace_id:payload.workspace_id,observed_at:1,generation_submitted:false,collection:null,
    targets:[{id:'a',state:'active',title:'a',metadata_revision:1,archived_at:0,collection_count:0,collections:[],collections_limited:false}]};
  assert.equal(Lens.project(record,value,receipt(s,0)).targets[0].archived_at,0);
  for(const bad of ['0',true,{},-1,Infinity]){
    value.targets[0].archived_at=bad;assert.throws(()=>Lens.project(record,value,receipt(s,0)));
  }
  value.targets[0].archived_at=null;assert.equal(Lens.project(record,value,receipt(s,0)).targets[0].archived_at,null);
});
test('Archived cards, selection and empty views explain organization without implying deletion',()=>{
  const s=configured({autoOpen:false});s.run("assetState.assets[0].archived_at=0;assetSelection=new Set(['a','b']);");
  assert.match(s.run("assetCardHTML(assetRecord('a'))"),/>Archived</);
  s.run('renderAssets()');assert.match(s.el('#assetSelectedList').innerHTML,/Archived/);
  s.el('#assetArchiveFilter').value='archived';s.run('assetState.assets=[];renderAssets()');
  assert.match(s.el('#assetGrid').innerHTML,/No archived assets/);
  s.el('#assetArchiveFilter').value='active';s.run("assetSourceMode='all';assetPaging={query:assetPageQuery(),history:[],unavailable:[],collectionNext:null};renderAssets()");
  assert.match(s.el('#assetGrid').innerHTML,/No active assets/);assert.match(s.el('#assetGrid').innerHTML,/data-asset-archive-view="all"/);
});
test('Off-page Archive confirmation is explicit and cancelling preserves all selection',async()=>{
  const s=configured({autoOpen:false});s.run("assetState.assets[0].archived_at=0;assetSelection=new Set(['a','b']);");
  s.run('window.confirm=text=>{window.lastArchivePrompt=text;return false;}');
  assert.equal(s.run("assetSelectionCanProceed('archive')"),false);
  assert.match(s.run('window.lastArchivePrompt'),/^Archive will include 1 selected asset outside this view/);
  assert.equal(s.run('[...assetSelection].join()'),'a,b');assert.equal(s.writes.length,0);
});

test('Negative Archive timestamps are refused by receipts, metadata and retained recovery',async()=>{
  const s=configured();const done=s.el('#assetArchive').onclick(),bad=receipt(s,0);
  bad.applied.archived_at=-1;s.writes[0].resolve(bad);await done;
  assert.equal(s.run('!!assetDetailPending'),true,'invalid reply must keep the exact pending command');
  const row=JSON.parse(s.run('JSON.stringify(activeAsset)'));row.archived_at=-1;
  assert.equal(s.run('validAssetMetadata('+JSON.stringify(row)+')'),false);
  const payload=JSON.parse(s.run("JSON.stringify(assetRecovery.read('detail'))"));payload.metadata.archived_at=-1;
  assert.throws(()=>Shelf.project('detail',payload));
});
