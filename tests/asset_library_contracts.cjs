// Exercise the shipped library projection and selection policy; no inference or storage writes.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
function library(count=3){
  const s=setup({autoOpen:false});
  s.el('#assetType').value='all';s.el('#assetSort').value='newest';
  s.run(`assetState.assets=Array.from({length:${count}},(_,i)=>({id:'a'+i,workspace_id:assetState.workspace_id,title:'Asset '+i,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:i,url:'/fixture.png',collections:[],metadata_revision:0,source:{},lineage:[],bytes:1}));renderAssets();`);
  return s;
}
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log('PASS',name);}catch(e){failed++;console.error('FAIL',name,'\n',e.message);}}
(async()=>{
  await test('Hidden selection is counted without silently changing its IDs',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1']);");s.el('#assetSearch').value='Asset 0';s.run('renderAssets()');
    assert.match(s.el('#assetSelectionSummary').textContent,/1 visible.*1 outside/i);assert.equal(s.run('assetSelection.size'),2);
  });
  await test('A filter miss in populated Trash is not an empty Trash claim',()=>{
    const s=library();s.run("assetState.assets[0].trashed_at=10;assetScope='trash';");s.el('#assetSearch').value='nothing matches';s.run('renderAssets()');
    assert.match(s.el('#assetGrid').innerHTML,/No matching assets/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/Trash is empty/);
  });
  await test('Empty Favorites explains the scope and offers All assets',()=>{
    const s=library();s.run("setAssetScope('favorite')");assert.match(s.el('#assetGrid').innerHTML,/No favorites yet/);assert.match(s.el('#assetGrid').innerHTML,/data-scope="all"/);
  });
  await test('An empty collection is distinct from an unavailable collection',()=>{
    const s=library();s.run("assetState.collections=[{id:'empty',name:'Empty project',count:0}];setAssetScope('collection:empty')");
    assert.match(s.el('#assetGrid').innerHTML,/This collection has no assets/);s.run("assetState.collections=[];renderAssets()");assert.match(s.el('#assetGrid').innerHTML,/Collection unavailable/);
  });
  await test('The visible selection limit is disclosed before and after selecting',()=>{
    const s=library(205);assert.match(s.el('#selectVisible').textContent,/200.*205/);s.el('#selectVisible').onclick();assert.equal(s.run('assetSelection.size'),200);assert.match(s.el('#assetMessage').textContent,/200.*205/);
  });
  await test('Filtered counts distinguish matches from total in scope',()=>{
    const s=library();s.el('#assetSearch').value='Asset 0';s.run('renderAssets()');assert.match(s.el('#assetVisibleCount').textContent,/1 of 3/);
  });
  await test('Filter reset preserves sort, selection, editor and pending-command bytes',()=>{
    const s=library();s.run("assetSelection=new Set(['a0']);openAsset('a0');assetLibraryPending={body:'exact original bytes'};");s.el('#assetNotes').value='my unsaved notes';s.el('#assetType').value='video';s.el('#assetSearch').value='nope';s.el('#assetSort').value='title';
    assert.equal(typeof s.el('#clearAssetFilters').onclick,'function');s.el('#clearAssetFilters').onclick();assert.equal(s.el('#assetSearch').value,'');assert.equal(s.el('#assetType').value,'all');assert.equal(s.el('#assetSort').value,'title');assert.equal(s.run('assetSelection.size'),1);assert.equal(s.el('#assetNotes').value,'my unsaved notes');assert.equal(s.run('assetLibraryPending.body'),'exact original bytes');assert.equal(s.writes.length,0);
  });
  await test('Selection review labels unavailable and trashed records and escapes titles',()=>{
    const s=library();s.run(`assetState.assets[0].title='<img src=x onerror=alert(1)>';assetState.assets[0].trashed_at=10;assetSelection=new Set(['a0','gone']);renderAssets();`);
    assert.match(s.el('#assetSelectedList').innerHTML,/In Trash/);assert.match(s.el('#assetSelectedList').innerHTML,/Unavailable/);assert.match(s.el('#assetSelectedList').innerHTML,/&lt;img/);assert.doesNotMatch(s.el('#assetSelectedList').innerHTML,/<img/);
  });
  await test('Keeping only visible IDs never rewrites an unconfirmed command',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1','gone']);assetLibraryPending={body:'do not replace',selection:['a0','a1']};");s.el('#assetSearch').value='Asset 0';
    assert.equal(typeof s.el('#keepVisibleSelection').onclick,'function');s.el('#keepVisibleSelection').onclick();assert.equal(s.run("JSON.stringify([...assetSelection])"),'["a0"]');assert.equal(s.run('assetLibraryPending.body'),'do not replace');assert.equal(s.run('assetLibraryPending.selection.length'),2);assert.equal(s.writes.length,0);
  });
  await test('Hidden selection requires consent; visible-only action does not',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1']);");s.el('#assetSearch').value='Asset 0';assert.equal(s.run('typeof assetSelectionCanProceed'),'function');
    assert.equal(s.run("assetSelectionCanProceed('trash')"),false);assert.equal(s.confirmations(),1);s.approve(true);assert.equal(s.run("assetSelectionCanProceed('trash')"),true);s.el('#assetSearch').value='';assert.equal(s.run("assetSelectionCanProceed('trash')"),true);assert.equal(s.confirmations(),2);
  });
  await test('Unavailable and oversized selections are refused without losing IDs',()=>{
    const s=library(201);assert.equal(s.run('typeof assetSelectionCanProceed'),'function');s.run("assetSelection=new Set(['gone'])");assert.equal(s.run("assetSelectionCanProceed('export')"),false);assert.equal(s.run('assetSelection.size'),1);
    s.run('assetSelection=new Set(assetState.assets.map(a=>a.id))');assert.equal(s.run("assetSelectionCanProceed('favorite')"),false);assert.equal(s.run('assetSelection.size'),201);assert.equal(s.confirmations(),0);
  });
  await test('Keeper review scope is not confused with checkbox selection',()=>{
    const s=library();s.run("assetSelection.add('a0');setAssetScope('selected')");assert.equal(s.el('#assetScopeTitle').textContent,'Keepers');assert.match(s.el('#assetGrid').innerHTML,/No keepers yet/);assert.equal(s.run('assetSelection.size'),0);
  });
  await test('All assets empty because every original is in Trash offers recovery',()=>{
    const s=library();s.run('for(const asset of assetState.assets)asset.trashed_at=10;renderAssets();');assert.match(s.el('#assetGrid').innerHTML,/Your assets are in Trash/);assert.match(s.el('#assetGrid').innerHTML,/data-scope="trash"/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/library is empty/);
  });
  await test('Awaiting review has its own scope count and empty-state explanation',()=>{
    const s=library();s.run("assetState.assets[0].review='selected';setAssetScope('unreviewed')");s.el('#assetSearch').value='no match';s.run('renderAssets()');assert.match(s.el('#assetVisibleCount').textContent,/0 of 2/);s.run("for(const a of assetState.assets)a.review='selected';renderAssets()");assert.match(s.el('#assetGrid').innerHTML,/No assets awaiting review/);
  });
  const sourced=(options={})=>{
    const s=setup({autoOpen:false,...options});s.el('#assetType').value='all';s.el('#assetSort').value='newest';
    s.run(`assetState.assets=[['m0',null,1],['m1',null,2],['g0','lab p71 · G16',3],['g1','lab p71 · G16',4]].map(([id,label,at])=>({id,workspace_id:assetState.workspace_id,title:'Anima · 1',preset_name:'Anima',output_index:0,prompt_excerpt:'prompt of '+id,run_label:label,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:at,url:'/fixture.png',collections:[],metadata_revision:0,source:{},lineage:[],bytes:1,filename:'f.png',sha256:'a'}));renderAssets();`);
    return s;
  };
  const shown=s=>JSON.parse(s.run('JSON.stringify(visibleAssets().map(a=>a.id))'));
  const memory=()=>({values:new Map(),getItem(key){return this.values.get(key)??null;},setItem(key,value){this.values.set(key,String(value));}});
  await test('Without labelled assets every source is shown and the source filter stays hidden',()=>{
    const s=library();assert.equal(s.run('assetSource()'),'all');assert.equal(s.el('#assetSource').hidden,true);assert.equal(s.run('visibleAssets().length'),3);assert.doesNotMatch(s.el('#assetVisibleCount').textContent,/hidden/);
  });
  await test('Labelled assets default the library and Review next to Mine',()=>{
    const s=sourced();assert.equal(s.el('#assetSource').hidden,false);assert.equal(s.el('#assetSource').value,'mine');assert.deepEqual(shown(s),['m1','m0']);
    assert.match(s.el('#assetVisibleCount').textContent,/^2 assets · 2 agent runs hidden$/);assert.match(s.el('#reviewNext').textContent,/2 unreviewed/);
    s.run('startReviewQueue()');assert.equal(s.run('JSON.stringify(assetQueue.ids)'),'["m1","m0"]');
  });
  await test('The source choice persists like grouping and survives a missing store',()=>{
    const store=memory();let s=sourced({localStorage:store});s.el('#assetSource').value='agent';s.el('#assetSource').onchange();
    assert.deepEqual(shown(s),['g1','g0']);assert.equal(store.values.get('studio.assets.source'),'agent');assert.match(s.el('#assetVisibleCount').textContent,/2 of yours hidden/);
    s=sourced({localStorage:store});assert.equal(s.run('assetSource()'),'agent');assert.deepEqual(shown(s),['g1','g0']);
    s.run("chooseAssetSource('all')");assert.equal(shown(s).length,4);assert.equal(store.values.get('studio.assets.source'),'all');
    s.el('#assetSearch').value='p71';s.run('renderAssets()');assert.deepEqual(shown(s),['g1','g0']);
    s=sourced();s.run("chooseAssetSource('agent')");assert.deepEqual(shown(s),['g1','g0']);
  });
  await test('A source filter that hides the whole view offers every source in one click',()=>{
    const s=sourced();s.run('assetState.assets=assetState.assets.filter(a=>a.run_label);renderAssets()');
    assert.match(s.el('#assetGrid').innerHTML,/None of your own runs here/);assert.match(s.el('#assetGrid').innerHTML,/data-asset-source="all"/);
    s.run("chooseAssetSource('all')");assert.deepEqual(shown(s),['g1','g0']);
  });
  await test('Default titles carry the prompt excerpt; renamed titles and markup do not leak',()=>{
    const s=sourced();s.run("chooseAssetSource('all')");let html=s.el('#assetGrid').innerHTML;
    assert.match(html,/class="asset-card-prompt"[^>]*>prompt of m0</);assert.match(html,/class="asset-run-label"[^>]*>lab p71 · G16</);
    s.run("assetState.assets[0].title='My knight';assetState.assets[1].prompt_excerpt='<b>x</b>';assetState.assets[2].run_label='<i>';renderAssets()");html=s.el('#assetGrid').innerHTML;
    assert.doesNotMatch(html,/prompt of m0/);assert.match(html,/&lt;b&gt;x&lt;\/b&gt;/);assert.doesNotMatch(html,/<b>x|<i>/);
  });
  await test('The review dialog shows the prompt text and run label',()=>{
    const s=sourced();s.run("chooseAssetSource('all');openAsset('g0')");const html=s.el('#assetDetails').innerHTML;
    assert.match(html,/Prompt text: prompt of g0/);assert.match(html,/Run label: lab p71 · G16/);
    s.run("openAsset('m0')");assert.doesNotMatch(s.el('#assetDetails').innerHTML,/Run label/);
  });
  // Selection ergonomics and view persistence (#939). Events go through the script's own document listeners.
  const selected=s=>JSON.parse(s.run('JSON.stringify([...assetSelection].sort())'));
  const tick=(s,id,{shift=false,checked=true}={})=>{const target={dataset:{assetCheck:id},checked,closest:q=>q==='.asset-card'?{classList:{toggle(){}}}:null};s.dispatch('click',{target,shiftKey:shift});s.dispatch('change',{target});return target;};
  const key=(s,k,{ctrl=false,meta=false,target={tagName:'INPUT',type:'checkbox',inGrid:true}}={})=>{const e={key:k,target,ctrlKey:ctrl,metaKey:meta,shiftKey:false,altKey:false,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};s.dispatch('keydown',e);return e;};
  const gridded=(count=3)=>{const s=library(count);s.el('#assetGrid').contains=node=>!!node?.inGrid;return s;};
  await test('Shift-click selects, then deselects, the range from the last clicked checkbox',()=>{
    const s=library(6);
    tick(s,'a4');tick(s,'a1',{shift:true});
    assert.deepEqual(selected(s),['a1','a2','a3','a4']);assert.match(s.el('#assetMessage').textContent,/Selected 4 assets in a range\. 4 selected/);
    tick(s,'a2',{shift:true,checked:false});assert.deepEqual(selected(s),['a3','a4']);
    // An anchor outside the view is not a range start: the click is an ordinary toggle.
    s.el('#assetSearch').value='Asset 5';s.run('renderAssets()');tick(s,'a5',{shift:true});
    assert.deepEqual(selected(s),['a3','a4','a5']);
  });
  await test('A Shift range follows the grouped grid order the operator sees',()=>{
    const s=library(4);s.run("assetState.assets.forEach((a,i)=>{a.preset_name=i%2?'Y':'X';});assetGroupMode='recipe';renderAssets()");
    assert.deepEqual(JSON.parse(s.run('JSON.stringify(assetVisibleOrder().map(a=>a.id))')),['a3','a1','a2','a0']);
    tick(s,'a3');tick(s,'a2',{shift:true});assert.deepEqual(selected(s),['a1','a2','a3']);
  });
  await test('A Shift range over the per-action limit changes nothing and says why',()=>{
    const s=library(205);tick(s,'a204');const box=tick(s,'a0',{shift:true});
    assert.equal(box.checked,false);assert.deepEqual(selected(s),['a204']);
    assert.match(s.el('#assetMessage').textContent,/would add 204 assets to the 1 already selected, over the limit of 200 per action\. Your selection is unchanged/);
  });
  await test('Ctrl/Cmd+A in the grid selects visible; Escape clears; text fields and open dialogs keep their keys',()=>{
    const s=gridded();
    let e=key(s,'a',{ctrl:true,target:{tagName:'INPUT',type:'search',inGrid:true}});assert.equal(e.defaultPrevented,false);assert.equal(s.run('assetSelection.size'),0);
    e=key(s,'a',{ctrl:true,target:{tagName:'BUTTON',inGrid:false}});assert.equal(e.defaultPrevented,false);assert.equal(s.run('assetSelection.size'),0);
    e=key(s,'A',{meta:true});assert.equal(e.defaultPrevented,true);assert.deepEqual(selected(s),['a0','a1','a2']);assert.match(s.el('#assetMessage').textContent,/Selected 3 visible assets/);
    s.run("document.querySelector=q=>q==='dialog[open]'?{}:null");
    e=key(s,'Escape');assert.equal(e.defaultPrevented,false);assert.equal(s.run('assetSelection.size'),3);
    s.run('document.querySelector=()=>null');
    e=key(s,'Escape',{target:{tagName:'BUTTON',inGrid:true}});assert.equal(e.defaultPrevented,true);assert.equal(s.run('assetSelection.size'),0);
    assert.match(s.el('#assetMessage').textContent,/^Selection cleared \(3\)/);
    e=key(s,'Escape');assert.equal(e.defaultPrevented,false);
  });
  await test('Select visible and scope changes report what they replace or clear',()=>{
    const s=library();s.run("assetSelection=new Set(['gone','a0'])");s.el('#selectVisible').onclick();
    assert.match(s.el('#assetMessage').textContent,/Selected 3 visible assets\. Replaced an earlier selection: 1 asset is no longer selected/);
    s.run("setAssetScope('trash')");assert.equal(s.el('#assetMessage').textContent,'Trash is recoverable. Original files and recipes remain on disk. Selection cleared (3).');
    s.run("setAssetScope('all')");assert.equal(s.el('#assetMessage').textContent,'');
    s.run("assetSelection=new Set(['a0','a1'])");s.el('#clearAssetSelection').onclick();assert.match(s.el('#assetMessage').textContent,/Selection cleared \(2\)/);
  });
  const withCollections=(options)=>{const s=setup({autoOpen:false,...options});s.run(`assetState.assets=Array.from({length:3},(_,i)=>({id:'a'+i,workspace_id:assetState.workspace_id,title:'Asset '+i,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:i,url:'/fixture.png',collections:i?[]:['c1'],metadata_revision:0,source:{},lineage:[],bytes:1}));`);return s;};
  await test('Scope, sort and media type persist; search persists for the tab; bad stored values are ignored',()=>{
    const store=memory(),s=withCollections({localStorage:store});
    s.run("assetState.collections=[{id:'c1',name:'Project',count:1}]");s.el('#assetSort').value='title';s.el('#assetType').value='image';s.el('#assetSearch').value='Asset';s.run("setAssetScope('collection:c1')");
    assert.deepEqual(['scope','sort','type'].map(k=>store.values.get('studio.assets.'+k)),['collection:c1','title','image']);assert.equal(s.storage.values.get('studio.assets.search'),'Asset');
    const reloaded=withCollections({localStorage:store,storage:s.storage});
    assert.equal(reloaded.el('#assetSort').value,'title');assert.equal(reloaded.el('#assetType').value,'image');assert.equal(reloaded.el('#assetSearch').value,'Asset');
    reloaded.run("assetState.collections=[{id:'c1',name:'Project',count:1}];renderAssets()");assert.equal(reloaded.run('assetScope'),'collection:c1');assert.equal(reloaded.run('visibleAssets().length'),1);
    // A remembered collection that was deleted meanwhile opens All assets on the first loaded render.
    const gone=withCollections({localStorage:store});gone.run('renderAssets()');assert.equal(gone.run('assetScope'),'all');assert.equal(store.values.get('studio.assets.scope'),'all');
    for(const [k,v] of [['scope','collection:bad id!'],['sort','random'],['type','<svg>']])store.setItem('studio.assets.'+k,v);
    const bad=withCollections({localStorage:store});assert.equal(bad.run('assetScope'),'all');assert.equal(bad.el('#assetSort').value,'');assert.equal(bad.el('#assetType').value,'');
    // No storage at all still opens the library.
    const none=withCollections();none.run("renderAssets()");assert.equal(none.run('assetScope'),'all');
  });
  const bulkClick=(s,action)=>s.dispatch('click',{target:{closest:q=>q==='[data-bulk]'||q==='[data-bulk],#createScene,#nativeExport'?{dataset:{bulk:action},getAttribute:()=>null}:null}});
  await test('Mark as agent run labels the selection in one revisioned command and the Mine view then hides it',async()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a2'])");
    const p=bulkClick(s,'agent_run');assert.equal(s.writes.length,1);
    assert.deepEqual(s.metadata(0),{ids:['a0','a2'],action:'edit',run_label:'Agent lab'});assert.deepEqual(s.payload(0).expected_revisions,{a0:0,a2:0});
    s.accept(0);await p;
    assert.deepEqual(JSON.parse(s.run("JSON.stringify(assetState.assets.map(a=>a.run_label??null))")),['Agent lab',null,'Agent lab']);
    assert.equal(s.run('assetSelection.size'),0);assert.equal(s.el('#assetSource').hidden,false);assert.deepEqual(shown(s),['a1']);
    assert.match(s.el('#assetMessage').textContent,/^Marked 2 as agent runs \(Agent lab\)\. The Mine view hides them.*Mark as mine reverses it/);
  });
  await test('Mark as mine clears the label; a typed label is trimmed and an unprintable one is never sent',async()=>{
    const s=library();s.run("assetState.assets.forEach(a=>{a.run_label='Agent lab';});chooseAssetSource('all');assetSelection=new Set(['a1'])");
    let p=bulkClick(s,'mine');assert.deepEqual(s.metadata(0),{ids:['a1'],action:'edit',run_label:null});s.accept(0);await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a1').run_label"),null);assert.match(s.el('#assetMessage').textContent,/^Marked 1 as yours; their run label is cleared/);
    s.run("assetSelection=new Set(['a1'])");s.el('#bulkRunLabel').value='bad\tlabel';await bulkClick(s,'agent_run');
    assert.equal(s.writes.length,1);assert.match(s.el('#assetMessage').textContent,/1 to 80 printable characters.*Nothing was changed/);
    s.el('#bulkRunLabel').value='  Night lab  ';p=bulkClick(s,'agent_run');assert.equal(s.payload(1).run_label,'Night lab');s.accept(1);await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a1').run_label"),'Night lab');
  });
  await test('A refused source command is reported and never marks the loaded assets',async()=>{
    const s=library();s.run("assetSelection=new Set(['a0'])");const p=bulkClick(s,'agent_run');
    const e=Error('Run label must be null or printable text of 1 to 80 characters');e.status=400;e.data={code:'invalid_asset_command'};s.writes[0].reject(e);await p;
    assert.equal(s.run("assetState.assets[0].run_label??null"),null);assert.match(s.el('#assetMessage').textContent,/refused/);
  });
  await test('Closing the asset dialog returns focus to the card that opened it, never stealing it from elsewhere',()=>{
    const s=library();s.run("globalThis.__focus=[];globalThis.__opener={isConnected:true,focus(){__focus.push('opener');}};document.body={};document.activeElement=__opener;openAsset('a0');document.activeElement=document.body");
    s.el('#assetDialog').close();assert.deepEqual(s.run('JSON.stringify(__focus)'),'["opener"]');
    // A re-rendered card is found by its asset id when the original node is gone.
    s.run("__opener.isConnected=false;document.activeElement=__opener;openAsset('a1');document.activeElement=document.body;document.querySelectorAll=q=>q==='#assetGrid [data-asset-open]'?[{dataset:{assetOpen:'a0'},focus(){__focus.push('a0');}},{dataset:{assetOpen:'a1'},focus(){__focus.push('a1');}}]:[]");
    s.el('#assetDialog').close();assert.deepEqual(s.run('JSON.stringify(__focus)'),'["opener","a1"]');
    s.run("document.activeElement=__opener;openAsset('a2');document.activeElement={id:'elsewhere'}");s.el('#assetDialog').close();assert.deepEqual(s.run('JSON.stringify(__focus)'),'["opener","a1"]');
  });
  await test('Refresh shows its busy state and waits for a background read instead of dropping the click',async()=>{
    const s=library();s.el('#workspaceRefresh').textContent='Refresh assets';
    s.run("globalThis.__reads=[];refreshAssets=async()=>{__reads.push([$('#workspaceRefresh').disabled,$('#workspaceRefresh').textContent]);return true;};assetRefreshing=true");
    const p=s.el('#workspaceRefresh').onclick();
    assert.equal(s.el('#workspaceRefresh').disabled,true);assert.equal(s.el('#workspaceRefresh').textContent,'Refreshing…');assert.equal(s.run('__reads.length'),0);
    assert.equal(await s.el('#workspaceRefresh').onclick(),false);
    s.run('assetRefreshing=false');[...s.timers.values()].at(-1)();await p;
    assert.equal(s.run('JSON.stringify(__reads)'),'[[true,"Refreshing…"]]');
    assert.equal(s.el('#workspaceRefresh').disabled,false);assert.equal(s.el('#workspaceRefresh').textContent,'Refresh assets');
    assert.match(s.el('#assetMessage').textContent,/Library refreshed: 3 active assets/);
  });
  console.log(`Asset library contracts: ${passed} passed, ${failed} failed`);if(failed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
