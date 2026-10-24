// Bounded Library reads using the shipped script and controllable I/O.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const scope='1'.repeat(32),stamp={epoch:'a'.repeat(32),revision:1};
const asset=(id,extra={})=>({id,workspace_id:scope,title:id,notes:'notes',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:1,metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,...extra});
const page=(assets,next=null)=>({format:'studio.asset-page/v1',workspace_id:scope,catalogue:stamp,assets,next_cursor:next,observation_only:true});
const collections=(items=[],next=null)=>({format:'studio.collection-page/v1',workspace_id:scope,catalogue:stamp,collections:items,next_cursor:next,observation_only:true});
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
function init(){const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';s.run('refreshAssets='+s.actualRefresh.toString());return s;}
async function refresh(s,assets,next=null,cols=collections()){
  const n=s.reads.length,p=s.actualRefresh(true);await flush();
  assert.match(s.reads[n].url,/^\/api\/assets\/page\?/);assert.match(s.reads[n+1].url,/^\/api\/collections\?/);
  assert.ok(!s.reads.some(r=>r.url==='/api/workspace'),'Library must not fetch a snapshot');
  s.reads[n].resolve(page(assets,next));s.reads[n+1].resolve(cols);return p;
}
let passed=0;
async function test(name,fn){await fn();console.log('PASS',name);passed++;}
(async()=>{
  await test('Refresh reads one bounded asset page and one collection page',async()=>{
    const s=init();assert.equal(await refresh(s,[asset('a')],'next'),true);
    assert.equal(s.reads.length,2);assert.equal(s.writes.length,0);assert.equal(s.run('assetState.assets.length'),1);
    assert.match(s.el('#assetPaging').innerHTML,/Next page/);assert.match(s.el('#assetVisibleCount').textContent,/page/i);
  });
  await test('Search is debounced, queries the server and resets paging',async()=>{
    const s=init();await refresh(s,[asset('first')],'next');
    s.run("assetPaging.cursor='old';assetPaging.history=[null]");
    s.el('#assetSearch').value='off-page %_';s.el('#assetSearch').oninput();
    s.el('#assetSearch').value='off-page %_ needle';s.el('#assetSearch').oninput();
    s.run('renderAssets()');assert.equal(s.reads.length,2,'repaints must respect the pending debounce');
    const n=s.reads.length;assert.equal(s.timers.size,1);assert.equal(n,2);
    const fn=[...s.timers.values()][0];s.timers.clear();fn();await flush();
    assert.equal(s.reads.length,n+2,'debounced search must request a new server page');
    const query=new URL(s.reads[n].url,'http://fixture').searchParams;
    assert.equal(query.get('q'),'off-page %_ needle');assert.equal(query.get('sort'),'newest');assert.equal(query.has('cursor'),false);
    s.reads[n].resolve(page([asset('found',{title:'off-page %_ needle'})]));s.reads[n+1].resolve(collections());await flush();
    assert.equal(s.run('assetPaging.history.length'),0);assert.equal(s.run('visibleAssets()[0].id'),'found');
    assert.doesNotMatch(s.el('#assetVisibleCount').textContent,/search, sort/);
  });
  await test('Sort queries the server, resets paging and preserves the server order',async()=>{
    const s=init();await refresh(s,[asset('first')],'next');s.run("assetPaging.cursor='old';assetPaging.history=[null]");
    s.el('#assetSort').value='title';const n=s.reads.length;s.el('#assetSort').onchange();await flush();
    const query=new URL(s.reads[n].url,'http://fixture').searchParams;
    assert.equal(query.get('sort'),'title');assert.equal(query.has('cursor'),false);assert.equal(query.has('q'),false);
    s.reads[n].resolve(page([asset('a',{title:'same'}),asset('b',{title:'same'})]));s.reads[n+1].resolve(collections());await flush();
    assert.equal(s.run('assetPaging.history.length'),0);assert.deepEqual(JSON.parse(s.run('JSON.stringify(visibleAssets().map(a=>a.id))')),['a','b']);
  });
  await test('A sort change during an in-flight read discards the old response and requests the latest query',async()=>{
    const s=init();await refresh(s,[asset('first')],'next');const n=s.reads.length,p=s.actualRefresh(true);await flush();
    s.el('#assetSort').value='oldest';s.el('#assetSort').onchange();assert.equal(s.reads.length,n+2);
    s.reads[n].resolve(page([asset('stale')]));s.reads[n+1].resolve(collections());assert.equal(await p,false);await flush();
    assert.equal(s.run('assetState.assets[0].id'),'first');assert.equal(s.reads.length,n+4);
    const query=new URL(s.reads[n+2].url,'http://fixture').searchParams;assert.equal(query.get('sort'),'oldest');assert.equal(query.has('cursor'),false);
    s.reads[n+2].resolve(page([asset('oldest')]));s.reads[n+3].resolve(collections());await flush();assert.equal(s.run('assetState.assets[0].id'),'oldest');
  });
  await test('Off-page is unresolved, never missing; explicit selection observation distinguishes Trash and deletion',async()=>{
    const s=init();await refresh(s,[asset('a')],'next');
    s.run("assetSelection=new Set(['old','gone']);renderAssets()");
    assert.equal(s.run('assetSelectionInfo().missing'),0);assert.equal(s.run('assetSelectionInfo().unresolved'),2);
    const p=s.run('resolveAssetSelection()');await flush();
    assert.equal(s.writes.length,1);assert.equal(s.writes[0].url,'/api/assets/selection');
    const body=JSON.parse(s.writes[0].options.body);assert.deepEqual(body.ids,['old','gone']);assert.equal(body.workspace_id,scope);
    s.writes[0].resolve({workspace_id:scope,catalogue:stamp,items:[{id:'old',state:'trashed',asset:asset('old',{trashed_at:0})},{id:'gone',state:'missing',asset:null}]});
    assert.equal(await p,true);assert.equal(s.run('assetSelectionInfo().missing'),1);assert.equal(s.run('assetSelectionInfo().unresolved'),0);
    assert.match(s.el('#assetSelectedList').innerHTML,/In Trash/);assert.match(s.el('#assetSelectedList').innerHTML,/Unavailable/);
    assert.equal(s.run('assetState.assets.length'),1,'resolved selection must not become grid rows');
  });
  await test('Opening an off-page detail resolves exactly that ID and leaves drafts untouched on late results',async()=>{
    const s=init();await refresh(s,[asset('a')],'next');
    const p=s.run("openAsset('old')");await flush();assert.equal(s.writes[0].url,'/api/assets/selection');
    s.writes[0].resolve({workspace_id:scope,catalogue:stamp,items:[{id:'old',state:'active',asset:asset('old')}]});await p;
    assert.equal(s.run('activeAsset.id'),'old');assert.equal(s.el('#assetNotes').value,'notes');
    s.el('#assetNotes').value='draft';const late=s.run("openAsset('another')");await flush();
    if(s.writes[1])s.writes[1].resolve({workspace_id:scope,catalogue:stamp,items:[{id:'another',state:'active',asset:asset('another')}]});
    await late;assert.equal(s.run('activeAsset.id'),'old');assert.equal(s.el('#assetNotes').value,'draft');
  });
  await test('A mixed Workspace refresh cannot replace the Library or retained selection',async()=>{
    const s=init();s.run("assetSelection=new Set(['a'])");const n=s.reads.length,p=s.actualRefresh(true);await flush();
    s.reads[n].resolve(page([asset('new')]));s.reads[n+1].resolve({...collections(),workspace_id:'b'.repeat(32)});
    assert.equal(await p,false);assert.equal(s.run('assetSelection.has("a")'),true);assert.equal(s.run('assetState.assets[0].id'),'a');
  });
  await test('Next and previous pages are explicit and retain selected IDs',async()=>{
    const s=init();await refresh(s,[asset('first')],'cursor-two');s.run("assetSelection=new Set(['first'])");
    const n=s.reads.length,p=s.run('moveAssetPage(true)');await flush();
    assert.match(s.reads[n].url,/cursor=cursor-two/);assert.equal(s.reads.length,n+2,'continuations must not auto-drain');
    s.reads[n].resolve(page([asset('second')],'cursor-three'));s.reads[n+1].resolve(collections());assert.equal(await p,true);
    assert.equal(s.run('assetSelection.has("first")'),true);assert.equal(s.run('assetSelectionInfo().unresolved'),1);assert.equal(s.run('assetSelectionInfo().missing'),0);
    assert.match(s.el('#assetPaging').innerHTML,/Page 2/);
    const before=s.reads.length,back=s.run('moveAssetPage(false)');await flush();assert.doesNotMatch(s.reads[before].url,/cursor=/);
    s.reads[before].resolve(page([asset('first')],'cursor-two'));s.reads[before+1].resolve(collections());assert.equal(await back,true);
    assert.equal(s.run('assetSelectionInfo().visible'),1);assert.match(s.el('#assetPaging').innerHTML,/Page 1/);
  });
  await test('A stale continuation keeps its page and stops without retries',async()=>{
    const s=init();await refresh(s,[asset('first')],'stale');
    const n=s.reads.length,p=s.run('moveAssetPage(true)');await flush();
    s.reads[n].reject(Object.assign(Error('Catalogue changed; refresh'),{status:409,data:{code:'asset_cursor_stale'}}));s.reads[n+1].resolve(collections());
    assert.equal(await p,false);await flush();assert.equal(s.reads.length,n+2);assert.equal(s.run('assetState.assets[0].id'),'first');assert.equal(s.run('assetPaging.cursor'),null);
  });
  await test('More collections uses one bound cursor and feeds the sidebar and destinations',async()=>{
    const s=init();await refresh(s,[asset('a')],null,collections([{id:'c1',name:'One',revision:1,count:0}],'more'));
    const n=s.reads.length,p=s.run('moreAssetCollections()');await flush();assert.match(s.reads[n].url,/cursor=more/);assert.equal(s.reads.length,n+1);
    s.reads[n].resolve(collections([{id:'c2',name:'Two',revision:1,count:0}]));assert.equal(await p,true);
    assert.match(s.el('#assetCollections').innerHTML,/Two/);assert.match(s.el('#bulkCollection').innerHTML,/Two/);assert.equal(s.el('#collectionPaging').innerHTML,'');
  });
  await test('Foreign and late ID observations cannot replace an editor or authorize writes',async()=>{
    const s=init();await refresh(s,[asset('a')]);
    const n=s.writes.length,p=s.run("openAsset('off')");await flush();s.run("assetState.workspace_id='b'.repeat(32);observeAssetWorkspaceIdentity()");
    s.writes[n].resolve({workspace_id:scope,items:[{id:'off',state:'active',asset:asset('off')}]});assert.equal(await p,false);
    assert.equal(s.el('#assetDialog').open,false);assert.equal(s.run('assetResolved.has("off")'),false);
  });
  await test('An off-page restored selection owns its original IDs, Workspace and expected revisions',async()=>{
    const s=init();await refresh(s,[asset('page')]);s.run("assetSelection=new Set(['old'])");
    const resolve=s.run('resolveAssetSelection()');await flush();
    s.writes[0].resolve({workspace_id:scope,items:[{id:'old',state:'trashed',asset:asset('old',{trashed_at:0,metadata_revision:7})}]});assert.equal(await resolve,true);
    const restore=s.run("mutateAssets({ids:['old'],action:'restore'})");await flush();
    const command=JSON.parse(s.writes[1].options.body);assert.deepEqual(command.ids,['old']);assert.equal(command.workspace_id,scope);assert.deepEqual(command.expected_revisions,{old:7});
    s.run("assetSelection=new Set(['page'])");s.writes[1].reject(Error('lost response'));await assert.rejects(restore);
    const retained=JSON.parse(s.storage.getItem('studio.asset-recovery.v1.library')||s.run("JSON.stringify(assetRecovery.read('library'))"));
    assert.equal(retained.operation.body,s.writes[1].options.body);assert.deepEqual(retained.selection,['old']);
    assert.equal(s.run('assetLibraryPending.body'),s.writes[1].options.body);assert.equal(s.run('assetLibraryPending.selection[0]'),'old');assert.equal(s.run('assetSelection.has("page")'),true);
  });
  await test('An unchanged read keeps resolved off-page IDs; a changed catalogue invalidates them',async()=>{
    const s=init();await refresh(s,[asset('a')],'next');s.run("assetSelection=new Set(['old'])");
    const p=s.run('resolveAssetSelection()');await flush();
    s.writes[0].resolve({workspace_id:scope,catalogue:stamp,items:[{id:'old',state:'active',asset:asset('old',{metadata_revision:3})}]});assert.equal(await p,true);
    assert.equal(await refresh(s,[asset('a')],'next'),true);
    assert.equal(s.run('assetResolved.has("old")'),true);assert.equal(s.run('assetSelectionInfo().unresolved'),0);
    const n=s.reads.length,q=s.actualRefresh(true);await flush();const changed={...stamp,revision:2};
    s.reads[n].resolve({...page([asset('a')],'next'),catalogue:changed});s.reads[n+1].resolve({...collections(),catalogue:changed});assert.equal(await q,true);
    assert.equal(s.run('assetResolved.has("old")'),false);assert.equal(s.run('assetSelectionInfo().unresolved'),1);
  });
  await test('A stale replayed cursor on a non-forced read falls back to page 1 with a notice; an explicit page move still stops',async()=>{
    const s=init();await refresh(s,[asset('first')],'next');s.run("assetPaging.cursor='old';assetPaging.history=[null]");
    const n=s.reads.length,p=s.actualRefresh();await flush();assert.match(s.reads[n].url,/cursor=old/);
    s.reads[n].reject(Object.assign(Error('Catalogue changed; refresh'),{status:409,data:{code:'asset_cursor_stale'}}));s.reads[n+1].resolve(collections());await flush();
    assert.equal(s.reads.length,n+4,'one retry, with both reads');assert.doesNotMatch(s.reads[n+2].url,/cursor=/);
    s.reads[n+2].resolve(page([asset('fresh')],'next'));s.reads[n+3].resolve(collections());
    assert.equal(await p,true);assert.equal(s.run('assetState.assets[0].id'),'fresh');assert.equal(s.run('assetPaging.cursor'),null);assert.equal(s.run('assetPaging.history.length'),0);
    assert.match(s.el('#assetMessage').textContent,/page 1 again/);assert.doesNotMatch(s.el('#assetMessage').textContent,/Catalogue changed/);
  });
  console.log('Workspace pagination contracts passed:',passed);
})().catch(error=>{console.error(error);process.exitCode=1;});
